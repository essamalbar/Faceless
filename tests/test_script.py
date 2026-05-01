"""Script writer tests — first pass only."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline.script import build_writer_prompt, generate_script_first_pass
from pipeline.types import Script, ThemeSeed


def test_writer_prompt_includes_seed_and_constraints():
    seed = ThemeSeed(theme="folkloric", premise="بئر قديم")
    p = build_writer_prompt(seed, target_words=2200, tolerance=200)
    assert "بئر قديم" in p
    assert "folkloric" in p
    assert "2200" in p or "2,200" in p
    assert "ضمير المتكلم" in p
    assert "MSA" in p or "الفصحى" in p


def test_first_pass_parses_valid_json(fake_gemini):
    seed = ThemeSeed(theme="folkloric", premise="بئر قديم")
    fake_gemini.when(lambda p: "بئر قديم" in p, json.dumps({
        "title": "بئر",
        "theme": "folkloric",
        "global_setting": "مدينة فجر, شتاء",
        "music_mood": "dread",
        "hook": "افتتاح",
        "story": "نص" * 1100,
        "word_count": 2200,
    }, ensure_ascii=False))
    s = generate_script_first_pass(fake_gemini, seed, target_words=2200, tolerance=200)
    assert isinstance(s, Script)
    assert s.title == "بئر"


def test_first_pass_overrides_theme_to_match_seed(fake_gemini):
    """If Gemini returns a different theme tag, we trust the seed."""
    seed = ThemeSeed(theme="folkloric", premise="بئر")
    fake_gemini.when(lambda p: True, json.dumps({
        "title": "x", "theme": "domestic",  # WRONG theme returned
        "global_setting": "x", "music_mood": "drone",
        "hook": "x", "story": "x" * 100, "word_count": 100,
    }, ensure_ascii=False))
    s = generate_script_first_pass(fake_gemini, seed, target_words=100, tolerance=10)
    assert s.theme == "folkloric"  # corrected to match seed


def test_first_pass_strips_markdown_code_fence(fake_gemini):
    """Gemini sometimes wraps JSON in ```json ... ``` fences."""
    seed = ThemeSeed(theme="folkloric", premise="x")
    payload = json.dumps({
        "title": "x", "theme": "folkloric", "global_setting": "x",
        "music_mood": "drone", "hook": "x", "story": "y" * 100, "word_count": 100,
    }, ensure_ascii=False)
    fake_gemini.when(lambda p: True, f"```json\n{payload}\n```")
    s = generate_script_first_pass(fake_gemini, seed, target_words=100, tolerance=10)
    assert s.title == "x"


def test_first_pass_raises_on_invalid_json(fake_gemini):
    seed = ThemeSeed(theme="folkloric", premise="x")
    fake_gemini.when(lambda p: True, "this is not json")
    with pytest.raises(ValueError):
        generate_script_first_pass(fake_gemini, seed, target_words=100, tolerance=10)
