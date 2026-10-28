from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
requires_ffmpeg = pytest.mark.skipif(not HAS_FFMPEG, reason="FFmpeg/ffprobe not installed")


def make_video(path: Path, seconds: float = 2.0, fps: int = 25, size: str = "320x240",
               codec: str = "libx264", pattern: str = "testsrc") -> Path:
    """Render a synthetic test-pattern video (no people, no biometric data)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    args = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "lavfi", "-i", f"{pattern}=size={size}:rate={fps}",
        "-t", str(seconds), "-pix_fmt", "yuv420p", "-c:v", codec, str(path),
    ]
    subprocess.run(args, check=True)
    return path


@pytest.fixture(scope="session")
def video_cache(tmp_path_factory) -> dict[str, Path]:
    if not HAS_FFMPEG:
        return {}
    d = tmp_path_factory.mktemp("video-cache")
    return {
        "mp4": make_video(d / "a.mp4", seconds=3, fps=25),
        "mkv": make_video(d / "b.mkv", seconds=2, fps=15, size="640x360", pattern="smptebars"),
        "avi": make_video(d / "c.avi", seconds=2, fps=10, codec="mpeg4", pattern="rgbtestsrc"),
    }


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(data_dir=tmp_path / "appdata", fingerprint_chunk_bytes=4096)


@pytest.fixture
def app(settings):
    return create_app(settings, start_worker=False)


@pytest.fixture
def client(app):
    with TestClient(app, base_url="http://127.0.0.1") as c:
        yield c


@pytest.fixture
def db(app):
    with app.state.session_factory() as session:
        yield session
