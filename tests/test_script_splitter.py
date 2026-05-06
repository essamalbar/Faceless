from __future__ import annotations

import pytest
from pipeline.script_splitter import split_prose_into_beats, _verbatim_match


class _StubLLM:
    """Mimics the .complete() interface of the LLM router used elsewhere."""
    def __init__(self, response: str):
        self.response = response
        self.calls = 0
    def complete(self, prompt: str, system: str = "") -> str:
        self.calls += 1
        return self.response


def test_splits_prose_into_n_beats_verbatim():
    raw = "أنا قاعدة بالمطبخ. ابني نسي. قلبي مكسور."
    llm_response = '''{"beats":[
        {"arabic":"أنا قاعدة بالمطبخ.","english_motion":"mother in kitchen","speaker":"mother","clip_duration_s":7.0},
        {"arabic":"ابني نسي.","english_motion":"son walks away","speaker":"son","clip_duration_s":7.0},
        {"arabic":"قلبي مكسور.","english_motion":"close-up tears","speaker":"mother","clip_duration_s":7.0}
    ]}'''
    llm = _StubLLM(llm_response)
    beats = split_prose_into_beats(llm, raw, target_beats=3, per_beat_seconds=7)
    assert len(beats) == 3
    assert beats[0].arabic == "أنا قاعدة بالمطبخ."
    assert beats[1].speaker == "son"


def test_verbatim_guard_rejects_rewritten_arabic():
    """If the LLM 'improves' the text, the verbatim check must reject and retry."""
    raw = "أنا قاعدة بالمطبخ."
    bad = '''{"beats":[{"arabic":"أنا قاعدة في المطبخ الحزين","english_motion":"x","speaker":"mother","clip_duration_s":8}]}'''
    good = '''{"beats":[{"arabic":"أنا قاعدة بالمطبخ.","english_motion":"x","speaker":"mother","clip_duration_s":8}]}'''
    class _RetryLLM:
        def __init__(self):
            self.calls = 0
        def complete(self, prompt, system=""):
            self.calls += 1
            return bad if self.calls == 1 else good
    llm = _RetryLLM()
    beats = split_prose_into_beats(llm, raw, target_beats=1, per_beat_seconds=8)
    assert llm.calls == 2  # first rejected, second accepted
    assert beats[0].arabic == "أنا قاعدة بالمطبخ."


def test_naive_fallback_on_persistent_verbatim_failure():
    """If the LLM keeps rewriting, fall back to sentence-split — must still
    produce >1 beats."""
    raw = "جملة أولى. جملة ثانية. جملة ثالثة."
    bad = '''{"beats":[{"arabic":"شيء مختلف","english_motion":"x","speaker":"mother","clip_duration_s":8}]}'''
    llm = _StubLLM(bad)
    beats = split_prose_into_beats(llm, raw, target_beats=3, per_beat_seconds=8)
    assert len(beats) >= 2  # naive splitter produces multiple beats


def test_verbatim_match_helper_tolerates_whitespace():
    assert _verbatim_match("أ ب ج", "أب ج") is True
    assert _verbatim_match("أ ب ج", "أ ب  ج\n") is True
    assert _verbatim_match("أ ب ج", "أ ب د") is False
