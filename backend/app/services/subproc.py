"""Safe subprocess helpers. Always pass argument lists; never use a shell."""

from __future__ import annotations

import subprocess
import sys

# Prevent a console window from flashing up for every ffprobe call on Windows.
_CREATIONFLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0


def run(args: list[str], timeout: float) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        args,
        capture_output=True,
        timeout=timeout,
        check=False,
        shell=False,
        stdin=subprocess.DEVNULL,
        creationflags=_CREATIONFLAGS,
    )
