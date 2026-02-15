import logging
import time
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, Request, Response
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.metrics import metrics_payload, record_http_metrics
from app.services.llm import get_llm

app = FastAPI(title=settings.APP_NAME, version="0.1.0")

setup_logging(settings.LOG_LEVEL)
logger = logging.getLogger("app")

def lc_config(request: Request, run_name: str, tags: list[str]) -> dict:
    return {
        "run_name": run_name,
        "tags": ["llm-api-service", settings.ENV, *tags],
        "metadata": {
            "request_id": getattr(request.state, "request_id", None),
            "path": request.url.path,
            "method": request.method,
        },
    }

# In-memory job store (resets on server restart)
JOBS: dict[str, dict] = {}


def run_ingest(job_id: str, source: str) -> None:
    try:
        JOBS[job_id] = {"status": "running", "progress": 0, "source": source}

        for i in range(1, 6):
            time.sleep(1)
            JOBS[job_id]["progress"] = i * 20

        JOBS[job_id]["status"] = "completed"
        JOBS[job_id]["result"] = {"message": f"Ingested source: {source}"}

    except Exception as e:
        JOBS[job_id] = {
            "status": "failed",
            "progress": JOBS.get(job_id, {}).get("progress", 0),
            "source": source,
            "error": str(e),
        }


def _metric_path(request: Request) -> str:
    """Use route template to avoid high-cardinality Prometheus labels."""
    route = request.scope.get("route")
    return getattr(route, "path", request.url.path)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid4())
    request.state.request_id = request_id

    start = time.perf_counter()
    path_label = _metric_path(request)
    status = "500"

    try:
        response = await call_next(request)
        status = str(response.status_code)
        response.headers["x-request-id"] = request_id
        return response

    except Exception:
        logger.exception(
            "request_id=%s method=%s path=%s status=500",
            request_id,
            request.method,
            request.url.path,
        )
        raise

    finally:
        duration_s = time.perf_counter() - start

        if path_label != "/metrics":
            record_http_metrics(
                method=request.method,
                path=path_label,
                status=status,
                duration_s=duration_s,
            )

        # Logs
        logger.info(
            "request_id=%s method=%s path=%s status=%s duration_ms=%.2f",
            request_id,
            request.method,
            path_label,
            status,
            duration_s * 1000,
        )


@app.get("/")
def root():
    return {"message": "LLM API Service is running"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/metrics")
def metrics():
    payload, content_type = metrics_payload()
    return Response(content=payload, media_type=content_type)


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str


class IngestRequest(BaseModel):
    source: str


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, request: Request):
    llm = get_llm()
    cfg = lc_config(request, run_name="chat", tags=["chat"])
    res = llm.invoke([HumanMessage(content=req.message)], config=cfg)
    return ChatResponse(reply=res.content)



# SSE streaming (best for web UI)
@app.post("/chat/stream")
def chat_stream(req: ChatRequest, request: Request):
    llm = get_llm()

    cfg = lc_config(request, run_name="chat_stream_sse", tags=["chat", "stream", "sse"])


    def generate():
        buffer = ""

        # NEW: send request_id as first SSE event
        yield f"event: meta\ndata: request_id={getattr(request.state, 'request_id', '')}\n\n"
       
        try:
            for chunk in llm.stream([HumanMessage(content=req.message)], config=cfg):
                token = getattr(chunk, "content", "") or ""
                if not token:
                    continue

                buffer += token

                if token.endswith((" ", "\n")) or len(buffer) >= 80:
                    yield f"data: {buffer}\n\n"
                    buffer = ""

            if buffer:
                yield f"data: {buffer}\n\n"

        except Exception as e:
            yield f"event: error\ndata: {type(e).__name__}: {e}\n\n"
            raise
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# Plain text streaming (best for curl)
@app.post("/chat/stream-text")
def chat_stream_text(req: ChatRequest, request: Request):
    llm = get_llm()

    cfg = lc_config(request, run_name="chat_stream_text", tags=["chat", "stream", "text"])


    def generate():
        # ✅ ADD THIS LINE (first yield)
        yield f"[request_id={getattr(request.state, 'request_id', '')}]\n"
        
        buffer = ""
        try:
            for chunk in llm.stream([HumanMessage(content=req.message)], config=cfg):
                token = getattr(chunk, "content", "") or ""
                if not token:
                    continue

                buffer += token
                if token.endswith((" ", "\n")) or len(buffer) >= 80:
                    yield buffer
                    buffer = ""

            if buffer:
                yield buffer

        except Exception as e:
            yield f"\n[ERROR] {type(e).__name__}: {e}\n"
            raise

    return StreamingResponse(generate(), media_type="text/plain")


@app.post("/ingest")
def ingest(req: IngestRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid4())
    JOBS[job_id] = {"status": "queued", "progress": 0, "source": req.source}
    background_tasks.add_task(run_ingest, job_id, req.source)
    return {"job_id": job_id, "status": "queued"}


@app.get("/status/{job_id}")
def status(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        return {"job_id": job_id, "status": "not_found"}
    return {"job_id": job_id, **job}


@app.get("/trace-check")
def trace_check(request: Request):
    return {
        "langsmith_tracing": bool(settings.LANGSMITH_TRACING),
        "langsmith_project": settings.LANGSMITH_PROJECT,
        "has_langsmith_api_key": bool(settings.LANGSMITH_API_KEY),
        "request_id": getattr(request.state, "request_id", None),
    }
