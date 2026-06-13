"""
Tests that grape is a first-class crop in the phenology DB — it must resolve
to its own stages/Kc/yield rather than silently falling back to wheat.
"""

from jeevn.domain.crop.phenology import CropPhenologyDatabase as DB


def test_grape_is_not_the_wheat_fallback():
    grape = DB.get_crop_data("grape")
    wheat = DB.get_crop_data("wheat")
    assert grape is not wheat
    assert grape["yield_potential_kg_per_acre"] == 10000
    assert grape["t_base"] == 10.0
    # Grape-specific stages exist (these do not appear in wheat/apple).
    assert "veraison" in grape["growth_stages"]
    assert "berry_development" in grape["growth_stages"]


def test_grape_stage_walk_by_gdd_lands_on_grape_stage():
    # Cumulative grape GDD: budburst 150, +shoot 450 = 600, +flowering 220 = 820.
    stage = DB.get_current_growth_stage("grape", days_since_sowing=50, accumulated_gdd=820)
    assert stage["stage"] == "flowering"
    assert stage["kc"] == 0.7


def test_grape_stage_walk_by_days():
    # Cumulative days: budburst 10, +shoot 30 = 40, +flowering 15 = 55.
    stage = DB.get_current_growth_stage("grape", days_since_sowing=50, accumulated_gdd=0)
    assert stage["stage"] == "flowering"


def test_grape_nutrient_targets_are_potassium_heavy():
    req = DB.get_crop_data("grape")["nutrient_requirements_kg_per_acre"]
    assert set(req) == {"N", "P", "K", "S", "Zn"}
    # Grapes are heavy K feeders — K target should exceed N.
    assert req["K"]["optimal"] > req["N"]["optimal"]


def test_unknown_crop_still_falls_back_to_wheat():
    assert DB.get_crop_data("sorghum") is DB.get_crop_data("wheat")
