from jeevn.ingestion.sentinel import ingest
from jeevn.remote_sensing.analysis.confidence import compute_raster

geojson = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [73.865536, 29.925147],
                        [73.865268, 29.924394],
                        [73.865976, 29.924449],
                        [73.865536, 29.925147]
                    ]
                ]
            }
        }
    ]
}

start_date = "2026-05-01"
end_date = "2026-05-12"

print("--- Testing Ingest ---")
ingest_result = ingest(geojson, start_date=start_date, end_date=end_date, aoi_id="network-test")
print(f"Success: {ingest_result.get('success', False)}")
print(f"Products Found: {ingest_result.get('products_found')}")
print(f"Metadata Path: {ingest_result.get('metadata_path')}")

print("\n--- Testing Raster Computation ---")
if ingest_result.get("metadata_path"):
    raster_result = compute_raster(ingest_result["metadata_path"])
    print(f"NDVI Raster Path: {raster_result.get('ndvi_raster')}")
    print(f"NDWI Raster Path: {raster_result.get('ndwi_raster')}")
    print(f"Raster Quality: {raster_result.get('raster_quality')}")
