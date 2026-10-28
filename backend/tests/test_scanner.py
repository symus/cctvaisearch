import os
import shutil

import pytest
from sqlalchemy import select

from app.models import Detection, IndexingStatus, LibraryFolder, Video
from app.services.scanner import iter_video_files, scan_folder
from tests.conftest import requires_ffmpeg

pytestmark = requires_ffmpeg


@pytest.fixture
def library(tmp_path, video_cache):
    root = tmp_path / "CCTV Exports"
    (root / "cam1" / "2024-03-01").mkdir(parents=True)
    (root / "Caméra 2 – 入口").mkdir()
    shutil.copy(video_cache["mp4"], root / "cam1" / "2024-03-01" / "front door 0800.mp4")
    shutil.copy(video_cache["mkv"], root / "Caméra 2 – 入口" / "片段.MKV")  # upper-case ext
    shutil.copy(video_cache["avi"], root / "cam1" / "yard.avi")
    (root / "cam1" / "notes.txt").write_text("not a video")
    (root / "cam1" / "._front door 0800.mp4").write_bytes(b"macOS metadata")
    return root


def videos(db):
    return {v.filename: v for v in db.scalars(select(Video))}


def test_recursive_discovery_filters_extensions(library, settings):
    names = sorted(p.name for p in iter_video_files(library, settings.video_extensions))
    assert names == ["front door 0800.mp4", "yard.avi", "片段.MKV"]


def test_initial_scan_records_metadata(db, library, settings):
    summary = scan_folder(db, library, settings)
    assert summary.discovered == 3 and summary.new == 3 and summary.failed == 0
    vids = videos(db)
    v = vids["front door 0800.mp4"]
    assert v.path == str(library / "cam1" / "2024-03-01" / "front door 0800.mp4")
    assert v.width == 320 and v.height == 240
    assert v.frame_rate == pytest.approx(25)
    assert v.duration_seconds == pytest.approx(3.0, abs=0.25)
    assert v.codec == "h264"
    assert v.indexing_status == IndexingStatus.pending
    assert len(v.file_hash) == 64
    assert vids["片段.MKV"].width == 640
    assert db.scalar(select(LibraryFolder)).last_scanned_at is not None


def test_rescan_skips_unchanged(db, library, settings, monkeypatch):
    scan_folder(db, library, settings)
    calls = []
    monkeypatch.setattr("app.services.scanner.fingerprint", lambda *a, **k: calls.append(a))
    summary = scan_folder(db, library, settings)
    assert summary.unchanged == 3 and summary.new == 0
    assert calls == []  # nothing re-hashed


def test_touch_without_content_change(db, library, settings):
    scan_folder(db, library, settings)
    f = library / "cam1" / "yard.avi"
    st = f.stat()
    os.utime(f, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))
    summary = scan_folder(db, library, settings)
    assert summary.unchanged == 3 and summary.changed == 0


def test_changed_file_resets_and_drops_detections(db, library, settings, video_cache):
    scan_folder(db, library, settings)
    v = videos(db)["yard.avi"]
    v.indexing_status = IndexingStatus.indexed
    db.add(Detection(video_id=v.id, timestamp_seconds=1.0, bounding_box=[0, 0, 1, 1], model_version="t"))
    db.commit()

    target = library / "cam1" / "yard.avi"
    shutil.copy(video_cache["mp4"], target)  # different content, same path
    summary = scan_folder(db, library, settings)
    assert summary.changed == 1
    db.refresh(v)
    assert v.indexing_status == IndexingStatus.pending
    assert v.codec == "h264"
    assert db.scalars(select(Detection)).all() == []


def test_duplicate_detection(db, library, settings):
    shutil.copy(library / "cam1" / "yard.avi", library / "yard (copy).avi")
    summary = scan_folder(db, library, settings)
    assert summary.duplicates == 1
    vids = videos(db)
    # The first copy encountered is the original; the other points at it.
    copy, orig = vids["yard (copy).avi"], vids["yard.avi"]
    assert {copy.duplicate_of_id, orig.duplicate_of_id} == {None, min(copy.id, orig.id)}
    # Filenames are not identifiers: same name in two folders are two videos.
    shutil.copy(library / "cam1" / "yard.avi", library / "Caméra 2 – 入口" / "yard.avi")
    scan_folder(db, library, settings)
    assert len([v for v in db.scalars(select(Video)) if v.filename == "yard.avi"]) == 2


def test_corrupted_and_unsupported_files(db, library, settings):
    (library / "broken.mp4").write_bytes(b"not really a video" * 50)
    summary = scan_folder(db, library, settings)
    assert summary.failed == 1 and summary.new == 4
    bad = videos(db)["broken.mp4"]
    assert bad.indexing_status == IndexingStatus.failed
    assert bad.error_message.startswith("Could not read video metadata")


def test_missing_and_reappearing_files(db, library, settings, tmp_path):
    scan_folder(db, library, settings)
    src = library / "cam1" / "yard.avi"
    parked = tmp_path / "parked.avi"
    shutil.move(src, parked)
    summary = scan_folder(db, library, settings)
    assert summary.missing == 1
    assert videos(db)["yard.avi"].indexing_status == IndexingStatus.missing
    shutil.move(parked, src)
    scan_folder(db, library, settings)
    assert videos(db)["yard.avi"].indexing_status == IndexingStatus.pending


def test_stop_mid_scan_commits_progress_and_resumes(db, library, settings):
    seen = []

    def stop_after_two():
        if len(seen) == 2:
            raise KeyboardInterrupt
        seen.append(1)

    with pytest.raises(KeyboardInterrupt):
        scan_folder(db, library, settings, should_stop=stop_after_two)
    db.rollback()
    assert len(db.scalars(select(Video)).all()) == 2  # committed before stopping
    summary = scan_folder(db, library, settings)
    assert summary.unchanged == 2 and summary.new == 1
