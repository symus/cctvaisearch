from __future__ import annotations

import shutil

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from .. import __version__
from ..config import Settings
from ..models import Detection, IndexingStatus, LibraryFolder, Video
from ..schemas import HealthOut, StatsOut
from ..services.hardware import detect_hardware
from .deps import get_db, get_settings_dep

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health", response_model=HealthOut)
def health(db: Session = Depends(get_db)) -> HealthOut:
    try:
        revision = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
        database = "ok"
    except Exception:  # noqa: BLE001
        revision, database = None, "error"
    return HealthOut(
        status="ok" if database == "ok" else "degraded",
        version=__version__,
        database=database,
        schema_revision=revision,
    )


@router.get("/system-info")
def system_info(request: Request, settings: Settings = Depends(get_settings_dep)) -> dict:
    hw = detect_hardware(settings.ffmpeg_path, settings.ffprobe_path).as_dict()
    usage = shutil.disk_usage(settings.data_dir)
    return {
        "hardware": hw,
        "storage": {
            "data_dir": str(settings.data_dir),
            "disk_total_bytes": usage.total,
            "disk_free_bytes": usage.free,
        },
        "models": {
            "face": {"status": "not_installed", "note": "Added in Milestone 4"},
            "person_detector": {"status": "not_installed", "note": "Added in Milestone 5"},
            "body_reid": {"status": "not_installed", "note": "Added in Milestone 5"},
        },
        "config": {
            "sample_fps": settings.sample_fps,
            "max_concurrent_jobs": settings.max_concurrent_jobs,
            "video_extensions": list(settings.video_extensions),
        },
    }


@router.get("/stats", response_model=StatsOut)
def stats(db: Session = Depends(get_db)) -> StatsOut:
    rows = db.execute(
        select(Video.indexing_status, func.count()).group_by(Video.indexing_status)
    ).all()
    by_status = {s.value: 0 for s in IndexingStatus}
    for status, count in rows:
        by_status[status.value] = count
    totals = db.execute(
        select(
            func.count(Video.id),
            func.coalesce(func.sum(Video.duration_seconds), 0.0),
            func.coalesce(func.sum(Video.size_bytes), 0),
        )
    ).one()
    return StatsOut(
        total_videos=totals[0],
        by_status=by_status,
        duplicates=db.scalar(select(func.count()).where(Video.duplicate_of_id.is_not(None))) or 0,
        total_duration_seconds=float(totals[1]),
        total_size_bytes=int(totals[2]),
        total_detections=db.scalar(select(func.count(Detection.id))) or 0,
        library_folders=db.scalar(select(func.count(LibraryFolder.id))) or 0,
    )
