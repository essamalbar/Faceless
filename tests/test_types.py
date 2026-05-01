"""Round-trip serialization tests for shared dataclasses."""
from __future__ import annotations

import json

from pipeline.types import Script, Shot, ThemeSeed, WordTiming


def test_themeseed_roundtrip():
    s = ThemeSeed(theme="folkloric", premise="بئر قديم في قرية مهجورة")
    assert s.to_dict() == {"theme": "folkloric", "premise": "بئر قديم في قرية مهجورة"}
    assert ThemeSeed.from_dict(s.to_dict()) == s


def test_script_roundtrip():
    s = Script(
        title="صوت الجار",
        theme="domestic",
        global_setting="apartment, urban Saudi Arabia, winter night",
        music_mood="dread",
        hook="الفقرة الافتتاحية",
        story="النص الكامل",
        word_count=2187,
    )
    data = s.to_dict()
    assert json.dumps(data, ensure_ascii=False)  # serializable
    assert Script.from_dict(data) == s


def test_shot_roundtrip():
    s = Shot(
        index=1,
        start_ms=0,
        end_ms=18420,
        arabic_text="كنت أسير...",
        english_prompt="lone figure walking...",
        negative_prompt="text, watermark",
        seed=1729384721,
    )
    assert Shot.from_dict(s.to_dict()) == s


def test_wordtiming_roundtrip():
    w = WordTiming(word="كنت", offset_ms=0, duration_ms=480)
    assert WordTiming.from_dict(w.to_dict()) == w


def test_script_invalid_mood_rejected():
    import pytest
    with pytest.raises(ValueError):
        Script(
            title="t", theme="domestic", global_setting="x",
            music_mood="not-a-mood", hook="h", story="s", word_count=100,
        )
