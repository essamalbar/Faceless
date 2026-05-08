"""ElevenLabs TTS client.

Uses the `xi-api-key` header (NOT Bearer). POST returns raw mp3 bytes
streamed from the API; we write to disk.

Same retry-with-backoff pattern as pipeline/kie.py and pipeline/llm_groq.py.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import requests

_SLEEP = time.sleep
_MAX_RETRIES = 3
_BACKOFF_S = (1, 5, 30)

BASE_URL = os.environ.get("ELEVENLABS_BASE_URL", "https://api.elevenlabs.io")


class ElevenLabsError(RuntimeError):
    pass


class ElevenLabsClient:
    """Minimal sync client for ElevenLabs TTS."""

    def __init__(self, api_key: str | None = None, base_url: str = BASE_URL):
        key = api_key or os.environ.get("ELEVENLABS_API_KEY")
        if not key:
            raise ElevenLabsError("ELEVENLABS_API_KEY not set")
        self._key = key
        self._base = base_url.rstrip("/")

    def synthesize(
        self, text: str, voice_id: str, model: str, out_path: Path,
        stability: float = 0.5, similarity_boost: float = 0.75,
    ) -> None:
        """POST /v1/text-to-speech/{voice_id} → write mp3 to out_path. Retries."""
        body = {
            "text": text,
            "model_id": model,
            "voice_settings": {
                "stability": stability,
                "similarity_boost": similarity_boost,
            },
        }
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                audio = self._post_audio(f"/v1/text-to-speech/{voice_id}", body)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(audio)
                return
            except Exception as e:
                last_exc = e
                if attempt < _MAX_RETRIES - 1:
                    _SLEEP(_BACKOFF_S[attempt])
        raise ElevenLabsError(f"synthesize failed after {_MAX_RETRIES} attempts: {last_exc}")

    def _post_audio(self, path: str, body: dict) -> bytes:
        url = f"{self._base}{path}"
        resp = requests.post(
            url, json=body,
            headers={"xi-api-key": self._key, "Content-Type": "application/json",
                     "Accept": "audio/mpeg"},
            timeout=120,
        )
        if resp.status_code >= 400:
            raise ElevenLabsError(f"POST {path} → {resp.status_code}: {resp.text[:500]}")
        return resp.content
