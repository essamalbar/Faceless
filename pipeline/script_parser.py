"""Markdown episode-script → structured beats.

Recognizes the format users write episode scripts in — supports BOTH
Arabic and English keywords:

    **Title: Sacred Necklace – Episode 4**           (or العنوان)
    **Scene 1 – Farewell**                            (or المشهد)
    **Mother (soft, emotional):**                     (or **الأم (بهمس):**)
    "Don't be afraid, my soul..."                     (or "أنا… وين…؟")

Per-beat english_motion is built from the SCENE-SPECIFIC stage directions
that precede each dialogue block — so two beats in the same scene get
DIFFERENT visual descriptions, not a generic placeholder.

The parser is regex-only — it never rewrites a single character of the
user's dialogue. Scenes with no `**SPEAKER:**` blocks become a single
silent beat with the scene's stage directions as the visual seed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Map speaker labels (Arabic OR English) to the pipeline's internal speaker
# IDs. All keys are lowercased before lookup; Arabic is unchanged by .lower().
_SPEAKER_LABEL_TO_EN: dict[str, str] = {
    # ----- Arabic -----
    "الشاب": "son", "الابن": "son",
    "الأم": "mother", "أم": "mother", "أمه": "mother",
    "الأب": "father", "أب": "father", "أبو": "father",
    "الدكتور": "doctor", "دكتور": "doctor", "الطبيب": "doctor",
    "الجار": "neighbor", "جاره": "neighbor",
    "الجدة": "grandmother", "جدته": "grandmother",
    "الزوجة": "wife", "زوجة": "wife",
    "البنت": "daughter", "ابنته": "daughter",
    "الصديق": "friend", "صديقه": "friend", "صاحبه": "friend",
    "الكيان": "enemy", "العدو": "enemy",
    "النسخة": "shadow", "النسخة الأخرى": "shadow", "الظل": "shadow",
    # ----- English -----
    "son": "son", "the son": "son", "young man": "son",
    "the young man": "son", "boy": "son",
    "mother": "mother", "mom": "mother", "mum": "mother",
    "the mother": "mother",
    "father": "father", "dad": "father", "the father": "father",
    "doctor": "doctor", "the doctor": "doctor",
    "neighbor": "neighbor", "neighbour": "neighbor", "the neighbor": "neighbor",
    "grandmother": "grandmother", "grandma": "grandmother", "the grandmother": "grandmother",
    "wife": "wife", "the wife": "wife",
    "daughter": "daughter", "the daughter": "daughter",
    "friend": "friend", "the friend": "friend", "buddy": "friend",
    "enemy": "enemy", "the enemy": "enemy",
    "entity": "enemy", "the entity": "enemy",
    "creature": "enemy", "the creature": "enemy",
    "shadow": "shadow", "the shadow": "shadow",
    "other self": "shadow", "the other self": "shadow",
    "dark self": "shadow", "the dark self": "shadow",
    "alter ego": "shadow", "the alter ego": "shadow",
    "other version": "shadow", "the other version": "shadow",
    "his shadow": "shadow", "his other self": "shadow",
}

# Scene heading: `**المشهد N – Title**` or `**Scene N – Title**` (en/em dash, hyphen)
_RE_SCENE = re.compile(
    r"\*\*\s*(?:المشهد|Scene|SCENE)\s+(\d+)\s*[–\-—:]\s*([^*]+?)\s*\*\*",
    re.IGNORECASE,
)

# Title line: `**العنوان: ...**` or `**Title: ...**`
_RE_TITLE = re.compile(
    r"\*\*\s*(?:العنوان|Title|TITLE)\s*[:：]\s*([^*\n]+?)\s*\*\*",
    re.IGNORECASE,
)

# Dialogue block. Speaker can be Arabic OR English (anything that isn't
# `*`, `:`, or a newline) optionally followed by `(stage direction)`. The
# quoted line follows on the next line(s); supports straight " and curly
# “” quotes; allows multi-line dialogue.
_RE_DIALOGUE = re.compile(
    r"\*\*\s*([^*\n:：]+?)\s*(?:\([^)]*\))?\s*[:：]\s*\*\*\s*\n+"
    r"\s*[\"“]([^\"”]+?)[\"”]",
    re.MULTILINE,
)


@dataclass
class ParsedBeat:
    arabic: str           # exact dialogue from the script (empty for silent beats)
    english_motion: str   # per-beat visual seed including scene's stage directions
    speaker: str          # internal speaker id
    clip_duration_s: float = 8.0
    character_name: str = ""


@dataclass
class ParsedScript:
    title: str
    beats: list[ParsedBeat]


def parse_arabic_speaker(label: str, default: str = "narrator") -> str:
    """Public alias kept for backwards-compat tests. Looks up an Arabic OR
    English speaker label in the map. Strips trailing punctuation and
    parentheticals before matching, case-insensitive on English."""
    return _lookup_speaker(label, default)


def _lookup_speaker(label: str, default: str = "narrator") -> str:
    """Normalize a speaker label and look it up in the alias map. If unknown,
    return the cleaned label as-is (loosened from the closed enum).

    Handles all of:
      "الشاب"             → son
      "الشاب (بهمس)"      → son
      "الأم (قوي):"       → mother   (parenthetical THEN colon)
      "Mother (soft):"    → mother
      "the young man"     → son
      "warrior"           → warrior  (unknown → pass-through)
    """
    # Strip trailing punctuation FIRST so "(soft):" → "(soft)"
    cleaned = label.strip().rstrip("：:،.,؟!").strip()
    # Then strip parentheticals anywhere in the label
    cleaned = re.sub(r"\s*\([^)]*\)", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    # Lowercase lookup — Arabic is unchanged by .lower(), English maps store keys lowercase
    return _SPEAKER_LABEL_TO_EN.get(
        cleaned.lower(),
        _SPEAKER_LABEL_TO_EN.get(cleaned, cleaned.lower() or default),
    )


def _clean_prose(s: str) -> str:
    """Strip markdown emphasis chars and collapse whitespace, keeping
    sentence punctuation intact. Used to normalize stage directions for
    inclusion in english_motion."""
    s = re.sub(r"\*+", "", s)            # **bold** → bold
    s = re.sub(r"^---+$", "", s, flags=re.MULTILINE)  # horizontal rules
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _english_motion(scene_num: int, scene_title: str, speaker: str,
                     stage_dir: str, is_silent: bool) -> str:
    """Build a per-beat english_motion seed.

    Includes the scene-specific stage-direction prose so two beats in the
    same scene get DIFFERENT visual descriptions. The user's prose is
    preserved verbatim — even if it's in Arabic, Veo will see it. They
    can edit any beat's motion in the UI before approving."""
    parts: list[str] = []
    parts.append(f"Scene {scene_num} — {scene_title}.")
    if stage_dir:
        # Truncate excessively long prose so the prompt stays Veo-friendly
        if len(stage_dir) > 320:
            stage_dir = stage_dir[:320].rstrip() + "…"
        parts.append(stage_dir + ("." if not stage_dir.endswith(".") else ""))
    if is_silent:
        parts.append(
            "Cinematic establishing shot, no dialogue, atmospheric music."
        )
    else:
        parts.append(
            f"The {speaker} character faces the camera at medium close-up, "
            f"mouth open mid-speech, lip-synced dialogue."
        )
    parts.append(
        "3D Pixar-style animation, anthropomorphic fruit characters, "
        "cinematic dramatic lighting, vertical 9:16."
    )
    return " ".join(parts)


