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
    """Test yield proxy estimation.

    `yield_proxy()` returns a dict with the keys `estimated_yield_t_ha`
    (units-explicit), `confidence`, and `peak_ndvi`. The output is the
    estimated yield in *tonnes per hectare*, clipped to a realistic
    0.5–12.0 range.
    """
    result = detections.yield_proxy(cumulative_ndvi=3.0)

    # Contract: dict with these three keys
    assert "estimated_yield_t_ha" in result
    assert "confidence" in result
    assert "peak_ndvi" in result

    # Yield is positive and within the function's clipped range
    assert 0.5 <= result["estimated_yield_t_ha"] <= 12.0
    # Confidence is also clipped to [0.15, 0.95]
    assert 0.15 <= result["confidence"] <= 0.95


def test_weeds_guidance():
    """Test weeds-guidance dict + branching narrative.

    `weeds_guidance()` returns a dict with `weed_pressure_score`,
    `entropy_value`, and `guidance` (a human-readable sentence). The
    branch the sentence falls into is driven by `texture_entropy`:
      - low entropy  → "Uniform canopy structure"
      - mid entropy  → "Moderate variance"
      - high entropy → "Significant structural variance"
    NDVI only dampens borderline-low pressure when ndvi > 0.75.
    """
    # Low entropy (canopy is uniform) → low-pressure branch
    low = detections.weeds_guidance(ndvi=0.5, texture_entropy=0.5)
    assert "Uniform canopy structure" in low["guidance"]
    assert low["weed_pressure_score"] < 0.3

    # Mid entropy → moderate branch
    mid = detections.weeds_guidance(ndvi=0.5, texture_entropy=2.0)
    assert "Moderate variance" in mid["guidance"]
    assert 0.3 < mid["weed_pressure_score"] < 0.6

    # High entropy → significant-pressure branch
    high = detections.weeds_guidance(ndvi=0.5, texture_entropy=3.0)
    assert "Significant structural variance" in high["guidance"]
    assert high["weed_pressure_score"] > 0.6

    # Ordering: more entropy → more weed pressure
    assert low["weed_pressure_score"] < mid["weed_pressure_score"] < high["weed_pressure_score"]
