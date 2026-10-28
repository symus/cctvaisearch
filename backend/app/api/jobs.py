from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..errors import AppError
from ..models import IndexJob
from ..schemas import IndexJobOut
from ..services.jobs import JobRunner
from .deps import get_db, get_runner

router = APIRouter(prefix="/api/index-jobs", tags=["jobs"])


@router.get("", response_model=list[IndexJobOut])
def list_jobs(limit: int = Query(50, ge=1, le=500), db: Session = Depends(get_db)):
    jobs = db.scalars(select(IndexJob).order_by(IndexJob.id.desc()).limit(limit)).all()
    return [IndexJobOut.model_validate(j) for j in jobs]


@router.get("/{job_id}", response_model=IndexJobOut)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(IndexJob, job_id)
    if job is None:
        raise AppError(404, "not_found", "Job not found")
    return IndexJobOut.model_validate(job)


@router.post("/{job_id}/cancel", response_model=IndexJobOut)
def cancel_job(job_id: int, db: Session = Depends(get_db), runner: JobRunner = Depends(get_runner)):
    job = db.get(IndexJob, job_id)
    if job is None:
        raise AppError(404, "not_found", "Job not found")
    return IndexJobOut.model_validate(runner.cancel(db, job))
