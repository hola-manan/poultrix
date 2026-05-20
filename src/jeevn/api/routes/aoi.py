"""
AOI ingestion + report routes.
"""

import uuid
import threading
from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, Response

from jeevn.api.schemas.aoi import AOIRequest, AOIResponse, HealthResponse, ReportResponse
from jeevn.remote_sensing.visualization import (
    colorize_raster, load_raster_data,
)

# Optional integrations — fall back gracefully if unavailable
try:
    from jeevn.infrastructure.db import connection as db, models
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False

try:
    from jeevn.infrastructure.monitoring import metrics
    MONITORING_AVAILABLE = True
except ImportError:
    MONITORING_AVAILABLE = False

try:
    from jeevn.ingestion import sentinel as sentinels_ingest
    INGEST_AVAILABLE = True
except ImportError:
    INGEST_AVAILABLE = False

try:
    from jeevn.remote_sensing import pipeline as run_preproc
    PREPROC_AVAILABLE = True
except ImportError:
    PREPROC_AVAILABLE = False


router = APIRouter()

# In-memory AOI store (primary runtime store — thread-safe)
AOI_STORE: Dict[str, Dict[str, Any]] = {}
AOI_STORE_LOCK = threading.Lock()


@router.get("/health", response_model=HealthResponse)
def health_check():
    """Health check endpoint"""
    return {"status": "ok"}


@router.post("/aoi", response_model=AOIResponse)
def create_aoi(request: AOIRequest):
    """Create a new AOI and trigger ingestion/preprocessing."""
    try:
        aoi_id = uuid.uuid4()
        aoi_id_str = str(aoi_id)

        aoi_record = {
            "id": aoi_id_str,
            "name": request.name,
            "geojson": request.geojson,
            "start_date": request.start_date,
            "end_date": request.end_date,
            "created_at": datetime.utcnow().isoformat(),
            "status": "created"
        }
        with AOI_STORE_LOCK:
            AOI_STORE[aoi_id_str] = aoi_record

        if DB_AVAILABLE:
            try:
                db.init_db()
                session = db.SessionLocal()
                db_aoi = models.AOI(
                    id=aoi_id,
                    name=request.name,
                    geojson_data=request.geojson,
                    start_date=request.start_date,
                    end_date=request.end_date
                )
                session.add(db_aoi)
                session.commit()
                session.close()
            except Exception as db_err:
                print(f"[INFO] DB integration skipped: {db_err}")

        metadata_path = None
        ndvi_csv = None
        ndvi_timeseries = None
        ndvi_raster = None
        ndwi_raster = None
        parcel_confidence = None
        raster_quality = None
        anomalies = None

        if INGEST_AVAILABLE:
            try:
                ingest_result = sentinels_ingest.ingest(
                    aoi_geojson=request.geojson,
                    start_date=request.start_date,
                    end_date=request.end_date,
                    aoi_id=aoi_id
                )
                metadata_path = ingest_result.get("metadata_path")

                if DB_AVAILABLE:
                    try:
                        session = db.SessionLocal()
                        ingest_job = models.IngestJob(
                            aoi_id=aoi_id,
                            status="completed",
                            metadata_path=metadata_path
                        )
                        session.add(ingest_job)
                        session.commit()
                        session.close()
                    except Exception as db_err:
                        print(f"[INFO] DB ingest job skipped: {db_err}")

                if metadata_path and PREPROC_AVAILABLE:
                    try:
                        agg_result = run_preproc.aggregate_ndvi(metadata_path)
                        ndvi_csv = agg_result.get("ndvi_csv")
                        ndvi_timeseries = agg_result.get("ndvi_timeseries")
                    except Exception as agg_err:
                        print(f"[INFO] NDVI aggregation skipped: {agg_err}")

                if metadata_path and PREPROC_AVAILABLE:
                    try:
                        raster_result = run_preproc.compute_raster(metadata_path)
                        ndvi_raster = raster_result.get("ndvi_raster")
                        ndwi_raster = raster_result.get("ndwi_raster")
                        parcel_confidence = raster_result.get("parcel_confidence")
                        raster_quality = raster_result.get("raster_quality")
                    except Exception as raster_err:
                        print(f"[INFO] NDVI raster computation skipped: {raster_err}")

                if ndvi_timeseries and PREPROC_AVAILABLE:
                    try:
                        anomalies = run_preproc.analyze_signals(ndvi_timeseries, ndvi_raster)
                    except Exception as sig_err:
                        print(f"[INFO] Advanced signals skipped: {sig_err}")

            except Exception as ingest_err:
                print(f"[INFO] Ingest failed, but continuing: {ingest_err}")

        aoi_record["status"] = "processed"
        aoi_record["metadata_path"] = metadata_path
        aoi_record["report"] = {
            "ndvi_csv": ndvi_csv,
            "ndvi_timeseries": ndvi_timeseries,
            "ndvi_raster": ndvi_raster,
            "ndwi_raster": ndwi_raster,
            "parcel_confidence": parcel_confidence,
            "raster_quality": raster_quality,
            "anomalies": anomalies
        }

        with AOI_STORE_LOCK:
            AOI_STORE[aoi_id_str] = aoi_record

        if MONITORING_AVAILABLE:
            try:
                metrics.aoi_created_counter.inc()
            except Exception as metrics_err:
                print(f"[INFO] Metrics counter skipped: {metrics_err}")

        return {
            "aoi_id": aoi_id_str,
            "metadata_path": metadata_path,
            "ndvi_csv": ndvi_csv,
            "ndvi_timeseries": ndvi_timeseries,
            "ndvi_raster": ndvi_raster,
            "ndwi_raster": ndwi_raster,
            "parcel_confidence": parcel_confidence,
            "raster_quality": raster_quality,
            "anomalies": anomalies
        }

    except Exception as e:
        if MONITORING_AVAILABLE:
            try:
                metrics.aoi_error_counter.inc()
            except Exception:
                pass
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/aoi/{aoi_id}/report", response_model=ReportResponse)
def get_aoi_report(aoi_id: str):
    """Get report for a previously created AOI."""
    with AOI_STORE_LOCK:
        if aoi_id not in AOI_STORE:
            raise HTTPException(status_code=404, detail="AOI not found")

        aoi_record = AOI_STORE[aoi_id]

    return {
        "aoi_id": aoi_id,
        "status": aoi_record.get("status", "unknown"),
        "metadata_path": aoi_record.get("metadata_path"),
        "report": aoi_record.get("report")
    }


