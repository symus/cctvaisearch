import pytest

from app.services.fingerprint import fingerprint
from app.services.media import (
    ProbeError,
    UnsupportedMediaError,
    parse_ffprobe_json,
    probe_video,
)
from tests.conftest import requires_ffmpeg


def test_parse_rates_and_skips_cover_art():
    meta = parse_ffprobe_json({
        "streams": [
            {"codec_type": "video", "codec_name": "mjpeg", "disposition": {"attached_pic": 1}},
            {"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080,
             "avg_frame_rate": "30000/1001", "r_frame_rate": "30/1"},
        ],
        "format": {"duration": "12.5", "format_name": "mov,mp4",
                   "tags": {"creation_time": "2024-03-01T10:00:00.000000Z"}},
    })
    assert meta.codec == "h264"
    assert meta.frame_rate == pytest.approx(29.97, abs=0.01)
    assert meta.duration_seconds == 12.5
    assert meta.creation_time.year == 2024


def test_parse_falls_back_to_r_frame_rate_and_stream_duration():
    meta = parse_ffprobe_json({
        "streams": [{"codec_type": "video", "codec_name": "hevc", "avg_frame_rate": "0/0",
                     "r_frame_rate": "25/1", "duration": "4.0"}],
        "format": {"duration": "N/A"},
    })
    assert meta.frame_rate == 25.0
    assert meta.duration_seconds == 4.0


def test_parse_no_video_stream():
    with pytest.raises(UnsupportedMediaError):
        parse_ffprobe_json({"streams": [{"codec_type": "audio"}], "format": {}})


@requires_ffmpeg
@pytest.mark.parametrize("key,fps,width,duration", [
    ("mp4", 25, 320, 3.0), ("mkv", 15, 640, 2.0), ("avi", 10, 320, 2.0)
])
def test_probe_real_files(video_cache, key, fps, width, duration):
    meta = probe_video(video_cache[key])
    assert meta.width == width
    assert meta.frame_rate == pytest.approx(fps, rel=0.01)
    assert meta.duration_seconds == pytest.approx(duration, abs=0.25)
    assert meta.codec


@requires_ffmpeg
def test_probe_corrupted_file(tmp_path):
    bad = tmp_path / "broken.mp4"
    bad.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"garbage" * 100)
    with pytest.raises(ProbeError):
        probe_video(bad)


@requires_ffmpeg
def test_probe_truncated_file(tmp_path, video_cache):
    data = video_cache["mkv"].read_bytes()
    cut = tmp_path / "cut.mkv"
    cut.write_bytes(data[:200])
    with pytest.raises(ProbeError):
        probe_video(cut)


def test_probe_requires_absolute_path():
    from pathlib import Path

    with pytest.raises(ValueError):
        probe_video(Path("relative.mp4"))


def test_fingerprint_detects_changes(tmp_path):
    f = tmp_path / "big.bin"
    data = bytearray(b"a" * 100_000)
    f.write_bytes(data)
    h1 = fingerprint(f, chunk_bytes=4096)
    assert fingerprint(f, chunk_bytes=4096) == h1  # deterministic
    data[50_000] = ord("b")  # middle chunk
    f.write_bytes(data)
    assert fingerprint(f, chunk_bytes=4096) != h1
    f.write_bytes(bytes(data) + b"x")  # size change
    assert fingerprint(f, chunk_bytes=4096) != h1


def test_fingerprint_small_file_is_full_hash(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.write_bytes(b"0123456789")
    b.write_bytes(b"0123456780")
    assert fingerprint(a) != fingerprint(b)
