"""
TREDO — AI Gateway
One simple gateway to talk to ANY LLM.
Just provide: base_url + api_key + model.

Works with:
- Ollama (http://localhost:11434/v1)
- OpenAI (https://api.openai.com/v1)
- Claude via OpenAI-compatible proxy
- Gemini via OpenAI-compatible proxy
- LMStudio, vLLM, Together, Groq, DeepSeek, Qwen — anything OpenAI-compatible

This module does NOT think, decide, trade, or store memory.
It ONLY sends prompts to LLMs and returns responses.

Usage:
    gateway = AIGateway(
        base_url="http://localhost:11434/v1",
        model="llama3.2",
    )
    response = await gateway.chat([
        Message("system", "You are a trading analyst."),
        Message("user", "Analyze BTC trend."),
    ])
    print(response.content)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from collections.abc import AsyncIterator

import httpx

from backend.ai.models import ChatResponse, Message

logger = logging.getLogger(__name__)


class AIGatewayError(Exception):
    """Raised when the AI gateway fails."""


class AIGateway:
    """
    Simple LLM gateway. Three config values: base_url, api_key, model.
    Talks OpenAI-compatible API format (works with everything).
    """

    def __init__(
        self,
        base_url: str = "",
        api_key: str = "",
        model: str = "",
    ) -> None:
        self._base_url = (
            base_url
            or os.getenv("TREDO_LLM_URL", "http://localhost:11434/v1")
        ).rstrip("/")
        self._api_key = api_key or os.getenv("TREDO_LLM_KEY", "")
        self._model = model or os.getenv("TREDO_LLM_MODEL", "llama3.2")
        self._timeout = 120
        self._max_retries = 3

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def model(self) -> str:
        return self._model

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    # ── Chat ─────────────────────────────────────────────────

    async def chat(
        self,
        messages: list[Message],
        model: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> ChatResponse:
        """
        Send a chat request and get a complete response.

        Args:
            messages: List of Message objects
            model: Override default model (optional)
            temperature: Creativity (0.0-2.0)
            max_tokens: Max response length
        """
        use_model = model or self._model
        payload = {
            "model": use_model,
            "messages": [m.to_dict() for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        start = time.time()
        data = await self._post("/chat/completions", payload)
        latency = (time.time() - start) * 1000

        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        usage = data.get("usage", {})

        return ChatResponse(
            content=message.get("content", ""),
            model=data.get("model", use_model),
            finish_reason=choice.get("finish_reason", "stop"),
            usage={
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            },
            latency_ms=latency,
        )

    async def chat_with_retry(
        self,
        messages: list[Message],
        model: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> ChatResponse:
        """Chat with automatic retry on failure."""
        last_error: Exception | None = None

        for attempt in range(1, self._max_retries + 1):
            try:
                return await self.chat(messages, model, temperature, max_tokens)
            except Exception as e:
                last_error = e
                if attempt < self._max_retries:
                    delay = attempt * 1.0
                    logger.warning(
                        "Chat attempt %d/%d failed: %s — retrying in %.1fs",
                        attempt, self._max_retries, e, delay,
                    )
                    await asyncio.sleep(delay)

        raise AIGatewayError(
            f"Chat failed after {self._max_retries} attempts: {last_error}"
        ) from last_error

    # ── Stream ───────────────────────────────────────────────

    async def stream(
        self,
        messages: list[Message],
        model: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        """
        Stream chat response token by token.

        Usage:
            async for token in gateway.stream(messages):
                print(token, end="", flush=True)
        """
        use_model = model or self._model
        payload = {
            "model": use_model,
            "messages": [m.to_dict() for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self._base_url}/chat/completions",
                    json=payload,
                    headers=self._headers(),
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        chunk = json.loads(data_str)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
        except httpx.ConnectError as e:
            raise AIGatewayError(
                f"Cannot connect to {self._base_url}. Is the LLM server running?"
            ) from e
        except httpx.TimeoutException as e:
            raise AIGatewayError(f"Stream timeout after {self._timeout}s") from e

    # ── Health & Info ────────────────────────────────────────

    async def health(self) -> dict[str, bool | str]:
        """Check if the LLM server is reachable."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{self._base_url}/models",
                    headers=self._headers(),
                )
                reachable = resp.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException):
            reachable = False

        return {
            "reachable": reachable,
            "base_url": self._base_url,
            "model": self._model,
        }

    async def list_models(self) -> list[str]:
        """List available models from the LLM server."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{self._base_url}/models",
                    headers=self._headers(),
                )
                resp.raise_for_status()
                data = resp.json()
        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError):
            return []

        return [m.get("id", "") for m in data.get("data", []) if m.get("id")]

    # ── Internal ─────────────────────────────────────────────

    async def _post(self, endpoint: str, payload: dict) -> dict:
        """POST to the LLM API and return parsed JSON."""
        url = f"{self._base_url}{endpoint}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    url, json=payload, headers=self._headers(),
                )
                resp.raise_for_status()
                return resp.json()
        except httpx.ConnectError as e:
            raise AIGatewayError(
                f"Cannot connect to {self._base_url}. Is the LLM server running?"
            ) from e
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            body = e.response.text
            if status == 401:
                raise AIGatewayError("Invalid API key") from e
            if status == 429:
                raise AIGatewayError("Rate limit exceeded") from e
            if status == 404:
                raise AIGatewayError(f"Model not found: {payload.get('model')}") from e
            raise AIGatewayError(f"HTTP {status}: {body}") from e
        except httpx.TimeoutException as e:
            raise AIGatewayError(f"Request timeout after {self._timeout}s") from e
