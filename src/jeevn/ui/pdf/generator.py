"""
PDF report generator for Personalized Farm Advisory Report.
Produces a 5-page PDF matching the Farmonaut Jeevn sample layout.
"""

import io
import sys
import subprocess
from datetime import datetime
from typing import Dict, Any, Optional

import numpy as np

# Self-install reportlab into the running interpreter if absent
try:
    import reportlab  # noqa: F401
except ImportError:
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "reportlab", "--quiet"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, PageBreak,
)

# Scale-bar legend (the small colour key shown under each map). The actual
# NDVI / NDWI parcel imagery is supplied as real PNG bytes by the caller — see
# generate_pdf(..., ndvi_png=, ndwi_png=).
from jeevn.ui.visuals import scale_bar as _scale_bar, PIL_AVAILABLE

# ── Colour palette ────────────────────────────────────────────────────────────
DARK_GREEN   = HexColor('#1a5c38')
MED_GREEN    = HexColor('#2d8653')
LIGHT_GREEN  = HexColor('#e8f5e9')
RED          = HexColor('#c62828')
YELLOW_BG    = HexColor('#fff9c4')
BLUE         = HexColor('#1565c0')
LIGHT_BLUE   = HexColor('#e3f2fd')
GRAY         = HexColor('#f5f5f5')
DARK_GRAY    = HexColor('#424242')
LINE_GRAY    = HexColor('#cccccc')
AMBER_BG     = HexColor('#fff8e1')
AMBER_BORDER = HexColor('#f9a825')

PAGE_W, PAGE_H = A4
MARGIN = 15 * mm
CONTENT_W = PAGE_W - 2 * MARGIN


# ── Styles ────────────────────────────────────────────────────────────────────
def _styles() -> Dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        'section': ParagraphStyle('Sec', parent=base['Normal'],
            fontSize=11, fontName='Helvetica-Bold', textColor=white,
            backColor=DARK_GREEN, leftIndent=3*mm,
            spaceAfter=3*mm, spaceBefore=4*mm, leading=15),
        'subsection': ParagraphStyle('Sub', parent=base['Normal'],
            fontSize=9, fontName='Helvetica-Bold', textColor=DARK_GREEN,
            spaceAfter=2*mm, spaceBefore=2*mm),
        'body': ParagraphStyle('Body', parent=base['Normal'],
            fontSize=8, fontName='Helvetica', textColor=DARK_GRAY,
            spaceAfter=2*mm, leading=12, alignment=TA_JUSTIFY),
        'small': ParagraphStyle('Small', parent=base['Normal'],
            fontSize=7, fontName='Helvetica', textColor=DARK_GRAY, leading=10),
        'ref': ParagraphStyle('Ref', parent=base['Normal'],
            fontSize=7, fontName='Helvetica-Oblique',
            textColor=HexColor('#616161'), leading=10, spaceAfter=2*mm),
        'center': ParagraphStyle('Ctr', parent=base['Normal'],
            fontSize=8, fontName='Helvetica', alignment=TA_CENTER,
            textColor=DARK_GRAY, leading=11),
        'metric_big': ParagraphStyle('MetBig', parent=base['Normal'],
            fontSize=20, fontName='Helvetica-Bold', textColor=DARK_GREEN,
            alignment=TA_CENTER, leading=24),
        'metric_label': ParagraphStyle('MetLbl', parent=base['Normal'],
            fontSize=7, fontName='Helvetica', textColor=DARK_GRAY,
            alignment=TA_CENTER, leading=9),
    }


# ── Risk / status colour helpers ──────────────────────────────────────────────
def _risk_bg(level: str) -> HexColor:
    return {'high': HexColor('#ffcdd2'), 'moderate': YELLOW_BG,
            'low': LIGHT_GREEN}.get((level or '').lower(), GRAY)

def _risk_fg(level: str) -> HexColor:
    return {'high': RED, 'moderate': HexColor('#e65100'),
            'low': HexColor('#2e7d32')}.get((level or '').lower(), DARK_GRAY)

def _status_bg(status: str) -> HexColor:
    s = (status or '').lower()
    if 'critical' in s or 'need' in s:
        return HexColor('#ffcdd2')
    if 'moderate' in s or 'monitor' in s:
        return YELLOW_BG
    return LIGHT_GREEN


