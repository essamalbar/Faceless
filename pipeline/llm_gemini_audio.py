"""Gemini with AUDIO input — the A&R judge's ear. Separate from the text
GeminiClient in pipeline/llm.py (which is text-only)."""
from __future__ import annotations

import os
from pathlib import Path


class GeminiAudioError(RuntimeError):
    pass


def _client(api_key: str):
    """Constructed at runtime so tests can monkeypatch."""
    from google import genai
    return genai.Client(api_key=api_key)


class GeminiAudioJudge:
    """One method: judge_audio(audio_path, system, user) -> str (model text)."""

    tier = "gemini"

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self._model = model or os.environ.get("GEMINI_AUDIO_MODEL", "gemini-2.5-flash")
        key = api_key or os.environ.get("GEMINI_API_KEY")
        if not key:
            raise GeminiAudioError("GEMINI_API_KEY not set")
        self._client = _client(key)

    def judge_audio(self, audio_path, system: str, user: str) -> str:
        from google.genai import types
        data = Path(audio_path).read_bytes()
        contents = [
            types.Part.from_bytes(data=data, mime_type="audio/mpeg"),
            types.Part.from_text(text=user),
        ]
        resp = self._client.models.generate_content(
            model=self._model,
            contents=contents,
            config={"system_instruction": system},
        )
        # resp.text is None on a safety-blocked/empty response — surface it as a
        # clear error (callers catch it and fall back) rather than returning None
        # into a JSON parser several layers away.
        if resp.text is None:
            raise GeminiAudioError("empty response from Gemini audio judge")
        return resp.text
