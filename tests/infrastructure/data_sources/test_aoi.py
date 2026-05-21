"""
Tests for the AOI composer's soil-moisture wiring (task #2).

The composer takes Open-Meteo's m³/m³ surface-soil-moisture reading and
combines it with SoilGrids' texture (via a USDA-NRCS field-capacity
lookup) to produce a fraction-of-field-capacity value the downstream
agronomic code expects.
"""

from contextlib import ExitStack
from unittest.mock import patch

import pytest

from jeevn.infrastructure.data_sources import aoi as aoi_mod
from jeevn.infrastructure.data_sources.aoi import fetch_aoi_data


def _stub_geocoding(lat, lon):
    return {"latitude": lat, "longitude": lon, "name": "Test", "city": "",
            "state": "", "country": "India", "timezone": "Asia/Kolkata",
            "_fabricated": False}


def _stub_weather(sm_mean):
    """Build a weather dict shaped like the real WeatherDataFetcher output."""
    return {
        "location": {"latitude": 29.92, "longitude": 73.97, "timezone": "Asia/Kolkata"},
        "daily": {
            "dates": ["2026-05-13", "2026-05-14"],
            "temp_max": [37.0, 38.0],
            "temp_min": [25.0, 26.0],
            "temp_mean": [31.0, 32.0],
            "rainfall": [0.0, 0.0],
            "solar_radiation": [27.0, 28.0],
            "wind_speed": [8.0, 9.0],
            "soil_moisture_0_to_7cm_mean": sm_mean,
        },
        "_fabricated": False,
    }


def _stub_soil_with_texture(texture):
    """Build a soil dict shaped like SoilDataFetcher's real-data output."""
    return {
        "location": {"latitude": 29.92, "longitude": 73.97, "name": "Test"},
        "properties": {
            "ph": 7.8,
            "ec": 0.5,
            "organic_carbon_percent": 0.56,
            "sand_percent": 51.0,
            "silt_percent": 23.0,
            "clay_percent": 26.0,
            "texture": texture,
            "cec": 16.5,
            "water_holding_capacity": 22,
            "infiltration_rate": 8,
            "bulk_density": 1.47,
            "soil_moisture_current": 0.65,  # fabricated default; should be replaced
        },
        "_fabricated_fields": {
            "ph": False, "ec": True, "organic_carbon_percent": False,
            "sand_percent": False, "silt_percent": False, "clay_percent": False,
            "texture": False, "cec": False,
            "water_holding_capacity": False, "infiltration_rate": False,
            "bulk_density": False,
            "soil_moisture_current": True,  # default-fabricated; composer flips it
        },
        "_aoi_in_built_up_land": False,
    }


def _run_with_stubs(*, weather, soil):
    """Run fetch_aoi_data with all three external adapters stubbed."""
    with ExitStack() as stack:
        stack.enter_context(patch.object(
            aoi_mod.GeographicDataFetcher, "get_location_info",
            side_effect=_stub_geocoding))
        stack.enter_context(patch.object(
            aoi_mod.WeatherDataFetcher, "fetch_weather",
            return_value=weather))
        stack.enter_context(patch.object(
            aoi_mod.SoilDataFetcher, "fetch_soil_data",
            return_value=soil))
        return fetch_aoi_data(29.92, 73.97, "Test", crop_name="apple")


def test_real_open_meteo_sm_converted_via_sandy_clay_loam_fc():
    """Sandy clay loam → FC=0.27. 0.20 m³/m³ → 0.20/0.27 ≈ 0.74."""
    result = _run_with_stubs(
        weather=_stub_weather(sm_mean=0.20),
        soil=_stub_soil_with_texture("sandy clay loam"),
    )
    props = result["soil"]["properties"]
    # 0.20 / 0.27 ≈ 0.741 → rounded to 0.74
    assert props["soil_moisture_current"] == pytest.approx(0.74, abs=0.01)
    # Raw m³/m³ preserved for transparency
    assert props["soil_moisture_m3m3"] == pytest.approx(0.20)


def test_sm_clamped_to_one_when_above_field_capacity():
    """After heavy rain m³/m³ can exceed FC. The fraction is clamped at 1.0."""
    result = _run_with_stubs(
        weather=_stub_weather(sm_mean=0.40),    # well above any FC
        soil=_stub_soil_with_texture("sandy loam"),   # FC = 0.18
    )
    assert result["soil"]["properties"]["soil_moisture_current"] == 1.0


def test_sm_flag_flipped_to_not_fabricated_when_open_meteo_returns_value():
    """Per-property tracking: real soil moisture leaves the fabricated list."""
    result = _run_with_stubs(
        weather=_stub_weather(sm_mean=0.25),
        soil=_stub_soil_with_texture("loam"),
    )
    # The top-level fabricated_sources list should NOT mention this property.
    assert "soil.soil_moisture_current" not in result["_fabricated_sources"]
    # The per-property soil flags should mark it not-fabricated.
    assert result["soil"]["_fabricated_fields"]["soil_moisture_current"] is False


def test_sm_stays_fabricated_when_weather_falls_back():
    """If Open-Meteo failed (weather fabricated), SM stays fabricated."""
    weather = _stub_weather(sm_mean=0.25)
    weather["_fabricated"] = True
    result = _run_with_stubs(
        weather=weather,
        soil=_stub_soil_with_texture("loam"),
    )
    # Weather is fabricated; SM not overlaid even though `sm_mean` is set.
    assert "weather" in result["_fabricated_sources"]
    assert "soil.soil_moisture_current" in result["_fabricated_sources"]


def test_sm_stays_fabricated_when_open_meteo_has_no_sm_value():
    """Weather succeeded but `soil_moisture_0_to_7cm_mean` is None → no overlay."""
    result = _run_with_stubs(
        weather=_stub_weather(sm_mean=None),
        soil=_stub_soil_with_texture("loam"),
    )
    # No SM value to overlay → composed soil_moisture_current stays as the
    # fabricated regional template (0.65), and SM is still in the
    # fabricated list.
    assert "soil.soil_moisture_current" in result["_fabricated_sources"]
    assert result["soil"]["properties"]["soil_moisture_current"] == 0.65
