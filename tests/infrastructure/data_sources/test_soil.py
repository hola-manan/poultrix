"""
Tests for the SoilGrids-backed soil data adapter:

- USDA texture classifier — known reference cases + the Ganganagar real
  values pulled from SoilGrids
- Depth-weighted 0–30 cm aggregation
- d_factor unit conversion (phh2o pH*10, soc dg/kg, bdod cg/cm³)
- SOC g/kg → % normalisation
- Per-property `_fabricated_fields` shape on both real-fetch and fallback paths
- Whole-fetch fallback when SoilGrids is unreachable
"""

from unittest.mock import patch

import pytest

from jeevn.infrastructure.data_sources import soil as soil_mod
from jeevn.infrastructure.data_sources.soil import (
    SoilDataFetcher,
    SoilGridsClient,
    classify_usda_texture,
    infiltration_from_texture,
    whc_from_texture,
    _convert_to_target_units,
    _depth_weighted_mean,
    _normalise_soc_to_percent,
)


# ── Texture classifier ─────────────────────────────────────────────────────

@pytest.mark.parametrize("sand,silt,clay,expected", [
    (100, 0, 0,    "sand"),
    (80, 12, 8,    "loamy sand"),
    (60, 30, 10,   "sandy loam"),
    (40, 40, 20,   "loam"),
    (20, 60, 20,   "silt loam"),
    (5, 90, 5,     "silt"),
    (50, 20, 30,   "sandy clay loam"),
    (30, 35, 35,   "clay loam"),
    (50, 5, 45,    "sandy clay"),
    (10, 40, 50,   "silty clay"),
    (15, 15, 70,   "clay"),
    # Ganganagar real SoilGrids values — sits at the loam/sandy-clay-loam
    # boundary; silt 29.4 > 28 keeps it in `loam`.
    (47.5, 29.4, 23.0, "loam"),
])
def test_classify_usda_texture(sand, silt, clay, expected):
    assert classify_usda_texture(sand, silt, clay) == expected


def test_whc_and_infiltration_from_texture():
    # Sandy soils drain fast and hold little water; clays the opposite.
    assert whc_from_texture("sand") < whc_from_texture("loam") < whc_from_texture("silty clay loam")
    assert infiltration_from_texture("sand") > infiltration_from_texture("loam") > infiltration_from_texture("clay")


def test_unknown_texture_falls_back_to_loam_values():
    assert whc_from_texture("nonsense") == whc_from_texture("loam")
    assert infiltration_from_texture("nonsense") == infiltration_from_texture("loam")


# ── Aggregation + unit conversion ──────────────────────────────────────────

def test_depth_weighted_mean_weights_by_thickness():
    # 0-5cm=10, 5-15cm=20, 15-30cm=30. Weights 5/10/15.
    # Expected: (10*5 + 20*10 + 30*15) / 30 = (50+200+450)/30 = 700/30 ≈ 23.33
    result = _depth_weighted_mean([
        {"label": "0-5cm",  "values": {"mean": 10}},
        {"label": "5-15cm", "values": {"mean": 20}},
        {"label": "15-30cm","values": {"mean": 30}},
    ])
    assert result == pytest.approx(23.333, rel=1e-3)


def test_depth_weighted_mean_skips_missing_values():
    result = _depth_weighted_mean([
        {"label": "0-5cm",  "values": {"mean": None}},
        {"label": "5-15cm", "values": {"mean": 20}},
        {"label": "15-30cm","values": {"mean": 30}},
    ])
    # Only 5-15 and 15-30 contribute. (20*10 + 30*15) / 25 = 650/25 = 26.0
    assert result == pytest.approx(26.0)


def test_depth_weighted_mean_returns_none_when_all_missing():
    assert _depth_weighted_mean([
        {"label": "0-5cm",  "values": {"mean": None}},
        {"label": "5-15cm", "values": {"mean": None}},
    ]) is None


def test_d_factor_unit_conversion():
    # phh2o: raw 77 (= pH*10) → 7.7 pH
    layer = {"unit_measure": {"d_factor": 10}}
    assert _convert_to_target_units(layer, 77) == pytest.approx(7.7)
    # bdod: raw 147 (= cg/cm³) → 1.47 g/cm³
    layer = {"unit_measure": {"d_factor": 100}}
    assert _convert_to_target_units(layer, 147) == pytest.approx(1.47)


def test_soc_g_per_kg_to_percent():
    # 1 g/kg = 0.1%
    assert _normalise_soc_to_percent(6.18) == pytest.approx(0.618, rel=1e-3)
    assert _normalise_soc_to_percent(0) == 0.0


# ── SoilGridsClient.fetch — happy path with mocked response ────────────────

