"""
Soil management analysis and recommendations
"""

from typing import Dict, Any

class SoilManagementCalculator:
    """Calculate soil management metrics and recommendations"""

    @staticmethod
    def analyze_soil(aoi_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze soil conditions and provide recommendations

        Args:
            aoi_data: Agricultural data from data_fetcher

        Returns:
            Soil analysis dict with status and recommendations
        """

        soil = aoi_data.get("soil", {})
        soil_props = soil.get("properties", {})

        analysis = {
            "ph": round(soil_props.get("ph", 7.0), 1),
            "salinity": SoilManagementCalculator._classify_salinity(soil_props.get("ec", 0.4)),
            "organic_carbon_percent": round(soil_props.get("organic_carbon_percent", 0.15), 2),
            "organic_carbon_status": SoilManagementCalculator._classify_organic_carbon(
                soil_props.get("organic_carbon_percent", 0.15),
                aoi_data.get("crop_name", "apple")
            ),
            "texture": soil_props.get("texture", "loam"),
            "sand_percent": soil_props.get("sand_percent"),
            "silt_percent": soil_props.get("silt_percent"),
            "clay_percent": soil_props.get("clay_percent"),
            "cec": soil_props.get("cec"),
            "cec_status": SoilManagementCalculator._classify_cec(soil_props.get("cec")),
            "water_holding_capacity_mm": soil_props.get("water_holding_capacity", 18),
            "infiltration_rate_mm_h": soil_props.get("infiltration_rate", 12),
            "soil_moisture_current": round(soil_props["soil_moisture_current"], 2),
        }

        # Apply Saxton & Rawls (2006) pedotransfer function if we have exact texture
        s, c, oc = analysis.get("sand_percent"), analysis.get("clay_percent"), analysis.get("organic_carbon_percent")
        if s is not None and c is not None and oc is not None:
            fc, pwp = SoilManagementCalculator.calculate_saxton_rawls(s, c, oc)
            analysis["field_capacity_vol"] = round(fc, 3)
            analysis["permanent_wilting_point_vol"] = round(pwp, 3)
            # AWC in mm/m = (FC - PWP) * 1000
            awc_mm_m = (fc - pwp) * 1000
            analysis["water_holding_capacity_mm_m"] = round(awc_mm_m, 1)

        analysis["detailed_findings"] = SoilManagementCalculator._generate_findings(
            analysis, aoi_data.get("crop_name", "apple")
        )

        analysis["recommendations"] = SoilManagementCalculator._get_recommendations(analysis)

        return analysis

    @staticmethod
    def _classify_salinity(ec: float) -> str:
        if ec < 0.25:
            return "negligible"
        elif ec < 0.75:
            return "low"
        elif ec < 2.25:
            return "moderate"
        else:
            return "high"

    @staticmethod
    def _classify_cec(cec):
        """USDA-style CEC classification in cmol(+)/kg.
        <10 = low (sandy), 10-25 = moderate, >25 = high (clay/organic).
        Returns None when CEC is unknown so the UI can hide the row.
        """
        if cec is None:
            return None
        if cec < 10:
            return "low (sandy / low organic matter)"
        if cec < 25:
            return "moderate"
        return "high (clay-rich or high organic matter)"

    @staticmethod
    def _classify_organic_carbon(soc_percent: float, crop: str = "apple") -> str:
        if crop.lower() == "apple":
            min_level = 1.0
            optimal_level = 2.5
        else:
            min_level = 0.8
            optimal_level = 2.0

        if soc_percent < 0.5:
            return f"critically low (current: {soc_percent}%, min required: {min_level}%)"
        elif soc_percent < min_level:
            return f"low (current: {soc_percent}%, target: {optimal_level}%)"
        elif soc_percent < optimal_level:
            return f"moderate (current: {soc_percent}%, optimal: {optimal_level}%)"
        else:
            return f"optimal (current: {soc_percent}%)"

    @staticmethod
    def _generate_findings(analysis: Dict[str, Any], crop: str) -> str:
        findings = []

        if 6.0 <= analysis["ph"] <= 8.0:
            findings.append(f"Soil pH is {analysis['ph']}, which is within acceptable range for {crop} cultivation.")
        elif analysis["ph"] < 6.0:
            findings.append(f"Soil pH is {analysis['ph']} (acidic). Lime application may be beneficial.")
        else:
            findings.append(f"Soil pH is {analysis['ph']} (alkaline). May limit micronutrient availability.")

        if analysis["salinity"] == "low":
            findings.append("Soil salinity is low, indicating good drainage and no salt accumulation issues.")
        elif analysis["salinity"] in ["moderate", "high"]:
            findings.append(f"Soil salinity is {analysis['salinity']}. Monitor for salt stress and consider leaching fraction.")

        findings.append(f"Soil organic carbon is {analysis['organic_carbon_status']}.")

        # Texture composition — emitted only when real sand/silt/clay are
        # available (SoilGrids fetch succeeded).
        s, si, c = analysis.get("sand_percent"), analysis.get("silt_percent"), analysis.get("clay_percent")
        if s is not None and si is not None and c is not None:
            findings.append(
                f"Soil texture is {analysis['texture']} "
                f"(sand {s:.0f}%, silt {si:.0f}%, clay {c:.0f}%)."
            )

        cec_status = analysis.get("cec_status")
        if cec_status and analysis.get("cec") is not None:
            findings.append(
                f"Cation exchange capacity is {analysis['cec']:.1f} cmol(+)/kg ({cec_status})."
            )

        if "water_holding_capacity_mm_m" in analysis:
            awc = analysis["water_holding_capacity_mm_m"]
            fc = analysis["field_capacity_vol"]
            pwp = analysis["permanent_wilting_point_vol"]
            findings.append(f"Saxton & Rawls PTF calculated Volumetric Field Capacity at {fc:.3f} m³/m³ and PWP at {pwp:.3f} m³/m³, yielding an Available Water Capacity of {awc:.1f} mm/m.")
            if awc < 100:
                findings.append("Low water-holding capacity; frequent irrigation will be necessary.")
            elif awc < 150:
                findings.append("Moderate water-holding capacity; typical for sandy/loam soils.")
            else:
                findings.append("Good water-holding capacity; supports longer intervals between irrigations.")
        else:
            if analysis["water_holding_capacity_mm"] < 15:
                findings.append("Low water-holding capacity; frequent irrigation will be necessary.")
            elif analysis["water_holding_capacity_mm"] < 20:
                findings.append("Moderate water-holding capacity; typical for sandy loam soils.")
            else:
                findings.append("Good water-holding capacity; supports longer intervals between irrigations.")

        return " ".join(findings)

    @staticmethod
    def calculate_saxton_rawls(sand_pct: float, clay_pct: float, organic_carbon_pct: float) -> tuple[float, float]:
        """
        Saxton & Rawls (2006) Pedotransfer Functions (PTF).
        Mathematically converts soil texture and organic matter into 
        exact volumetric water thresholds: Field Capacity (FC) and Permanent Wilting Point (PWP).
        
        Args:
            sand_pct: Sand percentage (0-100)
            clay_pct: Clay percentage (0-100)
            organic_carbon_pct: Soil Organic Carbon percentage
            
        Returns:
            Tuple of (Field Capacity m³/m³, Permanent Wilting Point m³/m³)
        """
        # Convert fractions
        S = sand_pct / 100.0
        C = clay_pct / 100.0
        # Convert Soil Organic Carbon to Soil Organic Matter
        OM = organic_carbon_pct * 1.724

        # PWP at -1500 kPa
        theta_1500t = -0.024*S + 0.487*C + 0.006*OM + 0.005*(S*OM) - 0.013*(C*OM) + 0.068*(S*C) + 0.031
        pwp = theta_1500t + (0.14 * theta_1500t - 0.02)
        
        # FC at -33 kPa
        theta_33t = -0.251*S + 0.195*C + 0.011*OM + 0.006*(S*OM) - 0.027*(C*OM) + 0.452*(S*C) + 0.299
        fc = theta_33t + (1.283 * (theta_33t**2) - 0.374 * theta_33t - 0.015)
        
        return max(0.0, min(fc, 1.0)), max(0.0, min(pwp, fc))

    @staticmethod
    def _get_recommendations(analysis: Dict[str, Any]) -> list:
        recommendations = []

        if "critically low" in analysis["organic_carbon_status"] or "low" in analysis["organic_carbon_status"]:
            recommendations.append({
                "category": "Organic Carbon Enhancement",
                "practices": [
                    "Incorporate well-rotted farmyard manure (20-25 tons/hectare)",
                    "Use compost or vermicompost at 5-10 tons/hectare",
                    "Implement cover cropping during off-season (clover, legumes, grasses)",
                    "Apply mulching around trees (4-6 inch depth)",
                    "Avoid soil disturbance; adopt conservation tillage where applicable"
                ],
                "timeline": "Continuous over 2-3 years for noticeable improvement"
            })

        if analysis["ph"] < 6.0:
            recommendations.append({
                "category": "pH Management",
                "practices": ["Apply lime at 2-4 tons/hectare for acid soils"],
                "timeline": "Apply in off-season; work into soil 2-3 months before planting"
            })

        if analysis["salinity"] in ["moderate", "high"]:
            recommendations.append({
                "category": "Salinity Management",
                "practices": [
                    "Ensure adequate leaching fraction in irrigation (15-20%)",
                    "Use drip irrigation with soil moisture monitoring",
                    "Apply gypsum to improve soil structure (2-4 tons/hectare for high salinity)"
                ],
                "timeline": "Implement immediately during growing season"
            })

        if not recommendations:
            recommendations.append({
                "category": "Soil Maintenance",
                "practices": [
                    "Continue current soil management practices",
                    "Monitor soil moisture regularly",
                    "Apply light organic amendments annually"
                ],
                "timeline": "Ongoing"
            })

        return recommendations