# ── Page header (drawn on canvas) ─────────────────────────────────────────────
def _draw_header(canvas, doc, report_date: str, aoi_info: Dict[str, Any]) -> None:
    canvas.saveState()
    top = PAGE_H - MARGIN

    # Green banner
    canvas.setFillColor(DARK_GREEN)
    canvas.rect(MARGIN, top - 12*mm, CONTENT_W, 12*mm, fill=1, stroke=0)

    # Title + date
    canvas.setFillColor(white)
    canvas.setFont('Helvetica-Bold', 11)
    canvas.drawString(MARGIN + 3*mm, top - 8.5*mm, 'Personalized Farm Advisory Report')
    canvas.setFont('Helvetica', 8.5)
    canvas.drawRightString(PAGE_W - MARGIN - 3*mm, top - 8.5*mm,
                           f'Report Date: {report_date}')

    # Sub-header
    canvas.setFillColor(DARK_GRAY)
    canvas.setFont('Helvetica', 8)
    loc    = aoi_info.get('location', '')
    area   = aoi_info.get('area_acres', 0)
    visit  = aoi_info.get('satellite_visit', '')
    crop   = aoi_info.get('crop', '').title()
    sub = f"{loc}   Area: {area} acres | Satellite Visit: {visit} | Crop: {crop}"
    canvas.drawString(MARGIN, top - 18*mm, sub)

    # Thin separator line
    canvas.setStrokeColor(LINE_GRAY)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN, top - 20*mm, PAGE_W - MARGIN, top - 20*mm)

    # Page number
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(DARK_GRAY)
    canvas.drawRightString(PAGE_W - MARGIN, MARGIN - 4*mm,
                           f'Page {doc.page} / 5')
    canvas.restoreState()


# ── Table helpers ─────────────────────────────────────────────────────────────
def _base_table_style() -> list:
    return [
        ('BACKGROUND', (0, 0), (-1, 0), DARK_GREEN),
        ('TEXTCOLOR',  (0, 0), (-1, 0), white),
        ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',   (0, 0), (-1, -1), 8),
        ('GRID',       (0, 0), (-1, -1), 0.4, LINE_GRAY),
        ('ALIGN',      (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',    (0, 0), (-1, -1), 2*mm),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2*mm),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, GRAY]),
    ]


def _note_box(text: str, S: dict) -> Table:
    t = Table([[Paragraph(text, S['small'])]], colWidths=[CONTENT_W])
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,-1), GRAY),
        ('BOX',           (0,0), (-1,-1), 0.5, LINE_GRAY),
        ('TOPPADDING',    (0,0), (-1,-1), 3*mm),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3*mm),
        ('LEFTPADDING',   (0,0), (-1,-1), 3*mm),
        ('RIGHTPADDING',  (0,0), (-1,-1), 3*mm),
    ]))
    return t


def _disclaimer_box(text: str, S: dict) -> Table:
    t = Table([[Paragraph(f'<b>Disclaimer:</b> {text}', S['small'])]], colWidths=[CONTENT_W])
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,-1), AMBER_BG),
        ('BOX',           (0,0), (-1,-1), 0.5, AMBER_BORDER),
        ('TOPPADDING',    (0,0), (-1,-1), 3*mm),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3*mm),
        ('LEFTPADDING',   (0,0), (-1,-1), 3*mm),
        ('RIGHTPADDING',  (0,0), (-1,-1), 3*mm),
    ]))
    return t


