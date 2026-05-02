# Tier-3 @sunstoriz-Quality Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the existing `--shorts` pipeline to produce 60–120 sec vertical TikTok videos that match @sunstoriz quality, by adding ElevenLabs voice + Whisper-aligned captions + Kie.ai Flux character sheets + image-referenced Veo 3 clips for cohesion.

**Architecture:** Five additive modules (ElevenLabs client, Whisper aligner, Flux character-sheet generator, Veo `REFERENCE_2_VIDEO` mode, frame-extraction helper) wired into the existing 8-stage `--shorts` orchestrator. Voice and video stages get a strategy switch driven by config; everything else is purely additive. All paid APIs are mocked in tests; one real run gates each phase.

**Tech Stack:** Python 3.11+, `uv`, `pytest`. New deps: `openai-whisper` (already used once), `requests` (already in repo). External services: ElevenLabs Multilingual v2 (TTS), Kie.ai Flux 1.1 Pro (character sheet), Kie.ai Veo 3 full (video, REFERENCE_2_VIDEO mode).

**Reference spec:** `docs/superpowers/specs/2026-05-02-sunstoriz-tier3-design.md` — read it before starting.

---

## File Structure

```
faceless/
├── pipeline/
│   ├── elevenlabs.py        # NEW — ElevenLabs HTTP client (parallel to llm_groq.py / kie.py)
│   ├── align.py             # NEW — Whisper force-alignment to refine word timings
│   ├── character_sheet.py   # NEW — orchestrates Flux call → out/<run>/character_sheet.png
│   ├── frames.py            # NEW — last-frame extraction via ffmpeg
│   ├── voice.py             # MODIFY — becomes a router (elevenlabs | edge_tts)
│   ├── kie.py               # MODIFY — add submit_image_job() for Flux + REFERENCE_2_VIDEO mode
│   ├── video.py             # MODIFY — REFERENCE_2_VIDEO with character sheet + chained last-frame
│   ├── script.py            # MODIFY — variable num_beats 8–15; writer picks based on premise
│   ├── config.py            # MODIFY — add ElevenLabsConfig + KieConfig.flux_*
│   └── types.py             # MODIFY — Beat gets clip_duration_s; Script gets target_duration_s
├── config.yaml              # MODIFY — new voice.provider, kie.flux_*, script.min/max_beats
├── .env                     # MODIFY — add ELEVENLABS_API_KEY
├── run.py                   # MODIFY — new align stage, new character_sheet stage
└── tests/
    ├── test_elevenlabs.py   # NEW
    ├── test_align.py        # NEW
    ├── test_character_sheet.py  # NEW
    ├── test_frames.py       # NEW
    ├── test_voice.py        # MODIFY — add router test
    ├── test_kie.py          # MODIFY — add Flux + REFERENCE_2_VIDEO tests
    ├── test_video.py        # MODIFY — image-chain mode tests
    ├── test_script.py       # MODIFY — variable beats tests
    └── test_run_shorts_smoke.py  # MODIFY — new pipeline order + character sheet stage
```

---

## Conventions for every task

- **Always TDD:** failing test first, then implementation, then verify pass, then commit.
- **Pytest is the only test runner.** Run from repo root: `uv run pytest <path> -v`.
- **No real API/network calls in tests.** Use the existing fakes pattern (monkeypatch `_post_json`, `_get_json`, etc.).
- **Commit after each task** with conventional-commit prefixes: `feat:`, `test:`, `fix:`, `chore:`.
- **Type-hint everything.** Use `from __future__ import annotations` at the top of every Python file.
- **Use `pathlib.Path` for paths.** Never `os.path`.
- **Imports are absolute** (`from pipeline.elevenlabs import ...`).
- **All HTTP clients follow the existing pattern** (see `pipeline/kie.py` and `pipeline/llm_groq.py`): retry-with-backoff, `_post_json` / `_get_json` indirection so tests can monkeypatch.
- **All new external APIs gracefully fall back** when the API key isn't set (mirrors what `llm_groq.py` does).

---

## Task 1: Update `pipeline/types.py` for variable-length beats

