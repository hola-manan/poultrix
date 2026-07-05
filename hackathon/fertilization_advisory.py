import math
from dataclasses import dataclass
from typing import Dict, List

@dataclass
class NutrientProfile:
    # How much N, P, K (in kg) is extracted to produce 1 ton of yield
    nitrogen_per_ton: float
    phosphorus_per_ton: float
    potassium_per_ton: float

@dataclass
class CropData:
    name: str
    optimal_yield_tons: float
    extraction_rate: NutrientProfile
    # Dictionary mapping phase name to (end_day, percentage_of_total_need)
    # e.g., "seedling": (25, 0.10) means seedling phase ends on day 25 and needs 10% of total N
    nitrogen_curve: Dict[str, tuple[int, float]] 
    sowing_date_offset: int # Days since sowing

@dataclass
class SoilHealthCard:
    nitrogen_kg: float
    phosphorus_kg: float
    potassium_kg: float
    ph_level: float
    organic_carbon_percent: float

def get_total_crop_need(crop: CropData) -> float:
    """Calculates total Nitrogen needed for the entire season based on optimal yield."""
    return crop.optimal_yield_tons * crop.extraction_rate.nitrogen_per_ton

def get_current_phase_demand(crop: CropData, current_day: int) -> float:
    """
    Calculates the daily Nitrogen demand based on exactly where the crop is 
    in its growth curve today.
    """
    total_need = get_total_crop_need(crop)
    previous_phase_end = 0
    
    for phase_name, (end_day, percentage) in crop.nitrogen_curve.items():
        if current_day <= end_day:
            days_in_phase = end_day - previous_phase_end
            phase_total_need = total_need * percentage
            daily_need = phase_total_need / days_in_phase
            return daily_need
        previous_phase_end = end_day
        
    return 0.0 # Crop has reached maturity/harvest

def calculate_piston_flow_leaching(
    current_moisture_mm: float, 
    rainfall_mm: float, 
    field_capacity_mm: float, 
    current_nitrogen_kg: float
) -> float:
    """
    Simplified Piston-Flow model (DSSAT/APSIM style) for Nitrogen Leaching.
    Calculates exactly how many kg of Nitrogen wash below the root zone.
    """
    new_moisture = current_moisture_mm + rainfall_mm
    
    if new_moisture <= field_capacity_mm:
        return 0.0 # Soil absorbed all rain, zero leaching.
        
    drainage_mm = new_moisture - field_capacity_mm
    n_concentration = current_nitrogen_kg / new_moisture
    return drainage_mm * n_concentration

def calculate_phosphorus_availability(soil_ph: float, total_p_kg: float) -> float:
    """
    Geochemical buffer curve approximation (Troug's Diagram).
    Uses a bell curve centered at optimal pH 6.5.
    """
    optimal_ph = 6.5
    # Variance controls how wide the "safe" pH band is
    variance = 1.2 
    
    # Calculate availability percentage using a Gaussian-like curve
    availability_pct = math.exp(-0.5 * ((soil_ph - optimal_ph) / variance) ** 2)
    
    # Cap at max 95% availability in perfect conditions
    availability_pct = min(0.95, availability_pct) 
    
    return total_p_kg * availability_pct

def simulate_volatilization_loss(
    max_temp_c: float, 
    days_since_application: int, 
    rainfall_since_app_mm: float,
    application_method: str = "surface_broadcast"
) -> float:
    """
    Simplified ALFAM-style Volatilization Model.
    Factors in application method (injection vs broadcast) and temperature kinetics.
    """
    if application_method in ["incorporated", "injected", "fertigation"]:
        return 0.0 # No exposure to air = no volatilization
        
    if rainfall_since_app_mm > 15:
        return 0.0 # Sufficient rain washed the urea into the soil profile
        
    # Urease enzyme kinetics accelerate with temperature
    # Base loss rate increases by 2% per degree above 15C
    base_loss_pct_per_day = 0.05 
    if max_temp_c > 15:
        base_loss_pct_per_day += (max_temp_c - 15) * 0.02
        
    total_loss_pct = base_loss_pct_per_day * days_since_application
    
    # Cannot lose more than 50% in standard conditions
    return min(0.50, total_loss_pct)

