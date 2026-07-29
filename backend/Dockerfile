FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY backend/requirements.lock ./backend/requirements.lock
COPY backend ./backend
RUN pip install --upgrade pip \
    && pip install -r backend/requirements.lock \
    && pip install --no-deps -e .

EXPOSE 8002

CMD ["python", "-m", "uvicorn", "backend.server:app", "--host", "0.0.0.0", "--port", "8002", "--no-date-header"]
