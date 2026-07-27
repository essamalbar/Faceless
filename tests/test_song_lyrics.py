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


class _FakeLLM:
    def __init__(self, payload):
        self._payload = payload
    def complete(self, user_msg, system):
        import json
        return json.dumps(self._payload, ensure_ascii=False)


_CINEMATIC_GOOD = {
    "title": "ليل",
    "lyrics": "[Verse 1]\na\nb\n\n[Chorus]\nc\nd\n",
    "style_prompt": "Arabic pop, 90 BPM, oud, male vocal, minor key",
    "cover_prompt": "a lone figure on a moonlit rooftop",
    "art_direction": "moonlit teal-and-amber palette, cinematic 35mm, melancholic",
    "scene_prompts": [
        "a lone figure on a moonlit rooftop",
        "empty city street under sodium lamps",
        "close-up of rain on a window",
    ],
}


def test_song_script_parses_art_direction_and_scenes():
    s = generate_song_script(
        llm=_FakeLLM(_CINEMATIC_GOOD), theme="loneliness",
        custom_lyrics=None, style_hint=None, language="ar",
    )
    assert s.art_direction.startswith("moonlit")
    assert len(s.scene_prompts) == 3
    assert s.scene_prompts[0] == "a lone figure on a moonlit rooftop"


def test_song_script_missing_scene_fields_default_empty():
    payload = dict(_CINEMATIC_GOOD)
    del payload["art_direction"]
    del payload["scene_prompts"]
    s = generate_song_script(
        llm=_FakeLLM(payload), theme="x",
        custom_lyrics=None, style_hint=None, language="ar",
    )
    assert s.art_direction == ""
    assert s.scene_prompts == []


class _MessyGroqLLM:
    """Mimics Groq/Llama fallback output: prose wrapper + RAW (unescaped)
    newlines inside the lyrics string — invalid strict JSON. The literal
    newlines must reach json.loads (json.dumps would escape them), so the
    string is built by hand."""
    def complete(self, user_msg, system):
        return (
            "Here is the song you asked for:\n"
            '{"title": "ليل",\n'
            ' "lyrics": "[Verse 1]\nسطر\n\n[Chorus]\nهوك",\n'
            ' "style_prompt": "Arabic pop, 90 BPM, oud, male vocal",\n'
            ' "cover_prompt": "a moonlit rooftop"}\n'
            "Hope you like it!"
        )


def test_song_script_tolerates_messy_groq_output():
    # Reproduces the prod failure: Groq fallback emitted prose + raw newlines
    # -> "Invalid control character". strict=False + {...} extraction fix it.
    s = generate_song_script(
        llm=_MessyGroqLLM(), theme="loneliness",
        custom_lyrics=None, style_hint=None, language="ar",
    )
    assert s.title == "ليل"
    assert "[Chorus]" in s.lyrics
    # style_prompt now comes from the producer pass, not the raw lyrics JSON.
    # This messy Groq style lacks the required spine language, so compose_style
    # judges it weak and ships the recipe fallback (which carries the spine).
    assert s.style_source == "fallback:recipe"
    assert "mixed and mastered" in s.style_prompt


def _routing_llm(lyrics_json: str, producer_json: str):
    """Fake LLM: returns producer JSON when it sees the producer system prompt,
    otherwise the lyrics JSON (also covers the optional diacritize call)."""
    llm = MagicMock()

    def _complete(prompt, system=None):
        if system and "music producer" in system.lower():
            return producer_json
        return lyrics_json

    llm.complete = MagicMock(side_effect=_complete)
    llm.last_tier = "anthropic"
    return llm


def test_generate_song_script_populates_producer_fields():
    lyrics_json = """{
        "title": "قمر",
        "lyrics": "[Verse 1]\\nكَلِمَات\\n[Chorus]\\nلَازِمَة",
        "style_prompt": "weak blob to be ignored",
        "cover_prompt": "moonlit portrait"
    }"""
    producer_json = """{
        "style_prompt": "Arabic pop ballad, cinematic strings and soft piano, warm male vocal, professionally mixed and mastered",
        "negative_tags": "robotic vocal, off-key"
    }"""
    llm = _routing_llm(lyrics_json, producer_json)
    script = generate_song_script(
        llm=llm, theme="أغنية حب حزينة", custom_lyrics=None,
        style_hint=None, language="ar", vocal_gender="m",
    )
    assert "mixed and mastered" in script.style_prompt
    assert script.negative_tags == "robotic vocal, off-key"
    assert script.style_source.startswith("producer:")
    assert script.writer_tier == "anthropic"
