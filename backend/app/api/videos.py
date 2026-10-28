from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import Settings
from ..errors import AppError
from ..models import IndexingStatus, JobType, LibraryFolder, Video
from ..schemas import IndexJobOut, LibraryFolderOut, ScanRequest, VideoOut, VideoPage
from ..services.jobs import JobRunner
from ..services.paths import PathValidationError, validate_scan_root
from .deps import get_db, get_runner, get_settings_dep

router = APIRouter(prefix="/api", tags=["videos"])


@router.post(
    "/videos/scan",
    response_model=IndexJobOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Scan a folder (recursively) for videos in the background",
)
def scan_videos(
    body: ScanRequest,
    settings: Settings = Depends(get_settings_dep),
    runner: JobRunner = Depends(get_runner),
) -> IndexJobOut:
    try:
        root = validate_scan_root(body.path, forbidden=[settings.data_dir])
    except PathValidationError as exc:
        raise AppError(400, "invalid_path", str(exc)) from exc
    job = runner.enqueue(JobType.scan, {"path": str(root)})
    return IndexJobOut.model_validate(job)


@router.get("/videos", response_model=VideoPage)
def list_videos(
    q: str | None = Query(None, max_length=200, description="Filename contains"),
    status_filter: IndexingStatus | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> VideoPage:
    stmt = select(Video)
    if q:
        stmt = stmt.where(Video.filename.contains(q, autoescape=True))
    if status_filter:
        stmt = stmt.where(Video.indexing_status == status_filter)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(stmt.order_by(Video.path).limit(limit).offset(offset)).all()
    return VideoPage(
        items=[VideoOut.model_validate(v) for v in items], total=total, limit=limit, offset=offset
    )


@router.get("/videos/{video_id}", response_model=VideoOut)
def get_video(video_id: int, db: Session = Depends(get_db)) -> VideoOut:
    video = db.get(Video, video_id)
    if video is None:
        raise AppError(404, "not_found", "Video not found")
    return VideoOut.model_validate(video)


@router.get("/library-folders", response_model=list[LibraryFolderOut])
def list_folders(db: Session = Depends(get_db)) -> list[LibraryFolderOut]:
    counts = dict(
        db.execute(select(Video.folder_id, func.count()).group_by(Video.folder_id)).all()
    )
    folders = db.scalars(select(LibraryFolder).order_by(LibraryFolder.path)).all()
    out = []
    for f in folders:
        item = LibraryFolderOut.model_validate(f)
        item.video_count = counts.get(f.id, 0)
        out.append(item)
    return out
