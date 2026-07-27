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

from pipeline.llm import resolve_tier
from pipeline.song_style import compose_style


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
    negative_tags: str = ""
    # Provenance: which writer tier served the lyrics, and whether the style
    # came from the producer LLM ("producer:<tier>") or the recipe fallback.
    style_source: str = ""
    writer_tier: str = ""


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

ARABIC PRONUNCIATION — REQUIRED:
When the song's language is Arabic, write the lyrics FULLY DIACRITIZED
(تشكيل كامل على كل كلمة) — the singing model reads the harakat. Keep the
dialect's own spellings (do NOT fusha-ize dialect words); section tags stay
in English.

SINGABILITY — REQUIRED:
  - Consistent rhyme scheme (قافية موحّدة) within each section.
  - Singable, consistent meter: lines within a section carry roughly the
    same syllable count.
  - The [Chorus] hook repeats VERBATIM every time (including its tashkeel).
  - Mature, poetic register (عمق شعري): vivid imagery, authentic idioms,
    contemporary adult language — NEVER childish, nursery-rhyme, or naive
    phrasing, and no worn-out clichés.
  - Emotionally specific: concrete moments and sensory details over
    abstract generalities.
  - Singable words — but depth first: this is music for adults.
  - No tongue-twisters or consonant pile-ups.

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


# --- Two-pass tashkeel -------------------------------------------------------
# Composing great lyrics and fully diacritizing them in ONE call degrades
# both. Pass 1 composes naturally; pass 2 is a dedicated diacritization call
# guarded so it can only ADD harakat — a changed word rejects the pass and
# the composed lyrics ship undiacritized (the review screen's تشكيل button
# can retry).

# Arabic harakat + tatweel — stripped to compare letter skeletons.
HARAKAT_RE = re.compile(r"[ً-ٰٟـ]")
# Orthographic variants diacritizers legitimately normalize (hamza seats,
# alef forms, alef maqsura) — folded before comparison so a hamza-seat
# correction (ا→أ) doesn't read as a "changed word".
_ARABIC_FOLD = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا",
    "ى": "ي", "ئ": "ي", "ؤ": "و",
})

DIACRITIZE_SYSTEM = """You add FULL Arabic diacritics (تشكيل كامل) to song
lyrics so a singing model pronounces every word correctly.

RULES:
- Add fatha/damma/kasra/sukun/shadda/tanwin to EVERY Arabic word.
- Do NOT add, remove, reorder, translate, or change ANY word.
- Do NOT "correct" dialect spellings toward فصحى (keep السما as السما, not
  السماء) — only add marks to the letters that are already there.
- Keep section tags ([Verse 1], [Chorus], ...) and line breaks EXACTLY as-is.
- Non-Arabic words pass through untouched.
- Output ONLY the diacritized lyrics — no commentary, no markdown."""


# Anything that is NOT a letter/digit (Arabic or Latin) — punctuation,
# quotes, dashes, brackets — is pronunciation-irrelevant and models freely
# add/remove it while diacritizing.
_NON_LETTER_RE = re.compile(r"[^\w\u0621-\u064A]+")


def tashkeel_density(text: str) -> float:
    """harakat marks per Arabic letter — a cheap 'is this diacritized?'
    signal (fully diacritized text lands ~0.6-0.9; bare text < 0.1)."""
    letters = sum(1 for c in text if "ء" <= c <= "ي")
    if not letters:
        return 0.0
    return len(HARAKAT_RE.findall(text)) / letters


def letter_skeleton(text: str) -> str:
    """LETTERS ONLY: harakat/tatweel stripped, hamza/alef variants folded,
    punctuation dropped, whitespace normalized — two lyrics with the same
    skeleton contain the same words (orthographic corrections like ا→أ and
    punctuation shuffles are NOT word changes)."""
    folded = HARAKAT_RE.sub("", text).translate(_ARABIC_FOLD)
    return " ".join(_NON_LETTER_RE.sub(" ", folded).split())


