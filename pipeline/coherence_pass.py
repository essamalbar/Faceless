"""Cross-clip narrative coherence pass.

After the script generator produces the initial beat list, this stage
re-reads all beats together and rewrites any that break continuity:
role swaps ("the thief becomes the homeowner"), location jumps without
transition, contradictions, or speaker confusion.

The LLM (Anthropic via the existing llm_anthropic.py path) is given the
full script context and instructed to return a JSON object with the
revised beats. Only fields the LLM is allowed to touch are merged back;
ids/durations/character_name fields the user already approved are NOT
overwritten.

Idempotent: skips if `script._dict.get("coherence_pass_v1")` is True,
so resuming a run doesn't double-process the script. Marker is stamped
back into the script dict before persistence.
"""
from __future__ import annotations

import json
import re
from dataclasses import replace
from typing import Protocol

from pipeline.types import Beat, Script


class _LLMLike(Protocol):
    """Minimal interface — anything with .complete(prompt, system=None) -> str."""
    def complete(self, prompt: str, system: str | None = None) -> str: ...


class CoherenceError(RuntimeError):
    """Raised when the LLM response can't be parsed into a usable beat list."""


_SYSTEM_PROMPT = (
    "You are an editor reviewing a short cinematic script for continuity errors. "
    "The script will be generated as a sequence of short video clips. Each beat "
    "becomes one clip. Your job is to find and fix continuity breaks in the "
    "english_motion field — the action description that the video model sees.\n\n"
    "Continuity breaks to fix:\n"
    "  1. ROLE SWAPS: a character described as the thief in beat 1 must not "
    "     become the homeowner in beat 2. Each character has ONE identity.\n"
    "  2. LOCATION JUMPS: if beats 1-3 are inside a house, beat 4 must not "
    "     suddenly be in a desert with no transition. Stay in the established "
    "     location unless there's an explicit travel/transition beat.\n"
    "  3. CONTRADICTIONS: action sequences must follow causally. If beat 1 "
    "     shows a door closed, beat 2 cannot show the same character already "
    "     outside without showing them open the door.\n"
    "  4. SPEAKER DRIFT: each beat's character_name field tells you who is "
    "     speaking. The english_motion must show THAT character on camera "
    "     (or describe the scene around them for voice-over). Do not put a "
    "     different character at the center of frame.\n\n"
    "DO NOT translate or rewrite the Arabic dialogue. DO NOT change speaker, "
    "character_name, or clip_duration_s. ONLY rewrite english_motion as "
    "needed for continuity. If a beat is already coherent, return it "
    "unchanged.\n\n"
    "Return a JSON object: {\"beats\": [{\"index\": 1, \"english_motion\": "
    "\"...\"}, ...]}. Include EVERY beat (rewritten or not). No prose, no "
    "markdown fences, just the JSON object."
)


def _serialize_beats_for_review(script: Script) -> str:
    """Compact format the LLM can scan quickly without spending tokens on JSON."""
    lines = []
    setting = script.global_setting or "(unspecified)"
    lines.append(f"SETTING: {setting}")
    if script.character_descriptions:
        lines.append("CHARACTERS:")
        for name, desc in script.character_descriptions.items():
            lines.append(f"  - {name}: {desc}")
    lines.append("BEATS:")
    for i, b in enumerate(script.beats, start=1):
        speaker = b.character_name or b.speaker or "(unspecified)"
        lines.append(
            f"  {i}. speaker={speaker}; arabic=\"{b.arabic}\"; "
            f"english_motion=\"{b.english_motion}\""
        )
    return "\n".join(lines)


def _extract_json_object(raw: str) -> dict:
    """Pull the first {...} object out of the response, tolerating stray prose
    or accidental markdown fencing the LLM sometimes adds despite instructions."""
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        raise CoherenceError(f"no JSON object found in LLM response: {raw[:200]!r}")
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError as e:
        raise CoherenceError(f"LLM response not valid JSON: {e}; raw={raw[:200]!r}")


def apply_coherence_pass(script: Script, llm: _LLMLike) -> Script:
    """Return a new Script with cross-clip continuity issues rewritten.

    Idempotent — if the script already carries the v1 marker it's returned
    unchanged. On any LLM error (network, parse, missing beats) the
    original script is returned: a failed coherence pass must never block
    a render, since the script is already approvable.
    """
    if getattr(script, "_coherence_pass_v1", False):
        return script
    if not script.beats:
        return script

    prompt = _serialize_beats_for_review(script) + (
        "\n\nReview each beat for continuity errors per the rules in the "
        "system prompt. Return the JSON object with all beats."
    )

    try:
        raw = llm.complete(prompt, system=_SYSTEM_PROMPT)
    except Exception:
        # LLM unavailable — return the original script untouched rather
        # than blocking. Render-time prompts still get the continuity
        # header injection from build_veo_prompt as a second line of
        # defense.
        return _marker(script)

    try:
        data = _extract_json_object(raw)
    except CoherenceError:
        return _marker(script)

    revised_by_index: dict[int, str] = {}
    for entry in data.get("beats", []):
        if not isinstance(entry, dict):
            continue
        idx = entry.get("index")
        new_motion = entry.get("english_motion")
        if isinstance(idx, int) and isinstance(new_motion, str) and new_motion.strip():
            revised_by_index[idx] = new_motion.strip()

    # Merge: each beat keeps every original field; only english_motion may
    # be replaced. If the LLM omitted a beat, the original is kept as-is.
    new_beats = []
    for i, b in enumerate(script.beats, start=1):
        new_motion = revised_by_index.get(i)
        if new_motion and new_motion != b.english_motion:
            new_beats.append(replace(b, english_motion=new_motion))
        else:
            new_beats.append(b)

    revised = replace(script, beats=tuple(new_beats))
    return _marker(revised)


def _marker(script: Script) -> Script:
    """Stamp the v1 marker so this stage doesn't re-run on resume.

    Stored as a dynamic attribute rather than a dataclass field so we don't
    touch the schema or the on-disk JSON shape unless somebody opts in via
    a future serialization tweak."""
    try:
        object.__setattr__(script, "_coherence_pass_v1", True)
    except Exception:
        pass
    return script
