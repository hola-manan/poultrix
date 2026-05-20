"""
UI-side visual helpers.

The NDVI / NDWI colour ramps and the raster colorizer live server-side in
`jeevn.remote_sensing.visualization` and are served via the API. The UI no
longer fabricates field maps from a scalar mean — when a real raster is
unavailable, the field-maps section says so explicitly.

The only thing still produced client-side is the small colour-scale legend
that sits next to the maps; that is purely a key for the colour ramp, not
imagery of the parcel.
"""

import io
from typing import Optional

# Reuse the canonical colour stops from the server-side renderer so the legend
# colours match the colorized maps pixel-for-pixel.
from jeevn.remote_sensing.visualization import (
    NDVI_STOPS, NDWI_STOPS, _interp_color, PIL_AVAILABLE,
)

try:
    from PIL import Image as PILImage, ImageDraw, ImageFont
except Exception:
    pass


def scale_bar(palette: str, label_lo: str, label_hi: str,
              w: int = 220, h: int = 22) -> Optional[io.BytesIO]:
    """Horizontal colour-scale legend with low/high text labels.

    `palette` is 'ndvi' or 'ndwi'. Returns BytesIO PNG, or None if PIL is
    unavailable.
    """
    if not PIL_AVAILABLE:
        return None
    try:
        stops = NDVI_STOPS if palette == 'ndvi' else NDWI_STOPS
        bar_h = max(10, h - 10)
        img = PILImage.new('RGB', (w, h), (255, 255, 255))
        draw = ImageDraw.Draw(img)
        for x in range(w):
            t = x / max(1, w - 1)
            draw.line([(x, 0), (x, bar_h - 1)], fill=_interp_color(stops, t))
        try:
            font = ImageFont.truetype("arial.ttf", 9)
        except Exception:
            font = ImageFont.load_default()
        draw.text((2, bar_h), label_lo, fill=(40, 40, 40), font=font)
        try:
            bbox = draw.textbbox((0, 0), label_hi, font=font)
            tw = bbox[2] - bbox[0]
        except Exception:
            tw = len(label_hi) * 5
        draw.text((w - tw - 2, bar_h), label_hi, fill=(40, 40, 40), font=font)
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return buf
    except Exception:
        return None
