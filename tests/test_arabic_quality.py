from __future__ import annotations

import json

from pipeline.song_lyrics import _SYSTEM_PROMPT, generate_song_script


class _CaptureLLM:
    def __init__(self):
        self.user_msg = None
        self.system = None

    def complete(self, prompt, system=None):
        if self.user_msg is None:  # capture the COMPOSE call only
            self.user_msg, self.system = prompt, system
        return json.dumps({
            "title": "ت", "lyrics": "[Verse 1]\nكَلِمَات\n[Chorus]\nلَازِمَة",
            "style_prompt": "s", "cover_prompt": "c",
            "art_direction": "", "scene_prompts": []}, ensure_ascii=False)


def test_lyrics_contract_requires_singability():
    # Tashkeel moved OUT of the compose pass (two-pass architecture) — the
    # compose contract keeps the singability rules.
    assert "rhyme" in _SYSTEM_PROMPT.lower()
    assert "VERBATIM" in _SYSTEM_PROMPT


def test_two_pass_diacritization_applies_to_composed_arabic():
    """Arabic compose → a second dedicated diacritize call whose result is
    used when the skeleton guard passes."""
    calls = []
    class _TwoPass:
        def complete(self, prompt, system=None):
            calls.append(system or "")
            if len(calls) == 1:
                return json.dumps({
                    "title": "ت", "lyrics": "[Chorus]\nيا ليل يا عين",
                    "style_prompt": "s", "cover_prompt": "c",
                    "art_direction": "", "scene_prompts": []},
                    ensure_ascii=False)
            return "[Chorus]\nيَا لَيْلُ يَا عَيْنُ"
    script = generate_song_script(llm=_TwoPass(), theme="x",
                                  custom_lyrics=None, style_hint=None,
                                  language="ar")
    assert len(calls) == 2
    assert "تشكيل" in calls[1]  # dedicated diacritize system prompt
    assert script.lyrics == "[Chorus]\nيَا لَيْلُ يَا عَيْنُ"


def test_two_pass_rejects_changed_words_keeps_composed():
    class _BadPass2:
        n = 0
        def complete(self, prompt, system=None):
            self.n += 1
            if self.n == 1:
                return json.dumps({
                    "title": "ت", "lyrics": "[Chorus]\nيا ليل يا عين",
                    "style_prompt": "s", "cover_prompt": "c",
                    "art_direction": "", "scene_prompts": []},
                    ensure_ascii=False)
            return "[Chorus]\nيَا قَمَرُ يَا عَيْنُ"  # swapped a word
    script = generate_song_script(llm=_BadPass2(), theme="x",
                                  custom_lyrics=None, style_hint=None,
                                  language="ar")
    assert script.lyrics == "[Chorus]\nيا ليل يا عين"  # composed text kept


def test_custom_lyrics_never_auto_diacritized():
    calls = []
    class _LLM:
        def complete(self, prompt, system=None):
            calls.append(1)
            return json.dumps({
                "title": "ت", "lyrics": "ignored",
                "style_prompt": "s", "cover_prompt": "c",
                "art_direction": "", "scene_prompts": []}, ensure_ascii=False)
    script = generate_song_script(llm=_LLM(), theme="x",
                                  custom_lyrics="[Chorus]\nكلماتي أنا",
                                  style_hint=None, language="ar")
    assert len(calls) == 1  # no second pass on user text
    assert script.lyrics == "[Chorus]\nكلماتي أنا"


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


def test_skeleton_folds_hamza_and_alef_variants():
    """Diacritizers legitimately correct hamza seats (ا→أ) — the guard must
    not treat that as a changed word."""
    from pipeline.song_lyrics import letter_skeleton
    composed = "[Chorus]\nانت الحبيب ومعك الامان يا قلبي"
    diacritized = "[Chorus]\nأَنْتَ الحَبِيبُ وَمَعَكَ الأَمَانُ يَا قَلْبِي"
    assert letter_skeleton(composed) == letter_skeleton(diacritized)


def test_diacritize_cuts_model_preamble():
    from pipeline.song_lyrics import diacritize_lyrics
    class _Chatty:
        def complete(self, prompt, system=None):
            return "إليك الكلمات مشكّلة:\n[Chorus]\nيَا لَيْلُ يَا عَيْنُ"
    out = diacritize_lyrics(_Chatty(), "[Chorus]\nيا ليل يا عين")
    assert out == "[Chorus]\nيَا لَيْلُ يَا عَيْنُ"


def test_contract_bans_childish_register():
    from pipeline.song_lyrics import _SYSTEM_PROMPT
    assert "NEVER childish" in _SYSTEM_PROMPT
    assert "عمق شعري" in _SYSTEM_PROMPT
