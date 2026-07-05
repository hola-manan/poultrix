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


def test_fao56_crop_resolves_to_generic_profile():
    # The FAO-56 crop DB now covers many crops, so a crop like sorghum is
    # *known* — it resolves to a generic 3-stage profile (initial/mid/late)
    # rather than falling back to wheat. Generic profiles intentionally omit
    # nutrient_requirements (the fertilizer step is guarded on their presence).
    data = DB.get_crop_data("sorghum")
    assert data is not DB.get_crop_data("wheat")
    assert set(data["growth_stages"]) == {"initial", "mid", "late"}
    assert "nutrient_requirements_kg_per_acre" not in data


def test_completely_unknown_crop_gets_safe_generic_default():
    # A crop absent from both the hardcoded set and the FAO-56 DB still returns
    # a safe, non-crashing generic default (no wheat, no nutrient targets).
    data = DB.get_crop_data("zzz-not-a-real-crop")
    assert set(data["growth_stages"]) == {"initial", "mid", "late"}
    assert "nutrient_requirements_kg_per_acre" not in data
