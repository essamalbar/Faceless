"""Cross-clip coherence pass — Anthropic is replaced via a stub."""
from __future__ import annotations

import json

from pipeline.coherence_pass import apply_coherence_pass
from pipeline.types import Beat, Script


class _StubLLM:
    """Implements .complete(prompt, system=None). Returns whatever was
    set as `response` on construction. Records the prompt + system for
    assertions."""

    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[dict] = []

    def complete(self, prompt: str, system: str | None = None) -> str:
        self.calls.append({"prompt": prompt, "system": system})
        return self.response


def _script(beats: list[Beat]) -> Script:
    return Script(
        title="t", theme="folkloric",
        global_setting="abandoned house, night",
        music_mood="dread",
        beats=tuple(beats),
        story_combined=" ".join(b.arabic for b in beats),
    )


def test_returns_unchanged_when_no_beats():
    script = _script([])
    llm = _StubLLM(response="{}")
    out = apply_coherence_pass(script, llm)
    assert out is script
    # Never even called the LLM — wasted spend prevented
    assert llm.calls == []


def test_rewrites_english_motion_when_llm_returns_revisions():
    script = _script([
        Beat(arabic="ج1", english_motion="man enters", clip_duration_s=8.0,
             speaker="thief", character_name="ibrahim"),
        Beat(arabic="ج2", english_motion="homeowner sees the man",
             clip_duration_s=8.0, speaker="owner", character_name="fatima"),
    ])
    llm = _StubLLM(response=json.dumps({
        "beats": [
            {"index": 1, "english_motion": "ibrahim enters the abandoned house"},
            {"index": 2, "english_motion": "fatima the owner enters and sees ibrahim"},
        ],
    }))
    out = apply_coherence_pass(script, llm)
    assert out.beats[0].english_motion == "ibrahim enters the abandoned house"
    assert out.beats[1].english_motion == "fatima the owner enters and sees ibrahim"
    # Arabic + speaker + character_name preserved (never touched)
    assert out.beats[0].arabic == "ج1"
    assert out.beats[0].character_name == "ibrahim"
    assert out.beats[1].character_name == "fatima"


def test_keeps_original_when_llm_omits_beats():
    """If the LLM forgets a beat in its response, the original is kept —
    we never silently lose content."""
    script = _script([
        Beat(arabic="ج1", english_motion="orig1", clip_duration_s=8.0),
        Beat(arabic="ج2", english_motion="orig2", clip_duration_s=8.0),
        Beat(arabic="ج3", english_motion="orig3", clip_duration_s=8.0),
    ])
    llm = _StubLLM(response=json.dumps({
        "beats": [
            {"index": 2, "english_motion": "REVISED2"},
        ],
    }))
    out = apply_coherence_pass(script, llm)
    assert out.beats[0].english_motion == "orig1"
    assert out.beats[1].english_motion == "REVISED2"
    assert out.beats[2].english_motion == "orig3"


def test_falls_back_to_original_on_invalid_json():
    """LLM returns prose, garbled markdown, etc → never blocks the render."""
    script = _script([
        Beat(arabic="ج1", english_motion="orig1", clip_duration_s=8.0),
    ])
    llm = _StubLLM(response="sorry I cannot help with that")
    out = apply_coherence_pass(script, llm)
    assert out.beats[0].english_motion == "orig1"


def test_falls_back_to_original_on_llm_exception():
    """Network error / API outage → original script returned (never raises)."""

    class _ThrowingLLM:
        def complete(self, prompt, system=None):
            raise RuntimeError("anthropic 503")

    script = _script([Beat(arabic="ج1", english_motion="orig1", clip_duration_s=8.0)])
    out = apply_coherence_pass(script, _ThrowingLLM())
    assert out.beats[0].english_motion == "orig1"


def test_idempotent_skips_when_marker_set():
    """Second call sees the v1 marker and short-circuits — saves a
    redundant Anthropic call when /resume is invoked after a crash."""
    script = _script([Beat(arabic="ج1", english_motion="orig", clip_duration_s=8.0)])
    llm = _StubLLM(response=json.dumps({
        "beats": [{"index": 1, "english_motion": "REVISED"}],
    }))
    once = apply_coherence_pass(script, llm)
    assert once.beats[0].english_motion == "REVISED"
    assert len(llm.calls) == 1

    twice = apply_coherence_pass(once, llm)
    assert twice is once  # exact same object — short-circuit hit
    assert len(llm.calls) == 1  # no second LLM call


def test_prompt_includes_setting_and_speaker_context():
    """The serialized review prompt must surface SETTING + speaker per
    beat so the LLM has enough context to detect role swaps."""
    script = _script([
        Beat(arabic="ج1", english_motion="m1", clip_duration_s=8.0,
             speaker="thief", character_name="ibrahim"),
    ])
    script = Script(
        title=script.title, theme=script.theme,
        global_setting=script.global_setting, music_mood=script.music_mood,
        beats=script.beats, story_combined=script.story_combined,
        character_descriptions={"ibrahim": "tall man with dark coat"},
    )
    llm = _StubLLM(response=json.dumps({"beats": []}))
    apply_coherence_pass(script, llm)
    sent_prompt = llm.calls[0]["prompt"]
    assert "abandoned house, night" in sent_prompt
    assert "ibrahim" in sent_prompt
    assert "tall man with dark coat" in sent_prompt


def test_ignores_blank_revisions():
    """LLM returns an empty string for a revision → original kept rather
    than overwriting with whitespace."""
    script = _script([Beat(arabic="ج1", english_motion="orig", clip_duration_s=8.0)])
    llm = _StubLLM(response=json.dumps({
        "beats": [{"index": 1, "english_motion": "   "}],
    }))
    out = apply_coherence_pass(script, llm)
    assert out.beats[0].english_motion == "orig"
