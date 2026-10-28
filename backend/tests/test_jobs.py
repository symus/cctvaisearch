import threading

from app.models import IndexJob, JobStatus, JobType
from app.services.jobs import JobRunner


def make_runner(app):
    return JobRunner(app.state.settings, app.state.session_factory)


def test_running_job_is_resumed_after_restart(app, db):
    job = IndexJob(job_type=JobType.scan, status=JobStatus.running, params={"path": "/x"})
    db.add(job)
    db.commit()

    ran = threading.Event()
    runner = make_runner(app)
    runner.register(JobType.scan, lambda ctx: ran.set() or {"ok": True})
    runner.start()
    try:
        assert ran.wait(5)
    finally:
        runner.shutdown(wait=True)
    db.refresh(job)
    assert job.status == JobStatus.completed and job.result == {"ok": True}


def test_handler_error_is_recorded(app, db):
    runner = make_runner(app)

    def boom(ctx):
        raise RuntimeError("decoder exploded")

    runner.register(JobType.scan, boom)
    job = runner.enqueue(JobType.scan, {})
    runner.run_sync(job.id)
    db.expire_all()
    stored = db.get(IndexJob, job.id)
    assert stored.status == JobStatus.failed
    assert stored.error_message == "decoder exploded"


def test_cancel_while_running(app, db):
    runner = make_runner(app)
    started, release = threading.Event(), threading.Event()

    def slow(ctx):
        started.set()
        release.wait(5)
        ctx.check()
        return {"finished": True}

    runner.register(JobType.scan, slow)
    runner.start()
    try:
        job = runner.enqueue(JobType.scan, {})
        assert started.wait(5)
        with app.state.session_factory() as s:
            runner.cancel(s, s.get(IndexJob, job.id))
        release.set()
    finally:
        runner.shutdown(wait=True)
    db.expire_all()
    assert db.get(IndexJob, job.id).status == JobStatus.cancelled


def test_shutdown_requeues_running_job(app, db):
    runner = make_runner(app)
    started = threading.Event()

    def waits_for_shutdown(ctx):
        started.set()
        while True:
            ctx.check()
            runner.stopping.wait(0.05)

    runner.register(JobType.scan, waits_for_shutdown)
    runner.start()
    job = runner.enqueue(JobType.scan, {})
    assert started.wait(5)
    runner.shutdown(wait=True)
    db.expire_all()
    assert db.get(IndexJob, job.id).status == JobStatus.queued


def test_unknown_job_type_fails_cleanly(app, db):
    runner = make_runner(app)  # no handlers registered
    job = runner.enqueue(JobType.index, {})
    runner.run_sync(job.id)
    db.expire_all()
    stored = db.get(IndexJob, job.id)
    assert stored.status == JobStatus.failed
    assert "No handler" in stored.error_message
