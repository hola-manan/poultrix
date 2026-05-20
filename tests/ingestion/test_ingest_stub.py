"""
Tests for ingest stub functionality
"""
import pytest
import json
from pathlib import Path
from jeevn.ingestion import runner as run_ingest

def test_stub_ingest_creates_metadata():
    """Test that stub ingest creates a valid metadata JSON file"""
    
    aoi_geojson = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]
            }
        }]
    }
    
    result = run_ingest.stub_ingest(
        aoi_geojson=aoi_geojson,
        start_date="2024-01-01",
        end_date="2024-12-31",
        aoi_id="test-aoi-123"
    )
    
    assert result["success"] is True
    assert result["metadata_path"] is not None
    
    # Verify file exists and is valid JSON
    metadata_path = Path(result["metadata_path"])
    assert metadata_path.exists()
    
    with open(metadata_path, 'r') as f:
        metadata = json.load(f)
    
    assert "aoi" in metadata
    assert "start_date" in metadata
    assert "end_date" in metadata
    assert "fetched_at" in metadata
    assert "tiles" in metadata
    assert len(metadata["tiles"]) > 0

def test_stub_ingest_metadata_structure():
    """Test that metadata JSON has the expected structure"""
    
    aoi_geojson = {"type": "FeatureCollection", "features": []}
    
    result = run_ingest.stub_ingest(
        aoi_geojson=aoi_geojson,
        aoi_id="test-123"
    )
    
    with open(result["metadata_path"], 'r') as f:
        metadata = json.load(f)
    
    # Verify structure
    assert isinstance(metadata["aoi"], dict)
    assert isinstance(metadata["tiles"], list)
    
    # Verify tile structure
    for tile in metadata["tiles"]:
        assert "tile_id" in tile
        assert "date" in tile
        assert "cloud_percentage" in tile
        assert 0 <= tile["cloud_percentage"] <= 100
