"""Gemini API wrapper. Two operations: complete + embed. Retry with backoff.

Also hosts FallbackLLM, a tiny wrapper that routes to a secondary provider
when the primary's complete() raises (e.g. Anthropic out of credits / outage)
so lyrics/script generation degrades instead of hard-failing.
"""
from __future__ import annotations

import os
import time


class FallbackLLM:
    """Wrap a primary + fallback LLM (each exposing complete(prompt, system)).

    If the primary's complete() raises after its own retries (Anthropic out
    of credits, 5xx outage, etc.), log and retry on the fallback. This keeps
    song/script generation available when the preferred provider is down.
    NOTE: the fallback (Groq) writes lower-quality Arabic than Anthropic — it
    is a safety net, not a quality equal. Keep the primary's balance funded.
    """

    def __init__(self, primary, fallback, on_fallback=None):
        self._primary = primary
        self._fallback = fallback
        # Optional observer fired when the primary fails (before the fallback
        # call). Lets the API persist a "quality degraded" marker so the UI
        # can warn instead of silently shipping weaker lyrics. Observer errors
        # are swallowed — telemetry must never break generation.
        self._on_fallback = on_fallback
        # Tier of the provider that actually served the most recent complete().
        # Read via resolve_tier(). A fresh FallbackLLM is built per generation
        # request (see api._build_llm), so this instance attribute is not shared.
        self.last_tier = None

    def complete(self, prompt: str, system: str | None = None) -> str:
        try:
            out = self._primary.complete(prompt, system=system)
            # Unwrap a nested FallbackLLM (symmetric with the fallback path)
            # so a chain nested on the primary side still reports the leaf.
            self.last_tier = (getattr(self._primary, "last_tier", None)
                              or getattr(self._primary, "tier", "unknown"))
            return out
        except Exception as e:
            print(f"[llm] primary provider failed ({e}); "
                  f"falling back to secondary provider")
            if self._on_fallback is not None:
                try:
                    self._on_fallback(e)
                except Exception:
                    pass
            out = self._fallback.complete(prompt, system=system)
            # Unwrap a nested FallbackLLM so we report the LEAF tier that served.
            self.last_tier = (getattr(self._fallback, "last_tier", None)
                              or getattr(self._fallback, "tier", "unknown"))
            return out

    def embed(self, text: str) -> list[float]:
        # Embeddings only have one real provider (Gemini); never fall back.
        return self._primary.embed(text)

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

    tier = "gemini"

    def __init__(self, api_key: str | None = None, model: str | None = None):
        model = model or os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
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
                    model="gemini-embedding-001",
                    contents=text,
                )
                return list(resp.embeddings[0].values)
            except Exception as e:
                last_exc = e
                if attempt < _MAX_RETRIES - 1:
                    _SLEEP(_BACKOFF_S[attempt])
        raise GeminiError(f"embed failed after {_MAX_RETRIES} attempts: {last_exc}")


def resolve_tier(llm) -> str:
    """Which provider actually served the last complete(): a FallbackLLM's
    last_tier, else a bare client's tier, else 'unknown'.

    Only str values count — a test double (e.g. MagicMock) auto-creates any
    attribute, so guarding on isinstance(str) keeps those out of run state and
    off the JSON write path (a MagicMock would raise in json.dumps)."""
    for attr in ("last_tier", "tier"):
        val = getattr(llm, attr, None)
        if isinstance(val, str) and val:
            return val
    return "unknown"
