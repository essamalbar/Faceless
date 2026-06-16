# Beat-Synced Song Video — Design Spec

**Date:** 2026-06-16
**Status:** Approved (sections 1–5 walked through with user)
**Builds on:** `docs/superpowers/specs/2026-05-28-ai-song-mode-design.md` (song mode)
and `docs/superpowers/specs/2026-06-11-song-karaoke-burn-in-design.md` (lyrics.json
+ `.ass` karaoke).

## Goal

Upgrade the song product from a single static cover with a slow Ken-Burns zoom to
a **beat-synced multi-scene music video**: a bounded pool of ~6–10 art-directed
Flux stills, cut and zoom-punched on a tempo/beat grid, with the existing
karaoke captions and brand watermark composited on top.

Ships as a **premium "Cinematic video" toggle** at song creation — `2` credits
vs the existing `1`-credit static cover. The static path is untouched and stays
the default.

### Quality bar (load-bearing, inherited from song mode)

**A first-time listener/viewer must not realize the video is AI-generated.**
This drives the "one art direction, per-section variation" image strategy
(§Architecture) — independent per-section prompts look AI-stitched; a shared look
with disciplined variation reads as one produced music video.

## Decisions (resolved during brainstorming)

| # | Question | Decision |
|---|---|---|
| 1 | What are the scenes made of? | **Multiple still images** (not AI motion clips). Cheapest, fastest, reuses `zoompan`. |
| 2 | What drives the cut cadence? | **Beat/bar grid** — detect tempo, cut on the beat. Energetic/modern. |
| 3 | How many images per song? | **Bounded pool (~6–10), cycled on beats.** Coherent + bounded cost. |
| 4 | Rollout + price? | **Premium toggle, 2 credits** (static stays 1). Protects margin, keeps the cheap option. |
| 5 | Image coherence? | **One art direction, per-section variation** (optional Flux-kontext style-lock). |
| — | ffmpeg render strategy? | **Approach A: single `filter_complex`, one atomic ffmpeg call** — no intermediate files (GCS-Fuse-safe). |

## Non-goals

- AI motion clips (Kling per-section video) — explicitly deferred; revisit only if
  users ask for true moving footage. Bounded-pool stills are the MVP.
- Multi-format export (9:16 / 16:9) — separate feature; this spec is 1080×1080
  square, matching current song output + the share page.
- Upgrading an existing static song to cinematic in place — the `re-assemble`
  infra could power it later; out of scope here to keep the spec focused.
- Lip sync — no lip sync anywhere in this product.
- Per-beat unique imagery — rejected in Q3 (chaotic + expensive).

## Architecture

The cinematic path is a **sibling** to the static path, not a rewrite.
`assemble_song_video` is unchanged for 1-credit songs.

### New modules (each one purpose, independently testable)

| Module | Responsibility | Depends on |
|---|---|---|
| `pipeline/song_beats.py` | `detect_beats(song_mp3) -> {tempo_bpm, beat_times[]}` via librosa. Idempotent → writes `beats.json`. Falls back to a fixed-BPM grid if librosa raises or finds nothing (`source: "fallback"`). | librosa (new dep) |
| `pipeline/song_scenes.py` | **Pure function** `build_cut_schedule(beat_times, sections, pool_size, bars_per_cut, beats_per_bar, audio_duration) -> [{image_idx, start, end, zoom_dir}]`. No ffmpeg, no I/O — the brain of the feature. | nothing |
| `pipeline/song_cinematic.py` | `build_filter_complex(schedule, n_images, ass_filter, has_watermark)` (pure string builder) + `assemble_cinematic_song_video(...)` which runs one atomic ffmpeg call. | shared helpers from `song_assemble.py` |

### Extended modules

- **`pipeline/song_lyrics.py`** — LLM output gains `art_direction` (one shared
  look: palette, setting, mood, era) + `scene_prompts: [...]` (per-section
  variations within it). `cover_prompt` stays (poster/thumbnail).
- **`pipeline/song_cover.py`** — generates the pool: `cover.png` (poster,
  unchanged) + `scenes/scene_01..NN.png`. **v1 style-lock = the shared
  `art_direction` string is prepended to every `scene_prompt`** so all images
  share palette/setting/mood. Flux-kontext conditioning (each scene generated as
  an edit of the cover) is a noted **future enhancement**, not v1 — keeps the
  generation path simple and avoids a kontext-specific failure surface.
