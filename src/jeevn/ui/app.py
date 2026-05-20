"""
Streamlit demo UI for Jeevn MVP.

This is a thin frontend. ALL data comes from the API via api_client —
no in-process imports of domain or application modules, no proxy fallbacks.
"""

import json
from datetime import datetime

import streamlit as st

try:
    import folium
    from streamlit_folium import st_folium
    from folium.plugins import Draw, Geocoder
    FOLIUM_AVAILABLE = True
except ImportError:
    FOLIUM_AVAILABLE = False

from jeevn.infrastructure import pseudo_satellite
from jeevn.ui.api_client import JeevnAPIClient
from jeevn.ui.geo_utils import extract_centroid, estimate_area_acres
from jeevn.ui.pdf.generator import generate_pdf, PIL_AVAILABLE
from jeevn.ui.sections import (
    field_maps, irrigation_schedule, soil_growth, pest_disease_weed, fertilizer,
)


st.set_page_config(
    page_title="Personalized Farm Advisory Report",
    page_icon="🌾",
    layout="wide"
)


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Configuration")

    api_url = st.text_input(
        "API URL",
        value="http://localhost:8000",
        help="Base URL for the Jeevn API"
    )

    st.markdown("---")

    if st.button("Check API Health"):
        client = JeevnAPIClient(api_url)
        if client.health():
            st.success("✅ API is healthy")
        else:
            st.error("❌ API connection failed")


client = JeevnAPIClient(api_url)


# ── Main UI ───────────────────────────────────────────────────────────────────
st.title("🌾 Personalized Farm Advisory Report")

tab_submit, tab_report = st.tabs(["Submit AOI", "View Report"])

with tab_submit:
    col1, col2 = st.columns(2)

    with col1:
        aoi_name = st.text_input("AOI Name", value="My Farm AOI")
        crop_type = st.text_input("Crop Type", value="Apple")
        start_date = st.date_input("Start Date / Sowing Date", value=datetime(2026, 5, 1))
        end_date = st.date_input("End Date")

    with col2:
        st.markdown("**Select Area on Map**")
        drawn_geojson = None

        if FOLIUM_AVAILABLE:
            m = folium.Map(
                location=[pseudo_satellite.DEFAULT_LATITUDE, pseudo_satellite.DEFAULT_LONGITUDE],
                zoom_start=8,
            )
            Geocoder().add_to(m)
            draw = Draw(
                draw_options={'polyline': False, 'polygon': True, 'rectangle': True,
                              'circle': False, 'marker': False, 'circlemarker': False},
                edit_options={'edit': False})
            draw.add_to(m)
            output = st_folium(m, height=300, use_container_width=True)
            if output and output.get("last_active_drawing"):
                drawn_geojson = {
                    "type": "FeatureCollection",
                    "features": [{"type": "Feature",
                                  "geometry": output["last_active_drawing"]["geometry"]}]
                }
                st.success("✅ AOI drawn successfully!")

        default_val = json.dumps(drawn_geojson, indent=2) if drawn_geojson else json.dumps({
            "type": "FeatureCollection",
            "features": [{"type": "Feature", "geometry": {
                "type": "Polygon",
                "coordinates": [[[73.865536, 29.925147], [73.865268, 29.924394], [73.865976, 29.924449], [73.865536, 29.925147]]]
            }}]
        }, indent=2)
        geojson_text = st.text_area("GeoJSON Code", height=100, value=default_val)

    if st.button("Submit & Generate Report", type="primary", use_container_width=True):
        try:
            geojson = json.loads(geojson_text)
        except Exception:
            st.error("Invalid GeoJSON — please check the code box.")
            st.stop()

        lat, lon = extract_centroid(geojson)
        area = estimate_area_acres(geojson)
        sowing = start_date.isoformat() if start_date else None
        end = end_date.isoformat() if end_date else None

        st.session_state.lat = lat
        st.session_state.lon = lon
        st.session_state.area_acres = area
        st.session_state.crop_type = crop_type
        st.session_state.pop('pdf_bytes', None)

        ndvi_timeseries = None
        with st.spinner("Fetching satellite NDVI data…"):
            try:
                aoi_result = client.submit_aoi(
                    name=aoi_name, geojson=geojson,
                    start_date=sowing, end_date=end,
                )
                st.session_state.aoi_result = aoi_result
                ndvi_timeseries = aoi_result.get("ndvi_timeseries")
            except Exception as e:
                st.error(f"AOI submission failed: {e}")
                st.stop()

        with st.spinner("Generating agricultural advisory via API…"):
            try:
                adv_result = client.generate_advisory(
                    name=aoi_name, latitude=lat, longitude=lon,
                    area_acres=area, crop_type=crop_type,
                    sowing_date=sowing, ndvi_timeseries=ndvi_timeseries,
                    location_name="",
                )
                if adv_result.get("status") == "completed":
                    st.session_state.advisory_report = adv_result.get("report") or {}
                else:
                    st.error(f"Advisory generation failed: {adv_result.get('error')}")
                    st.stop()
            except Exception as e:
                st.error(f"Advisory request failed: {e}")
                st.stop()

        st.success("✅ Analysis complete! Switch to the **View Report** tab.")


