"""
Test script to validate agricultural advisory report generation
"""

import sys
import json
from datetime import datetime, timedelta
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))
sys.path.insert(0, str(_root / "src"))

from jeevn.application.advisory_service import generate_agricultural_report_from_aoi


def test_agricultural_report():
    """Test agricultural report generation with Ganganagar location (from PDF)"""
    
    print("=" * 80)
    print("AGRICULTURAL ADVISORY REPORT GENERATION TEST")
    print("=" * 80)
    print()
    
    # Use Ganganagar, Rajasthan coordinates (from PDF report)
    lat = 29.9
    lon = 73.9
    area_acres = 0.421
    crop_name = "apple"
    
    # Sowing date - 4 months before may (Feb 1)
    sowing_date = "2026-02-01"
    location_name = "Ganganagar, Rajasthan"
    
    print(f"Generating agricultural report for:")
    print(f"  Location: {location_name} ({lat}, {lon})")
    print(f"  Crop: {crop_name}")
    print(f"  Area: {area_acres} acres")
    print(f"  Sowing Date: {sowing_date}")
    print()
    
    # Generate sample NDVI time series (30 days)
    ndvi_timeseries = []
    base_date = datetime.now() - timedelta(days=30)
    base_ndvi = 0.3
    
    for i in range(30):
        date = base_date + timedelta(days=i)
        # Simulate NDVI growth over 30 days
        ndvi = base_ndvi + (i / 30.0) * 0.35  # Growth from 0.3 to ~0.65
        ndvi_timeseries.append({
            "date": date.strftime("%Y-%m-%d"),
            "ndvi": round(ndvi, 3)
        })
    
    try:
        print("Fetching agricultural data and calculating advisory...")
        print()
        
        report = generate_agricultural_report_from_aoi(
            lat=lat,
            lon=lon,
            area_acres=area_acres,
            crop_name=crop_name,
            sowing_date=sowing_date,
            ndvi_timeseries=ndvi_timeseries,
            location_name=location_name
        )
        
        print("✓ Report generation successful!")
        print()
        print("-" * 80)
        print("REPORT SUMMARY")
        print("-" * 80)
        print()
        
        # Display key sections
        print("AOI INFORMATION:")
        aoi_info = report.get("aoi_info", {})
        print(f"  Location: {aoi_info.get('location')}")
        print(f"  Area: {aoi_info.get('area_acres')} acres")
        print(f"  Crop: {aoi_info.get('crop')}")
        print(f"  Satellite Visit: {aoi_info.get('satellite_visit')}")
        print()
        
        print("IRRIGATION SCHEDULE:")
        irrig = report.get("components", {}).get("irrigation_schedule", {})
        print(f"  ET0: {irrig.get('et0_mm_per_day')} mm/day")
        print(f"  Crop Coefficient (Kc): {irrig.get('kc')}")
        print(f"  Crop ET: {irrig.get('etc_mm_per_day')} mm/day")
        print(f"  Net Irrigation Required: {irrig.get('net_irrigation_mm')} mm")
        print(f"  Total Water (7 days): {irrig.get('total_water_mm')} mm")
        print(f"  Irrigation Days: {irrig.get('irrigation_days')}")
        print(f"  Best Time: {irrig.get('best_time')}")
        print()
        
        print("SOIL MANAGEMENT:")
        soil = report.get("components", {}).get("soil_management", {})
        print(f"  pH: {soil.get('ph')}")
        print(f"  Salinity: {soil.get('salinity')}")
        print(f"  Organic Carbon: {soil.get('organic_carbon_status')}")
        print(f"  Soil Moisture: {soil.get('soil_moisture_current')}")
        print()
        
        print("GROWTH & YIELD:")
        yield_proj = report.get("components", {}).get("growth_yield", {})
        print(f"  Current Growth Stage: {yield_proj.get('current_growth_stage')}")
        print(f"  Yield Potential: {yield_proj.get('yield_potential_kg_per_acre')} kg/acre")
        print(f"  Projected Yield: {yield_proj.get('yield_per_acre_kg')} kg/acre")
        print(f"  Total Yield: {yield_proj.get('total_yield_kg')} kg")
        print(f"  Potential Loss: {yield_proj.get('potential_loss_percent')}%")
        print(f"  Harvest Status: {yield_proj.get('harvest_status')}")
        print()
        
        print("PEST, DISEASE & WEED MANAGEMENT:")
        pest = report.get("components", {}).get("pest_disease_weed", {})
        summary = pest.get("summary", {})
        print(f"  High Risk Threats: {summary.get('high_risk_count')}")
        print(f"  Moderate Risk Threats: {summary.get('moderate_risk_count')}")
        print(f"  Low Risk Threats: {summary.get('low_risk_count')}")
        
        # Show high-risk threats
        high_risk_threats = [
            x["name"] for x in pest.get("pests_diseases", [])
            if x.get("risk_level") == "high"
        ]
        high_risk_weeds = [
            x["name"] for x in pest.get("weeds", [])
            if x.get("risk_level") == "high"
        ]
        
        if high_risk_threats:
            print(f"  High-Risk Pests/Diseases: {', '.join(high_risk_threats)}")
        if high_risk_weeds:
            print(f"  High-Risk Weeds: {', '.join(high_risk_weeds)}")
        print()
        
        print("FERTILIZER MANAGEMENT:")
        fert = report.get("components", {}).get("fertilizer_management", {})
        nutrients = fert.get("nutrient_requirements", {})
        print("  Nutrient Status:")
        for nutrient, data in nutrients.items():
            current = data.get("current_kg_per_acre", 0)
            target = data.get("target_kg_per_acre", "N/A")
            gap = data.get("gap_kg_per_acre", 0)
            status = data.get("status", "unknown")
            print(f"    {nutrient}: {current} kg/ac (target: {target}, gap: {gap}, status: {status})")
        print()
        
        print("SUMMARY & KEY FINDINGS:")
        summary = report.get("summary", {})
        if summary.get("key_findings"):
            print("  Key Findings:")
            for finding in summary.get("key_findings", []):
                print(f"    - {finding}")
        print()
        
        if summary.get("urgent_actions"):
            print("  Urgent Actions:")
            for action in summary.get("urgent_actions", []):
                print(f"    - {action}")
        print()
        
        if summary.get("recommendations"):
            print("  Recommendations:")
            for rec in summary.get("recommendations", [])[:3]:  # Show first 3
                print(f"    - {rec}")
        
        print()
        print("=" * 80)
        print("✓ Report generation test PASSED")
        print("=" * 80)
        
        # Save full report to JSON
        report_file = "/tmp/agricultural_report_test.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"Full report saved to: {report_file}")
        
        return True
        
    except Exception as e:
        print(f"✗ Error during report generation:")
        print(f"  {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_agricultural_report()
    sys.exit(0 if success else 1)
