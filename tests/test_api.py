from fastapi.testclient import TestClient

from app.main import app


def test_healthz():
    with TestClient(app) as client:
        assert client.get("/healthz").json() == {"status": "ok"}


def test_root_serves_inspection_page():
    with TestClient(app) as client:
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "PhishGuard — Email Inspection" in resp.text
        assert 'id="email-form"' in resp.text


def test_metrics_exposed():
    with TestClient(app) as client:
        assert "answer_requests_total" in client.get("/metrics").text


def test_classify_endpoint():
    with TestClient(app) as client:
        email = "From: a@b.com\nSubject: verify\n\nEnter your password to verify your account."
        resp = client.post("/v1/classify", json={"text": email})
        assert resp.status_code == 200
        data = resp.json()
        assert data["label"] in {"phishing", "legit", "suspicious"}
        assert 0.0 <= data["confidence"] <= 1.0
        assert resp.headers["x-request-id"]


def test_classify_rejects_empty_text():
    with TestClient(app) as client:
        assert client.post("/v1/classify", json={"text": ""}).status_code == 422
