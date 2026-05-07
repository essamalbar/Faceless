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


def test_align_replaces_whisper_words_with_original_text(monkeypatch, tmp_path: Path):
    """Whisper's transcription is unreliable for Arabic — we keep its TIMINGS
    but render the ORIGINAL script words. Captions must never display
    Whisper's hallucinated words."""
    audio = tmp_path / "n.mp3"
    audio.write_bytes(b"\xff\xfb\x90\x00")

    # Whisper transcribed garbage (this happens with Arabic on small/medium):
    fake_result = {
        "segments": [{
            "start": 0.0, "end": 1.5,
            "words": [
                {"word": "الفئرة", "start": 0.0, "end": 0.4},   # WRONG
                {"word": "الأديم", "start": 0.5, "end": 1.0},   # WRONG
                {"word": "بياكو.",  "start": 1.1, "end": 1.5},   # WRONG
            ],
        }],
    }

    class FakeModel:
        def transcribe(self, audio_path, **kw):
            return fake_result

    monkeypatch.setattr(align_mod, "_load_whisper", lambda model_name: FakeModel())

    # ORIGINAL script text — what the captions MUST display:
    original = "الفقيرة الأم بياكل."
    timings = align_arabic(audio, expected_text=original)

    assert [t.word for t in timings] == ["الفقيرة", "الأم", "بياكل."]
    # Whisper's timings are preserved
    assert timings[0].offset_ms == 0
    assert timings[1].offset_ms == 500
    assert timings[2].offset_ms == 1100


def test_align_interpolates_when_word_counts_mismatch(monkeypatch, tmp_path: Path):
    """When Whisper transcribes a different word count than the script
    (common with Arabic), we anchor on the first/last Whisper boundaries
    and linearly distribute the original words across that window."""
    audio = tmp_path / "n.mp3"
    audio.write_bytes(b"\xff\xfb\x90\x00")

    # Whisper produced 5 words; original script has 3.
    fake_result = {
        "segments": [{
            "start": 1.0, "end": 5.0,
            "words": [
                {"word": "a", "start": 1.0, "end": 1.4},
                {"word": "b", "start": 1.5, "end": 2.5},
                {"word": "c", "start": 2.6, "end": 3.0},
                {"word": "d", "start": 3.1, "end": 4.0},
                {"word": "e", "start": 4.1, "end": 5.0},
            ],
        }],
    }

    class FakeModel:
        def transcribe(self, audio_path, **kw):
            return fake_result

    monkeypatch.setattr(align_mod, "_load_whisper", lambda model_name: FakeModel())

    timings = align_arabic(audio, expected_text="واحد اثنان ثلاثة")

    assert [t.word for t in timings] == ["واحد", "اثنان", "ثلاثة"]
    # Anchored on first start (1.0s) and last end (5.0s) → 4s window / 3 words
    assert timings[0].offset_ms == 1000
    # Each word ~1333ms
    assert 1300 <= timings[0].duration_ms <= 1400
    # Last word starts roughly two-thirds in
    assert 3500 <= timings[2].offset_ms <= 3700


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
