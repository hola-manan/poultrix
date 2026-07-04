"""
Tests that a fresh ground-sensor reading fuses into the AOI composer as the
top-priority soil-moisture source, overriding the Open-Meteo/modelled tier.
"""

from contextlib import ExitStack
from unittest.mock import patch

import pytest

from jeevn.infrastructure.data_sources import aoi as aoi_mod
from jeevn.infrastructure.data_sources.aoi import fetch_aoi_data
from jeevn.infrastructure.data_sources.soil import field_capacity_from_texture


def _stub_geocoding(lat, lon):
    return {"latitude": lat, "longitude": lon, "name": "Test", "city": "",
            "district": "", "state": "", "country": "India",
            "timezone": "Asia/Kolkata", "_fabricated": False}


def _stub_weather(sm_mean=0.20):
    return {
        "location": {"latitude": 29.9, "longitude": 74.0, "timezone": "Asia/Kolkata"},
        "daily": {"dates": ["2026-05-13"], "temp_max": [37.0], "temp_min": [25.0],
                  "temp_mean": [31.0], "rainfall": [0.0], "solar_radiation": [27.0],
                  "wind_speed": [8.0], "soil_moisture_0_to_7cm_mean": sm_mean},
        "_fabricated": False,
    }


def _stub_soil(texture="loam"):
    return {
        "location": {"latitude": 29.9, "longitude": 74.0, "name": "Test"},
        "properties": {"ph": 7.5, "ec": 0.5, "organic_carbon_percent": 0.5,
                       "sand_percent": 40, "silt_percent": 40, "clay_percent": 20,
                       "texture": texture, "cec": 16.0, "bulk_density": 1.4,
                       "soil_moisture_current": 0.65},
        "_fabricated_fields": {"texture": False, "cec": False,
                               "soil_moisture_current": True},
        "_aoi_in_built_up_land": False,
    }


def _run(sensor_soil_moisture=None, sensor_is_fraction=False, soil_test=None):
    with ExitStack() as stack:
        stack.enter_context(patch.object(
            aoi_mod.GeographicDataFetcher, "get_location_info",
            side_effect=_stub_geocoding))
        stack.enter_context(patch.object(
            aoi_mod.WeatherDataFetcher, "fetch_weather", return_value=_stub_weather()))
        stack.enter_context(patch.object(
            aoi_mod.WeatherDataFetcher, "fetch_forecast",
            return_value={"daily": {}, "_fabricated": True}))
        stack.enter_context(patch.object(
            aoi_mod.SoilDataFetcher, "fetch_soil_data", return_value=_stub_soil()))
        stack.enter_context(patch.object(
            aoi_mod.TerrainDataFetcher, "fetch_terrain",
            return_value={"slope": 2.0, "aspect": 180, "source": "stub",
                          "_fabricated": True}))
        return fetch_aoi_data(
            29.9, 74.0, "Test", crop_name="apple",
            sensor_soil_moisture=sensor_soil_moisture,
            sensor_is_fraction=sensor_is_fraction, soil_test=soil_test)


def test_raw_sensor_reading_overrides_modelled_moisture():
    # Raw 0.30 m³/m³ on loam (FC≈0.32) → fraction ≈ 0.94, overriding Open-Meteo.
    fc = field_capacity_from_texture("loam")
    result = _run(sensor_soil_moisture=0.30)
    props = result["soil"]["properties"]
    assert props["soil_moisture_source"] == "ground-sensor"
    assert props["soil_moisture_current"] == pytest.approx(min(1.0, 0.30 / fc), abs=0.01)
    assert result["radar_soil_moisture"]["source"] == "ground-sensor"
    assert "soil.soil_moisture_current" not in result["_fabricated_sources"]


def test_fraction_sensor_reading_used_directly():
    result = _run(sensor_soil_moisture=0.42, sensor_is_fraction=True)
    assert result["soil"]["properties"]["soil_moisture_current"] == pytest.approx(0.42)
    assert result["radar_soil_moisture"]["source"] == "ground-sensor"


def test_no_sensor_leaves_modelled_source():
    result = _run(sensor_soil_moisture=None)
    assert result["soil"]["properties"].get("soil_moisture_source") != "ground-sensor"
    assert result["radar_soil_moisture"]["source"] != "ground-sensor"


def test_soil_test_flows_into_npk_profile():
    result = _run(soil_test={"N": "high"})
    assert result["soil_nutrients"]["N"]["source"] == "soil-test"
