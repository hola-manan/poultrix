"""
Tests for the grape disease risk models (crop_health.disease_models).

Two diseases, two data profiles:
* Gubler-Thomas powdery-mildew index — hourly temperature only.
* Downy-mildew wet-period flag — hedged, RH-as-leaf-wetness proxy.
"""

from jeevn.domain.crop_health.disease_models import (
    gubler_powdery_mildew_index,
    downy_mildew_wet_period_risk,
)


def _day(date: str, temps):
    """Return (times, temps) for one day of hourly values."""
    times = [f"{date}T{h:02d}:00" for h in range(len(temps))]
    return times, list(temps)


def _concat_days(*days):
    times, temps = [], []
    for d_times, d_temps in days:
        times += d_times
        temps += d_temps
    return times, temps


# ── Gubler-Thomas powdery mildew ────────────────────────────────────────────

def test_gubler_three_qualifying_days_reach_high():
    """Three consecutive days each with >=6 continuous hours in 21-30 C
    initiate the index at 60 -> high risk."""
    days = [_day(f"2026-05-{10+i:02d}", [25.0] * 24) for i in range(3)]
    times, temps = _concat_days(*days)
    r = gubler_powdery_mildew_index(times, temps)
    assert r["index"] == 60
    assert r["risk_level"] == "high"
    assert r["qualifying_days"] == 3
    assert r["spray_interval_days"] == 14


def test_gubler_unfavorable_temperatures_low():
    """Temperatures outside the 21-30 C band never qualify -> index 0, low."""
    days = [_day(f"2026-05-{10+i:02d}", [12.0] * 24) for i in range(5)]
    times, temps = _concat_days(*days)
    r = gubler_powdery_mildew_index(times, temps)
    assert r["index"] == 0
    assert r["risk_level"] == "low"
    assert r["qualifying_days"] == 0


def test_gubler_subsequent_qualifying_day_adds_twenty():
    """After initiation, a 4th qualifying day adds 20 (60 -> 80)."""
    days = [_day(f"2026-05-{10+i:02d}", [25.0] * 24) for i in range(4)]
    times, temps = _concat_days(*days)
    r = gubler_powdery_mildew_index(times, temps)
    assert r["index"] == 80
    assert r["risk_level"] == "high"


def test_gubler_heat_spike_applies_penalty():
    """A day reaching >=35 C takes a -10 heat penalty. After init at 60, a
    non-qualifying hot day -> -10 (non-qualifying) -10 (heat) = 40."""
    init = [_day(f"2026-05-{10+i:02d}", [25.0] * 24) for i in range(3)]
    # Day 4: all 18 C (below band, non-qualifying) with one 36 C hour.
    hot = [18.0] * 23 + [36.0]
    day4 = _day("2026-05-13", hot)
    times, temps = _concat_days(*init, day4)
    r = gubler_powdery_mildew_index(times, temps)
    assert r["index"] == 40
    assert r["risk_level"] == "moderate"


def test_gubler_under_six_hours_does_not_qualify():
    """A day with only 5 continuous in-band hours does not qualify."""
    temps = [25.0] * 5 + [12.0] * 19          # only a 5-hour run in band
    times, temps = _day("2026-05-10", temps)
    r = gubler_powdery_mildew_index(times, temps)
    assert r["qualifying_days"] == 0
    assert r["index"] == 0


# ── Downy mildew wet-period flag ────────────────────────────────────────────

def test_downy_long_optimal_wet_period_high():
    times, temps = _day("2026-06-20", [17.0] * 12)
    rh = [95.0] * 12
    pr = [0.0] * 12
    r = downy_mildew_wet_period_risk(times, temps, rh, pr)
    assert r["favorable"] is True
    assert r["risk_level"] == "high"
    assert r["wet_hours"] == 12
    assert r["confidence"] == "regional-proxy"


def test_downy_dry_warm_not_favorable():
    times, temps = _day("2026-06-20", [28.0] * 12)
    rh = [50.0] * 12
    pr = [0.0] * 12
    r = downy_mildew_wet_period_risk(times, temps, rh, pr)
    assert r["favorable"] is False
    assert r["risk_level"] == "low"
    assert r["wet_hours"] == 0


def test_downy_primary_infection_rule_fires():
    """A day with >=10 mm rain at >=10 C meets the 3-10 primary rule."""
    times, temps = _day("2026-06-20", [20.0] * 24)
    rh = [60.0] * 24
    pr = [1.0] * 12 + [0.0] * 12              # 12 mm total over the day
    r = downy_mildew_wet_period_risk(times, temps, rh, pr)
    assert r["primary_infection"] is True
    assert r["favorable"] is True


def test_downy_short_wet_period_below_threshold():
    """A 3-hour wet period is below the 4-hour favorable threshold."""
    times, temps = _day("2026-06-20", [17.0] * 3 + [28.0] * 9)
    rh = [95.0] * 3 + [50.0] * 9
    pr = [0.0] * 12
    r = downy_mildew_wet_period_risk(times, temps, rh, pr)
    assert r["wet_hours"] == 3
    assert r["favorable"] is False


def test_downy_handles_null_hours():
    """Open-Meteo can return None entries; the model must not crash."""
    times, temps = _day("2026-06-20", [17.0, None, 18.0, 19.0])
    rh = [95.0, None, 92.0, 91.0]
    pr = [0.0, None, 0.0, 0.0]
    r = downy_mildew_wet_period_risk(times, temps, rh, pr)
    assert "favorable" in r
