"""Tests for the tiered N/P/K profile resolver."""

import gzip

import pytest

from jeevn.infrastructure.data_sources import soil_nutrients as sn


_FIXTURE_CSV = """state,district,n_low_pct,n_med_pct,n_high_pct,p_low_pct,p_med_pct,p_high_pct,k_low_pct,k_med_pct,k_high_pct
himachal pradesh,shimla,10,30,60,20,50,30,5,25,70
"""

_VILLAGE_FIXTURE = """state,district,village,n_low_pct,n_med_pct,n_high_pct,p_low_pct,p_med_pct,p_high_pct,k_low_pct,k_med_pct,k_high_pct
Himachal Pradesh,Shimla,Mashobra,90,8,2,30,50,20,10,40,50
"""


def _clear():
    sn._load_shc_table.cache_clear()
    sn._load_shc_village_table.cache_clear()


@pytest.fixture
def shc_table(tmp_path, monkeypatch):
    csv_path = tmp_path / "shc_district_npk.csv"
    csv_path.write_text(_FIXTURE_CSV, encoding="utf-8")
    monkeypatch.setattr(sn, "_SHC_CSV_PATH", csv_path)
    # Neutralise the (real, bundled) village table so district tests are hermetic.
    monkeypatch.setattr(sn, "_SHC_VILLAGE_PATH", tmp_path / "no_village.csv.gz")
    _clear()
    yield
    _clear()


def test_soil_test_tier_wins(shc_table):
    loc = {"state": "Himachal Pradesh", "district": "Shimla"}
    profile = sn.resolve_npk(loc, {}, soil_test={"N": "high", "P": 0.4})
    assert profile["N"]["source"] == "soil-test"
    assert profile["N"]["confidence"] == "high"
    assert profile["N"]["supply_fraction"] == 1.0
    # numeric fraction accepted directly
    assert profile["P"]["supply_fraction"] == 0.4


def test_shc_district_tier(shc_table):
    loc = {"state": "Himachal Pradesh", "district": "Shimla"}
    profile = sn.resolve_npk(loc, {})
    for nutrient in ("N", "P", "K"):
        assert profile[nutrient]["source"] == "shc-district"
        assert profile[nutrient]["confidence"] == "medium"


def test_village_tier_wins_then_falls_back_to_district(tmp_path, monkeypatch):
    dcsv = tmp_path / "d.csv"
    dcsv.write_text(_FIXTURE_CSV, encoding="utf-8")
    vgz = tmp_path / "v.csv.gz"
    with gzip.open(vgz, "wt", encoding="utf-8") as fh:
        fh.write(_VILLAGE_FIXTURE)
    monkeypatch.setattr(sn, "_SHC_CSV_PATH", dcsv)
    monkeypatch.setattr(sn, "_SHC_VILLAGE_PATH", vgz)
    _clear()

    # Known village → village tier (note case/spacing normalised).
    loc = {"state": "Himachal Pradesh", "district": "Shimla", "village": "mashobra"}
    profile = sn.resolve_npk(loc, {})
    assert profile["N"]["source"] == "shc-village"

    # Unknown village → cascade down to district.
    loc2 = {"state": "Himachal Pradesh", "district": "Shimla", "village": "Nowhere"}
    assert sn.resolve_npk(loc2, {})["N"]["source"] == "shc-district"
    _clear()
    # K skews High (5/25/70) → high supply fraction; N skews High too.
    assert profile["K"]["supply_fraction"] > profile["P"]["supply_fraction"]


def test_state_fallback_when_district_absent(shc_table):
    loc = {"state": "Himachal Pradesh", "district": "Kinnaur"}  # not in table
    profile = sn.resolve_npk(loc, {})
    assert profile["N"]["source"] == "shc-state"
    assert profile["N"]["confidence"] == "low"


def test_soilgrids_tier_when_no_shc(shc_table):
    loc = {"state": "Punjab", "district": "Ludhiana"}  # no SHC row for Punjab
    soil_props = {"total_nitrogen_g_per_kg": 0.3, "cec": 30.0}
    profile = sn.resolve_npk(loc, soil_props)
    assert profile["N"]["source"] == "soilgrids"
    assert profile["N"]["status"] == "low"
    assert profile["K"]["source"] == "soilgrids"
    assert profile["K"]["status"] == "high"
    # P has no SoilGrids proxy → omitted (caller keeps the constant, flagged).
    assert "P" not in profile


def test_disable_soilgrids_env(shc_table, monkeypatch):
    monkeypatch.setenv("DISABLE_SOILGRIDS_NPK", "1")
    loc = {"state": "Punjab", "district": "Ludhiana"}
    profile = sn.resolve_npk(loc, {"total_nitrogen_g_per_kg": 0.3, "cec": 30.0})
    assert profile == {}


def test_missing_csv_skips_shc(tmp_path, monkeypatch):
    monkeypatch.setattr(sn, "_SHC_CSV_PATH", tmp_path / "does_not_exist.csv")
    sn._load_shc_table.cache_clear()
    loc = {"state": "Himachal Pradesh", "district": "Shimla"}
    # No SHC, no soilgrids props, no soil test → empty profile (constant fallback).
    assert sn.resolve_npk(loc, {}) == {}
    sn._load_shc_table.cache_clear()
