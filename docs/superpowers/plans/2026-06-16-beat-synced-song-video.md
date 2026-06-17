# Beat-Synced Song Video Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a premium "Cinematic video" mode that turns a song's static cover into a beat-synced multi-scene music video (a bounded pool of ~6–10 art-directed Flux stills, cut/zoom-punched on a tempo grid, with the existing karaoke + watermark overlaid), priced at 3 credits vs the 1-credit static path.

**Architecture:** Three new pipeline modules — `song_beats` (librosa tempo/beat detection), `song_scenes` (a *pure* cut-schedule builder), `song_cinematic` (a single-`filter_complex` ffmpeg assembler, Approach A). The existing static path (`song_assemble.assemble_song_video`) is untouched. `run.py` branches on a new `video_mode` field; the API gates credits and exposes the toggle; Flutter adds the picker. Graceful degradation: beat-detect / scene-image / render failures fall back without losing the run, and a render-failure downgrade refunds the 2-credit surcharge.

**Tech Stack:** Python 3 / FastAPI / ffmpeg / librosa (new) / Pillow / pytest; Flutter / Dart. Repo invariants: `from __future__ import annotations` first line; `pathlib.Path`; absolute imports from `pipeline.`; external services mocked in tests; ffmpeg runs locally on tiny inputs in smoke tests; artifacts resumable (exists → skip).

**Spec:** `docs/superpowers/specs/2026-06-16-beat-synced-song-video-design.md`

---

## File Structure

| File | Create/Modify | Responsibility |
|---|---|---|
| `pipeline/config.py` | Modify | Add 3 cinematic fields to `SongConfig` (with defaults). |
| `config.yaml` | Modify | Add `cinematic_credits_per_song`, `cinematic_pool_size`, `bars_per_cut`. |
| `pipeline/song_scenes.py` | Create | Pure cut-schedule builder + section extraction. No I/O, no ffmpeg. |
| `pipeline/song_beats.py` | Create | librosa tempo/beat detection → `beats.json`; fixed-BPM fallback. |
| `pipeline/song_lyrics.py` | Modify | `SongScript` gains `art_direction` + `scene_prompts`; LLM prompt emits them. |
| `pipeline/song_cover.py` | Modify | Add `generate_scene_images(...)` — render the pool with style-lock. |
| `pipeline/song_assemble.py` | Modify | Extract `build_metadata_args(...)` + `resolve_watermark(...)` for reuse. No behavior change. |
| `pipeline/song_cinematic.py` | Create | `build_filter_complex(...)` (pure) + `assemble_cinematic_song_video(...)` + `assert_playable(...)`. |
| `pipeline/api.py` | Modify | `video_mode` on request/song.json/summary; `/script` cost + `approve` credits branch; downgrade-refund reconciliation. |
| `run.py` | Modify | Cinematic branch: scene-gen, beat-detect stage, assembler branch, degradation + downgrade flag. |
| `pyproject.toml` | Modify | Add `librosa` dependency. |
| `lib/api/client.dart` | Modify | `createSong` accepts `videoMode`. |
| `lib/api/models.dart` | Modify | `SongSummary` + `SongScript` gain `videoMode` / cost fields. |
| `lib/screens/new_song_screen.dart` | Modify | Static/Cinematic segmented toggle; pass `videoMode`. |
| `tests/test_song_scenes.py` | Create | Pure-function coverage (the bulk of testing). |
| `tests/test_song_beats.py` | Create | librosa mocked + fallback. |
| `tests/test_song_cinematic.py` | Create | Pure filtergraph builder + ffmpeg smoke. |
| `tests/test_api.py` | Modify | `video_mode` cost/credit branches. |
| `tests/test_run_song_mode.py` | Modify | Cinematic smoke + degradation. |

---

## Task 1: Config — cinematic fields

**Files:**
- Modify: `pipeline/config.py:85-92`
- Modify: `config.yaml:94-105`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_config.py`:

```python
def test_song_config_has_cinematic_fields(tmp_path):
    from pipeline.config import load_config
    cfg = load_config(Path("config.yaml"))
    assert cfg.song is not None
    assert cfg.song.cinematic_credits_per_song == 3
    assert cfg.song.cinematic_pool_size == 7
    assert cfg.song.bars_per_cut == 4


def test_song_config_cinematic_defaults_when_absent():
    # Old config blocks without the new keys must still load.
    from pipeline.config import SongConfig
    c = SongConfig(
        suno_model="V5_5", suno_cost_usd=0.05,
        cover_flux_model="flux-kontext-max", cover_cost_usd=0.03,
        credits_per_song=1,
    )
    assert c.cinematic_credits_per_song == 3
    assert c.cinematic_pool_size == 7
    assert c.bars_per_cut == 4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py -k cinematic -v`
Expected: FAIL — `AttributeError: ... has no attribute 'cinematic_credits_per_song'` / `TypeError` on constructor.

- [ ] **Step 3: Add the fields**

In `pipeline/config.py`, replace the `SongConfig` body (lines 85–92):

```python
@dataclass(frozen=True)
class SongConfig:
    """AI-song-mode config — Suno + Flux cover + credit pricing."""
    suno_model: str                # Suno model id; V5_5 latest, V4_5 fallback
    suno_cost_usd: float           # per-song flat cost on Kie.ai
    cover_flux_model: str          # Kie.ai Flux model id for covers
    cover_cost_usd: float          # per-image flux cost
    credits_per_song: int          # user-facing price for one static song
    # Cinematic (beat-synced multi-scene) mode. Defaults keep old config
    # blocks loading unchanged.
    cinematic_credits_per_song: int = 3   # premium price; ~$0.30 ledger vs ~$0.26 raw
    cinematic_pool_size: int = 7          # # of Flux stills generated for the pool
    bars_per_cut: int = 4                 # change image every N bars on the beat grid
```

- [ ] **Step 4: Update `config.yaml`**

In `config.yaml`, under the `song:` block (after `credits_per_song: 1`), add:

```yaml
  # Cinematic (beat-synced multi-scene video) mode — premium toggle.
  cinematic_credits_per_song: 3
  cinematic_pool_size: 7
  bars_per_cut: 4
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_config.py -k cinematic -v`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add pipeline/config.py config.yaml tests/test_config.py
git commit -m "feat(song): cinematic config fields (3 credits, pool 7, bars/cut 4)"
```

---

## Task 2: `song_scenes.py` — pure cut-schedule builder (the brain)

**Files:**
- Create: `pipeline/song_scenes.py`
- Test: `tests/test_song_scenes.py`

This is the riskiest logic, so it is pure (no I/O, no ffmpeg) and gets the most tests.

- [ ] **Step 1: Write failing tests**

Create `tests/test_song_scenes.py`:

