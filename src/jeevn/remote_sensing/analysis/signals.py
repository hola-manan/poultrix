"""
Vegetation indices and stress detection signals.
"""

import numpy as np
from typing import Dict, Any, List

# Vegetation indices ---------------------------------------------------------

def ndvi(red: np.ndarray, nir: np.ndarray) -> np.ndarray:
    """Normalized Difference Vegetation Index"""
    return (nir - red) / (nir + red + 1e-6)


def ndwi(green: np.ndarray, swir: np.ndarray) -> np.ndarray:
    """Normalized Difference Water Index"""
    return (green - swir) / (green + swir + 1e-6)


def evi(red: np.ndarray, nir: np.ndarray, blue: np.ndarray) -> np.ndarray:
    """Enhanced Vegetation Index"""
    return 2.5 * (nir - red) / (nir + 6 * red - 7.5 * blue + 1)


def savi(red: np.ndarray, nir: np.ndarray, L: float = 0.5) -> np.ndarray:
    """Soil-Adjusted Vegetation Index"""
    return ((nir - red) / (nir + red + L)) * (1 + L)


def ndre(red_edge: np.ndarray, nir: np.ndarray) -> np.ndarray:
    """Normalized Difference Red Edge (red-edge NDVI)"""
    return (nir - red_edge) / (nir + red_edge + 1e-6)


def gci(nir: np.ndarray, green: np.ndarray) -> np.ndarray:
    """Green Chlorophyll Index"""
    return (nir / green) - 1


def msi(nir: np.ndarray, swir: np.ndarray) -> np.ndarray:
    """Moisture Stress Index"""
    return swir / nir


# Anomaly detection ----------------------------------------------------------

def z_score_anomaly(values: np.ndarray, threshold: float = 2.0) -> np.ndarray:
    """Detect anomalies via z-score (with robust modified-z fallback)."""
    values = np.asarray(values, dtype=float)
    mean = np.nanmean(values)
    std = np.nanstd(values)
    if std == 0 or np.isnan(std):
        return np.zeros(values.shape, dtype=object)

    z_scores = np.abs((values - mean) / std)
    anomalies = z_scores >= threshold

    if not np.any(anomalies):
        median = np.nanmedian(values)
        mad = np.nanmedian(np.abs(values - median))
        if mad > 0 and not np.isnan(mad):
            modified_z = 0.6745 * np.abs(values - median) / mad
            anomalies = modified_z >= threshold

    return np.array([bool(flag) for flag in anomalies], dtype=object)


def ndvi_anomaly(ndvi_timeseries: List[float], threshold: float = 0.3) -> Dict[str, Any]:
    """Detect rapid declines or low values in an NDVI time series."""
    if len(ndvi_timeseries) < 2:
        return {"anomaly": False, "reason": "insufficient_data"}

    ndvi_array = np.array(ndvi_timeseries)

    mean_ndvi = np.nanmean(ndvi_array)
    if mean_ndvi < 0.3:
        return {
            "anomaly": True,
            "reason": "low_ndvi",
            "mean_ndvi": float(mean_ndvi)
        }

    diffs = np.diff(ndvi_array)
    max_decline = np.min(diffs)

    if max_decline < -threshold:
        return {
            "anomaly": True,
            "reason": "rapid_decline",
            "max_decline": float(max_decline)
        }

    return {"anomaly": False}


# Stress detection -----------------------------------------------------------

def irrigation_stress_flag(ndvi: float, lst: float = None) -> bool:
    """Flag potential irrigation stress from NDVI (and optional LST)."""
    if ndvi < 0.4:
        return True
    if lst is not None and lst > 35:
        return True
    return False


def persistent_stress_detection(
    ndvi_timeseries: List[float],
    window_size: int = 3
) -> Dict[str, Any]:
    """Detect persistent low-NDVI windows."""
    ndvi_array = np.array(ndvi_timeseries)

    if len(ndvi_array) < window_size:
        return {"persistent_stress": False}

    rolling_mean = np.convolve(ndvi_array, np.ones(window_size) / window_size, mode='valid')

    low_stress_windows = np.sum(rolling_mean < 0.4)
    stress_pct = low_stress_windows / len(rolling_mean) if len(rolling_mean) > 0 else 0

    persistent = bool(stress_pct > 0.5)

    return {
        "persistent_stress": persistent,
        "stress_window_pct": float(stress_pct),
        "low_stress_windows": int(low_stress_windows)
    }


def water_stress_score(ndvi: float, ndwi: float) -> float:
    """Combined water stress score from NDVI and NDWI."""
    ndvi_norm = max(0, ndvi)
    ndwi_norm = max(0, ndwi)

    stress = (1 - ndvi_norm) * 0.6 + (1 - ndwi_norm) * 0.4

    return float(np.clip(stress, 0, 1))


def nutrient_stress_score(ndvi: float, red_edge_ndvi: float) -> float:
    ndvi_norm = max(0.01, ndvi)
    re_norm = max(0.01, red_edge_ndvi)

    ratio = re_norm / ndvi_norm
    stress = 1.0 - ((ratio - 0.2) / 0.6)
    return float(np.clip(stress, 0.05, 0.95))


def parcel_confidence_score(
    mean_ndvi: float,
    ndvi_std: float,
    valid_pixel_pct: float
) -> float:
    """Overall parcel confidence from NDVI summary statistics."""
    ndvi_score = min(1.0, max(0.0, (mean_ndvi + 1) / 2))
    uniformity = 1.0 - min(1.0, ndvi_std)
    validity = valid_pixel_pct / 100.0

    confidence = ndvi_score * 0.4 + uniformity * 0.3 + validity * 0.3

    return float(np.clip(confidence, 0, 1))
