"""ElevenLabs TTS client tests. Real HTTP is replaced via monkeypatch."""
from __future__ import annotations

from pathlib import Path

import pytest

from pipeline import elevenlabs as el_mod
from pipeline.elevenlabs import ElevenLabsClient, ElevenLabsError


def _client() -> ElevenLabsClient:
    return ElevenLabsClient(api_key="k")


def test_init_requires_api_key(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    with pytest.raises(ElevenLabsError):
        ElevenLabsClient()


def test_synthesize_writes_mp3(monkeypatch, tmp_path: Path):
    """submit + download path: returns the bytes written."""
    captured: dict = {}

    def fake_post(self, path, body):
        captured["path"] = path
        captured["body"] = body
        return b"\xff\xfb\x90\x00" + b"\x00" * 100  # valid mp3-ish prefix

    monkeypatch.setattr(ElevenLabsClient, "_post_audio", fake_post)
    out = tmp_path / "narration.mp3"
    _client().synthesize(
        text="مرحبا يا صديقي",
        voice_id="vid-123",
        model="eleven_multilingual_v2",
        out_path=out,
    )
    assert out.exists()
    assert out.stat().st_size > 0
    assert captured["path"] == "/v1/text-to-speech/vid-123"
    assert captured["body"]["text"] == "مرحبا يا صديقي"
    assert captured["body"]["model_id"] == "eleven_multilingual_v2"
    assert captured["body"]["voice_settings"]["stability"] == 0.5


def test_synthesize_retries_then_succeeds(monkeypatch, tmp_path: Path):
    calls = {"n": 0}

    def flaky(self, path, body):
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("transient")
        return b"\xff\xfb\x90\x00"

    monkeypatch.setattr(ElevenLabsClient, "_post_audio", flaky)
    monkeypatch.setattr(el_mod, "_SLEEP", lambda _s: None)
    _client().synthesize(text="hi", voice_id="v", model="m",
                          out_path=tmp_path / "n.mp3")
    assert calls["n"] == 3


def test_synthesize_raises_after_max_retries(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(ElevenLabsClient, "_post_audio",
                        lambda self, path, body: (_ for _ in ()).throw(RuntimeError("permanent")))
    monkeypatch.setattr(el_mod, "_SLEEP", lambda _s: None)
    with pytest.raises(ElevenLabsError, match="synthesize failed"):
        _client().synthesize(text="hi", voice_id="v", model="m",
                              out_path=tmp_path / "n.mp3")