```python
from __future__ import annotations

import pytest

from pipeline.song_scenes import Segment, build_cut_schedule, extract_sections


def _beats(n, step=0.5, start=0.0):
    return [start + i * step for i in range(n)]


def test_extract_sections_pulls_labels_and_starts():
    data = {"audio_duration": 30.0, "lines": [
        {"kind": "section", "text": "Verse 1", "start": 0.0},
        {"kind": "line", "text": "x", "start": 0.5, "end": 1.0},
        {"kind": "section", "text": "Chorus", "start": 8.0},
    ]}
    secs = extract_sections(data)
    assert secs == [{"label": "Verse 1", "start": 0.0},
                    {"label": "Chorus", "start": 8.0}]


def test_cut_every_n_bars_lands_on_beats():
    # 32 beats @ 0.5s = 16s; 4 bars * 4 beats = 16 beats/cut → cut at beat 0 and 16
    sched = build_cut_schedule(
        beat_times=_beats(32), sections=[{"label": "Verse 1", "start": 0.0}],
        pool_size=4, audio_duration=16.0, bars_per_cut=4, beats_per_bar=4,
    )
    starts = [round(s.start, 3) for s in sched]
    assert starts == [0.0, 8.0]  # beat[0]=0.0, beat[16]=8.0
    assert sched[-1].end == 16.0


def test_chorus_image_recurs():
    sections = [
        {"label": "Verse 1", "start": 0.0},
        {"label": "Chorus", "start": 8.0},
        {"label": "Verse 2", "start": 16.0},
        {"label": "Chorus", "start": 24.0},
    ]
    sched = build_cut_schedule(
        beat_times=[], sections=sections, pool_size=8, audio_duration=32.0,
    )
    # Fallback (no beats) → one segment per section start.
    img_at = {round(s.start): s.image_idx for s in sched}
    assert img_at[8] == img_at[24]      # both choruses share an image
    assert img_at[0] != img_at[16]      # verse 1 != verse 2


def test_zoom_dir_alternates():
    sched = build_cut_schedule(
        beat_times=_beats(48), sections=[{"label": "Verse 1", "start": 0.0}],
        pool_size=2, audio_duration=24.0, bars_per_cut=2, beats_per_bar=4,
    )
    dirs = [s.zoom_dir for s in sched]
    assert dirs[0] == "in" and dirs[1] == "out"
    assert all(d in ("in", "out") for d in dirs)


def test_short_segments_merged():
    # A trailing beat that would create a <0.6s sliver folds into the prior segment.
    sched = build_cut_schedule(
        beat_times=[0.0, 8.0, 15.9], sections=[{"label": "Verse 1", "start": 0.0}],
        pool_size=2, audio_duration=16.0, bars_per_cut=1, beats_per_bar=1,
        min_segment_s=0.6,
    )
    assert all((s.end - s.start) >= 0.6 for s in sched)
    assert sched[-1].end == 16.0


def test_empty_beats_fall_back_to_sections():
    sections = [{"label": "Verse 1", "start": 0.0}, {"label": "Chorus", "start": 10.0}]
    sched = build_cut_schedule(
        beat_times=[], sections=sections, pool_size=4, audio_duration=20.0,
    )
    assert [round(s.start) for s in sched] == [0, 10]


def test_pool_smaller_than_sections_cycles():
    sections = [{"label": f"Verse {i}", "start": float(i * 5)} for i in range(5)]
    sched = build_cut_schedule(
        beat_times=[], sections=sections, pool_size=2, audio_duration=25.0,
    )
    assert all(0 <= s.image_idx < 2 for s in sched)


def test_single_section_song():
    sched = build_cut_schedule(
        beat_times=_beats(16), sections=[{"label": "Verse 1", "start": 0.0}],
        pool_size=1, audio_duration=8.0, bars_per_cut=4, beats_per_bar=4,
    )
    assert all(s.image_idx == 0 for s in sched)
    assert sched[-1].end == 8.0


def test_segment_cap_enforced():
    sched = build_cut_schedule(
        beat_times=_beats(2000, step=0.1), sections=[{"label": "V", "start": 0.0}],
        pool_size=4, audio_duration=200.0, bars_per_cut=1, beats_per_bar=1,
        max_segments=60,
    )
    assert len(sched) <= 60
    assert sched[-1].end == 200.0


def test_pool_size_zero_raises():
    with pytest.raises(ValueError):
        build_cut_schedule(beat_times=[], sections=[], pool_size=0, audio_duration=5.0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_song_scenes.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pipeline.song_scenes'`.

- [ ] **Step 3: Implement `pipeline/song_scenes.py`**

```python
"""Pure cut-schedule builder for the cinematic (beat-synced) song video.

No I/O, no ffmpeg, no network — given beat times + section markers, it
returns a deterministic list of Segments that song_cinematic turns into
an ffmpeg filtergraph. This is the brain of the feature, kept pure so it
can be exhaustively unit-tested. See
docs/superpowers/specs/2026-06-16-beat-synced-song-video-design.md.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Segment:
    image_idx: int   # index into the pool, 0 <= image_idx < pool_size
    start: float     # seconds
    end: float       # seconds
    zoom_dir: str    # "in" | "out"


def extract_sections(lyrics_data: dict) -> list[dict]:
    """Pull [{label, start}] from a lyrics.json payload (kind=="section").

    Sections whose start is None (unaligned) are dropped — they carry no
    timing to cut on."""
    out: list[dict] = []
    for ln in lyrics_data.get("lines", []):
        if ln.get("kind") != "section":
            continue
        start = ln.get("start")
        if start is None:
            continue
        out.append({"label": str(ln.get("text", "")).strip(), "start": float(start)})
    return out


def _norm_label(label: str) -> str:
    """Normalize a section label for image assignment. Every [Chorus*]
    collapses to one key so the recurring hook reuses one image; other
    sections (Verse 1, Verse 2, Bridge) stay distinct."""
    low = label.strip().lower()
    if low.startswith("chorus"):
        return "chorus"
    return low


def _assign_section_images(sections: list[dict], pool_size: int) -> list[int]:
    """Image index per section occurrence (parallel to `sections`)."""
    label_to_idx: dict[str, int] = {}
    next_idx = 0
    out: list[int] = []
    for sec in sections:
        key = _norm_label(sec["label"])
        if key not in label_to_idx:
            label_to_idx[key] = next_idx % pool_size
            next_idx += 1
        out.append(label_to_idx[key])
    return out


def _image_for_time(t: float, starts: list[float], imgs: list[int]) -> int:
    """The image of the latest section whose start <= t."""
    chosen = imgs[0] if imgs else 0
    for start, img in zip(starts, imgs):
        if start <= t + 1e-6:
            chosen = img
        else:
            break
    return chosen


def _merge_short(segs: list[Segment], min_s: float, audio_duration: float) -> list[Segment]:
    """Fold sub-`min_s` segments into the previous one (or the next, for
    the first segment). Guarantees every segment >= min_s and the last
    ends at audio_duration."""
    if not segs:
        return segs
    merged: list[Segment] = []
    for seg in segs:
        if merged and (seg.end - seg.start) < min_s:
            prev = merged[-1]
            merged[-1] = Segment(prev.image_idx, prev.start, seg.end, prev.zoom_dir)
        else:
            merged.append(seg)
    # First segment too short → extend its end into the second (rare).
    if len(merged) >= 2 and (merged[0].end - merged[0].start) < min_s:
        second = merged[1]
        merged[0] = Segment(merged[0].image_idx, merged[0].start, second.end, merged[0].zoom_dir)
        del merged[1]
    last = merged[-1]
    merged[-1] = Segment(last.image_idx, last.start, audio_duration, last.zoom_dir)
    return merged


def _coarsen(segs: list[Segment], max_segments: int) -> list[Segment]:
    """Drop cut density to <= max_segments by merging runs of segments.
    Keeps image assignment of the first segment in each merged run."""
    if len(segs) <= max_segments:
        return segs
    group = (len(segs) + max_segments - 1) // max_segments
    out: list[Segment] = []
    for i in range(0, len(segs), group):
        chunk = segs[i:i + group]
        head = chunk[0]
        out.append(Segment(head.image_idx, head.start, chunk[-1].end, head.zoom_dir))
    return out


def build_cut_schedule(
    *,
    beat_times: list[float],
    sections: list[dict],
    pool_size: int,
    audio_duration: float,
    bars_per_cut: int = 4,
    beats_per_bar: int = 4,
    min_segment_s: float = 0.6,
    max_segments: int = 60,
) -> list[Segment]:
    """Build the cinematic cut timeline. See module docstring."""
    if pool_size < 1:
        raise ValueError("pool_size must be >= 1")

    section_starts = [float(s["start"]) for s in sections] if sections else [0.0]
    section_imgs = _assign_section_images(sections, pool_size) if sections else [0]

    beats_per_cut = max(1, bars_per_cut * beats_per_bar)
    if beat_times:
        cuts = [float(beat_times[i]) for i in range(0, len(beat_times), beats_per_cut)]
        if not cuts or cuts[0] > 0.0:
            cuts = [0.0] + cuts
    else:
        cuts = sorted({0.0, *section_starts})

    boundaries = sorted({c for c in cuts if 0.0 <= c < audio_duration})
    if not boundaries:
        boundaries = [0.0]
    boundaries.append(audio_duration)

    segs: list[Segment] = []
    for i in range(len(boundaries) - 1):
        start, end = boundaries[i], boundaries[i + 1]
        if end <= start:
            continue
        img = _image_for_time(start, section_starts, section_imgs)
        zoom = "in" if i % 2 == 0 else "out"
        segs.append(Segment(image_idx=img, start=start, end=end, zoom_dir=zoom))

    segs = _merge_short(segs, min_segment_s, audio_duration)
    segs = _coarsen(segs, max_segments)
    return segs
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_song_scenes.py -v`
Expected: PASS (all 10 tests).

