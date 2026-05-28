"""
ET0 reference evapotranspiration and soil water deficit calculations.
Uses FAO-56 / Hargreaves-Samani methodology.
"""

import math


class IrrigationCalculator:
    """Calculate irrigation water requirements using FAO methodology"""

    @staticmethod
    def calculate_et0_hargreaves_samani(temp_mean: float, temp_max: float, temp_min: float,
                                        solar_radiation: float, lat: float,
                                        day_of_year: int, wind_speed: float = 2) -> float:
        """
        Reference evapotranspiration (ET0) using Hargreaves-Samani (1985).
        Returns ET0 in mm/day.

        Hargreaves-Samani is a temperature-and-extraterrestrial-radiation
        method: `ET0 = 0.0023 · Ra · sqrt(Tmax - Tmin) · (Tmean + 17.8)`,
        where `Ra` is *extraterrestrial* (top-of-atmosphere) radiation
        expressed in mm/day equivalent — NOT measured surface shortwave.
        `_calculate_ra` returns Ra in MJ/m²/day, so we convert with the
        FAO-56 factor (1 mm = 2.45 MJ/m² → ×0.408). `solar_radiation` and
        `wind_speed` are accepted for signature compatibility but unused.
        """
        ra_mj = IrrigationCalculator._calculate_ra(lat, day_of_year)
        ra_mm = ra_mj * 0.408  # MJ/m²/day → mm/day equivalent
        temp_diff = max(0.1, temp_max - temp_min)
        et0 = 0.0023 * ra_mm * math.sqrt(temp_diff) * (temp_mean + 17.8)
        return max(0, et0)

    @staticmethod
    def _calculate_ra(lat: float, day_of_year: int) -> float:
        """Extraterrestrial radiation (Ra) in MJ/m²/day (FAO-56 eq. 21).
        Convert to mm/day equivalent with ×0.408 before use in
        Hargreaves-Samani.
        """
        lat_rad = math.radians(lat)
        b = 2 * math.pi * (day_of_year - 1) / 365.0

        d = (0.006918 - 0.399912 * math.cos(b) + 0.070257 * math.sin(b) -
             0.006758 * math.cos(2*b) + 0.000907 * math.sin(2*b) -
             0.00204 * math.cos(3*b) + 0.00304 * math.sin(3*b))

        omega = math.acos(-math.tan(lat_rad) * math.tan(d))
        dr = 1 + 0.033 * math.cos(2 * math.pi * day_of_year / 365.0)

        Ra = (24 * 60 / math.pi) * 0.0820 * dr * (omega * math.sin(lat_rad) * math.sin(d) +
                                                   math.cos(lat_rad) * math.cos(d) * math.sin(omega))

        return max(0, Ra)

    @staticmethod
    def calculate_kc(crop_name: str, growth_stage: str, rvi: float = 0.5) -> float:
        """Crop coefficient (Kc) from FAO-56, adjusted by RVI."""
        kc_values = {
            "apple": {
                "dormancy": 0.2,
                "budburst": 0.4,
                "flowering": 0.6,
                "fruit_set": 0.7,
                "fruitgrowth": 0.85,
                "mature": 0.9,
                "harvest": 0.7,
            },
            "wheat": {
                "emergence": 0.3,
                "tillering": 0.5,
                "booting": 0.7,
                "heading": 0.85,
                "milkstage": 0.85,
                "dough": 0.7,
                "mature": 0.3,
            },
            "default": {
                "initial": 0.5,
                "mid": 0.8,
                "final": 0.5,
            }
        }

        crop_lower = crop_name.lower()
        crop_kcs = kc_values.get(crop_lower, kc_values["default"])
        base_kc = crop_kcs.get(growth_stage.lower(), 0.5)

        rvi_factor = 0.8 + (rvi * 0.4)
        return base_kc * rvi_factor

    @staticmethod
    def calculate_etc(et0: float, kc: float) -> float:
        """Crop evapotranspiration: ETc = ET0 * Kc."""
        return et0 * kc

    @staticmethod
    def calculate_soil_water_deficit(current_soil_moisture: float,
                                     field_capacity: float = 0.25,
                                     wilting_point: float = 0.12,
                                     depletion_fraction: float = 0.5) -> float:
        """Soil water deficit (mm per 300mm depth) for irrigation triggering."""
        available_water = field_capacity - wilting_point
        readily_available = available_water * depletion_fraction
        threshold_moisture = wilting_point + readily_available

        if current_soil_moisture < threshold_moisture:
            deficit_mm = (threshold_moisture - current_soil_moisture) * 300
            return max(0, deficit_mm)

        return 0
