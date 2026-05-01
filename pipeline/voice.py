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
    """Run edge-tts in async context. Returns word-timing dicts."""
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


def generate_narration(
    text: str,
    voice: str,
    rate: str,
    pitch: str,
    mp3_path: Path,
    timings_path: Path,
) -> None:
    """Resumable: if both outputs already exist, skip."""
    if mp3_path.exists() and timings_path.exists():
        return
    ssml_text = inject_ssml_pauses(text)
    timings = _synthesize(ssml_text, voice, rate, pitch, mp3_path)
    timings_path.write_text(
        json.dumps(timings, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
