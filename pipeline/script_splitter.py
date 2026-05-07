"""LLM-based prose-to-beats splitter for the hybrid paste-script parser.

Used by POST /runs/parse-script when the regex parser finds zero dialogue
blocks (i.e. freeform prose, not the structured episode-markdown grammar).

Critical invariant: the LLM segments text but NEVER rewrites it. We verify
this by concatenating every output beat's `arabic` field and comparing
(whitespace-normalised) to the input. Mismatches retry once; persistent
mismatches fall back to a naive sentence-split that always produces
multiple beats."""
from __future__ import annotations

import json
import re

from pipeline.script_parser import ParsedBeat

_SYSTEM = (
    "You are a script-segmentation tool. You split Arabic prose into beats "
    "without rewriting a single character of the user's text. You only "
    "decide WHERE to cut and produce visual descriptions."
)

_PROMPT_TEMPLATE = """\
Split the following Arabic prose into approximately {target_beats} beats
(±1 acceptable). For each beat output:

- arabic: a verbatim contiguous slice of the input. Concatenated together,
  every beat's arabic field MUST equal the original input minus whitespace.
  Do not paraphrase, summarise, fix grammar, or change a single word.
- english_motion: a short English visual prompt for video generation (~25 words).
- speaker: one of mother, son, father, doctor, neighbor, grandmother, wife,
  daughter, friend, enemy, shadow. Pick the most likely speaker for that beat.
- clip_duration_s: a number between {min_s} and {max_s} based on beat length.
- character_name: a short Arabic name for the speaking character (e.g. "خالد",
  "فاطمة", "أم يوسف"). Use the SAME name for the same character across beats.

Return JSON only, no markdown:

{{"beats": [{{"arabic":"…","english_motion":"…","speaker":"…","clip_duration_s":N,"character_name":"اسم عربي قصير"}}, ...]}}

Input prose:
{raw}
"""

NAIVE_FALLBACK_SENTINEL = "(auto-generated visual — please review)"


def _normalize(s: str) -> str:
    """Remove all whitespace — used by the verbatim guard so trivial whitespace
    differences (spaces between joined beats, trailing newlines, etc.) don't
    trigger a retry."""
    return re.sub(r"\s+", "", s)


def _verbatim_match(input_text: str, joined_output: str) -> bool:
    """True iff the LLM's concatenated arabic equals the input modulo whitespace."""
    return _normalize(input_text) == _normalize(joined_output)


def _strip_code_fence(text: str) -> str:
    """Mirror the helper in pipeline/script.py — handle ```json ... ``` wraps."""
    s = text.strip()
    m = re.match(r"^```(?:json)?\s*\n(.*?)\n```\s*$", s, re.DOTALL)
    return m.group(1).strip() if m else s


def _parse_response(raw_response: str) -> list[ParsedBeat]:
    cleaned = _strip_code_fence(raw_response)
    data = json.loads(cleaned)
    beats_raw = data.get("beats") or []
    beats: list[ParsedBeat] = []
    for b in beats_raw:
        speaker = str(b.get("speaker", "")).strip().lower() or "narrator"
        beats.append(ParsedBeat(
            arabic=str(b.get("arabic", "")).strip(),
            english_motion=str(b.get("english_motion", "")).strip(),
            speaker=speaker,
            clip_duration_s=float(b.get("clip_duration_s", 8.0)),
            character_name=str(b.get("character_name", "")).strip(),
        ))
    return beats


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[\.!\?؟…])\s+|\n\n+")


def _naive_split(raw: str, target_beats: int, per_beat_seconds: int) -> list[ParsedBeat]:
    """Last-resort sentence splitter. Always produces ≥1 beat; tries to land
    near `target_beats` by grouping sentences into roughly-equal chunks."""
    sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(raw) if s.strip()]
    if not sentences:
        sentences = [raw.strip()] if raw.strip() else [""]
    if len(sentences) <= target_beats:
        groups = [[s] for s in sentences]
    else:
        per_group = max(1, len(sentences) // target_beats)
        groups = [
            sentences[i:i + per_group]
            for i in range(0, len(sentences), per_group)
        ]
        if len(groups) > target_beats and len(groups[-1]) <= 1:
            groups[-2].extend(groups[-1])
            groups.pop()
    return [
        ParsedBeat(
            arabic=" ".join(g),
            english_motion=NAIVE_FALLBACK_SENTINEL,
            speaker="mother",
            clip_duration_s=float(per_beat_seconds),
        )
        for g in groups
    ]


def split_prose_into_beats(
    llm,
    raw_text: str,
    target_beats: int = 8,
    per_beat_seconds: int = 8,
) -> list[ParsedBeat]:
    """Split freeform prose into beats. LLM-first with verbatim guard;
    naive sentence-split fallback if the LLM keeps rewriting."""
    target_beats = max(2, min(15, target_beats))
    min_s = max(4.0, per_beat_seconds * 0.6)
    max_s = min(12.0, per_beat_seconds * 1.4)
    prompt = _PROMPT_TEMPLATE.format(
        target_beats=target_beats,
        min_s=min_s, max_s=max_s,
        raw=raw_text,
    )
    for _attempt in range(2):
        try:
            response = llm.complete(prompt, system=_SYSTEM)
            beats = _parse_response(response)
        except (json.JSONDecodeError, ValueError, TypeError):
            continue
        if not beats:
            continue
        joined = " ".join(b.arabic for b in beats)
        if _verbatim_match(raw_text, joined):
            return beats
    # Both attempts failed — fall back
    return _naive_split(raw_text, target_beats, per_beat_seconds)