- [ ] **Step 5: Commit**

```bash
git add pipeline/song_scenes.py tests/test_song_scenes.py
git commit -m "feat(song): pure beat-synced cut-schedule builder (song_scenes)"
```

---

## Task 3: `song_beats.py` — tempo/beat detection + fallback

**Files:**
- Create: `pipeline/song_beats.py`
- Modify: `pyproject.toml` (add `librosa`)
- Test: `tests/test_song_beats.py`

- [ ] **Step 1: Add the dependency**

In `pyproject.toml`, add to the `dependencies` list (after `"openai-whisper>=20240930",`):

```toml
    # librosa: beat/tempo tracking for cinematic (beat-synced) song video.
    # Pulls scipy + numba; torch/numpy already ship for Whisper.
    "librosa>=0.10",
```

Then run: `uv sync`
Expected: resolves and installs librosa + scipy + numba.

- [ ] **Step 2: Write failing tests**

Create `tests/test_song_beats.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pipeline.song_beats as song_beats


def test_detect_beats_writes_json_and_parses(tmp_path, monkeypatch):
    def fake_track(path):
        return 123.4, [0.0, 0.5, 1.0, 1.5]
    monkeypatch.setattr(song_beats, "_librosa_beat_track", fake_track)
    out = tmp_path / "beats.json"
    result = song_beats.detect_beats(tmp_path / "song.mp3", out_json=out)
    assert result["tempo_bpm"] == 123.4
    assert result["beat_times"] == [0.0, 0.5, 1.0, 1.5]
    assert result["source"] == "librosa"
    assert json.loads(out.read_text()) == result


def test_detect_beats_idempotent(tmp_path, monkeypatch):
    out = tmp_path / "beats.json"
    out.write_text(json.dumps({"tempo_bpm": 90.0, "beat_times": [0.0], "source": "cached"}))
    def boom(path):
        raise AssertionError("should not be called when beats.json exists")
    monkeypatch.setattr(song_beats, "_librosa_beat_track", boom)
    result = song_beats.detect_beats(tmp_path / "song.mp3", out_json=out)
    assert result["source"] == "cached"


def test_detect_beats_fallback_on_error(tmp_path, monkeypatch):
    def boom(path):
        raise RuntimeError("librosa exploded")
    monkeypatch.setattr(song_beats, "_librosa_beat_track", boom)
    monkeypatch.setattr(song_beats, "_audio_duration_s", lambda p: 10.0)
    out = tmp_path / "beats.json"
    result = song_beats.detect_beats(tmp_path / "song.mp3", out_json=out,
                                     fallback_bpm=120.0)
    assert result["source"] == "fallback"
    assert result["tempo_bpm"] == 120.0
    # 120 BPM over 10s = 2 beats/s → ~20 beats
    assert len(result["beat_times"]) == 20
    assert result["beat_times"][0] == 0.0


def test_detect_beats_fallback_on_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(song_beats, "_librosa_beat_track", lambda p: (0.0, []))
    monkeypatch.setattr(song_beats, "_audio_duration_s", lambda p: 4.0)
    out = tmp_path / "beats.json"
    result = song_beats.detect_beats(tmp_path / "song.mp3", out_json=out)
    assert result["source"] == "fallback"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_song_beats.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pipeline.song_beats'`.

- [ ] **Step 4: Implement `pipeline/song_beats.py`**

```python
"""Tempo/beat detection for the cinematic song video.

Wraps librosa's beat tracker. Always succeeds: if librosa raises or
finds no beats, falls back to a fixed-BPM grid over the audio duration
so the cut-schedule builder still has a beat grid to work with.

Idempotent: if beats.json already exists, returns it and skips librosa
(same resumable pattern as the rest of the pipeline).
"""
from __future__ import annotations

import json
from pathlib import Path

from pipeline.align import _audio_duration_s


def _librosa_beat_track(song_mp3: Path) -> tuple[float, list[float]]:
    """Return (tempo_bpm, beat_times_seconds). Isolated so tests can
    monkeypatch it without importing librosa."""
    import librosa  # lazy: heavy import (numba/scipy)
    y, sr = librosa.load(str(song_mp3), mono=True)
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr)
    return float(tempo), [float(t) for t in beat_times]


def _write_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _fixed_grid(song_mp3: Path, bpm: float) -> dict:
    duration = _audio_duration_s(song_mp3)
    step = 60.0 / bpm
    n = max(1, int(duration / step))
    return {
        "tempo_bpm": bpm,
        "beat_times": [round(i * step, 4) for i in range(n)],
        "source": "fallback",
    }


def detect_beats(
    song_mp3: Path,
    *,
    out_json: Path,
    fallback_bpm: float = 120.0,
) -> dict:
    """Detect tempo + beats; write beats.json; return its contents."""
    if out_json.exists():
        return json.loads(out_json.read_text(encoding="utf-8"))

    try:
        tempo, beats = _librosa_beat_track(song_mp3)
        if beats:
            result = {"tempo_bpm": tempo, "beat_times": beats, "source": "librosa"}
        else:
            result = _fixed_grid(song_mp3, fallback_bpm)
    except Exception as e:  # librosa / audio decode failure — never fail the run
        print(f"[song_beats] detection failed ({e}); using fixed-BPM fallback")
        result = _fixed_grid(song_mp3, fallback_bpm)

    _write_atomic(out_json, result)
    return result
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_song_beats.py -v`
Expected: PASS (4 tests).

- [ ] **Step 6: Commit**

```bash
git add pipeline/song_beats.py tests/test_song_beats.py pyproject.toml uv.lock
git commit -m "feat(song): librosa beat detection with fixed-BPM fallback (song_beats)"
```

---

## Task 4: `song_lyrics.py` — art direction + scene prompts

**Files:**
- Modify: `pipeline/song_lyrics.py:18-24` (dataclass), `:39-86` (prompt), `:119-130` (parse)
- Test: `tests/test_script.py` (or wherever song-lyrics tests live; create `tests/test_song_lyrics.py` if none)

- [ ] **Step 1: Write the failing test**

Create `tests/test_song_lyrics.py`:

