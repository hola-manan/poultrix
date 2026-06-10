"""
Tests for the NISAR SME2 soil-moisture adapter.

The live pipeline (ASF search + Earthdata download + HDF5 read) is mocked
here so the suite needs no network or credentials. One opt-in integration
test runs against a real cached granule when present.
"""

import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from jeevn.infrastructure.data_sources import nisar as nisar_mod
from jeevn.infrastructure.data_sources.nisar import NisarSoilMoistureClient


def _fake_granule(scene="NISAR_L3_PR_SME2_test", start="2026-01-18T13:47:39Z"):
    g = MagicMock()
    g.properties = {
        "sceneName": scene,
        "fileName": scene + ".h5",
        "startTime": start,
    }
    return g


# ── No recent pass ──────────────────────────────────────────────────────────

def test_returns_none_when_no_granule_in_window():
    with patch.object(nisar_mod, "_find_latest_granule", return_value=None):
        assert NisarSoilMoistureClient.fetch_sm_at(29.92, 73.97) is None


def test_search_failure_returns_none():
    # _find_latest_granule swallows asf errors and returns None
    with patch("asf_search.search", side_effect=Exception("ASF down")):
        assert nisar_mod._find_latest_granule(29.92, 73.97, 14) is None


# ── No credentials ──────────────────────────────────────────────────────────

def test_download_skipped_without_credentials(monkeypatch):
    monkeypatch.delenv("EARTHDATA_USER", raising=False)
    monkeypatch.delenv("EARTHDATA_PASS", raising=False)
    with patch.object(nisar_mod, "_find_latest_granule", return_value=_fake_granule()):
        # Download returns None (no creds) -> whole fetch returns None
        assert NisarSoilMoistureClient.fetch_sm_at(29.92, 73.97) is None


# ── Happy path (mocked download + sample) ───────────────────────────────────

def test_happy_path_returns_sm_dict(monkeypatch, tmp_path):
    monkeypatch.setenv("EARTHDATA_USER", "u")
    monkeypatch.setenv("EARTHDATA_PASS", "p")
    fake_h5 = tmp_path / "g.h5"
    fake_h5.write_bytes(b"x" * 2_000_000)

    with patch.object(nisar_mod, "_find_latest_granule",
                      return_value=_fake_granule(start="2026-01-18T00:00:00Z")), \
         patch.object(nisar_mod, "_download_granule", return_value=fake_h5), \
         patch.object(nisar_mod, "_sample_sm",
                      return_value={"soil_moisture_m3m3": 0.226, "algorithm": "DSG",
                                    "quality_flag": 0}):
        result = NisarSoilMoistureClient.fetch_sm_at(29.92, 73.97)

    assert result is not None
    assert result["soil_moisture_m3m3"] == 0.226
    assert result["algorithm"] == "DSG"
    assert result["pass_date"] == "2026-01-18"
    assert result["source"] == "nisar-sme2"
    assert "test" in result["granule_id"].lower() or result["granule_id"]


def test_returns_none_when_sample_is_fill_or_out_of_coverage(monkeypatch, tmp_path):
    monkeypatch.setenv("EARTHDATA_USER", "u")
    monkeypatch.setenv("EARTHDATA_PASS", "p")
    fake_h5 = tmp_path / "g.h5"
    fake_h5.write_bytes(b"x" * 2_000_000)
    with patch.object(nisar_mod, "_find_latest_granule", return_value=_fake_granule()), \
         patch.object(nisar_mod, "_download_granule", return_value=fake_h5), \
         patch.object(nisar_mod, "_sample_sm", return_value=None):
        assert NisarSoilMoistureClient.fetch_sm_at(29.92, 73.97) is None


# ── Opt-in integration test against a real cached granule ───────────────────

_REAL_GRANULE = next(
    (p for p in (Path(__file__).resolve().parents[3] / "data" / "cache" / "nisar").glob("*.h5")
     if "QA_STATS" not in p.name),
    None,
) if (Path(__file__).resolve().parents[3] / "data" / "cache" / "nisar").exists() else None


@pytest.mark.skipif(_REAL_GRANULE is None, reason="No cached NISAR granule present.")
def test_sample_sm_against_real_granule():
    """Read SM at Ganganagar from a real downloaded SME2 granule."""
    result = nisar_mod._sample_sm(_REAL_GRANULE, 29.92, 73.97)
    assert result is not None
    assert 0.0 <= result["soil_moisture_m3m3"] <= 0.7  # plausible volumetric SM
    assert result["algorithm"] in ("DSG", "PMI", "TSR")
    assert result["quality_flag"] == 0


@pytest.mark.skipif(_REAL_GRANULE is None, reason="No cached NISAR granule present.")
def test_sample_sm_rejects_far_outside_coverage():
    """A point far from the granule footprint returns None."""
    assert nisar_mod._sample_sm(_REAL_GRANULE, -23.5, -46.6) is None  # Brazil
