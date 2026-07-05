"""
Grape fertilizer recommendations — must use the dedicated grape branch
(SOP not MOP, foliar Zn), not the generic per-nutrient fallback.
"""

from jeevn.domain.fertilizer.schedule import FertilizerScheduler


def _reqs():
    # Non-zero gaps for every nutrient so each product line can appear.
    return {
        "N": {"gap_kg_per_acre": 20.0},
        "P": {"gap_kg_per_acre": 10.0},
        "K": {"gap_kg_per_acre": 40.0},
        "S": {"gap_kg_per_acre": 12.0},
        "Zn": {"gap_kg_per_acre": 1.0},
    }


def _aoi(crop):
    return {"crop_name": crop, "current_growth_stage": {"stage": "fruit_set"},
            "soil": {"properties": {"ec": 0.4}}}


def test_grape_uses_sop_not_mop():
    sched = FertilizerScheduler.generate_fertilizer_schedule(_aoi("grape"), _reqs(), 1.0)
    products = " ".join(p["product"] for p in sched["recommended_products"]).lower()
    assert "sop" in products or "sulphate of potash" in products
    assert "mop" not in products
    assert "muriate" not in products


def test_grape_zinc_is_foliar():
    sched = FertilizerScheduler.generate_fertilizer_schedule(_aoi("grape"), _reqs(), 1.0)
    zinc = [p for p in sched["recommended_products"] if "Zinc" in p["product"]]
    assert zinc and "foliar" in zinc[0]["application_method"].lower()


def test_grape_branch_distinct_from_generic():
    """An unknown crop hits the generic branch (one 'Generic source' line per
    nutrient); grape must not."""
    grape = FertilizerScheduler.generate_fertilizer_schedule(_aoi("grape"), _reqs(), 1.0)
    other = FertilizerScheduler.generate_fertilizer_schedule(_aoi("sorghum"), _reqs(), 1.0)
    grape_products = {p["product"] for p in grape["recommended_products"]}
    other_products = {p["product"] for p in other["recommended_products"]}
    assert any("Generic source" in p for p in other_products)
    assert not any("Generic source" in p for p in grape_products)
