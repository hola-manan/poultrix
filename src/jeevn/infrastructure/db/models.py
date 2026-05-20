"""
SQLAlchemy models for AOI, IngestJob, and Artifact.
"""

from datetime import datetime
from sqlalchemy import Column, String, DateTime, JSON, Text
from sqlalchemy.dialects.postgresql import UUID
import uuid

from .connection import Base


def _utcnow():
    return datetime.utcnow()


class AOI(Base):
    """Area of Interest model"""
    __tablename__ = "aois"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    geojson_data = Column(JSON, nullable=False)
    start_date = Column(String(10), nullable=True)
    end_date = Column(String(10), nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    def __init__(self, **kwargs):
        kwargs.setdefault("created_at", _utcnow())
        kwargs.setdefault("updated_at", _utcnow())
        super().__init__(**kwargs)


class IngestJob(Base):
    """Ingest job tracking model"""
    __tablename__ = "ingest_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    aoi_id = Column(UUID(as_uuid=True), nullable=False)
    status = Column(String(50), default="pending")
    metadata_path = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    completed_at = Column(DateTime, nullable=True)

    def __init__(self, **kwargs):
        kwargs.setdefault("created_at", _utcnow())
        super().__init__(**kwargs)


class Artifact(Base):
    """Artifact storage model"""
    __tablename__ = "artifacts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    aoi_id = Column(UUID(as_uuid=True), nullable=False)
    artifact_type = Column(String(100), nullable=False)
    local_path = Column(Text, nullable=True)
    s3_uri = Column(Text, nullable=True)
    sha256_hash = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    def __init__(self, **kwargs):
        kwargs.setdefault("created_at", _utcnow())
        super().__init__(**kwargs)
