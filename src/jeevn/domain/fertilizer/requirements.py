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

        # Legacy fallback constants (used only for a nutrient that NO resolver
        # tier could estimate). Historically these were the *only* values and
        # were flagged in code as placeholders ("real system would use soil
        # test results"). They now sit behind the tiered NPK resolver.
        _FALLBACK_CURRENT = {"N": 13.65, "P": 11.0, "K": 82.0, "S": 7.0, "Zn": 0.8}

        # Per-nutrient soil-supply profile resolved upstream (soil test → SHC
        # district → SoilGrids/pedotransfer). Maps nutrient → {supply_fraction,
        # status, source, confidence}. Absent nutrients fall back to the constant.
        profile = aoi_data.get("soil_nutrients") or {}

        requirements = {}

        for nutrient in ["N", "P", "K", "S", "Zn"]:
            nutrient_req = nutrient_reqs.get(nutrient, {})

            if isinstance(nutrient_req, dict):
                target_optimal = nutrient_req.get("optimal", 10)
            else:
                target_optimal = nutrient_req

            prof = profile.get(nutrient)
            if prof and prof.get("supply_fraction") is not None:
                # Real/estimated soil supply as a fraction of the crop's
                # recommended dose (unit-consistent with `target_optimal`).
                current = prof["supply_fraction"] * target_optimal
                source = prof.get("source", "estimate")
                confidence = prof.get("confidence", "low")
                status_hint = prof.get("status")
            else:
                current = _FALLBACK_CURRENT.get(nutrient, 0)
                source = "fabricated"
                confidence = "none"
                status_hint = None

            rvi_factor = 0.8 + (rvi * 0.4)
            adjusted_target = target_optimal * rvi_factor

            gap = max(0, adjusted_target - current)

            requirements[nutrient] = {
                "current_kg_per_acre": round(current, 2),
                "target_kg_per_acre": f"{nutrient_req.get('low', adjusted_target - 5):.1f}-{adjusted_target:.1f}",
                "gap_kg_per_acre": round(gap, 2),
                "status": status_hint or NutrientRequirementCalculator._classify_nutrient_status(current, target_optimal),
                # Provenance so the advisory layer can confidence-gate fertilizer
                # alerts and the report can flag placeholder-derived doses.
                "source": source,
                "confidence": confidence,
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
