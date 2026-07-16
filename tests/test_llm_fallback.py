from __future__ import annotations

import pytest

from pipeline.llm import FallbackLLM


class _Ok:
    def complete(self, prompt, system=None):
        return "primary-out"


class _Boom:
    def complete(self, prompt, system=None):
        raise RuntimeError("credit balance too low")


class _Fallback:
    def complete(self, prompt, system=None):
        return "fallback-out"


def test_on_fallback_fires_only_on_primary_failure():
    seen = []
    llm = FallbackLLM(_Boom(), _Fallback(), on_fallback=seen.append)
    assert llm.complete("p") == "fallback-out"
    assert len(seen) == 1 and "credit" in str(seen[0])

    seen.clear()
    llm2 = FallbackLLM(_Ok(), _Fallback(), on_fallback=seen.append)
    assert llm2.complete("p") == "primary-out"
    assert seen == []


def test_on_fallback_errors_are_swallowed():
    def bad_observer(e):
        raise ValueError("observer crashed")
    llm = FallbackLLM(_Boom(), _Fallback(), on_fallback=bad_observer)
    assert llm.complete("p") == "fallback-out"  # generation unharmed


def test_whisper_cover_model_falls_back_to_base(monkeypatch, tmp_path):
    import pipeline.song_import as si
    calls = []

    class _Model:
        def transcribe(self, path, language=None):
            return {"text": "words"}

    def fake_load(name):
        calls.append(name)
        if name == "small":
            raise MemoryError("OOM")
        return _Model()

    monkeypatch.setenv("WHISPER_COVER_MODEL", "small")
    monkeypatch.setattr("pipeline.align._load_whisper", fake_load)
    audio = tmp_path / "a.mp3"; audio.write_bytes(b"\x00")
    assert si._transcribe(audio, "ar") == "words"
    assert calls == ["small", "base"]  # tried preferred, fell back


def test_whisper_base_failure_propagates(monkeypatch, tmp_path):
    import pipeline.song_import as si
    monkeypatch.setenv("WHISPER_COVER_MODEL", "base")
    monkeypatch.setattr("pipeline.align._load_whisper",
                        lambda n: (_ for _ in ()).throw(RuntimeError("no model")))
    audio = tmp_path / "a.mp3"; audio.write_bytes(b"\x00")
    with pytest.raises(RuntimeError):
        si._transcribe(audio, "ar")
