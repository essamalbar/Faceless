"""Groq LLM client — OpenAI-compatible Chat Completions API.

Free tier: ~30 RPM, no daily request cap (token-based limits only).
Best Arabic-capable model on Groq: llama-3.3-70b-versatile.

Same `complete()` interface as GeminiClient so pipeline stages can call
either interchangeably. `embed()` is NOT supported (Groq is inference-only)
— raises NotImplementedError; the Shorts path never calls it.
"""
from __future__ import annotations

import os
import time

import requests

_SLEEP = time.sleep
_MAX_RETRIES = 3
_BACKOFF_S = (1, 5, 30)

GROQ_BASE_URL = os.environ.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1")


class GroqError(RuntimeError):
    pass


class GroqClient:
    """OpenAI-compatible Chat Completions wrapper for Groq."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "llama-3.3-70b-versatile",
        base_url: str = GROQ_BASE_URL,
    ):
        key = api_key or os.environ.get("GROQ_API_KEY")
        if not key:
            raise GroqError("GROQ_API_KEY not set")
        self._key = key
        self._model = model
        self._base = base_url.rstrip("/")

    def complete(self, prompt: str, system: str | None = None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        body = {
            "model": self._model,
            "messages": messages,
            "temperature": 0.8,  # Stories benefit from some creativity
        }

        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                resp = self._post("/chat/completions", body)
                return resp["choices"][0]["message"]["content"]
            except Exception as e:
                last_exc = e
                if attempt < _MAX_RETRIES - 1:
                    _SLEEP(_BACKOFF_S[attempt])
        raise GroqError(f"complete failed after {_MAX_RETRIES} attempts: {last_exc}")

    def embed(self, text: str) -> list[float]:
        raise NotImplementedError(
            "Groq does not offer embeddings. Use Gemini or local sentence-transformers."
        )

    def _post(self, path: str, body: dict) -> dict:
        url = f"{self._base}{path}"
        resp = requests.post(
            url, json=body,
            headers={"Authorization": f"Bearer {self._key}",
                     "Content-Type": "application/json"},
            timeout=60,
        )
        if resp.status_code >= 400:
            raise GroqError(f"POST {path} → {resp.status_code}: {resp.text[:500]}")
        return resp.json()