def _extract_scenes(raw: str) -> list[tuple[int, str, str]]:
    """Split `raw` into scenes. Returns list of (scene_num, scene_title, body).
    If no scene headings are detected, the whole text is treated as one
    synthetic scene."""
    matches = list(_RE_SCENE.finditer(raw))
    if not matches:
        return [(1, "Episode", raw)]
    scenes: list[tuple[int, str, str]] = []
    for i, m in enumerate(matches):
        try:
            num = int(m.group(1))
        except ValueError:
            num = i + 1
        title = m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw)
        scenes.append((num, title, raw[start:end]))
    return scenes


def parse_episode_markdown(raw: str) -> ParsedScript:
    """Top-level entry point. Returns a `ParsedScript` ready for the UI to
    render in its structured-beat editor."""
    raw = raw.strip()

    title_m = _RE_TITLE.search(raw)
    title = title_m.group(1).strip() if title_m else "Untitled"

    beats: list[ParsedBeat] = []
    for scene_num, scene_title, scene_body in _extract_scenes(raw):
        dialogue_matches = list(_RE_DIALOGUE.finditer(scene_body))

        if dialogue_matches:
            # For each dialogue, capture the prose between the previous
            # boundary and this dialogue start as that beat's stage context.
            cursor = 0
            for m in dialogue_matches:
                stage_dir = _clean_prose(scene_body[cursor:m.start()])
                speaker = _lookup_speaker(m.group(1))
                beats.append(ParsedBeat(
                    arabic=m.group(2).strip(),
                    english_motion=_english_motion(
                        scene_num, scene_title, speaker, stage_dir,
                        is_silent=False),
                    speaker=speaker,
                ))
                cursor = m.end()
            # If significant prose remains AFTER the last dialogue (e.g.
            # closing stage direction "He stares at the sky"), append a
            # silent beat so it doesn't get lost. Threshold avoids tiny
            # trailing punctuation.
            trailing = _clean_prose(scene_body[cursor:])
            if len(trailing) > 60:
                beats.append(ParsedBeat(
                    arabic="",
                    english_motion=_english_motion(
                        scene_num, scene_title, "son", trailing,
                        is_silent=True),
                    speaker="son",
                ))
        else:
            # Silent scene — entire body is stage direction
            stage_dir = _clean_prose(scene_body)
            beats.append(ParsedBeat(
                arabic="",
                english_motion=_english_motion(
                    scene_num, scene_title, "son", stage_dir,
                    is_silent=True),
                speaker="son",
            ))
    return ParsedScript(title=title, beats=beats)
