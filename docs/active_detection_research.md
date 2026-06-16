# Research Brief — Active / Proximal Detection of Weeds, Pests & Disease

*A feasibility deep-dive grounded in the primary literature. Deliverable type: **research brief** (no build commitment). Written **crop-agnostic** and **nation-agnostic**. Scope = "active devices and science" (cameras, traps, sensors, drones, robots) — explicitly **not** satellite/remote sensing.*

*This revision reflects a close read of ~18 primary sources (arXiv / PMC / Scientific Reports / extension services / vendor API docs). Every accuracy figure below is traced to a named study in the Sources section.*

---

## Context — why this brief exists

The system's pest/disease/weed module is, today, **entirely heuristic**. Per [PROCESSES.md](../PROCESSES.md) §H/§J.4/§J.6:

- **Pest/disease risk** = `30%·temp_suitability + 25%·humidity_impact + 25%·rvi_risk + 20%·stage_susceptibility`, and humidity itself is **estimated** from `min(100, 40 + rainfall×2 + (30−temp)×2)` because "we have no direct RH source."
- **Weed risk** leans on the constant `RSM = 0.72` plus rainfall and an RVI proxy.
- **"Disease patch detection"** is a rolling NDVI decline — it "can't distinguish disease from drought, frost, or harvest," and carries a `np.random.uniform(0.02, 0.08)` jitter floor.

None of this *sees* a pest, a lesion, or a weed. This brief surveys what real **active/proximal** detection looks like in industry and academia, with measured numbers, and judges whether any of it is buildable into a software advisory tool **in a meaningful way**.

---

## Evidence at a glance

| Family | Best measured result (named study) | Device | Maturity | Software-tool fit |
|---|---|---|---|---|
| Vision — lab benchmark | **99.96%** acc on PlantVillage (ViT+MoE) | phone/camera | Productized | — (misleading; see below) |
| Vision — **in-the-wild** | **0.74** acc on PlantDoc; **67.2%** on PlantWild (89 cls) | phone/camera | High | **Strong** |
| Vision — mobile | **93.6–97.7%** on curated crops, **0.98–5.06 M** params (PMVT) | phone | High | **Strong** |
| Weeds — classification | **95.7%** (ResNet-50, DeepWeeds, 9 cls) | phone/drone/robot cam | High | Strong |
| Weeds — detect+act | **44–87%** herbicide cut (See & Spray, 415-ac trial) | $100k+ sprayer/robot | High | No (equipment) |
| Smart traps — counting | **97.89%** count acc, 1–14 s/img vs 199–501 s manual | IoT camera trap | High, has API | **Strong (optional tier)** |
| Smart traps — detection | **98.3% mAP50** (YOLOv9-TrapPest, 7 pests) | IoT electro-trap | High | Strong (optional tier) |
| Proximal optical | **96%/76%** grapevine virus (hyperspectral, 347 vines) | handheld spectro | Medium | Future premium tier |
| Weather DSS — disease | **87%** acc / **AUC 0.903** late-blight risk (RF) | weather + LW sensor | Very high (decades) | **Strongest** |
| Sensor — acoustic | **99.9%** RPW (fiber DAS, lab); 1–2 beetles/kg (grain) | piezo/fiber/mic | Niche | Niche only |
| Sensor — e-nose/VOC | pre-symptomatic in lab; μg/L detection floor | gas sensor array | Low (lab) | Not yet |

---

## Family 1 — Vision / image classification (the camera & smartphone route)

The largest, most mature body of work, and the **only family where the end user already owns the hardware** (a phone). But the literature is unambiguous that **the headline numbers are a lie of context**.

