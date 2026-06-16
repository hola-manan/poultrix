# Paper Reading Log — Active / Proximal Weed-Pest-Disease Detection

Running log of papers read, newest batches appended at the bottom. Each entry: **technique · dataset · key results (numbers) · limitations · link**. Companion to [active_detection_research.md](active_detection_research.md). Reading is continuous until explicitly stopped.

Legend for **Family**: `vision` (image classification/detection) · `trap` (smart traps) · `proximal` (handheld/robot optical) · `weather` (weather-driven DSS) · `sensor` (acoustic/VOC) · `actuation` (sprayers/robots) · `econ` (economics/edge/adoption).

---

## Batch 0 — seed (papers already read in full before the log existed)

### [0.1] Benchmarking In-the-Wild Multimodal Plant Disease Recognition (PlantWild) — 2024
- **Family:** vision · **Technique:** MVPDR — CLIP image features + K-means visual prototypes + textual prototypes, ensembled logits.
- **Dataset:** PlantWild (proposed) 18,542 wild images / 89 classes; vs PlantVillage 54,309/38 (lab), PlantDoc 2,598/27 (wild).
- **Key results:** Lab→field collapse measured directly — DHBP 98.88%→65.92% (−32.96 pts), T-CNN 98.80%→63.61% (−35.19). Best wild fully-supervised 67.2%; zero-shot 32.77% (vs CLIP 25.94%).
- **Limitations:** complex backgrounds/lighting/viewpoint, large intra-class variance, small inter-class discrepancy.
- **Link:** https://arxiv.org/html/2408.03120v1

### [0.2] Plant disease classification in the wild using ViT + Mixture of Experts — 2025
- **Family:** vision · **Technique:** ViT backbone + MoE experts + entropy/orthogonal/usage regularization + Gaussian-noise injection.
- **Dataset:** PlantVillage (54,306/38), PlantDoc (2,598), T-SNE-downsampled PV_200/PV_100.
- **Key results:** PlantVillage 0.9996 acc; PlantDoc 0.74 acc/F1 (best; ViT-Base 0.69, InceptionV3 0.65, EfficientNet 0.59); cross-domain PV_200→PlantDoc 0.68, PV_100→PlantDoc 0.49. Cites prior 99.35%→"below 40%". +20% over baseline ViT.
- **Limitations:** multi-disease-per-image, species transfer untested, MoE compute overhead on mobile.
- **Link:** https://pmc.ncbi.nlm.nih.gov/articles/PMC12213485/

### [0.3] PMVT: lightweight vision transformer for mobile plant disease ID — 2023
- **Family:** vision · **Technique:** MobileViT variant; 7×7 kernels in inverted-residual blocks + CBAM attention + depthwise-separable conv.
- **Dataset:** wheat 4,087/7, coffee ~813/3, rice binary.
- **Key results:** XXS 0.98 M params/0.31 GFLOPs → S 5.06 M/1.59 GFLOPs. Wheat 93.6–94.9%, coffee 85–88%, rice 92–97.7%. Beats MobileNetV3-Small/Large by 1.6–3.4 pts. 81–88 FPS.
- **Limitations:** ViT slower FPS/FLOPs than CNN.
- **Link:** https://pmc.ncbi.nlm.nih.gov/articles/PMC10562605/

### [0.4] Crop Pest Classification Using Deep Learning: A Review — 2025
- **Family:** vision · **Technique:** review of CNN/ViT hybrids, EfficientNetV2, YOLO, attention.
- **Dataset:** IP102 (102 pest classes, hierarchical), Paddy Pest (2022).
- **Key results:** identifies dominant methods; no single SOTA number.
- **Limitations:** class imbalance, fine-grained look-alikes, field-condition variability, sparse rare-species data.
- **Link:** https://arxiv.org/pdf/2507.01494

### [0.5] Mobile-Friendly Deep Learning for Plant Disease Detection (101 classes/33 crops) — 2025
- **Family:** vision · **Technique:** benchmark of MobileNet/EfficientNet/ViT/custom lightweight CNNs for on-phone use.
- **Dataset:** merged public datasets, 101 classes across 33 crops.
- **Key results:** lightweight architectures give best accuracy/efficiency trade-off (specific per-model numbers not extractable from PDF).
- **Link:** https://arxiv.org/pdf/2508.10817