def _mock_soilgrids_response_ganganagar():
    """Mimics the real SoilGrids v2.0 response for Ganganagar (29.9, 73.9)
    that we live-verified against the API on 2026-05-14.
    """
    return {
        "properties": {
            "layers": [
                {"name": "phh2o", "unit_measure": {"d_factor": 10},
                 "depths": [
                     {"label": "0-5cm",  "values": {"mean": 77}},
                     {"label": "5-15cm", "values": {"mean": 77}},
                     {"label": "15-30cm","values": {"mean": 77}},
                 ]},
                {"name": "bdod", "unit_measure": {"d_factor": 100},
                 "depths": [
                     {"label": "0-5cm",  "values": {"mean": 146}},
                     {"label": "5-15cm", "values": {"mean": 147}},
                     {"label": "15-30cm","values": {"mean": 147}},
                 ]},
                {"name": "cec", "unit_measure": {"d_factor": 10},
                 "depths": [
                     {"label": "0-5cm",  "values": {"mean": 166}},
                     {"label": "5-15cm", "values": {"mean": 166}},
                     {"label": "15-30cm","values": {"mean": 165}},
                 ]},
                {"name": "clay", "unit_measure": {"d_factor": 10},
                 "depths": [
                     {"label": "0-5cm",  "values": {"mean": 214}},
                     {"label": "5-15cm", "values": {"mean": 212}},
                     {"label": "15-30cm","values": {"mean": 248}},
                 ]},
                {"name": "sand", "unit_measure": {"d_factor": 10},
                 "depths": [
                     {"label": "0-5cm",  "values": {"mean": 492}},
                     {"label": "5-15cm", "values": {"mean": 494}},
                     {"label": "15-30cm","values": {"mean": 457}},
                 ]},
                {"name": "silt", "unit_measure": {"d_factor": 10},
                 "depths": [
                     {"label": "0-5cm",  "values": {"mean": 294}},
                     {"label": "5-15cm", "values": {"mean": 294}},
                     {"label": "15-30cm","values": {"mean": 295}},
                 ]},
                {"name": "soc", "unit_measure": {"d_factor": 10},
                 "depths": [
                     {"label": "0-5cm",  "values": {"mean": 106}},
                     {"label": "5-15cm", "values": {"mean": 60}},
                     {"label": "15-30cm","values": {"mean": 45}},
                 ]},
            ]
        }
    }


def test_soilgrids_client_parses_ganganagar_correctly():
    """End-to-end parse: mocked SoilGrids JSON → real-world units, 0-30cm."""
    mock_resp = type("R", (), {
        "raise_for_status": lambda self: None,
        "json": lambda self: _mock_soilgrids_response_ganganagar(),
    })()
    with patch.object(soil_mod.requests, "get", return_value=mock_resp):
        result = SoilGridsClient.fetch(lat=29.9, lon=73.9)

    assert result is not None
    # pH constant at 77/10 = 7.7 across all depths
    assert result["ph"] == pytest.approx(7.7)
    # Bulk density: weighted (146*5 + 147*10 + 147*15) / 30 / 100 ≈ 1.468
    assert result["bulk_density"] == pytest.approx(1.47, abs=0.01)
    # CEC: (166*5 + 166*10 + 165*15) / 30 / 10 ≈ 16.55
    assert result["cec"] == pytest.approx(16.55, abs=0.05)
    # Clay: (214*5 + 212*10 + 248*15) / 30 / 10 ≈ 23.03
    assert result["clay_percent"] == pytest.approx(23.0, abs=0.1)
    # SOC: (106*5 + 60*10 + 45*15) / 30 = 60.17 g/kg → /10 = 6.02%? No!
    # 60.17 g/kg / 10 = 6.017 in our normalise step which converts g/kg → %.
    # Actually 60.17 g/kg = 6.017 % (since 1 g/kg = 0.1 %).
    assert result["organic_carbon_percent"] == pytest.approx(0.602, abs=0.01)


def test_soilgrids_client_returns_none_on_network_error():
    with patch.object(soil_mod.requests, "get", side_effect=Exception("DNS fail")):
        assert SoilGridsClient.fetch(lat=29.9, lon=73.9) is None


# ── Public adapter — fabricated-field flags ────────────────────────────────

def test_fetch_soil_data_marks_real_fields_not_fabricated():
    mock_resp = type("R", (), {
        "raise_for_status": lambda self: None,
        "json": lambda self: _mock_soilgrids_response_ganganagar(),
    })()
    with patch.object(soil_mod.requests, "get", return_value=mock_resp):
        soil = SoilDataFetcher.fetch_soil_data(29.9, 73.9, "Ganganagar")

    fields = soil["_fabricated_fields"]
    assert fields["ph"] is False
    assert fields["organic_carbon_percent"] is False
    assert fields["bulk_density"] is False
    assert fields["cec"] is False
    assert fields["sand_percent"] is False
    assert fields["silt_percent"] is False
    assert fields["clay_percent"] is False
    # texture, WHC, infiltration are derived from real sand/silt/clay
    assert fields["texture"] is False
    assert fields["water_holding_capacity"] is False
    assert fields["infiltration_rate"] is False
    # EC and soil moisture have no real source yet
    assert fields["ec"] is True
    assert fields["soil_moisture_current"] is True