`Script.beats` already exists; we add a per-beat `clip_duration_s` field (so the orchestrator knows how long each Veo clip should be) and a top-level `target_duration_s` (writer's chosen total length).

**Files:**
- Modify: `pipeline/types.py`
- Modify: `tests/test_types.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_types.py`:

```python
def test_beat_carries_clip_duration():
    b = Beat(arabic="x", english_motion="m", clip_duration_s=7.5)
    assert b.clip_duration_s == 7.5
    assert Beat.from_dict(b.to_dict()) == b


def test_script_has_target_duration():
    s = Script(
        title="t", theme="folkloric", global_setting="x",
        music_mood="dread",
        beats=(Beat(arabic="a", english_motion="m", clip_duration_s=8.0),),
        story_combined="a",
        target_duration_s=64.0,
    )
    assert s.target_duration_s == 64.0
    assert Script.from_dict(s.to_dict()).target_duration_s == 64.0
```

- [ ] **Step 2: Run, verify failure**

```bash
uv run pytest tests/test_types.py::test_beat_carries_clip_duration -v
```
Expected: `TypeError: Beat.__init__() got an unexpected keyword argument 'clip_duration_s'` (or similar).

- [ ] **Step 3: Add fields to `Beat` and `Script`**

In `pipeline/types.py`, replace the `Beat` and `Script` definitions:

```python
@dataclass(frozen=True)
class Beat:
    """One narration beat ↔ one Veo clip in the Shorts pipeline."""
    arabic: str
    english_motion: str
    clip_duration_s: float = 8.0  # how long the matching Veo clip should run

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Beat":
        return cls(**d)


@dataclass(frozen=True)
class Script:
    """Script artifact for both pipeline modes."""
    title: str
    theme: str
    global_setting: str
    music_mood: str
    # Long-form fields (optional in shorts mode)
    hook: str = ""
    story: str = ""
    word_count: int = 0
    # Shorts-mode fields (optional in long-form mode)
    beats: tuple[Beat, ...] = ()
    story_combined: str = ""
    target_duration_s: float = 0.0  # writer's chosen length (Tier-3 variable)

    def __post_init__(self):
        if self.music_mood not in VALID_MOODS:
            raise ValueError(f"invalid music_mood: {self.music_mood}")
        if self.theme not in VALID_THEMES:
            raise ValueError(f"invalid theme: {self.theme}")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Script":
        d = dict(d)
        beats_raw = d.pop("beats", None) or ()
        beats = tuple(Beat.from_dict(b) if isinstance(b, dict) else b for b in beats_raw)
        return cls(**d, beats=beats) if "beats" not in d else cls(**d)
```

- [ ] **Step 4: Add `clips_dir` and `character_sheet_png` paths to `RunPaths`**

In `pipeline/types.py`, inside `RunPaths`, add after `clips_dir`:

```python
    @property
    def character_sheet_png(self) -> Path: return self.root / "character_sheet.png"
    @property
    def first_keyframe_png(self) -> Path: return self.root / "first_keyframe.png"
    @property
    def last_frames_dir(self) -> Path: return self.root / "last_frames"
```

- [ ] **Step 5: Run all type tests; full suite**

```bash
uv run pytest tests/test_types.py -v
uv run pytest --tb=no -q
```
Expected: previous 8 type tests + 2 new = 10 pass. Full suite ≥ 114 (was 112).

- [ ] **Step 6: Commit**

```bash
git add pipeline/types.py tests/test_types.py
git commit -m "feat(types): Beat.clip_duration_s + Script.target_duration_s for tier-3"
```

---

## Task 2: Update `pipeline/config.py` for ElevenLabs + Flux + script.min/max_beats

**Files:**
- Modify: `pipeline/config.py`
- Modify: `config.yaml`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Write failing test**

Replace the body of `test_load_full_config` in `tests/test_config.py` with a richer config that includes the new fields:

```python
def test_load_full_config(tmp_path: Path):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(textwrap.dedent("""
        voice:
          provider: elevenlabs
          name: ar-EG-SalmaNeural
          rate: "+0%"
          pitch: "+0Hz"
          elevenlabs_voice_id: 21m00Tcm4TlvDq8ikWAM
          elevenlabs_model: eleven_multilingual_v2
          fallback_to_edge_tts: true
        script:
          word_count_target: 320
          word_count_tolerance: 60
          enable_critique_pass: true
          repetition_threshold: 0.85
          min_beats: 8
          max_beats: 15
          words_per_beat: 30
        flux:
          steps: 4
          guidance: 3.5
          width: 1280
          height: 720
        assemble:
          output_width: 1920
          output_height: 1080
          shot_crossfade_ms: 350
          music_duck_db: -18
          music_silence_db: -8
          fade_in_s: 1
          fade_out_s: 1
        captions:
          burn_in: false
          font: Cairo-Bold
          font_size: 60
        kie:
          model: veo3
          num_clips: 8
          clip_duration_s: 8
          aspect_ratio: "9:16"
          cost_per_second_usd: 0.40
          max_spend_usd: 50.00
          poll_interval_s: 5
          poll_timeout_s: 300
          flux_model: flux-1.1-pro
          flux_cost_per_image_usd: 0.05
    """))
    cfg = load_config(cfg_path)
    assert cfg.voice.provider == "elevenlabs"
    assert cfg.voice.elevenlabs_voice_id == "21m00Tcm4TlvDq8ikWAM"
    assert cfg.voice.fallback_to_edge_tts is True
    assert cfg.script.min_beats == 8
    assert cfg.script.max_beats == 15
    assert cfg.kie.model == "veo3"
    assert cfg.kie.flux_model == "flux-1.1-pro"
    assert cfg.kie.flux_cost_per_image_usd == 0.05
    assert cfg.kie.max_spend_usd == 50.00
```

- [ ] **Step 2: Run, verify failure**

```bash
uv run pytest tests/test_config.py::test_load_full_config -v
```
Expected: `TypeError` on missing dataclass fields, OR `KeyError` from `raw["voice"]["provider"]`.

- [ ] **Step 3: Update `pipeline/config.py`**

Replace the relevant dataclasses:

```python
@dataclass(frozen=True)
class VoiceConfig:
    provider: str = "edge_tts"      # "edge_tts" | "elevenlabs"
    name: str = "ar-EG-SalmaNeural"  # Edge TTS voice name (legacy field)
    rate: str = "+0%"
    pitch: str = "+0Hz"
    # ElevenLabs-specific
    elevenlabs_voice_id: str = ""
    elevenlabs_model: str = "eleven_multilingual_v2"
    fallback_to_edge_tts: bool = True


@dataclass(frozen=True)
class ScriptConfig:
    word_count_target: int
    word_count_tolerance: int
    enable_critique_pass: bool
    repetition_threshold: float
    # Tier-3 variable-length beats
    min_beats: int = 8
    max_beats: int = 15
    words_per_beat: int = 30


@dataclass(frozen=True)
class KieConfig:
    """Kie.ai video-generation config."""
    model: str
    num_clips: int                 # legacy / fallback default; writer picks per-story
    clip_duration_s: int
    aspect_ratio: str
    cost_per_second_usd: float
    max_spend_usd: float
    poll_interval_s: int
    poll_timeout_s: int
    # Tier-3 Flux character sheet
    flux_model: str = "flux-1.1-pro"
    flux_cost_per_image_usd: float = 0.05
```

- [ ] **Step 4: Update shipped `config.yaml`**

Replace the `voice:` and `kie:` sections, add `min_beats`/`max_beats` to `script:`:

```yaml
voice:
  provider: elevenlabs           # tier-3 default; falls back to edge_tts if no key
  name: ar-EG-SalmaNeural
  rate: "+0%"
  pitch: "+0Hz"
  elevenlabs_voice_id: 21m00Tcm4TlvDq8ikWAM   # placeholder; user supplies from dashboard
  elevenlabs_model: eleven_multilingual_v2
  fallback_to_edge_tts: true

script:
  word_count_target: 320
  word_count_tolerance: 60
  enable_critique_pass: true
  repetition_threshold: 0.85
  min_beats: 8
  max_beats: 15
  words_per_beat: 30

kie:
  model: veo3                    # full quality, was veo3_fast
  num_clips: 8                   # default; writer overrides per-story
  clip_duration_s: 8
  aspect_ratio: "9:16"
  cost_per_second_usd: 0.40      # Veo 3 full pricing
  max_spend_usd: 50.00           # buffer for 15-clip / 120s tragedy
  poll_interval_s: 5
  poll_timeout_s: 300
  flux_model: flux-1.1-pro
  flux_cost_per_image_usd: 0.05
```

- [ ] **Step 5: Run config tests + full suite**

```bash
uv run pytest tests/test_config.py -v
uv run pytest --tb=no -q
```
Expected: 3 config tests pass. Full suite ≥ 114.

- [ ] **Step 6: Commit**

```bash
git add pipeline/config.py config.yaml tests/test_config.py
git commit -m "feat(config): voice provider routing + flux + variable beats"
```

---

## Task 3: Implement `pipeline/elevenlabs.py` HTTP client

**Files:**
- Create: `pipeline/elevenlabs.py`
- Create: `tests/test_elevenlabs.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_elevenlabs.py`:

```python
"""ElevenLabs TTS client tests. Real HTTP is replaced via monkeypatch."""
from __future__ import annotations

from pathlib import Path

import pytest

from pipeline import elevenlabs as el_mod
from pipeline.elevenlabs import ElevenLabsClient, ElevenLabsError


def _client() -> ElevenLabsClient:
    return ElevenLabsClient(api_key="k")


def test_init_requires_api_key(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    with pytest.raises(ElevenLabsError):
        ElevenLabsClient()


def test_synthesize_writes_mp3(monkeypatch, tmp_path: Path):
    """submit + download path: returns the bytes written."""
    captured: dict = {}

    def fake_post(self, path, body):
        captured["path"] = path
        captured["body"] = body
        return b"\xff\xfb\x90\x00" + b"\x00" * 100  # valid mp3-ish prefix

    monkeypatch.setattr(ElevenLabsClient, "_post_audio", fake_post)
    out = tmp_path / "narration.mp3"
    _client().synthesize(
        text="مرحبا يا صديقي",
        voice_id="vid-123",
        model="eleven_multilingual_v2",
        out_path=out,
    )
    assert out.exists()
    assert out.stat().st_size > 0
    assert captured["path"] == "/v1/text-to-speech/vid-123"
    assert captured["body"]["text"] == "مرحبا يا صديقي"
    assert captured["body"]["model_id"] == "eleven_multilingual_v2"
    assert captured["body"]["voice_settings"]["stability"] == 0.5


def test_synthesize_retries_then_succeeds(monkeypatch, tmp_path: Path):
    calls = {"n": 0}

    def flaky(self, path, body):
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("transient")
        return b"\xff\xfb\x90\x00"

    monkeypatch.setattr(ElevenLabsClient, "_post_audio", flaky)
    monkeypatch.setattr(el_mod, "_SLEEP", lambda _s: None)
    _client().synthesize(text="hi", voice_id="v", model="m",
                          out_path=tmp_path / "n.mp3")
    assert calls["n"] == 3


def test_synthesize_raises_after_max_retries(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(ElevenLabsClient, "_post_audio",
                        lambda self, path, body: (_ for _ in ()).throw(RuntimeError("permanent")))
    monkeypatch.setattr(el_mod, "_SLEEP", lambda _s: None)
    with pytest.raises(ElevenLabsError, match="synthesize failed"):
        _client().synthesize(text="hi", voice_id="v", model="m",
                              out_path=tmp_path / "n.mp3")
```

- [ ] **Step 2: Run, verify failure**

```bash
uv run pytest tests/test_elevenlabs.py -v
```
Expected: `ImportError: No module named 'pipeline.elevenlabs'`.

- [ ] **Step 3: Implement `pipeline/elevenlabs.py`**

```python
"""ElevenLabs TTS client.

Uses the `xi-api-key` header (NOT Bearer). POST returns raw mp3 bytes
streamed from the API; we write to disk.

Same retry-with-backoff pattern as pipeline/kie.py and pipeline/llm_groq.py.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import requests

_SLEEP = time.sleep
_MAX_RETRIES = 3
_BACKOFF_S = (1, 5, 30)

BASE_URL = os.environ.get("ELEVENLABS_BASE_URL", "https://api.elevenlabs.io")


class ElevenLabsError(RuntimeError):
    pass


class ElevenLabsClient:
    """Minimal sync client for ElevenLabs TTS."""

    def __init__(self, api_key: str | None = None, base_url: str = BASE_URL):
        key = api_key or os.environ.get("ELEVENLABS_API_KEY")
        if not key:
            raise ElevenLabsError("ELEVENLABS_API_KEY not set")
        self._key = key
        self._base = base_url.rstrip("/")

    def synthesize(
        self, text: str, voice_id: str, model: str, out_path: Path,
        stability: float = 0.5, similarity_boost: float = 0.75,
    ) -> None:
        """POST /v1/text-to-speech/{voice_id} → write mp3 to out_path. Retries."""
        body = {
            "text": text,
            "model_id": model,
            "voice_settings": {
                "stability": stability,
                "similarity_boost": similarity_boost,
            },
        }
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                audio = self._post_audio(f"/v1/text-to-speech/{voice_id}", body)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(audio)
                return
            except Exception as e:
                last_exc = e
                if attempt < _MAX_RETRIES - 1:
                    _SLEEP(_BACKOFF_S[attempt])
        raise ElevenLabsError(f"synthesize failed after {_MAX_RETRIES} attempts: {last_exc}")

    def _post_audio(self, path: str, body: dict) -> bytes:
        url = f"{self._base}{path}"
        resp = requests.post(
            url, json=body,
            headers={"xi-api-key": self._key, "Content-Type": "application/json",
                     "Accept": "audio/mpeg"},
            timeout=120,
        )
        if resp.status_code >= 400:
            raise ElevenLabsError(f"POST {path} → {resp.status_code}: {resp.text[:500]}")
        return resp.content
```

- [ ] **Step 4: Run tests; full suite**

```bash
uv run pytest tests/test_elevenlabs.py -v
uv run pytest --tb=no -q
```
Expected: 4 ElevenLabs tests pass. Full suite ≥ 118.

- [ ] **Step 5: Commit**

```bash
git add pipeline/elevenlabs.py tests/test_elevenlabs.py
git commit -m "feat(elevenlabs): TTS client with retry-with-backoff"
```

---

## Task 4: Refactor `pipeline/voice.py` into a provider router

`generate_narration()` keeps its existing signature but dispatches to ElevenLabs or Edge TTS based on `provider` argument. Old callers keep working.

**Files:**
- Modify: `pipeline/voice.py`
- Modify: `tests/test_voice.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_voice.py`:

```python
def test_generate_narration_dispatches_to_elevenlabs(monkeypatch, tmp_run_dir: Path,
                                                       fixtures_dir: Path):
    """provider='elevenlabs' must call ElevenLabsClient.synthesize, not edge-tts."""
    sample = (fixtures_dir / "narration_sample.mp3").read_bytes()
    captured: dict = {}

    class FakeEL:
        def synthesize(self, text, voice_id, model, out_path, **kw):
            captured["text"] = text
            captured["voice_id"] = voice_id
            captured["out"] = out_path
            out_path.write_bytes(sample)

    monkeypatch.setattr("pipeline.voice._build_elevenlabs", lambda: FakeEL())

    out_mp3 = tmp_run_dir / "narration.mp3"
    out_timings = tmp_run_dir / "word_timings.json"
    from pipeline.voice import generate_narration
    generate_narration(
        text="مرحبا",
        voice="ar-EG-SalmaNeural", rate="+0%", pitch="+0Hz",
        mp3_path=out_mp3, timings_path=out_timings,
        provider="elevenlabs",
        elevenlabs_voice_id="vid-1",
        elevenlabs_model="eleven_multilingual_v2",
    )
    assert out_mp3.exists()
    assert captured["voice_id"] == "vid-1"
    assert captured["text"] == "مرحبا"
    # Synthetic timings still written (Whisper align stage refines them later)
    import json
    timings = json.loads(out_timings.read_text(encoding="utf-8"))
    assert len(timings) >= 1


def test_generate_narration_falls_back_to_edge_tts_when_no_eleven_key(
    monkeypatch, tmp_run_dir: Path, fixtures_dir: Path,
):
    """provider='elevenlabs' but no key → fall back to edge_tts when fallback=True."""
    sample = (fixtures_dir / "narration_sample.mp3").read_bytes()

    def fake_build_el():
        from pipeline.elevenlabs import ElevenLabsError
        raise ElevenLabsError("ELEVENLABS_API_KEY not set")

    def fake_edge(text, voice, rate, pitch, mp3_path):
        mp3_path.write_bytes(sample)
        return [{"word": "ك", "offset_ms": 0, "duration_ms": 100}]

    monkeypatch.setattr("pipeline.voice._build_elevenlabs", fake_build_el)
    monkeypatch.setattr("pipeline.voice._synthesize", fake_edge)

    from pipeline.voice import generate_narration
    generate_narration(
        text="مرحبا",
        voice="ar-EG-SalmaNeural", rate="+0%", pitch="+0Hz",
        mp3_path=tmp_run_dir / "n.mp3",
        timings_path=tmp_run_dir / "t.json",
        provider="elevenlabs",
        elevenlabs_voice_id="vid-1",
        elevenlabs_model="eleven_multilingual_v2",
        fallback_to_edge_tts=True,
    )
    assert (tmp_run_dir / "n.mp3").exists()
```

- [ ] **Step 2: Run, verify failure**

```bash
uv run pytest tests/test_voice.py::test_generate_narration_dispatches_to_elevenlabs -v
```
Expected: `TypeError: generate_narration() got an unexpected keyword argument 'provider'`.

- [ ] **Step 3: Refactor `pipeline/voice.py`**

Add at the bottom of `pipeline/voice.py`:

```python
def _build_elevenlabs():
    """Indirection so tests can monkeypatch."""
    from pipeline.elevenlabs import ElevenLabsClient
    return ElevenLabsClient()
```

Replace the existing `generate_narration` with the routing version:

```python
def generate_narration(
    text: str,
    voice: str,
    rate: str,
    pitch: str,
    mp3_path: Path,
    timings_path: Path,
    *,
    provider: str = "edge_tts",
    elevenlabs_voice_id: str = "",
    elevenlabs_model: str = "eleven_multilingual_v2",
    fallback_to_edge_tts: bool = True,
) -> None:
    """Resumable: if both outputs present and timings non-empty, skip.

    provider:
      - "edge_tts"    — original Edge TTS path (free, lower quality)
      - "elevenlabs"  — ElevenLabs Multilingual v2 (paid, natural voice)

    Whichever provider is used, we always write a synthesized timings file
    (duration / word count). The Whisper align stage in run.py refines these
    into accurate per-word timings before captions are rendered.
    """
    # Resume guard
    if mp3_path.exists() and timings_path.exists():
        try:
            if json.loads(timings_path.read_text(encoding="utf-8")):
                return
        except json.JSONDecodeError:
            pass

    # 1. Produce mp3
    if not mp3_path.exists():
        if provider == "elevenlabs":
            try:
                client = _build_elevenlabs()
                client.synthesize(
                    text=text, voice_id=elevenlabs_voice_id,
                    model=elevenlabs_model, out_path=mp3_path,
                )
            except Exception as e:
                if not fallback_to_edge_tts:
                    raise
                print(f"[voice] elevenlabs failed ({type(e).__name__}: {e}); "
                      f"falling back to edge_tts")
                ssml_text = inject_ssml_pauses(text)
                _synthesize(ssml_text, voice, rate, pitch, mp3_path)
        else:
            ssml_text = inject_ssml_pauses(text)
            _synthesize(ssml_text, voice, rate, pitch, mp3_path)

    # 2. Write a placeholder timings file. The align stage will overwrite
    #    this with Whisper-derived ms-precise timings before captions render.
    duration_ms = _audio_duration_ms(mp3_path)
    timings = _synthesize_timings_from_duration(text, duration_ms)
    timings_path.write_text(
        json.dumps(timings, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
```

- [ ] **Step 4: Run all voice tests + full suite**

```bash
uv run pytest tests/test_voice.py -v
uv run pytest --tb=no -q
```
Expected: 7 prior + 2 new = 9 voice tests pass. Full suite ≥ 120.

- [ ] **Step 5: Commit**

```bash
git add pipeline/voice.py tests/test_voice.py
git commit -m "feat(voice): provider router (elevenlabs | edge_tts) with fallback"
```

---

## Task 5: Implement `pipeline/align.py` (Whisper force-alignment)

**Files:**
- Create: `pipeline/align.py`
- Create: `tests/test_align.py`
- Modify: `pyproject.toml` (add `openai-whisper` dep)

- [ ] **Step 1: Add Whisper dependency**

In `pyproject.toml` under `[project] dependencies`, add `"openai-whisper>=20240930"`. Then:

```bash
uv sync
```

Expected: `Resolved ... packages` and Whisper available.

- [ ] **Step 2: Write failing test**

Create `tests/test_align.py`:

```python
"""Whisper-based forced-alignment tests. Whisper itself is monkeypatched."""
from __future__ import annotations

from pathlib import Path

import pytest

from pipeline import align as align_mod
from pipeline.align import align_arabic
from pipeline.types import WordTiming


def test_align_returns_wordtimings_in_order(monkeypatch, tmp_path: Path):
    """The aligner returns one WordTiming per word, monotonic offsets."""
    audio = tmp_path / "n.mp3"
    audio.write_bytes(b"\xff\xfb\x90\x00")  # not real audio; whisper is mocked

    fake_result = {
        "language": "ar",
        "segments": [
            {
                "start": 0.00,
                "end": 1.50,
                "words": [
                    {"word": "كنتُ", "start": 0.00, "end": 0.50},
                    {"word": "وحيداً", "start": 0.55, "end": 1.05},
                    {"word": "هناك.", "start": 1.10, "end": 1.50},
                ],
            }
        ],
    }

    class FakeModel:
        def transcribe(self, audio_path, **kw):
            assert kw.get("language") == "ar"
            assert kw.get("word_timestamps") is True
            return fake_result

    monkeypatch.setattr(align_mod, "_load_whisper", lambda model_name: FakeModel())
    timings = align_arabic(audio, expected_text="كنتُ وحيداً هناك.")

    assert len(timings) == 3
    assert all(isinstance(t, WordTiming) for t in timings)
    assert timings[0].word == "كنتُ"
    assert timings[0].offset_ms == 0
    assert timings[0].duration_ms == 500
    assert timings[1].offset_ms == 550
    # Monotonic
    for i in range(1, len(timings)):
        assert timings[i].offset_ms >= timings[i - 1].offset_ms


def test_align_falls_back_when_whisper_returns_no_words(monkeypatch, tmp_path: Path):
    """If Whisper returns segments without word-level data, fall back to even-split."""
    audio = tmp_path / "n.mp3"
    audio.write_bytes(b"\xff\xfb\x90\x00")

    class FakeModel:
        def transcribe(self, audio_path, **kw):
            return {"language": "ar", "segments": []}

    monkeypatch.setattr(align_mod, "_load_whisper", lambda model_name: FakeModel())
    monkeypatch.setattr(align_mod, "_audio_duration_s", lambda p: 6.0)

    text = "كلمة1 كلمة2 كلمة3"
    timings = align_arabic(audio, expected_text=text)
    assert len(timings) == 3
    assert timings[0].offset_ms == 0
    # Approximately 2-second slices
    assert 1900 <= timings[0].duration_ms <= 2100
```

- [ ] **Step 3: Run, verify failure**

```bash
uv run pytest tests/test_align.py -v
```
Expected: `ImportError: No module named 'pipeline.align'`.

- [ ] **Step 4: Implement `pipeline/align.py`**

```python
"""Whisper-based force-alignment of Arabic narration audio.

Given the generated narration mp3 and the original Arabic text, produce
ms-precise word timings by transcribing the audio with Whisper's word_timestamps
mode. Whisper local model `small` is the default — accurate enough for Arabic
TikTok captions and runs in ~30s on M3 Pro.

If Whisper returns no word-level data (rare, on very short or noisy audio),
fall back to evenly distributing the expected words across the audio duration.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from pipeline.types import WordTiming

_DEFAULT_MODEL = "small"


def _load_whisper(model_name: str):
    """Module-level indirection so tests can monkeypatch."""
    import whisper
    return whisper.load_model(model_name)


def _audio_duration_s(path: Path) -> float:
    out = subprocess.check_output([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "csv=p=0", str(path),
    ], text=True).strip()
    return float(out)


def align_arabic(
    audio_path: Path, expected_text: str, model: str = _DEFAULT_MODEL,
) -> list[WordTiming]:
    """Transcribe audio with Whisper word_timestamps and produce ms-precise word timings.

    `expected_text` is the original Arabic narration; we use Whisper's transcript
    primarily for the timing data and don't insist Whisper got the words right
    (Arabic transcription is imperfect at the `small` size).
    """
    m = _load_whisper(model)
    result = m.transcribe(
        str(audio_path),
        language="ar",
        word_timestamps=True,
        verbose=False,
    )

    timings: list[WordTiming] = []
    for seg in result.get("segments", []):
        for w in seg.get("words", []) or []:
            word = str(w.get("word", "")).strip()
            start = float(w.get("start", 0.0))
            end = float(w.get("end", start))
            if not word:
                continue
            offset_ms = int(start * 1000)
            duration_ms = max(int((end - start) * 1000), 1)
            timings.append(WordTiming(
                word=word, offset_ms=offset_ms, duration_ms=duration_ms,
            ))

    if timings:
        return timings

    # Fallback: even split across audio duration
    words = [w for w in expected_text.split() if w.strip()]
    if not words:
        return []
    total_ms = int(_audio_duration_s(audio_path) * 1000)
    per_word = max(total_ms // len(words), 1)
    return [
        WordTiming(word=w, offset_ms=i * per_word, duration_ms=per_word)
        for i, w in enumerate(words)
    ]
```

- [ ] **Step 5: Run align tests + full suite**

```bash
uv run pytest tests/test_align.py -v
uv run pytest --tb=no -q
```
Expected: 2 align tests pass. Full suite ≥ 122.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock pipeline/align.py tests/test_align.py
git commit -m "feat(align): Whisper force-alignment module for Arabic narration"
```

---

## Task 6: Add Flux endpoint methods to `pipeline/kie.py`

**Files:**
- Modify: `pipeline/kie.py`
- Modify: `tests/test_kie.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_kie.py`:

```python
def test_submit_flux_image_job_sends_correct_body(monkeypatch):
    captured: dict = {}

    def fake_post(self, path, body):
        captured["path"] = path
        captured["body"] = body
        return {"code": 200, "data": {"taskId": "flux_task_x"}}

    monkeypatch.setattr(KieClient, "_post_json", fake_post)
    c = _client()
    task_id = c.submit_flux_image_job(
        prompt="character sheet of fruit characters",
        model="flux-1.1-pro",
        aspect_ratio="9:16",
    )
    assert task_id == "flux_task_x"
    assert captured["path"] == "/api/v1/flux/generate"
    assert captured["body"]["model"] == "flux-1.1-pro"
    assert captured["body"]["prompt"].startswith("character sheet")
    assert captured["body"]["aspectRatio"] == "9:16"


def test_poll_flux_returns_image_url(monkeypatch):
    """When successFlag=1, fullResultUrls[0] is the PNG URL."""
    monkeypatch.setattr(
        KieClient, "poll_job",
        lambda self, jid: {"data": {"successFlag": 1,
                                     "response": {"fullResultUrls": ["https://cdn/x.png"]}}},
    )
    monkeypatch.setattr(kie_mod, "_SLEEP", lambda _s: None)
    assert _client().wait_for_video("flux_task_x") == "https://cdn/x.png"
```

- [ ] **Step 2: Run, verify failure**

```bash
uv run pytest tests/test_kie.py::test_submit_flux_image_job_sends_correct_body -v
```
Expected: `AttributeError: 'KieClient' object has no attribute 'submit_flux_image_job'`.

- [ ] **Step 3: Add Flux method to `KieClient`**

In `pipeline/kie.py`, near `submit_video_job`, add:

```python
FLUX_SUBMIT_PATH = os.environ.get("KIE_FLUX_SUBMIT_PATH", "/api/v1/flux/generate")
```

Inside `KieClient`, add:

```python
    def submit_flux_image_job(
        self,
        prompt: str,
        model: str = "flux-1.1-pro",
        aspect_ratio: str = "9:16",
        image_urls: list[str] | None = None,
    ) -> str:
        """Submit a Flux text-to-image (or image-to-image) job; return taskId.

        Same poll endpoint and response shape as Veo (record-info), so callers
        can use the existing wait_for_video to retrieve the image URL.
        """
        body: dict = {
            "model": model,
            "prompt": prompt,
            "aspectRatio": aspect_ratio,
        }
        if image_urls:
            body["imageUrls"] = image_urls
        resp = self._post_json(FLUX_SUBMIT_PATH, body)
        data = resp.get("data") or {}
        task_id = data.get("taskId") or resp.get("taskId")
        if not task_id:
            raise KieError(f"flux submit response missing taskId: {resp}")
        return str(task_id)
```

- [ ] **Step 4: Run kie tests + full suite**

```bash
uv run pytest tests/test_kie.py -v
uv run pytest --tb=no -q
```
Expected: previous kie tests + 2 new pass. Full suite ≥ 124.

- [ ] **Step 5: Commit**

```bash
git add pipeline/kie.py tests/test_kie.py
git commit -m "feat(kie): submit_flux_image_job for character sheets"
```

---

## Task 7: Add `submit_image_to_video_job` for Veo `REFERENCE_2_VIDEO` mode

**Files:**
- Modify: `pipeline/kie.py`
- Modify: `tests/test_kie.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_kie.py`:

```python
def test_submit_reference_video_job_sends_image_urls(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        KieClient, "_post_json",
        lambda self, p, b: captured.update(path=p, body=b) or
        {"code": 200, "data": {"taskId": "ref_task_x"}},
    )
    c = _client()
    task_id = c.submit_video_job(
        prompt="lemon mother gives coins to strawberry son",
        model="veo3", aspect_ratio="9:16", seed=0,
        image_urls=["https://cdn/character_sheet.png",
                    "https://cdn/last_frame_clip_2.png"],
        generation_type="REFERENCE_2_VIDEO",
    )
    assert task_id == "ref_task_x"
    assert captured["body"]["generationType"] == "REFERENCE_2_VIDEO"
    assert captured["body"]["imageUrls"] == [
        "https://cdn/character_sheet.png",
        "https://cdn/last_frame_clip_2.png",
    ]
```

- [ ] **Step 2: Run, verify failure**

```bash
uv run pytest tests/test_kie.py::test_submit_reference_video_job_sends_image_urls -v
```
Expected: `TypeError: submit_video_job() got an unexpected keyword argument 'image_urls'`.

- [ ] **Step 3: Extend `submit_video_job`**

Replace `submit_video_job` body in `pipeline/kie.py`:

```python
    def submit_video_job(
        self,
        prompt: str,
        model: str,
        aspect_ratio: str,
        seed: int | None = None,           # ignored
        negative_prompt: str | None = None,  # ignored
        duration_s: int | None = None,       # ignored
        generation_type: str = "TEXT_2_VIDEO",
        resolution: str = "720p",
        image_urls: list[str] | None = None,  # NEW
    ) -> str:
        """Submit a Veo job; return the taskId.

        For REFERENCE_2_VIDEO / FIRST_AND_LAST_FRAMES_2_VIDEO modes, pass
        `image_urls` (a list of public-accessible image URLs).
        """
        body: dict = {
            "model": model,
            "prompt": prompt,
            "aspectRatio": aspect_ratio,
            "generationType": generation_type,
            "resolution": resolution,
        }
        if image_urls:
            body["imageUrls"] = image_urls
        resp = self._post_json(SUBMIT_PATH, body)
        data = resp.get("data") or {}
        task_id = data.get("taskId") or resp.get("taskId") or data.get("task_id")
        if not task_id:
            raise KieError(f"submit response missing taskId: {resp}")
        return str(task_id)
```

- [ ] **Step 4: Run + commit**

```bash
uv run pytest tests/test_kie.py -v
uv run pytest --tb=no -q
git add pipeline/kie.py tests/test_kie.py
git commit -m "feat(kie): support image_urls + generation_type for REFERENCE_2_VIDEO"
```

---

## Task 8: Implement `pipeline/character_sheet.py`

**Files:**
- Create: `pipeline/character_sheet.py`
- Create: `tests/test_character_sheet.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_character_sheet.py`:

```python
"""Character-sheet stage tests."""
from __future__ import annotations

from pathlib import Path

import pytest

from pipeline import character_sheet as cs_mod
from pipeline.character_sheet import generate_character_sheet
from pipeline.kie import KieClient


def _client() -> KieClient:
    return KieClient(api_key="k")


def test_generates_when_missing(monkeypatch, tmp_path: Path, fixtures_dir: Path):
    sample = (fixtures_dir / "pixel.png").read_bytes()
    monkeypatch.setattr(KieClient, "submit_flux_image_job",
                        lambda self, **kw: "flux_task_id")
    monkeypatch.setattr(KieClient, "wait_for_video",
                        lambda self, jid, **kw: "https://cdn/cs.png")

    def fake_download(self, url, out):
        out.write_bytes(sample)

    monkeypatch.setattr(KieClient, "_download", fake_download)
    monkeypatch.setattr(cs_mod, "_SLEEP", lambda _s: None)

    out = tmp_path / "character_sheet.png"
    generate_character_sheet(
        client=_client(),
        out_path=out,
        global_setting="anthropomorphic fruit characters family",
        model="flux-1.1-pro",
        poll_interval_s=1, poll_timeout_s=10,
    )
    assert out.exists()
    assert out.stat().st_size > 0


def test_skips_when_already_present(monkeypatch, tmp_path: Path):
    """Idempotent: if file exists, don't call Flux again."""
    out = tmp_path / "cs.png"
    out.write_bytes(b"existing")
    called = {"n": 0}
    monkeypatch.setattr(KieClient, "submit_flux_image_job",
                        lambda self, **kw: called.__setitem__("n", called["n"] + 1) or "x")

    generate_character_sheet(
        client=_client(), out_path=out,
        global_setting="x", model="flux-1.1-pro",
        poll_interval_s=1, poll_timeout_s=10,
    )
    assert called["n"] == 0
```

- [ ] **Step 2: Run, verify failure**

```bash
uv run pytest tests/test_character_sheet.py -v
```
Expected: `ImportError`.

- [ ] **Step 3: Implement `pipeline/character_sheet.py`**

```python
"""Stage X (Tier-3): Generate a single Flux character sheet for a video.

The sheet is a 1024×1024 image showing all the named anthropomorphic fruit
characters (lemon mother, strawberry son child + adult, apple doctor, etc.)
together. It's then passed via `imageUrls` as a reference to every Veo clip
to anchor character appearance across all clips.

Idempotent: skips Flux call if `out_path` already exists.
"""
from __future__ import annotations

import time
from pathlib import Path

from pipeline.kie import KieClient

_SLEEP = time.sleep

CHARACTER_SHEET_PROMPT = (
    "Character lineup sheet for a tragic Arabic family-drama animated short. "
    "Five anthropomorphic fruit characters standing side by side, full body, "
    "facing camera, neutral expressions, plain warm-grey background, "
    "consistent 3D Pixar-style rendering, photorealistic CGI textures: "
    "(1) Lemon mother — yellow lemon-shaped head with sad eyes, wearing a black hijab and dark dress; "
    "(2) Strawberry child — small red strawberry head with green leaves on top, wearing blue t-shirt and jeans; "
    "(3) Strawberry adult son — same red strawberry head but with a beard, wearing a traditional thobe; "
    "(4) Apple doctor — red apple head, white doctor coat, stethoscope; "
    "(5) Mango neighbor — orange mango head, casual button-up shirt. "
    "High detail, consistent shading, design-sheet aesthetic. NO text, NO watermark, NO logo."
)


def generate_character_sheet(
    client: KieClient,
    out_path: Path,
    global_setting: str,
    model: str = "flux-1.1-pro",
    poll_interval_s: int = 5,
    poll_timeout_s: int = 300,
) -> None:
    """Submit a Flux job for the character sheet, poll, download to out_path. Idempotent."""
    if out_path.exists():
        return
    job_id = client.submit_flux_image_job(
        prompt=CHARACTER_SHEET_PROMPT,
        model=model,
        aspect_ratio="1:1",
    )
    url = client.wait_for_video(
        job_id, poll_interval_s=poll_interval_s, timeout_s=poll_timeout_s,
    )
    client.download(url, out_path)
```

- [ ] **Step 4: Run + commit**

```bash
uv run pytest tests/test_character_sheet.py -v
uv run pytest --tb=no -q
git add pipeline/character_sheet.py tests/test_character_sheet.py
git commit -m "feat(character_sheet): Flux character lineup for visual cohesion"
```

---

## Task 9: Implement `pipeline/frames.py` (last-frame extraction)

**Files:**
- Create: `pipeline/frames.py`
- Create: `tests/test_frames.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_frames.py`:

```python
"""Last-frame extraction tests."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from pipeline import frames as frames_mod
from pipeline.frames import extract_last_frame


def test_extract_last_frame_invokes_ffmpeg_with_correct_args(monkeypatch, tmp_path: Path):
    captured: dict = {}

    def fake_run(args, check, **kw):
        captured["args"] = args
        Path(args[-1]).write_bytes(b"\x89PNG\r\n\x1a\n")  # PNG magic
        return subprocess.CompletedProcess(args, 0)

    # Make ffprobe return 8.0 sec
    monkeypatch.setattr(frames_mod, "_audio_duration_s", lambda p: 8.0)
    monkeypatch.setattr(subprocess, "run", fake_run)

    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"x")
    out = tmp_path / "last_frame.png"
    extract_last_frame(clip, out)
    assert out.exists()
    args = captured["args"]
    assert args[0] == "ffmpeg"
    # Seek to ~7.9s for an 8s clip (just before the end)
    assert any("7.9" in a for a in args) or any("7.95" in a for a in args)
    assert "-frames:v" in args
    assert "1" in args
```

- [ ] **Step 2: Run, verify failure**

```bash
uv run pytest tests/test_frames.py -v
```
Expected: `ImportError`.

- [ ] **Step 3: Implement `pipeline/frames.py`**

```python
"""Helpers for extracting frames from video clips.

Used by the Tier-3 video stage to chain image-to-video: last frame of clip N
becomes the first-frame reference for clip N+1.
"""
from __future__ import annotations

import subprocess
from pathlib import Path


def _audio_duration_s(path: Path) -> float:
    out = subprocess.check_output([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "csv=p=0", str(path),
    ], text=True).strip()
    return float(out)


def extract_last_frame(clip_path: Path, out_path: Path) -> None:
    """Pull the very last frame of a video clip and save as PNG.

    Seeks to (duration - 0.05s) and grabs one frame. The 50ms buffer avoids
    "no frame at exact end" issues with some codecs.
    """
    duration = _audio_duration_s(clip_path)
    seek_t = max(duration - 0.05, 0.0)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-ss", f"{seek_t:.2f}",
        "-i", str(clip_path),
        "-frames:v", "1",
        "-q:v", "2",
        str(out_path),
    ], check=True)
```

- [ ] **Step 4: Run + commit**

```bash
uv run pytest tests/test_frames.py -v
uv run pytest --tb=no -q
git add pipeline/frames.py tests/test_frames.py
git commit -m "feat(frames): last-frame extraction for image-to-video chaining"
```

---

## Task 10: Refactor `pipeline/video.py` for image-referenced chained generation

**Files:**
- Modify: `pipeline/video.py`
- Modify: `tests/test_video.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_video.py`:

```python
def test_generate_clips_uses_reference_2_video_with_character_sheet(
    monkeypatch, tmp_path: Path, fixtures_dir: Path,
):
    """Each clip must be submitted as REFERENCE_2_VIDEO with character_sheet in image_urls."""
    submit_calls: list[dict] = []

    def fake_submit(self, **kw):
        submit_calls.append(kw)
        return f"task_{len(submit_calls)}"

    monkeypatch.setattr(KieClient, "submit_video_job", fake_submit)
    monkeypatch.setattr(KieClient, "wait_for_video",
                        lambda self, jid, **kw: f"https://cdn/{jid}.mp4")

    def fake_dl(self, url, out_path):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"\x00\x00\x00\x18ftypmp42")

    monkeypatch.setattr(KieClient, "_download", fake_dl)
    monkeypatch.setattr("pipeline.video._extract_last_frame",
                        lambda clip, out: out.write_bytes(b"\x89PNG\r\n\x1a\n"))
    monkeypatch.setattr("pipeline.video._upload_image_get_url",
                        lambda path: f"https://cdn/upl/{path.name}")

    clips_dir = tmp_path / "clips"
    last_frames_dir = tmp_path / "last_frames"
    spend = tmp_path / "spend.json"
    char_sheet = tmp_path / "character_sheet.png"
    char_sheet.write_bytes(b"\x89PNG\r\n\x1a\n")

    from pipeline.video import generate_clips_chained
    generate_clips_chained(
        client=KieClient(api_key="k"),
        script=_script(3),
        clips_dir=clips_dir, last_frames_dir=last_frames_dir,
        spend_log_path=spend,
        character_sheet_path=char_sheet,
        model="veo3", aspect_ratio="9:16",
        cost_per_second_usd=0.40, max_spend_usd=20.0,
        poll_interval_s=1, poll_timeout_s=10,
    )
    # 3 clips submitted
    assert len(submit_calls) == 3
    # Every submit has REFERENCE_2_VIDEO
    for call in submit_calls:
        assert call["generation_type"] == "REFERENCE_2_VIDEO"
        # Character sheet always in image_urls
        assert any("character_sheet" in u or "/upl/" in u for u in call["image_urls"])
    # Clips 2 and 3 also reference last frame of previous
    assert len(submit_calls[1]["image_urls"]) >= 2
    assert len(submit_calls[2]["image_urls"]) >= 2


def test_generate_clips_chained_uses_per_beat_duration(monkeypatch, tmp_path: Path):
    """duration_seconds passed to Veo must come from beat.clip_duration_s."""
    durations: list = []

    def fake_submit(self, **kw):
        durations.append(kw.get("duration_s"))
        return f"task_{len(durations)}"

    monkeypatch.setattr(KieClient, "submit_video_job", fake_submit)
    monkeypatch.setattr(KieClient, "wait_for_video",
                        lambda self, jid, **kw: f"https://cdn/{jid}.mp4")
    monkeypatch.setattr(KieClient, "_download",
                        lambda self, url, out: out.parent.mkdir(parents=True, exist_ok=True) or
                                                out.write_bytes(b"x"))
    monkeypatch.setattr("pipeline.video._extract_last_frame",
                        lambda clip, out: out.write_bytes(b"x"))
    monkeypatch.setattr("pipeline.video._upload_image_get_url",
                        lambda path: f"https://cdn/{path.name}")

    # Build a script whose beats have varying durations
    s = Script(
        title="t", theme="folkloric", global_setting="x", music_mood="dread",
        beats=(
            Beat(arabic="a", english_motion="m", clip_duration_s=6.0),
            Beat(arabic="b", english_motion="m", clip_duration_s=9.5),
        ),
        story_combined="a b",
        target_duration_s=15.5,
    )

    char_sheet = tmp_path / "cs.png"
    char_sheet.write_bytes(b"x")

    from pipeline.video import generate_clips_chained
    generate_clips_chained(
        client=KieClient(api_key="k"),
        script=s,
        clips_dir=tmp_path / "clips",
        last_frames_dir=tmp_path / "lf",
        spend_log_path=tmp_path / "s.json",
        character_sheet_path=char_sheet,
        model="veo3", aspect_ratio="9:16",
        cost_per_second_usd=0.40, max_spend_usd=20.0,
        poll_interval_s=1, poll_timeout_s=10,
    )
    assert durations == [6.0, 9.5]
```

- [ ] **Step 2: Run, verify failure**

```bash
uv run pytest tests/test_video.py::test_generate_clips_uses_reference_2_video_with_character_sheet -v
```
Expected: `ImportError: cannot import name 'generate_clips_chained' from 'pipeline.video'`.

- [ ] **Step 3: Add `generate_clips_chained` and helpers to `pipeline/video.py`**

Append to `pipeline/video.py`:

```python
def _extract_last_frame(clip_path: Path, out_path: Path) -> None:
    """Indirection over pipeline.frames.extract_last_frame for monkeypatching."""
    from pipeline.frames import extract_last_frame
    extract_last_frame(clip_path, out_path)


def _upload_image_get_url(local_path: Path) -> str:
    """Upload a local image to 0x0.st (free, anonymous, no API key) and return
    the public URL so Kie.ai can fetch it.

    0x0.st is a public pastebin; files stay for ~7 days. We only need them for
    a few minutes (the duration of one Veo job), so this fits.
    Tests monkeypatch this function.
    """
    with local_path.open("rb") as f:
        resp = requests.post(
            "https://0x0.st",
            files={"file": (local_path.name, f, "image/png")},
            headers={"User-Agent": "faceless-pipeline/1.0"},
            timeout=60,
        )
    if resp.status_code >= 400:
        raise RuntimeError(
            f"upload to 0x0.st failed: {resp.status_code}: {resp.text[:200]}"
        )
    return resp.text.strip()


def generate_clips_chained(
    client: KieClient,
    script: Script,
    clips_dir: Path,
    last_frames_dir: Path,
    spend_log_path: Path,
    *,
    character_sheet_path: Path,
    model: str,
    aspect_ratio: str,
    cost_per_second_usd: float,
    max_spend_usd: float,
    poll_interval_s: int,
    poll_timeout_s: int,
    reroll_indices: list[int] | None = None,
) -> None:
    """Tier-3 video stage: REFERENCE_2_VIDEO with character sheet + chained last frames.

    For clip 1: image_urls = [character_sheet]
    For clip N (N>1): image_urls = [character_sheet, last_frame_of_clip_(N-1)]

    Per-beat clip duration from `beat.clip_duration_s`.
    """
    if not script.beats:
        raise ValueError("script has no beats — Tier-3 mode requires beats[]")
    clips_dir.mkdir(parents=True, exist_ok=True)
    last_frames_dir.mkdir(parents=True, exist_ok=True)

    reroll_set = set(reroll_indices or [])

    pending_durations: list[float] = []
    for i, beat in enumerate(script.beats):
        idx = i + 1
        out_path = _clip_filename(clips_dir, idx)
        if not (out_path.exists() and idx not in reroll_set):
            pending_durations.append(beat.clip_duration_s)

    projected = sum(pending_durations) * cost_per_second_usd
    if projected > max_spend_usd:
        raise BudgetExceededError(
            f"projected spend ${projected:.2f} exceeds cap ${max_spend_usd:.2f} "
            f"({len(pending_durations)} clips × ${cost_per_second_usd}/s). "
            f"Override with --max-spend or change config.kie.max_spend_usd."
        )

    sheet_url = _upload_image_get_url(character_sheet_path)
    spend_entries: list[dict] = []
    prev_last_frame_url: str | None = None

    for i, beat in enumerate(script.beats):
        idx = i + 1
        out_path = _clip_filename(clips_dir, idx)
        last_frame_path = last_frames_dir / f"{idx:02d}.png"
        if out_path.exists() and idx not in reroll_set:
            # Already done; still need to ensure last-frame is on disk for next iteration.
            if not last_frame_path.exists():
                _extract_last_frame(out_path, last_frame_path)
            prev_last_frame_url = _upload_image_get_url(last_frame_path)
            continue

        prompt = build_veo_prompt(beat, script.global_setting)
        image_urls = [sheet_url]
        if prev_last_frame_url:
            image_urls.append(prev_last_frame_url)

        job_id = client.submit_video_job(
            prompt=prompt,
            model=model,
            aspect_ratio=aspect_ratio,
            generation_type="REFERENCE_2_VIDEO",
            image_urls=image_urls,
            duration_s=int(beat.clip_duration_s),  # ignored by Veo, kept for API stability
        )
        url = client.wait_for_video(
            job_id, poll_interval_s=poll_interval_s, timeout_s=poll_timeout_s,
        )
        client.download(url, out_path)
        _extract_last_frame(out_path, last_frame_path)
        prev_last_frame_url = _upload_image_get_url(last_frame_path)

        spend_entries.append({
            "clip": idx, "seed": clip_seed(script.title, i),
            "duration_s": beat.clip_duration_s,
            "cost_usd": beat.clip_duration_s * cost_per_second_usd,
            "model": model,
        })

    if spend_entries:
        _record_spend(spend_log_path, spend_entries)
```

- [ ] **Step 4: Run + commit**

```bash
uv run pytest tests/test_video.py -v
uv run pytest --tb=no -q
git add pipeline/video.py tests/test_video.py
git commit -m "feat(video): REFERENCE_2_VIDEO chained generation with character sheet"
```

---

## Task 11: Update `pipeline/script.py` for variable num_beats and target_duration_s

**Files:**
- Modify: `pipeline/script.py`
- Modify: `tests/test_script.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_script.py`:

```python
def test_shorts_writer_picks_num_beats_in_range(fake_gemini):
    """Writer chooses 8-15 beats based on premise; orchestrator reads len(script.beats)."""
    from pipeline.script import generate_shorts_script
    seed = ThemeSeed(theme="folkloric", premise="x")
    fake_gemini.when(lambda p: True, json.dumps({
        "title": "long tragedy",
        "theme": "folkloric",
        "global_setting": "x",
        "music_mood": "dread",
        "target_duration_s": 100,
        "beats": [
            {"arabic": "ج" + str(i), "english_motion": "m", "clip_duration_s": 8.5}
            for i in range(12)
        ],
    }, ensure_ascii=False))
    s = generate_shorts_script(fake_gemini, seed, min_beats=8, max_beats=15,
                                words_per_beat=30)
    assert len(s.beats) == 12
    assert s.target_duration_s == 100
    assert s.beats[0].clip_duration_s == 8.5


def test_shorts_writer_clamps_to_min_beats_when_too_few(fake_gemini):
    """If LLM returns < min_beats, raise — that's a serious failure not silent fallback."""
    from pipeline.script import generate_shorts_script
    import pytest
    seed = ThemeSeed(theme="folkloric", premise="x")
    fake_gemini.when(lambda p: True, json.dumps({
        "title": "x", "theme": "folkloric", "global_setting": "x",
        "music_mood": "dread",
        "beats": [
            {"arabic": f"ج{i}", "english_motion": "m"} for i in range(5)
        ],
    }, ensure_ascii=False))
    with pytest.raises(ValueError, match="below min_beats"):
        generate_shorts_script(fake_gemini, seed, min_beats=8, max_beats=15)
```

- [ ] **Step 2: Run, verify failure**

```bash
uv run pytest tests/test_script.py::test_shorts_writer_picks_num_beats_in_range -v
```
Expected: failure (writer doesn't accept `min_beats`/`max_beats`).

- [ ] **Step 3: Update `SHORTS_WRITER_PROMPT_TEMPLATE` and `generate_shorts_script`**

In `pipeline/script.py`:

Replace `SHORTS_WRITER_PROMPT_TEMPLATE`'s opening line and JSON template:

```python
SHORTS_WRITER_PROMPT_TEMPLATE = """\
اكتب قصة ميلودراما عائلية مأساوية لـ TikTok، طولها بين 60 و 120 ثانية حسب تعقيد القصة.
أنت تختار عدد المشاهد ({min_beats} كحد أدنى، {max_beats} كحد أقصى) وزمن كل مشهد بناء على القصة.

الفرضية: {premise}
الفئة: {theme}

[... rest of the prompt unchanged through the JSON template ...]

أرجع JSON صالح فقط (بدون markdown أو ``` أو شرح) بهذه الحقول بالضبط:
{{
  "title": "عنوان مأساوي قصير",
  "theme": "{theme}",
  "global_setting": "...",
  "music_mood": "drone | dread | cosmic | discovery",
  "target_duration_s": <integer 60..120, your chosen total length>,
  "beats": [
    {{"arabic": "...", "english_motion": "...", "clip_duration_s": <float 6..10, this beat's duration>}},
    ...repeat between {min_beats} and {max_beats} times...
  ]
}}

ملاحظة: عدد البيتات لازم بين {min_beats} و {max_beats}. مجموع clip_duration_s لازم ≈ target_duration_s.
"""
```

Update `build_shorts_writer_prompt`:

```python
def build_shorts_writer_prompt(
    seed: ThemeSeed, min_beats: int = 8, max_beats: int = 15,
    words_per_beat: int = 30,
) -> str:
    min_words_per_beat = max(int(words_per_beat * 0.7), 18)
    min_total_words = min_beats * min_words_per_beat
    return SHORTS_WRITER_PROMPT_TEMPLATE.format(
        premise=seed.premise,
        theme=seed.theme,
        min_beats=min_beats,
        max_beats=max_beats,
        words_per_beat=words_per_beat,
        min_words_per_beat=min_words_per_beat,
        min_total_words=min_total_words,
        global_setting_hint="نفس الإعداد عبر المشاهد",
    )
```

Update `_parse_shorts_script_json` to read `target_duration_s` and per-beat `clip_duration_s`:

```python
    beats: tuple[Beat, ...] = tuple(
        Beat(
            arabic=str(b.get("arabic", "")).strip(),
            english_motion=str(b.get("english_motion", "")).strip(),
            clip_duration_s=float(b.get("clip_duration_s", 8.0)),
        )
        for b in beats_raw
    )
    target_duration_s = float(data.get("target_duration_s", 0.0))
    if target_duration_s <= 0:
        target_duration_s = sum(b.clip_duration_s for b in beats)

    # ... when constructing Script:
    return Script(
        title=...,
        ...
        target_duration_s=target_duration_s,
    )
```

Update `generate_shorts_script`:

```python
def generate_shorts_script(
    gemini, seed: ThemeSeed,
    *,
    min_beats: int = 8, max_beats: int = 15, words_per_beat: int = 30,
    min_total_words: int | None = None, max_expand_retries: int = 2,
) -> Script:
    if min_total_words is None:
        min_total_words = int(min_beats * words_per_beat * 0.7)
    prompt = build_shorts_writer_prompt(
        seed, min_beats=min_beats, max_beats=max_beats, words_per_beat=words_per_beat,
    )
    raw = gemini.complete(prompt, system=SHORTS_WRITER_SYSTEM)
    script = _parse_shorts_script_json(raw, seed)

    if len(script.beats) < min_beats:
        raise ValueError(f"writer returned {len(script.beats)} beats, below min_beats={min_beats}")

    for attempt in range(max_expand_retries):
        total = sum(len(b.arabic.split()) for b in script.beats)
        if total >= min_total_words:
            return script
        print(f"[script] expand pass {attempt+1}/{max_expand_retries}: "
              f"got {total} words, want ≥{min_total_words}")
        try:
            script = _expand_short_script(gemini, script, words_per_beat)
        except Exception as e:
            print(f"[script] expand failed ({type(e).__name__}: {e}); using shorter draft")
            return script
    return script
```

- [ ] **Step 4: Update existing test fixtures that pass `num_beats=4` etc.**

In `tests/test_script.py` other shorts tests, replace `num_beats=N` with `min_beats=1, max_beats=20` to keep them passing on shorter fixture data.

- [ ] **Step 5: Run + commit**

```bash
uv run pytest tests/test_script.py -v
uv run pytest --tb=no -q
git add pipeline/script.py tests/test_script.py
git commit -m "feat(script): variable num_beats 8-15 + per-beat clip_duration_s"
```

---

## Task 12: Update `run.py` orchestrator for new stages

**Files:**
- Modify: `run.py`
- Modify: `tests/test_run_shorts_smoke.py`

- [ ] **Step 1: Write failing smoke test update**

In `tests/test_run_shorts_smoke.py`, the `test_run_shorts_full_pipeline` test must be extended to assert that:
- A `character_sheet.png` is generated
- `align_arabic` is invoked (we monkeypatch it)
- `generate_clips_chained` is called (not the old `generate_clips`)

Edit the existing fake setup:

```python
    # Mock character sheet
    monkeypatch.setattr("pipeline.character_sheet.generate_character_sheet",
                        lambda **kw: kw["out_path"].write_bytes(b"\x89PNG\r\n\x1a\n"))

    # Mock Whisper align — return synthetic timings
    monkeypatch.setattr(
        "pipeline.align.align_arabic",
        lambda audio, expected_text, **kw: [
            type("WT", (), dict(word="x", offset_ms=0, duration_ms=500))()
        ],
    )

    # Mock the new chained video gen
    monkeypatch.setattr(
        "pipeline.video.generate_clips_chained",
        lambda **kw: [
            (kw["clips_dir"] / f"{i+1:02d}.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42")
            for i in range(len(kw["script"].beats))
        ],
    )
```

Add asserts at the end of the test:

```python
    assert (run_dir / "character_sheet.png").exists()
```

- [ ] **Step 2: Run, verify failure**

Expected: AssertionError on `character_sheet.png` not existing.

- [ ] **Step 3: Update `run.py`**

Add imports:

```python
from pipeline.align import align_arabic
from pipeline.character_sheet import generate_character_sheet
from pipeline.video import generate_clips_chained
```

Replace `_stage_video` body to call `generate_clips_chained` in the Tier-3 path. Add a new `_stage_character_sheet` and `_stage_align`:

```python
def _stage_character_sheet(client, cfg, paths, script):
    generate_character_sheet(
        client=client,
        out_path=paths.character_sheet_png,
        global_setting=script.global_setting,
        model=cfg.kie.flux_model,
        poll_interval_s=cfg.kie.poll_interval_s,
        poll_timeout_s=cfg.kie.poll_timeout_s,
    )


def _stage_align(paths, script):
    """Refine word_timings.json with Whisper force-alignment."""
    real_timings = align_arabic(
        audio_path=paths.narration_mp3,
        expected_text=script.story_combined,
    )
    paths.word_timings_json.write_text(
        json.dumps([t.to_dict() for t in real_timings],
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return real_timings
```

In the `--shorts` branch of `main_with_args`, change ordering:

```python
            with log.stage("seed"):
                seed = _stage_seed(args, gemini, log, paths, project_theme_log)
            with log.stage("script"):
                script = _stage_shorts_script(gemini, seed, cfg, paths)
            with log.stage("voice"):
                _stage_shorts_voice(args, cfg, script, paths)
            with log.stage("align"):
                timings = _stage_align(paths, script)
            with log.stage("character_sheet"):
                _stage_character_sheet(_build_kie(), cfg, paths, script)
            with log.stage("video"):
                _stage_video_chained(args, cfg, script, paths)  # NEW helper, calls generate_clips_chained
            with log.stage("music"):
                _stage_music(script, music_bundle, paths)
            with log.stage("captions"):
                burn_ass = _stage_shorts_captions(cfg, timings, paths)
                if args.no_burn_captions:
                    burn_ass = None
            with log.stage("assemble"):
                _stage_shorts_assemble(cfg, script, paths, burn_ass)
```

Implement `_stage_video_chained`:

```python
def _stage_video_chained(args, cfg, script, paths):
    if args.skip_video:
        # Black mp4 placeholder per beat (same approach as old _stage_video).
        import subprocess
        paths.clips_dir.mkdir(parents=True, exist_ok=True)
        for i, beat in enumerate(script.beats):
            p = paths.clips_dir / f"{i+1:02d}.mp4"
            if p.exists():
                continue
            subprocess.run([
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i",
                f"color=c=black:s=1080x1920:d={beat.clip_duration_s}",
                "-f", "lavfi", "-i",
                f"anullsrc=r=24000:cl=stereo:d={beat.clip_duration_s}",
                "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "128k", "-shortest",
                str(p),
            ], check=True)
        return

    reroll = []
    if args.reroll_clips:
        reroll = [int(x) for x in args.reroll_clips.split(",")]
    max_spend = args.max_spend if args.max_spend is not None else cfg.kie.max_spend_usd
    client = _build_kie()
    generate_clips_chained(
        client=client, script=script,
        clips_dir=paths.clips_dir,
        last_frames_dir=paths.last_frames_dir,
        spend_log_path=paths.kie_spend_json,
        character_sheet_path=paths.character_sheet_png,
        model=cfg.kie.model,
        aspect_ratio=cfg.kie.aspect_ratio,
        cost_per_second_usd=cfg.kie.cost_per_second_usd,
        max_spend_usd=max_spend,
        poll_interval_s=cfg.kie.poll_interval_s,
        poll_timeout_s=cfg.kie.poll_timeout_s,
        reroll_indices=reroll,
    )
```

In `_stage_shorts_voice`, pass new provider args:

```python
def _stage_shorts_voice(args, cfg, script, paths):
    voice = args.voice or cfg.voice.name
    generate_narration(
        text=script.story_combined,
        voice=voice, rate=cfg.voice.rate, pitch=cfg.voice.pitch,
        mp3_path=paths.narration_mp3, timings_path=paths.word_timings_json,
        provider=cfg.voice.provider,
        elevenlabs_voice_id=cfg.voice.elevenlabs_voice_id,
        elevenlabs_model=cfg.voice.elevenlabs_model,
        fallback_to_edge_tts=cfg.voice.fallback_to_edge_tts,
    )
```

- [ ] **Step 4: Run + commit**

```bash
uv run pytest --tb=no -q
git add run.py tests/test_run_shorts_smoke.py
git commit -m "feat(run): tier-3 orchestrator (align + character sheet + chained video)"
```

---

## Task 13: Update README/CLAUDE.md and final sanity check

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Document new env vars in CLAUDE.md**

Add a section under "Common commands":

```markdown
## Tier-3 environment variables (Shorts mode)

```bash
# Required
export KIE_API_KEY=<your kie.ai key>
export GROQ_API_KEY=<your groq key>
export ELEVENLABS_API_KEY=<your elevenlabs key>

# Optional — only if your network blocks aiquickdraw.com (UAE etc.)
export KIE_DOWNLOAD_PROXY=https://your-worker.workers.dev
export KIE_DOWNLOAD_PROXY_SECRET=<shared secret>
```

Image uploads (for Veo image-to-video chaining) use 0x0.st by default — anonymous,
no API key needed. Override `pipeline.video._upload_image_get_url` if you'd
rather use Cloudflare R2 / imgbb / your own bucket.

Run a tier-3 video:

```bash
source .env
uv run python run.py --shorts --theme folkloric --seed "أم فقيرة..."
```
```

- [ ] **Step 2: Run full suite one last time**

```bash
uv run pytest -v --tb=short 2>&1 | tail -10
```

Expected: all tests pass (target ≥ 130).

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(claude): document tier-3 env vars + CLI"
```

---

## Done criteria

The Tier-3 implementation is complete when:

- [ ] All 130+ tests pass.
- [ ] User has signed up at https://elevenlabs.io and added `ELEVENLABS_API_KEY` to `.env`.
- [ ] User has topped up Kie.ai to ≥ $50.
- [ ] One real run produces a 60–120 sec mp4 in `out/<run>/final.mp4`, total cost ≤ $50.
      (Image uploads to 0x0.st succeed — verify by hand once at Phase B kickoff.)
- [ ] User watches and judges quality vs @sunstoriz reference. Scope-passes when user says "yes, ship it."

---

## What this plan does NOT cover

Per spec §2 non-goals:

- Lip sync (HeyGen/SadTalker) — Tier 4 future spec.
- Multi-character voice routing.
- Manual scene curation/regeneration UI.
- YouTube/TikTok auto-publishing.
- Multi-channel scheduling.

Each of those is its own brainstorm → spec → plan cycle.
