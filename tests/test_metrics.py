from fastapi.testclient import TestClient

from app.main import app


def test_metrics_endpoint_works():
    client = TestClient(app, raise_server_exceptions=False)

    r = client.get("/metrics")
    assert r.status_code == 200
    assert "text/plain" in r.headers.get("content-type", "")

    body = r.text
    assert "http_requests_total" in body
    assert "http_request_duration_seconds" in body
