"""Fast content fingerprint for change and duplicate detection.

Hashing every byte of 2,000 hours of footage would take hours, so we hash the
file size plus three fixed-size chunks (start, middle, end). Small files are
hashed completely. Combined with size and mtime this reliably detects changed
and duplicated recordings without reading whole files.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


def fingerprint(path: Path, chunk_bytes: int = 1024 * 1024) -> str:
    size = path.stat().st_size
    h = hashlib.sha256()
    h.update(str(size).encode())
    with path.open("rb") as f:
        if size <= chunk_bytes * 3:
            for block in iter(lambda: f.read(1024 * 1024), b""):
                h.update(block)
        else:
            for offset in (0, size // 2 - chunk_bytes // 2, size - chunk_bytes):
                f.seek(offset)
                h.update(f.read(chunk_bytes))
    return h.hexdigest()
