# LLM API Service (FastAPI)

A job-ready FastAPI microservice that provides:
- **LLM chat** (`/chat`)
- **Streaming responses** via **SSE** (`/chat/stream`) and **plain text** (`/chat/stream-text`)
- **Background job runner** for long tasks (`/ingest` + `/status/{job_id}`)
- **Observability**: request logging + Prometheus metrics (`/metrics`) + tracing check (`/trace-check`)
- **Dockerized deployment** (runtime + test stages)
- **GitHub Actions CI** (ruff + pytest)

---

## Features

### 1) Chat (JSON)
- `POST /chat` → returns `{ "reply": "..." }`

### 2) Streaming
- `POST /chat/stream` → **SSE** streaming (best for web UI)
  - sends a `meta` event containing `request_id`
  - streams `data:` chunks
  - ends with `data: [DONE]`
- `POST /chat/stream-text` → **plain text** streaming (best for curl)
  - first line prints `[request_id=...]`

### 3) Background jobs (in-memory)
- `POST /ingest` → returns `job_id` (queued)
- `GET /status/{job_id}` → returns job status/progress/result  
> Note: This uses an in-memory `JOBS` dict (resets on restart). Replace with Redis later for production.

### 4) Observability
- `x-request-id`:
  - If the client sends `x-request-id`, the service reuses it
  - Otherwise, the service generates a UUID
  - The response always includes `x-request-id`
- `GET /metrics` exposes Prometheus metrics:
  - `http_requests_total{method,path,status}`
  - `http_request_duration_seconds{method,path}` (histogram)
- `GET /trace-check` confirms whether tracing settings are enabled (LangSmith config)

### Observability demo (logs + metrics + request_id)

1) Generate traffic
```bash
curl -s http://127.0.0.1:8000/health >/dev/null
curl -s http://127.0.0.1:8000/ >/dev/null
curl -N -X POST http://127.0.0.1:8000/chat/stream-text \
  -H "Content-Type: application/json" \
  -d '{"message":"Give 3 bullets about Kuwait"}'

---

## Project structure

```text
llm-api-service/
  app/
    main.py
    core/
      config.py
      logging.py
      metrics.py
    services/
      llm.py
  tests/
    test_api.py
    test_metrics.py
  Dockerfile
  .dockerignore
  pyproject.toml
  uv.lock
  README.md
