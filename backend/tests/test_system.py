from sqlalchemy import inspect, text


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["schema_revision"] == "0001"


def test_system_info_reports_cpu_provider_and_models(client):
    body = client.get("/api/system-info").json()
    hw = body["hardware"]
    assert hw["cpu_logical_cores"] >= 1
    assert hw["ram_total_mb"] > 0
    assert hw["inference_provider"] in ("cpu", "cuda", "directml")
    assert hw["inference_provider_reason"]
    assert {t["name"] for t in hw["tools"]} == {"ffmpeg", "ffprobe"}
    assert body["models"]["face"]["status"] == "not_installed"


def test_stats_empty(client):
    body = client.get("/api/stats").json()
    assert body["total_videos"] == 0
    assert body["by_status"]["pending"] == 0


def test_schema_tables_and_foreign_keys(app):
    engine = app.state.engine
    tables = set(inspect(engine).get_table_names())
    assert {
        "videos", "detections", "embeddings", "index_jobs",
        "search_sessions", "search_results", "library_folders", "alembic_version",
    } <= tables
    with engine.connect() as conn:
        assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1


def test_migrations_are_idempotent(settings):
    from app.main import create_app

    create_app(settings, start_worker=False)
    create_app(settings, start_worker=False)  # second start must not fail


def test_structured_404(client):
    r = client.get("/api/videos/999")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_structured_validation_error(client):
    r = client.get("/api/videos", params={"limit": 0})
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "validation_error"
    assert err["details"][0]["loc"][-1] == "limit"


def test_openapi_lists_endpoints(client):
    paths = client.get("/openapi.json").json()["paths"]
    for p in ("/api/health", "/api/system-info", "/api/videos/scan", "/api/videos",
              "/api/videos/{video_id}", "/api/index-jobs/{job_id}", "/api/index-jobs/{job_id}/cancel"):
        assert p in paths
