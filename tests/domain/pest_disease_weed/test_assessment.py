"""
Tests for the pest/disease/weed assessor after the grape-disease rework:
real RH replaces the fabricated proxy, RVI is dropped from disease scoring,
and grape powdery/downy mildew are computed by the weather-driven models.
"""

from jeevn.domain.pest_disease_weed.assessment import PestDiseaseWeedAssessor


def _ndvi(rvi=0.6, rsm=0.5):
    return {"rvi": rvi, "rsm": rsm, "rsm_source": "open-meteo", "rsm_pass_date": None}


def _aoi(crop="apple", rh_mean=None, hourly=None, stage="initial"):
    weather = {
        "daily": {
            "temp_mean": [26.0],
            "temp_max": [31.0],
            "rainfall": [0.0],
            "relative_humidity_mean": rh_mean,
        }
    }
    aoi = {
        "crop_name": crop,
        "weather": weather,
        "current_growth_stage": {"stage": stage},
    }
    if hourly is not None:
        aoi["forecast"] = {"hourly": hourly}
    return aoi


def _hourly_qualifying_for_gubler():
    """3 consecutive days of 25 C -> Gubler initiates (index 60)."""
    times, temps, rh, pr = [], [], [], []
    for d in range(3):
        for h in range(24):
            times.append(f"2026-05-{10+d:02d}T{h:02d}:00")
            temps.append(25.0)
            rh.append(70.0)
            pr.append(0.0)
    return {"time": times, "temperature_2m": temps,
            "relative_humidity_2m": rh, "precipitation": pr}


def test_real_rh_used_when_present():
    out = PestDiseaseWeedAssessor.assess_pest_disease_risk(
        _aoi(rh_mean=85.0), _ndvi())
    env = out["environmental_conditions"]
    assert env["humidity_estimate"] == 85
    assert env["humidity_estimated"] is False


def test_proxy_used_and_flagged_when_rh_absent():
    out = PestDiseaseWeedAssessor.assess_pest_disease_risk(
        _aoi(rh_mean=None), _ndvi())
    env = out["environmental_conditions"]
    assert env["humidity_estimated"] is True
    # proxy = 40 + rain*2 + (30 - temp)*2 = 40 + 0 + (30-26)*2 = 48
    assert env["humidity_estimate"] == 48


def test_rvi_does_not_affect_disease_score():
    """Two runs differing only in RVI must yield identical disease risks now
    that RVI is dropped from scoring."""
    low = PestDiseaseWeedAssessor.assess_pest_disease_risk(
        _aoi(rh_mean=70.0), _ndvi(rvi=0.2))
    high = PestDiseaseWeedAssessor.assess_pest_disease_risk(
        _aoi(rh_mean=70.0), _ndvi(rvi=0.9))
    lo = {d["name"]: d["risk_percent"] for d in low["pests_diseases"]}
    hi = {d["name"]: d["risk_percent"] for d in high["pests_diseases"]}
    assert lo == hi


def test_grape_gubler_and_downy_present_with_hourly():
    out = PestDiseaseWeedAssessor.assess_pest_disease_risk(
        _aoi(crop="grape", rh_mean=80.0, hourly=_hourly_qualifying_for_gubler()),
        _ndvi())
    by_name = {d["name"]: d for d in out["pests_diseases"]}
    assert "Powdery Mildew" in by_name
    powdery = by_name["Powdery Mildew"]
    assert powdery["model"] == "gubler_powdery"
    assert powdery["risk_level"] == "high"
    assert powdery["spray_interval_days"] == 14
    assert "Downy Mildew" in by_name
    assert by_name["Downy Mildew"]["confidence"] == "regional-proxy"


def test_grape_model_diseases_omitted_without_hourly():
    """No hourly feed -> model-driven diseases are omitted (not fabricated);
    only the heuristic grape pest remains."""
    out = PestDiseaseWeedAssessor.assess_pest_disease_risk(
        _aoi(crop="grape", rh_mean=80.0, hourly=None), _ndvi())
    names = {d["name"] for d in out["pests_diseases"]}
    assert "Powdery Mildew" not in names
    assert "Downy Mildew" not in names
    assert "Grape Mealybug" in names
