"""
NDVI computation. Supports both array-based and path-based inputs;
when given paths, applies optional cloud masking via SCL or QA60.

`ndvi_index(red, nir)` is the canonical scalar/array NDVI formula — every
NDVI calculation in the codebase should go through it.
"""

import numpy as np
from pathlib import Path
from typing import Union, Optional, Dict, Any

from jeevn.remote_sensing.masking.cloud import scl_cloud_mask, qa60_mask, apply_mask


def ndvi_index(red, nir):
    """Canonical NDVI: (NIR - Red) / (NIR + Red). Works on scalars or arrays.

    Uses a small epsilon to avoid division by zero. This is the single source
    of truth for the NDVI formula — do not inline `(nir - red) / (nir + red)`
    elsewhere.
    """
    return (nir - red) / (nir + red + 1e-6)


def compute_ndvi(
    red_array: np.ndarray,
    nir_array: np.ndarray,
    output_path: Optional[str] = None
) -> Union[np.ndarray, str]:
    """Compute NDVI from raster arrays. Optionally write to GeoTIFF."""
    red = red_array.astype(np.float32)
    nir = nir_array.astype(np.float32)
    ndvi = ndvi_index(red, nir).astype(np.float32)

    if output_path:
        try:
            import rasterio
            from rasterio.transform import Affine

            transform = Affine.identity()

            with rasterio.open(
                output_path,
                'w',
                driver='GTiff',
                height=ndvi.shape[0],
                width=ndvi.shape[1],
                count=1,
                dtype=ndvi.dtype,
                transform=transform
            ) as dst:
                dst.write(ndvi, 1)

            return str(output_path)
        except ImportError:
            print("[WARN] rasterio not available, returning array")
            return ndvi

    return ndvi


def compute_ndvi_with_mask(
    red_path: str,
    nir_path: str,
    scl_path: Optional[str] = None,
    qa60_path: Optional[str] = None,
    output_dir: Optional[str] = None
) -> Dict[str, Any]:
    """Compute NDVI from raster paths with optional cloud masking."""
    try:
        import rasterio
    except ImportError:
        raise ImportError("rasterio required for raster I/O")

    with rasterio.open(red_path) as src:
        red_data = src.read(1)
        profile = src.profile

    with rasterio.open(nir_path) as src:
        nir_data = src.read(1)

    ndvi = compute_ndvi(red_data, nir_data)

    mask = None
    if scl_path and Path(scl_path).exists():
        with rasterio.open(scl_path) as src:
            scl_data = src.read(1)
        mask = scl_cloud_mask(scl_data)
        ndvi = apply_mask(ndvi, mask)

    elif qa60_path and Path(qa60_path).exists():
        with rasterio.open(qa60_path) as src:
            qa60_data = src.read(1)
        mask = qa60_mask(qa60_data)
        ndvi = apply_mask(ndvi, mask)

    output_path = None
    if output_dir:
        output_path = Path(output_dir) / "ndvi_masked.tif"
        profile.update(dtype=ndvi.dtype, count=1)

        with rasterio.open(output_path, 'w', **profile) as dst:
            dst.write(ndvi, 1)

    return {
        "ndvi": ndvi,
        "mask": mask,
        "output_path": str(output_path) if output_path else None
    }
