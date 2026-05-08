from __future__ import annotations

from pipeline.script_freeform import (
    FreeformControls,
    build_freeform_prompt,
    generate_freeform_script,
)
from pipeline.types import ThemeSeed


def test_controls_interpolated_into_prompt():
    seed = ThemeSeed(theme="urban", premise="A photographer who loses memory.")
    controls = FreeformControls(
        dialect="egyptian", art_style="anime_2d",
        character_template="human", ending_type="twist",
        num_beats=10, per_beat_seconds=8,
    )
    prompt = build_freeform_prompt(seed, controls)
    assert "egyptian" in prompt.lower()
    assert "anime" in prompt.lower()
    assert "twist" in prompt.lower()
    assert "10" in prompt  # num_beats present
    assert "A photographer who loses memory." in prompt


def test_no_hardcoded_sunstoriz_in_default_prompt():
    """Critical: the default prompt MUST NOT mention fruit characters,
    Syrian dialect, or tragic-ending lock — those were the static-story bug."""
    seed = ThemeSeed(theme="folkloric", premise="x")
    controls = FreeformControls()  # all defaults
    prompt = build_freeform_prompt(seed, controls)
    lower = prompt.lower()
    assert "lemon" not in lower
    assert "strawberry" not in lower
    assert "syrian" not in lower
    # "tragic" is allowed only as a menu item (e.g. "closed_tragic"); it
    # must NOT appear as an enforced ending.
    if "tragic" in lower:
        assert "ai_choose" in lower or "menu" in lower or "ending type" in lower


class _StubLLM:
    def __init__(self, response): self.response = response
    def complete(self, prompt, system=""): return self.response


def test_generate_freeform_script_happy_path():
    llm = _StubLLM('''{
      "title":"Lost",
      "theme":"urban",
      "global_setting":"foggy city",
      "music_mood":"dread",
      "target_duration_s":24,
      "beats":[
        {"arabic":"بيت أول","english_motion":"x","clip_duration_s":8,"speaker":"mother"},
        {"arabic":"بيت ثاني","english_motion":"y","clip_duration_s":8,"speaker":"son"},
        {"arabic":"بيت ثالث","english_motion":"z","clip_duration_s":8,"speaker":"father"}
      ]
    }''')
    seed = ThemeSeed(theme="urban", premise="x")
    controls = FreeformControls(num_beats=3, per_beat_seconds=8)
    script = generate_freeform_script(llm, seed, controls)
    assert script.title == "Lost"
    assert len(script.beats) == 3
    assert script.beats[1].speaker == "son"


def test_freeform_prompt_mentions_character_name():
    """The freeform prompt instructs the LLM to pick consistent Arabic
    character names per character (matching the chosen dialect)."""
    p = build_freeform_prompt(
        ThemeSeed(theme="urban", premise="x"),
        FreeformControls(dialect="egyptian"),
    )
    assert "character_name" in p


def test_freeform_default_narration_style_is_cinematic():
    """Default narration_style is 'cinematic' — the old first-person mandate is gone."""
    from pipeline.script_freeform import FreeformControls
    c = FreeformControls()
    assert c.narration_style == "cinematic"


def test_cinematic_prompt_drops_first_person_mandate():
    """In cinematic mode, the prompt MUST NOT enforce first-person speech."""
    from pipeline.script_freeform import (
        build_freeform_prompt, FreeformControls, _SYSTEM,
    )
    from pipeline.types import ThemeSeed
    p = build_freeform_prompt(
        ThemeSeed(theme="urban", premise="x"),
        FreeformControls(narration_style="cinematic"),
    )
    full = (_SYSTEM + "\n" + p).lower()
    # Old mandate is gone
    assert "each beat speaks in first person" not in full
    assert "no narrator" not in full