### [0.6] Automatic Pest Counting from Pheromone Trap Images (Matsucoccus thunbergianae) — 2021
- **Family:** trap · **Technique:** object detectors — Faster R-CNN R101, EfficientDet D0/D4, RetinaNet50, SSD MobileNetv2 + image tiling.
- **Dataset:** 50 trap photos, 23,056 insect instances (30/10/10 split).
- **Key results:** 88–90% AP@IoU0.5; **counting accuracy up to 97.89%**; 1.19–14.14 s/image vs 199–501 s manual.
- **Limitations:** images more organized than real field.
- **Link:** https://pmc.ncbi.nlm.nih.gov/articles/PMC8068825/

### [0.7] YOLOv9-TrapPest: machine-vision electro-killing pheromone trap — 2025
- **Family:** trap · **Technique:** YOLOv9 + AKConv backbone + CBAM-PANet neck + FocalNet head; electrocute → image → rotate tray (unattended).
- **Dataset:** 7 moth species, ~1,640 images / ~12,500 specimens.
- **Key results:** **97.5% AP, 96.6% recall, 98.3% mAP50** (vs YOLOv9 93.9%, YOLOv8m 94.2%, Cascade R-CNN 94.4%).
- **Limitations:** wing-fragment false positives, similar-species confusion.
- **Link:** https://pmc.ncbi.nlm.nih.gov/articles/PMC11922902/

### [0.8] AI camera-based pheromone traps in orchards (iMETOS iSCOUT) — 2025
- **Family:** trap · **Technique:** solar camera trap + FieldClimate platform; 3 images/day.
- **Dataset:** 3 Turkish orchards (Mediterranean/continental/transitional); whitefly, medfly, peach twig borer.
- **Key results:** significant regional pest variation (p<0.05); year-round vs brief-summer activity by climate. No AI accuracy reported.
- **Link:** https://dergipark.org.tr/en/pub/jaefs/article/1815207

### [0.9] Pessl FieldClimate REST API (vendor spec, not a paper)
- **Family:** trap/weather · **Technique:** HMAC (SHA-256) or OAuth2; routes USER/SYSTEM/STATION/DATA/FORECAST/DISEASE/CHART.
- **Key results:** `DISEASE` route exposes crop-specific disease-risk models + ETo; `DATA` gives aggregated sensor time-series; leaf-wetness sensor codes present; rate limit currently disabled.
- **Link:** https://api.fieldclimate.com/v1/docs/

### [0.10] Proximal Methods for Plant Stress Detection Using Optical Sensors + ML (review) — 2020
- **Family:** proximal · **Technique:** review of RGB/multispectral/hyperspectral/thermal/fluorescence + SVM/ANN/CNN.
- **Key results:** field accuracies — soybean Fe-chlorosis RGB+DT 99.7%; wheat mildew/rust phone-RGB+RVM 88.89%; sugar-beet Cercospora HSI+SVM 86.42%; cucumber fungal RGB+AlexNet 92.6%; coffee phone-RGB+VGG16 86.51%; barley drought HSI 67.9%; wheat crown rot HSI+ANN 74.14%.
- **Limitations:** low disease specificity, lighting sensitivity, species variability, HSI cost (thousands $), asymptomatic invisible.
- **Link:** https://pmc.ncbi.nlm.nih.gov/articles/PMC7760370/

### [0.11] Detecting Grapevine Virus with Proximal Hyperspectral Sensing — 2023
- **Family:** proximal · **Technique:** ASD FieldSpec HandHeld 2 (325–1075 nm @1 nm) + PLS-DA.
- **Dataset:** 347 vines (173 Pinot Noir, 174 Chardonnay); GLRaV-1 + GVA.
- **Key results:** 96% (red) / 76% (white) at harvest; key bands red-edge 690–730, 550, 650 nm. NOT pre-symptomatic (peaks at harvest).
- **Limitations:** white-cultivar subtle symptoms; senescence degrades April readings; only PLS-DA tested.
- **Link:** https://pmc.ncbi.nlm.nih.gov/articles/PMC10007312/

