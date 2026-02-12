import time
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from app.core.config import settings
from app.services.llm import get_llm

app = FastAPI(title=settings.APP_NAME, version="0.1.0")

# JOBS as a module-level global variable,creates an empty dict. so all endpoints and background functions can access it.
# JOBS is of type dictionary: key is string type and value is dictionary
# e.g. JOBS= {"job1": {"status": "queued", "progress": 0, "source": "folderA"}, "job2": {"status": "queued", "progress": 0, "source": "folderB"},}
# JOBS["job1"] = {"status": "queued", "progress": 0, "source": "folderA"}
# JOBS["job1"]["progress"]--> is 0
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


@app.get("/")
def root():
    return {"message": "LLM API Service is running"}


@app.get("/health")
def health():
    return {"status": "ok"}


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str


class IngestRequest(BaseModel):
    source: str


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    llm = get_llm()
    res = llm.invoke([HumanMessage(content=req.message)])
    return ChatResponse(reply=res.content)


# SSE streaming (best for web UI)
@app.post("/chat/stream")
def chat_stream(req: ChatRequest):
    llm = get_llm()

    def generate():
        buffer = ""
        for chunk in llm.stream([HumanMessage(content=req.message)]):
            token = getattr(chunk, "content", "")
            if not token:
                continue

            buffer += token

            # flush on natural boundaries or buffer size
            if token.endswith((" ", "\n")) or len(buffer) >= 80:
                yield f"data: {buffer}\n\n"
                buffer = ""

        if buffer:
            yield f"data: {buffer}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# Plain text streaming (best for curl)
@app.post("/chat/stream-text")
def chat_stream_text(req: ChatRequest):
    llm = get_llm()

    def generate():
        buffer = ""
        for chunk in llm.stream([HumanMessage(content=req.message)]):
            token = getattr(chunk, "content", "")
            if not token:
                continue

            buffer += token
            if token.endswith((" ", "\n")) or len(buffer) >= 80:
                yield buffer
                buffer = ""

        if buffer:
            yield buffer

    return StreamingResponse(generate(), media_type="text/plain")


@app.post("/ingest")
def ingest(req: IngestRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid4())

    # Save initial state
    JOBS[job_id] = {"status": "queued", "progress": 0, "source": req.source}

    # Run in background after returning response
    background_tasks.add_task(run_ingest, job_id, req.source)

    return {"job_id": job_id, "status": "queued"}


@app.get("/status/{job_id}")
def status(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        return {"job_id": job_id, "status": "not_found"}
    return {"job_id": job_id, **job}
