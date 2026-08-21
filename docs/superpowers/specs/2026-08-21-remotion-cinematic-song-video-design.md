# Remotion Cinematic Song Video — Design

**Status:** approved direction (brainstormed 2026-08-21), ready for implementation plan.

## Goal

Replace the amateur procedural-ffmpeg animated song video with a **studio-grade, cinematic, cover-led** render produced by **Remotion** (a React/programmatic-video engine, rendered via headless Chromium) — at **$0** (Remotion free tier + self-hosted rendering on the existing Cloud Run free tier; no per-render, no license fee, no paid assets).

## Locked decisions (from the brainstorm)

- **Engine:** Remotion, **free tier** (individuals / teams ≤3 — faceless-lab is not under Binghatti and stays ≤3). Self-hosted rendering only — **never** Remotion Lambda (that's paid).
- **Aesthetic:** **Cinematic, cover-led.** The graded cover is full-bleed and dominates: slow push-in, per-genre color grade, film grain, letterbox bars, vignette; **elegant lower-third lyric captions that fade/slide in per line** (not the hero). Genre adapts grade/palette/type/motion-intensity.
- **Integration:** Remotion **bundled in the render worker image** (option A) — the Python worker shells out to `remotion render`. No separate service.

## Current state we build on / supersede

- The pipeline already produces, per song run, under `out/<run>/`: **`song.mp3`**, **`cover.png`**, **`lyrics_timing.json`** (from `song_align.align_song_lyrics` — per-line + per-word timings + `align_confidence` + section tags), **`beats.json`** (from `song_beats.detect_beats` — `tempo_bpm` + `beat_times`), and `genre_key`/title/artist in `api_state.json` + `song.json`.
- `video_mode="animated"` currently routes (run.py) to `song_animate.build_animated_video` (procedural ffmpeg FX). **This design supersedes that path**: `animated` will route to Remotion instead. The procedural FX modules (`pipeline/song_animate.py` FX chain, `pipeline/song_kinetic_ass.py`, `pipeline/song_overlays.py`, `scripts/gen_overlays.py`, `assets/overlays/`) become obsolete for `animated` and are removed. `static` and the existing beat-cut `cinematic` modes are **untouched**.
- The genre palette/vibe data in `pipeline/song_visual_style.py` is reused as the source for the Remotion genre theme (ported to TS), then `song_visual_style.py` (Python) is removed once nothing imports it.

## Non-goals (v1)

- No Remotion Lambda / any paid cloud rendering.
- No per-word karaoke (line-level fade captions only; cover-led).
- No 14 bespoke designs — ONE composition, genre-themed.
- No overlay-loop library (cinematic doesn't use it).
- `static` / `cinematic` modes unchanged.

## Architecture

```
Python render worker (Cloud Run Job, video_mode=animated)
  ├─ (existing) generate song.mp3, cover.png, lyrics_timing.json, beats.json
  ├─ pipeline/song_remotion.py:
  │    build props.json  → remotion render <SongVideo> --props props.json --output final.mp4
  │    (Node + Remotion + headless Chromium, all in the same image)
  └─ on success: final.mp4 ; on failure: static fallback + video_downgraded flag
```

### 1. Props contract — `props.json` (`pipeline/song_remotion.py` writes it)

The single interface between Python and the Remotion composition. All paths absolute (inside the render container).

```jsonc
{
  "coverPath": "/mnt/runs/.../cover.png",
  "audioPath": "/mnt/runs/.../song.mp3",
  "fps": 30,
  "width": 1080, "height": 1920,
  "durationInFrames": 4500,            // ceil(audio_seconds * fps)
  "genreKey": "arabic_trap",
  "title": "ليل المدينة", "artist": "Layla",
  "lyrics": [                          // from lyrics_timing.json, line-level
    {"text": "في ليل بعيد", "start": 12.30, "end": 17.90},
    ...
  ],
  "beatTimes": [0.51, 1.02, ...],      // from beats.json (for the beat pulse)
  "tempoBpm": 96
}
```

`song_remotion.py` derives `durationInFrames` from `ffprobe_duration(song.mp3) * fps`; maps `genre_key`; reads `lyrics_timing.json` line items (ignoring word-level for v1); reads `beats.json`.

### 2. The Remotion project — `remotion/`

A self-contained Node/TS project (its own `package.json`, `tsconfig.json`, `remotion.config.ts`). Not part of the Python package.

- **`src/SongVideo.tsx`** — the composition root. Props = the contract above. Renders `<AbsoluteFill>` layering (bottom→top): `<CoverBackdrop>`, `<Grain>`, `<Letterbox>`, `<Vignette>`, `<LyricCaptions>`, and `<Audio src={audioPath}>`. Registered in `src/Root.tsx` as composition id `SongVideo` with `durationInFrames`/`fps`/`width`/`height` driven by input props (via `calculateMetadata`).
- **`src/CoverBackdrop.tsx`** — full-bleed `<Img src={coverPath}>` with:
  - **push-in**: `scale = interpolate(frame, [0, durationInFrames], [1.0, 1.10])` (slow, eased), plus a **beat pulse**: a small `+scale` bump on frames nearest `beatTimes` (subtle, e.g. +0.01, decaying over ~6 frames).
  - **grade**: a CSS `filter` string from the genre theme (contrast/saturate/brightness/sepia/hue).
- **`src/Grain.tsx`** — an SVG `feTurbulence` noise `<AbsoluteFill>` at low opacity, `mix-blend-mode: overlay`, re-seeded per frame (deterministic from `frame`) so it shimmers like film grain.
- **`src/Letterbox.tsx`** — top/bottom black bars (ratio from theme, e.g. 8%).
- **`src/Vignette.tsx`** — radial-gradient darkening at the edges.
- **`src/LyricCaptions.tsx`** — the currently-active line (by `frame/fps` vs each line's `start`/`end`) rendered lower-third, with a fade+slide-in over ~8 frames at line start and fade-out at line end. Uses the theme font + accent. Cover-led → restrained size/weight.
- **`src/theme.ts`** — `genreTheme(genreKey)` → `{ grade: string(css filter), accent: string, fontFamily: string, pushInTo: number, grainOpacity: number, letterboxPct: number }`. One entry per `GENRE_RECIPES` key + a `generic` default (ported from `song_visual_style.py`). This is the single per-genre knob set.
- **Fonts:** the bundled Arabic/Latin faces (`assets/fonts/Amiri-Regular.ttf`, `Inter-Bold.ttf`) are `@font-face`-loaded in the composition (copied into `remotion/public/fonts/`), and awaited via `@remotion/fonts` `loadFont`/`delayRender` so Chromium has them before the first frame (otherwise Arabic renders tofu).

### 3. Python driver — `pipeline/song_remotion.py`

```python
def render_song_video(*, run_dir: Path, genre_key: str, title: str,
                      artist: str | None, out_path: Path) -> Path: ...
```
- Resumable: if `out_path` exists, return it.
- Builds `props.json` in `run_dir` from the existing artifacts + `ffprobe_duration`.
- Invokes `remotion render SongVideo --props <props.json> --output <tmp> --concurrency=<N>` via subprocess (the Remotion CLI, resolved from `remotion/node_modules`), rendering to a **local temp** then `shutil.copyfile` onto the gcsfuse mount (same off-Fuse pattern as `song_animate`).
- Raises on non-zero exit (stderr surfaced) so run.py's fallback fires.
- Mockable in tests via a single `subprocess.run` seam (like `song_animate._run`).

### 4. run.py wiring

The `video_mode == "animated"` branch calls `song_remotion.render_song_video(...)` instead of `song_animate.build_animated_video(...)`. On exception → fall back to `song_assemble.assemble_song_video(...)` **and set `video_downgraded=True`** in state so the API/app can show a "rendered as static" signal (fixes the silent fallback that hid the OOM bug). `align_song_lyrics` + `detect_beats` still run for `animated` (unchanged gate).

### 5. Dockerfile

Add to the render image: **Node LTS** (nvm/nodesource or `node:` multi-stage copy), the `remotion/` project with `npm ci --omit=dev`, and the headless browser via Remotion's `npx remotion browser ensure` (or `@remotion/renderer` `ensureBrowser()` at build) so Chromium is baked in — no runtime download. Keep ffmpeg (Remotion uses it for muxing; the static/cinematic modes still need it). Expected image growth ~1–1.3 GB.

## Data flow

`song.mp3` + `cover.png` + `lyrics_timing.json` + `beats.json` + `genre_key`/title/artist → `song_remotion.build props.json` → `remotion render SongVideo` (Chromium renders 4500 frames, muxes `<Audio>`) → `final.mp4` (local temp → copied to run dir).

## Error handling / fallbacks

- Remotion render non-zero exit / timeout → **fallback to static** `assemble_song_video` + `video_downgraded=True` (visible signal). Never a silently-wrong output.
- Missing font → guarded by `delayRender`/`loadFont` (render waits for fonts; if a font truly fails, log + continue with the fallback stack).
- Resumable: skip if `final.mp4` exists.
- Beats/lyrics missing → composition renders cover + push-in + grade with no captions/pulse (still a valid cinematic clip).
- All subprocess/ffmpeg/Chromium calls are mocked in tests (repo invariant — no real render in CI).

## Testing

- **Python (`pipeline/song_remotion.py`):** unit-test the props builder (durationInFrames math, genre_key mapping, lyrics line extraction, paths) and the render invocation (mocked `subprocess.run`: correct CLI + props path + output; resumable skip; raises on non-zero). run.py routing test: `animated` → `render_song_video` called; on raise → static fallback + `video_downgraded=True`.
- **Remotion (TS):** unit-test `genreTheme()` (every `GENRE_RECIPES` key resolves; generic default; valid CSS filter strings). Composition smoke: `@remotion/renderer` `selectComposition` + render **~3 frames** headless to assert it renders without error and produces frames (guarded to run only where Chromium is available; skipped in the Python CI lane).
- **Verification (manual, before ship):** one real full headless render of a sample song → eyeball quality + confirm size (~10–40 MB) + render time on the target job resources.

## Cost

**$0.** Remotion free tier (≤3 people, self-hosted). Headless Chromium runs in the existing Cloud Run Job (free tier). No AI, no per-render, no paid assets. The only "cost" is render *time*/compute (see risks).

## Risks & mitigations

- **Render time / compute (main risk):** Chromium rendering ~4500 frames is far heavier than an ffmpeg filtergraph — likely **minutes** per video and RAM-hungry. Mitigate: give the Cloud Run Job adequate CPU/RAM, set Remotion `--concurrency` to the vCPU count, keep fps at 30, and a generous job timeout. Measure on real job resources during verification; if too slow, drop to fps 24 or cap composition complexity. Still $0 within free-tier compute, just slower than ffmpeg.
- **Image size / cold start:** +~1.3 GB (Node + Chromium). Acceptable; mitigate with a multi-stage build + `--omit=dev`.
- **Arabic font rendering in Chromium:** must bundle fonts + `loadFont`/`delayRender` before frame 0 or Arabic is tofu. Covered in §2.
- **Remotion license (team size):** free only while ≤3 people; if faceless-lab grows past 3, a license is required. Documented; revisit if the team grows.
- **Determinism:** Remotion frames are deterministic → resumable + testable (a plus).
