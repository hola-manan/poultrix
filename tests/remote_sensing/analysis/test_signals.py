"""
Tests for signal detection and vegetation indices
"""
import pytest
import numpy as np
from jeevn.remote_sensing.analysis import signals

def test_ndvi_computation():
    """Test NDVI calculation formula"""
    
    red = np.array([100.0, 150.0, 50.0])
    nir = np.array([200.0, 300.0, 100.0])
    
    ndvi = signals.ndvi(red, nir)
    
    # Manual calculation for first value: (200-100)/(200+100) = 100/300 = 0.333
    assert np.isclose(ndvi[0], 1/3, atol=0.01)
    
    # All NDVI values should be between -1 and 1
    assert np.all(ndvi >= -1) and np.all(ndvi <= 1)

def test_z_score_anomaly_detection():
    """Test z-score anomaly detection"""
    
    # Normal distribution + one anomaly
    values = np.array([10.0, 10.5, 9.8, 10.2, 100.0])  # Last is anomaly
    
    anomalies = signals.z_score_anomaly(values, threshold=2.0)
    
    # Should detect the outlier
    assert anomalies[-1] is True
    assert np.sum(anomalies) >= 1

def test_irrigation_stress_flag():
    """Test irrigation stress detection"""
    
    # Low NDVI = stress
    assert signals.irrigation_stress_flag(ndvi=0.2) is True
    
    # Normal NDVI + high temp = stress
    assert signals.irrigation_stress_flag(ndvi=0.6, lst=40) is True
    
    # Normal NDVI + normal temp = no stress
    assert signals.irrigation_stress_flag(ndvi=0.6, lst=25) is False

def test_water_stress_score():
    """Test water stress scoring"""
    
    # High vegetation + high water = low stress
    score_good = signals.water_stress_score(ndvi=0.7, ndwi=0.5)
    
    # Low vegetation + low water = high stress
    score_bad = signals.water_stress_score(ndvi=0.2, ndwi=0.1)
    
    assert score_bad > score_good
    assert 0 <= score_good <= 1
    assert 0 <= score_bad <= 1

def test_parcel_confidence_score():
    """Test parcel confidence calculation"""
    
    # High confidence case
    conf_high = signals.parcel_confidence_score(
        mean_ndvi=0.6,
        ndvi_std=0.05,
        valid_pixel_pct=95.0
    )
    
    # Low confidence case
    conf_low = signals.parcel_confidence_score(
        mean_ndvi=0.2,
        ndvi_std=0.3,
        valid_pixel_pct=60.0
    )
    
    assert conf_high > conf_low
    assert 0 <= conf_high <= 1
    assert 0 <= conf_low <= 1

def test_ndvi_anomaly_detection():
    """Test NDVI time-series anomaly detection"""
    
    # Normal series
    normal_series = [0.5, 0.55, 0.6, 0.58, 0.6]
    result = signals.ndvi_anomaly(normal_series)
    assert result["anomaly"] is False
    
    # Low NDVI series
    low_series = [0.2, 0.15, 0.1, 0.12, 0.1]
    result = signals.ndvi_anomaly(low_series)
    assert result["anomaly"] is True
    assert result["reason"] == "low_ndvi"
    
    # Rapid decline
    decline_series = [0.7, 0.65, 0.3, 0.25]
    result = signals.ndvi_anomaly(decline_series, threshold=0.2)
    assert result["anomaly"] is True

def test_persistent_stress_detection():
    """Test persistent stress detection over time"""
    
    # Consistently low NDVI
    low_series = [0.3, 0.35, 0.32, 0.3, 0.28, 0.32]
    result = signals.persistent_stress_detection(low_series)
    assert result["persistent_stress"] is True
    
    # High NDVI
    high_series = [0.6, 0.65, 0.62, 0.6, 0.68, 0.62]
    result = signals.persistent_stress_detection(high_series)
    assert result["persistent_stress"] is False