```python
from __future__ import annotations

import json

from pipeline.song_lyrics import generate_song_script


class _FakeLLM:
    def __init__(self, payload):
        self._payload = payload
    def complete(self, user_msg, system):
        return json.dumps(self._payload, ensure_ascii=False)


_GOOD = {
    "title": "ليل",
    "lyrics": "[Verse 1]\na\nb\n\n[Chorus]\nc\nd\n",
    "style_prompt": "Arabic pop, 90 BPM, oud, male vocal, minor key",
    "cover_prompt": "a lone figure on a moonlit rooftop",
    "art_direction": "moonlit teal-and-amber palette, cinematic 35mm, melancholic",
    "scene_prompts": [
        "a lone figure on a moonlit rooftop",
        "empty city street under sodium lamps",
        "close-up of rain on a window",
    ],
}


def test_song_script_parses_art_direction_and_scenes():
    s = generate_song_script(
        llm=_FakeLLM(_GOOD), theme="loneliness",
        custom_lyrics=None, style_hint=None, language="ar",
    )
    assert s.art_direction.startswith("moonlit")
    assert len(s.scene_prompts) == 3
    assert s.scene_prompts[0] == "a lone figure on a moonlit rooftop"


def test_song_script_missing_scene_fields_default_empty():
    payload = dict(_GOOD)
    del payload["art_direction"]
    del payload["scene_prompts"]
    s = generate_song_script(
        llm=_FakeLLM(payload), theme="x",
        custom_lyrics=None, style_hint=None, language="ar",
    )
    assert s.art_direction == ""
    assert s.scene_prompts == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_song_lyrics.py -v`
Expected: FAIL — `AttributeError: 'SongScript' object has no attribute 'art_direction'`.

- [ ] **Step 3: Extend the dataclass**

In `pipeline/song_lyrics.py`, change the imports line 12 and the dataclass (lines 18–24):

```python
from dataclasses import dataclass, field
```

```python
@dataclass(frozen=True)
class SongScript:
    title: str
    lyrics: str
    style_prompt: str
    cover_prompt: str
    language: str
    # Cinematic mode: one shared art direction + per-section scene prompts.
    # Empty for static-only runs / older payloads.
    art_direction: str = ""
    scene_prompts: list = field(default_factory=list)
```

- [ ] **Step 4: Extend the LLM prompt**

In `pipeline/song_lyrics.py`, append to `_SYSTEM_PROMPT` (after the COVER PROMPT paragraph, before the closing `"""` on line 86):

```python

ART DIRECTION + SCENE PROMPTS (for the cinematic music-video mode):
  - art_direction: ONE sentence fixing the shared visual world for the
    whole video — palette, film stock/medium, lighting, mood. Every
    scene below must read as the same world.
  - scene_prompts: a JSON array of 6–8 image prompts, ONE per song
    section in order (Verse 1, Pre-Chorus, Chorus, Verse 2, ...). Each
    describes a distinct moment/angle WITHIN the art_direction (do not
    repeat the art_direction text in them). No text in any image.
    Reuse the SAME chorus imagery concept whenever [Chorus] repeats.
```

Also add both keys to the OUTPUT FORMAT list (after the `cover_prompt` bullet, line 45):

```python
  - art_direction: one-sentence shared look for the cinematic video
  - scene_prompts: JSON array of 6–8 per-section image prompts
```

- [ ] **Step 5: Parse the new fields**

In `pipeline/song_lyrics.py`, replace the `return SongScript(...)` block (lines 124–130):

```python
    return SongScript(
        title=parsed["title"],
        lyrics=lyrics,
        style_prompt=parsed["style_prompt"],
        cover_prompt=parsed["cover_prompt"],
        language=language,
        art_direction=str(parsed.get("art_direction", "")),
        scene_prompts=list(parsed.get("scene_prompts", []) or []),
    )
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_song_lyrics.py -v`
Expected: PASS (2 tests).

- [ ] **Step 7: Commit**

```bash
git add pipeline/song_lyrics.py tests/test_song_lyrics.py
git commit -m "feat(song): lyrics LLM emits art_direction + per-section scene_prompts"
```

---

## Task 5: `song_cover.py` — generate the scene pool

**Files:**
- Modify: `pipeline/song_cover.py` (add `generate_scene_images`)
- Test: `tests/test_song_cover.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/test_song_cover.py`:

```python
from __future__ import annotations

from pathlib import Path

from PIL import Image

import pipeline.song_cover as song_cover


class _FakeClient:
    def __init__(self, fail_indices=()):
        self.calls = 0
        self._fail = set(fail_indices)
    def submit_flux_image_job(self, *, prompt, model, aspect_ratio):
        self.calls += 1
        return f"task-{self.calls}"
    def wait_for_flux_image(self, task_id, **kw):
        idx = int(task_id.split("-")[1]) - 1
        if idx in self._fail:
            from pipeline.kie import KieError
            raise KieError("boom")
        return f"http://x/{task_id}.png"
    def download(self, url, out_path):
        Image.new("RGB", (16, 16), "blue").save(out_path)


def _cover(tmp_path):
    p = tmp_path / "cover.png"
    Image.new("RGB", (16, 16), "red").save(p)
    return p


def test_generate_scene_images_writes_pool(tmp_path):
    paths = song_cover.generate_scene_images(
        client=_FakeClient(), art_direction="moonlit teal",
        scene_prompts=["a", "b", "c"], out_dir=tmp_path,
        cover_fallback=_cover(tmp_path),
    )
    assert [p.name for p in paths] == ["scene_01.png", "scene_02.png", "scene_03.png"]
    assert all(p.exists() for p in paths)


def test_failed_scene_falls_back_to_cover(tmp_path):
    cover = _cover(tmp_path)
    paths = song_cover.generate_scene_images(
        client=_FakeClient(fail_indices=[1]),  # second scene fails
        art_direction="x", scene_prompts=["a", "b", "c"],
        out_dir=tmp_path, cover_fallback=cover,
    )
    assert len(paths) == 3
    # scene_02 fell back to a copy of the cover (same pixels as cover)
    assert Image.open(paths[1]).getpixel((0, 0)) == Image.open(cover).getpixel((0, 0))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_song_cover.py -v`
Expected: FAIL — `AttributeError: module 'pipeline.song_cover' has no attribute 'generate_scene_images'`.

- [ ] **Step 3: Implement `generate_scene_images`**

Append to `pipeline/song_cover.py`:

```python
def generate_scene_images(
    *,
    client: KieClient,
    art_direction: str,
    scene_prompts: list[str],
    out_dir: Path,
    cover_fallback: Path,
) -> list[Path]:
    """Render the cinematic scene pool to out_dir/scenes/scene_NN.png.

    Style-lock v1: the shared `art_direction` is prepended to every
    scene prompt so the pool reads as one music video. Each image is
    independent; if Flux fails for a scene (after the model fallback in
    submit), that slot reuses a copy of `cover_fallback` so the render
    never loses a frame. Returns the ordered list of scene paths.
    """
    import shutil

    scenes_dir = out_dir / "scenes"
    scenes_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    for i, prompt in enumerate(scene_prompts, start=1):
        dest = scenes_dir / f"scene_{i:02d}.png"
        if dest.exists():           # resumable: skip already-rendered scenes
            paths.append(dest)
            continue
        full_prompt = (
            f"{art_direction}. {prompt}, cinematic lighting, shallow depth "
            f"of field, high detail, no text, no watermark, square composition"
        )
        rendered = False
        for model in FLUX_MODELS_TRIED:
            try:
                task_id = client.submit_flux_image_job(
                    prompt=full_prompt, model=model, aspect_ratio="1:1",
                )
                url = client.wait_for_flux_image(task_id, poll_interval_s=5, timeout_s=180)
                client.download(url, dest)
                rendered = True
                break
            except (KieError, TransientKieError) as e:
                print(f"[song_cover] scene {i} {model} failed: {e}; next fallback")
                continue
        if not rendered:
            print(f"[song_cover] scene {i} all Flux models failed; reusing cover")
            shutil.copyfile(cover_fallback, dest)
        paths.append(dest)

    return paths
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_song_cover.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add pipeline/song_cover.py tests/test_song_cover.py
git commit -m "feat(song): generate_scene_images — style-locked Flux pool with cover fallback"
```

---

## Task 6: `song_assemble.py` — extract shared helpers (no behavior change)

