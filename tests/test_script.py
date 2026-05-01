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


def test_critique_pass_revises_when_flagged(fake_gemini):
    seed = ThemeSeed(theme="folkloric", premise="x")
    draft = Script(
        title="t", theme="folkloric", global_setting="x",
        music_mood="dread", hook="weak", story="y" * 100, word_count=100,
    )
    revised_payload = json.dumps({
        "title": "t-revised", "theme": "folkloric", "global_setting": "x",
        "music_mood": "dread", "hook": "stronger hook", "story": "z" * 100,
        "word_count": 100,
    }, ensure_ascii=False)
    fake_gemini.when(lambda p: "نقد" in p or "critique" in p.lower(), revised_payload)

    from pipeline.script import critique_pass
    out = critique_pass(fake_gemini, seed, draft)
    assert out.title == "t-revised"
    assert out.hook == "stronger hook"


def test_generate_script_full_pipeline_with_critique(fake_gemini):
    """End-to-end: first pass + critique pass."""
    seed = ThemeSeed(theme="folkloric", premise="بئر")
    first = json.dumps({
        "title": "v1", "theme": "folkloric", "global_setting": "x",
        "music_mood": "dread", "hook": "h", "story": "s" * 100, "word_count": 100,
    }, ensure_ascii=False)
    second = json.dumps({
        "title": "v2", "theme": "folkloric", "global_setting": "x",
        "music_mood": "dread", "hook": "h2", "story": "s" * 100, "word_count": 100,
    }, ensure_ascii=False)
    # First call returns first; second (critique) returns second.
    seq = [first, second]
    fake_gemini.when(lambda p: bool(seq), "")  # placeholder; we override below

    # Replace responses list with a sequencer
    fake_gemini._responses.clear()
    def sequencer(prompt: str):
        return seq.pop(0) if seq else None
    fake_gemini._responses.append(sequencer)

    from pipeline.script import generate_script
    out = generate_script(fake_gemini, seed, target_words=100, tolerance=10, enable_critique=True)
    assert out.title == "v2"


def test_generate_script_skips_critique_when_disabled(fake_gemini):
    seed = ThemeSeed(theme="folkloric", premise="بئر")
    fake_gemini.when(lambda p: True, json.dumps({
        "title": "v1", "theme": "folkloric", "global_setting": "x",
        "music_mood": "dread", "hook": "h", "story": "s" * 100, "word_count": 100,
    }, ensure_ascii=False))
    from pipeline.script import generate_script
    out = generate_script(fake_gemini, seed, target_words=100, tolerance=10, enable_critique=False)
    assert out.title == "v1"
    assert len(fake_gemini.complete_calls) == 1  # only first pass
