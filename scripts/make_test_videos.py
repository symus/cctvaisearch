"""Generate synthetic test videos (colour test patterns - no people).

Creates a small nested library with several formats, a duplicate, a
Unicode/space filename and a corrupted file, for trying out scanning.

Usage:
    python scripts/make_test_videos.py sample-videos
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

# (relative path, lavfi pattern, size, fps, seconds, codec)
CLIPS = [
    ("cam1/2024-03-01/front door 0800.mp4", "testsrc", "1280x720", 25, 30, "libx264"),
    ("cam1/2024-03-01/front door 0900.mp4", "testsrc2", "1280x720", 25, 20, "libx264"),
    ("cam2/yard.avi", "rgbtestsrc", "640x480", 12, 15, "mpeg4"),
    ("Caméra 3 – entrée/hall.mkv", "smptebars", "960x540", 15, 10, "libx264"),
    ("cam4/lobby.mov", "testsrc", "640x360", 30, 10, "libx264"),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate synthetic test videos.")
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print("ffmpeg not found on PATH", file=sys.stderr)
        return 1
    for rel, pattern, size, fps, secs, codec in CLIPS:
        dest = args.out / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [ffmpeg, "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"{pattern}=size={size}:rate={fps}",
             "-t", str(secs), "-pix_fmt", "yuv420p", "-c:v", codec, str(dest)],
            check=True,
        )
        print("created", dest)
    shutil.copy(args.out / CLIPS[0][0], args.out / "cam1" / "front door 0800 (copy).mp4")
    (args.out / "cam2" / "corrupted.mp4").write_bytes(b"this is not a video" * 100)
    print("created a duplicate and a corrupted file")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
