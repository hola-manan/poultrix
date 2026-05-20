"""
Section 3 of the report: irrigation schedule table + calculation note +
narrative + references. Mirrors PDF page 2.
"""

import streamlit as st
import pandas as pd


def render(components: dict, *, crop_name: str, location: str, lat: float,
           growth_stage_name: str):
    st.header("3.  Irrigation Schedule")

    if not components:
        st.info("Irrigation schedule data not available.")
        return

    total_water = components.get('total_water_mm', 0)
    irr_days = components.get('irrigation_days', 0)
    best_time = components.get('best_time', '05:00-08:00')
    et0 = components.get('et0_mm_per_day', 6.5)
    kc = components.get('kc', 0.95)
    daily = components.get('daily_schedule', [])

    st.markdown(
        f"**Total Water:** {total_water} mm | "
        f"**Irrigation Days:** {irr_days} | "
        f"**Best Time:** {best_time} | **Units:** mm"
    )

    if daily:
        rows = []
        for d in daily:
            drip = d.get('drip_mm', 0)
            rows.append({
                "Date": d.get('date', ''),
                "Drip (mm)": drip,
                "Basin (mm)": d.get('basin_mm', drip),
                "Sprinkler (mm)": d.get('sprinkler_mm', drip),
                "Rainfall": d.get('rainfall', '0 mm'),
                "Rain %": d.get('rain_percent', '0%'),
                "Evapotransp.": d.get('evapotransp', 'Moderate'),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("No daily schedule data available.")

    # Calculation note box (matches PDF Page 2 note)
    st.info(
        "**Irrigation Calculation Note:**  \n"
        "Irrigation Time required = (Irrigation Quantity in mm × Area covered by emitter "
        "in m²) / Flow rate of emitter.  \n"
        "**Example:** Quantity = 8 mm, Emitter area = 0.4 m², Flow = 2 L/hr → "
        "Time = (8 × 0.4) / 2 = 1.6 hours"
    )

    # ── Details — Irrigation ──────────────────────────────────────────────
    st.markdown("**Details — Irrigation**")
    st.markdown(
        f"{crop_name} is in {growth_stage_name.lower()}, requiring consistent moisture "
        f"for fruit set. ET0 was estimated at {et0:.0f}–{et0+1:.0f} mm due to "
        f"{location}'s seasonal temperatures. Baseline Kc ({kc:.2f}) was adjusted for "
        f"heat stress and high evapotranspiration. {irr_days} events are scheduled; "
        "alternate days maintain soil moisture without saturation."
    )
    st.caption(
        f"*References: ET0 calculated via Hargreaves-Samani for lat {lat}°N. "
        f"Kc values sourced from FAO-56 for {crop_name.lower()} cultivation. "
        "Local climate data informs heat-stress adjustments.*"
    )