def diacritize_lyrics(llm, lyrics: str) -> str | None:
    """Dedicated tashkeel pass. Returns the diacritized lyrics, or None when
    the model changed words (skeleton mismatch) or errored — callers keep
    the original in that case."""
    try:
        raw = llm.complete(lyrics, system=DIACRITIZE_SYSTEM).strip()
    except Exception as e:
        print(f"[lyrics] diacritize pass failed ({e}); keeping composed text")
        return None
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?|\n?```$", "", raw, flags=re.MULTILINE).strip()
    # Models sometimes prepend commentary; lyrics always start at a section
    # tag — cut anything before the first '['.
    if not raw.startswith("[") and "[" in raw:
        raw = raw[raw.index("["):].strip()
    if letter_skeleton(raw) != letter_skeleton(lyrics):
        # Log the first divergent words so prod logs show WHY (this guard
        # silently ate tashkeel once; never let it be a mystery again).
        wa, wb = letter_skeleton(lyrics).split(), letter_skeleton(raw).split()
        diffs = [f"{x!r}→{y!r}" for x, y in zip(wa, wb) if x != y][:5]
        print(f"[lyrics] diacritize pass changed words — rejected "
              f"(in={len(wa)}w out={len(wb)}w diffs={diffs})")
        return None
    return raw


_DIALECT_NAMES = {
    "msa": "Modern Standard Arabic (فصحى)",
    "egyptian": "Egyptian Arabic (مصري)",
    "khaleeji": "Gulf Arabic (خليجي)",
    "levantine": "Levantine Arabic (شامي)",
    "iraqi": "Iraqi Arabic (عراقي)",
}


def generate_song_script(
    *,
    llm,
    theme: str,
    custom_lyrics: str | None,
    style_hint: str | None,
    language: str,
    dialect: str | None = None,
    vocal_gender: str | None = "m",
) -> SongScript:
    """One-shot LLM call; returns a validated SongScript.

    If `custom_lyrics` is given, it is passed through verbatim — the LLM's
    lyrics field is ignored. If `style_hint` is given, it is appended to
    the user prompt as a "must include" so it surfaces in the LLM's
    style_prompt output. `dialect` (msa/egyptian/khaleeji/levantine/iraqi)
    pins the Arabic variety the lyrics are written in.
    """
    user_msg = f"Theme: {theme}\nLanguage: {language}"
    if dialect and dialect in _DIALECT_NAMES:
        user_msg += (f"\nDialect: write the lyrics in "
                     f"{_DIALECT_NAMES[dialect]} — authentic vocabulary and "
                     f"expressions of that dialect, still fully diacritized.")
    if style_hint:
        user_msg += f"\nMust include in style: {style_hint}"
    if custom_lyrics:
        user_msg += (
            "\n\nThe user has provided their own lyrics — do NOT rewrite them, "
            "but still produce title, style_prompt, and cover_prompt:\n"
            + custom_lyrics
        )

    # Free-tier writers occasionally emit ONE malformed JSON sample
    # (unescaped quote mid-lyrics etc.) — a fresh sample almost always
    # parses, so retry the call once before failing the request.
    parsed = None
    last_err: Exception | None = None
    for attempt in range(2):
        msg = user_msg if attempt == 0 else (
            user_msg + "\n\nIMPORTANT: reply with ONLY a VALID JSON object — "
                       "escape any double quotes inside string values.")
        raw = llm.complete(msg, system=_SYSTEM_PROMPT).strip()
        if raw.startswith("```"):
            # Strip fenced-code wrappers (some models always wrap).
            raw = re.sub(r"^```[a-z]*\n?|\n?```$", "", raw,
                         flags=re.MULTILINE).strip()
        # Some providers wrap the JSON in prose / emit raw newlines inside
        # string values — extract the outermost {...} and parse non-strict.
        if not raw.startswith("{"):
            start, end = raw.find("{"), raw.rfind("}")
            if start != -1 and end > start:
                raw = raw[start:end + 1]
        try:
            parsed = json.loads(raw, strict=False)
            break
        except json.JSONDecodeError as e:
            last_err = e
            print(f"[lyrics] JSON parse failed (attempt {attempt + 1}): {e}")
    if parsed is None:
        raise last_err  # surfaces as the existing 500 with a clear message

    lyrics = custom_lyrics if custom_lyrics else parsed["lyrics"]
    validate_section_tags(lyrics)

    # Tashkeel: the compose contract already requires full diacritization
    # (capable models deliver ~0.7+ harakat density). The dedicated
    # diacritize pass is a RESCUE for low-density output only — running it
    # unconditionally caused more harm than good (diacritizers fusha-ize
    # dialect spellings → guard rejects → bare lyrics shipped).
    if not custom_lyrics and language.startswith("ar"):
        if tashkeel_density(lyrics) < 0.30:
            diacritized = diacritize_lyrics(llm, lyrics)
            if diacritized:
                lyrics = diacritized

    # Capture which writer tier produced the lyrics BEFORE the producer pass
    # (compose_style makes its own call and would overwrite last_tier).
    writer_tier = resolve_tier(llm)

    # Producer pass: authoritative Suno style + negative tags. The lyrics-JSON
    # style_prompt (parsed["style_prompt"]) is intentionally ignored — a weak
    # writer's blob is exactly what this replaces.
    style = compose_style(
        llm, theme=theme, title=parsed["title"], lyrics=lyrics,
        language=language, dialect=dialect, style_hint=style_hint,
        vocal_gender=vocal_gender,
    )

    return SongScript(
        title=parsed["title"],
        lyrics=lyrics,
        style_prompt=style.style_prompt,
        cover_prompt=parsed["cover_prompt"],
        language=language,
        art_direction=str(parsed.get("art_direction", "")),
        scene_prompts=list(parsed.get("scene_prompts", []) or []),
        negative_tags=style.negative_tags,
        style_source=style.source,
        writer_tier=writer_tier,
    )