### [0.12] In-Situ Measurements for Downy Mildew Forecasting (grape) — 2022
- **Family:** weather · **Technique:** in-canopy Testo 174H (T/RH) + PHYTOS 31 leaf-wetness sensors; VitiMeteo/AgroMeteo model.
- **Key results (thresholds):** 50 degree-hour rule (T×wetness duration); min infection 13 °C + 8 mm rain; sporangia die >30 °C for >6 h; wetness threshold ≥460 counts. **Caveat:** off-site station read >900 counts vs canopy ~460; 19 nights canopy never wetted but station signalled daily exceedance; station 3.6 °C cooler / 3.5% wetter by day.
- **Limitations:** station distance + unknown in-canopy microclimate.
- **Link:** https://pmc.ncbi.nlm.nih.gov/articles/PMC9316467/

### [0.13] Predicting Daily Aerobiological Risk of Potato Late Blight (C5.0 + RF) — 2023
- **Family:** weather · **Technique:** C5.0 decision tree + Random Forest on weather + prior sporangia.
- **Dataset:** 586 samples, 5 seasons (2017–21), Galicia Spain; target ARL ≥10 sporangia/m³.
- **Key results:** RF 87% acc / κ 0.70 / sens 0.77 / spec 0.92 / AUC 0.903; C5.0 85% / κ 0.65 / AUC 0.904.
- **Limitations:** needs years of data + on-plot station + specialists.
- **Link:** https://pmc.ncbi.nlm.nih.gov/articles/PMC10146589/

### [0.14] Predicting Tree-Fruit Disease Infection Periods (revised Mills table) — extension
- **Family:** weather · **Technique:** Mills leaf-wetness × temperature lookup; Cougarblight degree-hours for fire blight.
- **Key results:** apple scab leaf-wetness hours — 41 h @6 °C, 11 h @10 °C, 6 h @16–24 °C, 11 h @26 °C. Fire blight via 4-day degree-hour accumulation + orchard history.
- **Link:** https://extension.psu.edu/tree-fruit-disease-predicting-infection-periods-to-apply-protection

### [0.15] DeepWeeds: Multiclass Weed Species Image Dataset — 2019
- **Family:** vision/actuation · **Technique:** ResNet-50 & Inception-v3 baselines.
- **Dataset:** 17,509 images, 8 weed species + negative (9 classes), northern Australia.
- **Key results:** ResNet-50 95.7%, Inception-v3 95.1% top-1.
- **Link:** https://github.com/AlexOlsen/DeepWeeds

### [0.16] Automated Acoustics for Stored-Product Insect Detection (review) — 2021
- **Family:** sensor · **Technique:** piezoelectric/MEMS-mic/accelerometer + bandpass + ANN/CNN/HMM/SVM/MFCC.
- **Key results:** AED 2010L detects 1–2 beetles/kg; banana weevil 90%; TreeVibes wood-borer ~90%; RPW 75–95% (grown) vs 33–39% (early); adult S. oryzae 500–1500 Hz, larval 6–8 kHz; immatures 37× more sounds.
- **Limitations:** "not yet as cost-effective as cell phones"; high variance; env-dependent.
- **Link:** https://pmc.ncbi.nlm.nih.gov/articles/PMC8003406/

### [0.17] Red Palm Weevil via ML + Fiber-Optic Distributed Acoustic Sensing — 2021
- **Family:** sensor · **Technique:** φ-OTDR fiber on date-palm trunks + ANN/CNN.
- **Dataset:** 8,000 examples (infested/healthy); larvae ~12 days, ~400 Hz signal.
- **Key results:** ANN 99.9% / CNN 99.7% acc; one unit monitors ~1,000 trees over ~10 km.
- **Limitations:** lab-validated only; wind-noise; labor-intensive fiber install + annual maintenance.
- **Link:** https://pmc.ncbi.nlm.nih.gov/articles/PMC7956387/

### [0.18] Modern Agricultural Technologies / Adoption (review) — 2025
- **Family:** econ · **Technique:** review.
- **Key results:** IoT sensors $500–2,000/ha; software $500–2,000/yr; autonomous tractors $300–500k; only 28% smallholders (SSA) trained; ~50% farms unconnected. Impact: AI pest prediction cut losses 60%→20% (Maharashtra cotton), pesticide −30–40%; US Midwest precision-N +22% corn, −15% fertilizer.
- **Link:** https://pmc.ncbi.nlm.nih.gov/articles/PMC12481170/

