"""Gemini API wrapper. Two operations: complete + embed. Retry with backoff."""
from __future__ import annotations

import os
import time

_SLEEP = time.sleep
_MAX_RETRIES = 3
_BACKOFF_S = (1, 5, 30)


class GeminiError(RuntimeError):
    pass


def _make_client(api_key: str):
    """Constructed at runtime so tests can monkeypatch."""
    from google import genai
    return genai.Client(api_key=api_key)


class GeminiClient:
    """Thin wrapper around google-genai with retries.

    Two methods:
      complete(prompt, system=None) -> str
      embed(text) -> list[float]
    """

    def __init__(self, api_key: str | None = None, model: str = "gemini-2.5-flash"):
        key = api_key or os.environ.get("GEMINI_API_KEY")
        if not key:
            raise GeminiError("GEMINI_API_KEY not set")
        self._client = _make_client(key)
        self._model = model

    def complete(self, prompt: str, system: str | None = None) -> str:
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                kwargs = {"model": self._model, "contents": prompt}
                if system:
                    kwargs["config"] = {"system_instruction": system}
                resp = self._client.models.generate_content(**kwargs)
                return resp.text
            except Exception as e:
                last_exc = e
                if attempt < _MAX_RETRIES - 1:
                    _SLEEP(_BACKOFF_S[attempt])
        raise GeminiError(f"complete failed after {_MAX_RETRIES} attempts: {last_exc}")

    def embed(self, text: str) -> list[float]:
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                resp = self._client.models.embed_content(
                    model="text-embedding-004",
                    contents=text,
                )
                return list(resp.embeddings[0].values)
            except Exception as e:
                last_exc = e
                if attempt < _MAX_RETRIES - 1:
                    _SLEEP(_BACKOFF_S[attempt])
        raise GeminiError(f"embed failed after {_MAX_RETRIES} attempts: {last_exc}")
