"""
Section 5 of the report: pest / disease / weed threat table + pest narrative
+ weed narrative + references. Mirrors PDF page 4.
"""

import streamlit as st
import pandas as pd


def render(components: dict, *, location: str, vigor: str = "good"):
    st.header("5.  Pest, Disease & Weed Management")

    if not components:
        st.info("Pest, disease & weed data not available.")
        return

    threats = (components.get('pests_diseases', []) +
               components.get('weeds', []))
    threats.sort(key=lambda x: x.get('risk_percent', 0), reverse=True)

    summ = components.get('summary', {})
    high = summ.get('high_risk_count', 0)
    mod = summ.get('moderate_risk_count', 0)
    low = summ.get('low_risk_count', 0)
    st.markdown(
        f"**High Risk:** {high} | **Moderate Risk:** {mod} | **Low Risk:** {low}"
    )

    if not threats:
        st.info("No pest/disease/weed threats detected.")
    else:
        rows = []
        for t in threats:
            rp = t.get('risk_percent', 0)
            rp_str = f"{rp:.0f}%" if isinstance(rp, (int, float)) else str(rp)
            rows.append({
                "Name": t.get('name', ''),
                "Category": (t.get('category') or '').title(),
                "Risk %": rp_str,
                "Risk Level": (t.get('risk_level') or 'low').title(),
                "Organic Solution": t.get('organic_solution', '—'),
                "Chemical Solution": t.get('chemical_solution', '—'),
            })
        df = pd.DataFrame(rows)

        def _highlight_risk(val):
            colours = {'High': 'background-color:#ffcdd2',
                       'Moderate': 'background-color:#fff9c4',
                       'Low': 'background-color:#e8f5e9'}
            return colours.get(val, '')

        styled = df.style.applymap(_highlight_risk, subset=['Risk Level'])
        st.dataframe(styled, use_container_width=True, hide_index=True)

    env_cond = components.get('environmental_conditions', {})
    temp_mean = env_cond.get('temperature', 30)
    humidity_est = env_cond.get('humidity_estimate', 60)
    rsm_val = env_cond.get('rsm', 0.72)
    gs_pest = (env_cond.get('growth_stage') or 'growth').replace('_', ' ')

    # ── Details — Pest & Disease ───────────────────────────────────────────
    st.markdown("**Details — Pest & Disease**")
    st.markdown(
        f"High canopy density ({vigor} vegetation vigor) creates a humid microclimate "
        f"conducive to fungal diseases. Rising {location} temperatures ({temp_mean:.0f}°C "
        f"mean) accelerate pest life cycles, while {humidity_est:.0f}% estimated humidity "
        f"increases susceptibility to leaf-spot diseases during the sensitive {gs_pest} "
        "period."
    )
    st.caption(
        "*References: Based on ICAR-CITH crop phenology guidelines and regional pest "
        "alerts. Satellite RVI/RSM correlations derived from Sentinel-1 SAR indices for "
        "biomass monitoring.*"
    )

    # ── Details — Weed ─────────────────────────────────────────────────────
    st.markdown("**Details — Weed**")
    st.markdown(
        f"High soil moisture (RSM {rsm_val:.2f}) suggests recent irrigation or high "
        "retention, which promotes weed germination in tree basins. Although the high "
        "vegetation index indicates good canopy closure, any light penetration on the "
        "plantation floor will trigger rapid weed growth. The semi-arid climate "
        "facilitates weed competition for nutrients during the critical fruit-set "
        f"transition following {gs_pest}."
    )
    st.caption(
        "*References: Weed risk assessed via Indian Society of Weed Science (ISWS) "
        "orchard management protocols and local irrigation–weed-growth correlations.*"
    )
