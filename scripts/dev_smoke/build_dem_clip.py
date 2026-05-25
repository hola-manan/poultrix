"""
One-shot prep script: clip the NOAA ETOPO 2022 30 arc-second global
surface-elevation GeoTIFF to an India bounding box and write a small
compressed GeoTIFF to `data/static/dem_india.tif`.

The global source is ~1.58 GB and tiled internally, so instead of
downloading the whole thing we use GDAL's /vsicurl/ to HTTP-range-read
just the bytes for the India window (~10-50 MB depending on tile layout).

The output is the fallback DEM used by `infrastructure/data_sources/terrain.py`
when the primary Open-Elevation API is unreachable. ~1 km precision is
admittedly coarse for slope/aspect, but the primary path (Open-Elevation
backed by SRTM ~30 m) covers most requests; this just keeps the system
useful when the network is down.

Source: https://www.ngdc.noaa.gov/mgg/global/relief/ETOPO2022/data/30s/
License: U.S. Government public domain (NOAA NCEI).

Usage:
    python scripts/dev_smoke/build_dem_clip.py

Requires: rasterio with GDAL >= 3 (for /vsicurl/ + HTTP range support).
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import from_bounds


# ── Source config ──────────────────────────────────────────────────────────
SOURCE_URL = (
    "https://www.ngdc.noaa.gov/mgg/global/relief/ETOPO2022/data/30s/"
    "30s_surface_elev_gtif/ETOPO_2022_v1_30s_N90W180_surface.tif"
)
# Wrap as a GDAL Virtual File System path so rasterio fetches via HTTP
# range requests instead of downloading the whole file.
VSI_PATH = f"/vsicurl/{SOURCE_URL}"

# India bounding box (lon_min, lat_min, lon_max, lat_max) in degrees.
INDIA_BBOX = (67.0, 5.0, 99.0, 38.0)

# ── Local paths ────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PATH = REPO_ROOT / "data" / "static" / "dem_india.tif"


def main() -> int:
    print("ETOPO 2022 30 arc-sec -> India clip (via /vsicurl/)")
    print(f"  source: {SOURCE_URL}")
    print(f"  output: {OUTPUT_PATH}")
    print(f"  india bbox: {INDIA_BBOX}")
    print()

    # Tell GDAL to be aggressive with range reads + caching for the remote file.
    os.environ.setdefault("GDAL_HTTP_TIMEOUT", "120")
    os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "5")
    os.environ.setdefault("GDAL_HTTP_RETRY_DELAY", "2")
    os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif")
    os.environ.setdefault("VSI_CACHE", "TRUE")
    os.environ.setdefault("VSI_CACHE_SIZE", str(256 * 1024 * 1024))  # 256 MB

    print("[1/2] Opening remote ETOPO global via /vsicurl/ + range reads ...")
    t0 = time.time()
    with rasterio.open(VSI_PATH) as src:
        print(f"    remote raster: {src.width} x {src.height} {src.dtypes[0]}, "
              f"CRS {src.crs}")
        window = from_bounds(*INDIA_BBOX, transform=src.transform)
        window = window.round_offsets().round_lengths()
        print(f"    India window: col_off={window.col_off}, row_off={window.row_off}, "
              f"w={window.width}, h={window.height}")
        arr = src.read(1, window=window)
        out_transform = src.window_transform(window)
        out_crs = src.crs
        out_dtype = src.dtypes[0]
        out_nodata = src.nodata
    print(f"    fetched {arr.nbytes / (1 << 20):.1f} MB raw in {time.time() - t0:.1f}s")

    # Quantize float32 -> int16 metres. ETOPO has ~0.5 m fractional precision,
    # but slope on a 1 km cellsize is insensitive to sub-metre noise. Halving
    # the dtype size dramatically improves compression. int16 nodata = -32768.
    INT16_NODATA = np.int16(-32768)
    if "float" in str(out_dtype):
        nodata_mask = (arr == out_nodata) if out_nodata is not None else np.zeros_like(arr, dtype=bool)
        # Clip to int16 range to handle any oddball values (Everest is 8849 m,
        # deepest trench is ~-11000 m — both fit in int16's [-32768, 32767]).
        arr16 = np.clip(np.round(arr), -32767, 32767).astype(np.int16)
        arr16[nodata_mask] = INT16_NODATA
        arr = arr16
        out_dtype = "int16"
        out_nodata = int(INT16_NODATA)
        print(f"    quantized to int16 metres (nodata={out_nodata})")

    print(f"[2/2] Writing {OUTPUT_PATH} ...")
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    profile = {
        "driver": "GTiff",
        "dtype": out_dtype,
        "count": 1,
        "width": arr.shape[1],
        "height": arr.shape[0],
        "crs": out_crs,
        "transform": out_transform,
        "compress": "DEFLATE",
        "predictor": 2,  # horizontal differencing — best for integer DEMs
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
    }
    if out_nodata is not None:
        profile["nodata"] = out_nodata

    with rasterio.open(OUTPUT_PATH, "w", **profile) as dst:
        dst.write(arr, 1)

    final_mb = OUTPUT_PATH.stat().st_size / (1 << 20)
    print(f"    wrote {final_mb:.2f} MB")
    print()
    print("Done. Commit `data/static/dem_india.tif` to ship the fallback DEM.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
