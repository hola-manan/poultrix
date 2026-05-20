"""
Jeevn - MVP API entrypoint.
FastAPI app — mounts routers, handles lifecycle, exposes metrics.
"""

from fastapi import FastAPI

from jeevn.api.routes.aoi import router as aoi_router
from jeevn.api.routes.aoi import AOI_STORE, AOI_STORE_LOCK  # noqa: F401 (re-export for tests)
from jeevn.api.routes.advisory import router as advisory_router

try:
    from jeevn.infrastructure.db import connection as db
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False

try:
    from jeevn.infrastructure.monitoring import metrics
    MONITORING_AVAILABLE = True
except ImportError:
    MONITORING_AVAILABLE = False


app = FastAPI(title="Jeevn - MVP API", version="1.0.0")

app.include_router(aoi_router)
app.include_router(advisory_router)

if MONITORING_AVAILABLE:
    try:
        app.mount("/metrics", metrics.metrics_app)
    except Exception as e:
        print(f"[INFO] Prometheus metrics not mounted: {e}")


@app.on_event("startup")
def startup():
    if DB_AVAILABLE:
        try:
            db.init_db()
            print("[INFO] Database initialized")
        except Exception as e:
            print(f"[INFO] Database initialization failed (optional): {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
