"""Database-backed background job runner.

Jobs are rows in ``index_jobs``; a small thread pool executes them so HTTP
handlers return immediately. State lives in the database, so after a restart
jobs that were queued or running are re-queued and resumed (job handlers are
written to be idempotent / incremental).
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from ..config import Settings
from ..models import IndexJob, JobStatus, JobType

log = logging.getLogger(__name__)


class JobCancelled(Exception):
    pass


class JobInterrupted(Exception):
    """The application is shutting down; the job will resume on next start."""


class JobContext:
    def __init__(self, runner: JobRunner, session: Session, job: IndexJob):
        self.runner = runner
        self.session = session
        self.job = job
        self.settings = runner.settings

    def check(self) -> None:
        """Raise if the job should stop. Call between units of work."""
        # Read the flag with a fresh query so cancellation from the API is seen.
        # An explicit cancel wins over shutdown, which would otherwise re-queue.
        cancelled = self.session.scalar(
            select(IndexJob.cancel_requested).where(IndexJob.id == self.job.id)
        )
        if cancelled:
            raise JobCancelled()
        if self.runner.stopping.is_set():
            raise JobInterrupted()

    def update(self, **fields) -> None:
        for key, value in fields.items():
            setattr(self.job, key, value)
        self.session.commit()


Handler = Callable[[JobContext], dict | None]


class JobRunner:
    def __init__(self, settings: Settings, session_factory: sessionmaker[Session]):
        self.settings = settings
        self.session_factory = session_factory
        self.handlers: dict[JobType, Handler] = {}
        self.stopping = threading.Event()
        self._executor: ThreadPoolExecutor | None = None

    def register(self, job_type: JobType, handler: Handler) -> None:
        self.handlers[job_type] = handler

    def start(self) -> None:
        self.stopping.clear()
        self._executor = ThreadPoolExecutor(
            max_workers=max(1, self.settings.max_concurrent_jobs), thread_name_prefix="job"
        )
        self._resume_pending()

    def shutdown(self, wait: bool = True) -> None:
        self.stopping.set()
        if self._executor:
            self._executor.shutdown(wait=wait, cancel_futures=True)
            self._executor = None

    def enqueue(self, job_type: JobType, params: dict) -> IndexJob:
        with self.session_factory() as session:
            job = IndexJob(job_type=job_type, status=JobStatus.queued, params=params)
            session.add(job)
            session.commit()
            session.refresh(job)
        self._submit(job.id)
        return job

    def cancel(self, session: Session, job: IndexJob) -> IndexJob:
        if job.status in (JobStatus.completed, JobStatus.failed, JobStatus.cancelled):
            return job
        job.cancel_requested = True
        if job.status == JobStatus.queued:
            job.status = JobStatus.cancelled
            job.finished_at = datetime.now(timezone.utc)
        session.commit()
        return job

    def _resume_pending(self) -> None:
        with self.session_factory() as session:
            jobs = session.scalars(
                select(IndexJob)
                .where(IndexJob.status.in_([JobStatus.queued, JobStatus.running]))
                .order_by(IndexJob.id)
            ).all()
            for job in jobs:
                if job.status == JobStatus.running:
                    log.info("Resuming job %s interrupted by a restart", job.id)
                    job.status = JobStatus.queued
            session.commit()
            ids = [j.id for j in jobs]
        for job_id in ids:
            self._submit(job_id)

    def _submit(self, job_id: int) -> None:
        if self._executor is None:
            return  # not started (e.g. tests); job stays queued until start()
        self._executor.submit(self._run, job_id)

    def run_sync(self, job_id: int) -> None:
        """Execute a job in the current thread (used by tests and CLI)."""
        self._run(job_id)

    def _run(self, job_id: int) -> None:
        with self.session_factory() as session:
            job = session.get(IndexJob, job_id)
            if job is None or job.status != JobStatus.queued:
                return
            if job.cancel_requested:
                job.status = JobStatus.cancelled
                session.commit()
                return
            handler = self.handlers.get(job.job_type)
            if handler is None:
                job.status = JobStatus.failed
                job.error_message = f"No handler for job type '{job.job_type.value}'"
                session.commit()
                return
            job.status = JobStatus.running
            job.started_at = job.started_at or datetime.now(timezone.utc)
            job.error_message = None
            session.commit()

            ctx = JobContext(self, session, job)
            try:
                result = handler(ctx)
            except JobInterrupted:
                session.rollback()
                job.status = JobStatus.queued
                session.commit()
                return
            except JobCancelled:
                session.rollback()
                job.status = JobStatus.cancelled
            except Exception as exc:  # noqa: BLE001 - recorded on the job
                log.exception("Job %s failed", job_id)
                session.rollback()
                job.status = JobStatus.failed
                job.error_message = str(exc) or exc.__class__.__name__
            else:
                job.status = JobStatus.completed
                job.progress = 1.0
                if result is not None:
                    job.result = result
            job.finished_at = datetime.now(timezone.utc)
            session.commit()
