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


def _ok_open_meteo_response():
    return type("R", (), {
        "raise_for_status": lambda self: None,
        "json": lambda self: {
            "timezone": "Asia/Kolkata",
            "daily": {
                "time": ["2026-05-13", "2026-05-14"],
                "temperature_2m_max": [37.0, 38.0],
                "temperature_2m_min": [25.0, 26.0],
                "temperature_2m_mean": [31.0, 32.0],
                "precipitation": [0.0, 0.0],
                "radiation_sum": [27.0, 28.0],
                "windspeed_10m_max": [8.0, 9.0],
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
