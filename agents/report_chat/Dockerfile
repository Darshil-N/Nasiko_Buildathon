FROM python:3.12-slim
WORKDIR /app
COPY src/ /app
RUN pip install --no-cache-dir \
    "a2a-sdk[http-server]==1.1.0" \
    "httpx>=0.27.0" \
    "uvicorn>=0.30.0" \
    "click>=8.0.0" \
    "pydantic>=2.7,<3" \
    "tenacity>=8.3,<10" \
    "openai>=1.0"
ENV PYTHONUNBUFFERED=1
RUN useradd --create-home --uid 10001 agent
USER agent
CMD ["python", "__main__.py", "--host", "0.0.0.0", "--port", "8000"]
