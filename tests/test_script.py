"""Shared parsing helper tests for pipeline/script.py.

The Sunstoriz writer machinery (build_writer_prompt, generate_script_first_pass,
generate_shorts_script, critique_pass, _cosine, check_and_record_uniqueness, etc.)
was deleted in PA-3. Tests for those functions have been removed here.

Only _parse_shorts_script_json (and its helpers _strip_code_fence /
_normalize_music_mood, exercised transitively) remain, because
pipeline/script_freeform.py imports them.
"""
from __future__ import annotations

import pytest

from pipeline.types import ThemeSeed


def test_parser_accepts_narrator_speaker():
    """Cinematic mode: voice-over / off-screen narration is allowed."""
    from pipeline.script import _parse_shorts_script_json
    raw = '''{
      "title":"t","theme":"folkloric","global_setting":"g","music_mood":"dread",
      "target_duration_s":16,
      "beats":[
        {"arabic":"كلام الراوي عن المدينة","english_motion":"wide aerial shot of the city at dusk","speaker":"narrator","clip_duration_s":8,"character_name":""},
        {"arabic":"شو هاد","english_motion":"close-up on khaled","speaker":"son","clip_duration_s":8,"character_name":"خالد"}
      ]
    }'''
    script = _parse_shorts_script_json(raw, ThemeSeed(theme="folkloric", premise="x"))
    assert script.beats[0].speaker == "narrator"
    assert script.beats[1].speaker == "son"


def test_parser_accepts_silent_action_beat():
    """Empty arabic is allowed for silent action / atmospheric beats. The
    english_motion must still be present (the visual prompt drives Veo)."""
    from pipeline.script import _parse_shorts_script_json
    raw = '''{
      "title":"t","theme":"folkloric","global_setting":"g","music_mood":"dread",
      "target_duration_s":16,
      "beats":[
        {"arabic":"","english_motion":"slow push-in on an empty kitchen at dawn, dust in the light","speaker":"narrator","clip_duration_s":7,"character_name":""},
        {"arabic":"خالد عم بفكر","english_motion":"medium close on khaled looking out the window","speaker":"son","clip_duration_s":8,"character_name":"خالد"}
      ]
    }'''
    script = _parse_shorts_script_json(raw, ThemeSeed(theme="folkloric", premise="x"))
    assert script.beats[0].arabic == ""
    assert script.beats[0].english_motion.startswith("slow push-in")


def test_parser_still_rejects_missing_english_motion():
    """The english_motion (visual prompt for Veo) is still required — empty
    arabic is fine but a beat with no visual direction is malformed."""
    from pipeline.script import _parse_shorts_script_json
    raw = '''{
      "title":"t","theme":"folkloric","global_setting":"g","music_mood":"dread",
      "target_duration_s":8,
      "beats":[{"arabic":"x","english_motion":"","speaker":"mother","clip_duration_s":8}]
    }'''
    with pytest.raises(ValueError):
        _parse_shorts_script_json(raw, ThemeSeed(theme="folkloric", premise="x"))


def test_parser_accepts_unknown_speaker_alien():
    """PA-1: A speaker like 'alien' is now valid — free-form speaker enum."""
    from pipeline.script import _parse_shorts_script_json
    raw = '''{
      "title":"t","theme":"folkloric","global_setting":"g","music_mood":"dread",
      "target_duration_s":8,
      "beats":[{"arabic":"x","english_motion":"y","speaker":"alien","clip_duration_s":8,"character_name":"زيد"}]
    }'''
    script = _parse_shorts_script_json(raw, ThemeSeed(theme="folkloric", premise="x"))
    assert script.beats[0].speaker == "alien"


def test_shorts_parser_reads_character_name():
    """When the writer returns character_name on each beat, it appears on Beat."""
    from pipeline.script import _parse_shorts_script_json
    raw = '''{
      "title": "t", "theme": "folkloric",
      "global_setting": "g", "music_mood": "dread",
      "target_duration_s": 16,
      "beats": [
        {"arabic":"x","english_motion":"y","clip_duration_s":8,"speaker":"mother","character_name":"أم خالد"},
        {"arabic":"x","english_motion":"y","clip_duration_s":8,"speaker":"son","character_name":"خالد"}
      ]
    }'''
    seed = ThemeSeed(theme="folkloric", premise="x")
    script = _parse_shorts_script_json(raw, seed)
    assert script.beats[0].character_name == "أم خالد"
    assert script.beats[1].character_name == "خالد"


def test_shorts_parser_legacy_omits_character_name():
    """Legacy LLM responses without character_name still parse — default ''."""
    from pipeline.script import _parse_shorts_script_json
    raw = '''{
      "title": "t", "theme": "folkloric",
      "global_setting": "g", "music_mood": "dread",
      "target_duration_s": 8,
      "beats": [{"arabic":"x","english_motion":"y","clip_duration_s":8,"speaker":"mother"}]
    }'''
    script = _parse_shorts_script_json(raw, ThemeSeed(theme="folkloric", premise="x"))
    assert script.beats[0].character_name == ""


# ===========================================================================
# PA-1: free-form speaker enum in _parse_shorts_script_json
# ===========================================================================

def test_parser_accepts_any_speaker_string():
    """Loosened enum: speaker can be 'warrior', 'wizard', 'pet', etc."""
    from pipeline.script import _parse_shorts_script_json
    raw = '''{
      "title":"t","theme":"folkloric","global_setting":"g","music_mood":"dread",
      "target_duration_s":16,
      "beats":[
        {"arabic":"x","english_motion":"y","clip_duration_s":8,"speaker":"warrior","character_name":"خالد"},
        {"arabic":"x","english_motion":"y","clip_duration_s":8,"speaker":"wizard","character_name":"عمر"}
      ]
    }'''
    script = _parse_shorts_script_json(raw, ThemeSeed(theme="folkloric", premise="x"))
    assert script.beats[0].speaker == "warrior"
    assert script.beats[1].speaker == "wizard"


def test_parser_still_rejects_empty_speaker():
    """Even loosened, empty speaker is invalid (would make the beat
    untraceable)."""
    from pipeline.script import _parse_shorts_script_json
    raw = '''{
      "title":"t","theme":"folkloric","global_setting":"g","music_mood":"dread",
      "target_duration_s":8,
      "beats":[{"arabic":"x","english_motion":"y","clip_duration_s":8,"speaker":""}]
    }'''
    with pytest.raises(ValueError):
        _parse_shorts_script_json(raw, ThemeSeed(theme="folkloric", premise="x"))


# ---------------------------------------------------------------------------
# PB-2: _parse_shorts_script_json reads character_descriptions
# ---------------------------------------------------------------------------

def test_parser_reads_character_descriptions():
    from pipeline.script import _parse_shorts_script_json
    raw = '''{
      "title":"t","theme":"folkloric","global_setting":"g","music_mood":"dread",
      "target_duration_s":8,
      "character_descriptions": {
        "خالد": "young man mid-20s, slim, short black hair, white thobe",
        "أم خالد": "woman mid-50s, black hijab, dark grey dress"
      },
      "beats":[{"arabic":"x","english_motion":"y","clip_duration_s":8,"speaker":"son","character_name":"خالد"}]
    }'''
    script = _parse_shorts_script_json(raw, ThemeSeed(theme="folkloric", premise="x"))
    assert script.character_descriptions["خالد"].startswith("young man")
    assert "أم خالد" in script.character_descriptions
