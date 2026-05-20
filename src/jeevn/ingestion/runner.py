"""
Stub ingest implementation — writes demo metadata JSON.
Used as fallback when real Sentinel-2 ingestion fails.
"""

import json
from datetime import datetime
from pathlib import Path


def stub_ingest(aoi_geojson, start_date=None, end_date=None, aoi_id=None):
    """Stub ingest path — writes demo metadata JSON."""
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)

    metadata = {
        "aoi": aoi_geojson,
        "start_date": start_date,
        "end_date": end_date,
        "fetched_at": datetime.utcnow().isoformat(),
        "tiles": [
            {
                "tile_id": "31TCG",
                "date": "2024-03-15",
                "cloud_percentage": 12.5
            },
            {
                "tile_id": "31TCG",
                "date": "2024-04-14",
                "cloud_percentage": 5.2
            }
        ]
    }

    metadata_filename = f"ingest_metadata_{aoi_id or 'demo'}.json"
    metadata_path = data_dir / metadata_filename

    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)

    return {
        "metadata_path": str(metadata_path),
        "success": True
    }