### [0.19] Low-Cost Edge AI & TinyML for Resource-Constrained Farming (review) — 2026
- **Family:** econ · **Technique:** review of MCU/RPi/ESP32/Coral/Jetson + quantization/pruning/distillation.
- **Key results:** TinyML models KB–low-MB, <256 KB RAM, 8-bit quant, 4–8× compression.
- **Link:** https://arxiv.org/pdf/2603.15085

## Batch 1

### [1.1] High-Performance Deep Learning for Instant Pest & Disease Detection — 2025
- **Family:** vision · **Technique:** feature-level fusion of MobileNetV2 + EfficientNetB0 (+ BN, dense, dropout).
- **Dataset:** CCMT — 24,881 original / 102,976 augmented images, 22 classes (cashew, cassava, maize, tomato).
- **Key results:** global acc 89.12% (raw 84.2%); precision/recall 95.68%; F1 95.67%; ROC-AUC 0.95; <10 ms/image inference.
- **Limitations:** visually-similar-class confusion, weak generalization beyond CCMT crops, GPU training needs, lighting/background sensitivity.
- **Link:** https://pmc.ncbi.nlm.nih.gov/articles/PMC12436414/

### [1.2] Review of Current Robotic Approaches for Precision Weed Management — 2022
- **Family:** actuation/vision · **Technique:** review — ML (RF/SVM/KNN/AdaBoost, multi-feature fusion) + DL (CNN/GCN, semantic segmentation, semi-supervised GANs).
- **Datasets:** Weed (6,000 img), Sugar-beets (5 TB RGB/NIR/Lidar), Plant-seedlings (9.7 GB), DeepWeeds (17,509), Grass-clover (31,600 occluded).
- **Key results:** detection — 98.40% (shape+edge), 92.9% @0.02 s, F1 93.59%, 97% hit-rate. Robots: EcoRobotix 20× herbicide cut, AVO 95% cut, LaserWeeder 15–20 ac/day. Early (wk4) weed survival 0.24±0.18 vs late (wk6) 0.54±0.08.
- **Limitations:** illumination/occlusion/growth-stage variability, scarce annotated data, crop-specific designs, high cost, real-time perception-control integration.
- **Link:** https://pmc.ncbi.nlm.nih.gov/articles/PMC9305686/

### [1.3] PDA-YOLO: High-Precision Stored-Grain Insect Pest Detection — 2025
- **Family:** trap/vision · **Technique:** YOLO11n + PoolFormer_C3k2 + AIFI (intra-scale feature interaction) + DMAE (small-target edge).
- **Dataset:** 6,200 images (aug from 2,000), 31,352 instances, 5 stored-grain species.
- **Key results:** mAP@0.5 96.6%, mAP@0.5:0.95 60.4%, F1 93.5%, 9.9 ms/image, 6.9 GFLOPs (+3.3 mAP50 over YOLO11n).
- **Limitations:** controlled collection-bottle environment, 5 species only, weak strict-IoU localization, not yet field-deployed.
- **Link:** https://pmc.ncbi.nlm.nih.gov/articles/PMC12193345/

### [1.4] MRD-LiNet: Lightweight Hybrid CNN + Gradient-Guided Unlearning (drought stress) — 2025
- **Family:** vision · **Technique:** lightweight hybrid CNN with machine-unlearning (gradient-guided feature forgetting) for drought-stress ID.
- **Dataset:** multispectral potato imagery (Idaho Falls Multispectral dataset).
- **Key results:** 90.0% acc; stressed-class F1 0.922, healthy F1 0.874; **0.231 M params (15–60× smaller** than MobileNet 3.5M/88.7%, DenseNet121 7.09M/90.7%, ViT-TL 14M/91.6%). Unlearning least-influential 5% of data lifted stressed recall 0.84→0.87, cut false negatives 119→99.
- **Link:** https://arxiv.org/abs/2509.06367

### [1.5] Integrating UAV Multispectral + Proximal Sensing for Cereal Monitoring — 2025
- **Family:** proximal · **Technique:** DJI P4 Multispectral (5 bands, 20 m, 1.1 cm GSD) + handheld Plant-O-Meter (6 bands); 19 vegetation indices vs yield.
- **Dataset:** 41 cereal genotypes, 130 plots, BBCH 43/49/65/75, single season.
- **Key results:** UAV-vs-handheld Pearson r — GRDVI 0.957, NDVI 0.954, SAVI 0.944; 80% agreement on top-20 genotype ranking.
- **Limitations:** single site/season, registration difficulty, uncontrolled environment.
- **Link:** https://pmc.ncbi.nlm.nih.gov/articles/PMC12097617/

