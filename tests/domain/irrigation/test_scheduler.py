"""
Tests for the rain-aware irrigation scheduler + ET0 unit correctness.

Regression coverage for the unit bugs fixed in 2026-05:
- ET0 was ~6x too high (inverted solar_radiation/0.408 conversion).
- Scheduler multiplied irrigation by 1000 (treating mm as metres) -> drip
  of thousands of mm/day.
- Rainfall was divided by 1000 before subtraction -> effectively ignored.
"""

import pytest

from jeevn.domain.irrigation import IrrigationScheduler
from jeevn.domain.irrigation.et0 import IrrigationCalculator


# ── ET0 sanity ──────────────────────────────────────────────────────────────

def test_et0_realistic_for_hot_semiarid_day():
    """Ganganagar late-May: Tmax~36, Tmin~25. Real ET0 should land in the
    ~4-8 mm/day band, NOT the ~23 mm/day the inverted-conversion bug produced.
    """
    et0 = IrrigationCalculator.calculate_et0_hargreaves_samani(
        temp_mean=30.0, temp_max=36.0, temp_min=25.0,
        solar_radiation=22.0,  # ignored by Hargreaves-Samani now
        lat=29.92, day_of_year=145,
    )
    assert 3.0 <= et0 <= 9.0, f"ET0 {et0:.2f} outside realistic band"


def test_et0_ignores_solar_radiation_argument():
    """Hargreaves-Samani uses extraterrestrial Ra, not measured shortwave.
    Passing wildly different solar_radiation must not change the result.
    """
    common = dict(temp_mean=30.0, temp_max=36.0, temp_min=25.0,
                  lat=29.92, day_of_year=145)
    a = IrrigationCalculator.calculate_et0_hargreaves_samani(solar_radiation=0.0, **common)
    b = IrrigationCalculator.calculate_et0_hargreaves_samani(solar_radiation=500.0, **common)
    assert a == b


# ── Scheduler fixtures ──────────────────────────────────────────────────────

def _aoi(forecast_daily=None):
    return {
        "location": {"latitude": 29.92, "longitude": 73.97},
        "crop_name": "wheat",
        "current_growth_stage": {"stage": "heading"},
        "forecast": {"daily": forecast_daily} if forecast_daily is not None else {},
    }


def _dry_forecast(days=7):
    from datetime import date, timedelta
    base = date(2026, 5, 20)
    return {
        "dates": [(base + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)],
        "temp_max": [36.0] * days,
        "temp_min": [25.0] * days,
        "temp_mean": [30.0] * days,
        "rainfall": [0.0] * days,
        "rain_probability": [0] * days,
    }


# ── Scheduler units ─────────────────────────────────────────────────────────

def test_drip_values_are_realistic_mm_not_thousands():
    """The *1000 bug produced drip ~7000 mm/day. Real net irrigation on a hot
    dry day is single-digit mm. Assert every applied value is < 20 mm.
    """
    sched = IrrigationScheduler.generate_schedule(
        _aoi(_dry_forecast()), {"rvi": 0.5}, area_acres=0.42,
    )
    drips = [d["drip_mm"] for d in sched["daily_schedule"]]
    assert all(0.0 <= v < 20.0 for v in drips), f"unrealistic drip values: {drips}"
    assert sched["total_water_mm"] < 100.0, sched["total_water_mm"]
    assert 3.0 <= sched["et0_mm_per_day"] <= 9.0


# ── Per-day rain subtraction ────────────────────────────────────────────────

def test_heavy_rain_day_zeroes_net_irrigation():
    """A day with rain >> ETc should need no irrigation even if it's an
    even (irrigation) day.
    """
    fc = _dry_forecast()
    fc["rainfall"] = [50.0] * 7      # 50 mm/day — far exceeds ETc
    fc["rain_probability"] = [95] * 7
    sched = IrrigationScheduler.generate_schedule(
        _aoi(fc), {"rvi": 0.5}, area_acres=0.42,
    )
    assert sched["total_water_mm"] == 0.0
    assert all(d["drip_mm"] == 0.0 for d in sched["daily_schedule"])


def test_dry_forecast_schedules_irrigation():
    """Zero rain → irrigation is scheduled on alternate (even) days."""
    sched = IrrigationScheduler.generate_schedule(
        _aoi(_dry_forecast()), {"rvi": 0.5}, area_acres=0.42,
    )
    assert sched["irrigation_days"] > 0
    assert sched["total_water_mm"] > 0.0


def test_rain_reduces_but_not_zeroes_net_on_light_rain():
    """Light rain (less than ETc) reduces net irrigation but doesn't zero it.
    Compare applied water on a dry even-day vs a light-rain even-day.
    """
    dry = IrrigationScheduler.generate_schedule(
        _aoi(_dry_forecast()), {"rvi": 0.5}, area_acres=0.42,
    )
    fc = _dry_forecast()
    fc["rainfall"] = [2.0] * 7  # light, below ETc
    light = IrrigationScheduler.generate_schedule(
        _aoi(fc), {"rvi": 0.5}, area_acres=0.42,
    )
    assert light["total_water_mm"] < dry["total_water_mm"]
    assert light["total_water_mm"] > 0.0


# ── Per-row rainfall display ────────────────────────────────────────────────

def test_rows_show_actual_forecast_rainfall_not_hardcoded_zero():
    fc = _dry_forecast()
    fc["rainfall"] = [0.0, 3.5, 0.0, 7.2, 0.0, 1.1, 0.0]
    fc["rain_probability"] = [5, 60, 10, 90, 0, 40, 5]
    sched = IrrigationScheduler.generate_schedule(
        _aoi(fc), {"rvi": 0.5}, area_acres=0.42,
    )
    rows = sched["daily_schedule"]
    assert rows[1]["rainfall"] == "3.5 mm"
    assert rows[1]["rain_percent"] == "60%"
    assert rows[3]["rainfall"] == "7.2 mm"
    assert rows[3]["rain_percent"] == "90%"


# ── Forecast-absent fallback ────────────────────────────────────────────────

def test_no_forecast_still_produces_schedule():
    """When the forecast is missing entirely, the scheduler must still
    produce a schedule (degraded, default temps) without crashing.
    """
    sched = IrrigationScheduler.generate_schedule(
        _aoi(forecast_daily=None), {"rvi": 0.5}, area_acres=0.42,
    )
    assert len(sched["daily_schedule"]) == 7
    assert 3.0 <= sched["et0_mm_per_day"] <= 9.0
    # No forecast → treated as zero rain → some irrigation scheduled.
    assert sched["total_water_mm"] > 0.0