with tab_report:
    aoi_result = st.session_state.get("aoi_result")
    advisory = st.session_state.get("advisory_report", {})

    if not aoi_result or not advisory:
        st.info("Submit an AOI first to fetch and calculate your personalised report.")
    else:
        comp = advisory.get("components", {})
        aoi_info = advisory.get("aoi_info", {})
        crop_type = st.session_state.get("crop_type", "Apple")

        confidence = aoi_result.get("parcel_confidence") or {}
        mean_ndvi = confidence.get("mean_ndvi")

        soil_comp = comp.get("soil_management") or {}
        growth_comp = comp.get("growth_yield") or {}
        soil_moisture = soil_comp.get("soil_moisture_current")

        # ── Shared context for narratives (mirrors PDF page header + body) ─
        crop_name = (aoi_info.get("crop") or crop_type or "Crop").title()
        location = aoi_info.get("location") or ""
        lat = aoi_info.get("latitude") or st.session_state.get("lat", 0)
        sat_visit = aoi_info.get("satellite_visit", datetime.now().strftime("%d %b %Y"))
        area_disp = aoi_info.get("area_acres", st.session_state.get("area_acres", "—"))
        growth_stage_name = (growth_comp.get("current_growth_stage") or "growth").replace("_", " ").title()
        vigor = (growth_comp.get("vegetation_vigor") or "good").lower()

        # ── Header (matches PDF banner) ────────────────────────────────────
        col_h1, col_h2 = st.columns([3, 1])
        col_h1.title("Personalized Farm Advisory Report")
        col_h2.info(f"**Report Date:** {datetime.now().strftime('%d/%m/%Y')}")
        st.markdown(
            f"**{location}**   |   **Area:** {area_disp} acres   |   "
            f"**Satellite Visit:** {sat_visit}   |   **Crop:** {crop_name}"
        )

        # Data-quality banner: warn if any input was fabricated.
        dq = advisory.get("data_quality") or {}
        fabricated = dq.get("fabricated_fields") or []
        if fabricated:
            details = dq.get("details") or {}
            bullets = "\n".join(f"- **{f}** — {details.get(f, f)}" for f in fabricated)
            st.warning(
                "⚠ Some inputs to this report are **fabricated defaults** "
                "(real measurements were not available). Treat the affected "
                "outputs as illustrative.\n\n" + bullets
            )

        st.markdown("---")

        # ── Page 1 of PDF: Field Maps + Analysis Scale ─────────────────────
        # Real Sentinel-2 NDVI / NDWI rasters are fetched on demand from the
        # API; the section displays an explicit "unavailable" notice when no
        # real raster was produced (e.g. stub ingest path).
        aoi_id = aoi_result.get("aoi_id", "")
        raster_quality = aoi_result.get("raster_quality") or {}
        field_maps.render(client, aoi_id, raster_quality)
        st.markdown("---")

        # ── Page 2 of PDF: Irrigation Schedule ─────────────────────────────
        irrigation_schedule.render(
            comp.get("irrigation_schedule"),
            crop_name=crop_name, location=location, lat=lat,
            growth_stage_name=growth_stage_name,
        )
        st.markdown("---")

        # ── Page 3 of PDF: Soil Management & Growth / Yield ────────────────
        soil_growth.render(
            soil_comp, growth_comp,
            crop_name=crop_name, location=location,
            growth_stage_name=growth_stage_name,
            satellite_visit=sat_visit,
        )
        st.markdown("---")

        # ── Page 4 of PDF: Pest, Disease & Weed Management ─────────────────
        pest_disease_weed.render(
            comp.get("pest_disease_weed"),
            location=location, vigor=vigor,
        )
        st.markdown("---")

        # ── Page 5 of PDF: Fertilizer Management ───────────────────────────
        fertilizer.render(
            comp.get("fertilizer_management"),
            crop_name=crop_name, growth_stage_name=growth_stage_name,
        )
        st.markdown("---")

        # Amber disclaimer box (matches PDF page 5 footer)
        st.warning(
            "**Disclaimer:** This farm advisory report is AI-generated and should be "
            "used as a general guide only. All recommendations should be verified by "
            "agricultural experts and adapted to local conditions before implementation."
        )

        st.markdown("### 📄 Export Report")
        _, col_pdf, _ = st.columns([1, 2, 1])
        with col_pdf:
            if st.button("Generate PDF Report", type="primary", use_container_width=True):
                with st.spinner("Building PDF…"):
                    try:
                        pdf_report = dict(advisory) if advisory else {}

                        if not pdf_report.get("aoi_info"):
                            pdf_report["aoi_info"] = {
                                "area_acres": st.session_state.get(
                                    "area_acres", pseudo_satellite.DEFAULT_AREA_ACRES),
                                "crop": crop_type,
                                "location": "",
                                "latitude": st.session_state.get("lat"),
                                "longitude": st.session_state.get("lon"),
                                "satellite_visit": sat_visit,
                            }
                            pdf_report["report_date"] = datetime.now().strftime("%d/%m/%Y")

                        # Pull the same real-raster PNGs the HTML field-maps
                        # section uses, so the PDF mirrors what the user
                        # already sees on screen byte-for-byte. When no real
                        # raster exists, the PDF shows an "unavailable" note
                        # instead of a fabricated map.
                        ndvi_png = (client.fetch_aoi_map(aoi_id, "ndvi")
                                    if raster_quality.get("ndvi_raster_available") else None)
                        ndwi_png = (client.fetch_aoi_map(aoi_id, "ndwi")
                                    if raster_quality.get("ndwi_raster_available") else None)
                        st.session_state.pdf_bytes = generate_pdf(
                            report=pdf_report,
                            ndvi_png=ndvi_png,
                            ndwi_png=ndwi_png,
                        )
                        if not PIL_AVAILABLE:
                            st.warning("Pillow (PIL) not available — field maps will be omitted.")
                    except Exception as pdf_err:
                        st.error(f"PDF generation failed: {pdf_err}")

            if st.session_state.get("pdf_bytes"):
                st.download_button(
                    label="⬇ Download PDF",
                    data=st.session_state.pdf_bytes,
                    file_name=f"farm_advisory_{datetime.now().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
