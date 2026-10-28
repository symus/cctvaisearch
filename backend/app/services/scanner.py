"""Recursive video-folder scanning with incremental change detection."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..config import Settings
from ..models import Detection, IndexingStatus, LibraryFolder, Video
from .fingerprint import fingerprint
from .media import ProbeError, UnsupportedMediaError, probe_video

log = logging.getLogger(__name__)

COMMIT_EVERY = 25


@dataclass
class ScanSummary:
    discovered: int = 0
    new: int = 0
    changed: int = 0
    unchanged: int = 0
    duplicates: int = 0
    failed: int = 0
    unsupported: int = 0
    missing: int = 0
    unreadable: int = 0

    def as_dict(self) -> dict:
        return asdict(self)


def iter_video_files(root: Path, extensions: tuple[str, ...]) -> Iterator[Path]:
    """Yield video files under ``root`` recursively, in a stable order.

    Symlinked directories are not followed (avoids loops), and folders that
    cannot be read are skipped rather than aborting the scan.
    """
    exts = tuple(e.lower() for e in extensions)
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False, onerror=_log_walk_error):
        dirnames.sort()
        for name in sorted(filenames):
            if name.lower().endswith(exts) and not name.startswith("._"):
                yield Path(dirpath) / name


def _log_walk_error(err: OSError) -> None:
    log.warning("Skipping unreadable folder: %s", err.filename)


def get_or_create_folder(session: Session, root: Path) -> LibraryFolder:
    folder = session.scalar(select(LibraryFolder).where(LibraryFolder.path == str(root)))
    if folder is None:
        folder = LibraryFolder(path=str(root))
        session.add(folder)
        session.flush()
    return folder


def _apply_probe(video: Video, path: Path, settings: Settings) -> str:
    """Fill metadata from ffprobe. Returns the resulting status bucket."""
    try:
        meta = probe_video(path, settings.ffprobe_path, settings.ffprobe_timeout_seconds)
    except UnsupportedMediaError as exc:
        video.indexing_status = IndexingStatus.unsupported
        video.error_message = str(exc)
        return "unsupported"
    except ProbeError as exc:
        video.indexing_status = IndexingStatus.failed
        video.error_message = f"Could not read video metadata: {exc}"
        return "failed"
    video.duration_seconds = meta.duration_seconds
    video.width = meta.width
    video.height = meta.height
    video.frame_rate = meta.frame_rate
    video.codec = meta.codec
    video.container_format = meta.container_format
    video.creation_time = meta.creation_time
    video.indexing_status = IndexingStatus.pending
    video.error_message = None
    return "ok"


def _find_duplicate(session: Session, file_hash: str, size: int, exclude_id: int | None) -> Video | None:
    stmt = (
        select(Video)
        .where(Video.file_hash == file_hash, Video.size_bytes == size, Video.duplicate_of_id.is_(None))
        .order_by(Video.id)
    )
    if exclude_id is not None:
        stmt = stmt.where(Video.id != exclude_id)
    return session.scalars(stmt).first()


def scan_folder(
    session: Session,
    root: Path,
    settings: Settings,
    *,
    on_progress: Callable[[int, ScanSummary, Path | None], None] | None = None,
    should_stop: Callable[[], None] | None = None,
) -> ScanSummary:
    """Scan ``root`` and upsert ``Video`` rows.

    ``should_stop`` is called between files and may raise to abort; work done so
    far is committed, so re-running the scan resumes cheaply (unchanged files
    are skipped on size + mtime).
    """
    summary = ScanSummary()
    folder = get_or_create_folder(session, root)
    seen_paths: set[str] = set()

    for path in iter_video_files(root, settings.video_extensions):
        if should_stop:
            try:
                should_stop()
            except BaseException:
                session.commit()
                raise
        summary.discovered += 1
        key = str(path)
        seen_paths.add(key)
        try:
            _scan_file(session, path, folder, settings, summary)
        except OSError as exc:
            # File vanished or is locked by the recorder; report and continue.
            summary.unreadable += 1
            log.warning("Cannot read %s: %s", path.name, exc.strerror or exc)
        if summary.discovered % COMMIT_EVERY == 0:
            session.commit()
        if on_progress:
            on_progress(summary.discovered, summary, path)

    # Videos previously found under this folder that no longer exist.
    prefix = str(root).rstrip("\\/") + os.sep
    for video in session.scalars(select(Video).where(Video.path.startswith(prefix, autoescape=True))):
        if video.path not in seen_paths and not os.path.exists(video.path):
            if video.indexing_status != IndexingStatus.missing:
                video.indexing_status = IndexingStatus.missing
                video.error_message = "File no longer found at its original path"
                summary.missing += 1

    folder.last_scanned_at = datetime.now(timezone.utc)
    session.commit()
    return summary


def _scan_file(
    session: Session, path: Path, folder: LibraryFolder, settings: Settings, summary: ScanSummary
) -> None:
    st = path.stat()
    video = session.scalar(select(Video).where(Video.path == str(path)))

    if (
        video is not None
        and video.size_bytes == st.st_size
        and video.mtime_ns == st.st_mtime_ns
        and video.indexing_status != IndexingStatus.missing
    ):
        summary.unchanged += 1
        return

    file_hash = fingerprint(path, settings.fingerprint_chunk_bytes)

    if video is not None:
        if video.indexing_status == IndexingStatus.missing and video.file_hash == file_hash:
            # File reappeared unchanged (e.g. drive re-attached); keep prior results.
            video.mtime_ns = st.st_mtime_ns
            video.indexing_status = (
                IndexingStatus.indexed if video.indexed_at else IndexingStatus.pending
            )
            video.error_message = None
            summary.unchanged += 1
            return
        content_changed = video.file_hash != file_hash
        video.size_bytes = st.st_size
        video.mtime_ns = st.st_mtime_ns
        video.folder_id = folder.id
        if not content_changed:
            # Only the timestamp changed (copied/touched); nothing to redo.
            summary.unchanged += 1
            return
        video.file_hash = file_hash
        # Derived data belongs to the old content.
        session.execute(delete(Detection).where(Detection.video_id == video.id))
        video.indexed_at = None
        video.indexing_progress = 0.0
        summary.changed += 1
    else:
        video = Video(
            path=str(path),
            filename=path.name,
            folder_id=folder.id,
            size_bytes=st.st_size,
            mtime_ns=st.st_mtime_ns,
            file_hash=file_hash,
        )
        session.add(video)
        session.flush()
        summary.new += 1

    original = _find_duplicate(session, file_hash, st.st_size, exclude_id=video.id)
    video.duplicate_of_id = original.id if original else None
    if original:
        summary.duplicates += 1

    outcome = _apply_probe(video, path, settings)
    if outcome == "failed":
        summary.failed += 1
    elif outcome == "unsupported":
        summary.unsupported += 1
