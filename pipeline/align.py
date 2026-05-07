"""Whisper-based force-alignment of Arabic narration audio.

We use Whisper purely as a stopwatch: it tells us WHEN each spoken word
starts and ends in the audio. We always RENDER the original Arabic
script text in the captions — Whisper's transcription itself is
discarded, because Arabic transcription at `small`/`medium` quality
hallucinates words that don't match the source script.

Procedure:
  1. Whisper transcribes audio → list of (transcribed_word, start, end).
  2. We zip those timings with the ORIGINAL script's word list by index.
     - If counts match exactly: 1:1 replacement.
     - If they differ (typical for Arabic): we anchor on Whisper's
       FIRST and LAST word boundaries and linearly distribute the
       original words across that range, so the sync stays usable.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from pipeline.types import WordTiming

# Default to `small` (483 MB, downloads reliably). `medium` (1.5 GB)
# transcribes Arabic better but its download repeatedly stalls partway
# on flaky VPNs, leaving a corrupt file that fails SHA256 forever after.
# We use Whisper as a stopwatch (timings only — original script text is
# rendered against those timings), so transcription accuracy matters
# less than the model loading reliably.
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


def _whisper_word_timings(audio_path: Path, model: str) -> list[tuple[float, float]]:
    """Run Whisper and return (start_s, end_s) tuples — words are dropped on purpose."""
    m = _load_whisper(model)
    result = m.transcribe(
        str(audio_path),
        language="ar",
        word_timestamps=True,
        verbose=False,
    )
    spans: list[tuple[float, float]] = []
    for seg in result.get("segments", []):
        for w in seg.get("words", []) or []:
            word = str(w.get("word", "")).strip()
            if not word:
                continue
            start = float(w.get("start", 0.0))
            end = float(w.get("end", start))
            spans.append((start, max(end, start)))
    return spans


def _spans_to_timings(words: list[str], spans: list[tuple[float, float]]) -> list[WordTiming]:
    """Place each `words[i]` onto the audio timeline implied by `spans`.

    Strategy:
    - If len(spans) == len(words): zip directly, each original word inherits
      its corresponding Whisper-detected timing. This is the happy path.
    - Otherwise: anchor on the first and last spans (most robust signals)
      and linearly interpolate across the original word indices. The total
      window stays right; per-word offsets are approximate but consistent.
    """
    if not words or not spans:
        return []
    if len(spans) == len(words):
        out: list[WordTiming] = []
        for w, (start, end) in zip(words, spans):
            offset_ms = int(start * 1000)
            duration_ms = max(int((end - start) * 1000), 1)
            out.append(WordTiming(word=w, offset_ms=offset_ms, duration_ms=duration_ms))
        return out

    first_start = spans[0][0]
    last_end = spans[-1][1]
    total_window = max(last_end - first_start, 0.001)
    per_word = total_window / len(words)
    out = []
    for i, w in enumerate(words):
        start = first_start + i * per_word
        offset_ms = int(start * 1000)
        duration_ms = max(int(per_word * 1000), 1)
        out.append(WordTiming(word=w, offset_ms=offset_ms, duration_ms=duration_ms))
    return out


def align_arabic(
    audio_path: Path, expected_text: str, model: str = _DEFAULT_MODEL,
) -> list[WordTiming]:
    """Force-align: Whisper's timings + ORIGINAL Arabic words from the script.

    `expected_text` is the source-of-truth narration text. Captions and
    karaoke MUST use these words verbatim — never Whisper's transcription.
    """
    words = [w for w in expected_text.split() if w.strip()]
    if not words:
        return []

    spans = _whisper_word_timings(audio_path, model)
    if spans:
        return _spans_to_timings(words, spans)

    # Last-resort fallback: no Whisper output at all (very short / silent audio).
    # Distribute words evenly across the full audio duration.
    total_ms = int(_audio_duration_s(audio_path) * 1000)
    per_word = max(total_ms // len(words), 1)
    return [
        WordTiming(word=w, offset_ms=i * per_word, duration_ms=per_word)
        for i, w in enumerate(words)
    ]
