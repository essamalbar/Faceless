"""A&R quality pipeline: given Suno takes, return the best one + why.

Three stages: screen_takes (free signal defect prune) → judge_takes (Gemini
audio A&R) → pick_best. Every stage degrades gracefully; nothing here ever
raises into the worker (a quality pipeline must not turn a paid render into a
hard failure). See docs/superpowers/specs/2026-08-03-song-ar-quality-pipeline-design.md.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# --- Stage 1: signal defect prune -------------------------------------------
_MIN_DURATION_FRAC = 0.6   # reject takes < 60% of the batch median duration
_MAX_CLIP_RATIO = 0.01     # > 1% full-scale samples = clipping
_MAX_SILENCE_RATIO = 0.5   # > 50% of frames below -40 dBFS = mostly silent


@dataclass(frozen=True)
class ScreenedTake:
    path: Path
    duration_s: float
    clip_ratio: float
    silence_ratio: float
    passed: bool
    reject_reason: str = ""


def _median(xs: list[float]) -> float:
    vals = sorted(x for x in xs if x is not None)
    if not vals:
        return 0.0
    n = len(vals)
    return vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2


def _measure(path: Path) -> tuple[float, float, float]:
    """(duration_s, clip_ratio, silence_ratio) via librosa. Injectable for tests."""
    import librosa
    import numpy as np
    y, sr = librosa.load(str(path), sr=None, mono=True)
    if not len(y) or not sr:
        return 0.0, 1.0, 1.0
    duration = len(y) / sr
    clip_ratio = float(np.mean(np.abs(y) >= 0.99))
    rms = librosa.feature.rms(y=y)[0]
    silence_ratio = float(np.mean(rms < 10 ** (-40 / 20)))
    return duration, clip_ratio, silence_ratio


def screen_takes(take_paths, *, measure=_measure) -> list[ScreenedTake]:
    raw = []
    for p in take_paths:
        p = Path(p)
        try:
            dur, clip, sil = measure(p)
        except Exception:
            dur, clip, sil = 0.0, 1.0, 1.0
        raw.append((p, dur, clip, sil))

    median_dur = _median([d for _, d, _, _ in raw])
    screened: list[ScreenedTake] = []
    for p, dur, clip, sil in raw:
        reason = ""
        if median_dur and dur < _MIN_DURATION_FRAC * median_dur:
            reason = "truncated"
        elif clip > _MAX_CLIP_RATIO:
            reason = "clipping"
        elif sil > _MAX_SILENCE_RATIO:
            reason = "mostly-silent"
        screened.append(ScreenedTake(p, dur, clip, sil, not reason, reason))

    # Never drop the whole batch: if everything failed, keep them all so the
    # judge / signal fallback can still pick the least-bad.
    if screened and not any(s.passed for s in screened):
        screened = [
            ScreenedTake(s.path, s.duration_s, s.clip_ratio, s.silence_ratio,
                         True, "all-failed-keep")
            for s in screened
        ]
    return screened