## Batch 2

### [2.1] Active Optics for Hyperspectral Imaging of Reflective Agricultural Leaf Sensors — 2025
- **Family:** proximal · **Technique:** autonomous optical rig — Velodyne HDL-32 LiDAR (locates retroreflective leaf sensors) + monochrome NIR camera + Optotune liquid lens + 6-filter wheel (630/640/650/660/670/680 nm, 10 nm FWHM) + fast steering mirror (±39°); DBSCAN to isolate sensors.
- **Target:** leaf-mounted reflective sensors that modulate hyperspectral signature with water/stress/nutrient state.
- **Key results:** detection range 0.8–2 m; indoor focus/track demo successful.
- **Limitations:** <2 m range (APD LiDAR), ±39° FOV, metallic-surface confusion indoors, DBSCAN needs refinement.
- **Link:** https://arxiv.org/html/2512.10213

### [2.2] Target-to-Sensor Multispectral Device for Leaf-Scale Soybean Phenotyping — 2023
- **Family:** proximal · **Technique:** handheld imager that uses airflow (2 DC fans) to pull a leaf flat to the sensor; 4 bands (460/525/630/850 nm); NDVI vs lab N.
- **Dataset:** greenhouse 20 plants (200/800 ppm N); field (2 varieties × 0/224 kg/ha N).
- **Key results:** greenhouse N-effect p = 5×10⁻⁶ (bottom leaf); field discriminated treatments p = 0.008 **while UAV failed (p = 0.239)**; <5 s/leaf (5× faster than prior).
- **Limitations:** canopy individual variance, greenhouse microclimate, inpainting noise, needs automation for scale.
- **Link:** https://pmc.ncbi.nlm.nih.gov/articles/PMC10098662/

### [2.3] Deep Learning in UAV-Based Imagery for Crop Disease/Pest Detection (review) — 2024
- **Family:** vision/proximal · **Technique:** review — RGB/multispectral/hyperspectral/thermal UAV + LeNet/U-Net/VGG/YOLO/HRNet (+ emerging GPT-4/LVM).
- **Key results (named studies):** Ginkgo VGG16/InceptionV3 98.5% lab / 92.19% field; apple leaf VGG16 99.01%; apple fire blight RF 94.0%; rice leaf blast 98.58%; banana yellow-leaf SVM 99.28%; pumpkin powdery mildew 89% early / 96% late; soybean blight LeNet 99.32%; cassava improved-U-Net 83.9%; coffee rust LMT 91.5%; tomato leaf-miner GA-BPNN 93.33%; wheat YOLOPC+GPT-4 90% report reasoning.
- **Limitations:** resolution, compute (the DL "bottleneck"), spectral shift train↔test, annotation cost, subtle early-stage disease; **no quantified pre-symptomatic lead-time** given.
- **Link:** https://www.frontiersin.org/journals/plant-science/articles/10.3389/fpls.2024.1435016/full

### [2.4] RoMu4o: Robotic Unit Automating Proximal Hyperspectral Leaf Sensing — 2025
- **Family:** proximal/actuation · **Technique:** ground robot, 6-DOF arm + DL vision motion planning + hyperspectral end-effector (own lighting) for leaf-level sampling.
- **Key results:** sampling success 95% (lab) / 79% (field); autonomous leaf-grasp + measurement 70% in pistachio orchard.
- **Limitations:** 25-pt lab→field gap; unstructured-orchard complexity.
- **Link:** https://arxiv.org/abs/2501.10621

### [2.5] Detecting Plant VOC Traces Using Indoor Air Quality Sensors — 2025
- **Family:** sensor · **Technique:** low-cost commercial IAQ/gas sensors + ML classifier (physics-based models deemed insufficient).
- **Dataset:** living basil; 16 terpenes in controlled tests.
- **Key results:** "successfully detected terpene output" — no accuracy/detection-limit numbers in abstract; pre-symptomatic not addressed.
- **Limitations:** single-plant validation, commercial (not lab) sensors, real-world complexity.
- **Link:** https://arxiv.org/abs/2504.03785