def test_fetch_soil_data_marks_all_fields_fabricated_on_network_failure():
    with patch.object(soil_mod.requests, "get", side_effect=Exception("API down")):
        soil = SoilDataFetcher.fetch_soil_data(29.9, 73.9, "Ganganagar")

    fields = soil["_fabricated_fields"]
    # Every soil property is fabricated when SoilGrids is unreachable
    assert all(fields.values()), f"Expected all-True, got: {fields}"


def test_fetch_soil_data_keeps_real_value_overlays():
    """Real pH should overwrite the regional template's hardcoded pH."""
    mock_resp = type("R", (), {
        "raise_for_status": lambda self: None,
        "json": lambda self: _mock_soilgrids_response_ganganagar(),
    })()
    with patch.object(soil_mod.requests, "get", return_value=mock_resp):
        soil = SoilDataFetcher.fetch_soil_data(29.9, 73.9, "Ganganagar")

    # Ganganagar template said pH 7.2; SoilGrids says 7.7
    assert soil["properties"]["ph"] == pytest.approx(7.7)
    # OC: template said 0.14%; SoilGrids says ~0.60%
    assert soil["properties"]["organic_carbon_percent"] == pytest.approx(0.6, abs=0.05)


# ── Built-up-land detection ────────────────────────────────────────────────

def _mock_soilgrids_response_all_null():
    """Simulates SoilGrids responding HTTP 200 but with every depth's
    `mean` value being None — the signal that the query point is in
    SoilGrids' land-mask exclusion zone (urban / water / rock).
    """
    null_depths = [
        {"label": "0-5cm",   "values": {"mean": None}},
        {"label": "5-15cm",  "values": {"mean": None}},
        {"label": "15-30cm", "values": {"mean": None}},
    ]
    return {
        "properties": {
            "layers": [
                {"name": "phh2o", "unit_measure": {"d_factor": 10}, "depths": null_depths},
                {"name": "soc",   "unit_measure": {"d_factor": 10}, "depths": null_depths},
                {"name": "bdod",  "unit_measure": {"d_factor": 100}, "depths": null_depths},
                {"name": "sand",  "unit_measure": {"d_factor": 10}, "depths": null_depths},
                {"name": "silt",  "unit_measure": {"d_factor": 10}, "depths": null_depths},
                {"name": "clay",  "unit_measure": {"d_factor": 10}, "depths": null_depths},
                {"name": "cec",   "unit_measure": {"d_factor": 10}, "depths": null_depths},
            ]
        }
    }


def test_client_returns_no_data_marker_for_urban_centroid():
    """HTTP 200 with all-null means → returns a sentinel dict, not None."""
    mock_resp = type("R", (), {
        "raise_for_status": lambda self: None,
        "json": lambda self: _mock_soilgrids_response_all_null(),
    })()
    with patch.object(soil_mod.requests, "get", return_value=mock_resp):
        result = SoilGridsClient.fetch(lat=29.9248, lon=73.8656)
    assert result == {"_no_data_in_land_mask": True}


def test_fetch_soil_data_marks_aoi_in_built_up_land_when_centroid_is_null():
    """All values stay fabricated AND _aoi_in_built_up_land flag is set."""
    mock_resp = type("R", (), {
        "raise_for_status": lambda self: None,
        "json": lambda self: _mock_soilgrids_response_all_null(),
    })()
    with patch.object(soil_mod.requests, "get", return_value=mock_resp):
        soil = SoilDataFetcher.fetch_soil_data(29.9248, 73.8656, "Ganganagar")

    assert soil["_aoi_in_built_up_land"] is True
    # Every property remains fabricated since we explicitly do NOT overlay
    # distant pixels' data — see memory feedback_no_data_in_city.
    assert all(soil["_fabricated_fields"].values())


def test_fetch_soil_data_does_not_mark_built_up_when_real_values_returned():
    """Happy path: real data → in_built_up_land is False."""
    mock_resp = type("R", (), {
        "raise_for_status": lambda self: None,
        "json": lambda self: _mock_soilgrids_response_ganganagar(),
    })()
    with patch.object(soil_mod.requests, "get", return_value=mock_resp):
        soil = SoilDataFetcher.fetch_soil_data(29.9, 73.9, "Ganganagar")
    assert soil["_aoi_in_built_up_land"] is False


def test_fetch_soil_data_does_not_mark_built_up_on_network_failure():
    """Network failure is different from built-up land — distinguishable."""
    with patch.object(soil_mod.requests, "get", side_effect=Exception("DNS fail")):
        soil = SoilDataFetcher.fetch_soil_data(29.9, 73.9, "Ganganagar")
    assert soil["_aoi_in_built_up_land"] is False
    # All properties are fabricated, same as the built-up case — but the
    # _aoi_in_built_up_land flag distinguishes "service down" from "AOI in
    # built-up land".
    assert all(soil["_fabricated_fields"].values())