def test_cinematic_prompt_offers_camera_direction_vocabulary():
    """Cinematic mode prompts for shot direction (wide, push-in, OTS, etc.)."""
    from pipeline.script_freeform import (
        build_freeform_prompt, FreeformControls, _SYSTEM,
    )
    from pipeline.types import ThemeSeed
    p = build_freeform_prompt(
        ThemeSeed(theme="urban", premise="x"),
        FreeformControls(narration_style="cinematic"),
    )
    full = (_SYSTEM + "\n" + p).lower()
    # Cinematic shot vocabulary should be referenced
    cues = ["wide", "push-in", "over-the-shoulder", "establishing",
            "close-up", "atmosphere", "voice-over", "narrator", "reaction"]
    found = sum(1 for c in cues if c in full)
    assert found >= 2, f"cinematic prompt should reference shot vocabulary; matched={found}"


def test_first_person_monologue_style_keeps_old_behavior():
    """When narration_style='first_person_monologue', the prompt explicitly
    requires first-person speech (preserves the old TV-interview style as opt-in)."""
    from pipeline.script_freeform import (
        build_freeform_prompt, FreeformControls,
    )
    from pipeline.types import ThemeSeed
    p = build_freeform_prompt(
        ThemeSeed(theme="urban", premise="x"),
        FreeformControls(narration_style="first_person_monologue"),
    )
    lower = p.lower()
    assert "first person" in lower or "first-person" in lower or "ضمير المتكلم" in p


def test_ai_choose_narration_lets_writer_decide():
    """When narration_style='ai_choose', the prompt does NOT mandate either style."""
    from pipeline.script_freeform import (
        build_freeform_prompt, FreeformControls,
    )
    from pipeline.types import ThemeSeed
    p = build_freeform_prompt(
        ThemeSeed(theme="urban", premise="x"),
        FreeformControls(narration_style="ai_choose"),
    )
    lower = p.lower()
    # No hard mandate either way; the prompt should mention both options exist
    # and the writer chooses based on the premise.
    assert "your choice" in lower or "ai_choose" in lower or "writer chooses" in lower or "based on the premise" in lower


def test_freeform_prompt_instructs_writer_to_stick_to_premise_cast():
    """Bug 1: the freeform prompt must instruct the LLM to NOT invent
    side characters that aren't in the user's premise."""
    from pipeline.script_freeform import build_freeform_prompt, FreeformControls
    from pipeline.types import ThemeSeed
    p = build_freeform_prompt(
        ThemeSeed(theme="folkloric", premise="قصة خيانة فراولة للموزة"),
        FreeformControls(),
    )
    p_lower = p.lower()
    # At least one of these instructional phrases must appear
    assert (
        "do not invent" in p_lower
        or "stick to" in p_lower
        or "only use characters" in p_lower
        or "do not add" in p_lower
        or "ممنوع اختراع" in p
        or "التزم" in p
    ), "prompt should instruct LLM not to invent extra characters"


# ---------------------------------------------------------------------------
# PB-2: freeform prompt asks for character_descriptions
# ---------------------------------------------------------------------------

def test_freeform_prompt_asks_for_character_descriptions():
    from pipeline.script_freeform import build_freeform_prompt, FreeformControls
    from pipeline.types import ThemeSeed
    p = build_freeform_prompt(
        ThemeSeed(theme="urban", premise="x"),
        FreeformControls(),
    )
    p_lower = p.lower()
    assert "character_descriptions" in p_lower


def test_freeform_prompt_asks_for_voice_in_character_descriptions():
    """Each character_description must include a voice profile (tone/age/etc.)
    so Veo has a textual anchor for voice consistency across clips."""
    from pipeline.script_freeform import build_freeform_prompt, FreeformControls
    from pipeline.types import ThemeSeed
    p = build_freeform_prompt(
        ThemeSeed(theme="urban", premise="x"),
        FreeformControls(),
    )
    p_lower = p.lower()
    # Voice-related guidance present in the writer prompt
    assert "voice" in p_lower
    # Should mention what to include — tone / age / accent / pitch
    assert any(k in p_lower for k in (
        "voice tone", "voice profile", "voice characteristics",
        "tone of voice", "vocal", "pitch",
    ))
