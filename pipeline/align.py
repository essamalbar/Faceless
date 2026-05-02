"""Whisper-based force-alignment of Arabic narration audio.

Given the generated narration mp3 and the original Arabic text, produce
ms-precise word timings by transcribing the audio with Whisper's word_timestamps
mode. Whisper local model `small` is the default — accurate enough for Arabic
TikTok captions and runs in ~30s on M3 Pro.

If Whisper returns no word-level data (rare, on very short or noisy audio),
fall back to evenly distributing the expected words across the audio duration.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from pipeline.types import WordTiming

_DEFAULT_MODEL = "small"


def _load_whisper(model_name: str):
    """Module-level indirection so tests can monkeypatch."""
    import whisper
    return whisper.load_model(model_name)


def _audio_duration_s(path: Path) -> float:
    out = subprocess.check_output([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "csv=p=0", str(path),
    ], text=True).strip()
    return float(out)


def align_arabic(
    audio_path: Path, expected_text: str, model: str = _DEFAULT_MODEL,
) -> list[WordTiming]:
    """Transcribe audio with Whisper word_timestamps and produce ms-precise word timings.

    `expected_text` is the original Arabic narration; we use Whisper's transcript
    primarily for the timing data and don't insist Whisper got the words right
    (Arabic transcription is imperfect at the `small` size).
    """
    m = _load_whisper(model)
    result = m.transcribe(
        str(audio_path),
        language="ar",
        word_timestamps=True,
        verbose=False,
    )

    timings: list[WordTiming] = []
    for seg in result.get("segments", []):
        for w in seg.get("words", []) or []:
            word = str(w.get("word", "")).strip()
            start = float(w.get("start", 0.0))
            end = float(w.get("end", start))
            if not word:
                continue
            offset_ms = int(start * 1000)
            duration_ms = max(int((end - start) * 1000), 1)
            timings.append(WordTiming(
                word=word, offset_ms=offset_ms, duration_ms=duration_ms,
            ))

    if timings:
        return timings

    # Fallback: even split across audio duration
    words = [w for w in expected_text.split() if w.strip()]
    if not words:
        return []
    total_ms = int(_audio_duration_s(audio_path) * 1000)
    per_word = max(total_ms // len(words), 1)
    return [
        WordTiming(word=w, offset_ms=i * per_word, duration_ms=per_word)
        for i, w in enumerate(words)
    ]
