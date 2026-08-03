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
