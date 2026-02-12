from fastapi.testclient import TestClient

from app.main import app

# Important: don't raise server exceptions; return 500 so we can assert it
client = TestClient(app, raise_server_exceptions=False)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_root():
    r = client.get("/")
    assert r.status_code == 200
    assert "message" in r.json()


def test_chat_requires_api_key_or_returns_error():
    """
    /chat calls the real LLM, so this test behaves differently depending on whether
    GROQ_API_KEY is set in your environment.

    - If GROQ_API_KEY is present, we expect a normal reply.
    - If not present, we expect a non-200 or an error.
    """
    r = client.post("/chat", json={"message": "Say hello in 2 words"})
    if r.status_code == 200:
        data = r.json()
        assert "reply" in data
        assert isinstance(data["reply"], str)
        assert len(data["reply"]) > 0
    else:
        # No key / provider error is acceptable in CI
        assert r.status_code in (400, 401, 403, 500)


def test_ingest_and_status():
    # Start a job
    r = client.post("/ingest", json={"source": "folderA"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    # Status should exist
    s = client.get(f"/status/{job_id}")
    assert s.status_code == 200
    payload = s.json()
    assert payload["job_id"] == job_id
    assert payload["status"] in ("queued", "running", "completed")
    assert "progress" in payload