def generate_fertilizer_advisory(
    crop: CropData, 
    soil: SoilHealthCard, 
    current_moisture_mm: float,
    field_capacity_mm: float,
    recent_rainfall_mm: float,
    recent_max_temp_c: float,
    applied_urea_kg: float,
    days_since_urea_app: int,
    urea_application_method: str,
    applied_p_fertilizer_kg: float
) -> str:
    """
    Generates a real-time advisory balancing soil reserves, demand, and loss mechanisms (Leaching, Volatilization, Fixation).
    """
    alerts = []
    
    # --- NITROGEN LOGIC (Leaching & Volatilization) ---
    available_n = soil.nitrogen_kg + (applied_urea_kg * 0.46)
    
    # Subtract weather losses (Volatilization of applied urea)
    volatilization_factor = simulate_volatilization_loss(
        recent_max_temp_c, days_since_urea_app, recent_rainfall_mm, urea_application_method
    )
    volatilized_n = (applied_urea_kg * 0.46) * volatilization_factor 
    available_n -= volatilized_n

    # Subtract weather losses (Leaching - Piston Flow)
    # Note: We calculate leaching AFTER volatilization since volatilized N is already gone
    leached_n = calculate_piston_flow_leaching(
        current_moisture_mm, recent_rainfall_mm, field_capacity_mm, available_n
    )
    available_n -= leached_n
    
    n_daily_demand = get_current_phase_demand(crop, crop.sowing_date_offset)
    n_lookahead_demand = n_daily_demand * 10 
    
    # --- PHOSPHORUS LOGIC (Fixation based on pH) ---
    total_p = soil.phosphorus_kg + applied_p_fertilizer_kg
    available_p = calculate_phosphorus_availability(soil.ph_level, total_p)
    p_critical = crop.sowing_date_offset < 40
    
    # --- GENERATE ALERTS ---
    if leached_n > 2.0:
        alerts.append(f"⚠️ WEATHER ALERT (LEACHING): Piston-Flow model detected {leached_n:.1f}kg of N washed below root zone.")
    if volatilization_factor > 0:
        alerts.append(f"⚠️ WEATHER ALERT (VOLATILIZATION): High temps caused {volatilized_n:.1f}kg of surface N to evaporate.")
        
    if available_p < 20 and p_critical:
        alerts.append(f"STATUS RED (PHOSPHORUS): Soil pH ({soil.ph_level}) is fixing P. Only {available_p:.1f}kg available. Apply soluble P immediately.")
        
    if available_n < n_lookahead_demand:
        deficit = n_lookahead_demand - available_n
        urea_needed = deficit / 0.46
        alerts.append(f"STATUS RED (NITROGEN): Soil Nitrogen critically low. Apply {urea_needed:.1f}kg of Urea.")
    elif available_n < (n_lookahead_demand * 1.5):
        alerts.append("STATUS YELLOW (NITROGEN): Nitrogen levels adequate for now, but will run low next week.")
    else:
        alerts.append("STATUS GREEN (NITROGEN): Nitrogen is optimal.")
        
    return "\n".join(alerts)

# Example Configuration (Mock Database Data)
CORN_DATA = CropData(
    name="Corn",
    optimal_yield_tons=10.0,
    extraction_rate=NutrientProfile(nitrogen_per_ton=20.0, phosphorus_per_ton=8.0, potassium_per_ton=18.0),
    nitrogen_curve={
        "Seedling": (25, 0.10),      # Day 0-25: 10%
        "Rapid Growth": (60, 0.50),  # Day 26-60: 50%
        "Mid Season": (100, 0.30),   # Day 61-100: 30%
        "Late Season": (120, 0.10)   # Day 101-120: 10%
    },
    sowing_date_offset=45 # E.g., Today is day 45 (Rapid Growth phase)
)
