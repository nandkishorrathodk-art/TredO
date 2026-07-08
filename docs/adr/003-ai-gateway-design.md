# ADR 003: AI Gateway Design

## Problem
The LLM landscape is highly fragmented and rapidly evolving (OpenAI, Claude, Gemini, DeepSeek, local Ollama). Integrating provider-specific SDKs leads to vendor lock-in, heavy dependency trees, and brittle code whenever an API changes.

## Decision
We built a unified, minimal `AIGateway` that leverages the fact that almost all modern LLM providers (or their proxies like vLLM, LMStudio, Together, Groq) support an OpenAI-compatible REST API. 

## Alternatives Considered
- **Provider-specific SDKs (openai, anthropic, google-generativeai):** High maintenance burden, conflicting dependency versions.
- **LangChain / LlamaIndex:** Far too heavy, adds abstraction layers that make debugging difficult and dictate architectural choices.
- **Multi-Provider Factory Pattern:** We initially tried building separate classes (`OpenAIProvider`, `ClaudeProvider`, etc.), but realized it was unnecessary overhead since they all accept similar payloads.

## Why this approach
- **Simplicity:** A single file with `base_url`, `api_key`, and `model` is all that's needed to talk to any LLM.
- **Dependency Light:** Uses only `httpx`. No heavy AI frameworks.
- **Future-Proof:** Can easily switch from a cloud provider (OpenAI) to a local provider (Ollama) by just changing the URL.

## Consequences
- **Pros:** Extremely low maintenance; zero vendor lock-in; easy to mock in tests.
- **Cons:** Advanced, provider-specific features (like Anthropic's specific caching headers) are not supported out-of-the-box, requiring manual payload adjustments if ever needed.
