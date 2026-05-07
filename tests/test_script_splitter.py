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


def test_splitter_reads_character_name_from_llm():
    """When the LLM returns character_name, the splitter populates it on ParsedBeat."""
    raw = "أنا قاعدة بالمطبخ. ابني نسي."
    response = '''{"beats":[
        {"arabic":"أنا قاعدة بالمطبخ.","english_motion":"x","speaker":"mother","clip_duration_s":7,"character_name":"أم خالد"},
        {"arabic":"ابني نسي.","english_motion":"y","speaker":"son","clip_duration_s":7,"character_name":"خالد"}
    ]}'''
    llm = _StubLLM(response)
    beats = split_prose_into_beats(llm, raw, target_beats=2, per_beat_seconds=7)
    assert beats[0].character_name == "أم خالد"
    assert beats[1].character_name == "خالد"


def test_splitter_legacy_omits_character_name():
    """Legacy LLM responses without character_name still parse with default ''."""
    raw = "أنا قاعدة بالمطبخ. ابني نسي."
    response = '''{"beats":[
        {"arabic":"أنا قاعدة بالمطبخ.","english_motion":"x","speaker":"mother","clip_duration_s":7},
        {"arabic":"ابني نسي.","english_motion":"y","speaker":"son","clip_duration_s":7}
    ]}'''
    llm = _StubLLM(response)
    beats = split_prose_into_beats(llm, raw, target_beats=2, per_beat_seconds=7)
    assert beats[0].character_name == ""


def test_splitter_prompt_mentions_character_name():
    """The splitter LLM prompt instructs it to pick Arabic character names."""
    from pipeline.script_splitter import _PROMPT_TEMPLATE
    assert "character_name" in _PROMPT_TEMPLATE


# ===========================================================================
# PA-1: free-form speaker enum in script_splitter
# ===========================================================================

def test_splitter_accepts_any_speaker_string():
    from pipeline.script_splitter import split_prose_into_beats
    raw = "أنا خالد، أنا محارب. سأنقذ المدينة."
    response = '''{"beats":[
        {"arabic":"أنا خالد، أنا محارب.","english_motion":"x","speaker":"warrior","clip_duration_s":7,"character_name":"خالد"},
        {"arabic":"سأنقذ المدينة.","english_motion":"y","speaker":"warrior","clip_duration_s":7,"character_name":"خالد"}
    ]}'''
    class _Stub:
        def complete(self, p, system=""): return response
    beats = split_prose_into_beats(_Stub(), raw, target_beats=2, per_beat_seconds=7)
    assert beats[0].speaker == "warrior"  # not coerced to "mother"
