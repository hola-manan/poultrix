"""
Agricultural advisory routes. Thin HTTP wrapper around application.advisory_service.
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException

from jeevn.api.schemas.advisory import (
    AgriculturalAdvisoryRequest,
    AgriculturalAdvisoryResponse,
)

try:
    from jeevn.application.advisory_service import AgriculturalReportGenerator
    ADVISORY_AVAILABLE = True
except ImportError as e:
    print(f"[INFO] Advisory service not available: {e}")
    ADVISORY_AVAILABLE = False


router = APIRouter()


@router.post("/advisory/agricultural", response_model=AgriculturalAdvisoryResponse)
def generate_agricultural_advisory(request: AgriculturalAdvisoryRequest):
    """Generate comprehensive agricultural advisory report for an AOI."""
    advisory_id = str(uuid.uuid4())

    try:
        if not ADVISORY_AVAILABLE:
            raise HTTPException(
                status_code=503,
                detail="Agricultural advisory module not available"
            )

        print(f"[INFO] Generating agricultural advisory for {request.name}")
        print(f"  Location: ({request.latitude}, {request.longitude})")
        print(f"  Crop: {request.crop_type}, Area: {request.area_acres} acres")

        report = AgriculturalReportGenerator.generate_report(
            lat=request.latitude,
            lon=request.longitude,
            area_acres=request.area_acres,
            crop_name=request.crop_type,
            sowing_date=request.sowing_date,
            ndvi_timeseries=request.ndvi_timeseries,
            location_name=request.location_name
        )

        print(f"[INFO] Agricultural advisory generated successfully: {advisory_id}")

        return {
            "advisory_id": advisory_id,
            "status": "completed",
            "report": report,
            "error": None
        }

    except HTTPException as e:
        print(f"[ERROR] HTTP error in agricultural advisory: {e.detail}")
        raise

    except Exception as e:
        print(f"[ERROR] Error generating agricultural advisory: {e}")
        return {
            "advisory_id": advisory_id,
            "status": "failed",
            "report": None,
            "error": str(e)
        }


@router.get("/advisory/agricultural/{advisory_id}")
def get_agricultural_advisory(advisory_id: str):
    """Retrieve previously generated agricultural advisory."""
    try:
        return {
            "advisory_id": advisory_id,
            "status": "stored",
            "message": "Retrieve from database implementation"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/advisory/health-check")
def check_advisory_system_health():
    """Check if agricultural advisory system is operational."""
    return {
        "status": "ok" if ADVISORY_AVAILABLE else "unavailable",
        "agricultural_module": "available" if ADVISORY_AVAILABLE else "not_available",
        "timestamp": datetime.utcnow().isoformat()
    }
