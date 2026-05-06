"""Freeform Arabic short-script generator.

Unlike pipeline.script.generate_shorts_script (which is locked to the
Sunstoriz fruit-melodrama template), this module's prompt is parameterised
by user-supplied controls — dialect, art style, character template, ending
type. The downstream Script schema is identical so Flux/Veo/assemble are
unchanged."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pipeline.script import _parse_shorts_script_json
from pipeline.types import Script, ThemeSeed


Dialect = Literal["msa", "syrian", "egyptian", "khaliji", "maghrebi", "iraqi"]
ArtStyle = Literal[
    "pixar_3d", "anime_2d", "cinematic_photo_real",
    "claymation", "hand_drawn", "ghibli",
]
CharacterTemplate = Literal[
    "human", "fruit_sunstoriz", "animal", "surreal", "ai_choose",
]
EndingType = Literal[
    "open", "closed_tragic", "closed_happy", "twist", "ai_choose",
]


_DIALECT_TO_HUMAN = {
    "msa": "Modern Standard Arabic (الفصحى)",
    "syrian": "Syrian / Levantine dialect (شامي)",
    "egyptian": "Egyptian dialect (مصري)",
    "khaliji": "Khaliji / Gulf dialect (خليجي)",
    "maghrebi": "Maghrebi / North-African dialect (مغربي)",
    "iraqi": "Iraqi dialect (عراقي)",
}

_ART_STYLE_TO_HUMAN = {
    "pixar_3d": "3D Pixar-style animation",
    "anime_2d": "2D anime",
    "cinematic_photo_real": "cinematic photo-real live-action look",
    "claymation": "claymation / stop-motion",
    "hand_drawn": "hand-drawn illustrative animation",
    "ghibli": "Studio Ghibli-style 2D animation",
}

_CHAR_TEMPLATE_TO_HUMAN = {
    "human": "human characters",
    "fruit_sunstoriz": "anthropomorphic fruit characters (Sunstoriz style)",
    "animal": "anthropomorphic animal characters",
    "surreal": "surreal / abstract creatures",
    "ai_choose": "let the writer choose whichever character cast fits the premise",
}

_ENDING_TO_HUMAN = {
    "open": "an open-ended, unresolved ending",
    "closed_tragic": "a closed tragic ending (clear loss / death / final breaking point)",
    "closed_happy": "a closed happy or hopeful ending",
    "twist": "a twist ending the audience does not see coming",
    "ai_choose": "whichever ending type best serves the premise",
}


@dataclass(frozen=True)
class FreeformControls:
    dialect: Dialect = "msa"
    art_style: ArtStyle = "cinematic_photo_real"
    character_template: CharacterTemplate = "ai_choose"
    ending_type: EndingType = "ai_choose"
    num_beats: int = 8
    per_beat_seconds: int = 8


_SYSTEM = (
    "You are an Arabic-language short-form video script writer. You adapt "
    "your style — dialect, character cast, ending type, art direction — to "
    "the user's premise and controls. You do not impose any fixed template."
)


_PROMPT_TEMPLATE = """\
Write a short-form Arabic video script (TikTok / Reels) for the following premise.

Premise: {premise}
Theme tag: {theme}

Controls:
- Dialect: {dialect}
- Visual / art style: {art_style}
- Character cast: {character_template}
- Ending type: {ending_type}
- Number of beats: exactly {num_beats}
- Target duration per beat: ~{per_beat_seconds}s (each clip_duration_s between {min_s} and {max_s})

Requirements:
- All Arabic dialogue MUST be in {dialect}. No mixing with other dialects.
- Each beat speaks in first person — a named character talks, not a narrator.
- Speaker values must be one of: mother, son, father, doctor, neighbor,
  grandmother, wife, daughter, friend, enemy, shadow.
- english_motion describes the visual action for that beat (~25 words),
  reinforcing visual continuity from the previous beat.
- The final beat must match the ending type above.
- music_mood: pick one of drone, dread, cosmic, discovery.

Return JSON only, no markdown:

{{
  "title": "...",
  "theme": "{theme}",
  "global_setting": "short English visual style summary",
  "music_mood": "drone|dread|cosmic|discovery",
  "target_duration_s": <int>,
  "beats": [
    {{"arabic":"...","english_motion":"...","clip_duration_s":<float>,"speaker":"..."}},
    ...exactly {num_beats} beats...
  ]
}}
"""


def build_freeform_prompt(seed: ThemeSeed, controls: FreeformControls) -> str:
    min_s = max(4.0, controls.per_beat_seconds * 0.6)
    max_s = min(12.0, controls.per_beat_seconds * 1.4)
    return _PROMPT_TEMPLATE.format(
        premise=seed.premise,
        theme=seed.theme,
        dialect=_DIALECT_TO_HUMAN[controls.dialect],
        art_style=_ART_STYLE_TO_HUMAN[controls.art_style],
        character_template=_CHAR_TEMPLATE_TO_HUMAN[controls.character_template],
        ending_type=_ENDING_TO_HUMAN[controls.ending_type],
        num_beats=controls.num_beats,
        per_beat_seconds=controls.per_beat_seconds,
        min_s=min_s, max_s=max_s,
    )


def generate_freeform_script(
    llm,
    seed: ThemeSeed,
    controls: FreeformControls,
) -> Script:
    prompt = build_freeform_prompt(seed, controls)
    raw = llm.complete(prompt, system=_SYSTEM)
    return _parse_shorts_script_json(raw, seed)
