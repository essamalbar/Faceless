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

BATCH_PROMPT_TEMPLATE = """\
You are translating an Arabic horror story into a sequence of English atmospheric image prompts.

Global story setting: {global_setting}

Below are {n} Arabic paragraphs from the story (one per shot, in order).
For each, write one English image prompt for an atmospheric horror image
illustrating that moment. Rules per prompt:
- NO text in the image (no signs, no captions).
- Photographic, dark, eerie aesthetic.
- Describe environment, lighting, time of day, one key visual element.
- ~25 words each.
- Do NOT include quotes around the prompt.
- Reuse the global setting consistently across all shots.

Return STRICTLY a JSON array of {n} strings (one prompt per paragraph,
in the same order). No commentary, no markdown fences, just the JSON.

Paragraphs:
{numbered_paragraphs}
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


def _strip_code_fence(text: str) -> str:
    """Remove ```json ... ``` or ``` ... ``` wrappers if present."""
    s = text.strip()
    fence = re.match(r"^```(?:json)?\s*\n(.*?)\n```\s*$", s, re.DOTALL)
    if fence:
        return fence.group(1).strip()
    return s


def _translate_prompts_batched(gemini, script: Script, arabic_paragraphs: list[str]) -> list[str]:
    """One Gemini call → N English prompts. Saves quota over per-shot calls."""
    if not arabic_paragraphs:
        return []
    numbered = "\n\n".join(f"[{i+1}] {p}" for i, p in enumerate(arabic_paragraphs))
    prompt = BATCH_PROMPT_TEMPLATE.format(
        global_setting=script.global_setting,
        n=len(arabic_paragraphs),
        numbered_paragraphs=numbered,
    )
    raw = _strip_code_fence(gemini.complete(prompt))
    try:
        prompts = json.loads(raw)
    except json.JSONDecodeError:
        # Defensive fallback: produce a generic prompt per chunk so the pipeline
        # still completes. Will look generic but won't fail.
        return [
            f"atmospheric horror scene in {script.global_setting}, dim moonlight, eerie mood"
            for _ in arabic_paragraphs
        ]
    if not isinstance(prompts, list):
        return [
            f"atmospheric horror scene in {script.global_setting}, dim moonlight, eerie mood"
            for _ in arabic_paragraphs
        ]
    # Pad/truncate to expected length to keep shot indexing aligned.
    if len(prompts) < len(arabic_paragraphs):
        prompts = list(prompts) + [
            f"atmospheric horror scene in {script.global_setting}, dim moonlight, eerie mood"
            for _ in range(len(arabic_paragraphs) - len(prompts))
        ]
    return [str(p).strip().strip('"\'') for p in prompts[: len(arabic_paragraphs)]]


def generate_shots(
    gemini,
    script: Script,
    timings: list[WordTiming],
    out_path: Path,
    target_segment_ms: int = 18000,
) -> list[Shot]:
    """Produce shots.json. Resumable (skips if file exists).

    Uses ONE batched Gemini call to translate all Arabic chunks into English
    image prompts. Avoids hitting the per-minute rate limit at ~40 shots/run.
    """
    if out_path.exists():
        return [Shot.from_dict(d) for d in json.loads(out_path.read_text(encoding="utf-8"))]

    sentence_ends = _sentence_end_indices(timings)
    chunks = chunk_by_timing(timings, target_segment_ms, sentence_ends)
    arabic_chunks = [_arabic_text_for_chunk(timings, c) for c in chunks]
    english_cores = _translate_prompts_batched(gemini, script, arabic_chunks)

    shots: list[Shot] = []
    for i, chunk in enumerate(chunks):
        arabic = arabic_chunks[i]
        english_core = english_cores[i]
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