### [2.6] Detection of Healthy and Diseased Crops in Drone Images using Deep Learning — 2023
- **Family:** vision · **Technique:** CNN image classification on internet-compiled crop-disease DB; prototype drone deployment.
- **Key results:** abstract gives no accuracy/precision/recall numbers.
- **Limitations:** unvalidated internet dataset, generalization to real fields under "challenging imaging conditions."
- **Link:** https://arxiv.org/abs/2305.13490

## Batch 3

### [3.1] Integrating UAVs, Satellite RS, and ML in Precision Agriculture (review) — 2025
- **Family:** vision/econ · **Technique:** review of UAV(0.1–5 cm)+satellite(10–30 m) fusion + CNN/RNN/SVM/Faster-R-CNN.
- **Key results:** disease >95% (tomato Botrytis, wheat powdery mildew, grape downy mildew); outbreak prediction 81–95% at **2–3 weeks pre-symptom**; weed discrimination **99.2%** (UAV-sat fusion), Faster-R-CNN+federated 99%. **Cross-region transfer cost: 12–18% accuracy loss** (US Corn Belt→East-African smallholder); sensor drift ±5–15%.
- **Limitations:** 50–200 h GPU/model, 10–100 TB/season, 16–32 GB GPU, UAV $500–2,000/km², connectivity + skills gaps for smallholders.
- **Link:** https://www.frontiersin.org/journals/agronomy/articles/10.3389/fagro.2025.1670380/full

### [3.2] PlantInfoCMS: Scalable Plant Disease Dataset Collection/Management — 2023
- **Family:** vision · **Technique:** annotation+QC platform (≥2 expert inspectors, third resolves disputes); rectangle + polygon labels.
- **Dataset:** 301,667 original / 195,124 labeled images, **32 crops, 185 pest/disease classes**.
- **Key results:** infrastructure paper — authors "have not yet systematically validated" a diagnostic model's accuracy.
- **Limitations:** image-only (no weather/soil/growth context), no severity staging.
- **Link:** https://pmc.ncbi.nlm.nih.gov/articles/PMC10255502/

## Batch 4

### [4.1] Multi-prediction Deep Learning for Plant ID + Disease (GSMo-CNN) — 2023
- **Family:** vision · **Technique:** Generalised Stacking Multi-output CNN (GSMo-CNN), InceptionV3 backbone; multi-model/label/output/task framing.
- **Dataset:** PlantVillage, Plant Leaves, PlantDoc.
- **Key results:** InceptionV3 beat AlexNet/VGG16/ResNet101/EfficientNet/MobileNet/custom; single model ≈ or > two models; "SOTA on three benchmarks" (specific % not in abstract).
- **Limitations:** cross-study comparison still hampered by varied datasets.
- **Link:** https://arxiv.org/abs/2310.16273

### [4.2] Leaf Disease ID using Color + Texture (GLCM) Features — 2021
- **Family:** vision · **Technique:** 6 color + 22 GLCM texture features + one-vs-one SVM (lightweight, mobile-oriented).
- **Key results:** 98.79% (±0.57) on 10-fold CV, but **82.47% on self-collected field data**; 91.40% healthy-vs-diseased. Another explicit lab→field drop.
- **Limitations:** self-collected performance far below CV; handcrafted-feature ceiling.
- **Link:** https://arxiv.org/abs/2102.04515

### [4.3] AI in Agriculture: Survey of DL for Crops/Fisheries/Livestock — 2025
- **Family:** vision/econ · **Technique:** systematic review of 200+ works — classical ML, DL, ViT, vision-language (CLIP) foundation models.
- **Key results:** narrative survey; flags datasets/metrics/geographic-focus variability as core problems.
- **Future directions:** multimodal fusion, efficient edge deployment, domain-adaptable models.
- **Link:** https://arxiv.org/abs/2507.22101

## Batch 5 — degree-day pest models · leaf-wetness ML · pre-symptomatic HSI · IoT/edge