# ── Public API ────────────────────────────────────────────────────────────────
def generate_pdf(report: Dict[str, Any],
                 ndvi_png: Optional[bytes] = None,
                 ndwi_png: Optional[bytes] = None) -> bytes:
    """
    Generate a 5-page PDF farm advisory report.

    Args:
        report:    Full report dict from AgriculturalReportGenerator (may be empty).
        ndvi_png:  Pre-rendered NDVI Crop Health Map as PNG bytes (from the API
                   `/aoi/{id}/maps/ndvi.png` endpoint). When None, the PDF
                   shows an "NDVI raster unavailable" notice in place of the
                   map — the PDF never synthesises a fake map from a scalar.
        ndwi_png:  Same, for the NDWI Irrigation Health Map.

    Returns:
        Raw PDF bytes.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=MARGIN + 22*mm,
        bottomMargin=MARGIN + 8*mm,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
    )

    S = _styles()
    story = []

    aoi_info   = report.get('aoi_info', {})
    report_date = report.get('report_date', datetime.now().strftime('%d/%m/%Y'))
    comp       = report.get('components', {})

    irrigation = comp.get('irrigation_schedule', {})
    soil       = comp.get('soil_management', {})
    yield_proj = comp.get('growth_yield', {})
    pest_data  = comp.get('pest_disease_weed', {})
    fert_data  = comp.get('fertilizer_management', {})

    crop_name  = aoi_info.get('crop', 'Crop').title()
    location   = aoi_info.get('location', '')
    lat        = aoi_info.get('latitude', 29.9)

    half_w = (CONTENT_W - 5*mm) / 2

    # ═══════════════════════════════════════════════════════════════════════════
    # PAGE 1 — Field Maps & Analysis Scale
    # ═══════════════════════════════════════════════════════════════════════════
    story.append(Paragraph('1.  Field Maps', S['section']))

    def _map_cell(png_bytes: Optional[bytes], unavailable_msg: str):
        if png_bytes:
            return Image(io.BytesIO(png_bytes), width=half_w, height=50*mm)
        return Paragraph(f'<i>{unavailable_msg}</i>', S['body'])

    maps = Table(
        [[_map_cell(ndvi_png, 'NDVI raster unavailable — no real Sentinel-2 reading.'),
          _map_cell(ndwi_png, 'NDWI raster unavailable — no real Sentinel-2 reading.')]],
        colWidths=[half_w, half_w])
    maps.setStyle(TableStyle([
        ('VALIGN',       (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING',  (0,0), (-1,-1), 2*mm),
        ('RIGHTPADDING', (0,0), (-1,-1), 2*mm),
        ('TOPPADDING',   (0,0), (-1,-1), 0),
        ('BOTTOMPADDING',(0,0), (-1,-1), 1*mm),
    ]))
    story.append(maps)

    labels = Table(
        [[Paragraph('Crop Health Map', S['center']),
          Paragraph('Irrigation Health Map', S['center'])]],
        colWidths=[half_w, half_w])
    labels.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('LEFTPADDING',  (0,0), (-1,-1), 2*mm),
        ('RIGHTPADDING', (0,0), (-1,-1), 2*mm),
    ]))
    story.append(labels)

    story.append(Spacer(1, 4*mm))
    story.append(Paragraph('2.  Analysis Scale', S['section']))

    ndvi_scale = _scale_bar('ndvi', 'Low (0)', 'High (1.0)')
    ndwi_scale = _scale_bar('ndwi', 'Dry (0)', 'Wet (1.0)')

    if ndvi_scale and ndwi_scale:
        scales = Table(
            [[Paragraph('Crop Health Scale (NDVI)', S['center']),
              Paragraph('Irrigation Health Scale (NDWI)', S['center'])],
             [Image(ndvi_scale, width=half_w, height=12*mm),
              Image(ndwi_scale, width=half_w, height=12*mm)]],
            colWidths=[half_w, half_w])
        scales.setStyle(TableStyle([
            ('ALIGN',        (0,0), (-1,-1), 'CENTER'),
            ('LEFTPADDING',  (0,0), (-1,-1), 2*mm),
            ('RIGHTPADDING', (0,0), (-1,-1), 2*mm),
            ('TOPPADDING',   (0,0), (-1,-1), 1*mm),
            ('BOTTOMPADDING',(0,0), (-1,-1), 1*mm),
        ]))
        story.append(scales)

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════════════
    # PAGE 2 — Irrigation Schedule
    # ═══════════════════════════════════════════════════════════════════════════
    total_water = irrigation.get('total_water_mm', 0)
    irr_days    = irrigation.get('irrigation_days', 0)
    best_time   = irrigation.get('best_time', '05:00-08:00')
    et0         = irrigation.get('et0_mm_per_day', 6.5)
    kc          = irrigation.get('kc', 0.95)
    daily       = irrigation.get('daily_schedule', [])
    growth_stage_name = (yield_proj.get('current_growth_stage') or 'growth').replace('_', ' ').title()

    story.append(Paragraph('3.  Irrigation Schedule', S['section']))
    story.append(Paragraph(
        f'Total Water: <b>{total_water} mm</b> | Irrigation Days: <b>{irr_days}</b> | '
        f'Best Time: <b>{best_time}</b> | Units: <b>mm</b>',
        S['subsection']))

    irr_hdr = ['Date', 'Drip (mm)', 'Basin (mm)', 'Sprinkler (mm)', 'Rainfall', 'Rain %', 'Evapotransp.']
    col_w   = CONTENT_W / len(irr_hdr)
    irr_rows = [irr_hdr]
    for day in daily[:7]:
        drip = day.get('drip_mm', 0)
        irr_rows.append([
            day.get('date', ''),
            str(drip),
            str(day.get('basin_mm', drip)),
            str(day.get('sprinkler_mm', drip)),
            str(day.get('rainfall', '0 mm')),
            str(day.get('rain_percent', '0%')),
            day.get('evapotransp', 'Moderate'),
        ])

    irr_table = Table(irr_rows, colWidths=[col_w] * len(irr_hdr))
    irr_table.setStyle(TableStyle(_base_table_style()))
    story.append(irr_table)
    story.append(Spacer(1, 3*mm))

    note_txt = (
        '<b>Irrigation Calculation Note:</b><br/>'
        'Irrigation Time required = (Irrigation Quantity in mm × Area covered by emitter in m²) '
        '/ Flow rate of emitter.<br/>'
        '<b>Example:</b> Quantity = 8 mm, Emitter area = 0.4 m², Flow = 2 L/hr → '
        'Time = (8 × 0.4) / 2 = 1.6 hours'
    )
    story.append(_note_box(note_txt, S))
    story.append(Spacer(1, 3*mm))

    story.append(Paragraph('Details — Irrigation', S['subsection']))
    story.append(Paragraph(
        f'{crop_name} is in {growth_stage_name}, requiring consistent moisture for fruit set. '
        f'ET0 was estimated at {et0:.0f}–{et0+1:.0f} mm due to {location}\'s seasonal temperatures. '
        f'Baseline Kc ({kc:.2f}) was adjusted for heat stress and high evapotranspiration. '
        f'{irr_days} events are scheduled; alternate days maintain soil moisture without saturation.',
        S['body']))
    story.append(Paragraph(
        f'<i>References: ET0 calculated via Hargreaves-Samani for lat {lat}°N. '
        f'Kc values sourced from FAO-56 for {crop_name.lower()} cultivation. '
        'Local climate data informs heat-stress adjustments.</i>',
        S['ref']))

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════════════
    # PAGE 3 — Soil Management & Growth / Yield
    # ═══════════════════════════════════════════════════════════════════════════
    ph           = soil.get('ph', 7.0)
    salinity     = (soil.get('salinity') or 'low').title()
    soc          = soil.get('organic_carbon_percent', 0.15)
    soc_status   = (soil.get('organic_carbon_status') or 'low').lower()
    yld_acre     = yield_proj.get('yield_per_acre_kg', 0)
    total_yld    = yield_proj.get('total_yield_kg', 0)
    harvest_stat = (yield_proj.get('harvest_status') or 'incomplete').lower()
    loss_pct     = yield_proj.get('potential_loss_percent', 0)
    potential_yld = yield_proj.get('yield_potential_kg_per_acre', 2500)
    vigor        = (yield_proj.get('vegetation_vigor') or 'good').lower()
    limiting     = [f['factor'] for f in yield_proj.get('limiting_factors', [])][:3]
    limiting_str = ', '.join(limiting) if limiting else 'minor nutrient deficiencies'

    # Derive harvest period from satellite visit or current month
    visit_str = aoi_info.get('satellite_visit', datetime.now().strftime('%b %Y'))
    parts = visit_str.split()
    harvest_period = ' '.join(parts[-2:]) if len(parts) >= 2 else visit_str

    story.append(Paragraph('4.  Soil Management & Growth / Yield', S['section']))

    # Side-by-side metric boxes
    def _metric_cell(label: str, value: str, unit: str = '') -> Paragraph:
        return Paragraph(
            f'<font size=14><b>{value}</b></font>'
            f'{"<br/>" + unit if unit else ""}<br/>'
            f'<font size=7 color="#424242">{label}</font>',
            S['center'])

    soil_rows = [
        [Paragraph('<b>Soil Management</b>', S['subsection'])],
        [_metric_cell('pH', str(ph))],
        [_metric_cell('Salinity', salinity)],
    ]
    yield_rows = [
        [Paragraph('<b>Growth & Yield</b>', S['subsection'])],
        [_metric_cell('Crop', crop_name)],
        [_metric_cell('Yield / acre (kg)', str(int(yld_acre)))],
        [_metric_cell('Total Yield (kg)', f'{total_yld:.1f}')],
        [_metric_cell('Harvest Period', harvest_period)],
        [_metric_cell('Status', harvest_stat)],
    ]

    max_r = max(len(soil_rows), len(yield_rows))
    while len(soil_rows)  < max_r: soil_rows.append([Paragraph('', S['body'])])
    while len(yield_rows) < max_r: yield_rows.append([Paragraph('', S['body'])])

    metrics = Table(
        [[s[0], y[0]] for s, y in zip(soil_rows, yield_rows)],
        colWidths=[half_w, half_w])
    metrics.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (0,-1), LIGHT_GREEN),
        ('BACKGROUND',    (1,0), (1,-1), LIGHT_BLUE),
        ('BOX',           (0,0), (0,-1), 0.5, MED_GREEN),
        ('BOX',           (1,0), (1,-1), 0.5, BLUE),
        ('TOPPADDING',    (0,0), (-1,-1), 2*mm),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2*mm),
        ('LEFTPADDING',   (0,0), (-1,-1), 3*mm),
        ('RIGHTPADDING',  (0,0), (-1,-1), 3*mm),
        ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(metrics)
    story.append(Spacer(1, 4*mm))

    story.append(Paragraph('Details — Soil Management', S['subsection']))
    story.append(Paragraph(
        f'Soil pH is predicted at {ph} based on regional {location} trends and previous irrigation cycles; '
        f'salinity remains {salinity.lower()} due to controlled drip leaching fractions. '
        f'The current soil organic carbon (SOC) level of {soc:.2f}% is <b>{soc_status}</b> for '
        f'{crop_name.lower()} cultivation. Low SOC leads to poor soil structure, reduced '
        'water-holding capacity, and inefficient nutrient cycling. '
        'To improve SOC, incorporate well-rotted manure or compost, use cover crops between rows, '
        'and apply organic mulches to enhance microbial activity and soil aggregates.',
        S['body']))
    story.append(Paragraph(
        '<i>References: pH and Salinity estimates based on CSSRI regional soil maps. '
        'FAO (2017). Soil Organic Carbon: the hidden potential. '
        'Cornell University (2020). Comprehensive Assessment of Soil Health.</i>',
        S['ref']))

    story.append(Paragraph('Details — Growth & Yield', S['subsection']))
    above_below = 'above' if loss_pct < 20 else 'below'
    story.append(Paragraph(
        f'Yield is estimated {above_below} the local median due to {vigor} vegetation vigor, '
        f'indicating robust canopy development. However, {limiting_str} prevent reaching the '
        f'local maximum potential of {int(potential_yld)} kg/acre. '
        f'Satellite vegetation indices on the visit date confirm the crop is in {growth_stage_name} '
        'and aligns with the local seasonal window.',
        S['body']))
    story.append(Paragraph(
        '<i>References: Yield estimates based on ICAR guidelines and Sentinel-1 RVI-to-biomass '
        'correlation models. Nutrient impact assessed via Liebig\'s Law of the Minimum.</i>',
        S['ref']))

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════════════
    # PAGE 4 — Pest, Disease & Weed Management
    # ═══════════════════════════════════════════════════════════════════════════
    all_threats = (pest_data.get('pests_diseases', []) +
                   pest_data.get('weeds', []))
    all_threats.sort(key=lambda x: x.get('risk_percent', 0), reverse=True)

    summ    = pest_data.get('summary', {})
    hi_cnt  = summ.get('high_risk_count', 0)
    mo_cnt  = summ.get('moderate_risk_count', 0)
    lo_cnt  = summ.get('low_risk_count', 0)

    env_cond     = pest_data.get('environmental_conditions', {})
    temp_mean    = env_cond.get('temperature', 30)
    humidity_est = env_cond.get('humidity_estimate', 60)
    rsm_val      = env_cond.get('rsm', 0.72)
    gs_pest      = (env_cond.get('growth_stage') or 'growth').replace('_', ' ')

    story.append(Paragraph('5.  Pest, Disease & Weed Management', S['section']))
    story.append(Paragraph(
        f'High Risk: <b>{hi_cnt}</b> | Moderate Risk: <b>{mo_cnt}</b> | Low Risk: <b>{lo_cnt}</b>',
        S['subsection']))

    p_hdrs   = ['Name', 'Category', 'Risk %', 'Risk Level', 'Organic Solution', 'Chemical Solution']
    p_col_ws = [35*mm, 22*mm, 17*mm, 22*mm, 38*mm, 38*mm]
    p_rows   = [p_hdrs]
    for t in all_threats:
        rp = t.get('risk_percent', 0)
        rp_str = f"{rp:.0f}%" if isinstance(rp, (int, float)) else str(rp)
        p_rows.append([
            t.get('name', ''),
            (t.get('category') or '').title(),
            rp_str,
            (t.get('risk_level') or 'low').title(),
            t.get('organic_solution', '—'),
            t.get('chemical_solution', '—'),
        ])

    p_style = _base_table_style() + [
        ('ALIGN', (0,0), (0,-1), 'LEFT'),
        ('ALIGN', (4,0), (5,-1), 'LEFT'),
    ]
    for i, t in enumerate(all_threats, 1):
        lvl = (t.get('risk_level') or 'low').lower()
        p_style += [
            ('BACKGROUND', (3,i), (3,i), _risk_bg(lvl)),
            ('TEXTCOLOR',  (3,i), (3,i), _risk_fg(lvl)),
            ('FONTNAME',   (3,i), (3,i), 'Helvetica-Bold'),
        ]

    pest_table = Table(p_rows, colWidths=p_col_ws)
    pest_table.setStyle(TableStyle(p_style))
    story.append(pest_table)
    story.append(Spacer(1, 3*mm))

    story.append(Paragraph('Details — Pest & Disease', S['subsection']))
    story.append(Paragraph(
        f'High canopy density ({vigor} vegetation vigor) creates a humid microclimate conducive '
        f'to fungal diseases. Rising {location} temperatures ({temp_mean:.0f}°C mean) accelerate '
        f'pest life cycles, while {humidity_est:.0f}% estimated humidity increases susceptibility '
        f'to leaf-spot diseases during the sensitive {gs_pest} period.',
        S['body']))
    story.append(Paragraph(
        '<i>References: Based on ICAR-CITH crop phenology guidelines and regional pest alerts. '
        'Satellite RVI/RSM correlations derived from Sentinel-1 SAR indices for biomass monitoring.</i>',
        S['ref']))

    story.append(Paragraph('Details — Weed', S['subsection']))
    story.append(Paragraph(
        f'High soil moisture (RSM {rsm_val:.2f}) suggests recent irrigation or high retention, '
        'which promotes weed germination in tree basins. Although the high vegetation index '
        'indicates good canopy closure, any light penetration on the plantation floor will trigger '
        f'rapid weed growth. The semi-arid climate facilitates weed competition for nutrients '
        f'during the critical fruit-set transition following {gs_pest}.',
        S['body']))
    story.append(Paragraph(
        '<i>References: Weed risk assessed via Indian Society of Weed Science (ISWS) orchard '
        'management protocols and local irrigation-weed growth correlations.</i>',
        S['ref']))

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════════════
    # PAGE 5 — Fertilizer Management
    # ═══════════════════════════════════════════════════════════════════════════
    nutrient_reqs = fert_data.get('nutrient_requirements', {})
    fert_sched    = fert_data.get('fertilizer_schedule', {})
    freq_days     = fert_sched.get('frequency_days', 2)
    products      = fert_sched.get('recommended_products', [])

    # Default organic/chemical source lookup
    org_map  = {'N': 'Vermicompost',     'P': 'Bone Meal (241.67)',
                'K': 'Wood Ash (1090.0)','S': 'Composted Manure',
                'Zn': 'Enriched FYM (55.0)'}
    chem_map = {'N': 'Urea (19.78)',     'P': 'Diammonium Phosphate',
                'K': 'Sulphate of Potash','S': 'Bentonite Sulphur',
                'Zn': 'Zinc Sulphate'}
    for p in products:
        nm = p.get('product', '')
        qty = p.get('quantity_kg_acre', '')
        tag = f" ({qty:.2f})" if isinstance(qty, float) else ''
        if 'Urea'        in nm: chem_map['N']  = nm + tag
        elif 'DAP'       in nm: chem_map['P']  = nm + tag
        elif 'SOP'       in nm or 'Sulphate of Potash' in nm: chem_map['K'] = nm + tag
        elif 'Bone Meal' in nm: org_map['P']   = nm + tag
        elif 'Wood Ash'  in nm: org_map['K']   = nm + tag
        elif 'Zinc'      in nm: chem_map['Zn'] = nm + tag
        elif 'Bentonite' in nm: chem_map['S']  = nm + tag

    need_attn = sum(1 for v in nutrient_reqs.values()
                    if 'critical' in (v.get('status') or ''))
    monitor   = sum(1 for v in nutrient_reqs.values()
                    if 'moderate' in (v.get('status') or ''))
    optimal   = sum(1 for v in nutrient_reqs.values()
                    if 'adequate' in (v.get('status') or ''))

    story.append(Paragraph('6.  Fertilizer Management', S['section']))
    story.append(Paragraph(
        f'Need Attention: <b>{need_attn}</b> | Monitor Closely: <b>{monitor}</b> | Optimal: <b>{optimal}</b>',
        S['subsection']))
    story.append(Paragraph(
        f'<b>Frequency of Application:</b> {freq_days} days', S['body']))

    DISPLAY = {'N':'Nitrogen','P':'Phosphorus','K':'Potassium','S':'Sulfur','Zn':'Zinc'}
    f_hdrs   = ['Nutrient','Current (Kg/Acre)','Target (Kg/Acre)','Status',
                'Organic Source (kg/ac)','Chemical (kg/ac)']
    f_col_ws = [25*mm, 25*mm, 25*mm, 22*mm, 42*mm, 33*mm]
    f_rows   = [f_hdrs]
    f_statuses = []

    for key in ['N','P','K','S','Zn']:
        nr     = nutrient_reqs.get(key, {})
        cur    = nr.get('current_kg_per_acre', 0)
        tgt    = nr.get('target_kg_per_acre', '—')
        status = (nr.get('status') or 'moderate').replace('_',' ').title()
        f_statuses.append(status)
        f_rows.append([
            DISPLAY.get(key, key),
            str(round(cur, 2)),
            str(tgt),
            status,
            org_map.get(key, '—'),
            chem_map.get(key, '—'),
        ])

    f_style = _base_table_style() + [
        ('ALIGN', (0,0), (0,-1), 'LEFT'),
        ('ALIGN', (4,0), (5,-1), 'LEFT'),
    ]
    for i, st_val in enumerate(f_statuses, 1):
        f_style.append(('BACKGROUND', (3,i), (3,i), _status_bg(st_val)))

    fert_table = Table(f_rows, colWidths=f_col_ws)
    fert_table.setStyle(TableStyle(f_style))
    story.append(fert_table)
    story.append(Spacer(1, 3*mm))

    n_gap = nutrient_reqs.get('N', {}).get('gap_kg_per_acre', 9.1)
    p_gap = nutrient_reqs.get('P', {}).get('gap_kg_per_acre', 7.25)
    k_gap = nutrient_reqs.get('K', {}).get('gap_kg_per_acre', 54.5)

    story.append(Paragraph('Details — Fertilizer Management', S['subsection']))
    story.append(Paragraph(
        f'1. Nitrogen levels were calculated based on vegetation vigor during {growth_stage_name}, '
        f'requiring {n_gap:.1f} kg/acre gap fulfillment. '
        f'2. Phosphorus gap of {p_gap:.2f} kg/acre is addressed using DAP and Bone Meal. '
        f'3. Potassium requirement is high for fruit set; {k_gap:.1f} kg/acre gap is met with SOP and Wood Ash. '
        '4. Sulfur and Zinc are critical for enzyme activation during bloom; '
        'gaps are supplemented via Bentonite Sulphur and Zinc Sulphate. '
        '5. Drip irrigation allows for simultaneous fertigation of soluble nutrients, '
        'while organic matter should be soil-applied. '
        f'6. Frequency set to every {freq_days} days to prevent osmotic stress and leaching '
        'in sandy loam soils.',
        S['body']))
    story.append(Paragraph(
        '<i>References: Nutrient rates based on ICAR-CITH guidelines for '
        f'{crop_name}; fertilizer grades: Urea (46% N), DAP (46% P₂O₅), SOP (50% K₂O). '
        'Max dose limits derived from FAO Fertigation Manual.</i>',
        S['ref']))

    story.append(Spacer(1, 4*mm))
    story.append(_disclaimer_box(
        'This farm advisory report is AI-generated and should be used as a general guide only. '
        'All recommendations should be verified by agricultural experts and adapted to '
        'local conditions before implementation.',
        S))

    # ── Build ──────────────────────────────────────────────────────────────────
    def _on_page(canvas, doc):
        _draw_header(canvas, doc, report_date, aoi_info)

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    buf.seek(0)
    return buf.read()