- **`pipeline/song_assemble.py`** — **factor out** the shared helpers already
  living here (`_write_ass_subtitles`, `_escape_ffmpeg_filter_path`,
  watermark/metadata builders) so `song_cinematic.py` reuses them. **No behavior
  change to the static path.**
- **`run.py`** (song branch), **`pipeline/api.py`** (`/songs`, credits),
  **Flutter** (`new_song_screen`, models/client) — wiring (§API/Credits/Flutter).

### Boundary rationale

`song_scenes.py` is deliberately pure — all the tricky cadence / pool-cycling
logic lives there with zero ffmpeg or file dependencies, so it can be
exhaustively unit-tested. `song_cinematic.py` only translates a finished
schedule into an ffmpeg string. That split is what makes the risky part safe.

## Data flow & run lifecycle

### New state fields (`song.json` / `state.json`)

```
video_mode:    "static" | "cinematic"    # set at POST /songs; default "static"
art_direction: "<one shared look>"
scene_prompts: ["<section 1 image>", ...]  # ~6–10
```

### New artifacts per run

```
beats.json              ← {tempo_bpm, beat_times[], source}   (song_beats)
scenes/scene_01.png …   ← the pool (cover.png doubles as poster/thumbnail)
```

The cut schedule stays **in-memory** — recomputed deterministically from
`beats.json` + `lyrics.json` at assemble time. Cheap; not worth persisting.

### Cinematic run lifecycle

The `static` path is unchanged. Cinematic inserts two stages and swaps the
assembler:

```
writing-lyrics      → also emits art_direction + scene_prompts
awaiting-approval    (review/regen as today; cost shows 2 credits)
approved             (deduct 2 credits)
generating-song      Suno → song.mp3 + takes          ← unchanged
generating-cover     Flux → cover.png + scenes/*.png  ← extended: render the pool
  └─ align lyrics → lyrics.json                       ← unchanged
detecting-beats      song_beats → beats.json          ← NEW, cheap (~seconds)
assembling           song_cinematic → final.mp4       ← NEW assembler (Approach A)
done | failed
```

`detecting-beats` is its own resumable stage (skips if `beats.json` exists),
matching the "artifact exists → skip" invariant.

### Core logic — `build_cut_schedule` (`song_scenes.py`)

Inputs: `beat_times[]`, `sections[]` (from `lyrics.json`), `pool_size`,
`bars_per_cut` (default 4), `beats_per_bar` (default 4), `audio_duration`.

1. **Snap to bars.** Group beats into bars; place a cut boundary every
   `bars_per_cut` bars → cut times that land *on the beat*.
2. **Assign an image per segment.** Walk segments in order; advance through the
   pool so each section's image gets screen time, and **reuse the chorus image
   whenever a `[Chorus]` section repeats** (recurring hook = recurring visual).
