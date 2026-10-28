from fastapi.testclient import TestClient


def test_rejects_foreign_origin_on_post(client, tmp_path):
    r = client.post("/api/videos/scan", json={"path": str(tmp_path)},
                    headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden_origin"


def test_allows_frontend_origin(client, tmp_path):
    (tmp_path / "v").mkdir()
    r = client.post("/api/videos/scan", json={"path": str(tmp_path / "v")},
                    headers={"Origin": "http://127.0.0.1:5173"})
    assert r.status_code == 202


def test_cors_header_only_for_allowed_origin(client):
    ok = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    bad = client.get("/api/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in bad.headers


def test_rejects_unknown_host_header(app):
    # DNS rebinding: attacker domain resolving to 127.0.0.1.
    with TestClient(app, base_url="http://attacker.example") as c:
        assert c.get("/api/health").status_code == 400


def test_form_post_is_not_accepted_as_json(client, tmp_path):
    r = client.post("/api/videos/scan", content=f'{{"path": "{tmp_path}"}}',
                    headers={"Content-Type": "text/plain"})
    assert r.status_code == 422
