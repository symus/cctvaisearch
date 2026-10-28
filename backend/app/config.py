"""Application configuration.

Values come from environment variables prefixed with ``CCTV_`` or from a
``.env`` file in the backend directory. See ``.env.example`` at the repo root.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data"

VIDEO_EXTENSIONS = (".mp4", ".avi", ".mkv", ".mov", ".m4v")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CCTV_",
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Where the database, thumbnails, reference photos, clips and indexes live.
    # Original footage is never copied here.
    data_dir: Path = DEFAULT_DATA_DIR

    # Network binding. Keep 127.0.0.1 unless you understand the privacy impact.
    host: str = "127.0.0.1"
    port: int = 8000

    # Host headers accepted (DNS-rebinding protection).
    allowed_hosts: list[str] = Field(default_factory=lambda: ["127.0.0.1", "localhost"])

    # Browser origins allowed to call the API (the Vite dev server by default).
    allowed_origins: list[str] = Field(
        default_factory=lambda: ["http://127.0.0.1:5173", "http://localhost:5173"]
    )

    # Ingestion
    video_extensions: tuple[str, ...] = VIDEO_EXTENSIONS
    ffprobe_path: str = "ffprobe"
    ffmpeg_path: str = "ffmpeg"
    ffprobe_timeout_seconds: float = 60.0
    # Bytes hashed from the start, middle and end of each file for the fingerprint.
    fingerprint_chunk_bytes: int = 1024 * 1024

    # Indexing (used from Milestone 3)
    sample_fps: float = 1.0
    max_concurrent_jobs: int = 1

    @field_validator("video_extensions", mode="before")
    @classmethod
    def _normalize_extensions(cls, value):
        if isinstance(value, str):
            value = [v for v in value.split(",") if v.strip()]
        return tuple(
            (v if v.startswith(".") else f".{v}").lower().strip() for v in value
        )

    @property
    def database_path(self) -> Path:
        return self.data_dir / "cctv.sqlite3"

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.database_path.as_posix()}"

    @property
    def thumbnails_dir(self) -> Path:
        return self.data_dir / "thumbnails"

    @property
    def references_dir(self) -> Path:
        return self.data_dir / "references"

    @property
    def clips_dir(self) -> Path:
        return self.data_dir / "clips"

    @property
    def indexes_dir(self) -> Path:
        return self.data_dir / "indexes"

    @property
    def models_dir(self) -> Path:
        return self.data_dir / "models"

    def ensure_dirs(self) -> None:
        for d in (
            self.data_dir,
            self.thumbnails_dir,
            self.references_dir,
            self.clips_dir,
            self.indexes_dir,
            self.models_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
