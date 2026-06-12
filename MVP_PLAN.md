# Jeevn — MVP Direction & Phased Roadmap

## Context

The repo (project "Jeevn") already generates a 5-page satellite-based farm advisory: real Sentinel-2 NDVI/NDWI/NDRE, Sentinel-1 RVI, FAO-56 + Hargreaves-Samani irrigation scheduling, ISRIC SoilGrids soil profile, rule-based pest/disease risk, and fertilizer gap analysis — with graceful fallbacks and fabrication tracking. Goal: define the smallest version that real farmers will *keep using* (free is fine; usage and data are the currency), pick a crop/region/channel on market merit, and lay out post-MVP phases. Photo-based disease CV is explicitly post-MVP.

Founder assets: a friend from a farming family, and a family contact who is an **agri-input dealer** dealing with farmers daily.

---

## Part 1 — Strategic choices

### Crop & region: **Wine/table grapes, Nashik–Sangli belt (Maharashtra)**; pomegranate (Solapur/Ahmednagar) as close second

Pure market-merit scoring (WTP × tech-readiness × decision frequency × fit with what's built):

| Criterion | Grape (Nashik) | Pomegranate | Apple (HP/J&K) | Wheat/cotton |
|---|---|---|---|---|
| WTP | **Proven** — farmers already pay consultants ₹10–50k/season; Fyllo/Fasal charge ₹40k+/yr here | High, less contested | Medium | Near-zero per farmer |
| Tech adoption | Highest in Indian horticulture; drip + fertigation universal | High | Medium | Low |
| Decision frequency (retention driver) | **Weekly** for 8–9 months (mildew windows, fertigation, deficit irrigation) | Weekly (bahar/deficit-irrigation management) | Seasonal bursts | A few decisions/season |
| Fit with current modules | Irrigation scheduler + fertigation + disease-risk = exact match; semi-arid → good Sentinel-2 visibility; 1–5 acre plots OK at 10 m | Same | Poor: monsoon clouds, steep terraced slopes break optical RS; mostly rain-fed | RS fit OK but advisory value/acre low |
| Pain today | Downy/powdery mildew after rain events; water scarcity; EU residue limits on exports force spray discipline | Water scarcity, bahar timing | Hail/weather | Price, not agronomy |

#### Why grapes — full rationale

1. **Willingness to pay is proven, not hypothetical.** Nashik grape farmers are among the very few farmer segments in India who *already* pay for agronomy advice — private crop consultants charge ₹10–50k/season, and agritech companies (Fyllo, Fasal) have built real revenue there at ₹40k+/year. The category doesn't need to be created, only won.
2. **The economics support it.** Grape revenue runs ₹3–8 lakh/acre; sprays alone can cost ₹50k–1L/acre/season. Advice that saves two unnecessary sprays — or prevents one missed mildew window — pays for itself many times over. On wheat at ₹40–50k/acre revenue, the same advisory is worth almost nothing per farmer.
3. **Decision frequency = the retention engine.** Grapes demand decisions weekly for 8–9 months: downy/powdery mildew risk after every rain or humidity spike, fertigation dosing by stage, deficit irrigation around fruit set. That cadence matches a weekly satellite report perfectly. Low-frequency crops mean the app gets opened twice and forgotten — no data flywheel.
4. **It plays to what's already built.** The strongest real (non-fabricated) modules are the FAO-56 irrigation scheduler, weather-driven disease risk scoring, and fertilizer gap analysis. Nashik grapes are ~100% drip-irrigated with fertigation in a water-scarce region, and downy mildew is literally a temperature-humidity-rain-event disease — a "rain Thursday → spray window Friday" alert is buildable from data already ingested (Open-Meteo).
5. **The satellite physics work there.** Semi-arid Deccan plateau: fewer clouds outside peak monsoon, flat terrain, 1–5 acre contiguous vineyard blocks that resolve fine at Sentinel-2's 10 m pixels. Apple (already in the crop DB) is the opposite: monsoon cloud cover, steep terraced slopes, rain-fed orchards — keep it supported, don't pilot on it.
6. **Export pressure forces discipline.** EU residue limits (MRLs) make Nashik growers unusually receptive to data-driven spray-window advice — and later give a paid B2B feature (spray-record/compliance reporting for exporters).

**Honest counterarguments:** Fyllo/Fasal are entrenched in Nashik with on-farm IoT sensors, which beat satellite + regional weather for microclimate disease prediction. The counter-position is price and zero hardware: they serve the top of the market; a free-then-cheap satellite-only product targets the much larger mass of growers who won't buy hardware. Grape agronomy is also demanding — a wrong spray call is trust-ending, hence the agronomist-review requirement below. If competition worries more than market maturity, flip the order and lead with pomegranate.

**Override rule:** if the input-dealer contact operates in a different irrigated-horticulture region (banana in Jalgaon, onion in Nashik district, citrus in Vidarbha…), pilot *there* — warm access to 20 farms beats theoretical merit. The crop-DB work is the same effort regardless of which 1–2 crops are added.

### Channel: **B2B-light ("concierge") via the input dealer + 1–2 crop consultants** — not pure self-serve, not heavy B2B

- Farmers will not discover or operate a Streamlit app; pure self-serve dies at cold start. Heavy B2B (FPO/enterprise contracts) needs accounts, SLAs, sales cycles — too early.
- Instead: **the founder (or the dealer) operates the existing Streamlit UI**, draws boundaries during onboarding, and delivers the weekly PDF to each farmer **manually via WhatsApp**. The dealer is the prototype of the eventual field-agent network; manual WhatsApp delivery is the prototype of the eventual WhatsApp automation. Zero new UI investment needed for the pilot.
- Watch the incentive risk: dealer-distributed advisory must stay agronomy-led, not input-sales-led, or farmer trust dies.

### The core product insight: sell a **weekly monitoring loop**, not a report

A one-time report is a demo. The retention engine is: *"every Monday — this week's irrigation plan, this week's disease-risk window, and what changed on your farm since last week."* Everything in the MVP scope serves that loop.

---

## Part 2 — MVP engineering scope (in this repo)

### 1. Trust pass: never present fabricated numbers as real (highest priority)
Fabrication tracking already exists (`src/jeevn/application/advisory_service.py`, `data_quality.fabricated_fields`; defaults in `src/jeevn/infrastructure/pseudo_satellite.py`). Change presentation, not plumbing:
- UI sections (`src/jeevn/ui/sections/*`) and PDF (`src/jeevn/ui/pdf/generator.py`): grey-out or omit fabricated fields with "data unavailable" instead of showing default numbers (NDVI 0.65, RSM 0.72, etc.).
- **Remove the LST chip** (stubbed "Pending Sentinel-3") from `ui/sections/irrigation_schedule.py` — placeholder chips erode credibility.
- **Kill hardcoded "current N/P/K/S/Zn"** (13.65/11.0/82.0/7.0/0.8 in the fertilizer section). Replace with an optional soil-test-report input form at AOI creation (most grape farmers test annually). Without a soil test: show only targets + crop/stage-appropriate product recommendations, labelled as general guidance.
- Replace hardcoded "Best time 05:00–08:00" with sunrise-derived timing or relabel as general guidance.

### 2. Persistence + weekly re-run (the retention engine)
- Move AOIs from the in-memory dict to the DB — SQLAlchemy models already exist (`src/jeevn/infrastructure/db/models.py`: AOI, IngestJob, Artifact). Persist generated advisories (fixes the stubbed `GET /advisory/agricultural/{advisory_id}`).
- Scheduled weekly regeneration per AOI (APScheduler or cron hitting the API).
- **Trend section**: `aggregate_ndvi` already writes an NDVI/NDWI/NDRE time-series CSV (`src/jeevn/remote_sensing/ndvi/aggregate.py`) — surface "this week vs last 4 weeks" as a chart + one-line change narrative in UI and PDF. This is the single most valuable new farmer-visible feature and it's mostly plumbing.

### 3. Crop database: add grape (+ pomegranate)
- Phenology stages, NDVI ranges, yield potential, Kc stages: `src/jeevn/domain/crop/phenology.py` (follow apple/wheat pattern).
- Pest/disease/weed entries with risk formulas — for grape, **downy mildew risk after rain events is the killer feature** (temp + humidity + rainfall driven, all data already flowing from Open-Meteo): `src/jeevn/domain/pest_disease_weed/assessment.py`.
- Fertilizer targets + product list: `src/jeevn/domain/fertilizer/requirements.py`, `schedule.py`.
- Get one agronomist/crop consultant to review these tables before pilot — wrong spray advice on grapes is a trust-ending event.

### 4. WhatsApp-ready output
- Add a 1-page summary as page 1 of the existing ReportLab PDF (this week's actions, risk flags, trend chart); detail pages follow. English numbers + consultant explanation is fine for MVP; Marathi/Hindi is Phase 1.

### 5. Minimal ground-truth loop
- Per-farm observation log (even a simple table: date, farmer-reported event, advisory followed Y/N), entered by founder/dealer after weekly WhatsApp check-ins. This is the seed of the data moat and the future CV training set.

### Explicitly OUT of MVP
Photo-CV diagnosis, NISAR (production paused anyway), Sentinel-3/LST, ML yield models, self-serve mobile app, payments/accounts, multi-language UI.

---

## Part 3 — Pilot & success metrics

- 15–30 farms via the input dealer + friend's network; free; 8–12 week run during an active disease-pressure window.
- Weekly: regenerate advisories → send PDFs on WhatsApp → log feedback/observations.
- Success = **retention behavior, not signups**: % of farmers who open/ask about the report each week, % who acted on ≥1 recommendation, farmer-initiated questions, "would you pay / refer" at week 8. Also track data-quality stats: % of reports with zero fabricated farmer-visible fields.

---

## Part 4 — Post-MVP roadmap

**Phase 1 — Automate the loop (after pilot retention is proven)**
- WhatsApp Business API: automated weekly report delivery + event-driven alerts ("rain forecast Thu → downy-mildew spray window Fri–Sat" — this alert alone can carry the product).
- Marathi/Hindi PDF + messages.
- **Photo collection (store-only)**: farmers send field photos on WhatsApp; store against the farm/date with human-reviewed labels. Builds the CV dataset cheaply.
- Soil-test onboarding hardening (photo/PDF of lab report → manual entry).

**Phase 2 — Data products & sensing depth**
- Photo-based disease/pest diagnosis: off-the-shelf model (PlantVillage-class) + human-in-the-loop review before fully automated answers; fine-tune on Phase-1 collected photos.
- Thermal/LST for water-stress: prefer **Landsat 8/9 thermal (~100 m, free, already on Planetary Computer)** over Sentinel-3 SLSTR (1 km — too coarse for 1–5 acre plots).
- NISAR L-band soil moisture when NASA-ISRO production resumes (pipeline already built in `infrastructure/data_sources/nisar.py`).
- In-field variability: per-zone NDVI sub-field maps with management-zone recommendations (raster pipeline already computes full-res GeoTIFFs).
- Irrigation timing from solar/ET curve instead of fixed window.

**Phase 3 — Scale & monetize**
- Field-agent app: multi-farm dashboard so one dealer/agent manages 100+ farms (this is the real B2B product).
- B2B SaaS: FPOs, grape exporters (spray-record/residue-compliance reporting for EU export is a direct money feature), input companies.
- Yield estimation ML trained on accumulated ground truth + RS time-series.
- Pricing experiments: per-acre/season freemium (alerts free, full advisory paid) — anchored by pilot WTP interviews.
- Second crop/region expansion using the now-templated crop-DB process.

---

## Verification (for the MVP build)

- Existing pytest suite (`tests/`) passes; add tests for new crop phenology/pest tables mirroring apple/wheat tests.
- End-to-end: create a Nashik-area grape AOI via Streamlit → confirm real Sentinel-2/weather/soil data flows, zero fabricated farmer-visible numbers, trend chart renders after ≥2 weekly runs (can simulate by backdating), PDF 1-page summary generates.
- Restart the API process → AOI and past advisories survive (persistence works).
- Dry-run the weekly scheduler against 2–3 test AOIs for two cycles before pilot launch.
