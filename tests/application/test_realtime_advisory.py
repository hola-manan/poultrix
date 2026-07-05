"""
Alert-logic tests for the real-time advisor.

The accurate report pipeline and the weather fetch are monkeypatched so these
tests are deterministic and offline — they exercise dry-spell detection, the
soil-water-deficit trigger, leaching hold, salinity, fertiliser confidence
gating, and the fail-safe data-gap path.
"""

import pytest

from jeevn.application import realtime_advisory as ra
from jeevn.application.realtime_advisory import RealtimeAdvisor, AdvisoryConfig
from jeevn.infrastructure.sensors import MockSoilSensor


def _report(soil_moisture_fraction=0.3, ec=0.5, fert=None, texture="loam"):
    fert = fert if fert is not None else {}
    return {
        "aoi_info": {"location": "Testville"},
        "components": {
            "irrigation_schedule": {
                "best_time": "05:00-08:00", "total_water_mm": 12.0,
                "irrigation_days": 2,
            },
            "fertilizer_management": {"nutrient_requirements": fert},
        },
        "environmental_context": {
            "soil": {"properties": {
                "soil_moisture_current": soil_moisture_fraction,
                "texture": texture, "ec": ec,
            }},
        },
    }


def _forecast(recent, forward, forward_prob=None, fabricated=False):
    forward_prob = forward_prob if forward_prob is not None else [0] * len(forward)
    rainfall = list(recent) + list(forward)
    prob = [0] * len(recent) + list(forward_prob)
    dates = [f"d{i}" for i in range(len(rainfall))]
    return {
        "daily": {"dates": dates, "rainfall": rainfall, "rain_probability": prob},
        "today_index": len(recent),
        "past_days": len(recent),
        "_fabricated": fabricated,
    }


@pytest.fixture
def patch_pipeline(monkeypatch):
    """Install report + forecast stubs; return setters for each test."""
    state = {"report": _report(), "forecast": _forecast([0, 0], [0, 0])}

    def fake_generate_report(**kwargs):
        return state["report"]

    def fake_fetch_forecast(lat, lon, days=7, past_days=0):
        return state["forecast"]

    monkeypatch.setattr(ra.AgriculturalReportGenerator, "generate_report",
                        staticmethod(fake_generate_report))
    monkeypatch.setattr(ra.WeatherDataFetcher, "fetch_forecast",
                        staticmethod(fake_fetch_forecast))
    return state


def _kinds(advisory):
    return {a.kind for a in advisory["alerts"]}


def test_dry_spell_and_irrigate_now(patch_pipeline):
    patch_pipeline["report"] = _report(soil_moisture_fraction=0.30)  # dry soil
    patch_pipeline["forecast"] = _forecast([0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0])
    advisor = RealtimeAdvisor(AdvisoryConfig(dry_spell_days=5))
    adv = advisor.evaluate(31.1, 77.1, crop="apple",
                           sensor=MockSoilSensor(soil_moisture=0.05))
    assert adv["dry_spell"].is_dry_spell
    assert "dry_spell" in _kinds(adv)
    assert "irrigate_now" in _kinds(adv)
    # deficit present → dry spell escalated to urgent
    assert adv["dry_spell"].severity == "urgent"


def test_wet_soil_no_irrigate(patch_pipeline):
    patch_pipeline["report"] = _report(soil_moisture_fraction=0.98)  # replete
    patch_pipeline["forecast"] = _forecast([5.0], [3.0, 4.0])
    advisor = RealtimeAdvisor()
    adv = advisor.evaluate(31.1, 77.1)
    assert "irrigate_now" not in _kinds(adv)


def test_hold_fertigation_on_heavy_rain(patch_pipeline):
    patch_pipeline["forecast"] = _forecast([0], [20.0, 5.0], [90, 80])
    advisor = RealtimeAdvisor(AdvisoryConfig(leach_rain_mm=15.0))
    adv = advisor.evaluate(31.1, 77.1)
    assert "hold_fertigation" in _kinds(adv)


def test_high_salinity_alert(patch_pipeline):
    patch_pipeline["report"] = _report(ec=2.4)
    advisor = RealtimeAdvisor()
    adv = advisor.evaluate(31.1, 77.1)
    assert "high_salinity" in _kinds(adv)


def test_data_gap_suppresses_dry_spell(patch_pipeline):
    patch_pipeline["forecast"] = _forecast([0, 0, 0], [0, 0, 0, 0, 0],
                                           fabricated=True)
    advisor = RealtimeAdvisor(AdvisoryConfig(dry_spell_days=5))
    adv = advisor.evaluate(31.1, 77.1)
    assert adv["weather_data_gap"] is True
    assert adv["dry_spell"].data_gap
    assert "dry_spell" not in _kinds(adv)
    assert "hold_fertigation" not in _kinds(adv)  # no leach calc on a gap


def test_fertilizer_confidence_gating(patch_pipeline):
    # Medium-confidence gap → fertilize alert present.
    patch_pipeline["report"] = _report(fert={
        "N": {"gap_kg_per_acre": 8.0, "confidence": "medium", "source": "shc-district"},
        "P": {"gap_kg_per_acre": 4.0, "confidence": "very_low", "source": "soilgrids"},
    })
    advisor = RealtimeAdvisor()
    adv = advisor.evaluate(31.1, 77.1)
    fert_alerts = [a for a in adv["alerts"] if a.kind == "fertilize"]
    assert len(fert_alerts) == 1
    # Only the medium-confidence N is surfaced; low-confidence P is excluded.
    assert "N" in fert_alerts[0].data["nutrients"]
    assert "P" not in fert_alerts[0].data["nutrients"]


def test_fertilizer_low_confidence_only_no_alert(patch_pipeline):
    patch_pipeline["report"] = _report(fert={
        "P": {"gap_kg_per_acre": 4.0, "confidence": "very_low", "source": "soilgrids"},
    })
    advisor = RealtimeAdvisor()
    adv = advisor.evaluate(31.1, 77.1)
    assert "fertilize" not in _kinds(adv)
