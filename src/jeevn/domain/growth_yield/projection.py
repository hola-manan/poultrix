"""
Yield projection from vegetation indices, nutrient status, and growth stage.
"""

from typing import Dict, Any


class YieldGrowthCalculator:
    """Calculate yield projections and growth indicators"""

    @staticmethod
    def calculate_yield_projection(aoi_data: Dict[str, Any],
                                   ndvi_data: Dict[str, Any],
                                   area_acres: float) -> Dict[str, Any]:
        crop_name = aoi_data.get("crop_name", "apple")
        crop_data = aoi_data.get("crop", {})
        growth_stage = aoi_data.get("current_growth_stage", {})

        yield_potential = crop_data.get("yield_potential_kg_per_acre", 2000)

        rvi = ndvi_data["rvi"]
        ndvi = ndvi_data["ndvi"]

        stage_name = growth_stage.get("stage", "initial")
        ndvi_range = growth_stage.get("ndvi_range", (0, 1))

        yield_projection = {
            "crop": crop_name,
            "area_acres": area_acres,
            "yield_potential_kg_per_acre": yield_potential,
            "yield_potential_total_kg": round(yield_potential * area_acres, 1),
        }

        vigor_score = YieldGrowthCalculator._assess_vegetation_vigor(rvi, ndvi, ndvi_range)
        yield_projection["vegetation_vigor"] = vigor_score["rating"]
        yield_projection["vegetation_vigor_score"] = round(vigor_score["score"], 2)

        stage_assessment = YieldGrowthCalculator._assess_growth_stage(
            stage_name, crop_name, aoi_data.get("days_since_sowing", 60)
        )
        yield_projection["current_growth_stage"] = stage_name
        yield_projection["growth_stage_assessment"] = stage_assessment

        reduction_factors = YieldGrowthCalculator._calculate_reduction_factors(
            aoi_data, ndvi_data, stage_name, crop_name
        )

        adjusted_yield = yield_potential
        for factor_name, reduction_percent in reduction_factors.items():
            adjusted_yield *= (1 - (reduction_percent / 100))

        yield_projection["yield_per_acre_kg"] = round(max(0, adjusted_yield), 0)
        yield_projection["total_yield_kg"] = round(max(0, adjusted_yield * area_acres), 1)
        yield_projection["potential_loss_percent"] = round(
            ((yield_potential - adjusted_yield) / yield_potential) * 100, 1
        )

        yield_projection["harvest_status"] = YieldGrowthCalculator._determine_harvest_status(
            stage_name, crop_name, aoi_data.get("days_since_sowing", 60)
        )

        yield_projection["limiting_factors"] = [
            {
                "factor": name,
                "impact": f"{reduction:.1f}% yield reduction" if reduction > 5 else "Minor impact"
            }
            for name, reduction in reduction_factors.items() if reduction > 0
        ]

        return yield_projection

    @staticmethod
    def _assess_vegetation_vigor(rvi: float, ndvi: float, ndvi_range: tuple) -> Dict[str, Any]:
        if rvi >= 0.75:
            rating = "Excellent"
            score = 95
        elif rvi >= 0.65:
            rating = "Good"
            score = 80
        elif rvi >= 0.50:
            rating = "Moderate"
            score = 60
        elif rvi >= 0.35:
            rating = "Poor"
            score = 35
        else:
            rating = "Very Poor"
            score = 15

        if ndvi < ndvi_range[0]:
            score *= 0.85
        elif ndvi > ndvi_range[1]:
            score *= 0.9

        return {
            "rating": rating,
            "score": min(100, max(0, score))
        }

    @staticmethod
    def _assess_growth_stage(stage_name: str, crop_name: str, days_since_sowing: int) -> str:
        stage_timing = {
            "apple": {
                "dormancy": (0, 120),
                "budburst": (120, 150),
                "flowering": (150, 170),
                "fruit_set": (170, 185),
                "fruitgrowth": (185, 275),
                "mature": (275, 305),
                "harvest": (305, 319),
            },
            "wheat": {
                "emergence": (0, 15),
                "tillering": (15, 60),
                "booting": (60, 80),
                "heading": (80, 90),
                "milkstage": (90, 110),
                "dough": (110, 125),
                "mature": (125, 135),
            }
        }

        crop_stages = stage_timing.get(crop_name.lower(), stage_timing["wheat"])
        stage_range = crop_stages.get(stage_name, (0, 365))

        if stage_range[0] <= days_since_sowing <= stage_range[1]:
            return "On schedule"
        elif days_since_sowing < stage_range[0]:
            return f"Early by {stage_range[0] - days_since_sowing} days (delayed development)"
        else:
            return f"Late by {days_since_sowing - stage_range[1]} days (accelerated development)"

    @staticmethod
    def _calculate_reduction_factors(aoi_data: Dict[str, Any],
                                     ndvi_data: Dict[str, Any],
                                     stage_name: str,
                                     crop_name: str) -> Dict[str, float]:
        reductions = {}

        rvi = ndvi_data["rvi"]
        if rvi < 0.60:
            reductions["Nutrient deficiency"] = 15.0
        elif rvi < 0.70:
            reductions["Moderate nutrient stress"] = 8.0

        weather = aoi_data.get("weather", {}).get("daily", {})
        temp_mean = weather.get("temp_mean", [30])[-1] if weather.get("temp_mean") else 30
        rainfall = weather.get("rainfall", [0])[-1] if weather.get("rainfall") else 0

        humidity_estimate = min(100, 40 + (rainfall * 2) + (30 - temp_mean) * 2)

        if humidity_estimate > 70 and stage_name in ["flowering", "fruit_set"]:
            reductions["Pest/disease pressure"] = 10.0

        soil = aoi_data.get("soil", {})
        soil_moisture = soil.get("properties", {})["soil_moisture_current"]

        if soil_moisture < 0.50:
            reductions["Water stress"] = 20.0
        elif soil_moisture < 0.60:
            reductions["Mild water stress"] = 5.0

        if stage_name == "flowering" and rvi < 0.60:
            reductions["Poor pollination potential"] = 5.0

        if crop_name.lower() == "apple" and rvi < 0.70:
            reductions["Reduced canopy density"] = 5.0

        return reductions

    @staticmethod
    def _determine_harvest_status(stage_name: str, crop_name: str,
                                  days_since_sowing: int) -> str:
        harvest_stages = {
            "apple": ("mature", 275, 305),
            "wheat": ("mature", 125, 135),
        }

        crop_info = harvest_stages.get(crop_name.lower(), ("mature", 100, 150))
        harvest_stage, min_days, max_days = crop_info

        if stage_name == harvest_stage:
            if min_days <= days_since_sowing <= max_days:
                return "ready"
            elif days_since_sowing < min_days:
                return "incomplete"
            else:
                return "overripe"
        elif days_since_sowing < min_days:
            return "incomplete"
        else:
            return "ready"
