"""Round-trip serialization tests for shared dataclasses."""
from __future__ import annotations

import json

from pipeline.types import Beat, Script, Shot, ThemeSeed, WordTiming


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


def test_beat_roundtrip():
    b = Beat(arabic="كنتُ وحيداً.", english_motion="lone figure walking, push-in camera")
    assert Beat.from_dict(b.to_dict()) == b


def test_script_shorts_mode_roundtrip():
    """Shorts script: beats[] populated; story/hook empty."""
    s = Script(
        title="بئر",
        theme="folkloric",
        global_setting="abandoned village, night",
        music_mood="dread",
        beats=(
            Beat(arabic="ب1", english_motion="m1"),
            Beat(arabic="ب2", english_motion="m2"),
        ),
        story_combined="ب1 ب2",
    )
    data = s.to_dict()
    json.dumps(data, ensure_ascii=False)  # serializable
    restored = Script.from_dict(data)
    assert restored == s
    assert len(restored.beats) == 2
    assert restored.beats[0].english_motion == "m1"


def test_script_long_form_mode_still_works():
    """Long-form mode: empty beats tuple, story populated."""
    s = Script(
        title="t", theme="domestic", global_setting="x",
        music_mood="dread", hook="h", story="long story", word_count=100,
    )
    assert s.beats == ()
    assert s.story == "long story"


def test_beat_carries_clip_duration():
    b = Beat(arabic="x", english_motion="m", clip_duration_s=7.5)
    assert b.clip_duration_s == 7.5
    assert Beat.from_dict(b.to_dict()) == b


def test_script_has_target_duration():
    s = Script(
        title="t", theme="folkloric", global_setting="x",
        music_mood="dread",
        beats=(Beat(arabic="a", english_motion="m", clip_duration_s=8.0),),
        story_combined="a",
        target_duration_s=64.0,
    )
    assert s.target_duration_s == 64.0
    assert Script.from_dict(s.to_dict()).target_duration_s == 64.0
