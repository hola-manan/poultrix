"""
SAR (Synthetic Aperture Radar) helpers.
"""

import numpy as np


def sar_db_to_linear(sar_db: np.ndarray) -> np.ndarray:
    """SAR dB → linear scale."""
    return 10 ** (sar_db / 10)


def sar_linear_to_db(sar_linear: np.ndarray) -> np.ndarray:
    """SAR linear → dB scale."""
    sar_linear = np.asarray(sar_linear, dtype=float)
    if np.any(sar_linear <= 0):
        raise ValueError("sar_linear values must be positive")
    return 10 * np.log10(sar_linear)


def sar_vh_vv_difference(vh: np.ndarray, vv: np.ndarray) -> np.ndarray:
    """VH-VV polarization difference in dB."""
    return vh - vv


def sar_moisture_index(sar_stack: np.ndarray, temporal_window: int = 3) -> np.ndarray:
    """Moisture proxy from temporal SAR stack (3D: time x H x W)."""
    if len(sar_stack.shape) != 3:
        raise ValueError("sar_stack must be 3D (time, height, width)")

    temporal_median = np.median(sar_stack, axis=0)

    return temporal_median / (np.max(temporal_median) + 1e-6)


def sar_stack_loading(
    sar_file_paths: list,
    normalize: bool = True
) -> np.ndarray:
    """Load + stack SAR rasters into 3D (time x H x W)."""
    try:
        import rasterio
    except ImportError:
        raise ImportError("rasterio required for SAR loading")

    sar_stack = []

    for file_path in sar_file_paths:
        with rasterio.open(file_path) as src:
            sar_data = src.read(1).astype(np.float32)

            if normalize:
                sar_data = (sar_data - np.nanmean(sar_data)) / (np.nanstd(sar_data) + 1e-6)

            sar_stack.append(sar_data)

    return np.stack(sar_stack, axis=0)
