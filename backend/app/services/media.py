"""Video metadata extraction with ffprobe."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .subproc import run


class ProbeError(Exception):
    """ffprobe could not read the file (malformed, truncated, or not media)."""


class UnsupportedMediaError(ProbeError):
    """The file was readable but has no decodable video stream."""


class ToolMissingError(Exception):
    """ffprobe is not installed or not on PATH."""


@dataclass
class VideoMetadata:
    duration_seconds: float | None
    width: int | None
    height: int | None
    frame_rate: float | None
    codec: str | None
    container_format: str | None
    creation_time: datetime | None


def _parse_rate(value: str | None) -> float | None:
    if not value or value in ("0/0", "N/A"):
        return None
    try:
        if "/" in value:
            num, den = value.split("/", 1)
            den_f = float(den)
            return round(float(num) / den_f, 3) if den_f else None
        return float(value)
    except ValueError:
        return None


def _parse_float(value) -> float | None:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if f > 0 else None


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_ffprobe_json(data: dict) -> VideoMetadata:
    streams = [s for s in data.get("streams", []) if s.get("codec_type") == "video"]
    # Skip embedded cover art / thumbnails.
    streams = [s for s in streams if not s.get("disposition", {}).get("attached_pic")]
    if not streams:
        raise UnsupportedMediaError("No video stream found")
    vs = streams[0]
    fmt = data.get("format", {})
    duration = _parse_float(fmt.get("duration")) or _parse_float(vs.get("duration"))
    frame_rate = _parse_rate(vs.get("avg_frame_rate")) or _parse_rate(vs.get("r_frame_rate"))
    creation = _parse_time(fmt.get("tags", {}).get("creation_time")) or _parse_time(
        vs.get("tags", {}).get("creation_time")
    )
    return VideoMetadata(
        duration_seconds=duration,
        width=vs.get("width"),
        height=vs.get("height"),
        frame_rate=frame_rate,
        codec=vs.get("codec_name"),
        container_format=fmt.get("format_name"),
        creation_time=creation,
    )


def probe_video(path: Path, ffprobe: str = "ffprobe", timeout: float = 60.0) -> VideoMetadata:
    # Absolute paths can never be mistaken for an ffprobe option.
    if not path.is_absolute():
        raise ValueError("probe_video requires an absolute path")
    args = [
        ffprobe,
        "-v", "error",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    try:
        proc = run(args, timeout=timeout)
    except FileNotFoundError as exc:
        raise ToolMissingError(f"ffprobe not found ({ffprobe}). Install FFmpeg.") from exc
    except subprocess.TimeoutExpired as exc:
        raise ProbeError(f"ffprobe timed out after {timeout:.0f}s") from exc
    if proc.returncode != 0:
        msg = proc.stderr.decode("utf-8", "replace").strip().splitlines()
        raise ProbeError(msg[-1] if msg else f"ffprobe exited with {proc.returncode}")
    try:
        data = json.loads(proc.stdout.decode("utf-8", "replace") or "{}")
    except json.JSONDecodeError as exc:
        raise ProbeError("ffprobe returned invalid JSON") from exc
    return parse_ffprobe_json(data)
