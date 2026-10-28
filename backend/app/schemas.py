"""Pydantic request/response models for the HTTP API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .models import IndexingStatus, JobStatus, JobType


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list | dict | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class HealthOut(BaseModel):
    status: str
    version: str
    database: str
    schema_revision: str | None


class ScanRequest(BaseModel):
    path: str = Field(..., min_length=1, max_length=32767, description="Absolute folder path")


class VideoOut(ORM):
    id: int
    path: str
    filename: str
    size_bytes: int
    file_hash: str
    duplicate_of_id: int | None
    duration_seconds: float | None
    width: int | None
    height: int | None
    frame_rate: float | None
    codec: str | None
    container_format: str | None
    creation_time: datetime | None
    indexing_status: IndexingStatus
    indexing_progress: float
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    indexed_at: datetime | None


class VideoPage(BaseModel):
    items: list[VideoOut]
    total: int
    limit: int
    offset: int


class LibraryFolderOut(ORM):
    id: int
    path: str
    created_at: datetime
    last_scanned_at: datetime | None
    video_count: int = 0


class IndexJobOut(ORM):
    id: int
    job_type: JobType
    status: JobStatus
    params: dict
    progress: float
    current_video_id: int | None
    processed_frames: int
    total_frames_estimate: int | None
    result: dict | None
    error_message: str | None
    cancel_requested: bool
    created_at: datetime
    started_at: datetime | None
    updated_at: datetime
    finished_at: datetime | None


class StatsOut(BaseModel):
    total_videos: int
    by_status: dict[str, int]
    duplicates: int
    total_duration_seconds: float
    total_size_bytes: int
    total_detections: int
    library_folders: int
