from __future__ import annotations

import json

from pipeline.song_lyrics import generate_song_script


class _FakeLLM:
    def __init__(self, payload):
        self._payload = payload
    def complete(self, user_msg, system):
        return json.dumps(self._payload, ensure_ascii=False)


_GOOD = {
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
        llm=_FakeLLM(_GOOD), theme="loneliness",
        custom_lyrics=None, style_hint=None, language="ar",
    )
    assert s.art_direction.startswith("moonlit")
    assert len(s.scene_prompts) == 3
    assert s.scene_prompts[0] == "a lone figure on a moonlit rooftop"


def test_song_script_missing_scene_fields_default_empty():
    payload = dict(_GOOD)
    del payload["art_direction"]
    del payload["scene_prompts"]
    s = generate_song_script(
        llm=_FakeLLM(payload), theme="x",
        custom_lyrics=None, style_hint=None, language="ar",
    )
    assert s.art_direction == ""
    assert s.scene_prompts == []