3. **Alternate `zoom_dir`** per segment so consecutive cuts to the same image
   still feel alive. v1: `zoom_dir ∈ {"in", "out"}` (Ken-Burns zoom direction,
   reusing today's `zoompan`). Directional panning is a future option.
4. **Guards:** enforce a min segment length (no sub-0.5s flashes — fold short
   tail beats into the previous segment); the last segment extends to
   `audio_duration`; if `beat_times` is empty, fall back to **section-boundary**
   cuts (still cinematic, not beat-snapped); cap total segments (merge to keep
   ≤ ~60) and `log()` if capped (no silent truncation).

Output: a complete, validated timeline that `song_cinematic.py` turns directly
into the filtergraph.

Example: 120 BPM, 4/4, cut every 4 bars → a cut every 8s; a 3:30 song → ~26
segments cycling an 8-image pool, chorus image recurring on each chorus.

## API, credits & Flutter wiring

### API (`pipeline/api.py`)

- `POST /songs` — body gains `video_mode: "static" | "cinematic"` (default
  `"static"` → every existing caller unaffected). Stored in `song.json`.
- `GET /songs/{id}/script` — cost block branches on `video_mode`: static =
  `suno + cover`; cinematic = `suno + (pool_size × cover_cost)`. Returns **credit
  count (1 vs 2)** and the **dollar figure** (cost-disclosure rule: real $ shown
  before any paid run).
- `POST /songs/{id}/approve` — deducts `1` or `2` credits via the existing
  `check_or_deduct` transaction, keyed on `video_mode`. The 402 guard reads the
  right amount.
- `SongRunSummary` gains `video_mode` so the list/detail UI can badge cinematic
  songs.

### Credits (`config.yaml` + `pipeline/credits.py`)

```yaml
song:
  credits_per_song: 1            # static (unchanged)
  cinematic_credits_per_song: 2  # NEW
  cinematic_pool_size: 7         # NEW — caps Flux cost & free-grant burn
  bars_per_cut: 4                # NEW — cadence knob
```

### Flutter (`lib/`)

- `new_song_screen.dart` — segmented toggle: **"Static cover · 1 credit"** vs
  **"Cinematic video · 2 credits"** + a one-line explainer. Passes `video_mode`
  into the create request.
- `api/models.dart` — `NewSongRequest` gains `video_mode`; `SongRunSummary` gains
  it too (default `"static"` so older shares deserialize).
- `api/client.dart` — thread `video_mode` through `createSong(...)`.
- `song_approve_screen.dart` / `cost_screen.dart` — show the 2-credit + dollar
  figure for cinematic before the spend confirm.

### Economics flag (open item for the owner)

A 7-image pool is ~$0.21 Flux + $0.05 Suno ≈ **$0.26 raw**, while 2 credits ≈
**$0.20** of ledger value — so at 2 credits cinematic is roughly
**break-even-to-slightly-negative**, and on the 60-credit free signup grant it is
pure cost. Spec ships **2 credits + pool cap 7** per the Q4 decision; bumping to
**3 credits** (healthy margin) or lowering the pool cap is a one-line
`config.yaml` change. Decide before launch.

## Error handling & graceful degradation

Guiding rule: **the user always ends with a playable video, and never overpays
for a downgrade.** Degradation ladder, top to bottom:

1. **Beat detection fails** → `build_cut_schedule` falls back to
   section-boundary cuts from `lyrics.json` (`beats.json.source = "fallback"`).
   Never fails the run.
2. **A pool image fails** → retry once, then **reuse `cover.png`** (or previous
   scene) for that slot. Only a cover failure fails the run (identical to today's
   static behavior).
3. **Cinematic ffmpeg render fails** → retry once, then **fall back to
   `assemble_song_video` (static path)** so the user still gets a playable file,
   **and refund the 1-credit surcharge** via the existing `credit-back` infra
   (effectively charged 1), with a clear `state.note`.
4. **Output-validity gate** — after render, `ffprobe` the result to confirm a
   video stream + audio stream + nonzero duration *before* marking `done`. Cheap
   insurance against the `MEDIA_ERR_SRC_NOT_SUPPORTED` class.
5. **Filtergraph-length guard** — cap total segments (≤ ~60); `log()` if capped —
   no silent truncation.
6. **GCS Fuse** — `song_cinematic` reuses `song_assemble`'s exact
   single-write-`.tmp`-then-atomic-rename + pre-delete pattern. No new Fuse
   surface.

## Testing

Mirrors the repo invariant — **external services mocked; ffmpeg runs locally on
tiny inputs** (as `test_assemble.py` already does).

- **`song_scenes.py` (pure — bulk of coverage):** cadence (cut every
  `bars_per_cut`); pool cycling assigns every section an image; **chorus image
  recurs** on repeated `[Chorus]`; `zoom_dir` alternates; min-segment-length
  folds sub-0.5s flashes; last segment extends to `audio_duration`; empty beats →
  section fallback; single-section song; `pool_size` greater/less than section
  count; segment-cap on pathological input.
- **`song_beats.py`:** monkeypatch librosa; parse `beat_track` output; fallback
  when librosa raises / returns empty → fixed-BPM grid.
- **`song_cinematic.py`:** unit-test `build_filter_complex(schedule, …)` as a
  pure string builder — every image referenced, `xfade` offsets match segment
  boundaries, labels chain validly. No ffmpeg in the unit test.
- **Integration smoke** (mirrors `test_run_song_mode.py`): real ffmpeg on 2–3
  tiny PNGs + short sine audio + a 2-line `lyrics.json` → assert a playable mp4,
  correct duration, both streams present (ffprobe).
- **Credits / API:** `POST /songs video_mode="cinematic"` → `/script` returns 2
  credits + correct $; approve deducts 2; <2 credits → 402; static still deducts
  1; **render-failure → static fallback + 1-credit refund recorded in the
  ledger**.
- **Degradation:** beat-detection failure still yields a schedule; scene-image
  failure reuses cover and completes.

## Dependency note

`librosa` is the new runtime dependency (`beat_track` → tempo + beat times).
`torch`/`numpy` already ship (Whisper), so the marginal weight is `scipy` /
`numba`. Add to `pyproject.toml` runtime deps; confirm it installs in the slim
Linux Docker image (Cloud Run) and not just macOS.