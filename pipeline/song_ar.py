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


# --- Stage 2: Gemini audio judge --------------------------------------------
import json
import re

_WEIGHTS = {"vocal_realism": 0.35, "artifacts": 0.25, "pronunciation": 0.20,
            "production": 0.10, "style_fit": 0.10}
_DEAL_BREAKER_CAP = 40.0

_JUDGE_SYSTEM = """You are a strict professional music A&R engineer. Listen to
this AI-generated song take and judge whether it sounds like a real human
release or obviously AI. Output ONLY a JSON object, no markdown:
  {"vocal_realism":0-100, "artifacts":0-100, "pronunciation":0-100,
   "production":0-100, "style_fit":0-100, "reason":"one line",
   "deal_breakers":[]}
Scoring (higher = better, including artifacts/pronunciation):
  vocal_realism : real human voice, breath, emotion vs robotic/synthetic
  artifacts     : FEWER autotune-warble/metallic/underwater/glitch = higher
  pronunciation : clear, correct words; for Arabic judge diction strictly
  production    : mix clarity, arrangement coherence, not muddy/thin
  style_fit     : matches the intended style
deal_breakers: list any hard failures (garbled/unintelligible words, wrong
language, long dead silence). Be strict — an AI-sounding vocal is not a pass."""


@dataclass(frozen=True)
class JudgedTake:
    path: Path
    composite: float
    subscores: dict = field(default_factory=dict)
    reason: str = ""
    source: str = "gemini"   # "gemini" | "signal-fallback"


@dataclass(frozen=True)
class Verdict:
    path: Path
    composite: float
    subscores: dict
    reason: str
    source: str
    clears_bar: bool


def _parse_json_object(raw: str) -> dict:
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?|\n?```$", "", raw, flags=re.MULTILINE).strip()
    if not raw.startswith("{"):
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end > start:
            raw = raw[start:end + 1]
    data = json.loads(raw, strict=False)
    if not isinstance(data, dict):
        raise ValueError("judge output was not a JSON object")
    return data


def _composite(sub: dict, deal_breakers: list) -> float:
    score = sum(_WEIGHTS[k] * float(sub.get(k, 0) or 0) for k in _WEIGHTS)
    if deal_breakers:
        score = min(score, _DEAL_BREAKER_CAP)
    return round(score, 1)


def _signal_composite(s: ScreenedTake) -> float:
    """Fallback score when the judge can't run: penalize measured defects."""
    return round(max(0.0, 100.0 - s.clip_ratio * 100.0 - s.silence_ratio * 50.0), 1)


def _judge_user_msg(style_prompt: str, language: str, dialect: str | None) -> str:
    d = f" ({dialect})" if dialect else ""
    return f"Intended style: {style_prompt}\nLanguage: {language}{d}"


def judge_takes(audio_llm, screened, *, style_prompt, language,
                dialect=None) -> list[JudgedTake]:
    out: list[JudgedTake] = []
    for s in [s for s in screened if s.passed]:
        try:
            raw = audio_llm.judge_audio(
                s.path, _JUDGE_SYSTEM,
                _judge_user_msg(style_prompt, language, dialect))
            parsed = _parse_json_object(raw)
            sub = {k: parsed.get(k, 0) for k in _WEIGHTS}
            comp = _composite(sub, parsed.get("deal_breakers") or [])
            out.append(JudgedTake(s.path, comp, sub,
                                  str(parsed.get("reason", "")), "gemini"))
        except Exception as e:
            print(f"[song-ar] judge failed for {s.path.name} ({e}); signal fallback")
            out.append(JudgedTake(s.path, _signal_composite(s), {},
                                  "signal-only", "signal-fallback"))
    return out


def pick_best(judged, *, quality_bar: int) -> Verdict:
    best = max(judged, key=lambda j: j.composite)
    return Verdict(best.path, best.composite, best.subscores, best.reason,
                   best.source, best.composite >= quality_bar)