**Files:**
- Modify: `pipeline/song_assemble.py:243-269` (metadata), `:212-218` (watermark)
- Test: `tests/test_assemble.py` (add a small unit test for the extracted helper)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_assemble.py`:

```python
def test_build_metadata_args_includes_share_token():
    from pipeline.song_assemble import build_metadata_args
    args = build_metadata_args(title="ليل", share_token="abc123")
    assert "-metadata" in args
    assert any("title=ليل" in a for a in args)
    assert any("abc123" in a for a in args)


def test_build_metadata_args_without_token():
    from pipeline.song_assemble import build_metadata_args
    args = build_metadata_args(title=None, share_token=None)
    assert any("artist=Faceless Lab" in a for a in args)
    assert any("faceless-lab.com" in a for a in args)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_assemble.py -k build_metadata_args -v`
Expected: FAIL — `ImportError: cannot import name 'build_metadata_args'`.

- [ ] **Step 3: Extract the helpers**

In `pipeline/song_assemble.py`, add two module-level functions (place them just above `def assemble_song_video`):

```python
def build_metadata_args(title: str | None, share_token: str | None) -> list[str]:
    """MP4 container provenance tags — shared by the static and cinematic
    assemblers. Lives in the moov atom for ffprobe / content-ID tools."""
    args: list[str] = []
    if title:
        args += ["-metadata", f"title={title}"]
    args += [
        "-metadata", "artist=Faceless Lab",
        "-metadata", "encoded_by=Faceless Lab",
        "-metadata", (
            "copyright=© Faceless Lab — AI-generated. "
            "Not for unauthorized commercial reuse."
        ),
    ]
    if share_token:
        args += ["-metadata",
                 f"comment=Generated with Faceless Lab — "
                 f"https://faceless-lab.com/p/{share_token}"]
    else:
        args += ["-metadata", "comment=Generated with Faceless Lab — faceless-lab.com"]
    return args


def resolve_watermark() -> tuple[bool, Path]:
    """(has_watermark, path). Shared by both assemblers."""
    watermark_png = _FONT_DIR.parent / "watermark.png"
    return watermark_png.exists(), watermark_png
```

Then in `assemble_song_video`, replace the inline `metadata_args` construction (lines ~248–269) with:

```python
    metadata_args = build_metadata_args(title, share_token)
```

and replace the inline watermark detection (lines ~217–218) with:

```python
    has_watermark, watermark_png = resolve_watermark()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_assemble.py -v`
Expected: PASS — new helper tests pass AND every existing `test_assemble.py` test still passes (proves no behavior change to the static path).

- [ ] **Step 5: Commit**

```bash
git add pipeline/song_assemble.py tests/test_assemble.py
git commit -m "refactor(song): extract build_metadata_args + resolve_watermark for reuse"
```

---

## Task 7: `song_cinematic.py` — filtergraph builder + assembler

**Files:**
- Create: `pipeline/song_cinematic.py`
- Test: `tests/test_song_cinematic.py`

- [ ] **Step 1: Write failing tests (pure builder)**

Create `tests/test_song_cinematic.py`:

```python
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from PIL import Image

from pipeline.song_scenes import Segment
from pipeline.song_cinematic import build_filter_complex, assemble_cinematic_song_video


def test_filter_complex_references_every_image():
    segs = [Segment(0, 0.0, 4.0, "in"), Segment(1, 4.0, 8.0, "out")]
    fc = build_filter_complex(segments=segs, n_images=2, ass_filter="", has_watermark=False)
    assert "[0:v]" in fc and "[1:v]" in fc   # both pool inputs referenced
    assert fc.strip().endswith("[v]")        # final label


def test_filter_complex_xfade_offsets_match_boundaries():
    segs = [Segment(0, 0.0, 4.0, "in"), Segment(1, 4.0, 9.0, "out")]
    fc = build_filter_complex(segments=segs, n_images=2, ass_filter="", has_watermark=False)
    assert "xfade" in fc
    # The crossfade STARTS _XFADE_S (0.35s) before the 4.0s boundary so the
    # transition completes on the beat: offset = 4.0 - 0.35 = 3.650.
    assert "offset=3.650" in fc


def test_filter_complex_appends_ass_and_watermark():
    segs = [Segment(0, 0.0, 4.0, "in")]
    fc = build_filter_complex(
        segments=segs, n_images=1,
        ass_filter=",ass='/tmp/lyrics.ass'", has_watermark=True,
    )
    assert "ass='/tmp/lyrics.ass'" in fc
    assert "overlay=W-w-28:28" in fc


def test_assemble_cinematic_produces_playable_mp4(tmp_path):
    # Integration smoke — real ffmpeg on tiny inputs.
    scene_paths = []
    for i, color in enumerate(["red", "green"], start=1):
        p = tmp_path / f"scene_{i:02d}.png"
        Image.new("RGB", (64, 64), color).save(p)
        scene_paths.append(p)
    song = tmp_path / "song.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=4",
         "-c:a", "libmp3lame", str(song)],
        check=True, capture_output=True,
    )
    out = tmp_path / "final.mp4"
    schedule = [Segment(0, 0.0, 2.0, "in"), Segment(1, 2.0, 4.0, "out")]
    assemble_cinematic_song_video(
        scene_paths=scene_paths, song_mp3=song, out_mp4=out,
        schedule=schedule, lyrics_json=None, title="t", share_token=None,
    )
    assert out.exists()
    # ffprobe: has a video + audio stream
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type",
         "-of", "csv=p=0", str(out)],
        check=True, capture_output=True, text=True,
    ).stdout
    assert "video" in probe and "audio" in probe
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_song_cinematic.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pipeline.song_cinematic'`.

- [ ] **Step 3: Implement `pipeline/song_cinematic.py`**

