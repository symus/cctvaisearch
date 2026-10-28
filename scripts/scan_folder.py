"""Scan a video folder from the command line (same logic as the web UI).

Usage (from the repo root, with the backend venv active):
    python scripts/scan_folder.py "D:\\CCTV\\Exports"
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.config import get_settings  # noqa: E402
from app.db import create_db_engine, make_session_factory, run_migrations  # noqa: E402
from app.services.paths import PathValidationError, validate_scan_root  # noqa: E402
from app.services.scanner import scan_folder  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan a video folder recursively.")
    parser.add_argument("folder", help="Absolute path of the folder to scan")
    args = parser.parse_args()

    settings = get_settings()
    try:
        root = validate_scan_root(args.folder, forbidden=[settings.data_dir])
    except PathValidationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    engine = create_db_engine(settings)
    run_migrations(engine)
    started = time.perf_counter()

    def progress(count, summary, _path):
        print(f"\r{count} files checked ({summary.new} new, {summary.failed} failed)", end="", flush=True)

    with make_session_factory(engine)() as session:
        summary = scan_folder(session, root, settings, on_progress=progress)
    print(f"\nDone in {time.perf_counter() - started:.1f}s: {summary.as_dict()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
