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
NarrationStyle = Literal["cinematic", "first_person_monologue", "ai_choose"]


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

_NARRATION_STYLE_TO_HUMAN = {
    "cinematic": (
        "Cinematic film style. Mix dialogue between characters, silent action "
        "beats (atmospheric / reaction shots), and occasional narrator "
        "voice-over. Use varied shot scales (wide establishing, "
        "over-the-shoulder, push-in, hand-held tracking, reaction close-up). "
        "Characters interact naturally with each other and with their "
        "environment — they do NOT address the camera in monologue."
    ),
    "first_person_monologue": (
        "First-person monologue style (TikTok @sunstoriz tradition). Every "
        "beat is a named character speaking direct-to-camera in first person "
        "(\"I…\"). english_motion frames each beat as a frontal medium "
        "close-up, mouth open mid-speech."
    ),
    "ai_choose": (
        "Narration style is your choice — pick whichever fits the premise "
        "based on the premise. "
        "If the premise calls for an intimate confessional tone, use "
        "first-person monologue. If the premise calls for environmental "
        "drama with multiple characters, use cinematic mixed-mode."
    ),
}


@dataclass(frozen=True)
class FreeformControls:
    dialect: Dialect = "msa"
    art_style: ArtStyle = "cinematic_photo_real"
    character_template: CharacterTemplate = "ai_choose"
    ending_type: EndingType = "ai_choose"
    num_beats: int = 8
    per_beat_seconds: int = 8
    narration_style: NarrationStyle = "cinematic"


_SYSTEM = (
    "You are an Arabic-language short-form video screenwriter. You can write in "
    "two modes: cinematic film style (mixed dialogue / silent / voice-over) or "
    "first-person monologue (every beat is a character speaking direct to camera). "
    "You adapt dialect, character cast, ending type, art direction, and narration "
    "style to the user's controls."
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

Narration style: {narration_style}

Beat types you may use:
- **Dialogue beat**: a named character speaks (arabic = the line). Speaker enum picks the role.
  In cinematic mode, dialogue is natural and reactive — characters answering each other,
  not delivering monologues.
- **Silent action beat**: arabic = "", speaker = "narrator". english_motion describes the
  visual / atmospheric / reaction shot. Use these for establishing, environmental detail,
  emotional reactions, scene transitions. (Available in cinematic / ai_choose modes.)
- **Voice-over beat**: speaker = "narrator", arabic carries short narration text. Use for
  poetic openings, time jumps, or final tag. (Available in cinematic / ai_choose modes.)

In first_person_monologue mode, EVERY beat is a Dialogue beat — silent and voice-over
beats are NOT used; every character speaks direct to camera in first person.

Requirements:
- Stick to the characters explicitly named or implied in the premise. Do NOT
  invent additional supporting characters (friends, neighbors, doctors,
  cousins, etc.) that the premise does not call for. If the premise mentions
  only two characters, use those two characters; the narrator may appear for
  silent / atmospheric / voice-over beats.
- All Arabic dialogue MUST be in {dialect}. No mixing with other dialects.
- Speaker values must be one of: mother, son, father, doctor, neighbor, grandmother,
  wife, daughter, friend, enemy, shadow, narrator. Use "narrator" for silent and
  voice-over beats.
- Each beat must include a `character_name` field — a SHORT Arabic name for the
  speaking character (e.g. "خالد", "فاطمة", "أم يوسف"). Use the SAME character_name
  for the same character across beats. For silent or voice-over beats with
  speaker="narrator", character_name may be empty "".
- Provide a `character_descriptions` map alongside `beats`. For every
  unique character_name that appears in any beat, include ONE concise
  English physical AND voice description (~20-30 words: age, build,
  hair, clothing AND voice tone/pitch/pace). These pin Veo's identity
  rendering AND voice consistency across all clips. Example:
  "young man mid-20s, slim, short black hair, white thobe; voice:
  warm tenor, slight rasp, measured calm pacing".

  IMPORTANT: if any beat uses speaker="narrator" with empty
  character_name (voice-over), ALSO include a "narrator" entry in
  character_descriptions with a voice-only profile (e.g. "deep
  masculine voice, late 40s, contemplative pacing, no visual"), so
  the narrator's voice stays consistent across all voice-over beats.
- english_motion describes the SHOT (English, ~30 words). In cinematic mode, this is
  cinematic shot direction: wide establishing, slow push-in, over-the-shoulder,
  hand-held tracking, reaction close-up, locked-off — NOT "facing camera, mouth open
  mid-speech, frontal medium close-up" as a fixed template. Vary the shot per beat.
  Reference visual continuity with neighboring beats: "continuing from prior frame",
  "same kitchen, now cut to medium close on the son", etc.
  In first_person_monologue mode, english_motion may use the frontal MCU framing.
- The final beat must match the ending type above.
- music_mood: pick one of drone, dread, cosmic, discovery.

Return JSON only, no markdown:

{{
  "title": "...",
  "theme": "{theme}",
  "global_setting": "short English visual style summary",
  "music_mood": "drone|dread|cosmic|discovery",
  "target_duration_s": <int>,
  "character_descriptions": {{
    "اسم شخصية 1": "young woman mid-30s, dark hair, beige hijab; voice: soft alto, gentle pace",
    "اسم شخصية 2": "...",
    "narrator": "deep masculine voice, late 40s, contemplative pacing, no visual"
  }},
  "beats": [
    {{"arabic":"...","english_motion":"...","clip_duration_s":<float>,"speaker":"...","character_name":"اسم عربي قصير أو فارغ للراوي"}},
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
        narration_style=_NARRATION_STYLE_TO_HUMAN[controls.narration_style],
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
