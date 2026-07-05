"""
Alert model + builder for the real-time advisory layer.

`build_alerts` turns a full advisory report + dry-spell verdict + soil-water
deficit into a small list of actionable `Alert`s. Only genuinely data-driven
signals raise alerts; fertilizer *dose* numbers are confidence-gated so a
placeholder-derived dose never pages a farmer (see `docstring` of
`data_sources/soil_nutrients.py`).
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from jeevn.domain.dry_spell import DrySpellResult

# Severity ranking for sorting / gating.
_SEVERITY_ORDER = {"urgent": 3, "alert": 2, "watch": 1, "info": 0}
_ALERTING_CONFIDENCE = {"high", "medium"}


@dataclass
class Alert:
    severity: str  # "urgent" | "alert" | "watch" | "info"
    kind: str      # machine slug, e.g. "dry_spell"
    title: str
    message: str
    data: Dict[str, Any] = field(default_factory=dict)

    @property
    def rank(self) -> int:
        return _SEVERITY_ORDER.get(self.severity, 0)


def build_alerts(report: Dict[str, Any],
                 dry_spell: DrySpellResult,
                 deficit_mm: Optional[float],
                 leach_rain_48h_mm: Optional[float],
                 *,
                 crop: str = "",
                 location: str = "",
                 leach_threshold_mm: float = 15.0,
                 salinity_ec_threshold: float = 1.5) -> List[Alert]:
    alerts: List[Alert] = []
    where = f" at {location}" if location else ""
    crop_label = crop or "crop"

    # ── Dry spell (genuine: real recent + forecast rainfall) ────────────────
    if dry_spell.is_dry_spell:
        alerts.append(Alert(
            severity=dry_spell.severity,  # "alert" or "urgent"
            kind="dry_spell",
            title=f"Dry spell — {dry_spell.dry_days} days",
            message=(
                f"Dry spell for your {crop_label}{where}: "
                + "; ".join(dry_spell.reasons)
                + ". Plan irrigation to avoid moisture stress."
            ),
            data={
                "dry_days": dry_spell.dry_days,
                "recent_dry_run": dry_spell.recent_dry_run,
                "forecast_dry_run": dry_spell.forecast_dry_run,
            },
        ))

    # ── Irrigate now (genuine: soil-water deficit from fused moisture) ───────
    irrig = report.get("components", {}).get("irrigation_schedule", {})
    if deficit_mm is not None and deficit_mm > 0:
        severity = "urgent" if deficit_mm >= 15 else "alert"
        alerts.append(Alert(
            severity=severity,
            kind="irrigate_now",
            title=f"Irrigate now — {deficit_mm:.0f} mm deficit",
            message=(
                f"Soil-water deficit of {deficit_mm:.0f} mm on your {crop_label}"
                f"{where}. Apply ~{deficit_mm:.0f} mm "
                f"(best time {irrig.get('best_time', '05:00-08:00')})."
            ),
            data={"deficit_mm": round(deficit_mm, 1)},
        ))

    # ── Hold fertigation (genuine: real forecast rain → leaching risk) ──────
    if leach_rain_48h_mm is not None and leach_rain_48h_mm >= leach_threshold_mm:
        alerts.append(Alert(
            severity="watch",
            kind="hold_fertigation",
            title="Hold fertigation — rain forecast",
            message=(
                f"{leach_rain_48h_mm:.0f} mm rain forecast in the next 48 h"
                f"{where}. Delay fertigation to avoid nutrient leaching; "
                "resume once heavy rain has passed."
            ),
            data={"forecast_rain_48h_mm": round(leach_rain_48h_mm, 1)},
        ))

    # ── High salinity (genuine: real ISRIC EC where covered) ────────────────
    ec = report.get("environmental_context", {}).get("soil", {}).get(
        "properties", {}).get("ec")
    if isinstance(ec, (int, float)) and ec > salinity_ec_threshold:
        alerts.append(Alert(
            severity="watch",
            kind="high_salinity",
            title=f"High soil salinity — EC {ec:.1f} dS/m",
            message=(
                f"Soil EC {ec:.1f} dS/m{where} exceeds {salinity_ec_threshold} "
                "dS/m. Reduce fertiliser concentration and prefer split "
                "fertigation to limit osmotic stress."
            ),
            data={"ec_ds_m": ec},
        ))

    # ── Fertiliser dose advisory (confidence-gated, never from placeholders) ─
    fert = report.get("components", {}).get("fertilizer_management", {})
    reqs = fert.get("nutrient_requirements", {})
    actionable = {
        n: r for n, r in reqs.items()
        if r.get("gap_kg_per_acre", 0) > 0
        and r.get("confidence") in _ALERTING_CONFIDENCE
    }
    if actionable:
        parts = [f"{n} {r['gap_kg_per_acre']:.1f} kg/acre" for n, r in actionable.items()]
        src = sorted({r.get("source", "estimate") for r in actionable.values()})
        alerts.append(Alert(
            severity="info",
            kind="fertilize",
            title="Fertiliser recommendation",
            message=(
                f"Estimated nutrient gap for your {crop_label}{where}: "
                + ", ".join(parts)
                + f" (based on {', '.join(src)} soil data)."
            ),
            data={"nutrients": actionable},
        ))

    alerts.sort(key=lambda a: a.rank, reverse=True)
    return alerts
