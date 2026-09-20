FROM python:3.12-slim
WORKDIR /app
COPY src/ /app
RUN pip install --no-cache-dir \
    "a2a-sdk[http-server]==1.1.0" \
    "httpx>=0.27.0" \
    "uvicorn>=0.30.0" \
    "click>=8.0.0" \
    "pydantic>=2.7,<3" \
    "pydantic-settings>=2.3,<3" \
    "pyyaml>=6.0,<7" \
    "numpy>=1.26,<3" \
    "pandas>=2.2,<3" \
    "h3>=4.0,<5" \
    "shapely>=2.0,<3" \
    "sqlalchemy>=2.0,<3" \
    "psycopg[binary]>=3.2,<4" \
    "geoalchemy2>=0.15,<1" \
    "fastapi>=0.115,<1" \
    "tenacity>=8.3,<10" \
    "openai>=1.0"
# Local development database on the host (read-only use). Override with DATABASE_URL if needed.
ENV PYTHONUNBUFFERED=1 \
    DATABASE_URL=postgresql+psycopg://sitescout:sitescout@host.docker.internal:5433/sitescout
RUN useradd --create-home --uid 10001 agent
USER agent
CMD ["python", "__main__.py", "--host", "0.0.0.0", "--port", "8000"]