@router.get(
    "/aoi/{aoi_id}/maps/{kind}.png",
    responses={200: {"content": {"image/png": {}}}},
    response_class=Response,
)
def get_aoi_map(aoi_id: str, kind: str):
    """Serve a colorized NDVI or NDWI map for an AOI as a PNG.

    The raster is the real one produced by `remote_sensing.compute_raster`
    from Sentinel-2 COG bands (B04/B08 for NDVI, B03/B11 for NDWI), cropped
    to the AOI polygon. If no real raster was produced for this AOI (e.g.
    the stub ingest path, or no STAC items), responds 404 — callers should
    render an "unavailable" message rather than substitute synthetic data.
    """
    if kind not in ("ndvi", "ndwi"):
        raise HTTPException(status_code=400, detail=f"Unknown map kind: {kind}")

    with AOI_STORE_LOCK:
        if aoi_id not in AOI_STORE:
            raise HTTPException(status_code=404, detail="AOI not found")
        aoi_record = AOI_STORE[aoi_id]
        report = aoi_record.get("report") or {}
        geometry = aoi_record.get("geojson", {}).get("features", [{}])[0].get("geometry")

    raster_path = report.get(f"{kind}_raster")
    if not raster_path:
        raise HTTPException(
            status_code=404,
            detail=f"{kind.upper()} raster not available for this AOI",
        )

    raster_data = load_raster_data(raster_path)
    if raster_data is None:
        raise HTTPException(
            status_code=404,
            detail=f"{kind.upper()} raster file could not be read: {raster_path}",
        )
    raster, transform, crs = raster_data

    png_bytes = colorize_raster(
        raster, 
        palette=kind, 
        geometry=geometry, 
        transform=transform, 
        crs=crs
    )
    if png_bytes is None:
        raise HTTPException(
            status_code=500,
            detail="Pillow not available; cannot render raster",
        )

    return Response(content=png_bytes, media_type="image/png")
