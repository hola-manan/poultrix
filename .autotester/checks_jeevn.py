import math
import re
from datetime import datetime

from auto_tester.core.checks import invariant, metamorphic

# Helper Functions

def _get_expected_fabricated_fields(run):
    """
    Reconstructs the set of expected fabricated fields based on pipeline inputs and trace.
    This models the logic in AgriculturalReportGenerator.generate_report.
    """
    expected = set()
    payload = run.case.payload

    # 1. Fabrication from aoi_data source (e.g., soil, weather)
    aoi_steps = [s for s in run.trace.steps if s.name == "fetch_aoi_data"]
    aoi_result = aoi_steps[0].result if aoi_steps and aoi_steps[0].result else {}
    
    if "_fabricated_sources" in aoi_result:
        expected.update(aoi_result["_fabricated_sources"])

    # 2. Fabrication from _process_ndvi_data logic
    ndvi_fab_set = {"ndvi", "rvi", "rsm"}

    # If ndvi_timeseries is provided, ndvi and its rvi proxy are not fabricated.
    if payload.get("ndvi_timeseries") and payload["ndvi_timeseries"]:
        ndvi_fab_set.discard("ndvi")
        ndvi_fab_set.discard("rvi")

    # If ndvi_raster_data provides a mean, ndvi is not fabricated.
    if payload.get("ndvi_raster_data") and payload["ndvi_raster_data"].get("ndvi_mean") is not None:
        ndvi_fab_set.discard("ndvi")

    # If a real Sentinel-1 RVI is fetched, rvi is not fabricated.
    sar_steps = [s for s in run.trace.steps if s.name == "Sentinel1Client.fetch_latest_rvi"]
    if sar_steps and sar_steps[0].result and sar_steps[0].result.get("rvi") is not None:
        ndvi_fab_set.discard("rvi")

    # If aoi_data provides a real RSM, rsm is not fabricated.
    rsm_info = aoi_result.get("radar_soil_moisture") or {}
    if rsm_info.get("value") is not None and rsm_info.get("source") != "fabricated":
        ndvi_fab_set.discard("rsm")
    
    expected.update(ndvi_fab_set)
    return expected


# Invariant Checks

@invariant(
    id="input_propagation",
    description="Key inputs (lat, lon, crop, area) must be correctly propagated to the report's aoi_info.",
    severity="critical",
    category="correctness"
)
def _(run):
    if not run.output or not run.output.get("aoi_info"):
        return None  # Handled by other checks

    payload = run.case.payload
    aoi_info = run.output["aoi_info"]
    
    errors = []
    
    if not math.isclose(payload.get("lat", 0), aoi_info.get("latitude", -1), abs_tol=1e-4):
        errors.append({"field": "latitude", "expected": payload.get("lat"), "observed": aoi_info.get("latitude")})
        
    if not math.isclose(payload.get("lon", 0), aoi_info.get("longitude", -1), abs_tol=1e-4):
        errors.append({"field": "longitude", "expected": payload.get("lon"), "observed": aoi_info.get("longitude")})

    if payload.get("crop_name") != aoi_info.get("crop"):
        errors.append({"field": "crop", "expected": payload.get("crop_name"), "observed": aoi_info.get("crop")})

    if not math.isclose(payload.get("area_acres", 0), aoi_info.get("area_acres", -1)):
        errors.append({"field": "area_acres", "expected": payload.get("area_acres"), "observed": aoi_info.get("area_acres")})

    if errors:
        return {
            "observed": "Input fields were not correctly propagated to the aoi_info section.",
            "evidence": {"mismatches": errors}
        }
    return None

@invariant(
    id="fabrication_disclosure",
    description="When a data source falls back to a default, the field must be listed in data_quality.fabricated_fields.",
    severity="critical",
    category="contract"
)
def _(run):
    if not run.output:
        return None

    if "data_quality" not in run.output or "fabricated_fields" not in run.output["data_quality"]:
        return {"observed": "The 'data_quality.fabricated_fields' list is missing from the output.", "evidence": {}}

    expected_fabricated = _get_expected_fabricated_fields(run)
    actual_fabricated = set(run.output["data_quality"]["fabricated_fields"])

    missing_disclosures = expected_fabricated - actual_fabricated

    if missing_disclosures:
        return {
            "observed": "Fabricated fields were used but not disclosed in data_quality.fabricated_fields.",
            "evidence": {
                "undisclosed_fabrications": sorted(list(missing_disclosures)),
                "disclosed_fabrications": sorted(list(actual_fabricated)),
                "all_expected_fabrications": sorted(list(expected_fabricated)),
            }
        }
    return None

