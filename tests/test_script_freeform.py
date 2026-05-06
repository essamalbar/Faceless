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
