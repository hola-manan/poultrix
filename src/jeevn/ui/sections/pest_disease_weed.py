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
    humidity_is_est = env_cond.get('humidity_estimated', True)
    humidity_label = "Humidity (est.)" if humidity_is_est else "Humidity"
    humidity_word = "estimated humidity" if humidity_is_est else "measured humidity"
    rsm_val = env_cond.get('rsm', 0.72)
    rsm_source = env_cond.get('rsm_source') or 'fabricated'
    rsm_pass_date = env_cond.get('rsm_pass_date')
    gs_pest = (env_cond.get('growth_stage') or 'growth').replace('_', ' ')

    # Source attribution shared between the RSM chip and the references caption.
    rsm_source_label = {
        "nisar-sme2": f"NISAR L-band (pass {rsm_pass_date})" if rsm_pass_date else "NISAR L-band",
        "open-meteo": "Open-Meteo modelled SM",
        "fabricated": "Pending real source",
    }.get(rsm_source, rsm_source)

    # ── Metric chips: Temperature / Humidity / RSM ────────────────────────
    # RSM was previously buried inline in the weed paragraph. The chip
    # surfaces both the value and its source — value alone is misleading
    # because today it usually comes from Open-Meteo (NISAR dormant).
    m1, m2, m3 = st.columns(3)
    m1.metric("Temperature", f"{temp_mean:.0f} °C")
    m2.metric(humidity_label, f"{humidity_est:.0f}%")
    m3.metric(
        "RSM (soil moisture)", f"{rsm_val:.2f}",
        delta=rsm_source_label, delta_color="off",
    )

    # ── Details — Pest & Disease ───────────────────────────────────────────
    st.markdown("**Details — Pest & Disease**")
    st.markdown(
        f"High canopy density ({vigor} vegetation vigor) creates a humid microclimate "
        f"conducive to fungal diseases. Rising {location} temperatures ({temp_mean:.0f}°C "
        f"mean) accelerate pest life cycles, while {humidity_est:.0f}% {humidity_word} "
        f"increases susceptibility to leaf-spot diseases during the sensitive {gs_pest} "
        "period."
    )

    # Weather-driven disease models (grape): surface the Gubler powdery-mildew
    # index + spray interval and the hedged downy-mildew wet-period flag so the
    # farmer sees the reasoning, not just a percentage.
    model_dx = [t for t in components.get('pests_diseases', []) if t.get('model')]
    if model_dx:
        st.markdown("**Disease risk models**")
        for d in model_dx:
            if d.get('model') == 'gubler_powdery':
                st.markdown(
                    f"- **{d['name']}** — Gubler-Thomas index "
                    f"**{d.get('risk_percent', 0):.0f}/100** "
                    f"({(d.get('risk_level') or '').title()}). Suggested spray "
                    f"interval ≈ **{d.get('spray_interval_days', '—')} days**. "
                    f"{d.get('rationale', '')}"
                )
            elif d.get('model') == 'downy_wet_period':
                st.markdown(
                    f"- **{d['name']}** — "
                    f"{'FAVORABLE' if d.get('favorable') else 'not favorable'} "
                    f"({(d.get('risk_level') or '').title()} risk, "
                    f"{d.get('confidence', 'regional-proxy')}). "
                    f"{d.get('rationale', '')}"
                )
    # Source-aware references. RVI is always Sentinel-1 (real) per task #10.
    # RSM source varies — quote it accurately rather than the old hardcoded
    # "Sentinel-1 SAR indices" line.
    rsm_ref = {
        "nisar-sme2": f"RSM from NISAR L-band SME2 pass {rsm_pass_date or ''}".rstrip(),
        "open-meteo": "RSM from Open-Meteo modelled surface soil moisture (NISAR dormant)",
        "fabricated": "RSM is a fabricated default — no real source available",
    }.get(rsm_source, f"RSM source: {rsm_source}")
    st.caption(
        "*References: Based on ICAR-CITH crop phenology guidelines and regional pest "
        f"alerts. RVI from Sentinel-1 RTC (γ⁰ backscatter, Horn formula). {rsm_ref}.*"
    )

    # ── Details — Weed ─────────────────────────────────────────────────────
    st.markdown("**Details — Weed**")
    st.markdown(
        f"High soil moisture (RSM {rsm_val:.2f}, {rsm_source_label}) suggests recent "
        "irrigation or high retention, which promotes weed germination in tree basins. "
        "Although the high vegetation index indicates good canopy closure, any light "
        "penetration on the plantation floor will trigger rapid weed growth. The "
        "semi-arid climate facilitates weed competition for nutrients during the "
        f"critical fruit-set transition following {gs_pest}."
    )
    st.caption(
        "*References: Weed risk assessed via Indian Society of Weed Science (ISWS) "
        "orchard management protocols and local irrigation–weed-growth correlations.*"
    )
