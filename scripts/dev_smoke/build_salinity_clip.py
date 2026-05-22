"""
One-shot prep script: download the ISRIC 2016 global soil salinity tiles,
mosaic them, clip to an India bounding box, and write a small compressed
GeoTIFF to `data/static/salinity_india.tif`.

The output is committed to the repo (under the gitignore exception added
for `data/static/`). After running this once, the runtime adapter in
`infrastructure/data_sources/soil.py` reads the clipped raster directly —
no network required at request time.

Source: https://files.isric.org/public/global_soil_salinity/salmap2016/
License: CC BY 4.0 (Wageningen University & ISRIC - World Soil Information)

Usage:
    python scripts/dev_smoke/build_salinity_clip.py

Expects rasterio + requests installed (they already are — rasterio is used
elsewhere in the codebase for Sentinel-2 raster processing).
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import requests
import rasterio
from rasterio.merge import merge


# ── Source config ──────────────────────────────────────────────────────────
SOURCE_YEAR = 2016
TILE_BASE_URL = f"https://files.isric.org/public/global_soil_salinity/salmap{SOURCE_YEAR}"

# Generated from the file index at the URL above. 3 row-tiles x 5 col-tiles.
TILE_NAMES = [
    f"salMap{SOURCE_YEAR}-{row:010d}-{col:010d}.tif"
    for row in (0, 32768, 65536)
    for col in (0, 32768, 65536, 98304, 131072)
]

# India bounding box (lon_min, lat_min, lon_max, lat_max) in degrees.
# Slightly padded so coastal/border AOIs are inside the clip.
INDIA_BBOX = (67.0, 5.0, 99.0, 38.0)

# ── Local paths ────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parents[2]
DOWNLOAD_DIR = REPO_ROOT / "data" / "cache" / "isric_salinity_2016"
OUTPUT_PATH = REPO_ROOT / "data" / "static" / "salinity_india.tif"


def _download_one(name: str, max_attempts: int = 4) -> Path:
    target = DOWNLOAD_DIR / name
    if target.exists() and target.stat().st_size > 0:
        return target

    url = f"{TILE_BASE_URL}/{name}"
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".part")

    last_err: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        # Resume from any bytes already on disk in `.part`.
        already = tmp.stat().st_size if tmp.exists() else 0
        headers = {"Range": f"bytes={already}-"} if already else {}
        suffix = f" (attempt {attempt}/{max_attempts}" + (
            f", resuming at {already / (1 << 20):.1f} MB)" if already else ")"
        )
        print(f"  -> downloading {name}{suffix}", flush=True)
        t0 = time.time()
        try:
            with requests.get(url, stream=True, timeout=180, headers=headers) as r:
                # 206 Partial Content for range request, 200 for fresh
                r.raise_for_status()
                mode = "ab" if already and r.status_code == 206 else "wb"
                if mode == "wb" and already:
                    # Server ignored Range header — restart from scratch.
                    already = 0
                with open(tmp, mode) as f:
                    for chunk in r.iter_content(chunk_size=1 << 20):  # 1 MiB
                        if chunk:
                            f.write(chunk)
            tmp.replace(target)
            dt = time.time() - t0
            size_mb = target.stat().st_size / (1024 * 1024)
            print(f"    {size_mb:.1f} MB in {dt:.1f}s", flush=True)
            return target
        except (requests.exceptions.ChunkedEncodingError,
                requests.exceptions.ConnectionError,
                requests.exceptions.ReadTimeout) as e:
            last_err = e
            partial_mb = tmp.stat().st_size / (1 << 20) if tmp.exists() else 0
            print(f"    transient error after {partial_mb:.1f} MB: {e}", flush=True)
            time.sleep(2 ** attempt)  # 2, 4, 8, 16s backoff

    raise RuntimeError(f"failed to download {name} after {max_attempts} attempts: {last_err}")


def main() -> int:
    print(f"ISRIC {SOURCE_YEAR} salinity -> India clip")
    print(f"  download cache: {DOWNLOAD_DIR}")
    print(f"  output: {OUTPUT_PATH}")
    print(f"  india bbox (lon_min, lat_min, lon_max, lat_max): {INDIA_BBOX}")
    print()

    # 1. Download all tiles (skipping any already present).
    print(f"[1/3] Fetching {len(TILE_NAMES)} ISRIC tiles ...")
    tile_paths = [_download_one(name) for name in TILE_NAMES]

    # 2. Merge with bounds= so only the India window is loaded into memory.
    print(f"[2/3] Merging tiles within India bbox ...")
    srcs = [rasterio.open(p) for p in tile_paths]
    try:
        merged_arr, merged_transform = merge(srcs, bounds=INDIA_BBOX)
        # All tiles share the same CRS — take it from the first source.
        merged_crs = srcs[0].crs
        dtype = srcs[0].dtypes[0]
        nodata = srcs[0].nodata
    finally:
        for s in srcs:
            s.close()

    bands, height, width = merged_arr.shape
    print(f"    output shape: bands={bands} h={height} w={width} dtype={dtype}")

    # 3. Write compressed GeoTIFF.
    print(f"[3/3] Writing {OUTPUT_PATH} ...")
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    profile = {
        "driver": "GTiff",
        "dtype": dtype,
        "count": bands,
        "width": width,
        "height": height,
        "crs": merged_crs,
        "transform": merged_transform,
        "compress": "DEFLATE",
        "predictor": 2 if dtype.startswith("int") or dtype.startswith("uint") else 3,
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
    }
    if nodata is not None:
        profile["nodata"] = nodata

    with rasterio.open(OUTPUT_PATH, "w", **profile) as dst:
        dst.write(merged_arr)

    final_mb = OUTPUT_PATH.stat().st_size / (1024 * 1024)
    print(f"    wrote {final_mb:.2f} MB")
    print()
    print("Done. Commit `data/static/salinity_india.tif` to ship it with the repo.")
    print(f"Cached tiles in {DOWNLOAD_DIR} can be deleted to reclaim ~360 MB.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
