"""
Terrain data adapter — slope + aspect from elevation.

Two-tier source design:

  1. PRIMARY: Open-Elevation REST API (keyless, anonymous, SRTM-backed).
     Queries a 3x3 grid of elevation points around the AOI centroid and
     computes slope + aspect locally using the Horn (1981) 3x3 kernel.

  2. FALLBACK: bundled ETOPO 2022 30 arc-sec India clip, sampled with
     rasterio. Used when Open-Elevation is unreachable. ~1 km precision
     is coarse but better than guessing.

  3. LAST RESORT: pseudo defaults (flat plain). Flagged via
     `_fabricated_fields` so the report surfaces the degraded data.

Output shape:
    {
        "slope_percent":    float,       # 0-100 (rise / run)
        "aspect_degrees":   float,       # 0-360, 0=N clockwise
        "aspect_compass":   str,         # one of {N, NE, E, SE, S, SW, W, NW, flat}
        "elevation_m":      float,       # centroid elevation
        "source":           str,         # "open-elevation" | "bundled-dem" | "fabricated"
    }

The composer in `aoi.py` hoists `_fabricated_fields["terrain.*"]` into
the top-level `_fabricated_sources` list so callers know the source.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from jeevn.infrastructure import pseudo_satellite


# ── Open-Elevation config ──────────────────────────────────────────────────
_OPEN_ELEVATION_URL = "https://api.open-elevation.com/api/v1/lookup"
_REQUEST_TIMEOUT_S = 15
_USER_AGENT = "Jeevn-MVP/0.1.0 (agricultural advisory)"

# 3x3 grid sample spacing. SRTM native resolution is ~30 m so 30 m here
# corresponds to ~1 pixel between samples — adequate for slope/aspect.
_GRID_SPACING_M = 30.0

# ── Bundled DEM (fallback) ─────────────────────────────────────────────────
_DEM_RASTER_PATH = (
    Path(__file__).resolve().parents[4] / "data" / "static" / "dem_india.tif"
)
# ETOPO 2022 is 30 arc-sec (~1 km). For the 3x3 sample around the centroid
# we step one cell at a time, giving slope/aspect over a ~3 km window.
_DEM_GRID_SPACING_M = 1000.0


# ── Aspect compass conversion ──────────────────────────────────────────────
_COMPASS_BANDS: List[Tuple[float, float, str]] = [
    (337.5, 360.0, "N"),
    (0.0,    22.5, "N"),
    (22.5,   67.5, "NE"),
    (67.5,  112.5, "E"),
    (112.5, 157.5, "SE"),
    (157.5, 202.5, "S"),
    (202.5, 247.5, "SW"),
    (247.5, 292.5, "W"),
    (292.5, 337.5, "NW"),
]


def aspect_degrees_to_compass(aspect_deg: float, slope_pct: float) -> str:
    """Convert aspect in degrees (0=N CW) to an 8-point compass label.
    When slope is essentially zero, aspect is undefined — return 'flat'.
    """
    if slope_pct < 0.5:
        return "flat"
    deg = aspect_deg % 360.0
    for low, high, name in _COMPASS_BANDS:
        if low <= deg < high:
            return name
    return "N"  # numerically defensive; should never hit


# ── Slope / aspect math (Horn 1981, 3x3 kernel) ────────────────────────────
def compute_slope_aspect(elevations_3x3: List[float], cellsize_m: float) -> Tuple[float, float]:
    """Compute (slope_percent, aspect_degrees) from a flat 9-element list
    laid out row-major as:

        [a b c        index 0 1 2
         d e f               3 4 5
         g h i]              6 7 8

    where `e` is the centroid and the rest are evenly spaced by `cellsize_m`
    in metres (north-up; row 0 is the northernmost row).

    Uses the standard Horn (1981) 3x3 kernel — matches GDAL/ArcGIS slope.

    Returns:
        slope_percent: rise/run as a percentage (0-100+)
        aspect_degrees: 0-360, measured clockwise from north (0=N, 90=E)
    """
    if len(elevations_3x3) != 9:
        raise ValueError("expected 9 elevations in 3x3 row-major order")

    a, b, c, d, e, f, g, h, i = elevations_3x3

    # Horn weighted partial derivatives
    dz_dx = ((c + 2 * f + i) - (a + 2 * d + g)) / (8.0 * cellsize_m)
    dz_dy = ((g + 2 * h + i) - (a + 2 * b + c)) / (8.0 * cellsize_m)

    slope_rise_run = math.sqrt(dz_dx * dz_dx + dz_dy * dz_dy)
    slope_percent = slope_rise_run * 100.0

    # Aspect: direction of steepest descent. atan2(dz/dy, -dz/dx) gives the
    # math-convention angle (counter-clockwise from east). Convert to
    # geographic convention (clockwise from north).
    if dz_dx == 0 and dz_dy == 0:
        aspect_degrees = 0.0
    else:
        aspect_radians = math.atan2(dz_dy, -dz_dx)
        aspect_degrees = math.degrees(aspect_radians)
        # atan2 returns [-180, 180]; convert to compass (0=N, CW positive)
        aspect_degrees = 90.0 - aspect_degrees
        if aspect_degrees < 0:
            aspect_degrees += 360.0

    return round(slope_percent, 2), round(aspect_degrees, 1)


# ── Lat/lon offsets for a 3x3 grid in metres ───────────────────────────────
def _grid_offsets_deg(lat: float, spacing_m: float) -> Tuple[float, float]:
    """Return (lat_delta, lon_delta) in degrees that correspond to
    `spacing_m` metres on the ground at the given latitude.

    Latitude: 1 deg = 111_320 m everywhere.
    Longitude: 1 deg = 111_320 * cos(lat) m.
    """
    lat_delta = spacing_m / 111_320.0
    lon_delta = spacing_m / (111_320.0 * max(0.01, math.cos(math.radians(lat))))
    return lat_delta, lon_delta


def _grid_3x3(lat: float, lon: float, spacing_m: float) -> List[Tuple[float, float]]:
    """Build the 3x3 (lat, lon) sample grid, row-major, north row first."""
    dlat, dlon = _grid_offsets_deg(lat, spacing_m)
    rows: List[Tuple[float, float]] = []
    for r in (1, 0, -1):  # north to south (lat decreasing)
        for c in (-1, 0, 1):  # west to east (lon increasing)
            rows.append((lat + r * dlat, lon + c * dlon))
    return rows


# ── Open-Elevation client (primary) ────────────────────────────────────────
class OpenElevationClient:
    """Keyless POST client for api.open-elevation.com."""

    @staticmethod
    def fetch_3x3_grid(lat: float, lon: float,
                       spacing_m: float = _GRID_SPACING_M
                       ) -> Optional[List[float]]:
        """Return 9 elevations (m) in row-major north-first order, or None
        on any HTTP / parse failure.
        """
        points = _grid_3x3(lat, lon, spacing_m)
        body = {"locations": [{"latitude": p[0], "longitude": p[1]} for p in points]}
        try:
            r = requests.post(
                _OPEN_ELEVATION_URL,
                json=body,
                headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
                timeout=_REQUEST_TIMEOUT_S,
            )
            r.raise_for_status()
            payload = r.json()
        except Exception as e:
            print(f"[WARN] Open-Elevation fetch failed: {e}")
            return None

        results = payload.get("results") or []
        if len(results) != 9:
            print(f"[WARN] Open-Elevation returned {len(results)} of 9 expected points")
            return None
        try:
            return [float(p["elevation"]) for p in results]
        except (KeyError, TypeError, ValueError) as e:
            print(f"[WARN] Open-Elevation parse failed: {e}")
            return None


# ── Bundled DEM sampler (fallback) ─────────────────────────────────────────
class LocalDEMSampler:
    """Reads the bundled ETOPO 2022 India clip from disk.

    Same lazy-open pattern as `SalinityRasterSampler` in `soil.py`. Holds
    one cached `rasterio.DatasetReader` for the process lifetime. Returns
    None when the raster is absent (fresh clone w/o build script run) or
    the AOI centroid is outside the raster bbox.
    """

    _dataset = None
    _open_attempted = False

    @classmethod
    def _get_dataset(cls):
        if cls._open_attempted:
            return cls._dataset
        cls._open_attempted = True
        try:
            import rasterio  # noqa: WPS433 — intentional lazy import
            if _DEM_RASTER_PATH.exists():
                cls._dataset = rasterio.open(_DEM_RASTER_PATH)
            else:
                print(
                    f"[WARN] DEM fallback raster not found at {_DEM_RASTER_PATH}; "
                    "run scripts/dev_smoke/build_dem_clip.py to generate it."
                )
        except Exception as e:
            print(f"[WARN] Could not open DEM raster: {e}")
        return cls._dataset

    @classmethod
    def fetch_3x3_grid(cls, lat: float, lon: float,
                       spacing_m: float = _DEM_GRID_SPACING_M
                       ) -> Optional[List[float]]:
        """Return 9 elevations from the bundled DEM in row-major
        north-first order, or None if out-of-coverage / raster missing.
        """
        ds = cls._get_dataset()
        if ds is None:
            return None

        left, bottom, right, top = ds.bounds
        if not (left <= lon <= right and bottom <= lat <= top):
            return None

        points = _grid_3x3(lat, lon, spacing_m)
        try:
            sampled = list(ds.sample([(p[1], p[0]) for p in points]))
        except Exception as e:
            print(f"[WARN] DEM sample failed at ({lat}, {lon}): {e}")
            return None

        try:
            elevations = [float(v[0]) for v in sampled]
        except (IndexError, TypeError, ValueError) as e:
            print(f"[WARN] DEM parse failed: {e}")
            return None

        # ETOPO uses a nodata sentinel for some ocean / void pixels; if any
        # of the 9 samples is wildly out of range, treat as no-data and let
        # the caller fall back.
        if any(e < -1000 or e > 9000 for e in elevations):
            return None
        return elevations


# ── Cellsize for the metric used during slope math ─────────────────────────
def _open_elevation_cellsize_m() -> float:
    return _GRID_SPACING_M


def _bundled_dem_cellsize_m() -> float:
    return _DEM_GRID_SPACING_M


# ── Public adapter ─────────────────────────────────────────────────────────
class TerrainDataFetcher:
    """Compose primary + fallback sources into a single terrain dict.

    Always returns a dict; never raises. The `source` field tells the caller
    which path produced the values, and `_fabricated_fields` (set by the
    composer in `aoi.py`) flips True only when even the bundled raster
    couldn't satisfy the request.
    """

    @staticmethod
    def fetch_terrain(lat: float, lon: float) -> Dict[str, Any]:
        # 1) Primary: Open-Elevation
        elevations = OpenElevationClient.fetch_3x3_grid(lat, lon)
        if elevations is not None:
            slope_pct, aspect_deg = compute_slope_aspect(
                elevations, _open_elevation_cellsize_m(),
            )
            return {
                "slope_percent": slope_pct,
                "aspect_degrees": aspect_deg,
                "aspect_compass": aspect_degrees_to_compass(aspect_deg, slope_pct),
                "elevation_m": round(elevations[4], 1),  # centroid is index 4
                "source": "open-elevation",
                "_fabricated": False,
            }

        # 2) Fallback: bundled DEM
        elevations = LocalDEMSampler.fetch_3x3_grid(lat, lon)
        if elevations is not None:
            slope_pct, aspect_deg = compute_slope_aspect(
                elevations, _bundled_dem_cellsize_m(),
            )
            return {
                "slope_percent": slope_pct,
                "aspect_degrees": aspect_deg,
                "aspect_compass": aspect_degrees_to_compass(aspect_deg, slope_pct),
                "elevation_m": round(elevations[4], 1),
                "source": "bundled-dem",
                "_fabricated": False,
            }

        # 3) Last resort: fabricated defaults
        defaults = pseudo_satellite.make_default_terrain()
        defaults["source"] = "fabricated"
        return defaults
