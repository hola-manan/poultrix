"""
Fertilizer application scheduling.
Translates nutrient gaps into specific product recommendations.
"""

from typing import Dict, Any, List


class FertilizerScheduler:
    """Generate fertilizer application schedule with product/dose recommendations"""

    # Nutrient content (%) of common fertilizer products
    FERTILIZER_GRADES = {
        "urea": {"N": 46},
        "dap": {"N": 18, "P": 46},
        "sop": {"K": 50, "S": 18},
        "mop": {"K": 60},
        "zinc_sulphate": {"Zn": 21},
        "bentonite_sulphur": {"S": 90},
        "vermicompost": {"N": 1.5, "P": 0.6, "K": 1.2, "organic_matter": 50},
        "bone_meal": {"P": 3, "Ca": 24},
        "wood_ash": {"K": 5, "Ca": 30},
        "enriched_fym": {"N": 0.3, "P": 0.15, "K": 0.2, "organic_matter": 40},
    }

    @staticmethod
    def generate_fertilizer_schedule(aoi_data: Dict[str, Any],
                                     nutrient_requirements: Dict[str, Any],
                                     area_acres: float,
                                     application_frequency_days: int = 2) -> Dict[str, Any]:
        crop_name = aoi_data.get("crop_name", "apple").lower()
        growth_stage = aoi_data.get("current_growth_stage", {}).get("stage", "initial")

        schedule = {
            "frequency_days": application_frequency_days,
            "total_nutrient_requirement_kg_acre": {},
            "recommended_products": [],
            "application_details": [],
            "cautions": []
        }

        for nutrient, req_data in nutrient_requirements.items():
            schedule["total_nutrient_requirement_kg_acre"][nutrient] = req_data["gap_kg_per_acre"]

        if crop_name == "apple":
            schedule["recommended_products"] = FertilizerScheduler._get_apple_recommendations(
                nutrient_requirements, area_acres
            )
        elif crop_name == "wheat":
            schedule["recommended_products"] = FertilizerScheduler._get_wheat_recommendations(
                nutrient_requirements, area_acres
            )
        else:
            schedule["recommended_products"] = FertilizerScheduler._get_generic_recommendations(
                nutrient_requirements, area_acres
            )

        schedule["application_details"] = [
            {
                "method": "Drip irrigation (fertigation)",
                "timing": "05:00-08:00 hours (cooler part of day)",
                "soil_ph_benefit": "Slight pH reduction may benefit nutrient availability",
                "precaution": "Avoid peak heat to prevent osmotic stress"
            }
        ]

        if aoi_data.get("soil", {}).get("properties", {}).get("ec", 0.4) > 1.5:
            schedule["cautions"].append("High soil salinity detected - reduce fertilizer concentration to prevent osmotic stress")

        if growth_stage in ["flowering", "fruit_set"]:
            schedule["cautions"].append("During bloom stage - avoid foliar spray during peak temperatures")

        return schedule

    @staticmethod
    def _get_apple_recommendations(nutrient_requirements: Dict[str, Any],
                                   area_acres: float) -> List[Dict[str, Any]]:
        recommendations = []

        n_gap = nutrient_requirements.get("N", {}).get("gap_kg_per_acre", 0)
        p_gap = nutrient_requirements.get("P", {}).get("gap_kg_per_acre", 0)
        k_gap = nutrient_requirements.get("K", {}).get("gap_kg_per_acre", 0)
        s_gap = nutrient_requirements.get("S", {}).get("gap_kg_per_acre", 0)
        zn_gap = nutrient_requirements.get("Zn", {}).get("gap_kg_per_acre", 0)

        if n_gap > 0:
            urea_needed = n_gap / 0.46
            recommendations.append({
                "product": "Urea (46% N)",
                "quantity_kg_acre": round(urea_needed, 2),
                "application_method": "Fertigation via drip",
                "timing": "Split applications every 2 days",
                "notes": "Soluble and suitable for drip fertigation"
            })

        if p_gap > 0:
            dap_needed = (p_gap * 0.7) / 0.46
            bone_meal_needed = (p_gap * 0.3) / 0.03

            recommendations.append({
                "product": "DAP - Diammonium Phosphate (46% P2O5)",
                "quantity_kg_acre": round(dap_needed, 2),
                "application_method": "Fertigation",
                "timing": "With nitrogen applications",
                "notes": "Also provides nitrogen; highly soluble"
            })

            recommendations.append({
                "product": "Bone Meal (3% P)",
                "quantity_kg_acre": round(bone_meal_needed, 2),
                "application_method": "Soil application",
                "timing": "Mix into soil around drip emitters",
                "notes": "Organic source; slow-release phosphorus"
            })

        if k_gap > 0:
            sop_needed = (k_gap * 0.7) / 0.50
            wood_ash_needed = (k_gap * 0.3) / 0.05

            recommendations.append({
                "product": "SOP - Sulphate of Potash (50% K2O)",
                "quantity_kg_acre": round(sop_needed, 2),
                "application_method": "Fertigation",
                "timing": "With other nutrients every 2 days",
                "notes": "Also provides sulfur; may lower soil pH"
            })

            recommendations.append({
                "product": "Wood Ash (5% K)",
                "quantity_kg_acre": round(wood_ash_needed, 2),
                "application_method": "Soil application",
                "timing": "Apply around tree base",
                "notes": "Alkaline; also provides calcium"
            })

        if s_gap > 0:
            bentonite_needed = s_gap / 0.90
            recommendations.append({
                "product": "Bentonite Sulphur (90% S)",
                "quantity_kg_acre": round(bentonite_needed, 2),
                "application_method": "Fertigation",
                "timing": "During fruit set and growth",
                "notes": "Critical for enzyme activation"
            })

        if zn_gap > 0:
            zn_sulphate_needed = zn_gap / 0.21
            recommendations.append({
                "product": "Zinc Sulphate (21% Zn)",
                "quantity_kg_acre": round(zn_sulphate_needed, 2),
                "application_method": "Fertigation or foliar spray",
                "timing": "Monthly during growing season",
                "notes": "Important micronutrient; prevent deficiency chlorosis"
            })

        recommendations.append({
            "product": "Enriched FYM (Farmyard Manure)",
            "quantity_kg_acre": 55.0,
            "application_method": "Soil application (annual)",
            "timing": "Off-season or pre-planting",
            "notes": "Improves soil structure and organic carbon"
        })

        recommendations.append({
            "product": "Vermicompost",
            "quantity_kg_acre": round(n_gap / 0.015, 2),
            "application_method": "Soil application around trees",
            "timing": "Split applications; 2-3 times per season",
            "notes": "Improves soil biology and nutrient availability"
        })

        return recommendations

    @staticmethod
    def _get_wheat_recommendations(nutrient_requirements: Dict[str, Any],
                                   area_acres: float) -> List[Dict[str, Any]]:
        recommendations = []

        n_gap = nutrient_requirements.get("N", {}).get("gap_kg_per_acre", 0)
        p_gap = nutrient_requirements.get("P", {}).get("gap_kg_per_acre", 0)
        k_gap = nutrient_requirements.get("K", {}).get("gap_kg_per_acre", 0)

        if n_gap > 0:
            urea_base = n_gap * 0.5 / 0.46
            urea_top = n_gap * 0.5 / 0.46

            recommendations.append({
                "product": "Urea (46% N) - Base application",
                "quantity_kg_acre": round(urea_base, 2),
                "application_method": "Broadcast + incorporation at sowing",
                "timing": "Pre-sowing",
                "notes": "50% of N requirement"
            })

            recommendations.append({
                "product": "Urea (46% N) - Top dressing",
                "quantity_kg_acre": round(urea_top, 2),
                "application_method": "Top dress during tillering",
                "timing": "At tillering stage (30-40 DAS)",
                "notes": "50% of N requirement; critical for grain fill"
            })

        if p_gap > 0:
            dap_needed = p_gap / 0.20

            recommendations.append({
                "product": "DAP - Diammonium Phosphate",
                "quantity_kg_acre": round(dap_needed, 2),
                "application_method": "Broadcast at sowing",
                "timing": "Pre-sowing incorporation",
                "notes": "Ensures available P at seedling stage"
            })

        if k_gap > 0:
            mop_needed = k_gap / 0.60

            recommendations.append({
                "product": "MOP - Muriate of Potash",
                "quantity_kg_acre": round(mop_needed, 2),
                "application_method": "Broadcast + incorporation",
                "timing": "Pre-sowing",
                "notes": "For K-deficient soils"
            })

        return recommendations

    @staticmethod
    def _get_generic_recommendations(nutrient_requirements: Dict[str, Any],
                                     area_acres: float) -> List[Dict[str, Any]]:
        recommendations = []

        for nutrient, req_data in nutrient_requirements.items():
            gap = req_data.get("gap_kg_per_acre", 0)
            if gap > 0:
                recommendations.append({
                    "product": f"{nutrient} - Generic source",
                    "quantity_kg_acre": round(gap, 2),
                    "application_method": "As per soil and water conditions",
                    "timing": "According to growth stage",
                    "notes": f"Based on {gap:.1f} kg/acre gap"
                })

        return recommendations
