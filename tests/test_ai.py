"""
TREDO — AI Gateway Tests
Tests chat, streaming, retry, timeout, errors, health check.
All HTTP calls are mocked — no real LLM server needed.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from backend.ai.gateway import AIGateway, AIGatewayError
from backend.ai.models import Message, ChatResponse


@pytest.fixture
def gateway() -> AIGateway:
    """Create a gateway with test config."""
    return AIGateway(
        base_url="http://localhost:11434/v1",
        api_key="test-key-123",
        model="llama3.2",
    )


def _mock_chat_response(content: str = "Hello!", model: str = "llama3.2") -> dict:
    """Create a mock OpenAI-compatible chat response."""
    return {
        "choices": [{
            "message": {"role": "assistant", "content": content},
            "finish_reason": "stop",
        }],
        "model": model,
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
        },
    }


def _mock_models_response() -> dict:
    return {
        "data": [
            {"id": "llama3.2"},
            {"id": "mistral"},
            {"id": "codellama"},
        ]
    }


# ══════════════════════════════════════════════════════════
# Initialization Tests
# ══════════════════════════════════════════════════════════


class TestInit:
    def test_default_config(self):
        gw = AIGateway()
        assert gw.base_url == "http://localhost:11434/v1"
        assert gw.model == "llama3.2"

    def test_custom_config(self, gateway: AIGateway):
        assert gateway.base_url == "http://localhost:11434/v1"
        assert gateway.model == "llama3.2"

    def test_env_config(self, monkeypatch):
        monkeypatch.setenv("TREDO_LLM_URL", "https://api.openai.com/v1")
        monkeypatch.setenv("TREDO_LLM_KEY", "sk-test")
        monkeypatch.setenv("TREDO_LLM_MODEL", "gpt-4o")
        gw = AIGateway()
        assert gw.base_url == "https://api.openai.com/v1"
        assert gw.model == "gpt-4o"

    def test_trailing_slash_stripped(self):
        gw = AIGateway(base_url="http://localhost:11434/v1/")
        assert gw.base_url == "http://localhost:11434/v1"

    def test_headers_with_key(self, gateway: AIGateway):
        headers = gateway._headers()
        assert headers["Authorization"] == "Bearer test-key-123"

    def test_headers_without_key(self):
        gw = AIGateway(base_url="http://localhost:11434/v1")
        headers = gw._headers()
        assert "Authorization" not in headers


# ══════════════════════════════════════════════════════════
# Chat Tests
# ══════════════════════════════════════════════════════════


class TestChat:
    @pytest.mark.asyncio
    async def test_chat_success(self, gateway: AIGateway):
        mock_resp = MagicMock()
        mock_resp.json.return_value = _mock_chat_response("BTC is bullish")
        mock_resp.raise_for_status = MagicMock()

        with patch("backend.ai.gateway.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            response = await gateway.chat([
                Message("user", "What is BTC trend?"),
            ])

            assert response.content == "BTC is bullish"
            assert response.model == "llama3.2"
            assert response.total_tokens == 15
            assert response.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_chat_with_system_message(self, gateway: AIGateway):
        mock_resp = MagicMock()
        mock_resp.json.return_value = _mock_chat_response("Analysis ready")
        mock_resp.raise_for_status = MagicMock()

        with patch("backend.ai.gateway.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            response = await gateway.chat([
                Message("system", "You are a trading AI."),
                Message("user", "Analyze market."),
            ])

            assert response.content == "Analysis ready"
            # Verify both messages were sent
            call_args = mock_client.post.call_args
            payload = call_args.kwargs.get("json") or call_args[1].get("json")
            assert len(payload["messages"]) == 2

    @pytest.mark.asyncio
    async def test_chat_custom_model(self, gateway: AIGateway):
        mock_resp = MagicMock()
        mock_resp.json.return_value = _mock_chat_response("OK", "gpt-4o")
        mock_resp.raise_for_status = MagicMock()

        with patch("backend.ai.gateway.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            response = await gateway.chat(
                [Message("user", "hi")], model="gpt-4o",
            )
            assert response.model == "gpt-4o"

    @pytest.mark.asyncio
    async def test_chat_custom_temperature(self, gateway: AIGateway):
        mock_resp = MagicMock()
        mock_resp.json.return_value = _mock_chat_response("Creative!")
        mock_resp.raise_for_status = MagicMock()

        with patch("backend.ai.gateway.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            await gateway.chat(
                [Message("user", "hi")], temperature=1.5,
            )
            call_args = mock_client.post.call_args
            payload = call_args.kwargs.get("json") or call_args[1].get("json")
            assert payload["temperature"] == 1.5


# ══════════════════════════════════════════════════════════
# Error Handling Tests
# ══════════════════════════════════════════════════════════


class TestErrors:
    @pytest.mark.asyncio
    async def test_connection_error(self, gateway: AIGateway):
        with patch("backend.ai.gateway.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with pytest.raises(AIGatewayError, match="Cannot connect"):
                await gateway.chat([Message("user", "hi")])

    @pytest.mark.asyncio
    async def test_timeout_error(self, gateway: AIGateway):
        with patch("backend.ai.gateway.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("slow"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with pytest.raises(AIGatewayError, match="timeout"):
                await gateway.chat([Message("user", "hi")])

    @pytest.mark.asyncio
    async def test_invalid_api_key(self, gateway: AIGateway):
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        with patch("backend.ai.gateway.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(
                side_effect=httpx.HTTPStatusError("401", request=MagicMock(), response=mock_response)
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with pytest.raises(AIGatewayError, match="Invalid API key"):
                await gateway.chat([Message("user", "hi")])

    @pytest.mark.asyncio
    async def test_rate_limit(self, gateway: AIGateway):
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = "Too many requests"

        with patch("backend.ai.gateway.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(
                side_effect=httpx.HTTPStatusError("429", request=MagicMock(), response=mock_response)
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with pytest.raises(AIGatewayError, match="Rate limit"):
                await gateway.chat([Message("user", "hi")])

    @pytest.mark.asyncio
    async def test_model_not_found(self, gateway: AIGateway):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Model not found"

        with patch("backend.ai.gateway.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(
                side_effect=httpx.HTTPStatusError("404", request=MagicMock(), response=mock_response)
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with pytest.raises(AIGatewayError, match="Model not found"):
                await gateway.chat([Message("user", "hi")])


# ══════════════════════════════════════════════════════════
# Retry Tests
# ══════════════════════════════════════════════════════════


class TestRetry:
    @pytest.mark.asyncio
    async def test_retry_succeeds_on_second_attempt(self, gateway: AIGateway):
        mock_resp_ok = MagicMock()
        mock_resp_ok.json.return_value = _mock_chat_response("Recovered!")
        mock_resp_ok.raise_for_status = MagicMock()

        gateway._max_retries = 3

        with patch("backend.ai.gateway.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(
                side_effect=[httpx.ConnectError("fail"), mock_resp_ok]
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            response = await gateway.chat_with_retry([Message("user", "hi")])
            assert response.content == "Recovered!"

    @pytest.mark.asyncio
    async def test_retry_exhausted(self, gateway: AIGateway):
        gateway._max_retries = 2

        with patch("backend.ai.gateway.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.ConnectError("fail"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with pytest.raises(AIGatewayError, match="failed after 2 attempts"):
                await gateway.chat_with_retry([Message("user", "hi")])


# ══════════════════════════════════════════════════════════
# Health Check Tests
# ══════════════════════════════════════════════════════════


class TestHealth:
    @pytest.mark.asyncio
    async def test_health_reachable(self, gateway: AIGateway):
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch("backend.ai.gateway.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            status = await gateway.health()
            assert status["reachable"] is True
            assert status["base_url"] == "http://localhost:11434/v1"
            assert status["model"] == "llama3.2"

    @pytest.mark.asyncio
    async def test_health_unreachable(self, gateway: AIGateway):
        with patch("backend.ai.gateway.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("offline"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            status = await gateway.health()
            assert status["reachable"] is False

    @pytest.mark.asyncio
    async def test_health_timeout(self, gateway: AIGateway):
        with patch("backend.ai.gateway.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("slow"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            status = await gateway.health()
            assert status["reachable"] is False


# ══════════════════════════════════════════════════════════
# List Models Tests
# ══════════════════════════════════════════════════════════


class TestListModels:
    @pytest.mark.asyncio
    async def test_list_models_success(self, gateway: AIGateway):
        mock_resp = MagicMock()
        mock_resp.json.return_value = _mock_models_response()
        mock_resp.raise_for_status = MagicMock()

        with patch("backend.ai.gateway.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            models = await gateway.list_models()
            assert len(models) == 3
            assert "llama3.2" in models
            assert "mistral" in models

    @pytest.mark.asyncio
    async def test_list_models_offline(self, gateway: AIGateway):
        with patch("backend.ai.gateway.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("offline"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            models = await gateway.list_models()
            assert models == []


# ══════════════════════════════════════════════════════════
# Model Tests
# ══════════════════════════════════════════════════════════


class TestModels:
    def test_message_to_dict(self):
        m = Message("user", "hello")
        assert m.to_dict() == {"role": "user", "content": "hello"}

    def test_message_system(self):
        m = Message("system", "You are helpful.")
        assert m.role == "system"

    def test_chat_response_tokens(self):
        r = ChatResponse(
            content="test", model="llama3.2",
            usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        )
        assert r.total_tokens == 15

    def test_chat_response_defaults(self):
        r = ChatResponse(content="test", model="llama3.2")
        assert r.finish_reason == "stop"
        assert r.latency_ms == 0.0
        assert r.total_tokens == 0
