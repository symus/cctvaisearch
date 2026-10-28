"""Filesystem path validation.

User-supplied paths are only accepted for scanning a folder. Everything else
(playback, thumbnails, clips) is looked up by database ID, and files are only
served if they lie inside an approved library folder.
"""

from __future__ import annotations

import os
from pathlib import Path


class PathValidationError(ValueError):
    pass


def canonical(path: str | os.PathLike[str]) -> Path:
    return Path(os.path.realpath(os.path.expanduser(os.fspath(path))))


def is_within(path: Path, root: Path) -> bool:
    try:
        p = os.path.normcase(str(canonical(path)))
        r = os.path.normcase(str(canonical(root)))
        return os.path.commonpath([p, r]) == r
    except ValueError:  # different drives on Windows
        return False


def validate_scan_root(raw: str, forbidden: list[Path] | None = None) -> Path:
    """Validate a folder the user asked to scan and return its canonical path."""
    if not raw or "\x00" in raw:
        raise PathValidationError("Folder path is empty or contains invalid characters")
    expanded = os.path.expanduser(raw.strip())
    if not os.path.isabs(expanded):
        raise PathValidationError("Folder path must be absolute, e.g. D:\\CCTV\\Exports")
    root = canonical(expanded)
    if not root.exists():
        raise PathValidationError("Folder does not exist")
    if not root.is_dir():
        raise PathValidationError("Path is not a folder")
    for f in forbidden or []:
        # Scanning the app's own data directory would index thumbnails and clips.
        if is_within(root, f) or is_within(f, root):
            raise PathValidationError("Folder overlaps the application data directory")
    return root
