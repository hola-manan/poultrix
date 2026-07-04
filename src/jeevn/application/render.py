"""
Human-readable rendering of alerts and advisories.

Kept deliberately transport-agnostic: these functions produce short plain-text
strings that Part-2 delivery (SMS / WhatsApp) can send verbatim, and that the
`ConsoleNotifier` prints today.
"""

from typing import Any, Dict, List

from .alerts import Alert

_SEVERITY_ICON = {
    "urgent": "🚨",
    "alert": "⚠️",
    "watch": "🟡",
    "info": "ℹ️",
}


def render_alert(alert: Alert) -> str:
    """One-line-ish rendering of a single alert, suitable for SMS/WhatsApp."""
    icon = _SEVERITY_ICON.get(alert.severity, "•")
    return f"{icon} {alert.title}\n{alert.message}"


def render_alerts(alerts: List[Alert]) -> str:
    if not alerts:
        return "✅ No advisories right now — conditions are within normal range."
    return "\n\n".join(render_alert(a) for a in alerts)


def render_advisory(advisory: Dict[str, Any]) -> str:
    """A compact multi-section digest of a full advisory result."""
    lines: List[str] = []
    loc = advisory.get("location", "")
    crop = advisory.get("crop", "")
    header = "Agricultural advisory"
    if crop or loc:
        header += f" — {crop}{' @ ' + loc if loc else ''}"
    lines.append(header)

    ds = advisory.get("dry_spell")
    if ds is not None:
        if getattr(ds, "data_gap", False):
            lines.append("• Weather data unavailable — dry-spell check skipped.")
        elif ds.is_dry_spell:
            lines.append(f"• Dry spell: {ds.dry_days} consecutive dry days.")
        else:
            lines.append(f"• No dry spell ({ds.dry_days} dry days so far).")

    irrig = (advisory.get("report", {}).get("components", {})
             .get("irrigation_schedule", {}))
    if irrig:
        lines.append(
            f"• Irrigation: {irrig.get('total_water_mm', 0)} mm over "
            f"{irrig.get('irrigation_days', 0)} day(s); best time "
            f"{irrig.get('best_time', '05:00-08:00')}."
        )

    alerts = advisory.get("alerts", [])
    lines.append("")
    lines.append(render_alerts(alerts))
    return "\n".join(lines)
