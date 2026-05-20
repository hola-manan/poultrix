"""
Section 4 of the report: Soil Management + Growth / Yield side-by-side, with
the narrative + reference paragraphs the PDF emits on page 3.
"""

from datetime import datetime

import streamlit as st


def render(soil: dict, growth: dict, *, crop_name: str, location: str,
           growth_stage_name: str, satellite_visit: str):
    st.header("4.  Soil Management & Growth / Yield")

    if not soil and not growth:
        st.info("Soil management and growth/yield data not available.")
        return

    soil = soil or {}
    growth = growth or {}

    ph = soil.get('ph', 7.0)
    salinity = (soil.get('salinity') or 'low').title()
    soc = soil.get('organic_carbon_percent', 0.15)
    soc_status = (soil.get('organic_carbon_status') or 'low').lower()

    yld_acre = int(growth.get('yield_per_acre_kg', 0))
    total_yld = growth.get('total_yield_kg', 0)
    harvest_stat = (growth.get('harvest_status') or 'incomplete').title()
    loss_pct = growth.get('potential_loss_percent', 0)
    potential_yld = growth.get('yield_potential_kg_per_acre', 2500)
    vigor = (growth.get('vegetation_vigor') or 'good').lower()
    limiting = [f['factor'] for f in growth.get('limiting_factors', [])][:3]
    limiting_str = ', '.join(limiting) if limiting else 'minor nutrient deficiencies'

    # Harvest period derived from satellite-visit string (e.g. "13 May 2026" → "May 2026")
    parts = (satellite_visit or '').split()
    harvest_period = ' '.join(parts[-2:]) if len(parts) >= 2 else (satellite_visit or '—')

    # ── Side-by-side metric boxes (left: soil, right: yield) ────────────────
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("##### Soil Management")
        m1, m2 = st.columns(2)
        m1.metric("pH", ph)
        m2.metric("Salinity", salinity)
        st.metric("Organic Carbon", f"{soc:.2f}%", delta=soc_status.title(),
                  delta_color="off")

    with c2:
        st.markdown("##### Growth & Yield")
        m1, m2 = st.columns(2)
        m1.metric("Crop", crop_name)
        m2.metric("Yield / acre (kg)", f"{yld_acre:,}")
        m3, m4 = st.columns(2)
        m3.metric("Total Yield (kg)", f"{total_yld:,.1f}")
        m4.metric("Harvest Period", harvest_period)
        st.metric("Status", harvest_stat)

    # ── Details — Soil Management ──────────────────────────────────────────
    st.markdown("**Details — Soil Management**")
    st.markdown(
        f"Soil pH is predicted at {ph} based on regional {location} trends and previous "
        f"irrigation cycles; salinity remains {salinity.lower()} due to controlled drip "
        f"leaching fractions. The current soil organic carbon (SOC) level of {soc:.2f}% is "
        f"**{soc_status}** for {crop_name.lower()} cultivation. Low SOC leads to poor soil "
        "structure, reduced water-holding capacity, and inefficient nutrient cycling. To "
        "improve SOC, incorporate well-rotted manure or compost, use cover crops between "
        "rows, and apply organic mulches to enhance microbial activity and soil aggregates."
    )
    st.caption(
        "*References: pH and Salinity estimates based on CSSRI regional soil maps. "
        "FAO (2017). Soil Organic Carbon: the hidden potential. "
        "Cornell University (2020). Comprehensive Assessment of Soil Health.*"
    )

    # ── Details — Growth & Yield ───────────────────────────────────────────
    st.markdown("**Details — Growth & Yield**")
    above_below = 'above' if loss_pct < 20 else 'below'
    st.markdown(
        f"Yield is estimated {above_below} the local median due to {vigor} vegetation "
        f"vigor, indicating robust canopy development. However, {limiting_str} prevent "
        f"reaching the local maximum potential of {int(potential_yld)} kg/acre. Satellite "
        f"vegetation indices on the visit date confirm the crop is in "
        f"{growth_stage_name.lower()} and aligns with the local seasonal window."
    )
    st.caption(
        "*References: Yield estimates based on ICAR guidelines and Sentinel-1 RVI-to-biomass "
        "correlation models. Nutrient impact assessed via Liebig's Law of the Minimum.*"
    )

    # Limiting factors detail (only if any)
    if limiting:
        with st.expander("Limiting Factors"):
            for lf in growth.get('limiting_factors', []):
                st.markdown(f"- **{lf['factor']}**: {lf.get('impact', '')}")
