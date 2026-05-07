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


def _build_elevenlabs():
    """Indirection so tests can monkeypatch."""
    from pipeline.elevenlabs import ElevenLabsClient
    return ElevenLabsClient()


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


def _audio_duration_ms_safe(path: Path) -> int:
    """ffprobe wrapper that returns 0 on failure (test fixtures may be tiny)."""
    try:
        return _audio_duration_ms(path)
    except Exception:
        return 0


def generate_narration_per_beat(
    beats,  # list[Beat] (avoid circular import at module-load time)
    character_voices: dict,
    parts_dir: Path,
    combined_mp3_path: Path,
    timings_path: Path,
    *,
    elevenlabs_model: str = "eleven_multilingual_v2",
    fallback_voice_id: str = "",
) -> None:
    """Synthesize one mp3 per beat with the speaker's voice, then concat.

    Output:
      - parts_dir/01.mp3, 02.mp3, …  : per-beat audio
      - combined_mp3_path             : full narration (concat of parts)
      - timings_path                  : word_timings.json built from
        per-beat durations, with each beat's words evenly distributed
        across that beat's measured audio length. No Whisper needed —
        the per-beat boundaries are exact, so caption sync is precise
        without depending on transcription accuracy.
    """
    if not beats:
        raise ValueError("no beats")
    parts_dir.mkdir(parents=True, exist_ok=True)
    combined_mp3_path.parent.mkdir(parents=True, exist_ok=True)

    client = _build_elevenlabs()
    part_paths: list[Path] = []
    for i, beat in enumerate(beats, start=1):
        part = parts_dir / f"{i:02d}.mp3"
        if not part.exists():
            voice_id = character_voices.get(beat.speaker) or fallback_voice_id
            if not voice_id:
                raise RuntimeError(
                    f"no voice id for speaker={beat.speaker!r} and no fallback"
                )
            client.synthesize(
                text=beat.arabic,
                voice_id=voice_id,
                model=elevenlabs_model,
                out_path=part,
            )
        part_paths.append(part)

    if not combined_mp3_path.exists():
        _ffmpeg_concat_mp3s(part_paths, combined_mp3_path)

    # Build deterministic word timings from per-beat audio durations.
    timings: list[dict] = []
    cursor_ms = 0
    for part, beat in zip(part_paths, beats):
        beat_ms = _audio_duration_ms_safe(part)
        words = [w for w in beat.arabic.split() if w.strip()]
        if not words:
            cursor_ms += beat_ms
            continue
        per_word = max(beat_ms // len(words), 1) if beat_ms > 0 else 1
        for j, w in enumerate(words):
            timings.append({
                "word": w,
                "offset_ms": cursor_ms + j * per_word,
                "duration_ms": per_word,
            })
        cursor_ms += beat_ms

    timings_path.write_text(
        json.dumps(timings, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def generate_narration(
    text: str,
    voice: str,
    rate: str,
    pitch: str,
    mp3_path: Path,
    timings_path: Path,
    *,
    provider: str = "edge_tts",
    elevenlabs_voice_id: str = "",
    elevenlabs_model: str = "eleven_multilingual_v2",
    fallback_to_edge_tts: bool = True,
) -> None:
    """Resumable: if both outputs present and timings non-empty, skip.

    provider:
      - "edge_tts"    — original Edge TTS path (free, lower quality)
      - "elevenlabs"  — ElevenLabs Multilingual v2 (paid, natural voice)

    Whichever provider is used, we always write a synthesized timings file
    (duration / word count). The Whisper align stage in run.py refines these
    into accurate per-word timings before captions are rendered.
    """
    # Resume guard
    if mp3_path.exists() and timings_path.exists():
        try:
            if json.loads(timings_path.read_text(encoding="utf-8")):
                return
        except json.JSONDecodeError:
            pass

    # 1. Produce mp3
    if not mp3_path.exists():
        if provider == "elevenlabs":
            try:
                client = _build_elevenlabs()
                client.synthesize(
                    text=text, voice_id=elevenlabs_voice_id,
                    model=elevenlabs_model, out_path=mp3_path,
                )
            except Exception as e:
                if not fallback_to_edge_tts:
                    raise
                print(f"[voice] elevenlabs failed ({type(e).__name__}: {e}); "
                      f"falling back to edge_tts")
                ssml_text = inject_ssml_pauses(text)
                _synthesize(ssml_text, voice, rate, pitch, mp3_path)
        else:
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
