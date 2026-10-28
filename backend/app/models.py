"""SQLAlchemy ORM models.

Schema changes must be accompanied by an Alembic migration in
``backend/migrations/versions``. The database is upgraded automatically at
startup.
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class IndexingStatus(str, enum.Enum):
    pending = "pending"
    indexing = "indexing"
    indexed = "indexed"
    failed = "failed"
    unsupported = "unsupported"
    missing = "missing"


class JobStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class JobType(str, enum.Enum):
    scan = "scan"
    index = "index"


class ReviewStatus(str, enum.Enum):
    unreviewed = "unreviewed"
    confirmed = "confirmed"
    rejected = "rejected"


def _enum(e: type[enum.Enum]) -> Enum:
    # Store enum values as plain strings so the DB stays readable and portable.
    return Enum(e, native_enum=False, length=32, values_callable=lambda x: [m.value for m in x])


class LibraryFolder(Base):
    """A folder the user explicitly approved for scanning and playback."""

    __tablename__ = "library_folders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    path: Mapped[str] = mapped_column(Text, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_scanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Video(Base):
    __tablename__ = "videos"
    __table_args__ = (
        Index("ix_videos_status", "indexing_status"),
        Index("ix_videos_file_hash", "file_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    folder_id: Mapped[int | None] = mapped_column(
        ForeignKey("library_folders.id", ondelete="SET NULL")
    )
    path: Mapped[str] = mapped_column(Text, unique=True)
    filename: Mapped[str] = mapped_column(Text)
    size_bytes: Mapped[int] = mapped_column(Integer)
    mtime_ns: Mapped[int] = mapped_column(Integer)
    # Partial content fingerprint (sha256 of size + head/middle/tail chunks).
    file_hash: Mapped[str] = mapped_column(String(64))
    duplicate_of_id: Mapped[int | None] = mapped_column(
        ForeignKey("videos.id", ondelete="SET NULL")
    )
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    frame_rate: Mapped[float | None] = mapped_column(Float)
    codec: Mapped[str | None] = mapped_column(String(64))
    container_format: Mapped[str | None] = mapped_column(String(128))
    creation_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    indexing_status: Mapped[IndexingStatus] = mapped_column(
        _enum(IndexingStatus), default=IndexingStatus.pending
    )
    indexing_progress: Mapped[float] = mapped_column(Float, default=0.0)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    detections: Mapped[list[Detection]] = relationship(
        back_populates="video", cascade="all, delete-orphan", passive_deletes=True
    )


class Detection(Base):
    __tablename__ = "detections"
    __table_args__ = (Index("ix_detections_video_ts", "video_id", "timestamp_seconds"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"))
    timestamp_seconds: Mapped[float] = mapped_column(Float)
    # [x1, y1, x2, y2] in source-frame pixels.
    bounding_box: Mapped[list[float]] = mapped_column(JSON)
    track_id: Mapped[int | None] = mapped_column(Integer)
    face_quality: Mapped[float | None] = mapped_column(Float)
    person_detection_confidence: Mapped[float | None] = mapped_column(Float)
    model_version: Mapped[str] = mapped_column(String(128))
    thumbnail_path: Mapped[str | None] = mapped_column(Text)

    video: Mapped[Video] = relationship(back_populates="detections")
    embeddings: Mapped[list[Embedding]] = relationship(
        back_populates="detection", cascade="all, delete-orphan", passive_deletes=True
    )


class Embedding(Base):
    __tablename__ = "embeddings"
    __table_args__ = (
        Index("ix_embeddings_feature_model", "feature_type", "model_name", "model_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    detection_id: Mapped[int] = mapped_column(ForeignKey("detections.id", ondelete="CASCADE"))
    feature_type: Mapped[str] = mapped_column(String(16))  # "face" | "body"
    model_name: Mapped[str] = mapped_column(String(128))
    model_version: Mapped[str] = mapped_column(String(64))
    dimension: Mapped[int] = mapped_column(Integer)
    normalized: Mapped[bool] = mapped_column(Boolean, default=True)
    # Raw float32 bytes; FAISS indexes are rebuilt from these.
    vector: Mapped[bytes | None] = mapped_column()
    # Row id inside the persisted FAISS index, if any.
    vector_reference: Mapped[int | None] = mapped_column(Integer)

    detection: Mapped[Detection] = relationship(back_populates="embeddings")


class IndexJob(Base):
    __tablename__ = "index_jobs"
    __table_args__ = (Index("ix_index_jobs_status", "status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_type: Mapped[JobType] = mapped_column(_enum(JobType))
    status: Mapped[JobStatus] = mapped_column(_enum(JobStatus), default=JobStatus.queued)
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    current_video_id: Mapped[int | None] = mapped_column(
        ForeignKey("videos.id", ondelete="SET NULL")
    )
    processed_frames: Mapped[int] = mapped_column(Integer, default=0)
    total_frames_estimate: Mapped[int | None] = mapped_column(Integer)
    result: Mapped[dict | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SearchSession(Base):
    __tablename__ = "search_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Path inside the restricted references directory; never user-supplied.
    reference_image_path: Mapped[str | None] = mapped_column(Text)
    mode: Mapped[str] = mapped_column(String(16), default="combined")
    model_version: Mapped[str | None] = mapped_column(String(128))
    filters: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[JobStatus] = mapped_column(_enum(JobStatus), default=JobStatus.queued)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    results: Mapped[list[SearchResult]] = relationship(
        back_populates="session", cascade="all, delete-orphan", passive_deletes=True
    )


class SearchResult(Base):
    __tablename__ = "search_results"
    __table_args__ = (Index("ix_search_results_session_rank", "search_session_id", "ranking_score"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    search_session_id: Mapped[int] = mapped_column(
        ForeignKey("search_sessions.id", ondelete="CASCADE")
    )
    detection_id: Mapped[int] = mapped_column(ForeignKey("detections.id", ondelete="CASCADE"))
    face_similarity: Mapped[float | None] = mapped_column(Float)
    body_similarity: Mapped[float | None] = mapped_column(Float)
    ranking_score: Mapped[float] = mapped_column(Float)
    review_status: Mapped[ReviewStatus] = mapped_column(
        _enum(ReviewStatus), default=ReviewStatus.unreviewed
    )

    session: Mapped[SearchSession] = relationship(back_populates="results")
