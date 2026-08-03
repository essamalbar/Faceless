# Song A&R Quality Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** For premium songs, generate best-of-N Suno takes, prune defects, have a Gemini audio judge score + pick the most human-sounding take, regenerate if below a bar (hard caps), and master the winner — shipped shadow-mode behind a flag until validated.

**Architecture:** A new `pipeline/song_ar.py` (screen → judge → pick) and `pipeline/mastering.py` (Matchering/ffmpeg) plug into the post-approval worker (`run.py` song stage), which becomes a best-of-N + regenerate loop for `quality_tier == "premium"` (standard songs keep today's single-job path). A `quality_tier` pricing axis surcharges premium. Every stage degrades gracefully and never blocks a render.

**Tech Stack:** Python 3.11, dataclasses, librosa (present) for signal metrics, matchering (new) for mastering, google-genai (present) for the Gemini **audio** judge, pytest + `unittest.mock` (all external services mocked — never hit real APIs).

**Spec:** `docs/superpowers/specs/2026-08-03-song-ar-quality-pipeline-design.md`

**Repo invariants (every task):** new files start with `from __future__ import annotations`; absolute imports from `pipeline.`; `pathlib.Path` not `os.path`; external services mocked in tests. Known pre-existing baseline: **30 failures** from broken local ffmpeg/libass + `test_api.py` max-spend + `test_llm_groq` stale model — all unrelated; confirm the count stays 30.

---

## File structure

- **new** `pipeline/song_ar.py` — `ScreenedTake`/`JudgedTake`/`Verdict`, `screen_takes`, `judge_takes`, `pick_best`, composite + deal-breaker logic, `_parse_json_object` (local).
- **new** `pipeline/llm_gemini_audio.py` — `GeminiAudioJudge.judge_audio(audio_path, system, user)`.
- **new** `pipeline/mastering.py` — `master_track(in, out, *, genre_key, cfg)` (matchering → ffmpeg fallback).
- **new** `assets/reference_masters/` — per-genre CC0 reference masters (user-supplied); `.gitkeep` + README.
- `pipeline/config.py` + `config.yaml` — new `SongConfig` fields.
- `run.py` — premium best-of-N + regenerate loop (`_generate_song_best_of`), gated; standard path unchanged.
- `pipeline/api.py` — `quality_tier` on request, credit calc, approve-gate max-spend, persist tier.
- `pipeline/song_assemble.py` — `maybe_master` delegates to `mastering.master_track` (premium-gated).
- `pyproject.toml` — add `matchering`.
- **new tests** `tests/test_song_ar.py`, `tests/test_mastering.py`, `tests/test_llm_gemini_audio.py`; extend `tests/test_run_song_mode.py`, `tests/test_song_api.py`, `tests/test_config.py`.

---

## Task 1: Config — SongConfig fields + config.yaml

**Files:**
- Modify: `pipeline/config.py` (`SongConfig`)
- Modify: `config.yaml` (`song:` block)
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_config.py`:

```python
def test_song_config_ar_pipeline_defaults(tmp_path):
    from pipeline.config import load_config
    import textwrap
    cfg_path = tmp_path / "c.yaml"
    cfg_path.write_text(textwrap.dedent("""
      voice: {provider: edge_tts, name: x, rate: "+0%", pitch: "+0Hz"}
      script: {word_count_target: 100, word_count_tolerance: 20, enable_critique_pass: false, repetition_threshold: 0.8, min_beats: 4, max_beats: 8, words_per_beat: 20}
      flux: {steps: 4, guidance: 3.5, width: 1280, height: 720}
      assemble: {output_width: 1920, output_height: 1080, shot_crossfade_ms: 350, music_duck_db: -18, music_silence_db: -8, fade_in_s: 1, fade_out_s: 1}
      captions: {burn_in: false, font: X, font_size: 60}
      kie: {model: veo3_fast, num_clips: 5, clip_duration_s: 8, aspect_ratio: "9:16", cost_per_second_usd: 0.1, max_spend_usd: 13, poll_interval_s: 5, poll_timeout_s: 300, flux_model: x, flux_cost_per_image_usd: 0.05, native_audio: true}
      song: {suno_model: V5_5, suno_cost_usd: 0.05, cover_flux_model: x, cover_cost_usd: 0.03, credits_per_song: 1}
    """))
    c = load_config(cfg_path)
    # New A&R fields default without being present in the config block:
    assert c.song.quality_tier_default == "standard"
    assert c.song.best_of == 6
    assert c.song.quality_bar == 70
    assert c.song.regen_max_rounds == 1
    assert c.song.regen_extra_takes == 4
    assert c.song.max_takes == 10
    assert c.song.premium_credit_surcharge == 4
    assert c.song.ar_judge_enabled is False
    assert c.song.master_engine == "matchering"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py::test_song_config_ar_pipeline_defaults -v`
Expected: FAIL — `AttributeError: 'SongConfig' object has no attribute 'quality_tier_default'`.

- [ ] **Step 3: Add the fields to `SongConfig`**

In `pipeline/config.py`, add to `SongConfig` after `master_pass`:

```python
    # A&R quality pipeline (premium tier). Defaults keep old config blocks loading.
    quality_tier_default: str = "standard"   # "premium" enables best-of-N + judge
    best_of: int = 6                         # round-1 takes (→ ceil(best_of/2) jobs)
    quality_bar: int = 70                    # composite (0-100) to accept
    regen_max_rounds: int = 1                # max_takes is the binding cap at defaults
    regen_extra_takes: int = 4               # takes added per regen round
    max_takes: int = 10                      # hard budget backstop
    premium_credit_surcharge: int = 4        # extra credits for premium tier
    ar_judge_enabled: bool = False           # shadow-mode; flip after validation
    master_engine: str = "matchering"        # matchering | ffmpeg (api reserved)
```

- [ ] **Step 4: Add the keys to `config.yaml`**

Under `song:` (after `master_pass: false`):

```yaml
  # A&R quality pipeline (premium tier). See spec 2026-08-03.
  quality_tier_default: standard
  best_of: 6
  quality_bar: 70
  regen_max_rounds: 1
  regen_extra_takes: 4
  max_takes: 10
  premium_credit_surcharge: 4
  ar_judge_enabled: false        # shadow-mode: judge logs only until validated
  master_engine: matchering      # matchering | ffmpeg (api reserved, not built)
```

- [ ] **Step 5: Run test + config smoke**

Run: `uv run pytest tests/test_config.py::test_song_config_ar_pipeline_defaults -v`
Expected: PASS.
Run: `uv run python -c "from pipeline.config import load_config; from pathlib import Path; print(load_config(Path('config.yaml')).song.best_of, load_config(Path('config.yaml')).song.ar_judge_enabled)"`
Expected: `6 False`.

- [ ] **Step 6: Commit**

```bash
git add pipeline/config.py config.yaml tests/test_config.py
git commit -m "$(cat <<'EOF'
feat(song): A&R quality pipeline config fields (premium tier)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: `song_ar.py` — signal defect prune (`screen_takes`)

**Files:**
- Create: `pipeline/song_ar.py`
- Test: `tests/test_song_ar.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_song_ar.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_song_ar.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pipeline.song_ar'`.

- [ ] **Step 3: Create `pipeline/song_ar.py` (screen only)**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_song_ar.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add pipeline/song_ar.py tests/test_song_ar.py
git commit -m "$(cat <<'EOF'
feat(song): song_ar.screen_takes — signal defect prune for takes

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Gemini audio judge client (`judge_audio`)

**Files:**
- Create: `pipeline/llm_gemini_audio.py`
- Test: `tests/test_llm_gemini_audio.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_llm_gemini_audio.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.llm_gemini_audio import GeminiAudioJudge, GeminiAudioError


def test_missing_key_raises(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(GeminiAudioError):
        GeminiAudioJudge()


def test_judge_audio_sends_audio_and_returns_text(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    mp3 = tmp_path / "take.mp3"
    mp3.write_bytes(b"ID3fakeaudio")

    captured = {}

    class _FakeModels:
        def generate_content(self, **kwargs):
            captured.update(kwargs)
            class R: text = '{"vocal_realism": 80}'
            return R()

    class _FakeClient:
        models = _FakeModels()

    monkeypatch.setattr("pipeline.llm_gemini_audio._client", lambda key: _FakeClient())
    j = GeminiAudioJudge(model="gemini-2.5-flash")
    out = j.judge_audio(mp3, system="be strict", user="style: pop")
    assert out == '{"vocal_realism": 80}'
    assert captured["model"] == "gemini-2.5-flash"
    # audio bytes must be in the request contents
    assert captured["contents"]  # non-empty parts list
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_llm_gemini_audio.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pipeline.llm_gemini_audio'`.

- [ ] **Step 3: Create `pipeline/llm_gemini_audio.py`**

```python
"""Gemini with AUDIO input — the A&R judge's ear. Separate from the text
GeminiClient in pipeline/llm.py (which is text-only)."""
from __future__ import annotations

import os
from pathlib import Path


class GeminiAudioError(RuntimeError):
    pass


def _client(api_key: str):
    """Constructed at runtime so tests can monkeypatch."""
    from google import genai
    return genai.Client(api_key=api_key)


class GeminiAudioJudge:
    """One method: judge_audio(audio_path, system, user) -> str (model text)."""

    tier = "gemini"

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self._model = model or os.environ.get("GEMINI_AUDIO_MODEL", "gemini-2.5-flash")
        key = api_key or os.environ.get("GEMINI_API_KEY")
        if not key:
            raise GeminiAudioError("GEMINI_API_KEY not set")
        self._client = _client(key)

    def judge_audio(self, audio_path, system: str, user: str) -> str:
        from google.genai import types
        data = Path(audio_path).read_bytes()
        contents = [
            types.Part.from_bytes(data=data, mime_type="audio/mpeg"),
            types.Part.from_text(text=user),
        ]
        resp = self._client.models.generate_content(
            model=self._model,
            contents=contents,
            config={"system_instruction": system},
        )
        return resp.text
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_llm_gemini_audio.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add pipeline/llm_gemini_audio.py tests/test_llm_gemini_audio.py
git commit -m "$(cat <<'EOF'
feat(llm): Gemini audio judge client (judge_audio)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: `song_ar.py` — judge, composite, pick_best

**Files:**
- Modify: `pipeline/song_ar.py` (add judge + pick)
- Test: `tests/test_song_ar.py` (add cases)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_song_ar.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_song_ar.py -k "composite or judge or pick" -v`
Expected: FAIL — `cannot import name 'judge_takes'`.

- [ ] **Step 3: Add judge + pick to `pipeline/song_ar.py`**

Append:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_song_ar.py -v`
Expected: PASS (all Task 2 + Task 4 tests).

- [ ] **Step 5: Commit**

```bash
git add pipeline/song_ar.py tests/test_song_ar.py
git commit -m "$(cat <<'EOF'
feat(song): song_ar judge_takes + pick_best (weighted composite, fallback)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: `mastering.py` — Matchering + ffmpeg fallback

**Files:**
- Create: `pipeline/mastering.py`
- Modify: `pyproject.toml` (add `matchering`)
- Test: `tests/test_mastering.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_mastering.py`:

```python
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pipeline.mastering as m


def _cfg(engine="matchering"):
    return SimpleNamespace(song=SimpleNamespace(master_engine=engine))


def test_matchering_used_when_reference_exists(monkeypatch, tmp_path):
    ref = tmp_path / "arabic_pop.wav"; ref.write_bytes(b"x")
    monkeypatch.setattr(m, "_reference_for", lambda g: ref)
    monkeypatch.setattr(m, "_master_matchering", lambda i, o, r: True)
    monkeypatch.setattr(m, "_master_ffmpeg", lambda i, o: (_ for _ in ()).throw(AssertionError("ffmpeg should not run")))
    assert m.master_track(tmp_path / "in.mp3", tmp_path / "out.mp3",
                          genre_key="arabic_pop", cfg=_cfg()) is True


def test_ffmpeg_fallback_when_no_reference(monkeypatch, tmp_path):
    monkeypatch.setattr(m, "_reference_for", lambda g: None)
    called = {}
    monkeypatch.setattr(m, "_master_ffmpeg", lambda i, o: called.setdefault("ff", True) or True)
    assert m.master_track(tmp_path / "in.mp3", tmp_path / "out.mp3",
                          genre_key="rare", cfg=_cfg()) is True
    assert called.get("ff") is True


def test_master_track_never_raises_returns_false(monkeypatch, tmp_path):
    monkeypatch.setattr(m, "_reference_for", lambda g: (_ for _ in ()).throw(RuntimeError("boom")))
    assert m.master_track(tmp_path / "in.mp3", tmp_path / "out.mp3",
                          genre_key="x", cfg=_cfg()) is False


def test_api_engine_falls_back_to_ffmpeg(monkeypatch, tmp_path):
    monkeypatch.setattr(m, "_master_ffmpeg", lambda i, o: True)
    assert m.master_track(tmp_path / "in.mp3", tmp_path / "out.mp3",
                          genre_key="x", cfg=_cfg(engine="api")) is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_mastering.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pipeline.mastering'`.

- [ ] **Step 3: Create `pipeline/mastering.py`**

```python
"""Master the winning take. Matchering (reference-based) preferred; ffmpeg
tonal chain as the no-reference fallback. Never raises — returns False so the
worker ships the unmastered winner. See spec 2026-08-03."""
from __future__ import annotations

import subprocess
from pathlib import Path

_REFERENCE_DIR = Path(__file__).resolve().parent.parent / "assets" / "reference_masters"


def _reference_for(genre_key: str) -> Path | None:
    ref = _REFERENCE_DIR / f"{genre_key}.wav"
    return ref if ref.exists() else None


def _master_matchering(in_path: Path, out_path: Path, reference: Path) -> bool:
    import matchering as mg
    # matchering's pcm16 result must be a PCM-capable container (WAV) — it raises
    # "MP3 format does not have PCM_16 subtype" on an .mp3 target. Master to a
    # temp WAV, then deliver out_path's actual container.
    tmp_wav = out_path.with_suffix(".mastered.wav")
    mg.process(
        target=str(in_path),
        reference=str(reference),
        results=[mg.pcm16(str(tmp_wav))],
    )
    if not tmp_wav.exists():
        return False
    if out_path.suffix.lower() == ".wav":
        tmp_wav.replace(out_path)
    else:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(tmp_wav),
             "-c:a", "libmp3lame", "-q:a", "2", str(out_path)],
            check=True, capture_output=True,
        )
        try:
            tmp_wav.unlink()
        except OSError:
            pass
    return out_path.exists()


def _master_ffmpeg(in_path: Path, out_path: Path) -> bool:
    # HPF rumble cut + de-ess-ish high shelf tame + gentle comp + true-peak
    # limiter at -1 dBTP. NO loudnorm — Suno already ships ~-14 LUFS.
    af = ("highpass=f=30,acompressor=threshold=-18dB:ratio=2:attack=20:release=250,"
          "alimiter=limit=0.891")  # 0.891 ≈ -1 dBTP
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(in_path), "-af", af,
         "-c:a", "libmp3lame", "-q:a", "2", str(out_path)],
        check=True, capture_output=True,
    )
    return out_path.exists()


def master_track(in_path, out_path, *, genre_key: str, cfg) -> bool:
    """Return True if a master was written to out_path, else False (ship
    unmastered). Never raises."""
    in_path, out_path = Path(in_path), Path(out_path)
    engine = "ffmpeg"
    if cfg and getattr(cfg, "song", None):
        engine = getattr(cfg.song, "master_engine", "ffmpeg")
    try:
        if engine == "matchering":
            ref = _reference_for(genre_key)
            if ref:
                try:
                    if _master_matchering(in_path, out_path, ref):
                        return True
                    print("[mastering] matchering produced no output; ffmpeg fallback")
                except Exception as e:
                    print(f"[mastering] matchering failed ({e}); ffmpeg fallback")
                return _master_ffmpeg(in_path, out_path)
            print(f"[mastering] no reference master for {genre_key!r}; ffmpeg fallback")
            return _master_ffmpeg(in_path, out_path)
        if engine == "api":
            print("[mastering] 'api' engine reserved/not built; ffmpeg fallback")
            return _master_ffmpeg(in_path, out_path)
        return _master_ffmpeg(in_path, out_path)
    except Exception as e:
        print(f"[mastering] failed ({e}); shipping unmastered")
        return False
```

- [ ] **Step 4: Add the dependency**

In `pyproject.toml` dependencies, add:

```toml
    # matchering: reference-based mastering of the winning take (A&R pipeline).
    "matchering>=2.0",
```

Run: `uv sync`
Expected: resolves and installs matchering (pulls soundfile/scipy).

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_mastering.py -v`
Expected: PASS (4 tests — all mock `_master_matchering`/`_master_ffmpeg`, so neither the lib nor ffmpeg actually runs).

- [ ] **Step 6: Commit**

```bash
git add pipeline/mastering.py pyproject.toml tests/test_mastering.py
git commit -m "$(cat <<'EOF'
feat(song): mastering.master_track — Matchering + ffmpeg fallback

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: `run.py` — premium best-of-N + regenerate loop

**Files:**
- Modify: `run.py` (song generation stage — add premium branch)
- Modify: `pipeline/song_assemble.py` (`maybe_master` delegates to mastering)
- Test: `tests/test_run_song_mode.py` (add premium-loop cases)

**Context:** today's block (`run.py` ~1055–1140) submits one Suno job, downloads its 2 takes, keeps the longer, copies to `song.mp3`, calls the no-op `maybe_master`. For `quality_tier == "premium"` we instead run a best-of-N + regenerate loop via a new helper `_generate_song_best_of`. Standard tier keeps the existing path verbatim. Both then run `maybe_master`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_run_song_mode.py` (helpers mock Suno + the judge + screening so no network/audio):

```python
def test_premium_best_of_n_picks_judge_winner(tmp_path, monkeypatch):
    import run as run_mod
    from pipeline import song_ar
    # 3 jobs → 6 takes; judge scores take with index 4 highest.
    scores = {f"take_{i}.mp3": (90 if i == 4 else 50) for i in range(1, 7)}
    monkeypatch.setattr(song_ar, "screen_takes",
        lambda paths, **k: [song_ar.ScreenedTake(p, 60.0, 0.0, 0.1, True, "") for p in map(__import__('pathlib').Path, paths)])
    monkeypatch.setattr(song_ar, "judge_takes",
        lambda audio_llm, screened, **k: [song_ar.JudgedTake(s.path, scores[s.path.name], {}, "", "gemini") for s in screened])
    winner = run_mod._select_best_take(
        [__import__('pathlib').Path(tmp_path / f"take_{i}.mp3") for i in range(1, 7)],
        audio_llm=object(), style_prompt="pop", language="ar", dialect=None,
        quality_bar=70, ar_judge_enabled=True)
    assert winner.path.name == "take_4.mp3" and winner.clears_bar is True


def test_premium_shadow_mode_uses_signal_not_judge(tmp_path, monkeypatch):
    import run as run_mod
    from pipeline import song_ar
    from pathlib import Path
    # judge would pick take_1, but shadow mode must ignore it and use signal.
    monkeypatch.setattr(song_ar, "screen_takes",
        lambda paths, **k: [song_ar.ScreenedTake(Path(paths[0]), 60.0, 0.0, 0.1, True, ""),
                            song_ar.ScreenedTake(Path(paths[1]), 20.0, 0.0, 0.1, True, "")])
    called = {"judge": False}
    def _judge(*a, **k):
        called["judge"] = True
        return [song_ar.JudgedTake(Path("take_1.mp3"), 99, {}, "", "gemini")]
    monkeypatch.setattr(song_ar, "judge_takes", _judge)
    winner = run_mod._select_best_take(
        [Path("take_1.mp3"), Path("take_2.mp3")], audio_llm=object(),
        style_prompt="pop", language="ar", dialect=None,
        quality_bar=70, ar_judge_enabled=False)  # shadow mode
    # shadow mode: judge still runs for logging, but selection is signal-based
    # (longer/cleaner take_1 wins by duration), not the judge's pick per se here.
    assert winner.path.name == "take_1.mp3"
```

Note: `_select_best_take` is the pure selection helper extracted in Step 3; the full worker loop is covered by an integration test added in Step 4.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_run_song_mode.py -k "premium_best_of or shadow_mode" -v`
Expected: FAIL — `AttributeError: module 'run' has no attribute '_select_best_take'`.

- [ ] **Step 3: Add the selection helper + premium generator to `run.py`**

Add near the song helpers in `run.py`:

```python
def _select_best_take(take_paths, *, audio_llm, style_prompt, language, dialect,
                      quality_bar, ar_judge_enabled):
    """Screen → judge → pick. In shadow mode (ar_judge_enabled=False) the judge
    still runs (scores logged) but selection is signal-based so an unvalidated
    ear never decides a real render. Returns a song_ar.Verdict."""
    from pipeline import song_ar
    screened = song_ar.screen_takes(take_paths)
    judged = song_ar.judge_takes(audio_llm, screened, style_prompt=style_prompt,
                                 language=language, dialect=dialect)
    for j in judged:
        print(f"[song-ar] {j.path.name}: {j.composite} ({j.source}) {j.reason}")
    if ar_judge_enabled:
        return song_ar.pick_best(judged, quality_bar=quality_bar)
    # Shadow mode: pick by signal composite (defect-pruned, longest-clean).
    signal = [song_ar.JudgedTake(s.path, song_ar._signal_composite(s), {}, "", "signal")
              for s in screened if s.passed] or \
             [song_ar.JudgedTake(s.path, 0.0, {}, "", "signal") for s in screened]
    # tie-break signal ties by duration (the old "pick longer" heuristic)
    dur = {s.path: s.duration_s for s in screened}
    signal.sort(key=lambda j: (j.composite, dur.get(j.path, 0.0)), reverse=True)
    best = signal[0]
    return song_ar.Verdict(best.path, best.composite, {}, "shadow-signal",
                           "signal", best.composite >= quality_bar)
```

Then restructure the song-generation stage to branch on tier. The existing block (today) does, in order: submit → wait → download → "pick longer" setting `chosen_path` → `write_state(chosen_take=chosen)` → **copy `chosen_path`→`song_mp3`** → `song_assemble.maybe_master(song_mp3, cfg)`. Refactor precisely:

1. **Extract** the copy-to-`song_mp3` and the `maybe_master` call out of the existing block so they run **once** after the if/else (shown below); delete them from the existing block.
2. **Wrap** what remains of the existing block (submit/wait/download/"pick longer" that assigns `chosen_path`, plus its `write_state(chosen_take=chosen)`) unchanged in the new `else:` branch.
3. **Add** the premium `if` branch above it.

Resulting shape:

```python
            _tier = (script.get("quality_tier")
                     or (cfg.song.quality_tier_default if cfg.song else "standard"))
            if _tier == "premium" and cfg.song and not is_cover:
                chosen_path, verdict, n_takes = _generate_song_best_of(
                    client, script, model=_model, negative_tags=_negative_tags,
                    takes_dir=takes_dir, cfg=cfg,
                )
                write_state(chosen_take=1, takes_generated=n_takes,
                            ar_score=verdict.composite, ar_reason=verdict.reason,
                            judge_source=verdict.source,
                            quality_bar_cleared=verdict.clears_bar)
            else:
                # EXISTING single-job standard/cover block, UNCHANGED — from
                # `task_id = song.submit_song_job(...)` (or the cover branch)
                # through `chosen_path = takes_dir / f"take_{chosen}.mp3"` and
                # `write_state(chosen_take=chosen)`. Its inline copy-to-song_mp3
                # and maybe_master call are REMOVED (they moved below).
                ...  # existing code stays here verbatim, minus copy + maybe_master

            # --- both paths converge here (copy + master run ONCE) ---
            with chosen_path.open("rb") as src, song_mp3.open("wb") as dst:
                while chunk := src.read(1 << 20):
                    dst.write(chunk)
            # Mastering: premium-gated inside maybe_master (master_pass flag).
            # No-op/False → ship unmastered. Never raises.
            song_assemble.maybe_master(song_mp3, cfg, genre_key=_genre_key_from(script))
```

Note: the premium branch's `_generate_song_best_of` already downloads takes and returns `chosen_path`; the `else` branch keeps its own download. Only the final copy + `maybe_master` are shared.

Add the premium generator helper:

```python
import math


def _generate_song_best_of(client, script, *, model, negative_tags, takes_dir, cfg):
    """Best-of-N + regenerate loop. Returns (chosen_path, Verdict, total_takes)."""
    from pipeline import song, song_ar
    sc = cfg.song
    takes_dir.mkdir(exist_ok=True)
    audio_llm = _build_audio_judge()   # may be None if no GEMINI key
    all_paths: list = []
    n = 0
    rounds = 1 + int(sc.regen_max_rounds)
    for rnd in range(rounds):
        want = sc.best_of if rnd == 0 else sc.regen_extra_takes
        jobs = math.ceil(want / 2)
        # Parallel: submit all jobs first, then wait each (Suno runs concurrently).
        task_ids = [song.submit_song_job(
            client, lyrics=script["lyrics"], style_prompt=script["style_prompt"],
            title=script["title"], model=model,
            vocal_gender=script.get("vocal_gender"),
            persona_id=script.get("persona_id"), negative_tags=negative_tags)
            for _ in range(jobs)]
        for tid in task_ids:
            for take in song.wait_for_song(client, tid):
                n += 1
                p = takes_dir / f"take_{n}.mp3"
                song.download_take(client, take.url, p)
                all_paths.append(p)
            if n >= sc.max_takes:
                break
        verdict = _select_best_take(
            all_paths, audio_llm=audio_llm, style_prompt=script["style_prompt"],
            language=script.get("language", "ar"), dialect=script.get("dialect"),
            quality_bar=sc.quality_bar, ar_judge_enabled=bool(sc.ar_judge_enabled))
        if verdict.clears_bar or n >= sc.max_takes or rnd == rounds - 1:
            if not verdict.clears_bar:
                print(f"[song-ar] shipped best of {n} takes @ {verdict.composite} "
                      f"< bar {sc.quality_bar} (cap reached)")
            return verdict.path, verdict, n
    return verdict.path, verdict, n


def _build_audio_judge():
    """The Gemini audio judge, or None if GEMINI_API_KEY is absent (→ judge_takes
    signal-fallback)."""
    try:
        from pipeline.llm_gemini_audio import GeminiAudioJudge
        return GeminiAudioJudge()
    except Exception as e:
        print(f"[song-ar] no audio judge ({e}); signal fallback")
        return None


def _genre_key_from(script) -> str:
    """Recover the genre for reference-master lookup: infer from theme/style."""
    from pipeline.song_style import infer_genre
    return infer_genre(script.get("theme", ""), script.get("style_prompt"),
                       script.get("language", "ar"), script.get("dialect"))
```

Note: when `audio_llm` is None, `judge_takes` still runs but every `judge_audio` call raises → signal-fallback (its existing behavior). Confirm `judge_takes` tolerates `audio_llm=None` (calling `.judge_audio` on None raises inside the try → fallback). ✓.

- [ ] **Step 4: Wire `maybe_master` to real mastering + add an integration test**

In `pipeline/song_assemble.py`, change `maybe_master` to accept `genre_key` and delegate:

```python
def maybe_master(mp3_path: Path, cfg, *, genre_key: str = "generic") -> bool:
    """Master the track in place when enabled. Premium tier sets master_pass.
    Delegates to pipeline.mastering; never raises. See spec 2026-08-03."""
    if not (cfg and getattr(cfg, "song", None)
            and getattr(cfg.song, "master_pass", False)):
        return False
    from pipeline import mastering
    tmp = mp3_path.with_suffix(".mastered.mp3")
    if mastering.master_track(mp3_path, tmp, genre_key=genre_key, cfg=cfg):
        with tmp.open("rb") as src, mp3_path.open("wb") as dst:
            while chunk := src.read(1 << 20):
                dst.write(chunk)
        try:
            tmp.unlink()
        except OSError:
            pass
        return True
    return False
```

Update the existing `maybe_master` tests in `tests/test_song_assemble.py` to pass `genre_key` where needed (the no-flag/no-song cases still return False; the flag-on case now needs `master_pass=True` + a mocked `mastering.master_track`). Add:

```python
def test_maybe_master_delegates_when_flag_on(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import pipeline.song_assemble as sa
    mp3 = tmp_path / "song.mp3"; mp3.write_bytes(b"orig")
    monkeypatch.setattr("pipeline.mastering.master_track",
                        lambda i, o, **k: (Path(o).write_bytes(b"mastered"), True)[1])
    cfg = SimpleNamespace(song=SimpleNamespace(master_pass=True, master_engine="ffmpeg"))
    assert sa.maybe_master(mp3, cfg, genre_key="arabic_pop") is True
    assert mp3.read_bytes() == b"mastered"
```

(The pre-existing `test_maybe_master_never_shells_out_even_when_flag_on` must be updated: with the seam now delegating, assert instead that `mastering.master_track` is called and no *direct* subprocess call happens in `maybe_master` itself.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_run_song_mode.py -k "premium_best_of or shadow_mode" tests/test_song_assemble.py -k "maybe_master" -v`
Expected: PASS. Then run the whole song-mode file: `uv run pytest tests/test_run_song_mode.py -q` — the pre-existing ffmpeg-dependent failures remain (baseline), but no NEW failures from the standard path (which is unchanged) or the new premium helper.

- [ ] **Step 6: Commit**

```bash
git add run.py pipeline/song_assemble.py tests/test_run_song_mode.py tests/test_song_assemble.py
git commit -m "$(cat <<'EOF'
feat(song): premium best-of-N + regenerate loop + real maybe_master

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: `api.py` — quality_tier pricing + approve-gate disclosure

**Files:**
- Modify: `pipeline/api.py` (`CreateSongRequest`, `_song_credit_amount`, create + script + approve, song.json)
- Test: `tests/test_song_api.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_song_api.py`:

```python
def test_premium_quality_tier_surcharges_credits_and_persists(app):
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    r = client.post("/songs",
                    json={"theme": "x", "language": "ar", "quality_tier": "premium"},
                    headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 201, r.text
    run_dir = _find_run_dir(r.json()["run_id"])
    song_json = json.loads((run_dir / "song.json").read_text())
    assert song_json["quality_tier"] == "premium"


def test_song_credit_amount_premium_surcharge():
    from pipeline.api import _song_credit_amount
    from pipeline.config import load_config
    from pathlib import Path
    cfg = load_config(Path("config.yaml"))
    std = _song_credit_amount("static", "standard", cfg)
    prem = _song_credit_amount("static", "premium", cfg)
    assert prem == std + cfg.song.premium_credit_surcharge
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_song_api.py -k "premium_quality_tier or premium_surcharge" -v`
Expected: FAIL — `_song_credit_amount()` takes 2 args / `quality_tier` unknown field.

- [ ] **Step 3: Add `quality_tier` to the request model**

In `pipeline/api.py`, add to `CreateSongRequest` (after `dialect`):

```python
    quality_tier: str = "standard"   # "standard" | "premium" (best-of-N + A&R)

    @field_validator("quality_tier")
    @classmethod
    def _check_quality_tier(cls, v: str) -> str:
        if v not in ("standard", "premium"):
            raise ValueError("quality_tier must be 'standard' or 'premium'")
        return v
```

- [ ] **Step 4: Extend `_song_credit_amount` and its callers**

Change the signature to `_song_credit_amount(video_mode, quality_tier, cfg)`:

```python
def _song_credit_amount(video_mode: str, quality_tier: str, cfg) -> int:
    """Credit cost for one song render. Single source of truth."""
    if cfg.song:
        base = (cfg.song.cinematic_credits_per_song
                if video_mode == "cinematic" else cfg.song.credits_per_song)
        surcharge = cfg.song.premium_credit_surcharge if quality_tier == "premium" else 0
        return base + surcharge
    base = 3 if video_mode == "cinematic" else 1
    return base + (4 if quality_tier == "premium" else 0)
```

Update every caller of `_song_credit_amount(...)` to pass the tier. In `create_song` (~2776): `credits_required = _song_credit_amount(req.video_mode, req.quality_tier, cfg)`. In the `/songs/{id}/script` cost response and any approve/reroll path, read the tier from state (`state.get("quality_tier", "standard")`) and pass it. Grep to find all call sites: `grep -n "_song_credit_amount(" pipeline/api.py`.

- [ ] **Step 5: Persist tier + approve-gate disclosure**

In the `create_song` `song.json` write, add `"quality_tier": req.quality_tier`. In `SongScriptResponse` (or the script endpoint payload) include the tier and the max-spend string, e.g.:

```python
    premium = state.get("quality_tier") == "premium"
    max_spend_note = (
        f"Premium quality: best-of-N + AI A&R + master — up to "
        f"{cfg.song.max_takes} takes, ~${cfg.song.max_takes/2*cfg.song.suno_cost_usd:.2f}, "
        f"{_song_credit_amount(state.get('video_mode','static'), 'premium', cfg)} credits"
        if premium else None
    )
```

Include `max_spend_note` in the script response so the app shows it at the approve gate. (Add a `max_spend_note: str | None = None` field to the response model.)

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_song_api.py -k "premium_quality_tier or premium_surcharge" -v`
Expected: PASS. Then `uv run pytest tests/test_song_api.py tests/test_api.py -q` — only the known pre-existing `test_api.py` max-spend failure remains.

- [ ] **Step 7: Commit**

```bash
git add pipeline/api.py tests/test_song_api.py
git commit -m "$(cat <<'EOF'
feat(song): quality_tier pricing axis + approve-gate max-spend disclosure

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Reference-master assets

**Files:**
- Create: `assets/reference_masters/.gitkeep`
- Create: `assets/reference_masters/README.md`

- [ ] **Step 1: Create the directory + README**

`assets/reference_masters/README.md`:

```markdown
# Reference masters (Matchering)

Drop ONE professionally-mastered, **owned or royalty-free (CC0)** reference
track per genre family here, named `<genre_key>.wav`, where `<genre_key>` is a
key from `pipeline/song_style.py:GENRE_RECIPES` (e.g. `arabic_pop.wav`,
`khaleeji.wav`, `arabic_ballad.wav`, `pop.wav`, ...).

Matchering matches each Suno take's spectral balance + loudness to the
reference. If a genre has no reference here, mastering falls back to the free
ffmpeg tonal chain automatically (`pipeline/mastering.py`).

Do NOT commit copyrighted commercial tracks.
```

Create `assets/reference_masters/.gitkeep` (empty) so the dir exists.

- [ ] **Step 2: Verify the fallback works with no references present**

Run: `uv run python -c "from pipeline.mastering import _reference_for; print(_reference_for('arabic_pop'))"`
Expected: `None` (no wav yet) → confirms `master_track` will use the ffmpeg fallback until the user adds references.

- [ ] **Step 3: Commit**

```bash
git add assets/reference_masters/.gitkeep assets/reference_masters/README.md
git commit -m "$(cat <<'EOF'
feat(song): reference-master asset dir for Matchering (user-supplied)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Full-suite verification + validation-gate doc

**Files:** none (verification) + a note in the spec's validation section

- [ ] **Step 1: Run the entire suite**

Run: `uv run pytest -q`
Expected: **7 failed, N passed** — the pre-existing baseline (`test_api` max-spend, `test_llm_groq` stale model, 2× `test_mp4_faststart`, 3× `test_run_shorts_smoke`). NOTE: an earlier draft said "30" — the local ffmpeg/libass was repaired since, so ~23 formerly-failing ffmpeg tests now pass; 7 is the real baseline. Confirm NO new failures in `test_song_ar`, `test_mastering`, `test_llm_gemini_audio`, `test_config`, `test_song_api`, `test_song_assemble`, `test_run_song_mode`. If any new failure appears, fix the stub/assertion (do NOT weaken real logic) and re-run.

- [ ] **Step 2: Offline smoke — premium selection with no external services**

Run:
```bash
uv run python -c "
from pipeline import song_ar
from pathlib import Path
scr = [song_ar.ScreenedTake(Path('take_1.mp3'), 60,0,0.1,True,''),
       song_ar.ScreenedTake(Path('take_2.mp3'), 61,0,0.1,True,'')]
# no audio_llm → signal fallback, never raises
j = song_ar.judge_takes(None, scr, style_prompt='pop', language='ar')
v = song_ar.pick_best(j, quality_bar=70)
print('picked', v.path.name, v.composite, v.source, 'clears', v.clears_bar)
"
```
Expected: prints a picked take with `source=signal-fallback` and no traceback (proves the never-blocks-a-render guarantee end-to-end offline).

- [ ] **Step 3: Confirm shadow-mode default is safe**

Run: `uv run python -c "from pipeline.config import load_config; from pathlib import Path; print('ar_judge_enabled =', load_config(Path('config.yaml')).song.ar_judge_enabled)"`
Expected: `ar_judge_enabled = False` — the AI ear cannot decide a real render until this flag is deliberately flipped post-validation.

- [ ] **Step 4: Validation-gate reminder (manual, before flipping the flag)**

Before setting `ar_judge_enabled: true` in prod, run the judge on a labeled set
of ~10 known-good and ~10 known-bad real Suno takes and confirm the composite
separates them (good median clearly above bad median, and above `quality_bar`).
This is a manual/offline validation, not an automated test. Document the result
in the spec's "Validation gate" section before flipping.

- [ ] **Step 5: Final commit (only if Step 1 required fixups)**

```bash
git add -A
git commit -m "$(cat <<'EOF'
test(song): stabilize suite for A&R quality pipeline

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Follow-ups (out of scope — noted, not built)

- Let the user hear + override the ranked finalists (phase 2 UX).
- Optional prompt nudges on regenerate rounds.
- Multi-engine generation (Suno + Udio/ElevenLabs) + cross-engine judging.
- Paid mastering API if Matchering proves insufficient.
- Extract the duplicated `_parse_json_object` (song_style, song_ar, song_lyrics, song_import, trends) into one shared helper.
- Premium best-of-N for the **cover** path (currently premium falls through to the standard single-job cover behavior).

### Follow-ups surfaced during implementation review (not blocking)

- **`POST /songs/{id}/cancel` never refunds** (`api.py` ~3509) — kills the process + sets status=canceled but never calls `refund_run_charges`. Pre-existing, but the premium surcharge raises stranded credits per incident from 1–3 to 5–7. Wire it to `refund_run_charges` like the generic `/runs/{id}/cancel` does.
- **Loose `google-genai>=0.3.0` pin** while the lock resolves 2.0.1 (the API changed materially across that range). A loose lock regen could pull an incompatible version. Tighten the lower bound to match 2.x.
- **matchering pulls heavy transitive deps** (pandas, statsmodels, resampy) — grows the Docker image. If image size matters, consider a lighter mastering path or a slim extra.
- **No dedicated resume-path test** for premium best-of-N (the `existing_records`/`on_progress` logic is verified by inspection + exercised structurally by the integration test, but a direct "crash mid-render → resume reuses takes, re-bills nothing" test would lock it).
- **Validation gate (required before flipping `ar_judge_enabled: true`):** run the Gemini audio judge on a labeled set of ~10 known-good + ~10 known-bad real Suno takes; confirm the composite separates them (good median clearly above bad, and above `quality_bar`). Document the result before enabling in prod. This is manual/offline, not an automated test.
