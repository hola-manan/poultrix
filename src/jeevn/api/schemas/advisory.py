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


class RealtimeAdvisoryRequest(BaseModel):
    name: str
    latitude: float
    longitude: float
    crop_type: Optional[str] = "wheat"
    area_acres: Optional[float] = 1.0
    sowing_date: Optional[str] = None
    location_name: Optional[str] = ""
    village: Optional[str] = None
    include_report: Optional[bool] = False


class RealtimeAdvisoryResponse(BaseModel):
    advisory_id: str
    status: str
    advisory: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
