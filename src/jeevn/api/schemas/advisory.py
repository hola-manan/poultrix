"""
Pydantic request/response models for agricultural advisory endpoints.
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel


class AgriculturalAdvisoryRequest(BaseModel):
    name: str
    latitude: float
    longitude: float
    area_acres: Optional[float] = 0.421
    crop_type: Optional[str] = "apple"
    sowing_date: Optional[str] = None
    ndvi_timeseries: Optional[list] = None
    location_name: Optional[str] = ""


class AgriculturalAdvisoryResponse(BaseModel):
    advisory_id: str
    status: str
    report: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
