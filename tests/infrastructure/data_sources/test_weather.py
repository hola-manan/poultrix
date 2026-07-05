"""
Tests for the Open-Meteo weather adapter.

Focus: future-date clamping. Open-Meteo's `archive-api` returns 400 Bad
Request when `end_date > today`. The user's submission flow can pass
future dates (sowing date + 6 months → end of a crop season that hasn't
happened yet), so the adapter must clamp before calling the API.
"""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from jeevn.infrastructure.data_sources import weather as weather_mod
from jeevn.infrastructure.data_sources.weather import WeatherDataFetcher


def _today():
    return datetime.now().strftime("%Y-%m-%d")


def _ok_open_meteo_response(sm_hourly=None):
    """sm_hourly defaults to 48 values: a 24-h ramp from 0.20 to 0.30."""
    if sm_hourly is None:
        sm_hourly = [0.20] * 24 + [0.30] * 24
    n = len(sm_hourly)
    return type("R", (), {
        "raise_for_status": lambda self: None,
        "json": lambda self: {
            "timezone": "Asia/Kolkata",
            "daily": {
                "time": ["2026-05-13", "2026-05-14"],
                "temperature_2m_max": [37.0, 38.0],
                "temperature_2m_min": [25.0, 26.0],
                "temperature_2m_mean": [31.0, 32.0],
                "precipitation_sum": [0.0, 0.0],
                "shortwave_radiation_sum": [27.0, 28.0],
                "windspeed_10m_max": [8.0, 9.0],
            },
            "hourly": {
                "time": [f"2026-05-14T{h:02d}:00" for h in range(n)],
                "temperature_2m": [25.0] * n,
                # Last 24 values are 80.0 -> last-24h mean RH = 80.
                "relative_humidity_2m": [50.0] * max(0, n - 24) + [80.0] * min(n, 24),
                "precipitation": [0.0] * n,
                "soil_moisture_0_to_7cm": sm_hourly,
            },
        },
    })()


def test_future_end_date_clamped_to_today():
    captured = {}

    def fake_get(url, params=None, timeout=None):
        captured["params"] = params
        return _ok_open_meteo_response()

    future = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")
    past = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")

    with patch.object(weather_mod.requests, "get", side_effect=fake_get):
        result = WeatherDataFetcher.fetch_weather(29.9, 73.9, past, future)

    assert result["_fabricated"] is False
    # end_date should have been clamped to today before being sent to the API
    assert captured["params"]["end_date"] == _today()
    # start_date was already in the past — left alone
    assert captured["params"]["start_date"] == past


def test_future_start_and_end_dates_both_clamped():
    captured = {}

    def fake_get(url, params=None, timeout=None):
        captured["params"] = params
        return _ok_open_meteo_response()

    far_future_start = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    far_future_end   = (datetime.now() + timedelta(days=60)).strftime("%Y-%m-%d")

    with patch.object(weather_mod.requests, "get", side_effect=fake_get):
        WeatherDataFetcher.fetch_weather(29.9, 73.9, far_future_start, far_future_end)

    # Both clamped to today; start should not exceed end after clamping
    assert captured["params"]["start_date"] == _today()
    assert captured["params"]["end_date"] == _today()


def test_past_dates_passed_through_unchanged():
    captured = {}

    def fake_get(url, params=None, timeout=None):
        captured["params"] = params
        return _ok_open_meteo_response()

    start = "2024-01-01"
    end   = "2024-12-31"
    with patch.object(weather_mod.requests, "get", side_effect=fake_get):
        WeatherDataFetcher.fetch_weather(29.9, 73.9, start, end)

    assert captured["params"]["start_date"] == start
    assert captured["params"]["end_date"] == end


def test_falls_back_to_default_on_network_failure():
    with patch.object(weather_mod.requests, "get", side_effect=Exception("API down")):
        result = WeatherDataFetcher.fetch_weather(29.9, 73.9)
    assert result["_fabricated"] is True
    assert "daily" in result


