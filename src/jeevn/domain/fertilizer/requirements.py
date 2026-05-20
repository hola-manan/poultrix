"""
Nutrient requirement calculations.
Computes per-nutrient gaps from current soil levels vs. crop targets.
"""

from typing import Dict, Any


class NutrientRequirementCalculator:
    """Calculate nutrient requirements for a crop"""

    @staticmethod
    def calculate_nutrient_requirements(aoi_data: Dict[str, Any],
                                        area_acres: float,
                                        rvi: float,
                                        yield_potential_kg_acre: float = None) -> Dict[str, Any]:
        crop_data = aoi_data.get("crop", {})
        crop_name = aoi_data.get("crop_name", "apple")

        if not yield_potential_kg_acre:
            yield_potential_kg_acre = crop_data.get("yield_potential_kg_per_acre", 2000)

        nutrient_reqs = crop_data.get("nutrient_requirements_kg_per_acre", {})

        # Example current soil levels (real system would use soil test results)
        current_levels = {
            "N": 13.65,
            "P": 11.0,
            "K": 82.0,
            "S": 7.0,
            "Zn": 0.8,
        }

        requirements = {}

        for nutrient in ["N", "P", "K", "S", "Zn"]:
            nutrient_req = nutrient_reqs.get(nutrient, {})
            current = current_levels.get(nutrient, 0)

            if isinstance(nutrient_req, dict):
                target_optimal = nutrient_req.get("optimal", current + 10)
            else:
                target_optimal = nutrient_req

            rvi_factor = 0.8 + (rvi * 0.4)
            adjusted_target = target_optimal * rvi_factor

            gap = max(0, adjusted_target - current)

            requirements[nutrient] = {
                "current_kg_per_acre": round(current, 2),
                "target_kg_per_acre": f"{nutrient_req.get('low', adjusted_target - 5):.1f}-{adjusted_target:.1f}",
                "gap_kg_per_acre": round(gap, 2),
                "status": NutrientRequirementCalculator._classify_nutrient_status(current, target_optimal),
            }

        return requirements

    @staticmethod
    def _classify_nutrient_status(current: float, target: float) -> str:
        if current < target * 0.5:
            return "critical"
        elif current < target * 0.8:
            return "moderate"
        else:
            return "adequate"
