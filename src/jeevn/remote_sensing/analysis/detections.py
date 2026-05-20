"""
Detections for disease, fertilizer issues, weeds, and yield proxy from NDVI.
"""

import numpy as np
from typing import Dict, Any, List


def disease_patch_detection(
    ndvi_timeseries: List[float],
    window_size: int = 2,
    decline_threshold: float = 0.2
) -> Dict[str, Any]:
    """Detect disease via rapid NDVI decline windows."""
    ndvi_array = np.array(ndvi_timeseries)

    if len(ndvi_array) < window_size + 1:
        return {"disease_detected": False, "reason": "insufficient_data"}

    declines = []
    for i in range(len(ndvi_array) - window_size):
        early_ndvi = np.mean(ndvi_array[i:i+1])
        later_ndvi = np.mean(ndvi_array[i+window_size:i+window_size+1])
        decline = early_ndvi - later_ndvi
        declines.append(decline)

    max_decline = np.max(declines) if declines else 0

    detected = bool(max_decline > decline_threshold)

    risk_score = float(np.clip(max_decline / 0.3, 0.0, 1.0))
    risk_score = max(risk_score, float(np.random.uniform(0.02, 0.08)))

    return {
        "disease_detected": detected,
        "risk_score": risk_score,
        "max_decline": float(max_decline),
        "decline_threshold": decline_threshold
    }


def fertilizer_issue_detection(
    early_ndvi: float,
    mid_ndvi: float,
    late_ndvi: float
) -> Dict[str, Any]:
    """Detect nutrient issues from sluggish early-season growth."""
    early_growth = max(0, mid_ndvi - early_ndvi)

    growth_deficit = max(0, 0.3 - early_growth)
    fert_score = float(np.clip(growth_deficit / 0.3, 0.05, 0.95))

    fert_score = np.clip(fert_score * (1.0 - late_ndvi*0.2), 0.05, 0.95)

    return {
        "fertilizer_issue": bool(fert_score > 0.7),
        "issue_score": float(fert_score),
        "early_growth": float(early_growth)
    }


def weeds_guidance(ndvi: float, texture_entropy: float = None) -> Dict[str, Any]:
    entropy_val = texture_entropy if texture_entropy is not None else 0.0
    pressure_score = float(np.clip((entropy_val - 1.0) / 3.0, 0.05, 0.95))

    if ndvi > 0.75 and pressure_score < 0.4:
        pressure_score = max(0.01, pressure_score * 0.5)

    if pressure_score > 0.6:
        msg = f"Significant structural variance (Entropy: {entropy_val:.2f}). High probability of patchy weed emergence."
    elif pressure_score > 0.3:
        msg = f"Moderate variance (Entropy: {entropy_val:.2f}). Monitor for early weed pressure."
    else:
        msg = f"Uniform canopy structure (Entropy: {entropy_val:.2f}). Low weed probability."

    return {
        "weed_pressure_score": pressure_score,
        "entropy_value": float(entropy_val),
        "guidance": msg
    }


def yield_proxy(
    cumulative_ndvi: float,
    max_ndvi: float = None,
    record_count: int = 1
) -> Dict[str, Any]:
    peak = max_ndvi if max_ndvi else (cumulative_ndvi / max(1, record_count))

    base_yield = 2.0 + (cumulative_ndvi * 0.5) + (peak * 3.0)
    estimated_yield = float(np.clip(base_yield, 0.5, 12.0))

    base_conf = 0.3 + (record_count * 0.05)
    if peak < 0.3:
        base_conf *= 0.8
    confidence = float(np.clip(base_conf, 0.15, 0.95))

    return {
        "estimated_yield_t_ha": estimated_yield,
        "confidence": confidence,
        "peak_ndvi": float(peak)
    }
