"""
Agricultural advisory service.
Orchestrates domain calculations and produces the full advisory report DTO.
This is the single source of truth that API and UI both consume.

Whenever a real measurement is missing and a pseudo default is substituted,
the field name is added to `report["data_quality"]["fabricated_fields"]`
so the UI/PDF can surface the warning to the user.
"""

from typing import Dict, Any, List, Tuple
from datetime import datetime

from jeevn.infrastructure.data_sources.aoi import fetch_aoi_data
from jeevn.infrastructure import pseudo_satellite
from jeevn.domain.irrigation import IrrigationScheduler
from jeevn.domain.soil import SoilManagementCalculator
from jeevn.domain.fertilizer import NutrientRequirementCalculator, FertilizerScheduler
from jeevn.domain.pest_disease_weed import PestDiseaseWeedAssessor
from jeevn.domain.growth_yield import YieldGrowthCalculator, GrowthMonitoring


class AgriculturalReportGenerator:
    """Generate comprehensive agricultural advisory report."""

    @staticmethod
    def generate_report(lat: float, lon: float,
                        area_acres: float = pseudo_satellite.DEFAULT_AREA_ACRES,
                        crop_name: str = pseudo_satellite.DEFAULT_CROP_NAME,
                        sowing_date: str = None,
                        ndvi_timeseries: list = None,
                        ndvi_raster_data: Dict[str, Any] = None,
                        location_name: str = "") -> Dict[str, Any]:
        """Generate complete agricultural advisory report."""

        aoi_data = fetch_aoi_data(
            lat, lon, location_name,
            crop_name=crop_name, sowing_date=sowing_date,
        )
        aoi_fabricated = aoi_data.pop("_fabricated_sources", [])

        ndvi_data, ndvi_fabricated = AgriculturalReportGenerator._process_ndvi_data(
            ndvi_timeseries, ndvi_raster_data,
        )

        report: Dict[str, Any] = {
            "report_date": datetime.now().strftime("%d/%m/%Y"),
            "aoi_info": {
                "area_acres": area_acres,
                "location": aoi_data["location"].get("name", location_name),
                "crop": crop_name,
                "state": aoi_data["location"].get("state", ""),
                "latitude": round(lat, 4),
                "longitude": round(lon, 4),
                "satellite_visit": datetime.now().strftime("%d %b %Y"),
            },
            "components": {},
        }

        report["components"]["field_maps"] = {
            "crop_health_map": ndvi_raster_data.get("crop_health_path") if ndvi_raster_data else None,
            "irrigation_health_map": ndvi_raster_data.get("irrigation_health_path") if ndvi_raster_data else None,
            "ndvi_raster": ndvi_raster_data.get("ndvi_raster") if ndvi_raster_data else None,
        }

        report["components"]["irrigation_schedule"] = IrrigationScheduler.generate_schedule(
            aoi_data, ndvi_data, area_acres,
        )

        report["components"]["soil_management"] = SoilManagementCalculator.analyze_soil(aoi_data)

        report["components"]["growth_yield"] = YieldGrowthCalculator.calculate_yield_projection(
            aoi_data, ndvi_data, area_acres,
        )

        if ndvi_timeseries and len(ndvi_timeseries) > 1:
            report["components"]["growth_trajectory"] = GrowthMonitoring.analyze_growth_trajectory(
                ndvi_timeseries,
            )

        report["components"]["pest_disease_weed"] = PestDiseaseWeedAssessor.assess_pest_disease_risk(
            aoi_data, ndvi_data,
        )

        nutrient_requirements = NutrientRequirementCalculator.calculate_nutrient_requirements(
            aoi_data, area_acres, rvi=ndvi_data["rvi"],
        )
        fertilizer_schedule = FertilizerScheduler.generate_fertilizer_schedule(
            aoi_data, nutrient_requirements, area_acres,
        )
        report["components"]["fertilizer_management"] = {
            "nutrient_requirements": nutrient_requirements,
            "fertilizer_schedule": fertilizer_schedule,
        }

        report["environmental_context"] = {
            "weather": aoi_data.get("weather", {}),
            "soil": aoi_data.get("soil", {}),
            "growth_stage": aoi_data.get("current_growth_stage", {}),
        }

        report["summary"] = AgriculturalReportGenerator._generate_summary(report)

        # Data-quality block: which inputs were fabricated this run.
        fabricated = sorted(set(aoi_fabricated + ndvi_fabricated))
        report["data_quality"] = {
            "fabricated_fields": fabricated,
            "details": {f: pseudo_satellite.describe(f) for f in fabricated},
            "warning": (
                "Some inputs to this report are fabricated defaults — see "
                "`fabricated_fields`. Treat the affected outputs as illustrative."
                if fabricated else
                "All inputs were obtained from real sources."
            ),
        }

        return report

    @staticmethod
    def _process_ndvi_data(
        ndvi_timeseries: list = None,
        ndvi_raster_data: Dict[str, Any] = None,
    ) -> Tuple[Dict[str, Any], List[str]]:
        """Return (data, fabricated_keys).

        `data` always has ndvi/rvi/rsm keys. Each key starts as a fabricated
        pseudo-satellite default and gets overwritten when a real measurement
        is available. Keys still using the default are returned in
        `fabricated_keys` so the report can flag them.
        """
        data: Dict[str, Any] = {
            "ndvi": pseudo_satellite.NDVI,
            "rvi": pseudo_satellite.RVI,
            "rsm": pseudo_satellite.RSM,
        }
        fabricated = {"ndvi", "rvi", "rsm"}

        if ndvi_timeseries:
            latest = ndvi_timeseries[-1]
            ts_ndvi = latest.get("ndvi")
            if ts_ndvi is not None:
                data["ndvi"] = ts_ndvi
                # RVI is typically 5–10% higher than NDVI
                data["rvi"] = min(1.0, ts_ndvi * 1.08)
                fabricated.discard("ndvi")
                fabricated.discard("rvi")

        if ndvi_raster_data:
            raster_ndvi = ndvi_raster_data.get("ndvi_mean")
            if raster_ndvi is not None:
                data["ndvi"] = raster_ndvi
                fabricated.discard("ndvi")
            if "parcel_confidence" in ndvi_raster_data:
                data["parcel_confidence"] = ndvi_raster_data["parcel_confidence"]

        return data, sorted(fabricated)

    @staticmethod
    def _generate_summary(report: Dict[str, Any]) -> Dict[str, Any]:
        summary: Dict[str, Any] = {
            "key_findings": [],
            "urgent_actions": [],
            "recommendations": [],
        }

        components = report.get("components", {})

        irrig = components.get("irrigation_schedule", {})
        if irrig:
            total_water = irrig.get("total_water_mm", 0)
            summary["key_findings"].append(
                f"Irrigation Requirement: {total_water} mm over {irrig.get('irrigation_days', 4)} days"
            )
            summary["recommendations"].append(
                f"Implement alternate-day drip irrigation at {irrig.get('best_time', '05:00-08:00')} for optimal efficiency"
            )

        soil = components.get("soil_management", {})
        if soil:
            soc_status = soil.get("organic_carbon_status", "")
            if "low" in soc_status.lower() or "critical" in soc_status.lower():
                summary["urgent_actions"].append(
                    "Soil organic carbon critically low - implement amendment program immediately"
                )
            summary["key_findings"].append(
                f"Soil pH: {soil.get('ph', 'N/A')}, Salinity: {soil.get('salinity', 'N/A')}"
            )

        yield_proj = components.get("growth_yield", {})
        if yield_proj:
            yield_per_acre = yield_proj.get("yield_per_acre_kg", 0)
            loss_percent = yield_proj.get("potential_loss_percent", 0)
            summary["key_findings"].append(
                f"Projected Yield: {yield_per_acre} kg/acre ({loss_percent:.1f}% below potential)"
            )
            limiting = yield_proj.get("limiting_factors", [])
            if limiting:
                summary["urgent_actions"].append(
                    f"Address limiting factors: {', '.join([f['factor'] for f in limiting])}"
                )

        pest = components.get("pest_disease_weed", {})
        if pest:
            high_risk = [
                x["name"] for x in pest.get("pests_diseases", [])
                if x.get("risk_level") == "high"
            ]
            if high_risk:
                summary["urgent_actions"].append(
                    f"High-risk pests/diseases detected: {', '.join(high_risk)} - Monitor closely"
                )
            summary["key_findings"].append(
                f"Pest pressure: {pest.get('summary', {}).get('high_risk_count', 0)} high-risk, "
                f"{pest.get('summary', {}).get('moderate_risk_count', 0)} moderate-risk threats"
            )

        fert = components.get("fertilizer_management", {})
        if fert:
            nutrients = fert.get("nutrient_requirements", {})
            moderate_nutrients = [
                k for k, v in nutrients.items() if v.get("status") == "moderate"
            ]
            if moderate_nutrients:
                summary["key_findings"].append(
                    f"Moderate nutrient deficiencies in: {', '.join(moderate_nutrients)}"
                )

        if not summary["urgent_actions"]:
            summary["urgent_actions"].append("Continue monitoring; current conditions are favorable")

        return summary


def generate_agricultural_report_from_aoi(
    lat: float, lon: float,
    area_acres: float = pseudo_satellite.DEFAULT_AREA_ACRES,
    crop_name: str = pseudo_satellite.DEFAULT_CROP_NAME,
    sowing_date: str = None,
    ndvi_timeseries: list = None,
    location_name: str = "",
) -> Dict[str, Any]:
    """Convenience entrypoint for generating a full advisory report."""
    return AgriculturalReportGenerator.generate_report(
        lat, lon, area_acres, crop_name, sowing_date,
        ndvi_timeseries, location_name=location_name,
    )
