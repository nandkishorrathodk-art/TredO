"""
TREDO — AI Data Models
Simple typed models for chat messages and responses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Message:
    """A single message in a chat conversation."""
    role: str       # "system", "user", "assistant"
    content: str

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass
class ChatResponse:
    """Response from an LLM."""
    content: str
    model: str
    finish_reason: str = "stop"
    usage: dict[str, int] = field(default_factory=lambda: {
        "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
    })
    latency_ms: float = 0.0

    @property
    def total_tokens(self) -> int:
        return self.usage.get("total_tokens", 0)
