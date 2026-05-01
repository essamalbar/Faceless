"""Stage 3: Edge TTS narration + word-level timings."""
from __future__ import annotations

import asyncio
import json
import re
import time
from pathlib import Path


def inject_ssml_pauses(text: str) -> str:
    """Convert plain Arabic text to text with SSML <break/> tags.

    - Paragraph break (\\n\\n)  → 1500ms
    - Ellipsis or em-dash    → 1200ms
    - Period                 → 600ms
    """
    # Order matters: handle long-form punctuation first.
    text = text.replace("\n\n", '<break time="1500ms"/>')
    text = re.sub(r"\.\.\.|…|—", '<break time="1200ms"/>', text)
    text = re.sub(r"\.(?!\d)", '<break time="600ms"/>', text)  # avoid breaking decimals
    return text


async def _edge_tts_run(text: str, voice: str, rate: str, pitch: str, mp3_path: Path) -> list[dict]:
    """Run edge-tts in async context. Returns word-timing dicts (may be empty for some languages)."""
    import edge_tts

    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate, pitch=pitch)
    timings: list[dict] = []
    with mp3_path.open("wb") as f:
        async for chunk in communicate.stream():
            t = chunk["type"]
            if t == "audio":
                f.write(chunk["data"])
            elif t == "WordBoundary":
                # offset and duration are in 100-nanosecond units (HNS)
                offset_ms = chunk["offset"] // 10_000
                duration_ms = chunk["duration"] // 10_000
                timings.append({
                    "word": chunk["text"],
                    "offset_ms": int(offset_ms),
                    "duration_ms": int(duration_ms),
                })
    return timings


_SLEEP = time.sleep
_MAX_RETRIES = 3
_BACKOFF_S = (1, 5, 30)


def _synthesize(text: str, voice: str, rate: str, pitch: str, mp3_path: Path) -> list[dict]:
    """Sync wrapper around the async edge-tts call with retry. Replaceable in tests."""
    mp3_path.parent.mkdir(parents=True, exist_ok=True)
    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            return asyncio.run(_edge_tts_run(text, voice, rate, pitch, mp3_path))
        except Exception as e:
            last_exc = e
            if attempt < _MAX_RETRIES - 1:
                _SLEEP(_BACKOFF_S[attempt])
    raise RuntimeError(f"edge-tts failed after {_MAX_RETRIES} attempts: {last_exc}")


def _audio_duration_ms(mp3_path: Path) -> int:
    """Return audio duration in milliseconds via ffprobe."""
    import subprocess
    out = subprocess.check_output([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "csv=p=0",
        str(mp3_path),
    ], text=True).strip()
    return int(float(out) * 1000)


def _strip_ssml(text: str) -> str:
    """Remove SSML break tags so word splitting works on plain text."""
    return re.sub(r"<break[^/]*/>", " ", text)


def _synthesize_timings_from_duration(text: str, total_duration_ms: int) -> list[dict]:
    """Build approximate word timings by evenly distributing audio duration across words.

    Used when the TTS service doesn't emit WordBoundary events (e.g. Arabic on edge-tts).
    The result is good enough for shot chunking (which works at ~15-20s granularity)
    and acceptable for captions (lines re-grouped from these timings stay roughly synced).
    """
    plain = _strip_ssml(text)
    words = [w for w in plain.split() if w.strip()]
    if not words:
        return []
    per_word_ms = total_duration_ms // len(words)
    timings: list[dict] = []
    offset = 0
    for word in words:
        timings.append({
            "word": word,
            "offset_ms": offset,
            "duration_ms": per_word_ms,
        })
        offset += per_word_ms
    return timings


def generate_narration(
    text: str,
    voice: str,
    rate: str,
    pitch: str,
    mp3_path: Path,
    timings_path: Path,
) -> None:
    """Resumable: if both outputs already exist AND timings is non-empty, skip.

    If TTS produced audio but no WordBoundary events (Arabic / some other voices),
    synthesize word timings from total audio duration so downstream stages have
    something to chunk on.

    On re-run, if the mp3 already exists but timings.json is empty/missing, we
    skip the expensive TTS call and just re-derive timings from audio duration.
    """
    # Skip entirely if both artifacts are present and non-empty.
    if mp3_path.exists() and timings_path.exists():
        try:
            if json.loads(timings_path.read_text(encoding="utf-8")):
                return
        except json.JSONDecodeError:
            pass

    ssml_text = inject_ssml_pauses(text)

    # Only call TTS if mp3 is missing. If mp3 exists, we just need timings.
    if not mp3_path.exists():
        timings = _synthesize(ssml_text, voice, rate, pitch, mp3_path)
    else:
        timings = []  # force fallback to duration-based synthesis

    if not timings:
        # Pass the ORIGINAL text (not ssml_text) so sentence-ending punctuation
        # is preserved on words — the downstream shot chunker snaps to those.
        duration_ms = _audio_duration_ms(mp3_path)
        timings = _synthesize_timings_from_duration(text, duration_ms)
    timings_path.write_text(
        json.dumps(timings, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