```python
"""Cinematic (beat-synced) song-video assembler — Approach A.

ONE ffmpeg invocation: each pool image is scaled + zoompan'd on its
segment, the segments are chained with xfade, then the existing karaoke
.ass and brand watermark are composited on top. No intermediate files
(GCS-Fuse-safe): write to .tmp, then atomic rename — same pattern as
song_assemble.assemble_song_video.

See docs/superpowers/specs/2026-06-16-beat-synced-song-video-design.md.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from pipeline.song_assemble import (
    FPS,
    OUTPUT_SIZE,
    UPSCALE_SIZE,
    ZOOM_END,
    _escape_ffmpeg_filter_path,
    _write_ass_subtitles,
    build_metadata_args,
    resolve_watermark,
)
from pipeline.song_scenes import Segment

_XFADE_S = 0.35  # crossfade duration on each cut (matches assemble shot crossfade)


def assert_playable(mp4: Path) -> None:
    """Raise if the output has no video+audio stream or zero duration.
    Cheap guard against the MEDIA_ERR_SRC_NOT_SUPPORTED failure class."""
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_type:format=duration", "-of", "json", str(mp4)],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(probe.stdout)
    kinds = {s.get("codec_type") for s in data.get("streams", [])}
    duration = float(data.get("format", {}).get("duration", 0.0) or 0.0)
    if "video" not in kinds or "audio" not in kinds or duration <= 0.0:
        raise RuntimeError(f"output not playable: streams={kinds} duration={duration}")


def build_filter_complex(
    *,
    segments: list[Segment],
    n_images: int,
    ass_filter: str,
    has_watermark: bool,
) -> str:
    """Pure: turn a cut schedule into one ffmpeg -filter_complex string.

    Inputs are the N pool images ([0:v]..[N-1:v]); audio is a separate
    input mapped later. Each segment trims its image to its duration with
    a zoompan, then segments are xfade-chained in order."""
    parts: list[str] = []
    seg_labels: list[str] = []

    for i, seg in enumerate(segments):
        dur = max(0.1, seg.end - seg.start)
        frames = max(1, int(dur * FPS))
        if seg.zoom_dir == "in":
            z = f"1+{(ZOOM_END - 1.0):.6f}*on/{frames}"
        else:
            z = f"{ZOOM_END:.6f}-{(ZOOM_END - 1.0):.6f}*on/{frames}"
        label = f"s{i}"
        parts.append(
            f"[{seg.image_idx}:v]scale={UPSCALE_SIZE}:{UPSCALE_SIZE},"
            f"zoompan=z='{z}':d={frames}:s={OUTPUT_SIZE}x{OUTPUT_SIZE}:fps={FPS},"
            f"trim=duration={dur:.3f},setpts=PTS-STARTPTS[{label}]"
        )
        seg_labels.append(label)

    # Chain with xfade. Single segment → no xfade needed.
    if len(seg_labels) == 1:
        chain_out = seg_labels[0]
    else:
        prev = seg_labels[0]
        acc = segments[0].end - segments[0].start
        for i in range(1, len(seg_labels)):
            out = f"x{i}"
            offset = max(0.0, acc - _XFADE_S)
            parts.append(
                f"[{prev}][{seg_labels[i]}]"
                f"xfade=transition=fade:duration={_XFADE_S}:offset={offset:.3f}[{out}]"
            )
            acc += (segments[i].end - segments[i].start) - _XFADE_S
            prev = out
        chain_out = prev

    # Karaoke captions then watermark, mirroring the static assembler.
    tail = f"[{chain_out}]format=yuv420p{ass_filter}"
    if has_watermark:
        # The watermark PNG is the LAST input; index = n_images + 1 (audio is n_images).
        wm_idx = n_images + 1
        return (
            ";".join(parts) + ";" +
            tail + "[vsub];" +
            f"[{wm_idx}:v]scale=240:55[wm];" +
            "[vsub][wm]overlay=W-w-28:28[v]"
        )
    return ";".join(parts) + ";" + tail + "[v]"


def assemble_cinematic_song_video(
    *,
    scene_paths: list[Path],
    song_mp3: Path,
    out_mp4: Path,
    schedule: list[Segment],
    lyrics_json: Path | None = None,
    title: str | None = None,
    share_token: str | None = None,
) -> None:
    """Render the beat-synced video in one ffmpeg call. Raises
    CalledProcessError on ffmpeg failure or RuntimeError if the result
    fails the playability gate."""
    ass_filter = ""
    if lyrics_json is not None and lyrics_json.exists():
        try:
            data = json.loads(lyrics_json.read_text(encoding="utf-8"))
            ass_path = lyrics_json.with_name("lyrics.ass")
            if _write_ass_subtitles(data, ass_path):
                ass_filter = f",ass='{_escape_ffmpeg_filter_path(ass_path)}'"
        except (OSError, json.JSONDecodeError, ValueError):
            ass_filter = ""

    has_watermark, watermark_png = resolve_watermark()
    filter_complex = build_filter_complex(
        segments=schedule, n_images=len(scene_paths),
        ass_filter=ass_filter, has_watermark=has_watermark,
    )

    cmd = ["ffmpeg", "-y"]
    for p in scene_paths:                       # inputs 0..N-1 : pool images
        cmd += ["-loop", "1", "-i", str(p)]
    cmd += ["-i", str(song_mp3)]                # input N : audio
    if has_watermark:
        cmd += ["-loop", "1", "-i", str(watermark_png)]   # input N+1 : watermark
    cmd += [
        "-filter_complex", filter_complex,
        "-map", "[v]", "-map", f"{len(scene_paths)}:a",
        *build_metadata_args(title, share_token),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        "-movflags", "+faststart",
        "-threads", "0",
        "-f", "mp4",
        str(out_mp4) + ".tmp",
    ]
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = Path(str(out_mp4) + ".tmp")
    if tmp_path.exists():
        try:
            tmp_path.unlink()
        except OSError:
            try:
                tmp_path.write_bytes(b"")
            except OSError:
                pass
    subprocess.run(cmd, check=True, capture_output=True)
    tmp_path.replace(out_mp4)
    assert_playable(out_mp4)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_song_cinematic.py -v`
Expected: PASS (4 tests). If the smoke test is slow/needs ffmpeg, confirm `ffmpeg`/`ffprobe` are on PATH.

- [ ] **Step 5: Commit**

```bash
git add pipeline/song_cinematic.py tests/test_song_cinematic.py
git commit -m "feat(song): single-filtergraph beat-synced assembler (song_cinematic)"
```

---

## Task 8: API — `video_mode` request/cost/credits + downgrade refund

**Files:**
- Modify: `pipeline/api.py:380-392` (request), `:408+` cost resp, `:430-450` summary, `:2360-2433` create, `:2574-2592` script, `:2798-2860` approve, `:2553-2573` get_song
- Test: `tests/test_api.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_api.py` (reuse the module's existing authed test client + service-token fixtures; mirror the existing song tests' setup):

```python
def test_create_cinematic_song_sets_video_mode(client, auth_headers, monkeypatch):
    _stub_song_llm(monkeypatch)  # existing helper that fakes _build_song_llm
    r = client.post("/songs", json={"theme": "x", "video_mode": "cinematic"},
                    headers=auth_headers)
    assert r.status_code == 201
    run_id = r.json()["run_id"]
    s = client.get(f"/songs/{run_id}/script", headers=auth_headers).json()
    assert s["cost_credits"] == 3


def test_create_static_song_defaults_one_credit(client, auth_headers, monkeypatch):
    _stub_song_llm(monkeypatch)
    r = client.post("/songs", json={"theme": "x"}, headers=auth_headers)
    run_id = r.json()["run_id"]
    s = client.get(f"/songs/{run_id}/script", headers=auth_headers).json()
    assert s["cost_credits"] == 1


def test_invalid_video_mode_rejected(client, auth_headers, monkeypatch):
    _stub_song_llm(monkeypatch)
    r = client.post("/songs", json={"theme": "x", "video_mode": "bogus"},
                    headers=auth_headers)
    assert r.status_code == 422
```

If `_stub_song_llm` does not already exist in the test module, add it near the other song-test helpers:

```python
def _stub_song_llm(monkeypatch):
    from pipeline.song_lyrics import SongScript
    import pipeline.api as api
    def fake_script(**kw):
        return SongScript(
            title="t", lyrics="[Verse 1]\na\n\n[Chorus]\nb\n",
            style_prompt="pop, 90 BPM", cover_prompt="c",
            language=kw.get("language", "ar"),
            art_direction="moonlit", scene_prompts=["a", "b"],
        )
    monkeypatch.setattr("pipeline.song_lyrics.generate_song_script", fake_script)
    monkeypatch.setattr(api, "_build_song_llm", lambda: object())
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_api.py -k video_mode -v`
Expected: FAIL — `cost_credits` is 1 for cinematic / 422 not raised.

- [ ] **Step 3a: Add `video_mode` to the request model**

In `pipeline/api.py`, in `CreateSongRequest` (after `suno_model`, line 392) add:

```python
    # "static" (1-credit cover video) or "cinematic" (beat-synced
    # multi-scene video, priced higher). Validated below.
    video_mode: str = "static"

    @field_validator("video_mode")
    @classmethod
    def _check_video_mode(cls, v: str) -> str:
        if v not in ("static", "cinematic"):
            raise ValueError("video_mode must be 'static' or 'cinematic'")
        return v
```

Ensure `from pydantic import field_validator` is imported at the top of the file (add it to the existing pydantic import if absent).

- [ ] **Step 3b: Add `video_mode` to `SongScriptResponse` and `SongRunSummary`**

In `SongScriptResponse` (line 400) add field: `video_mode: str = "static"`.
In `SongRunSummary` (after `watermarked`, line 450) add: `video_mode: str = "static"`.

- [ ] **Step 3c: Persist `video_mode` + scene fields in `create_song`**

