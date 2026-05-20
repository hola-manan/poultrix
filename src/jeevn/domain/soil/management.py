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
            "water_holding_capacity_mm": soil_props.get("water_holding_capacity", 18),
            "infiltration_rate_mm_h": soil_props.get("infiltration_rate", 12),
            "soil_moisture_current": round(soil_props["soil_moisture_current"], 2),
        }

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

        if analysis["water_holding_capacity_mm"] < 15:
            findings.append("Low water-holding capacity; frequent irrigation will be necessary.")
        elif analysis["water_holding_capacity_mm"] < 20:
            findings.append("Moderate water-holding capacity; typical for sandy loam soils.")
        else:
            findings.append("Good water-holding capacity; supports longer intervals between irrigations.")

        return " ".join(findings)

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
