FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock README.md ./
RUN uv venv --python 3.13
RUN . .venv/bin/activate && uv sync

# Copy only app code into base (runtime stays small)
COPY app ./app


FROM base AS test
# Copy tests only for the test stage
COPY tests ./tests
CMD [".venv/bin/pytest", "-q"]


FROM base AS runtime
EXPOSE 8000
CMD [".venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
