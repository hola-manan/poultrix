"""
Tests for SAR helpers
"""
import pytest
import numpy as np
from jeevn.remote_sensing.analysis import sar

def test_sar_db_to_linear_conversion():
    """Test SAR dB to linear conversion"""
    
    sar_db = np.array([-10.0, -5.0, 0.0, 5.0, 10.0])
    sar_linear = sar.sar_db_to_linear(sar_db)
    
    # All values should be positive
    assert np.all(sar_linear > 0)
    
    # Reversibility check
    sar_db_back = sar.sar_linear_to_db(sar_linear)
    assert np.allclose(sar_db, sar_db_back, atol=1e-10)

def test_sar_vh_vv_difference():
    """Test VH-VV difference calculation"""
    
    vh = np.array([-15.0, -12.0, -10.0])
    vv = np.array([-5.0, -6.0, -8.0])
    
    diff = sar.sar_vh_vv_difference(vh, vv)
    
    # VH is typically lower than VV (more negative)
    assert np.all(diff < 0)
    
    # Difference should be consistent
    expected_diff = vh - vv
    assert np.allclose(diff, expected_diff)

def test_sar_moisture_index():
    """Test SAR-based moisture index"""
    
    # Synthetic 3-observation SAR stack
    sar_stack = np.random.uniform(0, 100, (3, 10, 10))
    
    moisture_index = sar.sar_moisture_index(sar_stack)
    
    # Should be normalized between 0 and 1
    assert np.all(moisture_index >= 0)
    assert np.all(moisture_index <= 1)
    
    # Should have same spatial dimensions as input
    assert moisture_index.shape == (10, 10)

def test_sar_stack_loading_dimension():
    """Test SAR stack dimensions"""
    
    # Create synthetic SAR stack (would normally load from files)
    sar_stack = np.random.uniform(0, 100, (5, 50, 50))
    
    # Stack should be (time, height, width)
    assert sar_stack.shape[0] == 5  # 5 time observations
    assert sar_stack.shape[1] == 50  # 50x50 spatial grid
    assert sar_stack.shape[2] == 50
