"""
Pest, disease, and weed risk assessment based on environmental conditions
"""

from typing import Dict, Any, List, Optional

from jeevn.domain.crop_health.disease_models import (
    gubler_powdery_mildew_index,
    downy_mildew_wet_period_risk,
)

# Map a downy-mildew categorical risk level to a representative percentage so
# it can share the report's numeric `risk_percent` column. The hedged
# rationale + confidence travel alongside as separate fields.
_DOWNY_LEVEL_TO_PCT = {"high": 75, "moderate": 50, "low": 20}


class PestDiseaseWeedAssessor:
    """Assess risk of pests, diseases, and weeds"""

    PEST_DATABASE = {
        "apple": {
            "pests": [
                {
                    "name": "Spider Mites",
                    "category": "pest",
                    "temperature_range": (20, 40),
                    "humidity_impact": "low_humidity_increases_risk",
                    "rvi_risk_factor": lambda rvi: 0.6 + (rvi * 0.5),
                    "stage_susceptibility": {"flowering": 1.2, "fruit_set": 1.1, "fruitgrowth": 0.9},
                    "organic_solution": "Neem oil spray",
                    "chemical_solution": "Abamectin"
                },
                {
                    "name": "Powdery Mildew",
                    "category": "disease",
                    "temperature_range": (15, 25),
                    "humidity_impact": "high_humidity_increases_risk",
                    "rvi_risk_factor": lambda rvi: 0.5 + (rvi * 0.4),
                    "stage_susceptibility": {"flowering": 1.1, "fruit_set": 1.0},
                    "organic_solution": "Sulfur dust",
                    "chemical_solution": "Myclobutanil"
                },
                {
                    "name": "Codling Moth",
                    "category": "pest",
                    "temperature_range": (10, 30),
                    "humidity_impact": "moderate",
                    "rvi_risk_factor": lambda rvi: 0.3 + (rvi * 0.3),
                    "stage_susceptibility": {"fruit_set": 1.2, "fruitgrowth": 1.0},
                    "organic_solution": "Pheromone traps",
                    "chemical_solution": "Chlorantraniliprole"
                },
                {
                    "name": "Alternaria Leaf Spot",
                    "category": "disease",
                    "temperature_range": (15, 30),
                    "humidity_impact": "high_humidity_increases_risk",
                    "rvi_risk_factor": lambda rvi: 0.4 + (rvi * 0.3),
                    "stage_susceptibility": {"flowering": 1.2, "fruit_set": 1.1, "fruitgrowth": 0.8},
                    "organic_solution": "Bordeaux mixture",
                    "chemical_solution": "Mancozeb spray"
                }
            ],
            "weeds": [
                {
                    "name": "Bermuda Grass",
                    "category": "weed",
                    "moisture_trigger": 0.7,
                    "rvi_impact": lambda rvi: 0.6 - (rvi * 0.3),
                    "organic_solution": "Manual hoeing",
                    "chemical_solution": "Glyphosate"
                },
                {
                    "name": "Chenopodium album",
                    "category": "weed",
                    "moisture_trigger": 0.65,
                    "rvi_impact": lambda rvi: 0.5 - (rvi * 0.2),
                    "organic_solution": "Organic mulching",
                    "chemical_solution": "Paraquat dichloride"
                }
            ]
        },
        "wheat": {
            "pests": [
                {
                    "name": "Armyworm",
                    "category": "pest",
                    "temperature_range": (15, 30),
                    "humidity_impact": "high_humidity_increases_risk",
                    "rvi_risk_factor": lambda rvi: 0.4 + (rvi * 0.4),
                    "stage_susceptibility": {"tillering": 1.2, "booting": 1.1},
                    "organic_solution": "Spinosad",
                    "chemical_solution": "Flubendiamide"
                }
            ],
            "weeds": [
                {
                    "name": "Phalaris minor",
                    "category": "weed",
                    "moisture_trigger": 0.6,
                    "rvi_impact": lambda rvi: 0.7 - (rvi * 0.3),
                    "organic_solution": "Manual weeding",
                    "chemical_solution": "Fenoxaprop-ethyl"
                }
            ]
        },
        # Grape — the pilot crop. Powdery + downy mildew are computed by the
        # weather-driven models in `crop_health.disease_models` (flagged with
        # a `model` key), NOT the generic susceptibility heuristic. See the
        # go/no-go: powdery (Gubler-Thomas) is a confident temperature-driven
        # alert; downy is a hedged regional wet-period flag.
        "grape": {
            "pests": [
                {
                    "name": "Powdery Mildew",
                    "category": "disease",
                    "model": "gubler_powdery",
                    "organic_solution": "Wettable/dusting sulfur or potassium bicarbonate",
                    "chemical_solution": "Myclobutanil or trifloxystrobin (rotate FRAC groups)"
                },
                {
                    "name": "Downy Mildew",
                    "category": "disease",
                    "model": "downy_wet_period",
                    "organic_solution": "Copper hydroxide applied ahead of a forecast wet window",
                    "chemical_solution": "Metalaxyl-M + mancozeb on a confirmed infection period"
                },
                {
                    "name": "Grape Mealybug",
                    "category": "pest",
                    "temperature_range": (24, 32),
                    "humidity_impact": "moderate",
                    "stage_susceptibility": {"fruit_set": 1.2, "fruitgrowth": 1.1},
                    "organic_solution": "Release Cryptolaemus; spot-treat with neem oil",
                    "chemical_solution": "Buprofezin (avoid during harvest pre-interval)"
                }
            ],
            "weeds": [
                {
                    "name": "Bermuda Grass",
                    "category": "weed",
                    "moisture_trigger": 0.65,
                    "rvi_impact": lambda rvi: 0.6 - (rvi * 0.3),
                    "organic_solution": "Inter-row mowing + mulch under vines",
                    "chemical_solution": "Glyphosate (directed, shielded spray)"
                }
            ]
        }
    }

    @staticmethod
    def assess_pest_disease_risk(aoi_data: Dict[str, Any], ndvi_data: Dict[str, Any]) -> Dict[str, Any]:
        crop_name = aoi_data.get("crop_name", "apple")
        weather = aoi_data.get("weather", {}).get("daily", {})
        growth_stage = aoi_data.get("current_growth_stage", {}).get("stage", "initial")

        temp_mean = weather.get("temp_mean", [30])[-1] if weather.get("temp_mean") else 30
        temp_max = weather.get("temp_max", [35])[-1] if weather.get("temp_max") else 35
        rainfall = weather.get("rainfall", [0])[-1] if weather.get("rainfall") else 0

        # Real measured RH (last-24h mean from Open-Meteo) when available;
        # otherwise fall back to the coarse legacy proxy and flag it estimated
        # so the UI/PDF can label it honestly.
        rh_real = weather.get("relative_humidity_mean")
        if rh_real is not None:
            humidity = round(float(rh_real), 0)
            humidity_estimated = False
        else:
            humidity = round(min(100, 40 + (rainfall * 2) + (30 - temp_mean) * 2), 0)
            humidity_estimated = True

        # Hourly series for the weather-driven disease models — prefer the
        # forward forecast (actionable "this week" window), fall back to the
        # recent archive. None when neither feed has hourly data.
        hourly = PestDiseaseWeedAssessor._select_hourly(aoi_data)

        rvi = ndvi_data["rvi"]
        rsm = ndvi_data["rsm"]

        crop_lower = crop_name.lower()
        crop_pests = PestDiseaseWeedAssessor.PEST_DATABASE.get(crop_lower, {})

        assessment = {
            "environmental_conditions": {
                "temperature": round(temp_mean, 1),
                "temperature_max": round(temp_max, 1),
                "rainfall_mm": round(rainfall, 1),
                # `humidity_estimate` kept as the value key for backward-compat
                # with existing UI/PDF readers; `humidity_estimated` says
                # whether it is the measured value or the fallback proxy.
                "humidity_estimate": humidity,
                "humidity_estimated": humidity_estimated,
                "rvi": round(rvi, 2),
                "rsm": round(rsm, 2),
                "rsm_source": ndvi_data.get("rsm_source") or "fabricated",
                "rsm_pass_date": ndvi_data.get("rsm_pass_date"),
                "growth_stage": growth_stage
            },
            "pests_diseases": [],
            "weeds": [],
            "summary": {
                "high_risk_count": 0,
                "moderate_risk_count": 0,
                "low_risk_count": 0
            }
        }

        for pest_disease in crop_pests.get("pests", []):
            if pest_disease.get("model"):
                entry = PestDiseaseWeedAssessor._assess_model_disease(pest_disease, hourly)
                if entry is None:
                    # Hourly weather unavailable — omit the row rather than
                    # present a fabricated risk (trust-pass principle).
                    continue
            else:
                risk_score = PestDiseaseWeedAssessor._calculate_pest_disease_risk(
                    pest_disease, temp_mean, humidity, growth_stage
                )
                risk_level = "high" if risk_score >= 70 else "moderate" if risk_score >= 40 else "low"
                entry = {
                    "name": pest_disease["name"],
                    "category": pest_disease["category"],
                    "risk_percent": risk_score,
                    "risk_level": risk_level,
                    "organic_solution": pest_disease.get("organic_solution", "Not available"),
                    "chemical_solution": pest_disease.get("chemical_solution", "Not available")
                }

            assessment["summary"][f"{entry['risk_level']}_risk_count"] += 1
            assessment["pests_diseases"].append(entry)

        for weed in crop_pests.get("weeds", []):
            risk_score = PestDiseaseWeedAssessor._calculate_weed_risk(
                weed, humidity, rsm, rvi, rainfall
            )

            risk_level = "high" if risk_score >= 60 else "moderate" if risk_score >= 35 else "low"
            assessment["summary"][f"{risk_level}_risk_count"] += 1

            assessment["weeds"].append({
                "name": weed["name"],
                "category": "weed",
                "risk_percent": risk_score,
                "risk_level": risk_level,
                "organic_solution": weed.get("organic_solution", "Not available"),
                "chemical_solution": weed.get("chemical_solution", "Not available")
            })

        assessment["pests_diseases"].sort(key=lambda x: x["risk_percent"], reverse=True)
        assessment["weeds"].sort(key=lambda x: x["risk_percent"], reverse=True)

        return assessment

    @staticmethod
    def _select_hourly(aoi_data: Dict[str, Any]) -> Optional[Dict[str, List]]:
        """Pick the hourly weather series that drives the disease models.

        Prefers the forward `forecast` block (the actionable "this week"
        window) over the historical `weather` archive. Returns None when
        neither feed supplied hourly data (e.g. fabricated weather) — callers
        then omit model-driven diseases rather than fabricate a risk.
        """
        for key in ("forecast", "weather"):
            block = aoi_data.get(key) or {}
            hourly = block.get("hourly") or {}
            temps = hourly.get("temperature_2m") or []
            if temps:
                return {
                    "time": hourly.get("time") or [],
                    "temperature_2m": temps,
                    "relative_humidity_2m": hourly.get("relative_humidity_2m") or [],
                    "precipitation": hourly.get("precipitation") or [],
                }
        return None

    @staticmethod
    def _assess_model_disease(pest_disease: Dict[str, Any],
                              hourly: Optional[Dict[str, List]]) -> Optional[Dict[str, Any]]:
        """Build a report row for a model-driven disease (Gubler powdery /
        downy wet-period). Returns None if no hourly data is available."""
        if not hourly:
            return None

        model = pest_disease["model"]
        entry = {
            "name": pest_disease["name"],
            "category": "disease",
            "model": model,
            "organic_solution": pest_disease.get("organic_solution", "Not available"),
            "chemical_solution": pest_disease.get("chemical_solution", "Not available"),
        }

        if model == "gubler_powdery":
            r = gubler_powdery_mildew_index(hourly["time"], hourly["temperature_2m"])
            entry.update({
                "risk_percent": r["index"],
                "risk_level": r["risk_level"],
                "spray_interval_days": r["spray_interval_days"],
                "rationale": r["rationale"],
            })
            return entry

        if model == "downy_wet_period":
            r = downy_mildew_wet_period_risk(
                hourly["time"], hourly["temperature_2m"],
                hourly["relative_humidity_2m"], hourly["precipitation"],
            )
            entry.update({
                "risk_percent": _DOWNY_LEVEL_TO_PCT[r["risk_level"]],
                "risk_level": r["risk_level"],
                "favorable": r["favorable"],
                "confidence": r["confidence"],
                "rationale": r["rationale"],
            })
            return entry

        return None

    @staticmethod
    def _calculate_pest_disease_risk(pest_disease: Dict[str, Any],
                                     temp: float, humidity: float,
                                     growth_stage: str) -> float:
        # Canopy vigor (RVI) was previously weighted at 25% of disease risk —
        # agronomically unjustified, so it is dropped. The remaining drivers
        # (temperature suitability, humidity, growth-stage susceptibility) are
        # re-weighted to keep the 0-100 scale and the 70/40 risk thresholds.
        score = 0

        temp_range = pest_disease.get("temperature_range", (15, 30))
        if temp_range[0] <= temp <= temp_range[1]:
            temp_score = 100 - abs(temp - (temp_range[0] + temp_range[1]) / 2) * 5
            score += temp_score * 0.40
        else:
            score += 0

        humidity_impact = pest_disease.get("humidity_impact", "moderate")
        if humidity_impact == "high_humidity_increases_risk":
            score += (humidity / 100) * 35
        elif humidity_impact == "low_humidity_increases_risk":
            score += ((100 - humidity) / 100) * 35
        else:
            score += 17.5

        stage_susc = pest_disease.get("stage_susceptibility", {})
        stage_factor = stage_susc.get(growth_stage, 0.7)
        score += stage_factor * 25

        return min(100, max(0, score))

    @staticmethod
    def _calculate_weed_risk(weed: Dict[str, Any],
                             humidity: float, rsm: float,
                             rvi: float, rainfall: float) -> float:
        score = 0

        moisture_threshold = weed.get("moisture_trigger", 0.65)
        if rsm > moisture_threshold:
            moisture_score = ((rsm - moisture_threshold) / (1 - moisture_threshold)) * 40
            score += moisture_score

        score += min(20, (rainfall / 20) * 20)

        rvi_impact = weed.get("rvi_impact", lambda x: 0.5)
        score += max(0, (1 - rvi_impact(rvi)) * 40)

        return min(100, max(0, score))

    @staticmethod
    def get_management_recommendations(assessment: Dict[str, Any]) -> List[Dict[str, Any]]:
        recommendations = []

        high_risk = [x for x in assessment["pests_diseases"] if x["risk_level"] == "high"]
        if high_risk:
            recommendations.append({
                "priority": "HIGH",
                "threats": [x["name"] for x in high_risk],
                "recommendations": [
                    {
                        "threat": threat["name"],
                        "approach": "Preventive monitoring" if threat["risk_percent"] < 85 else "Active management",
                        "organic": threat["organic_solution"],
                        "chemical": threat["chemical_solution"],
                        "frequency": "Weekly monitoring" if threat["risk_percent"] < 85 else "Twice weekly"
                    } for threat in high_risk
                ]
            })

        high_risk_weeds = [x for x in assessment["weeds"] if x["risk_level"] == "high"]
        if high_risk_weeds:
            recommendations.append({
                "priority": "HIGH",
                "threats": [x["name"] for x in high_risk_weeds],
                "recommendations": [
                    {
                        "threat": weed["name"],
                        "approach": "Manual removal + chemical control",
                        "organic": weed["organic_solution"],
                        "chemical": weed["chemical_solution"],
                        "timing": "Before flowering stage"
                    } for weed in high_risk_weeds
                ]
            })

        recommendations.append({
            "priority": "ONGOING",
            "recommendations": [
                "Scout fields twice weekly during high-risk periods",
                "Maintain proper canopy management for air circulation",
                "Remove infested plant material promptly",
                "Rotate chemical active ingredients to prevent resistance",
                "Keep weather records for future prediction models"
            ]
        })

        return recommendations
