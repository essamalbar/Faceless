from __future__ import annotations

import json

from pipeline.song_lyrics import _SYSTEM_PROMPT, generate_song_script


class _CaptureLLM:
    def __init__(self):
        self.user_msg = None
        self.system = None

    def complete(self, prompt, system=None):
        self.user_msg, self.system = prompt, system
        return json.dumps({
            "title": "ت", "lyrics": "[Verse 1]\nكَلِمَات\n[Chorus]\nلَازِمَة",
            "style_prompt": "s", "cover_prompt": "c",
            "art_direction": "", "scene_prompts": []}, ensure_ascii=False)


def test_lyrics_contract_requires_tashkeel_and_singability():
    assert "FULLY DIACRITIZED" in _SYSTEM_PROMPT
    assert "تشكيل كامل" in _SYSTEM_PROMPT
    assert "rhyme" in _SYSTEM_PROMPT.lower()
    assert "VERBATIM" in _SYSTEM_PROMPT


def test_dialect_lands_in_user_msg():
    llm = _CaptureLLM()
    generate_song_script(llm=llm, theme="حب", custom_lyrics=None,
                         style_hint=None, language="ar", dialect="egyptian")
    assert "Egyptian Arabic" in llm.user_msg

    llm2 = _CaptureLLM()
    generate_song_script(llm=llm2, theme="حب", custom_lyrics=None,
                         style_hint=None, language="ar", dialect=None)
    assert "Dialect" not in llm2.user_msg


def test_unknown_dialect_ignored():
    llm = _CaptureLLM()
    generate_song_script(llm=llm, theme="x", custom_lyrics=None,
                         style_hint=None, language="ar", dialect="klingon")
    assert "Dialect" not in llm.user_msg


def test_letter_skeleton_ignores_harakat_only():
    from pipeline.api import _letter_skeleton
    plain = "[Chorus]\nيا ليل يا عين"
    diacritized = "[Chorus]\nيَا لَيْلُ يَا عَيْنُ"
    assert _letter_skeleton(plain) == _letter_skeleton(diacritized)
    changed = "[Chorus]\nيا قمر يا عين"
    assert _letter_skeleton(plain) != _letter_skeleton(changed)