@invariant(
    id="ndvi_trajectory_logic",
    description="The 'growth_trajectory' component should only exist if input 'ndvi_timeseries' has >1 points.",
    severity="medium",
    category="correctness"
)
def _(run):
    if not run.output or not run.output.get("components"):
        return None

    payload = run.case.payload
    components = run.output["components"]
    
    has_trajectory = "growth_trajectory" in components
    has_sufficient_ndvi_data = isinstance(payload.get("ndvi_timeseries"), list) and len(payload["ndvi_timeseries"]) > 1

    if has_sufficient_ndvi_data and not has_trajectory:
        return {
            "observed": "growth_trajectory component is missing despite sufficient ndvi_timeseries data.",
            "evidence": {"ndvi_timeseries_length": len(payload["ndvi_timeseries"])}
        }
    
    if not has_sufficient_ndvi_data and has_trajectory:
        return {
            "observed": "growth_trajectory component is present despite insufficient ndvi_timeseries data.",
            "evidence": {"ndvi_timeseries": payload.get("ndvi_timeseries")}
        }

    if has_trajectory:
        expected_points = len(payload["ndvi_timeseries"])
        actual_points = components["growth_trajectory"].get("data_points")
        if expected_points != actual_points:
            return {
                "observed": "growth_trajectory.data_points does not match the length of the input ndvi_timeseries.",
                "evidence": {"expected": expected_points, "observed": actual_points}
            }
    
    return None

@invariant(
    id="internal_consistency_soil",
    description="Soil properties in 'soil_management' must be consistent with 'environmental_context'.",
    severity="high",
    category="correctness"
)
def _(run):
    if not run.output or not run.output.get("components", {}).get("soil_management") or not run.output.get("environmental_context", {}).get("soil", {}).get("properties"):
        return None

    soil_mgmt = run.output["components"]["soil_management"]
    soil_ctx = run.output["environmental_context"]["soil"]["properties"]
    
    mismatches = []
    fields_to_check = ["ph", "organic_carbon_percent", "sand_percent", "silt_percent", "clay_percent", "cec"]
    
    for field in fields_to_check:
        mgmt_val = soil_mgmt.get(field)
        ctx_val = soil_ctx.get(field)
        if mgmt_val is None or ctx_val is None:
            continue
        if not math.isclose(mgmt_val, ctx_val, rel_tol=1e-5):
            mismatches.append({"field": field, "soil_management": mgmt_val, "environmental_context": ctx_val})

    if mismatches:
        return {
            "observed": "Soil properties are inconsistent between soil_management and environmental_context.",
            "evidence": {"mismatches": mismatches}
        }
    return None

@invariant(
    id="internal_consistency_terrain",
    description="Terrain data in 'irrigation_schedule' must match 'environmental_context'.",
    severity="high",
    category="correctness"
)
def _(run):
    if not run.output or not run.output.get("components", {}).get("irrigation_schedule", {}).get("terrain") or not run.output.get("environmental_context", {}).get("terrain"):
        return None

    irrigation_terrain = run.output["components"]["irrigation_schedule"]["terrain"]
    context_terrain = run.output["environmental_context"]["terrain"]

    if irrigation_terrain != context_terrain:
        return {
            "observed": "Terrain data is inconsistent between irrigation_schedule and environmental_context.",
            "evidence": {
                "irrigation_schedule_terrain": irrigation_terrain,
                "environmental_context_terrain": context_terrain
            }
        }
    return None

@invariant(
    id="yield_calculation",
    description="Total yield must equal yield per acre multiplied by the area.",
    severity="medium",
    category="accuracy"
)
def _(run):
    if not run.output or not run.output.get("components", {}).get("growth_yield"):
        return None

    gy = run.output["components"]["growth_yield"]
    area = gy.get("area_acres")
    
    errors = []

    if all(k in gy for k in ["yield_per_acre_kg", "total_yield_kg"]) and area is not None:
        expected_total = gy["yield_per_acre_kg"] * area
        if not math.isclose(expected_total, gy["total_yield_kg"], rel_tol=1e-5):
            errors.append({
                "type": "actual_yield",
                "yield_per_acre": gy["yield_per_acre_kg"],
                "area": area,
                "expected_total": expected_total,
                "observed_total": gy["total_yield_kg"]
            })

    if all(k in gy for k in ["yield_potential_kg_per_acre", "yield_potential_total_kg"]) and area is not None:
        expected_potential = gy["yield_potential_kg_per_acre"] * area
        if not math.isclose(expected_potential, gy["yield_potential_total_kg"], rel_tol=1e-5):
            errors.append({
                "type": "potential_yield",
                "yield_potential_per_acre": gy["yield_potential_kg_per_acre"],
                "area": area,
                "expected_total": expected_potential,
                "observed_total": gy["yield_potential_total_kg"]
            })

    if errors:
        return {
            "observed": "Total yield calculation is incorrect.",
            "evidence": {"errors": errors}
        }
    return None