def test_soil_moisture_last_24h_mean_is_computed():
    """The hourly soil-moisture array is reduced to a single 24-h mean
    that the AOI composer can normalise to fraction-of-field-capacity.
    """
    # 48 hourly values: 24 at 0.20, then 24 at 0.30. Last-24h mean = 0.30.
    sm_hourly = [0.20] * 24 + [0.30] * 24

    with patch.object(weather_mod.requests, "get",
                       return_value=_ok_open_meteo_response(sm_hourly=sm_hourly)):
        result = WeatherDataFetcher.fetch_weather(29.92, 73.97)

    assert result["daily"]["soil_moisture_0_to_7cm_mean"] == pytest.approx(0.30)


def test_soil_moisture_skips_nulls_in_last_24h_window():
    """Open-Meteo can return None entries for sparse hours — those should
    be skipped, the mean computed only over the non-null tail.
    """
    sm_hourly = [None] * 20 + [0.25] * 5 + [None] * 19 + [0.35] * 5
    with patch.object(weather_mod.requests, "get",
                       return_value=_ok_open_meteo_response(sm_hourly=sm_hourly)):
        result = WeatherDataFetcher.fetch_weather(29.92, 73.97)
    # Last 24 values are: [None]*19 + [0.35]*5  → non-null mean is 0.35
    assert result["daily"]["soil_moisture_0_to_7cm_mean"] == pytest.approx(0.35)


def test_soil_moisture_mean_is_none_when_all_null():
    sm_hourly = [None] * 48
    with patch.object(weather_mod.requests, "get",
                       return_value=_ok_open_meteo_response(sm_hourly=sm_hourly)):
        result = WeatherDataFetcher.fetch_weather(29.92, 73.97)
    assert result["daily"]["soil_moisture_0_to_7cm_mean"] is None


def test_hourly_params_are_requested():
    """Lock in the hourly variables the disease models depend on: temperature,
    relative humidity, precipitation, and soil moisture."""
    captured = {}

    def fake_get(url, params=None, timeout=None):
        captured["params"] = params
        return _ok_open_meteo_response()

    with patch.object(weather_mod.requests, "get", side_effect=fake_get):
        WeatherDataFetcher.fetch_weather(29.92, 73.97)
    hourly_param = captured["params"].get("hourly", "")
    for var in ("temperature_2m", "relative_humidity_2m",
                "precipitation", "soil_moisture_0_to_7cm"):
        assert var in hourly_param, hourly_param


def test_hourly_block_and_rh_mean_surfaced():
    """The hourly series is surfaced for the disease models, and the last-24h
    mean RH is computed from the real feed (no fabricated proxy)."""
    with patch.object(weather_mod.requests, "get",
                      return_value=_ok_open_meteo_response()):
        result = WeatherDataFetcher.fetch_weather(29.92, 73.97)

    assert result["daily"]["relative_humidity_mean"] == pytest.approx(80.0)
    hourly = result["hourly"]
    assert hourly["temperature_2m"] and hourly["relative_humidity_2m"]
    assert len(hourly["time"]) == len(hourly["temperature_2m"])


def test_fabricated_weather_has_empty_hourly_and_null_rh():
    """On fallback we must NOT synthesise hourly weather — the disease models
    rely on absence to avoid presenting fabricated numbers as real."""
    with patch.object(weather_mod.requests, "get", side_effect=Exception("down")):
        result = WeatherDataFetcher.fetch_weather(29.9, 73.9)
    assert result["_fabricated"] is True
    assert result["daily"]["relative_humidity_mean"] is None
    assert result["hourly"]["temperature_2m"] == []


def test_uses_current_open_meteo_variable_names():
    """Lock in the variable rename. Open-Meteo deprecated the legacy
    `precipitation` and `radiation_sum` names in favour of `precipitation_sum`
    and `shortwave_radiation_sum`; the legacy names now 400. This test fails
    immediately if anyone reintroduces the legacy spelling.
    """
    captured = {}

    def fake_get(url, params=None, timeout=None):
        captured["params"] = params
        return _ok_open_meteo_response()

    with patch.object(weather_mod.requests, "get", side_effect=fake_get):
        WeatherDataFetcher.fetch_weather(29.9, 73.9)

    daily_param = captured["params"]["daily"]
    assert "precipitation_sum" in daily_param, daily_param
    assert "shortwave_radiation_sum" in daily_param, daily_param
    # Legacy names must NOT be present.
    assert ",precipitation," not in daily_param and not daily_param.endswith(",precipitation"), daily_param
    assert ",radiation_sum," not in daily_param and not daily_param.endswith(",radiation_sum"), daily_param
