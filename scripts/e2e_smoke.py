"""
End-to-end smoke test for Jeevn API
"""
import requests
import json
import time
import os
from pathlib import Path
from typing import Dict, Any

def run_smoke_test():
    """Run end-to-end smoke test"""
    
    api_url = os.environ.get("API_URL", "http://localhost:8000")
    
    print(f"🧪 Jeevn E2E Smoke Test")
    print(f"API URL: {api_url}")
    print("-" * 50)
    
    # Test 1: Health check
    print("1️⃣  Health check...")
    try:
        response = requests.get(f"{api_url}/health", timeout=5)
        assert response.status_code == 200, f"Health check failed: {response.status_code}"
        print("   ✅ Health check passed")
    except Exception as e:
        print(f"   ❌ Health check failed: {e}")
        return False
    
    # Test 2: Create AOI
    print("2️⃣  Creating AOI...")
    try:
        payload = {
            "name": "Smoke Test AOI",
            "geojson": {
                "type": "FeatureCollection",
                "features": [{
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[
                            [0.0, 0.0],
                            [1.0, 0.0],
                            [1.0, 1.0],
                            [0.0, 1.0],
                            [0.0, 0.0]
                        ]]
                    }
                }]
            },
            "start_date": "2024-01-01",
            "end_date": "2024-12-31"
        }
        
        response = requests.post(
            f"{api_url}/aoi",
            json=payload,
            timeout=30
        )
        
        assert response.status_code == 200, f"AOI creation failed: {response.status_code}"
        result = response.json()
        aoi_id = result.get("aoi_id")
        
        print(f"   ✅ AOI created: {aoi_id}")
        print(f"      - Metadata path: {result.get('metadata_path')}")
        print(f"      - NDVI CSV: {result.get('ndvi_csv')}")
        print(f"      - NDVI Raster: {result.get('ndvi_raster')}")
        
    except Exception as e:
        print(f"   ❌ AOI creation failed: {e}")
        return False
    
    # Test 3: Fetch report
    print("3️⃣  Fetching report...")
    try:
        response = requests.get(
            f"{api_url}/aoi/{aoi_id}/report",
            timeout=10
        )
        
        assert response.status_code == 200, f"Report fetch failed: {response.status_code}"
        report = response.json()
        
        print(f"   ✅ Report fetched")
        print(f"      - Status: {report.get('status')}")
        print(f"      - Metadata path: {report.get('metadata_path')}")
        
    except Exception as e:
        print(f"   ❌ Report fetch failed: {e}")
        return False
    
    # Test 4: Verify metadata file
    print("4️⃣  Verifying metadata file...")
    try:
        metadata_path = result.get("metadata_path")
        if metadata_path and Path(metadata_path).exists():
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            print(f"   ✅ Metadata file exists and is valid")
            print(f"      - AOI: {metadata.get('aoi', {}).get('type', 'N/A')}")
            print(f"      - Fetched at: {metadata.get('fetched_at', 'N/A')}")
        else:
            print(f"   ⚠️  Metadata file not found: {metadata_path}")
    
    except Exception as e:
        print(f"   ⚠️  Metadata verification failed: {e}")
    
    print("-" * 50)
    print("✅ Smoke test completed successfully!")
    
    return True

if __name__ == "__main__":
    success = run_smoke_test()
    exit(0 if success else 1)
