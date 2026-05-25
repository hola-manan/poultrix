"""
Tests for the terrain adapter (slope + aspect from elevation).

Covers:
- Horn (1981) 3x3 slope/aspect math — reference cases vs known geometry
- Aspect-degrees -> 8-point compass conversion (including 'flat')
- Open-Elevation client happy path + failure modes
- LocalDEMSampler bbox check + missing-file behaviour
- TerrainDataFetcher two-tier composition: primary -> fallback -> fabricated
"""
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from jeevn.infrastructure.data_sources import terrain as terrain_mod
from jeevn.infrastructure.data_sources.terrain import (
    LocalDEMSampler,
    OpenElevationClient,
    TerrainDataFetcher,
    aspect_degrees_to_compass,
    compute_slope_aspect,
    _grid_3x3,
)


# ── Horn (1981) slope/aspect math ──────────────────────────────────────────

def test_compute_slope_aspect_perfectly_flat():
    """Flat 3x3 -> slope 0%, aspect normalised to 0 (treated as flat by caller)."""
    flat = [100.0] * 9
    slope, aspect = compute_slope_aspect(flat, cellsize_m=30.0)
    assert slope == 0.0
    assert aspect == 0.0


def test_compute_slope_aspect_east_facing_100_percent():
    """Standard GIS aspect convention = downhill direction. An east-facing
    slope descends going east — elevations should be HIGH on the west,
    LOW on the east. dz/dx then points uphill (toward higher x = east),
    and aspect normalises to 90 (east).
    """
    east_facing = [
        60, 30, 0,
        60, 30, 0,
        60, 30, 0,
    ]
    slope, aspect = compute_slope_aspect(east_facing, cellsize_m=30.0)
    assert slope == pytest.approx(100.0, abs=0.5)
    assert aspect == pytest.approx(90.0, abs=0.5)


def test_compute_slope_aspect_south_facing():
    """Elevations decrease going south (row 0 = north, row 2 = south).
    A south-facing slope means terrain points / drops toward the south,
    so aspect should be ~180 degrees.
    """
    south = [
        60, 60, 60,   # north row (highest)
        30, 30, 30,
         0,  0,  0,   # south row (lowest)
    ]
    slope, aspect = compute_slope_aspect(south, cellsize_m=30.0)
    assert slope == pytest.approx(100.0, abs=0.5)
    assert aspect == pytest.approx(180.0, abs=0.5)


def test_compute_slope_aspect_rejects_bad_input():
    with pytest.raises(ValueError):
        compute_slope_aspect([1, 2, 3], cellsize_m=30.0)


# ── Aspect compass ────────────────────────────────────────────────────────

@pytest.mark.parametrize("deg,slope,expected", [
    (0,    5.0,  "N"),
    (45,   5.0,  "NE"),
    (90,   5.0,  "E"),
    (135,  5.0,  "SE"),
    (180,  5.0,  "S"),
    (225,  5.0,  "SW"),
    (270,  5.0,  "W"),
    (315,  5.0,  "NW"),
    (359,  5.0,  "N"),
    # Slope below the 0.5% threshold -> 'flat' regardless of degree
    (90,   0.1,  "flat"),
    (180,  0.0,  "flat"),
])
def test_aspect_compass(deg, slope, expected):
    assert aspect_degrees_to_compass(deg, slope) == expected


# ── Grid construction ────────────────────────────────────────────────────

def test_grid_3x3_centroid_is_middle():
    points = _grid_3x3(lat=20.0, lon=70.0, spacing_m=30.0)
    assert len(points) == 9
    # Index 4 is the centroid
    assert points[4] == (20.0, 70.0)


def test_grid_3x3_north_row_has_higher_lat():
    points = _grid_3x3(lat=20.0, lon=70.0, spacing_m=30.0)
    # Rows 0-2 are north of centroid; rows 6-8 are south
    assert all(p[0] > 20.0 for p in points[:3])
    assert all(p[0] < 20.0 for p in points[6:9])


# ── Open-Elevation client ─────────────────────────────────────────────────

def _mock_open_elevation_response(elevations):
    """Build a fake requests.Response-shaped object returning the given
    9 elevations in order.
    """
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value={
        "results": [
            {"latitude": 0.0, "longitude": 0.0, "elevation": float(e)}
            for e in elevations
        ]
    })
    return resp


def test_open_elevation_client_happy_path():
    resp = _mock_open_elevation_response([100, 100, 100, 100, 105, 110, 110, 110, 110])
    with patch.object(terrain_mod.requests, "post", return_value=resp):
        elevations = OpenElevationClient.fetch_3x3_grid(20.0, 70.0)
    assert elevations == [100, 100, 100, 100, 105, 110, 110, 110, 110]