# Metamorphic Checks

@metamorphic(
    id="area_scaling",
    description="Doubling area should double total yields but not affect per-acre metrics.",
    transform=lambda p: {**p, "area_acres": p.get("area_acres", 1) * 2},
    severity="high",
    category="correctness"
)
def _(base, variant):
    if not base.output or not variant.output:
        return None
    if not base.output.get("components", {}).get("growth_yield") or not variant.output.get("components", {}).get("growth_yield"):
        return None

    base_gy = base.output["components"]["growth_yield"]
    var_gy = variant.output["components"]["growth_yield"]
    
    errors = []

    # Check invariant per-acre values
    if not math.isclose(base_gy.get("yield_per_acre_kg", -1), var_gy.get("yield_per_acre_kg", -2), rel_tol=1e-5):
        errors.append({"field": "yield_per_acre_kg", "base": base_gy.get("yield_per_acre_kg"), "variant": var_gy.get("yield_per_acre_kg")})
    
    # Check scaled total values
    if not math.isclose(base_gy.get("total_yield_kg", -1) * 2, var_gy.get("total_yield_kg", -2), rel_tol=1e-5):
        errors.append({"field": "total_yield_kg", "base_x_2": base_gy.get("total_yield_kg", -1) * 2, "variant": var_gy.get("total_yield_kg")})

    if not math.isclose(base_gy.get("yield_potential_total_kg", -1) * 2, var_gy.get("yield_potential_total_kg", -2), rel_tol=1e-5):
        errors.append({"field": "yield_potential_total_kg", "base_x_2": base_gy.get("yield_potential_total_kg", -1) * 2, "variant": var_gy.get("yield_potential_total_kg")})

    if errors:
        return {
            "observed": "Metrics did not scale correctly with area_acres.",
            "evidence": {"mismatches": errors}
        }
    return None

@metamorphic(
    id="sowing_date_impact",
    description="Changing the sowing date should result in a different current growth stage.",
    transform=lambda p: {**p, "sowing_date": "2024-02-15"} if p.get("sowing_date") == "2023-11-10" else {**p, "sowing_date": "2023-10-01"},
    severity="high",
    category="correctness"
)
def _(base, variant):
    if not base.output or not variant.output:
        return None
    if not base.output.get("components", {}).get("growth_yield") or not variant.output.get("components", {}).get("growth_yield"):
        return None

    base_stage = base.output["components"]["growth_yield"].get("current_growth_stage")
    variant_stage = variant.output["components"]["growth_yield"].get("current_growth_stage")

    if base_stage == variant_stage:
        return {
            "observed": "Changing the sowing date had no effect on the calculated current_growth_stage.",
            "evidence": {
                "base_sowing_date": base.case.payload.get("sowing_date"),
                "variant_sowing_date": variant.case.payload.get("sowing_date"),
                "observed_stage": base_stage
            }
        }
    return None

@metamorphic(
    id="ndvi_removal_impact",
    description="Removing NDVI timeseries should trigger fabrication disclosure and remove trajectory analysis.",
    transform=lambda p: {key: value for key, value in p.items() if key != "ndvi_timeseries"},
    severity="critical",
    category="contract"
)
def _(base, variant):
    if not base.output or not variant.output:
        return None

    base_components = base.output.get("components", {})
    variant_components = variant.output.get("components", {})

    # 1. Check for removal of growth_trajectory
    if "growth_trajectory" in variant_components:
        return {
            "observed": "growth_trajectory component was present in the variant run, but should have been removed.",
            "evidence": {"variant_components": list(variant_components.keys())}
        }

    # 2. Check for fabrication disclosure
    base_fab = set(base.output.get("data_quality", {}).get("fabricated_fields", []))
    variant_fab = set(variant.output.get("data_quality", {}).get("fabricated_fields", []))

    # If the base run already had fabricated NDVI, this test is not informative.
    if "ndvi" in base_fab:
        return None

    if "ndvi" not in variant_fab:
        return {
            "observed": "'ndvi' was not disclosed as fabricated after removing the timeseries data.",
            "evidence": {
                "base_fabricated_fields": sorted(list(base_fab)),
                "variant_fabricated_fields": sorted(list(variant_fab))
            }
        }
    
    return None