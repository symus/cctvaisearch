"""The ``scan`` job: walk a library folder and record video metadata."""

from __future__ import annotations

from pathlib import Path

from .jobs import JobContext
from .scanner import ScanSummary, scan_folder

PROGRESS_EVERY = 5


def run_scan_job(ctx: JobContext) -> dict:
    root = Path(ctx.job.params["path"])
    if not root.is_dir():
        raise RuntimeError("Folder is no longer available")

    def on_progress(count: int, summary: ScanSummary, path: Path | None) -> None:
        if count % PROGRESS_EVERY == 0:
            # The total is unknown while walking, so report running counts.
            ctx.update(result=summary.as_dict())

    summary = scan_folder(
        ctx.session, root, ctx.settings, on_progress=on_progress, should_stop=ctx.check
    )
    return summary.as_dict()
