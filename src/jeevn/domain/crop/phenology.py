"""
Crop phenology — pure static lookup data.
Defines growth stages, nutrient requirements, and yield potentials per crop.
"""

from typing import Dict, Any


class CropPhenologyDatabase:
    """Database of crop-specific phenology, coefficients, and requirements"""

    CROP_DATA = {
        "apple": {
            "t_base": 4.4,
            "growth_stages": {
                "dormancy": {"days": 120, "gdd": 0, "kc": 0.3, "ndvi_range": (0.0, 0.2)},
                "budburst": {"days": 30, "gdd": 200, "kc": 0.4, "ndvi_range": (0.2, 0.4)},
                "flowering": {"days": 20, "gdd": 150, "kc": 0.6, "ndvi_range": (0.4, 0.6)},
                "fruit_set": {"days": 15, "gdd": 150, "kc": 0.7, "ndvi_range": (0.6, 0.7)},
                "fruitgrowth": {"days": 90, "gdd": 900, "kc": 0.8, "ndvi_range": (0.65, 0.8)},
                "mature": {"days": 30, "gdd": 300, "kc": 0.9, "ndvi_range": (0.75, 0.85)},
                "harvest": {"days": 14, "gdd": 140, "kc": 0.7, "ndvi_range": (0.7, 0.8)},
            },
            "nutrient_requirements_kg_per_acre": {
                "N": {"low": 18.2, "optimal": 27.3, "high": 36.4},
                "P": {"low": 13.7, "optimal": 22.8, "high": 31.8},
                "K": {"low": 109.2, "optimal": 163.8, "high": 218.4},
                "S": {"low": 9.1, "optimal": 13.7, "high": 18.2},
                "Zn": {"low": 0.9, "optimal": 1.8, "high": 2.7},
            },
            "yield_potential_kg_per_acre": 2500,
            "harvest_window_days": 14,
            "maturity_days": 120,
            "low_chill_variety": True,
        },
        "wheat": {
            "t_base": 4.0,
            "growth_stages": {
                "emergence": {"days": 15, "gdd": 150, "kc": 0.3, "ndvi_range": (0.1, 0.3)},
                "tillering": {"days": 45, "gdd": 450, "kc": 0.5, "ndvi_range": (0.3, 0.5)},
                "booting": {"days": 20, "gdd": 250, "kc": 0.7, "ndvi_range": (0.5, 0.65)},
                "heading": {"days": 10, "gdd": 120, "kc": 0.8, "ndvi_range": (0.65, 0.75)},
                "milkstage": {"days": 20, "gdd": 240, "kc": 0.8, "ndvi_range": (0.7, 0.75)},
                "dough": {"days": 15, "gdd": 200, "kc": 0.7, "ndvi_range": (0.6, 0.7)},
                "mature": {"days": 10, "gdd": 100, "kc": 0.4, "ndvi_range": (0.3, 0.5)},
            },
            "nutrient_requirements_kg_per_acre": {
                "N": {"low": 36.4, "optimal": 54.6, "high": 72.8},
                "P": {"low": 18.2, "optimal": 27.3, "high": 36.4},
                "K": {"low": 18.2, "optimal": 27.3, "high": 36.4},
            },
            "yield_potential_kg_per_acre": 3650,
            "maturity_days": 120,
        },
        # Grape (table/wine, Nashik-Sangli belt) — the pilot crop. The season
        # is modelled from forward (fruit) pruning (~Oct) through harvest
        # (~Feb-Mar), ~155 days. t_base 10 deg C is the standard Vitis
        # vinifera GDD base. Stages map to the disease/yield logic: `flowering`
        # and `fruit_set` drive the humidity/pollination branches, `harvest`
        # anchors harvest-status. Grapes are heavy K feeders, hence the
        # K-weighted nutrient targets.
        "grape": {
            "t_base": 10.0,
            "growth_stages": {
                "budburst": {"days": 10, "gdd": 150, "kc": 0.3, "ndvi_range": (0.20, 0.35)},
                "shoot_growth": {"days": 30, "gdd": 450, "kc": 0.5, "ndvi_range": (0.35, 0.55)},
                "flowering": {"days": 15, "gdd": 220, "kc": 0.7, "ndvi_range": (0.55, 0.70)},
                "fruit_set": {"days": 15, "gdd": 220, "kc": 0.8, "ndvi_range": (0.60, 0.75)},
                "berry_development": {"days": 35, "gdd": 520, "kc": 0.85, "ndvi_range": (0.65, 0.80)},
                "veraison": {"days": 20, "gdd": 300, "kc": 0.8, "ndvi_range": (0.60, 0.75)},
                "ripening": {"days": 20, "gdd": 300, "kc": 0.7, "ndvi_range": (0.55, 0.70)},
                "harvest": {"days": 10, "gdd": 150, "kc": 0.6, "ndvi_range": (0.50, 0.65)},
            },
            "nutrient_requirements_kg_per_acre": {
                "N": {"low": 36.0, "optimal": 50.0, "high": 64.0},
                "P": {"low": 16.0, "optimal": 24.0, "high": 32.0},
                "K": {"low": 60.0, "optimal": 90.0, "high": 120.0},
                "S": {"low": 8.0, "optimal": 14.0, "high": 20.0},
                "Zn": {"low": 0.9, "optimal": 1.8, "high": 2.7},
            },
            "yield_potential_kg_per_acre": 10000,
            "maturity_days": 155,
        }
    }

    @staticmethod
    def get_crop_data(crop_name: str) -> Dict[str, Any]:
        crop_lower = crop_name.lower()
        return CropPhenologyDatabase.CROP_DATA.get(crop_lower, CropPhenologyDatabase.CROP_DATA["wheat"])

    @staticmethod
    def get_current_growth_stage(crop_name: str, days_since_sowing: int, accumulated_gdd: float = 0) -> Dict[str, Any]:
        crop_data = CropPhenologyDatabase.get_crop_data(crop_name)
        stages = crop_data.get("growth_stages", {})

        cumulative_days = 0
        cumulative_gdd = 0
        for stage_name, stage_data in stages.items():
            cumulative_days += stage_data.get("days", 0)
            cumulative_gdd += stage_data.get("gdd", stage_data.get("days", 0) * 15)

            if accumulated_gdd > 0:
                if accumulated_gdd <= cumulative_gdd:
                    return {
                        "stage": stage_name,
                        "kc": stage_data.get("kc", 0.5),
                        "ndvi_range": stage_data.get("ndvi_range", (0, 1)),
                        "days_in_stage": days_since_sowing,
                        "gdd_in_stage": round(accumulated_gdd - (cumulative_gdd - stage_data.get("gdd", 0)), 1)
                    }
            else:
                if days_since_sowing <= cumulative_days:
                    return {
                        "stage": stage_name,
                        "kc": stage_data.get("kc", 0.5),
                        "ndvi_range": stage_data.get("ndvi_range", (0, 1)),
                        "days_in_stage": days_since_sowing - max(0, cumulative_days - stage_data.get("days", 0))
                    }

        return {
            "stage": list(stages.keys())[-1] if stages else "unknown",
            "kc": 0.3,
            "ndvi_range": (0, 0.5),
            "days_in_stage": 0,
            "gdd_in_stage": 0
        }
