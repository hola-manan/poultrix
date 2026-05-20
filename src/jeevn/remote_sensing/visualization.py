"""
Server-side raster colorization.

Takes a *real* NDVI/NDWI numpy array (typically loaded from a GeoTIFF cropped
to the AOI polygon) and produces a colorized PNG. Pixels outside the polygon
arrive as NaN and are rendered fully transparent so the report image shows
the parcel shape, not a rectangle.

This module replaces the procedural synthetic field maps that used to live in
`jeevn.ui.visuals`. Anything the user sees should now come from a real raster.
"""

import io
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

try:
    from PIL import Image as PILImage, ImageFilter
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False


# ── Color stops ──────────────────────────────────────────────────────────────
NDVI_STOPS: List[Tuple[float, Tuple[int, int, int]]] = [
    (0.0, (211, 47, 47)),   (0.3, (245, 124, 0)),
    (0.5, (251, 192, 45)),  (0.7, (56, 142, 60)),
    (1.0, (27, 94, 32)),
]
NDWI_STOPS: List[Tuple[float, Tuple[int, int, int]]] = [
    (0.0, (183, 28, 28)),    (0.3, (239, 154, 154)),
    (0.5, (245, 245, 245)),  (0.7, (144, 202, 249)),
    (1.0, (13, 71, 161)),
]


def _interp_color(stops, t: float) -> Tuple[int, int, int]:
    t = max(0.0, min(1.0, float(t)))
    for i in range(len(stops) - 1):
        a, ca = stops[i]
        b, cb = stops[i + 1]
        if a <= t <= b:
            f = 0.0 if b == a else (t - a) / (b - a)
            return tuple(int(ca[j] + (cb[j] - ca[j]) * f) for j in range(3))
    return stops[-1][1]


def _normalize_for_palette(palette: str, value: np.ndarray) -> np.ndarray:
    """Map raw index values into the 0–1 colour-stop space.

    NDVI values are roughly in [-1, 1]; NDWI similarly. The stops are defined
    on [0, 1]. We rescale to that range and clamp.
    """
    if palette == "ndvi":
        # NDVI in [-1, 1] → [0, 1]
        return np.clip((value + 1.0) / 2.0, 0.0, 1.0)
    if palette == "ndwi":
        return np.clip((value + 1.0) / 2.0, 0.0, 1.0)
    return np.clip(value, 0.0, 1.0)


def load_raster_array(path: str) -> Optional[np.ndarray]:
    """Load an NDVI/NDWI raster from a `.tif` (rasterio) or `.npy` (numpy) file.

    Returns None if the file is missing or unreadable.
    """
    data = load_raster_data(path)
    if data:
        return data[0]
    return None


def load_raster_data(path: str):
    """Load an NDVI/NDWI raster from a `.tif` (rasterio) or `.npy` (numpy) file.

    Returns (array, transform, crs) or None if the file is missing or unreadable.
    """
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        return None
    try:
        if p.suffix == ".npy":
            return np.load(p), None, None
        import rasterio
        with rasterio.open(p) as src:
            arr = src.read(1).astype(np.float32)
            nodata = src.nodata
            if nodata is not None:
                arr = np.where(arr == nodata, np.nan, arr)
            return arr, src.transform, src.crs
    except Exception as e:
        print(f"[WARN] Failed to load raster {path}: {e}")
        return None


def colorize_raster(
    raster: np.ndarray,
    palette: str,
    output_size: Optional[Tuple[int, int]] = (440, 320),
    smooth: bool = True,
    geometry: Optional[dict] = None,
    transform: Optional[any] = None,
    crs: Optional[any] = None,
) -> Optional[bytes]:
    """Convert a real NDVI/NDWI raster into PNG bytes.

    Args:
        raster: 2-D float array. NaN pixels (e.g. outside the AOI polygon)
            become fully transparent in the output.
        palette: "ndvi" or "ndwi" — selects the colour ramp.
        output_size: (width, height) to upsample to. Real rasters at the
            parcel scale are tiny (a few × a few pixels at 10 m Sentinel-2
            resolution); a single emitter cell would otherwise be invisible.
            Pass None to leave at native size.
        smooth: apply a small Gaussian blur after upsampling so the upscaled
            pixels do not look like crude blocks.

    Returns PNG bytes, or None if PIL is unavailable or the input is empty.
    """
    if not PIL_AVAILABLE:
        return None
    if raster is None or raster.size == 0:
        return None

    stops = NDVI_STOPS if palette == "ndvi" else NDWI_STOPS

    # Build RGBA: alpha=0 outside the polygon (NaN), alpha=255 inside.
    nan_mask = np.isnan(raster)
    rescaled = _normalize_for_palette(palette, np.nan_to_num(raster, nan=0.0))

    h, w = raster.shape
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    for i in range(h):
        for j in range(w):
            if nan_mask[i, j]:
                rgba[i, j] = (0, 0, 0, 0)
            else:
                rgba[i, j, :3] = _interp_color(stops, float(rescaled[i, j]))
                rgba[i, j, 3] = 255

    img = PILImage.fromarray(rgba, "RGBA")

    if output_size:
        # Upsample with NEAREST first so blocks remain crisp, then blur a bit.
        img = img.resize(output_size, PILImage.NEAREST)

        if smooth:
            img = img.filter(ImageFilter.GaussianBlur(radius=1.5))

        if geometry and transform and crs:
            try:
                from rasterio.warp import transform_geom
                from PIL import ImageDraw
                
                proj_geom = transform_geom("EPSG:4326", crs, geometry)
                if proj_geom.get("type") == "Polygon":
                    coords = proj_geom["coordinates"][0]
                    pixel_coords = []
                    
                    scale_x = output_size[0] / w
                    scale_y = output_size[1] / h
                    
                    for x, y in coords:
                        px, py = ~transform * (x, y)
                        pixel_coords.append((px * scale_x, py * scale_y))
                        
                    draw = ImageDraw.Draw(img)
                    draw.polygon(pixel_coords, outline=(255, 255, 255, 255), width=3)
            except Exception as e:
                print(f"[WARN] Failed to draw geojson vector boundary: {e}")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()
