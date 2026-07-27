"""Anthropic Claude LLM client — Messages API.

Used by the Shorts script writer for noticeably better Arabic narrative
output than Groq Llama 3.3 (no Latin/Chinese character contamination,
proper first-person perspective management, real dialect compliance).

Same `complete()` interface as GroqClient / GeminiClient so the pipeline
stages can call any of them interchangeably. `embed()` is NOT supported
on Anthropic — raises NotImplementedError; the Shorts path never calls it.

Pricing reference (May 2026):
  - claude-sonnet-4-6: $3 / $15 per Mtok in/out — ~$0.02 per shorts script
  - claude-opus-4-7:   $15 / $75 per Mtok in/out — ~$0.10 per shorts script
"""
from __future__ import annotations

import os
import time

import requests

_SLEEP = time.sleep
_MAX_RETRIES = 3
_BACKOFF_S = (1, 5, 30)

ANTHROPIC_BASE_URL = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
ANTHROPIC_API_VERSION = os.environ.get("ANTHROPIC_API_VERSION", "2023-06-01")


class AnthropicError(RuntimeError):
    pass


class AnthropicClient:
    """Messages API wrapper. Default model is Sonnet 4.6 — best price/quality
    for the Shorts script generator."""

    tier = "anthropic"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-sonnet-4-6",
        base_url: str = ANTHROPIC_BASE_URL,
        max_tokens: int = 4096,
    ):
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise AnthropicError("ANTHROPIC_API_KEY not set")
        self._key = key
        self._model = model
        self._base = base_url.rstrip("/")
        self._max_tokens = max_tokens

    def complete(self, prompt: str, system: str | None = None) -> str:
        body: dict = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "temperature": 0.8,  # narrative tasks benefit from some creativity
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            body["system"] = system

        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                resp = self._post("/v1/messages", body)
                # Response shape: {content: [{type: "text", text: "..."}], ...}
                blocks = resp.get("content") or []
                texts = [b.get("text", "") for b in blocks if b.get("type") == "text"]
                if not texts:
                    raise AnthropicError(f"no text content in response: {resp}")
                return "".join(texts)
            except Exception as e:
                last_exc = e
                if attempt < _MAX_RETRIES - 1:
                    _SLEEP(_BACKOFF_S[attempt])
        raise AnthropicError(f"complete failed after {_MAX_RETRIES} attempts: {last_exc}")

    def embed(self, text: str) -> list[float]:
        raise NotImplementedError(
            "Anthropic does not offer embeddings. Use Gemini or local sentence-transformers."
        )

    def _post(self, path: str, body: dict) -> dict:
        url = f"{self._base}{path}"
        resp = requests.post(
            url, json=body,
            headers={
                "x-api-key": self._key,
                "anthropic-version": ANTHROPIC_API_VERSION,
                "content-type": "application/json",
            },
            timeout=120,
        )
        if resp.status_code >= 400:
            raise AnthropicError(f"POST {path} → {resp.status_code}: {resp.text[:500]}")
        return resp.json()
