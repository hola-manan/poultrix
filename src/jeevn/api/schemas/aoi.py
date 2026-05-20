"""
Pydantic request/response models for AOI endpoints.
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, ConfigDict


class AOIRequest(BaseModel):
    name: str
    geojson: dict
    start_date: Optional[str] = None
    end_date: Optional[str] = None

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "name": "Sample AOI",
            "geojson": {
                "type": "FeatureCollection",
                "features": [{
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[
                            [0.0, 0.0],
                            [1.0, 0.0],
                            [1.0, 1.0],
                            [0.0, 1.0],
                            [0.0, 0.0]
                        ]]
                    }
                }]
            },
            "start_date": "2024-01-01",
            "end_date": "2024-12-31"
        }
    })


class HealthResponse(BaseModel):
    status: str


class AOIResponse(BaseModel):
    aoi_id: str
    metadata_path: Optional[str] = None
    ndvi_csv: Optional[str] = None
    ndvi_timeseries: Optional[list] = None
    ndvi_raster: Optional[str] = None
    ndwi_raster: Optional[str] = None
    parcel_confidence: Optional[Dict[str, Any]] = None
    raster_quality: Optional[Dict[str, Any]] = None
    anomalies: Optional[Dict[str, Any]] = None


class ReportResponse(BaseModel):
    aoi_id: str
    status: str
    metadata_path: Optional[str] = None
    report: Optional[Dict[str, Any]] = None
