"""
Tests for database models and API integration
"""
import pytest
import uuid
from datetime import datetime
from jeevn.infrastructure.db import connection as db, models


def test_aoi_model_creation():
    """Test AOI model instantiation"""
    test_id = uuid.uuid4()
    aoi = models.AOI(
        id=test_id,
        name="Test AOI",
        geojson_data={"type": "FeatureCollection", "features": []},
        start_date="2024-01-01",
        end_date="2024-12-31"
    )
    
    assert aoi.id == test_id
    assert aoi.name == "Test AOI"
    assert aoi.start_date == "2024-01-01"
    assert aoi.end_date == "2024-12-31"
    assert aoi.created_at is not None
    assert aoi.updated_at is not None


def test_ingest_job_model_creation():
    """Test IngestJob model instantiation"""
    aoi_id = uuid.uuid4()
    ingest_job = models.IngestJob(
        aoi_id=aoi_id,
        status="pending",
        metadata_path="/path/to/metadata.json"
    )
    
    assert ingest_job.aoi_id == aoi_id
    assert ingest_job.status == "pending"
    assert ingest_job.metadata_path == "/path/to/metadata.json"
    assert ingest_job.created_at is not None


def test_artifact_model_creation():
    """Test Artifact model instantiation"""
    aoi_id = uuid.uuid4()
    artifact = models.Artifact(
        aoi_id=aoi_id,
        artifact_type="ndvi_raster",
        local_path="/path/to/ndvi.tif",
        s3_uri="s3://bucket/ndvi.tif",
        sha256_hash="abc123def456"
    )
    
    assert artifact.aoi_id == aoi_id
    assert artifact.artifact_type == "ndvi_raster"
    assert artifact.local_path == "/path/to/ndvi.tif"
    assert artifact.s3_uri == "s3://bucket/ndvi.tif"
    assert artifact.created_at is not None


def test_database_initialization():
    """Test that database can be initialized without errors"""
    try:
        db.init_db()
        # If no exception is raised, test passes
        assert True
    except Exception as e:
        pytest.fail(f"Database initialization failed: {e}")


def test_session_creation():
    """Test that database sessions can be created"""
    try:
        session = db.SessionLocal()
        assert session is not None
        session.close()
    except Exception as e:
        pytest.fail(f"Session creation failed: {e}")
