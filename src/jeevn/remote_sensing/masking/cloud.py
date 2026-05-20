"""
Cloud masking utilities for Sentinel-2 (SCL and QA60).
"""

import numpy as np


def scl_cloud_mask(scl_array: np.ndarray, cloud_classes: list = None) -> np.ndarray:
    """
    Boolean mask from Sentinel-2 Scene Classification Layer (SCL).
    Default cloud classes: {3 shadow, 8 cloud-med, 9 cloud-high, 10 cirrus}.
    """
    if cloud_classes is None:
        cloud_classes = {3, 8, 9, 10}
    else:
        cloud_classes = set(cloud_classes)

    return np.isin(scl_array, list(cloud_classes))


def qa60_mask(qa60_array: np.ndarray) -> np.ndarray:
    """
    Boolean mask from Sentinel-2 QA60 band.
    Bit 10 = cloud, bit 11 = cirrus.
    """
    cloud_bit = (qa60_array >> 10) & 1
    cirrus_bit = (qa60_array >> 11) & 1
    return (cloud_bit == 1) | (cirrus_bit == 1)


def apply_mask(
    data_array: np.ndarray,
    mask: np.ndarray,
    fill_value: float = np.nan
) -> np.ndarray:
    """Apply cloud mask to data array. Masked pixels become fill_value."""
    masked_data = data_array.astype(np.float32)
    masked_data[mask] = fill_value
    return masked_data