def test_open_elevation_client_returns_none_on_http_failure():
    with patch.object(terrain_mod.requests, "post", side_effect=Exception("DNS fail")):
        assert OpenElevationClient.fetch_3x3_grid(20.0, 70.0) is None


def test_open_elevation_client_returns_none_when_results_truncated():
    """If the API returns fewer than 9 points, fail cleanly."""
    resp = _mock_open_elevation_response([100, 100, 100])
    with patch.object(terrain_mod.requests, "post", return_value=resp):
        assert OpenElevationClient.fetch_3x3_grid(20.0, 70.0) is None


# ── LocalDEMSampler ───────────────────────────────────────────────────────

def _reset_local_dem_cache():
    if LocalDEMSampler._dataset is not None:
        try:
            LocalDEMSampler._dataset.close()
        except Exception:
            pass
    LocalDEMSampler._dataset = None
    LocalDEMSampler._open_attempted = False


def test_local_dem_sampler_handles_missing_raster(monkeypatch, tmp_path):
    """Fresh clone where build_dem_clip.py hasn't been run yet — raster
    is absent and sampler returns None without raising.
    """
    bogus = tmp_path / "missing.tif"
    monkeypatch.setattr(terrain_mod, "_DEM_RASTER_PATH", bogus)
    _reset_local_dem_cache()
    assert LocalDEMSampler.fetch_3x3_grid(29.92, 73.97) is None
    _reset_local_dem_cache()  # let other tests see the real raster again


@pytest.mark.skipif(
    not (Path(__file__).resolve().parents[3] / "data" / "static" / "dem_india.tif").exists(),
    reason="Bundled DEM raster not present (run scripts/dev_smoke/build_dem_clip.py).",
)
def test_local_dem_sampler_returns_grid_for_india_aoi():
    """Default Ganganagar AOI is inside the India bbox; should return 9
    realistic elevations (Sri Ganganagar ~200 m above sea level).
    """
    _reset_local_dem_cache()
    grid = LocalDEMSampler.fetch_3x3_grid(29.92, 73.97)
    assert grid is not None
    assert len(grid) == 9
    # Ganganagar is roughly 170-250 m above sea level
    assert all(50 < e < 400 for e in grid), f"unexpected elevations: {grid}"


@pytest.mark.skipif(
    not (Path(__file__).resolve().parents[3] / "data" / "static" / "dem_india.tif").exists(),
    reason="Bundled DEM raster not present (run scripts/dev_smoke/build_dem_clip.py).",
)
def test_local_dem_sampler_returns_none_outside_india():
    _reset_local_dem_cache()
    # Brazil
    assert LocalDEMSampler.fetch_3x3_grid(-23.5, -46.6) is None
    # Iowa
    assert LocalDEMSampler.fetch_3x3_grid(42.0, -93.6) is None


# ── TerrainDataFetcher two-tier composition ────────────────────────────────

def test_fetch_terrain_uses_open_elevation_when_available():
    resp = _mock_open_elevation_response([200, 200, 200, 200, 200, 200, 200, 200, 200])
    with patch.object(terrain_mod.requests, "post", return_value=resp):
        result = TerrainDataFetcher.fetch_terrain(29.92, 73.97)
    assert result["source"] == "open-elevation"
    assert result["slope_percent"] == 0.0
    assert result["aspect_compass"] == "flat"
    assert result["elevation_m"] == 200.0
    assert result.get("_fabricated") is False or "_fabricated" not in result


def test_fetch_terrain_falls_back_to_bundled_dem_when_open_elevation_fails():
    """Open-Elevation fails -> bundled DEM provides values."""
    fake_grid = [180, 180, 180, 190, 200, 210, 220, 220, 220]
    with patch.object(terrain_mod.requests, "post", side_effect=Exception("API down")):
        with patch.object(LocalDEMSampler, "fetch_3x3_grid", return_value=fake_grid):
            result = TerrainDataFetcher.fetch_terrain(29.92, 73.97)
    assert result["source"] == "bundled-dem"
    assert result["elevation_m"] == 200.0  # centroid is index 4


def test_fetch_terrain_falls_back_to_fabricated_when_both_fail():
    """Both Open-Elevation AND bundled DEM unavailable -> fabricated."""
    with patch.object(terrain_mod.requests, "post", side_effect=Exception("API down")):
        with patch.object(LocalDEMSampler, "fetch_3x3_grid", return_value=None):
            result = TerrainDataFetcher.fetch_terrain(29.92, 73.97)
    assert result["source"] == "fabricated"
    assert result.get("_fabricated") is True
    # Default values from pseudo_satellite.DEFAULT_TERRAIN
    assert result["slope_percent"] == 0.5
    assert result["aspect_compass"] == "flat"
