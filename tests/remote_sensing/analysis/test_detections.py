"""
Tests for agricultural detections (disease, fertilizer, etc)
"""
import pytest
from jeevn.remote_sensing.analysis import detections

def test_disease_patch_detection():
    """Test disease detection from NDVI decline"""
    
    # Healthy series
    healthy = [0.7, 0.72, 0.75, 0.73, 0.70]
    result = detections.disease_patch_detection(healthy)
    assert result["disease_detected"] is False
    
    # Disease series with rapid decline
    disease = [0.7, 0.65, 0.3, 0.25, 0.2]
    result = detections.disease_patch_detection(disease, decline_threshold=0.2)
    assert result["disease_detected"] is True
    assert result["max_decline"] > 0.2

def test_fertilizer_issue_detection():
    """Test fertilizer issue detection"""
    
    # Weak early growth (fertilizer issue)
    early, mid, late = 0.15, 0.18, 0.65
    result = detections.fertilizer_issue_detection(early, mid, late)
    assert result["fertilizer_issue"] is True
    
    # Good early growth (no issue)
    early, mid, late = 0.4, 0.6, 0.75
    result = detections.fertilizer_issue_detection(early, mid, late)
    assert result["fertilizer_issue"] is False

def test_yield_proxy():
    """Test yield proxy estimation"""
    
    result = detections.yield_proxy(cumulative_ndvi=3.0)
    
    assert "estimated_yield" in result
    assert "confidence" in result
    assert 0 <= result["confidence"] <= 1
    assert result["estimated_yield"] > 0

def test_weeds_guidance():
    """Test weeds guidance placeholder"""
    
    # Low NDVI guidance
    msg = detections.weeds_guidance(ndvi=0.25)
    assert "Low NDVI" in msg
    
    # No obvious indicators
    msg = detections.weeds_guidance(ndvi=0.7)
    assert "No obvious" in msg