### [5.1] Degree-Day Phenological Model for Codling Moth, Mediterranean validation — 2018
- **Family:** weather/pest · **Technique:** 3-parameter non-linear regression of cumulative pheromone-trap catch vs accumulated degree-days; biofix = Jan 1, lower threshold 10.1 °C.
- **Dataset:** apple orchards, Greece, 2011–2014.
- **Key results:** R² > 0.9 for all three male flights. 1st-generation first males 250–300 DD (peak 468 DD); 2nd-flight first males 850–900 DD (peak 1130 DD).
- **Limitations:** local calibration; trap-catch as development proxy.
- **Link:** https://www.researchgate.net/publication/324692150
- *Cross-ref:* WSU operational rule — first cover spray at **250 DD after biofix ≈ 3% egg hatch**; biofix = first trap catch (or calendar date). WSU models 15+ tree-fruit pests (incl. apple scab, fireblight, oriental fruit moth, leafrollers). https://treefruit.wsu.edu/crop-protection/opm/dd-models/

### [5.2] Estimating Leaf Wetness Duration with ML + Climate Reanalysis — 2021
- **Family:** weather · **Technique:** Random Forest, kernel SVM, feed-forward NN, CART on hourly ERA5/MERRA2 reanalysis; vs empirical RH≥90% / dew-point-depression baselines.
- **Dataset:** 3 yr hourly leaf-wetness obs, 9 sites Alabama + 6 sites California.
- **Key results:** ML(ERA5) beats MERRA2-based and the observation-based RH model; all three ML methods beat CART on daily-RMSE. (Related multi-step ML LWD work reports hybrid R² ≈ 0.89 validation.)
- **Limitations:** reanalysis grid vs in-canopy microclimate (cf. [0.12] downy-mildew caveat); site-specific sensor calibration.
- **Link:** https://www.sciencedirect.com/science/article/abs/pii/S016819232100232X · multi-step: https://www.sciencedirect.com/science/article/abs/pii/S0168169924005222

### [5.3] Hyperspectral Pre-Symptomatic Detection of Tomato Bacterial Leaf Spot — 2024
- **Family:** proximal · **Technique:** RESONON Pika L (400–1000 nm, 300 bands) + Pika NIR320 (900–1700 nm, 168 bands); 7 classifiers (LDA/SVM/KNN/RF/GBM/MLP/XGBoost) on raw spectra vs vegetation indices.
- **Key results:** spectral difference detectable **2 h after inoculation**; pre-symptomatic separation at **1–3 dai**. But generalization modest — leaf-level LDA 0.74 (mid-stage), pixel-level RF 0.63±0.13 (VISNIR @7 dai); VIs improved performance 26–37%. Key bands 740–750 nm + 1400 nm (early).
- **Limitations:** detached-leaf training → poor transfer to living plants; small sample; background sensitivity; "model not able to generalize to leave-out test."
- **Link:** https://pmc.ncbi.nlm.nih.gov/articles/PMC11557939/

### [5.4] Pre-Symptomatic Detection Lead-Times (HSI, multi-study synthesis)
- **Family:** proximal · **Technique:** hyperspectral imaging capturing transpiration/pigment changes before visible lesions.
- **Key results (lead-times):** grapevine downy mildew detected **2 dpi vs symptoms at 4 dpi** (2 days early); tomato fungal — *A. alternata*/*B. cinerea* reliable by Day 3 (symptoms Day 5), *A. solani*/*F. oxysporum* by Day 5 (symptoms Day 7); potato **late vs early blight pre-symptomatically differentiated** by contrasting physiological signatures.
- **Limitations:** controlled/inoculated conditions; lead-time shrinks in the field; HSI cost.
- **Links:** potato https://www.mdpi.com/2072-4292/12/2/286 · grapevine https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9456054/

### [5.5] AI + IoT Edge Device for Crop Pest & Disease Detection — 2025
- **Family:** vision/econ · **Technique:** Tiny-LiteNet (MobileNetV2 teacher → SE-depthwise student, knowledge distillation) on Raspberry Pi 5; solar + Li battery + GSM/GPRS; humidity/temp/rain sensors.
- **Dataset:** 23,100 images — 12,400 pest/5 classes + 10,700 disease/4 classes (PlantVillage + field).
- **Key results:** **1.48 M params / 1.2 MB; 98.6% acc, F1 98.4%, 16 ms inference on-device, 4.7 W**.
- **Limitations:** rule-based (preprogrammed) advice text; PlantVillage-sourced training → lab-bias risk; field-deployment metrics not given.
- **Link:** https://pmc.ncbi.nlm.nih.gov/articles/PMC12216444/

## Batch 6 — real-time weeds · thermal/CWSI · wheat rust · domain adaptation · rice UAV

