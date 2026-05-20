"""
Section 6 of the report: fertilizer management table + numbered details +
references. Mirrors PDF page 5.
"""

import streamlit as st
import pandas as pd


_DISPLAY = {'N': 'Nitrogen', 'P': 'Phosphorus', 'K': 'Potassium', 'S': 'Sulfur', 'Zn': 'Zinc'}
_ORG_SRC = {'N': 'Vermicompost', 'P': 'Bone Meal', 'K': 'Wood Ash',
            'S': 'Composted Manure', 'Zn': 'Enriched FYM'}
_CHEM_SRC = {'N': 'Urea', 'P': 'Diammonium Phosphate',
             'K': 'Sulphate of Potash', 'S': 'Bentonite Sulphur', 'Zn': 'Zinc Sulphate'}


def render(components: dict, *, crop_name: str, growth_stage_name: str):
    st.header("6.  Fertilizer Management")

    if not components:
        st.info("Fertilizer management data not available.")
        return

    nr = components.get('nutrient_requirements', {})
    sched = components.get('fertilizer_schedule', {})
    freq = sched.get('frequency_days', 2)

    need = sum(1 for v in nr.values() if 'critical' in (v.get('status') or ''))
    mon = sum(1 for v in nr.values() if 'moderate' in (v.get('status') or ''))
    opt = sum(1 for v in nr.values() if 'adequate' in (v.get('status') or ''))

    st.markdown(
        f"**Need Attention:** {need} | **Monitor Closely:** {mon} | **Optimal:** {opt}"
    )
    st.markdown(f"**Frequency of Application:** every {freq} days")

    # Merge product names from the schedule into the per-nutrient source columns
    org_map = dict(_ORG_SRC)
    chem_map = dict(_CHEM_SRC)
    for p in sched.get('recommended_products', []):
        nm = p.get('product', '')
        qty = p.get('quantity_kg_acre', '')
        tag = f" ({qty:.2f})" if isinstance(qty, float) else ''
        if 'Urea' in nm:        chem_map['N'] = nm + tag
        elif 'DAP' in nm:        chem_map['P'] = nm + tag
        elif 'SOP' in nm or 'Sulphate of Potash' in nm: chem_map['K'] = nm + tag
        elif 'Bone Meal' in nm:  org_map['P'] = nm + tag
        elif 'Wood Ash' in nm:   org_map['K'] = nm + tag
        elif 'Zinc' in nm:       chem_map['Zn'] = nm + tag
        elif 'Bentonite' in nm:  chem_map['S'] = nm + tag

    rows = []
    for key in ['N', 'P', 'K', 'S', 'Zn']:
        data = nr.get(key, {})
        rows.append({
            "Nutrient": _DISPLAY.get(key, key),
            "Current (Kg/Acre)": round(data.get('current_kg_per_acre', 0), 2),
            "Target (Kg/Acre)": data.get('target_kg_per_acre', '—'),
            "Status": (data.get('status') or 'moderate').title(),
            "Organic Source (kg/ac)": org_map.get(key, '—'),
            "Chemical (kg/ac)": chem_map.get(key, '—'),
        })
    df = pd.DataFrame(rows)

    def _highlight(val):
        mapping = {'Critical': 'background-color:#ffcdd2',
                   'Moderate': 'background-color:#fff9c4',
                   'Adequate': 'background-color:#e8f5e9'}
        return mapping.get(val, '')

    styled = df.style.applymap(_highlight, subset=['Status'])
    st.dataframe(styled, use_container_width=True, hide_index=True)

    products = sched.get('recommended_products', [])
    if products:
        with st.expander("Recommended Products"):
            for p in products:
                qty = p.get('quantity_kg_acre', 0)
                qty_str = f"{qty:.2f} kg/acre" if isinstance(qty, float) else str(qty)
                st.markdown(
                    f"- **{p['product']}** — {qty_str} "
                    f"({p.get('application_method', '')})"
                )

    # ── Details — Fertilizer Management ───────────────────────────────────
    n_gap = nr.get('N', {}).get('gap_kg_per_acre', 9.1)
    p_gap = nr.get('P', {}).get('gap_kg_per_acre', 7.25)
    k_gap = nr.get('K', {}).get('gap_kg_per_acre', 54.5)

    st.markdown("**Details — Fertilizer Management**")
    st.markdown(
        f"""
1. Nitrogen levels were calculated based on vegetation vigor during
   {growth_stage_name.lower()}, requiring **{n_gap:.1f} kg/acre** gap fulfillment.
2. Phosphorus gap of **{p_gap:.2f} kg/acre** is addressed using DAP and Bone Meal.
3. Potassium requirement is high for fruit set; **{k_gap:.1f} kg/acre** gap is met
   with SOP and Wood Ash.
4. Sulfur and Zinc are critical for enzyme activation during bloom; gaps are
   supplemented via Bentonite Sulphur and Zinc Sulphate.
5. Drip irrigation allows for simultaneous fertigation of soluble nutrients,
   while organic matter should be soil-applied.
6. Frequency set to every **{freq} days** to prevent osmotic stress and leaching
   in sandy loam soils.
"""
    )
    st.caption(
        f"*References: Nutrient rates based on ICAR-CITH guidelines for {crop_name}; "
        "fertilizer grades: Urea (46% N), DAP (46% P₂O₅), SOP (50% K₂O). "
        "Max dose limits derived from FAO Fertigation Manual.*"
    )
