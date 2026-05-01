"""Stage 4: scene splitter — turns script + word timings into shots.json."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from pipeline.types import Script, Shot, WordTiming

STYLE_SUFFIX = (
    "dark atmospheric horror photography, dim moonlight, slight film grain, "
    "35mm aesthetic, low light, cinematic composition, eerie mood, "
    "muted desaturated colors, ultra-realistic, 16:9"
)
NEGATIVE_PROMPT = (
    "text, watermark, logo, blurry, low quality, deformed faces, "
    "clear faces, multiple subjects, busy composition, cartoon, illustration"
)

# Arabic + Latin sentence enders
SENTENCE_END_CHARS = {".", "؟", "!", "…"}

PROMPT_TRANSLATE_TEMPLATE = """\
You are translating an Arabic horror story into atmospheric image prompts.

Story global setting: {global_setting}

Below is one Arabic paragraph (~15-20 seconds of narration). Output ONE
English image prompt for an atmospheric horror image illustrating this moment.
NO text in the image. Photographic, dark, eerie. Describe environment,
lighting, time of day, key visual element. ~25 words. Plain text only,
no quotes, no preamble.

Arabic paragraph:
{arabic_text}

Output:
"""


def shot_seed(title: str, index: int) -> int:
    """Deterministic seed per (title, shot_index). Stable across runs."""
    h = hashlib.sha256(f"{title}::{index}".encode("utf-8")).hexdigest()
    return int(h[:8], 16)  # 32-bit unsigned


def _sentence_end_indices(timings: list[WordTiming]) -> set[int]:
    """Word indices whose token ends with a sentence-end character."""
    ends: set[int] = set()
    for i, wt in enumerate(timings):
        if wt.word and wt.word.strip() and wt.word.strip()[-1] in SENTENCE_END_CHARS:
            ends.add(i)
    if timings:
        ends.add(len(timings) - 1)  # always include the very last word
    return ends


def chunk_by_timing(
    timings: list[WordTiming],
    target_ms: int,
    sentence_ends: set[int],
) -> list[dict]:
    """Walk word timings; close chunk near `target_ms`, snapping to sentence ends.

    Returns list of {start_ms, end_ms, first_word_index, last_word_index}.
    """
    if not timings:
        return []
    chunks: list[dict] = []
    chunk_start_idx = 0
    chunk_start_ms = timings[0].offset_ms
    for i, wt in enumerate(timings):
        elapsed = (wt.offset_ms + wt.duration_ms) - chunk_start_ms
        is_sentence_end = i in sentence_ends
        is_last_word = i == len(timings) - 1
        # No future sentence-end exists in this chunk's remaining words → close now
        future_sentence_ends = any(j in sentence_ends for j in range(i, len(timings)))
        can_snap = is_sentence_end or not future_sentence_ends
        if (elapsed >= target_ms and can_snap) or is_last_word:
            chunks.append({
                "start_ms": chunk_start_ms,
                "end_ms": wt.offset_ms + wt.duration_ms,
                "first_word_index": chunk_start_idx,
                "last_word_index": i,
            })
            if not is_last_word:
                chunk_start_idx = i + 1
                chunk_start_ms = timings[i + 1].offset_ms
    return chunks


def _arabic_text_for_chunk(timings: list[WordTiming], chunk: dict) -> str:
    words = [t.word for t in timings[chunk["first_word_index"] : chunk["last_word_index"] + 1]]
    return " ".join(w for w in words if w.strip())


def generate_shots(
    gemini,
    script: Script,
    timings: list[WordTiming],
    out_path: Path,
    target_segment_ms: int = 18000,
) -> list[Shot]:
    """Produce shots.json. Resumable (skips if file exists)."""
    if out_path.exists():
        return [Shot.from_dict(d) for d in json.loads(out_path.read_text(encoding="utf-8"))]

    sentence_ends = _sentence_end_indices(timings)
    chunks = chunk_by_timing(timings, target_segment_ms, sentence_ends)

    shots: list[Shot] = []
    for i, chunk in enumerate(chunks):
        arabic = _arabic_text_for_chunk(timings, chunk)
        prompt = PROMPT_TRANSLATE_TEMPLATE.format(
            global_setting=script.global_setting,
            arabic_text=arabic,
        )
        english_core = gemini.complete(prompt).strip()
        # strip surrounding quotes if Gemini ignored instructions
        english_core = english_core.strip('"\'')
        english_full = f"{english_core}, {STYLE_SUFFIX}"
        shots.append(Shot(
            index=i + 1,
            start_ms=chunk["start_ms"],
            end_ms=chunk["end_ms"],
            arabic_text=arabic,
            english_prompt=english_full,
            negative_prompt=NEGATIVE_PROMPT,
            seed=shot_seed(script.title, i),
        ))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps([s.to_dict() for s in shots], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return shots
