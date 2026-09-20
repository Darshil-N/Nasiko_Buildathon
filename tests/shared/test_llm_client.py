"""Tests for the LLM client (steps 1.7.1 - 1.7.4)."""

from unittest.mock import MagicMock, patch

import pytest
from openai import APIConnectionError
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice
from pydantic import BaseModel

from shared.llm.client import LLMClient
from shared.llm.strict_json import LLMJsonParseError, generate_strict_json


def _make_mock_response(content: str) -> ChatCompletion:
    return ChatCompletion(
        id="mock-id",
        choices=[
            Choice(
                finish_reason="stop",
                index=0,
                message=ChatCompletionMessage(content=content, role="assistant"),
            )
        ],
        created=1234567890,
        model="mock-model",
        object="chat.completion",
    )


class TestLLMClient:
    @patch("shared.llm.client.OpenAI")
    def test_provider_abstraction_no_router(
        self, mock_openai: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Step 1.7.1: outside agents, direct provider connections are used."""
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://fake-ollama/v1")
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
        monkeypatch.setenv("OPENROUTER_BASE_URL", "https://fake-or/api/v1")

        client = LLMClient(use_router=False)
        assert client.use_router is False
        assert client.base_url == "http://fake-ollama/v1"
        assert client.backup_base_url == "https://fake-or/api/v1"
        assert mock_openai.call_count == 2

    @patch("shared.llm.client.OpenAI")
    def test_provider_abstraction_with_router(
        self, mock_openai: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Step 1.7.1: inside agents, Nasiko's LLM Router is used."""
        monkeypatch.setenv("LLM_ROUTER_URL", "http://fake-router/v1")

        client = LLMClient(use_router=True)
        assert client.use_router is True
        assert client.base_url == "http://fake-router/v1"
        assert client.backup_client is None
        assert mock_openai.call_count == 1

    @patch("shared.llm.client.OpenAI")
    def test_successful_primary_call(self, mock_openai: MagicMock) -> None:
        mock_instance = mock_openai.return_value
        mock_instance.chat.completions.create.return_value = _make_mock_response("Hello!")

        client = LLMClient(use_router=False)
        result = client.generate([{"role": "user", "content": "Hi"}])
        assert result == "Hello!"
        mock_instance.chat.completions.create.assert_called_once()

    @patch("shared.llm.client.OpenAI")
    def test_fallback_on_connection_error(
        self, mock_openai: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Step 1.7.3: Automatic fallback from primary to backup."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

        # Primary client fails, backup succeeds
        primary_mock = MagicMock()
        primary_mock.chat.completions.create.side_effect = APIConnectionError(request=MagicMock())

        backup_mock = MagicMock()
        backup_mock.chat.completions.create.return_value = _make_mock_response("Backup answer")

        mock_openai.side_effect = [primary_mock, backup_mock]

        # Use small tenacity wait for testing
        with patch("shared.llm.client.wait_exponential", return_value=MagicMock(return_value=0)):
            client = LLMClient(use_router=False)
            result = client.generate([{"role": "user", "content": "Hi"}])

        assert result == "Backup answer"
        assert primary_mock.chat.completions.create.call_count == 3  # retried 3 times
        backup_mock.chat.completions.create.assert_called_once()


class DummyOutput(BaseModel):
    name: str
    age: int


class TestStrictJson:
    def test_successful_parsing(self) -> None:
        client = MagicMock(spec=LLMClient)
        client.generate.return_value = '{"name": "Alice", "age": 30}'

        result = generate_strict_json(client, DummyOutput, [{"role": "user", "content": "Hi"}])
        assert isinstance(result, DummyOutput)
        assert result.name == "Alice"
        assert result.age == 30

    def test_retry_on_invalid_json_format(self) -> None:
        """Step 1.7.2: Retries on validation error."""
        client = MagicMock(spec=LLMClient)
        # First call returns bad JSON (missing quote)
        # Second call returns good JSON
        client.generate.side_effect = ['{name: "Alice", "age": 30}', '{"name": "Alice", "age": 30}']

        result = generate_strict_json(
            client, DummyOutput, [{"role": "user", "content": "Hi"}], max_retries=1
        )
        assert client.generate.call_count == 2
        assert result.name == "Alice"

    def test_retry_on_pydantic_validation_error(self) -> None:
        client = MagicMock(spec=LLMClient)
        # First call returns valid JSON but wrong schema (age is string)
        # Second call returns valid schema
        client.generate.side_effect = [
            '{"name": "Alice", "age": "thirty"}',
            '{"name": "Alice", "age": 30}',
        ]

        result = generate_strict_json(
            client, DummyOutput, [{"role": "user", "content": "Hi"}], max_retries=1
        )
        assert client.generate.call_count == 2
        assert result.name == "Alice"

    def test_raises_error_after_max_retries(self) -> None:
        client = MagicMock(spec=LLMClient)
        client.generate.return_value = '{"name": "Alice"}'  # missing age

        with pytest.raises(LLMJsonParseError, match="Failed to generate valid JSON"):
            generate_strict_json(
                client, DummyOutput, [{"role": "user", "content": "Hi"}], max_retries=1
            )

        assert client.generate.call_count == 2
