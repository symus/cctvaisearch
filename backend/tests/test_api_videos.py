import shutil

from tests.conftest import requires_ffmpeg


def run_job(app, job_id):
    app.state.runner.run_sync(job_id)


def test_scan_invalid_path(client, tmp_path):
    r = client.post("/api/videos/scan", json={"path": "relative/path"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "invalid_path"
    r = client.post("/api/videos/scan", json={"path": str(tmp_path / "missing")})
    assert r.status_code == 400


def test_scan_rejects_data_dir(client, settings):
    r = client.post("/api/videos/scan", json={"path": str(settings.data_dir)})
    assert r.status_code == 400


def test_scan_missing_body(client):
    assert client.post("/api/videos/scan", json={}).status_code == 422


@requires_ffmpeg
def test_scan_end_to_end(app, client, tmp_path, video_cache):
    lib = tmp_path / "lib"
    (lib / "sub").mkdir(parents=True)
    shutil.copy(video_cache["mp4"], lib / "sub" / "entrance cam.mp4")
    shutil.copy(video_cache["mkv"], lib / "lobby.mkv")

    r = client.post("/api/videos/scan", json={"path": str(lib)})
    assert r.status_code == 202
    job = r.json()
    assert job["status"] == "queued" and job["job_type"] == "scan"

    run_job(app, job["id"])
    job = client.get(f"/api/index-jobs/{job['id']}").json()
    assert job["status"] == "completed"
    assert job["result"]["new"] == 2 and job["progress"] == 1.0

    page = client.get("/api/videos").json()
    assert page["total"] == 2
    assert [v["filename"] for v in page["items"]] == ["lobby.mkv", "entrance cam.mp4"]

    assert client.get("/api/videos", params={"q": "entrance"}).json()["total"] == 1
    assert client.get("/api/videos", params={"q": "%"}).json()["total"] == 0  # escaped
    assert client.get("/api/videos", params={"status": "pending"}).json()["total"] == 2
    assert client.get("/api/videos", params={"status": "bogus"}).status_code == 422

    vid = page["items"][0]["id"]
    detail = client.get(f"/api/videos/{vid}").json()
    assert detail["width"] == 640

    folders = client.get("/api/library-folders").json()
    assert folders[0]["video_count"] == 2

    stats = client.get("/api/stats").json()
    assert stats["total_videos"] == 2 and stats["by_status"]["pending"] == 2
    assert stats["total_duration_seconds"] > 4


def test_cancel_queued_job(app, client, tmp_path):
    (tmp_path / "lib").mkdir()
    job = client.post("/api/videos/scan", json={"path": str(tmp_path / "lib")}).json()
    r = client.post(f"/api/index-jobs/{job['id']}/cancel")
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    run_job(app, job["id"])  # must not run a cancelled job
    assert client.get(f"/api/index-jobs/{job['id']}").json()["status"] == "cancelled"
    assert client.post("/api/index-jobs/999/cancel").status_code == 404


def test_list_jobs(client, tmp_path):
    (tmp_path / "lib").mkdir()
    client.post("/api/videos/scan", json={"path": str(tmp_path / "lib")})
    jobs = client.get("/api/index-jobs").json()
    assert len(jobs) == 1


def test_folder_removed_before_job_runs(app, client, tmp_path):
    d = tmp_path / "gone"
    d.mkdir()
    job = client.post("/api/videos/scan", json={"path": str(d)}).json()
    d.rmdir()
    run_job(app, job["id"])
    body = client.get(f"/api/index-jobs/{job['id']}").json()
    assert body["status"] == "failed"
    assert "no longer available" in body["error_message"]
