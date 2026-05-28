from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from pipeline.song_lyrics import (
    SongScript,
    generate_song_script,
    validate_section_tags,
)


def _stub_llm(json_response: str):
    """Build a fake LLM client whose .complete() returns the given string."""
    llm = MagicMock()
    llm.complete = MagicMock(return_value=json_response)
    return llm


def test_validate_section_tags_accepts_full_structure():
    lyrics = """[Verse 1]
line a
line b

[Chorus]
hook 1
hook 2"""
    validate_section_tags(lyrics)


def test_validate_section_tags_rejects_flat_lyrics():
    with pytest.raises(ValueError, match="missing Suno section tags"):
        validate_section_tags("just a wall of text\nwithout brackets")


def test_validate_section_tags_requires_chorus():
    with pytest.raises(ValueError, match="missing \\[Chorus\\]"):
        validate_section_tags("[Verse 1]\nlines only")


def test_generate_song_script_from_theme_only():
    llm_payload = """{
        "title": "تحت حراسة القمر",
        "lyrics": "[Verse 1]\\nا\\n[Chorus]\\nب",
        "style_prompt": "Arabic pop ballad, slow tempo 72 BPM, oud + cinematic strings + light percussion, male vocal with subtle vibrato, modern 2020s production, melancholic minor key",
        "cover_prompt": "young Arab man under moonlight, fine art photography"
    }"""
    llm = _stub_llm(llm_payload)
    script = generate_song_script(
        llm=llm,
        theme="sad Arabic ballad about the moon",
        custom_lyrics=None,
        style_hint=None,
        language="ar",
    )
    assert isinstance(script, SongScript)
    assert script.title == "تحت حراسة القمر"
    assert "[Verse 1]" in script.lyrics
    assert "[Chorus]" in script.lyrics
    assert "BPM" in script.style_prompt
    assert script.language == "ar"


def test_generate_song_script_honors_user_lyrics_passthrough():
    """When custom_lyrics is provided, the LLM must NOT rewrite them."""
    user_lyrics = "[Verse 1]\nmy own words\n[Chorus]\nstay verbatim"
    llm_payload = """{
        "title": "Mine",
        "lyrics": "WRONG — LLM tried to rewrite",
        "style_prompt": "indie folk, 80 BPM, acoustic guitar + light percussion, female vocal soft, 2010s production, hopeful major key",
        "cover_prompt": "a quiet morning landscape"
    }"""
    llm = _stub_llm(llm_payload)
    script = generate_song_script(
        llm=llm,
        theme="my own song",
        custom_lyrics=user_lyrics,
        style_hint=None,
        language="en",
    )
    assert script.lyrics == user_lyrics


def test_generate_song_script_merges_user_style_hint():
    """When style_hint is provided, the LLM must extend it, not replace."""
    llm_payload = """{
        "title": "Test",
        "lyrics": "[Verse 1]\\na\\n[Chorus]\\nb",
        "style_prompt": "rock, 120 BPM, electric guitar + drums, male vocal raspy, 1990s production, energetic minor key, violin",
        "cover_prompt": "a stage at dusk"
    }"""
    llm = _stub_llm(llm_payload)
    script = generate_song_script(
        llm=llm,
        theme="energetic rock song",
        custom_lyrics=None,
        style_hint="must include violin",
        language="en",
    )
    assert "violin" in script.style_prompt


def test_generate_song_script_validates_lyrics_have_section_tags():
    """If the LLM ignores the contract, we catch it before submitting to Suno."""
    bad_payload = """{
        "title": "Broken",
        "lyrics": "no section tags at all just words",
        "style_prompt": "anything",
        "cover_prompt": "anything"
    }"""
    llm = _stub_llm(bad_payload)
    with pytest.raises(ValueError, match="missing Suno section tags|missing \\[Chorus\\]"):
        generate_song_script(
            llm=llm, theme="x", custom_lyrics=None, style_hint=None, language="ar",
        )
