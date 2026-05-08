"""Stage 3: Edge TTS narration + word-level timings."""
from __future__ import annotations

import asyncio
import json
import re
import time
from pathlib import Path


def inject_ssml_pauses(text: str) -> str:
    """Convert plain Arabic text to text with SSML <break/> tags.

    Pauses are kept very light to avoid choppy narration. TTS provides natural
    sub-pauses on punctuation already; we only add explicit breaks for paragraph
    transitions and ellipses (where the writer is signalling a longer beat).
    Periods are NOT padded — TTS handles them naturally.

    - Paragraph break (\\n\\n) → 600ms (atmospheric beat between sections)
    - Ellipsis / em-dash      → 400ms (intentional dramatic pause)
    - Period                  → no break (was 600ms — caused listener fatigue)
    """
    text = text.replace("\n\n", '<break time="600ms"/>')
    text = re.sub(r"\.\.\.|…|—", '<break time="400ms"/>', text)
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


def _ffmpeg_concat_mp3s(part_paths: list[Path], out_path: Path) -> None:
    """Concat per-beat mp3s into a single narration mp3. Replaceable in tests."""
    import subprocess
    # ffmpeg's concat demuxer needs a list file with `file 'PATH'` lines.
    list_file = out_path.with_suffix(".concat.txt")
    list_file.write_text(
        "\n".join(f"file '{p}'" for p in part_paths) + "\n",
        encoding="utf-8",
    )
    try:
        subprocess.run([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "concat", "-safe", "0",
            "-i", str(list_file),
            "-c:a", "libmp3lame", "-q:a", "4",
            str(out_path),
        ], check=True)
    finally:
        list_file.unlink(missing_ok=True)


def generate_narration(
    text: str,
    voice: str,
    rate: str,
    pitch: str,
    mp3_path: Path,
    timings_path: Path,
) -> None:
    """Resumable: if both outputs present and timings non-empty, skip.

    Uses Edge TTS (free). Writes a synthesized timings file (duration / word
    count). The Whisper align stage in run.py refines these into accurate
    per-word timings before captions are rendered.
    """
    # Resume guard
    if mp3_path.exists() and timings_path.exists():
        try:
            if json.loads(timings_path.read_text(encoding="utf-8")):
                return
        except json.JSONDecodeError:
            pass

    # 1. Produce mp3 via Edge TTS.
    if not mp3_path.exists():
        ssml_text = inject_ssml_pauses(text)
        _synthesize(ssml_text, voice, rate, pitch, mp3_path)

    # 2. Write a placeholder timings file. The align stage will overwrite
    #    this with Whisper-derived ms-precise timings before captions render.
    duration_ms = _audio_duration_ms(mp3_path)
    timings = _synthesize_timings_from_duration(text, duration_ms)
    timings_path.write_text(
        json.dumps(timings, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
