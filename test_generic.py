import os
import sys

sys.path.insert(0, os.path.abspath("src"))

from jeevn.domain.crop.phenology import CropPhenologyDatabase
from jeevn.application.advisory_service import AgriculturalReportGenerator
import datetime

# Mock ndvi data
ndvi_timeseries = [
    {"date": (datetime.datetime.now() - datetime.timedelta(days=7)).strftime("%Y-%m-%d"), "ndvi_mean": 0.5, "ndwi_mean": 0.1, "ndre_mean": 0.3},
    {"date": datetime.datetime.now().strftime("%Y-%m-%d"), "ndvi_mean": 0.6, "ndwi_mean": 0.2, "ndre_mean": 0.4}
]

print("Generating report for maize...")
report = AgriculturalReportGenerator.generate_report(
    lat=20.0,
    lon=73.0,
    area_acres=2.0,
    crop_name="maize",
    sowing_date=(datetime.datetime.now() - datetime.timedelta(days=30)).strftime("%Y-%m-%d"),
    ndvi_timeseries=ndvi_timeseries
)

print("\nReport components:")
print(list(report["components"].keys()))

assert "fertilizer_management" not in report["components"], "Fertilizer management should be omitted for generic crops"

print("\nSuccess! Generic crop pipeline works.")
