"""
Tests for NDVI aggregation and raster confidence
"""
import pytest
import json
import tempfile
from pathlib import Path
from jeevn.remote_sensing.ndvi import aggregate as aggregate_ndvi
from jeevn.remote_sensing.analysis import confidence as raster_confidence

def test_ndvi_aggregation_from_stub_metadata():
    """Test NDVI aggregation from stub metadata"""
    
    # Create temporary metadata file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        metadata = {
            "aoi": {"type": "FeatureCollection"},
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "fetched_at": "2024-01-01T00:00:00",
            "tiles": [
                {"tile_id": "31TCG", "date": "2024-03-15", "cloud_percentage": 12.5},
                {"tile_id": "31TCG", "date": "2024-04-14", "cloud_percentage": 5.2}
            ]
        }
        json.dump(metadata, f)
        metadata_path = f.name
    
    try:
        result = aggregate_ndvi.aggregate_ndvi(metadata_path)
        
        assert result["ndvi_csv"] is not None
        assert Path(result["ndvi_csv"]).exists()
        assert result["record_count"] == 2  # 2 tiles
    
    finally:
        Path(metadata_path).unlink()

def test_parcel_confidence_scoring():
    """Test parcel confidence calculation"""
    
    # High confidence NDVI raster
    ndvi_good = 0.6 + 0.05 * (0.99 - 0.98)  # High mean, low std
    confidence_good = raster_confidence.compute_parcel_confidence(
        np.random.normal(0.6, 0.02, (100, 100))
    )
    
    # Low confidence NDVI raster
    confidence_low = raster_confidence.compute_parcel_confidence(
        np.random.normal(0.2, 0.2, (100, 100))
    )
    
    assert confidence_good["confidence_score"] > confidence_low["confidence_score"]

def test_parcel_confidence_with_nan():
    """Test parcel confidence with NaN values (clouds)"""
    
    ndvi_raster = np.random.uniform(0.3, 0.8, (100, 100))
    ndvi_raster[10:20, 10:20] = np.nan  # Cloud area
    
    confidence = raster_confidence.compute_parcel_confidence(ndvi_raster)
    
    assert confidence["valid_pixel_pct"] < 100.0
    assert confidence["confidence_score"] > 0
    assert confidence["mean_ndvi"] is not None

import numpy as np

