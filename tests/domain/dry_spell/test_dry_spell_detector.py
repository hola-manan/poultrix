"""Tests for the pure dry-spell detector."""

from jeevn.domain.dry_spell import DrySpellDetector


def test_flags_spell_from_recent_plus_forecast_runs():
    # 3 trailing dry past days + 4 leading dry forecast days = 7 >= 5.
    recent = [5.0, 0.0, 0.0, 0.0]            # last 3 are dry
    forecast = [0.0, 0.0, 0.0, 0.0, 8.0]     # first 4 dry, then rain
    prob = [10, 20, 15, 25, 80]
    r = DrySpellDetector.detect(recent, forecast, prob, min_dry_days=5)
    assert r.is_dry_spell
    assert r.recent_dry_run == 3
    assert r.forecast_dry_run == 4
    assert r.dry_days == 7
    assert r.severity == "alert"
    assert not r.data_gap


def test_high_rain_probability_breaks_forecast_run():
    # Modelled amount ~0 but 90% probability → not a dry day.
    recent = [0.0, 0.0]
    forecast = [0.0, 0.0, 0.0]
    prob = [90, 10, 10]
    r = DrySpellDetector.detect(recent, forecast, prob, min_dry_days=3)
    assert r.forecast_dry_run == 0
    assert r.dry_days == 2  # only the two recent dry days


def test_deficit_escalates_to_urgent():
    recent = [0.0, 0.0, 0.0]
    forecast = [0.0, 0.0, 0.0]
    r = DrySpellDetector.detect(recent, forecast, [0, 0, 0], min_dry_days=5,
                                soil_moisture_deficit_mm=20.0)
    assert r.is_dry_spell
    assert r.severity == "urgent"


def test_no_spell_when_recent_rain():
    r = DrySpellDetector.detect([10.0, 0.0], [0.0, 5.0], [0, 60], min_dry_days=5)
    assert not r.is_dry_spell
    assert r.severity in ("none", "watch")


def test_data_gap_suppresses_alert():
    # A fabricated/failed forecast must never read as "no rain".
    r = DrySpellDetector.detect([0.0] * 10, [0.0] * 7, [0] * 7,
                                min_dry_days=5, data_gap=True)
    assert not r.is_dry_spell
    assert r.data_gap
    assert r.severity == "none"


def test_empty_series_is_a_gap_not_a_dry_spell():
    r = DrySpellDetector.detect(None, None)
    assert r.data_gap
    assert not r.is_dry_spell
