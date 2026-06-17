"""Lyrics + style + cover-prompt generation for song mode.

The LLM is constrained by contract to emit Suno-readable structure
(section tags) and a structured style prompt. See the spec section
"Lyrics-LLM contract" for the load-bearing reasons; without this,
Suno output sounds obviously-AI.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field


_SECTION_TAG_RE = re.compile(r"\[(Verse|Pre-Chorus|Chorus|Bridge|Outro)[\s\d]*\]", re.I)


@dataclass(frozen=True)
class SongScript:
    title: str
    lyrics: str
    style_prompt: str
    cover_prompt: str
    language: str
    # Cinematic mode: one shared art direction + per-section scene prompts.
    # Empty for static-only runs / older payloads.
    art_direction: str = ""
    scene_prompts: list = field(default_factory=list)


def validate_section_tags(lyrics: str) -> None:
    """Raise ValueError if the lyrics block is missing Suno section tags
    or doesn't contain at least one [Chorus]."""
    if not _SECTION_TAG_RE.search(lyrics):
        raise ValueError(
            "lyrics missing Suno section tags ([Verse 1], [Chorus], ...) — "
            "Suno requires these to structure the arrangement"
        )
    if not re.search(r"\[Chorus\]", lyrics, re.I):
        raise ValueError("lyrics missing [Chorus] section")


_SYSTEM_PROMPT = """You write song lyrics for Suno V5.5.

OUTPUT FORMAT: a JSON object with these keys (no surrounding markdown, no commentary):
  - title:        short song title in the song's language
  - lyrics:       the full song with REQUIRED section tags
  - style_prompt: a structured comma-separated descriptor
  - cover_prompt: a prompt for an AI image model to make the album cover
  - art_direction: one-sentence shared look for the cinematic video
  - scene_prompts: JSON array of 6–8 per-section image prompts

LYRICS — REQUIRED SHAPE:
[Verse 1]
4–6 lines

[Pre-Chorus]
2–4 lines

[Chorus]
4 lines, hooky, will repeat

[Verse 2]
4–6 lines

[Chorus]
(same chorus, repeated verbatim)

[Bridge]
2–4 lines, contrasting

[Chorus]
(same chorus, possibly modified)

[Outro]
1–2 lines or empty

The bracket tags are LOAD-BEARING. Suno reads them. Do not omit them.

STYLE PROMPT — REQUIRED SHAPE (comma-separated):
  Genre/sub-genre, tempo (with BPM), instrumentation, vocal description,
  era/production style, mood + key.
Example: "Arabic pop ballad, slow tempo 72 BPM, oud + cinematic strings
+ light percussion, male vocal with subtle vibrato, modern 2020s
production warm analog mix, melancholic minor key"

COVER PROMPT — describe a single image: subject, setting, lighting, mood,
photography or art style. No text in the image (we burn the title on
separately). Leave space at the top-right corner.

If the user gave a style hint, include it in the style_prompt.

ART DIRECTION + SCENE PROMPTS (for the cinematic music-video mode):
  - art_direction: ONE sentence fixing the shared visual world for the
    whole video — palette, film stock/medium, lighting, mood. Every
    scene below must read as the same world.
  - scene_prompts: a JSON array of 6–8 image prompts, ONE per song
    section in order (Verse 1, Pre-Chorus, Chorus, Verse 2, ...). Each
    describes a distinct moment/angle WITHIN the art_direction (do not
    repeat the art_direction text in them). No text in any image.
    Reuse the SAME chorus imagery concept whenever [Chorus] repeats.
"""


def generate_song_script(
    *,
    llm,
    theme: str,
    custom_lyrics: str | None,
    style_hint: str | None,
    language: str,
) -> SongScript:
    """One-shot LLM call; returns a validated SongScript.

    If `custom_lyrics` is given, it is passed through verbatim — the LLM's
    lyrics field is ignored. If `style_hint` is given, it is appended to
    the user prompt as a "must include" so it surfaces in the LLM's
    style_prompt output.
    """
    user_msg = f"Theme: {theme}\nLanguage: {language}"
    if style_hint:
        user_msg += f"\nMust include in style: {style_hint}"
    if custom_lyrics:
        user_msg += (
            "\n\nThe user has provided their own lyrics — do NOT rewrite them, "
            "but still produce title, style_prompt, and cover_prompt:\n"
            + custom_lyrics
        )

    raw = llm.complete(user_msg, system=_SYSTEM_PROMPT)
    raw = raw.strip()
    if raw.startswith("```"):
        # Strip fenced-code wrappers (some models always wrap).
        raw = re.sub(r"^```[a-z]*\n?|\n?```$", "", raw, flags=re.MULTILINE).strip()
    # The Groq/Llama fallback provider sometimes wraps the JSON in prose and
    # emits raw newlines inside string values — both break strict json.loads.
    # Extract the outermost {...} and parse non-strict so raw control chars in
    # the lyrics are tolerated. Anthropic output already satisfies both, so
    # this is purely additive robustness for the fallback path.
    if not raw.startswith("{"):
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end > start:
            raw = raw[start:end + 1]
    parsed = json.loads(raw, strict=False)

    lyrics = custom_lyrics if custom_lyrics else parsed["lyrics"]
    validate_section_tags(lyrics)

    return SongScript(
        title=parsed["title"],
        lyrics=lyrics,
        style_prompt=parsed["style_prompt"],
        cover_prompt=parsed["cover_prompt"],
        language=language,
        art_direction=str(parsed.get("art_direction", "")),
        scene_prompts=list(parsed.get("scene_prompts", []) or []),
    )
