from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.llm_gemini_audio import GeminiAudioJudge, GeminiAudioError


def test_missing_key_raises(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(GeminiAudioError):
        GeminiAudioJudge()


def test_judge_audio_sends_audio_and_returns_text(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    mp3 = tmp_path / "take.mp3"
    mp3.write_bytes(b"ID3fakeaudio")

    captured = {}

    class _FakeModels:
        def generate_content(self, **kwargs):
            captured.update(kwargs)
            class R: text = '{"vocal_realism": 80}'
            return R()

    class _FakeClient:
        models = _FakeModels()

    monkeypatch.setattr("pipeline.llm_gemini_audio._client", lambda key: _FakeClient())
    j = GeminiAudioJudge(model="gemini-2.5-flash")
    out = j.judge_audio(mp3, system="be strict", user="style: pop")
    assert out == '{"vocal_realism": 80}'
    assert captured["model"] == "gemini-2.5-flash"
    # audio bytes must be in the request contents
    assert captured["contents"]  # non-empty parts list


def test_model_env_override(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    monkeypatch.setenv("GEMINI_AUDIO_MODEL", "gemini-custom-audio")
    monkeypatch.setattr("pipeline.llm_gemini_audio._client", lambda key: object())
    assert GeminiAudioJudge()._model == "gemini-custom-audio"


def test_empty_response_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    mp3 = tmp_path / "t.mp3"
    mp3.write_bytes(b"x")

    class _Models:
        def generate_content(self, **kwargs):
            class R:
                text = None
            return R()

    class _Client:
        models = _Models()

    monkeypatch.setattr("pipeline.llm_gemini_audio._client", lambda key: _Client())
    with pytest.raises(GeminiAudioError):
        GeminiAudioJudge().judge_audio(mp3, system="s", user="u")
