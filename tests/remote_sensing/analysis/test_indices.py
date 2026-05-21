"""
Tests for vegetation indices
"""
import pytest
import numpy as np
from jeevn.remote_sensing.analysis import signals

def test_ndwi_computation():
    """Test NDWI calculation"""
    
    green = np.array([100.0, 150.0, 200.0])
    swir = np.array([50.0, 75.0, 100.0])
    
    ndwi = signals.ndwi(green, swir)
    
    # NDWI = (green - swir) / (green + swir)
    # Should be positive when green > swir
    assert np.all(ndwi >= 0)
    assert np.all(ndwi <= 1)

def test_evi_computation():
    """Test Enhanced Vegetation Index"""
    
    red = np.array([100.0])
    nir = np.array([200.0])
    blue = np.array([50.0])
    
    evi = signals.evi(red, nir, blue)
    
    # EVI should be a valid value
    assert -1 <= evi[0] <= 1

def test_savi_computation():
    """Test Soil-Adjusted Vegetation Index"""
    
    red = np.array([100.0, 150.0])
    nir = np.array([200.0, 300.0])
    
    savi = signals.savi(red, nir, L=0.5)
    
    # SAVI should be between -1 and 1
    assert np.all(savi >= -1) and np.all(savi <= 1)

def test_gci_computation():
    """Test Green Chlorophyll Index"""
    
    nir = np.array([200.0, 300.0])
    green = np.array([100.0, 150.0])
    
    gci = signals.gci(nir, green)
    
    # GCI = (NIR / Green) - 1
    assert gci[0] > 0  # NIR > Green in vegetation
    assert gci[1] > 0

def test_msi_computation():
    """Test Moisture Stress Index"""
    
    nir = np.array([200.0, 300.0])
    swir = np.array([100.0, 200.0])
    
    msi = signals.msi(nir, swir)
    
    # MSI = SWIR / NIR
    # Higher MSI (higher SWIR) suggests water stress
    assert msi[0] > 0
    assert msi[0] < msi[1]  # Second value has higher stress

def test_nutrient_stress_score():
    """Test nutrient stress detection.

    `nutrient_stress_score()` returns `1 - (ratio - 0.2) / 0.6`, clipped
    to [0.05, 0.95], where `ratio = red_edge_ndvi / ndvi`. A healthy plant
    has ratio close to 0.8 (re tracks ndvi → low stress, score ≈ 0.05).
    A stressed plant has a much smaller ratio (re lags far behind ndvi →
    high stress, score approaches 0.95).

    The previous version of this test used inputs whose ratios both
    landed at/above 0.8, so both scores clamped to 0.05 and the
    `<` assertion failed. Inputs below pick ratios deep in the
    unclamped range so the relative ordering is meaningful.
    """
    # Healthy: red-edge tracks NDVI closely (ratio ≈ 0.64) → low stress
    score_healthy = signals.nutrient_stress_score(ndvi=0.7, red_edge_ndvi=0.45)

    # Stressed: red-edge lags far behind NDVI (ratio ≈ 0.36) → high stress
    score_stressed = signals.nutrient_stress_score(ndvi=0.7, red_edge_ndvi=0.25)

    assert score_healthy < score_stressed
    # Both inside the unclamped band [0.05, 0.95]
    assert 0.05 < score_healthy < score_stressed < 0.95
