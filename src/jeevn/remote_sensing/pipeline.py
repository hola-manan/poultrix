"""
Remote-sensing pipeline orchestration.
Ties together NDVI aggregation, raster computation, and analysis signals.
"""

from typing import Dict, Any
import numpy as np

from .ndvi import aggregate as aggregate_ndvi_module
from .analysis import confidence as raster_confidence
from .analysis import signals, detections, texture, sar


def aggregate_ndvi(metadata_path: str) -> Dict[str, Any]:
    """Wrapper for NDVI aggregation."""
    return aggregate_ndvi_module.aggregate_ndvi(metadata_path)


def compute_raster(metadata_path: str) -> Dict[str, Any]:
    """Wrapper for raster computation and parcel confidence."""
    return raster_confidence.compute_raster(metadata_path)


def run_preproc(metadata_path: str) -> Dict[str, Any]:
    """Full preprocessing orchestration for one metadata JSON."""
    result = {
        "metadata_path": metadata_path,
        "outputs": {},
        "errors": []
    }

    try:
        ndvi_result = aggregate_ndvi(metadata_path)
        result["outputs"]["ndvi_csv"] = ndvi_result.get("ndvi_csv")
        result["outputs"]["record_count"] = ndvi_result.get("record_count")
    except Exception as e:
        result["errors"].append(f"NDVI aggregation failed: {e}")

    try:
        raster_result = compute_raster(metadata_path)
        result["outputs"]["ndvi_raster"] = raster_result.get("ndvi_raster")
        result["outputs"]["parcel_confidence"] = raster_result.get("parcel_confidence")
    except Exception as e:
        result["errors"].append(f"Raster computation failed: {e}")

    return result


def analyze_signals(ndvi_timeseries: list, ndvi_raster_path: str = None) -> Dict[str, Any]:
    anomalies = {}
    if not ndvi_timeseries:
        return anomalies

    ndvi_vals = [x["ndvi"] for x in ndvi_timeseries]

    anomalies["ndvi_anomaly"] = signals.ndvi_anomaly(ndvi_vals)
    anomalies["persistent_stress"] = signals.persistent_stress_detection(ndvi_vals)
    anomalies["z_score_anomalies"] = signals.z_score_anomaly(ndvi_vals).tolist()

    anomalies["disease_patch"] = detections.disease_patch_detection(ndvi_vals)
    cumulative_ndvi = sum(ndvi_vals)
    anomalies["yield_proxy"] = detections.yield_proxy(cumulative_ndvi, max(ndvi_vals), len(ndvi_vals))

    if len(ndvi_vals) >= 3:
        anomalies["fertilizer_issue"] = detections.fertilizer_issue_detection(ndvi_vals[0], ndvi_vals[len(ndvi_vals)//2], ndvi_vals[-1])

    latest_ndvi = ndvi_vals[-1] if ndvi_vals else 0

    latest_ndwi = ndvi_timeseries[-1].get("ndwi", 0.5) if ndvi_timeseries else 0.5
    latest_ndre = ndvi_timeseries[-1].get("ndre", 0.4) if ndvi_timeseries else 0.4

    anomalies["water_stress"] = signals.water_stress_score(latest_ndvi, latest_ndwi)
    anomalies["nutrient_stress"] = signals.nutrient_stress_score(latest_ndvi, latest_ndre)
    anomalies["irrigation_stress"] = signals.irrigation_stress_flag(latest_ndvi)

    real_raster = None
    if ndvi_raster_path:
        try:
            if ndvi_raster_path.endswith('.npy'):
                real_raster = np.load(ndvi_raster_path)
            elif ndvi_raster_path.endswith('.tif'):
                import rasterio
                with rasterio.open(ndvi_raster_path) as src:
                    real_raster = src.read(1)
        except Exception as e:
            print(f"[WARN] Failed to load real raster for texture: {e}")

    if real_raster is not None and not np.isnan(real_raster).all():
        valid_data = real_raster[~np.isnan(real_raster)]
        safe_raster = np.nan_to_num(real_raster, nan=np.nanmean(valid_data))
        texture_std = texture.local_std(safe_raster).mean()
        texture_ent = texture.local_entropy(safe_raster).mean()
    else:
        mock_raster = np.random.uniform(latest_ndvi-0.1, latest_ndvi+0.1, (20, 20))
        texture_std = texture.local_std(mock_raster).mean()
        texture_ent = texture.local_entropy(mock_raster).mean()
    anomalies["texture"] = {"mean_std": float(texture_std), "mean_entropy": float(texture_ent)}

    mock_sar = np.random.uniform(0.1, 0.5, (3, 10, 10))
    moisture_idx = sar.sar_moisture_index(mock_sar).mean()
    anomalies["sar_moisture_index"] = float(moisture_idx)

    anomalies["weeds_guidance"] = detections.weeds_guidance(latest_ndvi, texture_ent)

    return anomalies
