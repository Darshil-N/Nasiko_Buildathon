# SiteScout backend image. Build context is the repository root:
#   docker compose build backend
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencies first so this layer is cached until the requirement files change.
COPY requirements/base.txt requirements/backend.txt requirements/
RUN pip install -r requirements/backend.txt

COPY backend/ backend/
COPY pipelines/ pipelines/
COPY scoring/ scoring/
COPY shared/ shared/
COPY config/ config/

# Run as an unprivileged user.
RUN useradd --create-home --uid 10001 app && chown -R app:app /app
USER app

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=5 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/v1/health', timeout=4).status == 200 else 1)"

# Migrations are never run automatically; the owner approves each database change.
CMD ["uvicorn", "backend.app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
