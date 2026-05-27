"""
Synthetic Aperture Radar (SAR) data adapter — Sentinel-1.

Queries Microsoft Planetary Computer's STAC catalogue for the most-recent
Sentinel-1 RTC (Radiometrically Terrain Corrected) scene over the AOI,
reads VV + VH backscatter at the centroid, and computes the Radar
Vegetation Index (RVI = 4·VH / (VV + VH)).

RTC values are in linear power units (γ0), so the RVI formula applies
directly without a dB→linear conversion. Sentinel-1 GRD (the non-RTC
variant) would need calibration first; we explicitly choose RTC to avoid
that complexity.

Used by the advisory service to replace the fabricated RVI default with
a real radar measurement when a recent scene exists. Falls back to
fabricated when STAC is unreachable or no scene found in the last
`days_back` window.

NISAR L-band SAR (when it graduates from Beta — see task #4) will live in
this same module as a higher-priority source: Sentinel-1 for temporal
frequency (C-band penetrates only the top few cm and is attenuated by
dense canopy), NISAR for canopy-penetrating L-band measurements.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import requests


# ── MPC STAC endpoints ─────────────────────────────────────────────────────
_STAC_SEARCH_URL = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
_SAS_TOKEN_URL = (
    "https://planetarycomputer.microsoft.com/api/sas/v1/token/sentinel-1-rtc"
)
_COLLECTION = "sentinel-1-rtc"
_REQUEST_TIMEOUT_S = 30

# How far back to look for a Sentinel-1 RTC scene. Sentinel-1A alone has
# a 12-day repeat; combined with 1C it drops to ~6 days at most latitudes.
# 10 days is a comfortable window that almost always finds a scene.
_DEFAULT_DAYS_BACK = 10

# Sample window around the AOI centroid: 5 x 5 pixels at 20 m native
# resolution = 100 m x 100 m. Averages out SAR speckle without smoothing
# across heterogeneous parcels.
_SAMPLE_WINDOW_PIXELS = 5


# ── STAC query + SAS signing ───────────────────────────────────────────────
def _stac_search(lat: float, lon: float, days_back: int) -> list:
    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=days_back)
    body = {
        "collections": [_COLLECTION],
        "intersects": {"type": "Point", "coordinates": [lon, lat]},
        "datetime": (
            f"{start_dt.strftime('%Y-%m-%d')}T00:00:00Z/"
            f"{end_dt.strftime('%Y-%m-%d')}T23:59:59Z"
        ),
        "limit": 10,
    }
    response = requests.post(_STAC_SEARCH_URL, json=body, timeout=_REQUEST_TIMEOUT_S)
    response.raise_for_status()
    return response.json().get("features", [])


def _sas_token() -> str:
    """Get a Planetary Computer SAS token for the sentinel-1-rtc container.
    Without it, asset hrefs return 403 outside of MPC compute.
    """
    try:
        r = requests.get(_SAS_TOKEN_URL, timeout=10)
        r.raise_for_status()
        return r.json().get("token", "") or ""
    except Exception as e:
        print(f"[WARN] MPC SAS token fetch failed (continuing unsigned): {e}")
        return ""


def _sign_href(href: str, token: str) -> str:
    if not token or "?" in href:
        return href
    return f"{href}?{token}"


# ── Raster sampling ────────────────────────────────────────────────────────
def _sample_mean(href: str, lat: float, lon: float,
                 window_px: int = _SAMPLE_WINDOW_PIXELS) -> Optional[float]:
    """Read a (window_px x window_px) pixel window around the (lat, lon)
    centroid from a Cloud-Optimized GeoTIFF accessed via /vsicurl/ HTTP
    range reads, and return the mean of valid samples (linear power).
    """
    import rasterio  # noqa: WPS433 — intentional lazy import
    from rasterio.warp import transform as warp_transform

    try:
        with rasterio.open(f"/vsicurl/{href}") as ds:
            # Reproject lat/lon into the raster's CRS to find the pixel index.
            xs, ys = warp_transform(
                "EPSG:4326", ds.crs, [lon], [lat],
            )
            row, col = ds.index(xs[0], ys[0])
            half = window_px // 2
            row_off = max(0, row - half)
            col_off = max(0, col - half)
            row_end = min(ds.height, row + half + 1)
            col_end = min(ds.width, col + half + 1)
            if row_off >= row_end or col_off >= col_end:
                return None
            window = ((row_off, row_end), (col_off, col_end))
            arr = ds.read(1, window=window)
            nodata = ds.nodata

        flat = arr.astype("float64").ravel()
        if nodata is not None:
            flat = flat[flat != nodata]
        # Drop zero / negative power values too — SAR backscatter in linear
        # units must be > 0; zeros are typically masked or nodata leakage.
        flat = flat[flat > 0]
        if flat.size == 0:
            return None
        return float(flat.mean())
    except Exception as e:
        print(f"[WARN] Sentinel-1 sample read failed for {href[:80]}...: {e}")
        return None


# ── Polygon-clipped RVI raster (for the field map) ─────────────────────────
def _polygon_centroid(geojson: dict) -> Optional[tuple]:
    """Return (lat, lon) centroid of the first polygon in a GeoJSON
    Feature / FeatureCollection / bare geometry. Used as the STAC query
    point — the polygon itself is used for the raster mask.
    """
    if not geojson:
        return None
    geom = geojson
    if geojson.get("type") == "FeatureCollection":
        feats = geojson.get("features") or []
        if not feats:
            return None
        geom = feats[0].get("geometry") or {}
    elif geojson.get("type") == "Feature":
        geom = geojson.get("geometry") or {}
    if geom.get("type") != "Polygon":
        return None
    ring = geom.get("coordinates", [[]])[0]
    if not ring:
        return None
    lons = [p[0] for p in ring]
    lats = [p[1] for p in ring]
    return (sum(lats) / len(lats), sum(lons) / len(lons))


def _polygon_geometry(geojson: dict) -> Optional[dict]:
    if not geojson:
        return None
    if geojson.get("type") == "FeatureCollection":
        feats = geojson.get("features") or []
        if not feats:
            return None
        return feats[0].get("geometry")
    if geojson.get("type") == "Feature":
        return geojson.get("geometry")
    return geojson


def fetch_rvi_raster(
    geojson: dict, aoi_id: str, days_back: int = _DEFAULT_DAYS_BACK,
    output_dir: str = "data",
) -> Optional[Dict[str, Any]]:
    """Fetch Sentinel-1 RTC VV + VH bands clipped to the AOI polygon,
    compute per-pixel RVI, and write a GeoTIFF to `<output_dir>/rvi_<aoi_id>.tif`.

    Pixels outside the polygon are written as NaN so the colorizer can
    render them transparent.

    Returns `{rvi_raster, scene_date, scene_id, source}` (path string +
    metadata) or None on any failure.
    """
    centroid = _polygon_centroid(geojson)
    if centroid is None:
        return None
    lat, lon = centroid

    try:
        features = _stac_search(lat, lon, days_back)
    except Exception as e:
        print(f"[WARN] MPC STAC search failed: {e}")
        return None
    if not features:
        return None

    features.sort(
        key=lambda f: f["properties"].get("datetime", ""),
        reverse=True,
    )
    latest = features[0]
    scene_id = latest.get("id", "")
    scene_date_iso = latest["properties"].get("datetime", "")
    scene_date = scene_date_iso.split("T")[0] if scene_date_iso else ""

    assets = latest.get("assets") or {}
    vv_href = (assets.get("vv") or {}).get("href", "")
    vh_href = (assets.get("vh") or {}).get("href", "")
    if not vv_href or not vh_href:
        return None

    token = _sas_token()
    vv_signed = _sign_href(vv_href, token)
    vh_signed = _sign_href(vh_href, token)

    geom = _polygon_geometry(geojson)
    if geom is None:
        return None

    try:
        import rasterio  # noqa: WPS433
        from rasterio.mask import mask as rio_mask
        from rasterio.warp import transform_geom
        from rasterio.crs import CRS

        # Open VV first to learn the scene CRS, then reproject the polygon
        # into that CRS so mask() reads only the AOI window.
        with rasterio.open(f"/vsicurl/{vv_signed}") as src_vv:
            scene_crs = src_vv.crs
            geom_in_scene_crs = transform_geom(CRS.from_epsg(4326), scene_crs, geom)
            vv_arr, vv_transform = rio_mask(
                src_vv, [geom_in_scene_crs], crop=True, filled=True, nodata=np.nan,
                indexes=1, all_touched=False,
            )
            vv_nodata = src_vv.nodata

        with rasterio.open(f"/vsicurl/{vh_signed}") as src_vh:
            vh_arr, _ = rio_mask(
                src_vh, [geom_in_scene_crs], crop=True, filled=True, nodata=np.nan,
                indexes=1, all_touched=False,
            )
    except Exception as e:
        print(f"[WARN] Sentinel-1 raster mask read failed: {e}")
        return None

    vv = vv_arr.astype("float64")
    vh = vh_arr.astype("float64")
    if vv_nodata is not None:
        vv = np.where(vv == vv_nodata, np.nan, vv)
        vh = np.where(vh == vv_nodata, np.nan, vh)
    # Pixels at/below 0 in linear power are masked or calibration glitches.
    vv = np.where(vv > 0, vv, np.nan)
    vh = np.where(vh > 0, vh, np.nan)

    denom = vv + vh
    with np.errstate(invalid="ignore", divide="ignore"):
        rvi = 4.0 * vh / denom
    rvi = np.where(np.isfinite(rvi), rvi, np.nan)
    rvi = np.clip(rvi, 0.0, 1.5)

    # Write GeoTIFF preserving the masked transform (already in scene CRS).
    out_path = Path(output_dir) / f"rvi_{aoi_id}.tif"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import rasterio  # local re-bind for the writer
        profile = {
            "driver": "GTiff",
            "dtype": "float32",
            "count": 1,
            "height": rvi.shape[0],
            "width": rvi.shape[1],
            "crs": scene_crs,
            "transform": vv_transform,
            "nodata": float("nan"),
            "compress": "DEFLATE",
            "tiled": True,
            "blockxsize": 256,
            "blockysize": 256,
        }
        with rasterio.open(out_path, "w", **profile) as dst:
            dst.write(rvi.astype("float32"), 1)
    except Exception as e:
        print(f"[WARN] Sentinel-1 RVI raster write failed: {e}")
        return None

    return {
        "rvi_raster": str(out_path),
        "scene_date": scene_date,
        "scene_id": scene_id,
        "source": "sentinel-1-rtc",
    }


# ── Public client ──────────────────────────────────────────────────────────
class Sentinel1Client:
    """STAC-driven Sentinel-1 RTC client. Returns the latest scene's RVI
    at the AOI centroid, or None on any failure (network, no scenes,
    raster errors).
    """

    @staticmethod
    def fetch_latest_rvi(
        lat: float, lon: float, days_back: int = _DEFAULT_DAYS_BACK,
    ) -> Optional[Dict[str, Any]]:
        """Return `{rvi, scene_date, scene_id, source}` for the latest
        Sentinel-1 RTC scene over (lat, lon), or None if no usable scene
        was found in the last `days_back` days.
        """
        try:
            features = _stac_search(lat, lon, days_back)
        except Exception as e:
            print(f"[WARN] MPC STAC search failed: {e}")
            return None

        if not features:
            print(f"[INFO] No Sentinel-1 RTC scene at ({lat}, {lon}) "
                  f"in last {days_back} days")
            return None

        # Sort by datetime descending, take newest.
        features.sort(
            key=lambda f: f["properties"].get("datetime", ""),
            reverse=True,
        )
        latest = features[0]
        scene_id = latest.get("id", "")
        scene_date_iso = latest["properties"].get("datetime", "")
        scene_date = scene_date_iso.split("T")[0] if scene_date_iso else ""

        assets = latest.get("assets") or {}
        vv_asset = assets.get("vv") or {}
        vh_asset = assets.get("vh") or {}
        vv_href = vv_asset.get("href", "")
        vh_href = vh_asset.get("href", "")
        if not vv_href or not vh_href:
            print(f"[WARN] Sentinel-1 scene {scene_id} missing VV/VH assets")
            return None

        token = _sas_token()
        vv_signed = _sign_href(vv_href, token)
        vh_signed = _sign_href(vh_href, token)

        vv_mean = _sample_mean(vv_signed, lat, lon)
        vh_mean = _sample_mean(vh_signed, lat, lon)
        if vv_mean is None or vh_mean is None:
            return None

        denom = vv_mean + vh_mean
        if denom <= 0:
            return None

        # RVI = 4 * VH / (VV + VH), valued roughly in [0, 1] for vegetated land.
        # Bare soil RVI ~0.2; dense vegetation ~0.8-1.0+.
        rvi = 4.0 * vh_mean / denom
        # Clip to [0, 1.5] to defang any speckle / edge artefacts that could
        # produce wild values; downstream consumers expect a number near [0, 1].
        rvi_clipped = max(0.0, min(1.5, rvi))

        return {
            "rvi": round(rvi_clipped, 3),
            "scene_date": scene_date,
            "scene_id": scene_id,
            "source": "sentinel-1-rtc",
        }
