"""
Section 1 & 2 of the report: real Sentinel-2 Crop Health (NDVI) and Irrigation
Health (NDWI) maps + their colour-scale legends. Mirrors PDF page 1.

The map images come from the API endpoint /aoi/{id}/maps/{kind}.png, which
serves the real raster cropped to the AOI polygon. When the server has no
real raster (stub ingest, no STAC items, rasterio missing), we explicitly
say so rather than substitute synthetic imagery.
"""

import streamlit as st

from jeevn.ui.api_client import JeevnAPIClient
from jeevn.ui.visuals import scale_bar, PIL_AVAILABLE


def render(api_client: JeevnAPIClient, aoi_id: str, raster_quality: dict | None = None):
    st.header("1.  Field Maps")

    rq = raster_quality or {}
    ndvi_available = bool(rq.get("ndvi_raster_available"))
    ndwi_available = bool(rq.get("ndwi_raster_available"))
    capture_date = rq.get("capture_date")
    date_suffix = f" (Captured: {capture_date})" if capture_date else ""

    ndvi_bytes = api_client.fetch_aoi_map(aoi_id, "ndvi") if ndvi_available else None
    ndwi_bytes = api_client.fetch_aoi_map(aoi_id, "ndwi") if ndwi_available else None

    c1, c2 = st.columns(2)

    with c1:
        if ndvi_bytes:
            st.image(
                ndvi_bytes,
                caption=f"Crop Health Map (Sentinel-2 NDVI, cropped to AOI){date_suffix}",
                use_container_width=True,
            )
        else:
            st.info(
                "Crop Health Map unavailable — no real Sentinel-2 NDVI raster "
                "was produced for this AOI (typical when running the stub "
                "ingest, when no recent STAC items are found, or when "
                "`rasterio` is not installed)."
            )

    with c2:
        if ndwi_bytes:
            st.image(
                ndwi_bytes,
                caption=f"Irrigation Health Map (Sentinel-2 NDWI, cropped to AOI){date_suffix}",
                use_container_width=True,
            )
        else:
            st.info(
                "Irrigation Health Map unavailable — no real Sentinel-2 NDWI "
                "raster was produced for this AOI."
            )

    st.header("2.  Analysis Scale")

    if not PIL_AVAILABLE:
        st.info("Scale bars require Pillow (PIL). Install it to enable them.")
        return

    ndvi_scale = scale_bar('ndvi', 'Low (0)', 'High (1.0)')
    ndwi_scale = scale_bar('ndwi', 'Dry (0)', 'Wet (1.0)')
    if ndvi_scale and ndwi_scale:
        c1, c2 = st.columns(2)
        c1.markdown("**Crop Health Scale (NDVI)**")
        c1.image(ndvi_scale, use_container_width=True)
        c2.markdown("**Irrigation Health Scale (NDWI)**")
        c2.image(ndwi_scale, use_container_width=True)
