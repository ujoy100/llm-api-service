import os

from langchain_groq import ChatGroq

from app.core.config import settings


def get_llm() -> ChatGroq:
    # Ensure Groq key is available to the SDK
    if settings.GROQ_API_KEY:
        os.environ["GROQ_API_KEY"] = settings.GROQ_API_KEY

    # LangSmith tracing (optional)
    if settings.LANGSMITH_API_KEY:
        os.environ["LANGSMITH_API_KEY"] = settings.LANGSMITH_API_KEY
        os.environ["LANGSMITH_PROJECT"] = settings.LANGSMITH_PROJECT
        os.environ["LANGSMITH_TRACING"] = "true" if settings.LANGSMITH_TRACING else "false"
    else:
        # If no key, force tracing off (avoids noisy errors)
        os.environ["LANGSMITH_TRACING"] = "false"

    return ChatGroq(
        model="llama-3.1-8b-instant",
        temperature=0.2,
        streaming=True,
    )
