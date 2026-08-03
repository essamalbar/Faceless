from __future__ import annotations

from pathlib import Path

from pipeline.song_ar import ScreenedTake, screen_takes


def _fake_measure(metrics):
    # metrics: {name: (duration, clip_ratio, silence_ratio)}
    def _m(path: Path):
        return metrics[path.name]
    return _m


def test_screen_rejects_truncated_clipped_silent_keeps_valid():
    paths = [Path(f"take_{i}.mp3") for i in range(1, 5)]
    metrics = {
        "take_1.mp3": (60.0, 0.0, 0.1),   # valid
        "take_2.mp3": (20.0, 0.0, 0.1),   # truncated (< 60% of 60s median)
        "take_3.mp3": (58.0, 0.05, 0.1),  # clipping
        "take_4.mp3": (59.0, 0.0, 0.9),   # mostly silent
    }
    out = screen_takes(paths, measure=_fake_measure(metrics))
    by = {s.path.name: s for s in out}
    assert by["take_1.mp3"].passed is True
    assert by["take_2.mp3"].reject_reason == "truncated"
    assert by["take_3.mp3"].reject_reason == "clipping"
    assert by["take_4.mp3"].reject_reason == "mostly-silent"


def test_screen_reject_precedence_truncated_wins():
    # A take violating all three checks must be labeled by the FIRST failure
    # (truncated) — locks the if/elif order against silent inversion.
    paths = [Path("take_1.mp3"), Path("take_2.mp3")]
    metrics = {
        "take_1.mp3": (60.0, 0.0, 0.1),   # valid → non-zero median
        "take_2.mp3": (10.0, 0.5, 0.9),   # truncated AND clipping AND silent
    }
    out = {s.path.name: s for s in screen_takes(paths, measure=_fake_measure(metrics))}
    assert out["take_2.mp3"].reject_reason == "truncated"


def test_screen_keeps_all_when_every_take_fails():
    paths = [Path("take_1.mp3"), Path("take_2.mp3")]
    metrics = {"take_1.mp3": (0.0, 1.0, 1.0), "take_2.mp3": (0.0, 1.0, 1.0)}
    out = screen_takes(paths, measure=_fake_measure(metrics))
    assert all(s.passed for s in out)  # never drop the whole batch


def test_screen_measure_exception_marks_take_failed_not_crash():
    def _boom(path):
        raise RuntimeError("decode error")
    out = screen_takes([Path("take_1.mp3")], measure=_boom)
    # single take, measure failed → treated as junk, but keep-all rescues it
    assert len(out) == 1 and out[0].passed is True


import json

from pipeline.song_ar import (
    JudgedTake, Verdict, judge_takes, pick_best, _composite,
)


class _FakeJudge:
    def __init__(self, response=None, raises=False):
        self._response = response
        self._raises = raises

    def judge_audio(self, audio_path, system, user):
        if self._raises:
            raise RuntimeError("gemini down")
        return self._response


_GOOD = json.dumps({"vocal_realism": 90, "artifacts": 80, "pronunciation": 85,
                    "production": 70, "style_fit": 75, "reason": "clean vocal",
                    "deal_breakers": []})


def _screened(name="take_1.mp3", passed=True):
    return ScreenedTake(Path(name), 60.0, 0.0, 0.1, passed, "")


def test_composite_weighted_and_dealbreaker_cap():
    sub = {"vocal_realism": 100, "artifacts": 100, "pronunciation": 100,
           "production": 100, "style_fit": 100}
    assert _composite(sub, []) == 100.0
    assert _composite(sub, ["garbled words"]) == 40.0  # hard-capped


def test_judge_takes_uses_gemini_when_valid():
    judged = judge_takes(_FakeJudge(_GOOD), [_screened()],
                         style_prompt="pop", language="ar")
    assert judged[0].source == "gemini"
    assert judged[0].composite > 70


def test_judge_takes_signal_fallback_on_error():
    judged = judge_takes(_FakeJudge(raises=True), [_screened()],
                         style_prompt="pop", language="ar")
    assert judged[0].source == "signal-fallback"


def test_judge_takes_skips_failed_screens():
    judged = judge_takes(_FakeJudge(_GOOD),
                         [_screened("a.mp3", True), _screened("b.mp3", False)],
                         style_prompt="pop", language="ar")
    assert [j.path.name for j in judged] == ["a.mp3"]


def test_pick_best_picks_highest_and_sets_clears_bar():
    judged = [JudgedTake(Path("a.mp3"), 55.0, {}, "", "gemini"),
              JudgedTake(Path("b.mp3"), 82.0, {}, "", "gemini")]
    v = pick_best(judged, quality_bar=70)
    assert isinstance(v, Verdict)
    assert v.path.name == "b.mp3" and v.clears_bar is True
    v2 = pick_best([judged[0]], quality_bar=70)
    assert v2.clears_bar is False


def test_pick_best_empty_raises_clear_error():
    import pytest
    with pytest.raises(ValueError):
        pick_best([], quality_bar=70)


def test_composite_clamps_out_of_range_subscores():
    sub = {k: 150 for k in ("vocal_realism", "artifacts", "pronunciation",
                            "production", "style_fit")}
    assert _composite(sub, []) == 100.0  # clamped to 100, not 150


def test_judge_takes_missing_all_score_keys_falls_back():
    bad = json.dumps({"foo": "bar"})  # valid JSON, none of the score keys
    judged = judge_takes(_FakeJudge(bad), [_screened()],
                         style_prompt="pop", language="ar")
    assert judged[0].source == "signal-fallback"
