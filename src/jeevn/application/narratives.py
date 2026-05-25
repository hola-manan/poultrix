"""
Pure narrative-shaping helpers — no I/O, no streamlit, no reportlab.

These functions live in `application/` so both the Streamlit UI and the
PDF generator can import them and produce identical text from the same
inputs (single source of truth for branching narrative thresholds).
"""

from __future__ import annotations


def terrain_irrigation_advice(slope_pct: float, aspect_compass: str) -> str:
    """Branching narrative for slope/aspect implications on irrigation.

    Thresholds picked from FAO Irrigation & Drainage Paper 24 and ICAR
    field guidelines:
      < 2%  : essentially flat — basin or flood OK, drip optional
      2-5%  : mild slope — drip preferred to avoid runoff and uneven wetting
      > 5%  : steep — drip + contour layout or terracing required
    Aspect colours the insolation note: south-facing rows in the northern
    hemisphere see more sun (higher ET), north-facing the opposite.
    """
    if slope_pct < 2.0:
        method = (
            "essentially flat, so basin or flood irrigation is acceptable; "
            "drip remains the most water-efficient choice"
        )
    elif slope_pct < 5.0:
        method = (
            "a mild slope, so drip irrigation is preferred over basin or "
            "flood to prevent runoff and uneven wetting"
        )
    else:
        method = (
            "a steep slope, requiring drip irrigation laid out along contour "
            "lines, with terracing recommended to prevent erosion"
        )

    aspect_note = ""
    if aspect_compass in ("S", "SE", "SW"):
        aspect_note = (
            " The south-facing aspect increases insolation and "
            "evapotranspiration; schedule irrigation slightly earlier in the "
            "morning to compensate."
        )
    elif aspect_compass in ("N", "NE", "NW"):
        aspect_note = (
            " The north-facing aspect receives less direct sun, so "
            "evapotranspiration is moderated."
        )
    return f"Field slope is {method}.{aspect_note}"