### [6.1] YOLO- vs Transformer-based Real-Time Weed Detection — 2025
- **Family:** vision/actuation · **Technique:** YOLOv8/v9/v10 (5 sizes each) vs RT-DETR-l/x.
- **Dataset:** 5,611 field images, 3 crops (sunflower/wheat/maize) + 13 weed species.
- **Key results:** species-level mAP50 70.8–73.5%, grouped mAP50 76.1–79.9%, mAP50-95 42–47%; RT-DETR-l best precision 82.44%. Speed YOLOv8n 7.6 ms → YOLOv9e 32 ms (RTX 4090); CPU 15× slower.
- **Limitations:** **~80% "inadequate for mechanical hoeing"**; thin grass weeds (Setaria) missed; DETR weak on small objects; lighting/soil untested.
- **Link:** https://arxiv.org/abs/2501.17387

### [6.2] Recent AI Methods for Crop Water Stress (review) — 2024
- **Family:** proximal/weather · **Technique:** review; CWSI = (Tl − Twet)/(Tdry − Twet) from canopy-air ΔT + VPD; thermal (3–14 µm) ground/UAV + CNN/SVM/GAN.
- **Key results:** maize GoogLeNet 97.9%, winter-wheat ResNet50 (thermal) 98.4%, rice ANN 99.4%, wheat CNN-LSTM 100%, cotton MobileNetV3 F1 0.999, potato XGBoost 99.7%.
- **Limitations:** canopy/soil temperature mixing, RGB needs fixed lighting, thermal cost, multispectral misses early stress.
- **Link:** https://pmc.ncbi.nlm.nih.gov/articles/PMC11478660/

### [6.3] Wheat Yellow Rust Recognition from UAV (PSPNet) — 2021
- **Family:** vision · **Technique:** PSPNet + ResNet34 semantic segmentation (vs SVM/RF/BPNN/FCN/U-Net); weakly-supervised SVM→PSPNet variant.
- **Dataset:** 5,580 patches (256², UAV RGB), Henan China; classes healthy/rust/soil; 30 m alt, 0.7 cm/px.
- **Key results:** PSPNet 98% acc / κ 0.96 / mIoU 89% (rust F1 0.80); generalization plot 2,688 m².
- **Limitations:** imaged at plucking stage (low rust visibility); single crop/disease; suggests hyperspectral next.
- **Link:** https://pmc.ncbi.nlm.nih.gov/articles/PMC8513082/

### [6.4] MSUN: Unsupervised Domain Adaptation Lab→Field — 2023  ⭐ gap-closing
- **Family:** vision · **Technique:** nonadversarial UDA — multi-representation (1×1/3×3/5×5) + subdomain LMMD alignment + entropy/uncertainty regularization.
- **Dataset:** source PlantVillage (54,306/38) → targets PlantDoc (5,601/27), apple PPD (3,385/3), corn CLD (4,547/4), tomato TLD (2,908/5).
- **Key results:** lab→field gap closed substantially — apple 39.27%→72.31% (+33pp), corn 75.96%→96.78% (+21pp), tomato 21.46%→50.58% (+29pp), multi-species PlantDoc 30.78%→56.06% (+25pp). Beats DAN/D-CORAL/DANN/DAAN/DSAN/MRAN.
- **Limitations:** still ~50–56% on high-variety multi-species; pseudo-label uncertainty under high intra-class variation.
- **Link:** https://pmc.ncbi.nlm.nih.gov/articles/PMC10059679/

### [6.5] Field-Scale Rice Bacterial Leaf Blight via UAV Multispectral — 2024
- **Family:** vision · **Technique:** U-Net + ResNet101 (vs MobileNetV2, DeepLabV3+); DJI P4 Multispectral (6 bands), 20 m alt; MS + NDVI/NDRE.
- **Dataset:** 234 diseased + 36 healthy subplots, central Thailand (inoculation-induced BLB); 1,857 patches.
- **Key results:** best (MS+NDVI) mIoU 97.20%, acc 99.42%, F1 98.56%, precision 97.97%, recall 99.16%; 1.04 s/iter.
- **Limitations:** inoculation-induced (not natural epidemic); limited dataset diversity.
- **Link:** https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0314535

<!-- APPEND-NEW-BATCHES-BELOW -->
