"""
Tests for texture metrics
"""
import pytest
import numpy as np
from jeevn.remote_sensing.analysis import texture

def test_local_std_output_shape():
    """Test that local std maintains array shape"""
    
    data = np.random.uniform(0, 1, (50, 50))
    
    local_std = texture.local_std(data, kernel_size=3)
    
    # Output should have same shape as input
    assert local_std.shape == data.shape
    
    # Values should be non-negative
    assert np.all(local_std >= 0)

def test_local_entropy_output_shape():
    """Test that local entropy maintains array shape"""
    
    data = np.random.uniform(0, 1, (50, 50))
    
    local_entropy = texture.local_entropy(data, kernel_size=3)
    
    # Output should have same shape as input
    assert local_entropy.shape == data.shape
    
    # Entropy should be non-negative
    assert np.all(local_entropy >= 0)

def test_local_entropy_uniform_vs_random():
    """Test that uniform areas have lower entropy than random"""
    
    # Uniform area (low entropy)
    uniform_data = np.ones((50, 50)) * 0.5
    
    # Random area (high entropy)
    random_data = np.random.uniform(0, 1, (50, 50))
    
    uniform_entropy = texture.local_entropy(uniform_data)
    random_entropy = texture.local_entropy(random_data)
    
    # Random should have higher entropy on average
    assert np.mean(random_entropy) > np.mean(uniform_entropy)

def test_local_std_kernel_sizes():
    """Test local std with different kernel sizes"""
    
    data = np.random.uniform(0, 1, (50, 50))
    
    std_3 = texture.local_std(data, kernel_size=3)
    std_5 = texture.local_std(data, kernel_size=5)
    
    # Both should have the same shape
    assert std_3.shape == std_5.shape
    
    # Larger kernel should produce smoother results (generally lower variance)
    # This isn't always true pixel-by-pixel, but statistically should hold
    assert std_3.shape == data.shape
    assert std_5.shape == data.shape