In `create_song`, the `song.json` payload (lines 2408–2427) — add three keys before the closing `}`:

```python
            "video_mode": req.video_mode,
            "art_direction": script.art_direction,
            "scene_prompts": script.scene_prompts,
```

Also gate the up-front balance check on the right amount — replace lines 2375–2378:

```python
    credits_required = (
        (cfg.song.cinematic_credits_per_song if req.video_mode == "cinematic"
         else cfg.song.credits_per_song)
        if cfg.song else (3 if req.video_mode == "cinematic" else 1)
    )
    if user.role != "service" and get_balance(user.id) < credits_required:
        _raise_402_insufficient_credits(get_balance(user.id), credits_required)
```

- [ ] **Step 3d: Branch `/script` cost**

In `get_song_script` (lines 2584–2592), replace the `return SongScriptResponse(...)`:

```python
    video_mode = script.get("video_mode", "static")
    if cfg.song and video_mode == "cinematic":
        credits = cfg.song.cinematic_credits_per_song
        usd = cfg.song.suno_cost_usd + cfg.song.cinematic_pool_size * cfg.song.cover_cost_usd
    elif cfg.song:
        credits = cfg.song.credits_per_song
        usd = cfg.song.suno_cost_usd + cfg.song.cover_cost_usd
    else:
        credits, usd = (3 if video_mode == "cinematic" else 1), 0.08
    return SongScriptResponse(
        title=script["title"], lyrics=script["lyrics"],
        style_prompt=script["style_prompt"], cover_prompt=script["cover_prompt"],
        language=script["language"], cost_credits=credits, cost_usd=usd,
        video_mode=video_mode,
    )
```

- [ ] **Step 3e: Branch `approve_song` credit amount**

In `approve_song`, replace the `amount = ...` line (2823):

```python
    script = json.loads((run_dir / "song.json").read_text())
    video_mode = script.get("video_mode", "static")
    if cfg.song and video_mode == "cinematic":
        amount = cfg.song.cinematic_credits_per_song
    elif cfg.song:
        amount = cfg.song.credits_per_song
    else:
        amount = 3 if video_mode == "cinematic" else 1
```

(The `check_or_deduct(..., reason="song-spend")` call below now deducts the right amount automatically.)

- [ ] **Step 3f: Surface `video_mode` in the summary builder**

Find the function that builds `SongRunSummary` from state (the `_summarize`-style helper used by `list_songs`/`get_song`) and add `video_mode=state.get("video_mode", "static")` (read from `song.json` if the builder reads that; otherwise persist `video_mode` into `state.json` in `create_song` via `_write_state(run_dir, video_mode=req.video_mode)` and read it from state). Use whichever source the existing builder already reads.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_api.py -k "video_mode or song" -v`
Expected: PASS — new tests pass; existing song API tests still pass.

- [ ] **Step 5: Commit**

```bash
git add pipeline/api.py tests/test_api.py
git commit -m "feat(api): video_mode toggle — 3-credit cinematic cost + approval branch"
```

---

## Task 9: `run.py` — wire the cinematic worker path + degradation

**Files:**
- Modify: `run.py:1022-1121` (song branch)
- Test: `tests/test_run_song_mode.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_run_song_mode.py` (reuse the module's existing fakes for Suno/Flux/ffmpeg; mirror the existing static smoke test's setup):

```python
def test_cinematic_run_produces_video(tmp_path, monkeypatch, song_run_fixture):
    # song_run_fixture: existing helper that lays down song.json + takes +
    # stubs the Kie client. Set video_mode=cinematic in song.json.
    run_dir = song_run_fixture(video_mode="cinematic",
                               scene_prompts=["a", "b"], art_direction="moonlit")
    monkeypatch.setattr("pipeline.song_beats.detect_beats",
                        lambda mp3, *, out_json, **kw: {
                            "tempo_bpm": 120.0, "beat_times": [0.0, 1.0, 2.0],
                            "source": "stub"})
    captured = {}
    import pipeline.song_cinematic as sc
    def fake_assemble(**kw):
        kw["out_mp4"].write_bytes(b"\x00")  # pretend ffmpeg made a file
        captured["called"] = True
    monkeypatch.setattr(sc, "assemble_cinematic_song_video", fake_assemble)
    rc = run_song_worker(run_dir)   # the existing entrypoint the test already calls
    assert rc == 0
    assert captured.get("called") is True


def test_cinematic_render_failure_downgrades_and_flags(tmp_path, monkeypatch, song_run_fixture):
    run_dir = song_run_fixture(video_mode="cinematic",
                               scene_prompts=["a", "b"], art_direction="x")
    monkeypatch.setattr("pipeline.song_beats.detect_beats",
                        lambda mp3, *, out_json, **kw: {"tempo_bpm": 120.0,
                                                        "beat_times": [0.0], "source": "stub"})
    import pipeline.song_cinematic as sc
    def boom(**kw):
        raise RuntimeError("ffmpeg blew up")
    monkeypatch.setattr(sc, "assemble_cinematic_song_video", boom)
    static_called = {}
    import pipeline.song_assemble as sa
    def fake_static(**kw):
        kw["out_mp4"].write_bytes(b"\x00")
        static_called["yes"] = True
    monkeypatch.setattr(sa, "assemble_song_video", fake_static)
    rc = run_song_worker(run_dir)
    import json
    state = json.loads((run_dir / "state.json").read_text())
    assert rc == 0
    assert static_called.get("yes") is True
    assert state.get("video_downgraded") is True
    assert state.get("status") == "complete"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_run_song_mode.py -k cinematic -v`
Expected: FAIL — cinematic branch / downgrade flag don't exist yet.

- [ ] **Step 3: Wire the worker branch**

In `run.py`, add the imports near the other song imports at the top:

```python
from pipeline import song_beats, song_cinematic, song_scenes
```

In the song branch, after the cover stage (after `apply_title_overlay`, ~line 1051) insert scene-pool generation, gated on cinematic mode:

```python
        video_mode = current_state.get("video_mode") or script.get("video_mode", "static")
        scene_paths: list[Path] = []
        if video_mode == "cinematic":
            write_state(status="generating_cover")
            scene_paths = song_cover.generate_scene_images(
                client=client,
                art_direction=script.get("art_direction", ""),
                scene_prompts=script.get("scene_prompts") or [script["cover_prompt"]],
                out_dir=run_dir,
                cover_fallback=final_cover_path,
            )
```

After the lyrics-align stage (after the `align_song_lyrics` try/except, ~line 1098) insert the beat-detection stage:

```python
        beats_data = None
        if video_mode == "cinematic":
            write_state(status="detecting_beats")
            beats_data = song_beats.detect_beats(
                song_mp3, out_json=run_dir / "beats.json",
            )
