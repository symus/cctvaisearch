"""FastAPI application factory."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .api import jobs, system, videos
from .config import Settings, get_settings
from .db import create_db_engine, make_session_factory, run_migrations
from .errors import install_error_handlers
from .models import JobType
from .security import install_security
from .services.hardware import detect_hardware
from .services.jobs import JobRunner
from .services.scan_job import run_scan_job

log = logging.getLogger("cctv")

FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"

# The built UI loads nothing from other origins.
SPA_HEADERS = {
    "Content-Security-Policy": "default-src 'self'; img-src 'self' data: blob:; "
    "media-src 'self' blob:; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}


def create_app(settings: Settings | None = None, *, start_worker: bool = True) -> FastAPI:
    settings = settings or get_settings()
    engine = create_db_engine(settings)
    run_migrations(engine)
    session_factory = make_session_factory(engine)
    runner = JobRunner(settings, session_factory)
    runner.register(JobType.scan, run_scan_job)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        hw = detect_hardware(settings.ffmpeg_path, settings.ffprobe_path)
        log.info(
            "CCTV AI Search %s | data=%s | RAM %d MB | inference=%s (%s)",
            __version__, settings.data_dir, hw.ram_total_mb,
            hw.inference_provider, hw.inference_provider_reason,
        )
        for tool in hw.tools:
            if not tool.available:
                log.warning("%s not found on PATH - video scanning will fail", tool.name)
        if start_worker:
            runner.start()
        yield
        runner.shutdown(wait=True)
        engine.dispose()

    app = FastAPI(
        title="CCTV AI Search",
        version=__version__,
        description="Local-first candidate search over CCTV recordings. "
        "Similarity scores are not proof of identity.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.runner = runner

    install_security(app, settings)
    install_error_handlers(app)
    app.include_router(system.router)
    app.include_router(videos.router)
    app.include_router(jobs.router)
    _mount_frontend(app)
    return app


def _mount_frontend(app: FastAPI) -> None:
    """Serve the built React app (``npm run build``) from the same origin."""
    if not (FRONTEND_DIST / "index.html").is_file():
        return
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{spa_path:path}", include_in_schema=False)
    def spa(spa_path: str):
        if spa_path.startswith("api/"):
            from .errors import AppError

            raise AppError(404, "not_found", "Not found")
        return FileResponse(FRONTEND_DIST / "index.html", headers=SPA_HEADERS)
