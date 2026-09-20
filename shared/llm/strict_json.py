"""Strict JSON helper for LLM structured outputs."""

import json
import logging
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from shared.llm.client import LLMClient

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMJsonParseError(Exception):
    """Raised when the LLM output cannot be parsed into the target Pydantic model."""


def generate_strict_json(
    client: LLMClient,
    model: type[T],
    messages: list[dict[str, str]],
    *,
    max_retries: int = 1,
    **kwargs: Any,
) -> T:
    """Generate a strict JSON response matching a Pydantic model.

    Appends JSON schema instructions to the prompt and validates the output.
    Retries up to max_retries on validation errors.
    """
    schema = model.model_json_schema()
    system_prompt = (
        "You must respond with valid JSON only. "
        "Do not include markdown blocks or any other text. "
        f"Your output must exactly match this JSON schema:\n\n{json.dumps(schema)}"
    )

    # Prepend the strict JSON system prompt
    extended_messages = [{"role": "system", "content": system_prompt}, *messages]

    # Force JSON mode for OpenAI-compatible endpoints
    kwargs["response_format"] = {"type": "json_object"}

    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            raw_response = client.generate(extended_messages, **kwargs)
            return model.model_validate_json(raw_response)
        except ValidationError as e:
            last_error = e
            logger.warning(
                "Attempt %d/%d failed JSON validation: %s",
                attempt + 1,
                max_retries + 1,
                e,
            )
            # Add the error feedback to the conversation for the next attempt
            if attempt < max_retries:
                extended_messages.extend(
                    [
                        {"role": "assistant", "content": raw_response},
                        {
                            "role": "user",
                            "content": (
                                "Your previous response failed validation. "
                                f"Please fix these errors and return valid JSON:\n{e}"
                            ),
                        },
                    ]
                )
        except json.JSONDecodeError as e:
            last_error = e
            logger.warning(
                "Attempt %d/%d failed JSON decoding: %s",
                attempt + 1,
                max_retries + 1,
                e,
            )
            if attempt < max_retries:
                extended_messages.extend(
                    [
                        {"role": "assistant", "content": raw_response},
                        {
                            "role": "user",
                            "content": (
                                "Your previous response was not valid JSON. "
                                "Return ONLY raw valid JSON."
                            ),
                        },
                    ]
                )

    raise LLMJsonParseError(
        f"Failed to generate valid JSON after {max_retries + 1} attempts"
    ) from last_error
