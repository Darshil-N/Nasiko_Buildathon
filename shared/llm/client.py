"""LLM Client for Nasiko."""

import logging
import os
from typing import Any

from openai import APIConnectionError, APITimeoutError, OpenAI
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

# Primary: Ollama locally
_DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434/v1"
_DEFAULT_OLLAMA_MODEL = "qwen2.5:7b-instruct"

# Backup: OpenRouter
_DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
_DEFAULT_OPENROUTER_MODEL = "meta-llama/llama-3-8b-instruct:free"


class LLMClient:
    """OpenAI-compatible LLM client with automatic fallback."""

    def __init__(self, *, use_router: bool = False, timeout: float = 30.0) -> None:
        """Initialize the client.

        If use_router is True, points to Nasiko's internal LLM router.
        Otherwise points to Ollama (primary) with OpenRouter (backup).
        """
        self.use_router = use_router

        if use_router:
            # Nasiko deploys agents with OPENAI_BASE_URL pointing at its LLM Router and an
            # OPENAI_API_KEY that is a short-lived identity token, not a real provider key (see
            # agents/hello_world/src/llm.py, verified working against the real deployment).
            self.base_url = os.getenv("OPENAI_BASE_URL", "http://localhost:8080/v1")
            self.api_key = os.getenv("OPENAI_API_KEY", "dummy")
            self.model = os.getenv("OPENAI_MODEL", _DEFAULT_OLLAMA_MODEL)
            self.client = OpenAI(base_url=self.base_url, api_key=self.api_key, timeout=timeout)
            self.backup_client = None
        else:
            self.base_url = os.getenv("OLLAMA_BASE_URL", _DEFAULT_OLLAMA_BASE_URL)
            self.api_key = "ollama"
            self.model = os.getenv("OLLAMA_MODEL", _DEFAULT_OLLAMA_MODEL)
            self.client = OpenAI(base_url=self.base_url, api_key=self.api_key, timeout=timeout)

            self.backup_base_url = os.getenv("OPENROUTER_BASE_URL", _DEFAULT_OPENROUTER_BASE_URL)
            self.backup_api_key = os.getenv("OPENROUTER_API_KEY", "")
            self.backup_model = os.getenv("OPENROUTER_MODEL", _DEFAULT_OPENROUTER_MODEL)

            if self.backup_api_key:
                self.backup_client = OpenAI(
                    base_url=self.backup_base_url, api_key=self.backup_api_key, timeout=timeout
                )
            else:
                self.backup_client = None

    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type((APIConnectionError, APITimeoutError)),
        reraise=True,
    )
    def _call_primary(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        """Call the primary LLM with tenacity retries."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,  # type: ignore[arg-type]
            **kwargs,
        )
        return response.choices[0].message.content or ""

    def generate(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        """Generate a response from the LLM.

        Falls back to the backup client if the primary fails due to connection or timeout.
        """
        try:
            return self._call_primary(messages, **kwargs)
        except (APIConnectionError, APITimeoutError) as e:
            if self.backup_client:
                logger.warning(
                    "Primary LLM %s failed (%s). Falling back to backup %s.",
                    self.base_url,
                    e,
                    self.backup_base_url,
                )
                response = self.backup_client.chat.completions.create(
                    model=self.backup_model,
                    messages=messages,  # type: ignore[arg-type]
                    **kwargs,
                )
                return response.choices[0].message.content or ""
            logger.error("Primary LLM %s failed and no backup configured.", self.base_url)
            raise