```

Replace the Stage 3 assemble block (lines 1100–1113) with a branch:

```python
        # --- Stage 3: assemble ---
        write_state(status="assembling")
        share_token = current_state.get("share_token") or None
        lyrics_arg = lyrics_json if lyrics_json.exists() else None

        if video_mode == "cinematic" and scene_paths:
            sections = song_scenes.extract_sections(
                json.loads(lyrics_json.read_text(encoding="utf-8"))
                if lyrics_json.exists() else {"lines": []}
            )
            from pipeline.song_assemble import ffprobe_duration
            schedule = song_scenes.build_cut_schedule(
                beat_times=(beats_data or {}).get("beat_times", []),
                sections=sections,
                pool_size=len(scene_paths),
                audio_duration=ffprobe_duration(song_mp3),
                bars_per_cut=cfg.song.bars_per_cut if cfg.song else 4,
            )
            try:
                song_cinematic.assemble_cinematic_song_video(
                    scene_paths=scene_paths, song_mp3=song_mp3, out_mp4=final_mp4,
                    schedule=schedule, lyrics_json=lyrics_arg,
                    title=script.get("title"), share_token=share_token,
                )
            except Exception as cine_err:
                print(f"[song-post-approve] cinematic assemble failed ({cine_err}); "
                      f"falling back to static cover video")
                song_assemble.assemble_song_video(
                    cover_path=final_cover_path, song_mp3=song_mp3, out_mp4=final_mp4,
                    lyrics_json=lyrics_arg, title=script.get("title"),
                    share_token=share_token,
                )
                # Flag the downgrade so the API refunds the surcharge on next read.
                write_state(video_downgraded=True)
        else:
            song_assemble.assemble_song_video(
                cover_path=final_cover_path, song_mp3=song_mp3, out_mp4=final_mp4,
                lyrics_json=lyrics_arg, title=script.get("title"),
                share_token=share_token,
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_run_song_mode.py -v`
Expected: PASS — cinematic smoke + downgrade test pass; existing static song-mode tests still pass.

- [ ] **Step 5: Commit**

```bash
git add run.py tests/test_run_song_mode.py
git commit -m "feat(song): cinematic worker path — scene pool, beat stage, assembler branch + downgrade fallback"
```

---

## Task 10: API — refund the surcharge on downgrade

**Files:**
- Modify: `pipeline/api.py` — `get_song` (line ~2553) + a new reconciliation helper
- Test: `tests/test_api.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_api.py`:

```python
def test_downgrade_refunds_surcharge_once(client, auth_headers, monkeypatch, service_user):
    # Simulate a completed cinematic run that downgraded to static.
    run_dir = _make_song_run_dir(video_mode="cinematic", status="complete",
                                  video_downgraded=True)  # test helper
    import pipeline.credits as credits
    calls = []
    monkeypatch.setattr(credits, "refund",
                        lambda user, **kw: calls.append(kw["amount"]))
    rid = run_dir.name
    client.get(f"/songs/{rid}", headers=auth_headers)   # first read → refund 2
    client.get(f"/songs/{rid}", headers=auth_headers)   # second read → no-op
    assert calls == [2]   # cinematic(3) - static(1) refunded exactly once
```

(If `_make_song_run_dir` doesn't exist, add a small helper that writes `state.json` + `song.json` under the authed user's runs root.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_api.py -k downgrade_refunds -v`
Expected: FAIL — refund never called.

- [ ] **Step 3: Add the reconciliation helper + call it from `get_song`**

In `pipeline/api.py`, add near the other song helpers:

```python
def _reconcile_downgrade_refund(run_dir: Path, user: "User") -> None:
    """If a cinematic run downgraded to static, refund the credit
    surcharge exactly once. Idempotent via the surcharge_refunded flag."""
    import pipeline.credits as _credits
    from pipeline.config import load_config
    state = _read_state(run_dir)
    if not state.get("video_downgraded") or state.get("surcharge_refunded"):
        return
    cfg = load_config(Path(os.environ.get("FACELESS_CONFIG", str(REPO_ROOT / "config.yaml"))))
    if cfg.song:
        surcharge = cfg.song.cinematic_credits_per_song - cfg.song.credits_per_song
    else:
        surcharge = 2
    if surcharge > 0:
        _credits.refund(user, amount=surcharge, run_id=run_dir.name,
                        reason="cinematic-downgrade-refund")
    _write_state(run_dir, surcharge_refunded=True)
```

In `get_song` (GET `/songs/{run_id}`, line ~2553), call it right after resolving the dir:

```python
    run_dir = _resolve_song_dir(run_id, user)
    _reconcile_downgrade_refund(run_dir, user)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_api.py -k downgrade_refunds -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/api.py tests/test_api.py
git commit -m "feat(api): refund cinematic surcharge once when a run downgrades to static"
```

---

## Task 11: Flutter — toggle + wiring

**Files:**
- Modify: `lib/api/client.dart:522-546` (`createSong`)
- Modify: `lib/api/models.dart` (`SongSummary`, `SongScript`)
- Modify: `lib/screens/new_song_screen.dart` (segmented toggle)
- Verify: `flutter analyze`

- [ ] **Step 1: Thread `videoMode` through `createSong`**

In `lib/api/client.dart`, edit `createSong` (lines 522–539) to add the param + body key:

```dart
  Future<String> createSong({
    required String theme,
    String? customLyrics,
    String? styleHint,
    String language = 'ar',
    String? personaId,
    String vocalGender = 'm',
    String? sunoModel,
    String videoMode = 'static',
  }) async {
    final body = <String, dynamic>{
      'theme': theme,
      if (customLyrics != null && customLyrics.isNotEmpty) 'custom_lyrics': customLyrics,
      if (styleHint != null && styleHint.isNotEmpty) 'style_hint': styleHint,
      'language': language,
      if (personaId != null && personaId.isNotEmpty) 'persona_id': personaId,
      'vocal_gender': vocalGender,
      if (sunoModel != null) 'suno_model': sunoModel,
      'video_mode': videoMode,
    };
```

- [ ] **Step 2: Add `videoMode` to `SongSummary` + `SongScript`**

In `lib/api/models.dart` `SongSummary`: add field `final String videoMode;`, constructor `this.videoMode = 'static',`, and in `fromJson`: `videoMode: (j['video_mode'] as String?) ?? 'static',`.

In `SongScript` (line 349): add `final int costCredits;` / `final String videoMode;` if not already present, and parse `cost_credits` + `video_mode` in its `fromJson` (the approve/cost screens already read cost — confirm field names match what `SongScriptResponse` returns: `cost_credits`, `cost_usd`, `video_mode`).

- [ ] **Step 3: Add the toggle to `new_song_screen.dart`**

In `lib/screens/new_song_screen.dart`, add state `String _videoMode = 'static';` and a segmented control above the submit button:

```dart
SegmentedButton<String>(
  segments: const [
    ButtonSegment(value: 'static', label: Text('Static cover · 1 credit')),
    ButtonSegment(value: 'cinematic', label: Text('Cinematic video · 3 credits')),
  ],
  selected: {_videoMode},
  onSelectionChanged: (s) => setState(() => _videoMode = s.first),
),
```

Then pass it in the existing `createSong(...)` call: `videoMode: _videoMode,`.

- [ ] **Step 4: Verify analyzer + format**

Run: `flutter analyze`
Expected: no NEW errors from these files (pre-existing `lib/main.dart` lints per CLAUDE.md are unrelated).

- [ ] **Step 5: Commit**

```bash
git add lib/api/client.dart lib/api/models.dart lib/screens/new_song_screen.dart
git commit -m "feat(app): cinematic/static video-mode toggle on new-song screen"
```

---

## Task 12: Full suite + manual smoke

**Files:** none (verification only)

- [ ] **Step 1: Run the full Python suite**

Run: `uv run pytest -q`
Expected: all green. If any pre-existing test broke, fix before proceeding.

- [ ] **Step 2: Manual end-to-end smoke (optional, costs real Kie credits)**

```bash
source .env
uv run python run.py --mode song --resume out/<a-cinematic-run-dir>
```
Expected: `final.mp4` exists, plays with multiple scenes cutting on the beat, karaoke + watermark present.

- [ ] **Step 3: Final commit / open PR**

```bash
git push -u origin feat/beat-synced-song-video
gh pr create --fill
```

---

## Notes for the implementer

- **TDD throughout:** every task writes the test first, watches it fail, then implements.
- **The pure module (`song_scenes`) is the safety net** — if cut timing looks wrong in the final video, fix it there with a new failing test, not by poking the ffmpeg string.
- **Never hit real APIs in tests** (repo invariant). librosa/Flux/Suno are monkeypatched; only ffmpeg/ffprobe run locally on tiny generated inputs.
- **Resumability:** `scenes/scene_NN.png` and `beats.json` skip if present — a re-`/resume` after an assemble failure won't re-pay Suno or re-render the pool.
