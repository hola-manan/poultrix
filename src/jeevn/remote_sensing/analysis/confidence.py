"""
Parcel-level NDVI raster + NDWI raster computation and confidence summary.

This module produces *real* rasters from Sentinel-2 COG bands when available:
- NDVI from B04 (red) + B08 (NIR)
- NDWI from B03 (green) + B11 (SWIR)

If the COG bands cannot be fetched (no STAC, no rasterio, network failure),
the corresponding raster is reported as `None` rather than synthesised — the
report's data-quality layer will flag this so the UI/PDF can show the user
that no real raster was available.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional

import numpy as np

from jeevn.remote_sensing.ndvi.compute import ndvi_index


def compute_parcel_confidence(ndvi_raster: np.ndarray) -> Dict[str, Any]:
    """Confidence score from NDVI raster (mean + uniformity + validity)."""
    valid_pixels = ndvi_raster[~np.isnan(ndvi_raster)]

    if len(valid_pixels) == 0:
        return {
            "mean_ndvi": None,
            "std_ndvi": None,
            "valid_pixel_pct": 0,
            "confidence_score": 0.0
        }

    mean_ndvi = float(np.mean(valid_pixels))
    std_ndvi = float(np.std(valid_pixels))
    valid_pct = float(100.0 * len(valid_pixels) / ndvi_raster.size)

    ndvi_score = min(1.0, max(0.0, (mean_ndvi + 1) / 2))
    uniformity_score = 1.0 - min(1.0, std_ndvi)
    validity_score = valid_pct / 100.0

    confidence_score = (ndvi_score * 0.4 + uniformity_score * 0.3 + validity_score * 0.3)

    return {
        "mean_ndvi": mean_ndvi,
        "std_ndvi": std_ndvi,
        "valid_pixel_pct": valid_pct,
        "confidence_score": float(confidence_score),
        "min_ndvi": float(np.min(valid_pixels)),
        "max_ndvi": float(np.max(valid_pixels))
    }


def _compute_index_raster(red_url: str, nir_url: str, geometry: dict
                          ) -> Optional["tuple"]:
    """Return (raster_array, profile) for a normalised-difference index
    using the two given band URLs, cropped to the AOI geometry.

    Returns None if rasterio is unavailable or any band fetch fails.
    """
    try:
        import rasterio
        from rasterio.mask import mask
        from rasterio.warp import transform_geom
    except ImportError:
        return None

    try:
        from rasterio.warp import reproject, Resampling
        with rasterio.open(red_url) as src_red:
            projected_geom = transform_geom("EPSG:4326", src_red.crs, geometry)
            red_data, out_transform = mask(src_red, [projected_geom], crop=True, all_touched=True)
            profile = src_red.profile
            raster_crs = src_red.crs

        with rasterio.open(nir_url) as src_nir:
            nir_data, nir_transform = mask(src_nir, [projected_geom], crop=True, all_touched=True)

        red_data = red_data[0].astype(np.float32)
        nir_data = nir_data[0].astype(np.float32)

        if red_data.shape != nir_data.shape:
            resampled_nir = np.empty_like(red_data)
            reproject(
                nir_data,
                resampled_nir,
                src_transform=nir_transform,
                src_crs=raster_crs,
                dst_transform=out_transform,
                dst_crs=raster_crs,
                resampling=Resampling.bilinear
            )
            nir_data = resampled_nir

        valid_mask = (red_data > 0) & (nir_data > 0)
        raster = np.full_like(red_data, np.nan, dtype=np.float32)
        raster[valid_mask] = ndvi_index(red_data[valid_mask], nir_data[valid_mask])

        profile.update({
            "driver": "GTiff",
            "height": raster.shape[0],
            "width": raster.shape[1],
            "transform": out_transform,
            "count": 1,
            "dtype": "float32",
            "nodata": np.nan,
        })
        return raster, profile
    except Exception as e:
        print(f"[WARN] Index raster generation failed: {e}")
        return None


def _write_raster_tif(path: Path, raster: np.ndarray, profile: dict
                      ) -> Optional[str]:
    """Persist a float32 raster as GeoTIFF; returns the path or None on failure."""
    try:
        import rasterio
        with rasterio.open(path, "w", **profile) as dst:
            dst.write(raster.astype(np.float32), 1)
        return str(path)
    except Exception as e:
        print(f"[WARN] Failed to write raster {path}: {e}")
        return None


def compute_raster(metadata_path: str,
                   output_dir: str = "data") -> Dict[str, Any]:
    """Compute real NDVI + NDWI rasters from the latest cloud-optimised
    Sentinel-2 item in `metadata_path`. Both rasters are independently
    optional — either may be `None` if its source bands or rasterio are
    unavailable.

    Returns:
        ndvi_raster: path to GeoTIFF or None
        ndwi_raster: path to GeoTIFF or None
        parcel_confidence: dict or None (None when no NDVI raster)
        raster_quality: which rasters are real vs missing (for data_quality
                        propagation into the advisory report).
    """
    metadata_path_obj = Path(metadata_path)
    metadata_dir = metadata_path_obj.parent
    # Scope output filenames to this AOI so concurrent submissions do not
    # overwrite each other's rasters in the shared data/ directory.
    stem = metadata_path_obj.stem  # e.g. "ingest_metadata_<aoi_id>"

    with open(metadata_path, "r") as f:
        metadata = json.load(f)

    geometry = metadata.get("aoi", {}).get("features", [{}])[0].get("geometry")
    stac_items = metadata.get("stac_items", [])

    ndvi_path = None
    ndwi_path = None
    ndvi_array = None
    capture_date = None

    if stac_items and geometry:
        latest_item = sorted(stac_items, key=lambda x: x["properties"]["datetime"])[-1]
        capture_date = latest_item.get("properties", {}).get("datetime")
        if capture_date:
            capture_date = capture_date[:10]
        assets = latest_item.get("assets", {})
        red_url = assets.get("B04", {}).get("href")
        nir_url = assets.get("B08", {}).get("href")
        green_url = assets.get("B03", {}).get("href")
        swir_url = assets.get("B11", {}).get("href")

        # ── NDVI = (NIR - Red) / (NIR + Red) ────────────────────────────────
        if red_url and nir_url:
            result = _compute_index_raster(red_url, nir_url, geometry)
            if result is not None:
                ndvi_array, profile = result
                ndvi_path = _write_raster_tif(
                    metadata_dir / f"{stem}_ndvi.tif", ndvi_array, profile,
                )

        if green_url and swir_url:
            # Pass Green (10m) first so the output is 10m resolution.
            # ndvi_index calculates (band2 - band1) / (band2 + band1), so
            # passing (Green, SWIR) calculates (SWIR - Green) / (SWIR + Green).
            # We invert it to get (Green - SWIR) / (Green + SWIR) = NDWI.
            result = _compute_index_raster(green_url, swir_url, geometry)
            if result is not None:
                ndwi_array, profile = result
                ndwi_array = -ndwi_array
                ndwi_path = _write_raster_tif(
                    metadata_dir / f"{stem}_ndwi.tif", ndwi_array, profile,
                )

    parcel_confidence = compute_parcel_confidence(ndvi_array) if ndvi_array is not None else None

    return {
        "ndvi_raster": ndvi_path,
        "ndwi_raster": ndwi_path,
        "parcel_confidence": parcel_confidence,
        "raster_quality": {
            "ndvi_raster_available": ndvi_path is not None,
            "ndwi_raster_available": ndwi_path is not None,
            "capture_date": capture_date,
        },
    }
