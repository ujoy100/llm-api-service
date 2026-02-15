import os

from langchain_groq import ChatGroq

from app.core.config import settings


def _apply_runtime_env() -> None:
    """Put settings into real process env vars (LangSmith/Groq read from os.environ)."""
    if settings.GROQ_API_KEY:
        os.environ["GROQ_API_KEY"] = settings.GROQ_API_KEY

    # LangSmith tracing
    if settings.LANGSMITH_API_KEY:
        os.environ["LANGSMITH_API_KEY"] = settings.LANGSMITH_API_KEY
        os.environ["LANGSMITH_PROJECT"] = settings.LANGSMITH_PROJECT
        os.environ["LANGSMITH_ENDPOINT"] = getattr(
            settings, "LANGSMITH_ENDPOINT", "https://api.smith.langchain.com"
        )
        os.environ["LANGSMITH_TRACING"] = "true" if settings.LANGSMITH_TRACING else "false"

        # Backward-compatible flag (some stacks still read this)
        os.environ["LANGCHAIN_TRACING_V2"] = os.environ["LANGSMITH_TRACING"]


def get_llm() -> ChatGroq:
    _apply_runtime_env()
    return ChatGroq(
        model="llama-3.1-8b-instant",
        temperature=0.2,
        streaming=True,
    )