**The lab number is meaningless; the field number is what ships.** Across multiple independent benchmarks:
- A 2025 ViT+Mixture-of-Experts model scored **0.9996** on PlantVillage but **0.74** on the in-the-wild PlantDoc set; the same paper cites prior work going from **99.35% → "below 40%"** on field images ([Frontiers/PMC12213485](https://pmc.ncbi.nlm.nih.gov/articles/PMC12213485/)).
- The PlantWild benchmark (18,542 wild images, **89 classes**) measured the drop directly: a strong fine-grained model fell **98.88% → 65.92%** (−32.96 pts); another **98.80% → 63.61%** (−35.19 pts). Their best multimodal baseline reached only **67.2%** on wild data, and **32.77% zero-shot** ([arXiv 2408.03120](https://arxiv.org/html/2408.03120v1)).
- Trained on a *downsampled* PlantVillage and tested cross-domain on PlantDoc, even the best model managed **0.68**, with vanilla ViT at **0.48** ([PMC12213485](https://pmc.ncbi.nlm.nih.gov/articles/PMC12213485/)).

**Why it collapses** (the papers name the same factors): complex/cluttered backgrounds, viewpoint and lighting variation, small objects at distance, subtle early-stage symptoms, large intra-class variance + small inter-class discrepancy, and multiple diseases in one image.

**Mobile is solved enough to ship.** [PMVT](https://pmc.ncbi.nlm.nih.gov/articles/PMC10562605/) (a MobileViT variant) runs at **0.98–5.06 M parameters / 0.31–1.59 GFLOPs**, scoring **93.6–94.9%** (wheat, 7 classes), **85–88%** (coffee), **92–97.7%** (rice), beating MobileNetV3 by 1.6–3.4 pts at 81–88 FPS. [TinyML reviews](https://arxiv.org/pdf/2603.15085) show such models quantize to 8-bit, compress 4–8×, and run under **256 KB RAM** on ESP32/Cortex-M class hardware.

**Industrial anchor:** [Plantix](https://www.gsma.com/solutions-and-impact/connectivity-for-good/mobile-for-development/blog/detecting-and-managing-crop-pests-and-diseases-with-ai-insights-from-plantix/) — ~800 symptoms across 60 crops, geo-time-tagged photos aggregating into regional pest maps.

**Pest-specific datasets** are harder than disease: IP102 has **102 pest classes** in a hierarchy with heavy class imbalance and fine-grained look-alikes ([review, arXiv 2507.01494](https://arxiv.org/pdf/2507.01494)).

**Takeaway:** buildable and accessible, but only honest if (a) trained/validated on *field* data, (b) confidence-gated, and (c) framed as decision support with a human in the loop. A model advertised at "99%" will perform around **65–75%** in a real field.

---

## Family 2 — Smart traps (the gold standard for *insect pests*)

This is where automated detection is genuinely **mature and quantified**, because the imaging happens in a controlled enclosure (a trap), not the open canopy.

- **Counting from trap images:** across Faster R-CNN, EfficientDet, RetinaNet and SSD, a study on 50 trap photos containing **23,056 insects** reached **88–90% AP** and **up to 97.89% counting accuracy**, at **1.19–14.14 s/image vs 199–501 s** for a human ([PMC8068825](https://pmc.ncbi.nlm.nih.gov/articles/PMC8068825/)).
- **Fully-unattended electro-traps:** YOLOv9-TrapPest, over 7 moth species, hit **97.5% AP / 96.6% recall / 98.3% mAP50**, beating baseline YOLOv9 (93.9%) — the trap electrocutes, images, then rotates the tray clear for continuous operation ([PMC11922902](https://pmc.ncbi.nlm.nih.gov/articles/PMC11922902/)).
- **Field deployments** (e.g. iMETOS iSCOUT across three climatically distinct orchards) confirm the operational pattern — solar trap, **3 images/day**, significant regional pest variation (p<0.05) — though vendor studies rarely publish accuracy ([orchard study](https://dergipark.org.tr/en/pub/jaefs/article/1815207)). Commercial: [Trapview](https://www.cnn.com/2022/11/24/business/trapview-ai-pest-management-spc-intl/index.html) (60+ species), [Semios](https://semios.com/our-hardware/automated-camera-traps/).

**Integration is real and documented.** The [Pessl FieldClimate REST API](https://api.fieldclimate.com/v1/docs/) uses **HMAC (SHA-256) or OAuth2**, exposes seven route groups including **`DATA`** (historical readings, min/max/avg aggregations), **`DISEASE`** (crop-specific disease-risk models + ETo), `STATION`, and `FORECAST`, ships crop-specific disease models (Apple, Apricot/Plum, Viticulture…), surfaces leaf-wetness sensor codes, and currently enforces **no rate limit**. A third-party tool can pull weather, leaf wetness, and disease-model output directly.

**The catch:** the grower must **own the trap/station** (hundreds–thousands of dollars). This is an **optional connected-device tier**, not the default path.

---

## Family 3 — Optical proximal sensing (handheld / robot hyperspectral & multispectral)

Powerful and partly pre-symptomatic, but **specialist hardware** and **low disease specificity**.

- A proximal-sensing review tabulates realistic field/greenhouse accuracies: soybean iron chlorosis (RGB+decision-tree) **99.7%**; wheat powdery mildew/rust (smartphone RGB + RVM) **88.89%**; sugar-beet Cercospora (hyperspectral+SVM) **86.42%**; cucumber fungal (RGB+AlexNet) **92.6%**; coffee leaf-miner/rust (smartphone RGB + VGG16) **86.51%**; barley drought (hyperspectral) **67.9%**; wheat crown rot (hyperspectral+ANN) **74.14%** ([PMC7760370](https://pmc.ncbi.nlm.nih.gov/articles/PMC7760370/)).
- Handheld hyperspectral (ASD FieldSpec, **325–1075 nm @ 1 nm**, PLS-DA, 347 vines) classified grapevine virus at **96% (red) / 76% (white)** — but **not** pre-symptomatically; accuracy peaked only at harvest ([PMC10007312](https://pmc.ncbi.nlm.nih.gov/articles/PMC10007312/)).

**Limitations the review is explicit about:** optical data alone lacks disease *specificity* (a lesion and drought can look alike); strong sensitivity to lighting/time-of-day; reflectance differs by species; hyperspectral cameras cost thousands of dollars; truly asymptomatic pathogens remain invisible to reflectance. → a plausible *future premium tier*, not a near-term default.

---

## Family 4 — Weather-driven infection & degree-day models (the science backbone)

The family that fits a **software advisory tool best**: the core inputs are weather the system **already fetches hourly**, and the models are **decades-validated across many crops** — so it stays crop-agnostic.

- **Disease infection models** convert *temperature × leaf-wetness/RH* into infection-period risk. The **revised Mills table** for apple scab requires **41 h** of leaf wetness at 6 °C, **11 h** at 10 °C, **6 h** at 16–24 °C, **11 h** at 26 °C ([PSU Extension](https://extension.psu.edu/tree-fruit-disease-predicting-infection-periods-to-apply-protection)); the same family includes **BlightPro/Blitecast/Wallin** (potato & tomato late blight), **TOMCAST** (a Disease-Severity-Value model adapted across potato, asparagus, carrot, celery, pistachio), grape downy mildew, cereal, and strawberry DSS, plus [RIMpro](https://rimpro.cloud/platform/apple-scab-venturia-inaequalis/). Fire blight uses degree-hour models (Cougarblight, 4-day accumulations).
- **Quantified rules** (grape downy mildew, in-situ study): the **50 degree-hour** rule (temperature × leaf-wetness duration); minimum infection **13 °C + 8 mm rain**; sporangia die above **30 °C for >6 h**; leaf-wetness threshold operationalized as **≥460 sensor counts** (PHYTOS 31) ([PMC9316467](https://pmc.ncbi.nlm.nih.gov/articles/PMC9316467/)).
- **ML upgrades** of these models work: potato late-blight aerobiological risk (≥10 sporangia/m³) over 586 samples across 5 seasons reached **Random Forest 87% accuracy, κ 0.70, AUC 0.903** (C5.0: 85%, AUC 0.904) ([PMC10146589](https://pmc.ncbi.nlm.nih.gov/articles/PMC10146589/)).
- **Pest emergence** uses insect-specific degree-days from a biofix — the textbook method PROCESSES §H.1 already names as the "scientific ideal."

**Key feasibility point — and its sharp caveat.** Leaf wetness and RH are the missing inputs, and **RH/rain/temperature are already in the Open-Meteo hourly feed the system uses**. Leaf wetness can be *estimated* (RH ≥ ~90% + rain hours) with **zero new hardware**. **But** the downy-mildew study is a direct warning: an off-site weather station read leaf wetness at **>900 counts** while the in-canopy average was **~460**, and on **19 nights the canopy never actually wetted** despite the station signalling daily exceedance (it also read 3.6 °C cooler and 3.5% wetter by day). **Microclimate inside the canopy diverges sharply from gridded/off-site weather** — so a weather-*estimated* leaf-wetness model should be presented as a *risk indicator*, and upgraded to a *measured* in-canopy sensor (or trap/station) when one is connected. That is exactly the system's existing tiered "real-where-available" pattern for RVI and RSM (PROCESSES §A.4/§A.5).

---

## Family 5 — Other sensor science + machine-scale actuation (context, not candidates)

- **Acoustic** is real but **niche**. Fiber-optic distributed acoustic sensing on date-palm trunks detected red palm weevil larvae at **99.9% (ANN) / 99.7% (CNN)**, one unit covering **~1,000 trees over ~10 km** — but **lab-validated only**, with wind-noise confusion and labor-intensive fiber install/maintenance ([PMC7956387](https://pmc.ncbi.nlm.nih.gov/articles/PMC7956387/)). Stored-grain acoustics detect **1–2 beetles/kg**, with banana-weevil and wood-borer systems near **90%** — but the review concludes commercial acoustic devices have "not yet achieved the versatility, ease of use, and cost-effectiveness of currently available cell phones" ([PMC8003406](https://pmc.ncbi.nlm.nih.gov/articles/PMC8003406/)). Good for grain storage and palms, not foliar disease.
- **E-nose / VOC** can flag disease *before* symptoms in the lab, but field detection limits sit around **μg/L** (vs pg–ng for lab GC-MS), and most reported devices are bench instruments. **Lab-stage** — not deployable as a farmer-facing feature.
- **Smart sprayers & weeding robots** detect and *act* at machine scale: [DeepWeeds](https://github.com/AlexOlsen/DeepWeeds) (17,509 images, 8 species + negative) benchmarks at **95.7%** (ResNet-50) / **95.1%** (Inception-v3); [John Deere See & Spray](https://www.deere.com/en/sprayers/see-spray-gen-2/) cut herbicide **44–87%** over a 415-acre Iowa State 2024 trial (>$15/acre saved); [Bosch–BASF One Smart Spray](https://www.farmprogress.com/) up to **70%**; [Carbon Robotics LaserWeeder](https://carbonrobotics.com/laserweeder) kills weeds with mm-accurate CO₂ lasers. All **$100k+ capital equipment** — ecosystem context, not a software feature.

---

## The two hard truths (read before believing any vendor demo)

1. **The lab-to-field gap is ~30 percentage points, repeatedly.** 99% on PlantVillage → ~65–75% on real photos is not a one-off; it reproduces across PlantDoc, PlantWild, and cross-domain tests. Any accuracy claim must be sourced from *field* validation, and outputs must be confidence-gated and human-checkable.
2. **Off-site weather ≠ canopy microclimate.** Leaf wetness — the single most important disease-model input — can differ by 2× between a weather station and the inside of the canopy, flipping infection-period verdicts on ~⅓ of nights in the cited study. Weather-*estimated* disease risk is a useful indicator but is not equivalent to a *measured* in-canopy reading.

Both map cleanly onto machinery the codebase already has: a **graded provenance / confidence** field, and a **tiered real-where-available** source pattern.

---

## Feasibility verdict — what is "meaningful and possible"

**Possible now, software-only (no hardware mandate):**
1. **Weather-driven infection / degree-day models (family 4).** Highest ROI, lowest risk, crop-agnostic, buildable from the existing hourly weather feed. Replaces the fabricated humidity proxy and the random-jitter "disease patch" with validated agronomic science (Mills/TOMCAST/Blitecast-class rules), surfaced honestly as a *weather-estimated risk indicator*.
2. **Image-upload detection (family 1).** Smartphone = universal active device; a photo → `{class, confidence, location}` becomes real evidence overriding the heuristic when present — viable only with field-trained data + confidence gating. Drone tiles reuse the same path.

**Possible with optional hardware (a "connected-device" tier):**
3. **Smart-trap / sensor API ingest (family 2).** Real insect counts + *measured* leaf wetness via the FieldClimate REST API → upgrades family-4 models from estimated to measured and replaces the heuristic pest score with observed pressure. Model it as a tiered real-where-available source, exactly like RVI/RSM.

**Real but not a fit now:** smart sprayers / weeding robots (capital equipment); e-nose VOC (lab-stage); acoustic (niche: grain/palm); handheld hyperspectral (specialist — possible future premium proximal tier).

**Cross-cutting constraints:** the lab-to-field gap and canopy-microclimate caveat above; hardware ownership + rural connectivity (one review: only **28%** of smallholders trained on digital tools, **~50%** of farms unconnected; IoT sensors **$500–2,000/ha**) ([PMC12481170](https://pmc.ncbi.nlm.nih.gov/articles/PMC12481170/)); the need for a ground-truth label source to claim accuracy honestly; and uncertainty surfacing — which slots into the existing data-quality/fabrication tracking (PROCESSES §L). The upside is real where deployed: the same review reports an AI pest-prediction deployment cutting crop losses **60% → 20%** and pesticide use **30–40%**.

---

## How each route would touch the system (high-level — *not* an implementation plan)

A single crop-agnostic abstraction unifies all three routes: a **`DetectionEvidence`** with `{kind: pest|disease|weed, label, confidence, source, observed_at, location?}`, where `source ∈ {image_inference, connected_device, weather_model, heuristic}`. The pest/disease/weed assessment then **prefers real evidence over the heuristic**, in priority order — the same override pattern the codebase already uses where real RVI/RSM beat their proxies (PROCESSES §A.4/§A.5).

- **Route 1 (image):** an upload endpoint + an inference adapter producing `image_inference` evidence. *(Serving choice — multimodal LLM vs self-hosted CNN/ViT vs third-party API — deliberately deferred.)*
- **Route 2 (weather science):** pure functions over the existing hourly weather (Mills-style wetness-hours, TOMCAST DSVs, degree-day biofix), emitting `weather_model` evidence. No new dependency, no hardware.
- **Route 3 (device ingest):** an optional FieldClimate (HMAC/OAuth) client emitting `connected_device` evidence + measured leaf wetness that *upgrades* Route 2.
- **Cross-cutting:** extend the fabrication/quality flags to a graded provenance — `detected (image, conf 0.82)` > `measured (in-canopy sensor)` > `modelled (weather)` > `estimated (heuristic)` — and add PROCESSES.md entries when any route is built.

---

## Open questions to resolve *before* any build

1. **Vision serving** — multimodal LLM vs self-hosted CNN/ViT vs third-party API.
2. **Starter pathogen/pest set** — the framework is crop-agnostic, but a first build needs a seed set of weather models and image classes; which?
3. **Ground-truth source** — where do field-labeled validation samples come from, so accuracy is claimed honestly (target the ~65–75% field reality, not 99%)?
4. **Device tier in v1?** — ship Route 3 against the live FieldClimate API, or stub the tier until a grower owns hardware?

---

## Sources (by family, with what each contributed)

**Vision / image:**
[PlantWild in-the-wild benchmark, 18,542 img/89 cls, lab→field −33 pts (arXiv 2408.03120)](https://arxiv.org/html/2408.03120v1) ·
[ViT+Mixture-of-Experts, 0.9996 lab vs 0.74 PlantDoc (PMC12213485)](https://pmc.ncbi.nlm.nih.gov/articles/PMC12213485/) ·
[PMVT mobile ViT, 0.98–5.06 M params (PMC10562605)](https://pmc.ncbi.nlm.nih.gov/articles/PMC10562605/) ·
[Crop-pest DL review / IP102 (arXiv 2507.01494)](https://arxiv.org/pdf/2507.01494) ·
[Mobile CNN benchmark, 101 cls/33 crops (arXiv 2508.10817)](https://arxiv.org/pdf/2508.10817) ·
[Plantix (GSMA)](https://www.gsma.com/solutions-and-impact/connectivity-for-good/mobile-for-development/blog/detecting-and-managing-crop-pests-and-diseases-with-ai-insights-from-plantix/)
**Smart traps:**
[Trap-image counting, 97.89% acc (PMC8068825)](https://pmc.ncbi.nlm.nih.gov/articles/PMC8068825/) ·
[YOLOv9-TrapPest electro-trap, 98.3% mAP50 (PMC11922902)](https://pmc.ncbi.nlm.nih.gov/articles/PMC11922902/) ·
[iSCOUT orchard deployment (dergipark)](https://dergipark.org.tr/en/pub/jaefs/article/1815207) ·
[FieldClimate REST API spec (HMAC/OAuth, DISEASE/DATA routes)](https://api.fieldclimate.com/v1/docs/) ·
[Trapview (CNN)](https://www.cnn.com/2022/11/24/business/trapview-ai-pest-management-spc-intl/index.html) ·
[Semios camera traps](https://semios.com/our-hardware/automated-camera-traps/)
**Proximal optical:**
[Proximal optical stress-sensing review + accuracy table (PMC7760370)](https://pmc.ncbi.nlm.nih.gov/articles/PMC7760370/) ·
[Grapevine virus hyperspectral, 96%/76% (PMC10007312)](https://pmc.ncbi.nlm.nih.gov/articles/PMC10007312/)
**Weather-driven models:**
[Revised Mills table + Cougarblight (PSU Extension)](https://extension.psu.edu/tree-fruit-disease-predicting-infection-periods-to-apply-protection) ·
[Apple scab / RIMpro](https://rimpro.cloud/platform/apple-scab-venturia-inaequalis/) ·
[Downy-mildew in-situ thresholds + canopy-microclimate caveat (PMC9316467)](https://pmc.ncbi.nlm.nih.gov/articles/PMC9316467/) ·
[Late-blight ML, RF 87%/AUC 0.903 (PMC10146589)](https://pmc.ncbi.nlm.nih.gov/articles/PMC10146589/)
**Sensor science:**
[Acoustic stored-product review, 1–2 beetles/kg (PMC8003406)](https://pmc.ncbi.nlm.nih.gov/articles/PMC8003406/) ·
[Red palm weevil fiber-DAS, 99.9% lab (PMC7956387)](https://pmc.ncbi.nlm.nih.gov/articles/PMC7956387/)
**Actuation / weeds:**
[DeepWeeds, 95.7% (GitHub/Olsen 2019)](https://github.com/AlexOlsen/DeepWeeds) ·
[John Deere See & Spray](https://www.deere.com/en/sprayers/see-spray-gen-2/) ·
[Carbon Robotics LaserWeeder](https://carbonrobotics.com/laserweeder)
**Economics / edge:**
[Adoption barriers + impact figures (PMC12481170)](https://pmc.ncbi.nlm.nih.gov/articles/PMC12481170/) ·
[TinyML for smallholders, <256 KB RAM (arXiv 2603.15085)](https://arxiv.org/pdf/2603.15085)
