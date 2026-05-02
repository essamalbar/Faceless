"""Whisper-based forced-alignment tests. Whisper itself is monkeypatched."""
from __future__ import annotations

from pathlib import Path

import pytest

from pipeline import align as align_mod
from pipeline.align import align_arabic
from pipeline.types import WordTiming


def test_align_returns_wordtimings_in_order(monkeypatch, tmp_path: Path):
    """The aligner returns one WordTiming per word, monotonic offsets."""
    audio = tmp_path / "n.mp3"
    audio.write_bytes(b"\xff\xfb\x90\x00")  # not real audio; whisper is mocked

    fake_result = {
        "language": "ar",
        "segments": [
            {
                "start": 0.00,
                "end": 1.50,
                "words": [
                    {"word": "كنتُ", "start": 0.00, "end": 0.50},
                    {"word": "وحيداً", "start": 0.55, "end": 1.05},
                    {"word": "هناك.", "start": 1.10, "end": 1.50},
                ],
            }
        ],
    }

    class FakeModel:
        def transcribe(self, audio_path, **kw):
            assert kw.get("language") == "ar"
            assert kw.get("word_timestamps") is True
            return fake_result

    monkeypatch.setattr(align_mod, "_load_whisper", lambda model_name: FakeModel())
    timings = align_arabic(audio, expected_text="كنتُ وحيداً هناك.")

    assert len(timings) == 3
    assert all(isinstance(t, WordTiming) for t in timings)
    assert timings[0].word == "كنتُ"
    assert timings[0].offset_ms == 0
    assert timings[0].duration_ms == 500
    assert timings[1].offset_ms == 550
    # Monotonic
    for i in range(1, len(timings)):
        assert timings[i].offset_ms >= timings[i - 1].offset_ms


def test_align_falls_back_when_whisper_returns_no_words(monkeypatch, tmp_path: Path):
    """If Whisper returns segments without word-level data, fall back to even-split."""
    audio = tmp_path / "n.mp3"
    audio.write_bytes(b"\xff\xfb\x90\x00")

    class FakeModel:
        def transcribe(self, audio_path, **kw):
            return {"language": "ar", "segments": []}

    monkeypatch.setattr(align_mod, "_load_whisper", lambda model_name: FakeModel())
    monkeypatch.setattr(align_mod, "_audio_duration_s", lambda p: 6.0)

    text = "كلمة1 كلمة2 كلمة3"
    timings = align_arabic(audio, expected_text=text)
    assert len(timings) == 3
    assert timings[0].offset_ms == 0
    # Approximately 2-second slices
    assert 1900 <= timings[0].duration_ms <= 2100
