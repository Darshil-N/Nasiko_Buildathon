"""One LLM call through the platform's OpenAI-compatible endpoint.

Nasiko deploys agents with ``OPENAI_BASE_URL`` pointing at its LLM Router and an
``OPENAI_API_KEY`` that is a short-lived identity token, not a real provider key. The router
decides the provider and model, so the ``model`` sent here is only a placeholder.
"""

from __future__ import annotations

import os

import httpx

SYSTEM_PROMPT = "You are a concise assistant. Answer in one or two sentences."


class LlmError(RuntimeError):
    """The LLM call failed; the message says why, without leaking secrets."""


async def ask(prompt: str, *, timeout_s: float = 180.0) -> str:
    """Send ``prompt`` and return the model's reply text."""
    base = os.environ.get("OPENAI_BASE_URL", "").rstrip("/")
    if not base:
        raise LlmError("OPENAI_BASE_URL is not set in the agent environment")
    headers = {"Authorization": f"Bearer {os.environ.get('OPENAI_API_KEY', '')}"}
    body = {
        "model": os.environ.get("OPENAI_MODEL", "router-decides"),
        "temperature": 0,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    }
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        try:
            response = await client.post(f"{base}/chat/completions", headers=headers, json=body)
        except httpx.HTTPError as exc:
            raise LlmError(f"could not reach the LLM endpoint at {base}: {exc}") from exc
    if response.status_code != 200:
        raise LlmError(f"LLM endpoint returned HTTP {response.status_code}: {response.text[:300]}")
    try:
        return str(response.json()["choices"][0]["message"]["content"]).strip()
    except (KeyError, IndexError, ValueError) as exc:
        raise LlmError(f"unexpected LLM response shape: {response.text[:300]}") from exc
