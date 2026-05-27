"""
Tests for the Sentinel-1 RTC SAR adapter.

Covers:
- STAC search success → newest scene picked
- STAC search empty → returns None (fallback)
- STAC network failure → returns None
- VV/VH missing from assets → returns None
- Raster read returns None for one band → returns None
- Happy path: known VV + VH means produce the expected RVI
- RVI clipping when speckle yields an out-of-range value
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from jeevn.infrastructure.data_sources import sar as sar_mod
from jeevn.infrastructure.data_sources.sar import Sentinel1Client


# ── STAC search-result fixtures ────────────────────────────────────────────

def _feature(scene_id: str, iso_date: str, with_assets: bool = True) -> dict:
    base = {
        "id": scene_id,
        "properties": {"datetime": iso_date},
        "assets": {},
    }
    if with_assets:
        base["assets"] = {
            "vv": {"href": f"https://example.com/{scene_id}_vv.tif"},
            "vh": {"href": f"https://example.com/{scene_id}_vh.tif"},
        }
    return base


def _mock_stac_post(features: list):
    """Build a `requests.post` patch that returns the given features."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value={"features": features})
    return patch.object(sar_mod.requests, "post", return_value=resp)


def _mock_sas_token(token: str = ""):
    """Patch the SAS token fetch — returns the given token (or empty)."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value={"token": token})
    return patch.object(sar_mod.requests, "get", return_value=resp)


# ── STAC integration tests ─────────────────────────────────────────────────

def test_fetch_latest_rvi_returns_none_when_no_scenes_found():
    with _mock_stac_post([]):
        result = Sentinel1Client.fetch_latest_rvi(29.92, 73.97)
    assert result is None


def test_fetch_latest_rvi_returns_none_on_stac_failure():
    with patch.object(sar_mod.requests, "post", side_effect=Exception("DNS fail")):
        result = Sentinel1Client.fetch_latest_rvi(29.92, 73.97)
    assert result is None


def test_fetch_latest_rvi_picks_newest_scene():
    """When multiple scenes match, the one with the latest datetime wins."""
    features = [
        _feature("S1_older",  "2026-05-10T00:00:00Z"),
        _feature("S1_newest", "2026-05-19T01:08:38Z"),
        _feature("S1_middle", "2026-05-15T00:00:00Z"),
    ]
    with _mock_stac_post(features), _mock_sas_token(""):
        # Patch the raster sampler so we don't hit the network.
        with patch.object(sar_mod, "_sample_mean", side_effect=[0.05, 0.10]):
            result = Sentinel1Client.fetch_latest_rvi(29.92, 73.97)

    assert result is not None
    assert result["scene_id"] == "S1_newest"
    assert result["scene_date"] == "2026-05-19"
    assert result["source"] == "sentinel-1-rtc"


def test_fetch_latest_rvi_returns_none_when_vv_or_vh_missing():
    features = [_feature("S1_partial", "2026-05-19T00:00:00Z", with_assets=False)]
    with _mock_stac_post(features), _mock_sas_token(""):
        result = Sentinel1Client.fetch_latest_rvi(29.92, 73.97)
    assert result is None


def test_fetch_latest_rvi_returns_none_when_raster_read_fails():
    """If `_sample_mean` returns None for either band → adapter returns None."""
    features = [_feature("S1_one", "2026-05-19T00:00:00Z")]
    with _mock_stac_post(features), _mock_sas_token(""):
        with patch.object(sar_mod, "_sample_mean", side_effect=[None, 0.10]):
            result = Sentinel1Client.fetch_latest_rvi(29.92, 73.97)
    assert result is None


# ── RVI math ───────────────────────────────────────────────────────────────

def test_rvi_formula_known_means():
    """RVI = 4·VH / (VV + VH).
    With VV=0.10, VH=0.04 (typical bare-soil values, linear power):
        RVI = 4 * 0.04 / 0.14 = 0.16 / 0.14 ≈ 1.143
    Clipped to 1.5; rounded to 3 decimals.
    """
    features = [_feature("S1_one", "2026-05-19T00:00:00Z")]
    with _mock_stac_post(features), _mock_sas_token(""):
        with patch.object(sar_mod, "_sample_mean", side_effect=[0.10, 0.04]):
            result = Sentinel1Client.fetch_latest_rvi(29.92, 73.97)
    assert result is not None
    assert result["rvi"] == pytest.approx(1.143, abs=0.001)


def test_rvi_low_for_dense_canopy():
    """High VV + lower VH ratio → low RVI (which is counter-intuitive vs the
    name, but consistent with the formula's behaviour: when VH << VV the
    surface is more specular/smooth, e.g., bare or sparse canopy).
    """
    features = [_feature("S1_one", "2026-05-19T00:00:00Z")]
    with _mock_stac_post(features), _mock_sas_token(""):
        with patch.object(sar_mod, "_sample_mean", side_effect=[0.20, 0.02]):
            # RVI = 4 * 0.02 / 0.22 = 0.08 / 0.22 ≈ 0.364
            result = Sentinel1Client.fetch_latest_rvi(29.92, 73.97)
    assert result is not None
    assert result["rvi"] == pytest.approx(0.364, abs=0.001)


def test_rvi_clipped_to_upper_bound_on_speckle():
    """If a speckle artefact pushes VH > VV by a wide margin (VH/VV >>>),
    RVI = 4 * VH / (VV + VH) -> 4 as VV -> 0. We cap at 1.5 to defang.
    """
    features = [_feature("S1_speckle", "2026-05-19T00:00:00Z")]
    with _mock_stac_post(features), _mock_sas_token(""):
        with patch.object(sar_mod, "_sample_mean", side_effect=[0.001, 0.5]):
            result = Sentinel1Client.fetch_latest_rvi(29.92, 73.97)
    # Raw RVI ≈ 4 * 0.5 / 0.501 ≈ 3.99; clipped to 1.5
    assert result["rvi"] == 1.5


def test_rvi_returns_none_when_both_means_are_zero():
    """Zero denom → guard returns None instead of dividing by zero."""
    features = [_feature("S1_zeros", "2026-05-19T00:00:00Z")]
    with _mock_stac_post(features), _mock_sas_token(""):
        # _sample_mean already filters out zeros; if both return None
        # the adapter returns None earlier. Belt-and-braces test: even
        # with both returning 0 the adapter must not crash.
        with patch.object(sar_mod, "_sample_mean", side_effect=[0.0, 0.0]):
            result = Sentinel1Client.fetch_latest_rvi(29.92, 73.97)
    assert result is None
