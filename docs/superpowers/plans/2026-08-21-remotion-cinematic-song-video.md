# Remotion Cinematic Song Video — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render the `video_mode="animated"` song video as a studio-grade, cinematic, cover-led clip via Remotion (headless Chromium), replacing the amateur procedural-ffmpeg FX path — at $0.

**Architecture:** A self-contained Node/Remotion project (`remotion/`) defines one genre-themed `SongVideo` composition (full-bleed graded cover + push-in + grain + letterbox + lower-third fade-in captions + embedded audio). The Python worker writes `props.json` from artifacts it already produces and shells out to `remotion render`; on failure it falls back to the static assembler with a visible `video_downgraded` flag. Remotion + Node + Chromium are bundled into the render image.

**Tech Stack:** Remotion (React/TypeScript, free tier, self-hosted), headless Chromium, Node LTS, vitest (TS unit tests), Python 3.13 + pytest (driver + routing), ffmpeg (mux + static fallback).

**Spec:** `docs/superpowers/specs/2026-08-21-remotion-cinematic-song-video-design.md`

## Global Constraints

- **$0 only:** Remotion **free tier**, self-hosted headless Chromium (NEVER Remotion Lambda / paid cloud). No AI, no per-render cost, no paid assets.
- Python files start with `from __future__ import annotations`; `pathlib.Path`; absolute imports (`from pipeline.x import y`).
- **External processes mocked in tests** — never run real `remotion render` / ffmpeg / Chromium in pytest. Python tests mock the single `subprocess.run` seam. TS unit tests cover PURE logic only (no Chromium); the full render is verified once, manually.
- Resumable: skip if `final.mp4` exists. Write to a LOCAL temp then `shutil.copyfile` onto the gcsfuse mount (never faststart/seek directly on Fuse).
- **Cover-led:** the cover dominates; captions are restrained lower-third. Line-level fade captions only (no per-word karaoke in v1).
- `genre_key` values are exactly the keys of `GENRE_RECIPES` (`pipeline/song_style.py`): arabic_pop, arabic_ballad, khaleeji, tarab_classic, arabic_trap, folk_shaabi, hiphop_rap, rnb_soul, pop, rock, edm_electropop, cinematic_ost, generic.
- Output 1080×1920, 30 fps. `durationInFrames = ceil(audio_seconds * 30)`.
- `static` and existing beat-cut `cinematic` modes MUST remain unchanged.
- Arabic fonts must be loaded before frame 0 (via `@remotion/fonts` + `delayRender`) or Arabic renders as tofu.

## File Structure

- Create: `remotion/package.json`, `remotion/tsconfig.json`, `remotion/remotion.config.ts`, `remotion/vitest.config.ts`
- Create: `remotion/src/Root.tsx` (registers the composition), `remotion/src/theme.ts` (+ `theme.test.ts`)
- Create: `remotion/src/CoverBackdrop.tsx`, `remotion/src/Grain.tsx`, `remotion/src/Letterbox.tsx`, `remotion/src/Vignette.tsx`
- Create: `remotion/src/LyricCaptions.tsx` (+ `captions.ts` pure helper + `captions.test.ts`)
- Create: `remotion/src/SongVideo.tsx`, `remotion/src/props.ts` (the shared props type)
- Create: `remotion/public/fonts/` (copies of `assets/fonts/Amiri-Regular.ttf`, `Inter-Bold.ttf`)
- Create: `pipeline/song_remotion.py` (+ `tests/test_song_remotion.py`)
- Modify: `run.py` (animated branch → Remotion), `tests/test_run_song_mode.py`
- Modify: `Dockerfile` (Node + Chromium + remotion project)
- Delete (supersession): `pipeline/song_animate.py`, `pipeline/song_kinetic_ass.py`, `pipeline/song_overlays.py`, `pipeline/song_ass_util.py`, `pipeline/song_visual_style.py`, `scripts/gen_overlays.py`, `assets/overlays/`, and their tests — done in Task 7 after nothing imports them.

---

### Task 1: Remotion project scaffold + genre theme

**Files:**
- Create: `remotion/package.json`, `remotion/tsconfig.json`, `remotion/remotion.config.ts`, `remotion/vitest.config.ts`, `remotion/src/props.ts`, `remotion/src/theme.ts`, `remotion/src/Root.tsx`
- Test: `remotion/src/theme.test.ts`

**Interfaces:**
- Produces: `SongProps` (TS type), `genreTheme(genreKey: string): Theme`, composition id `"SongVideo"`.

- [ ] **Step 1: Scaffold the project**

`remotion/package.json` (pin Remotion 4.x; scripts for render + test):
```json
{
  "name": "faceless-remotion",
  "private": true,
  "version": "1.0.0",
  "scripts": {
    "test": "vitest run",
    "render": "remotion render"
  },
  "dependencies": {
    "@remotion/cli": "4.0.220",
    "@remotion/fonts": "4.0.220",
    "remotion": "4.0.220",
    "react": "18.3.1",
    "react-dom": "18.3.1"
  },
  "devDependencies": {
    "@types/react": "18.3.3",
    "typescript": "5.5.4",
    "vitest": "2.0.5"
  }
}
```
`remotion/tsconfig.json`: standard React/ESNext (`jsx: "react-jsx"`, `strict: true`, `moduleResolution: "bundler"`).
`remotion/remotion.config.ts`:
```ts
import {Config} from '@remotion/cli/config';
Config.setVideoImageFormat('jpeg');
Config.setConcurrency(null); // null = auto (vCPU count)
```
`remotion/vitest.config.ts`: `import {defineConfig} from 'vitest/config'; export default defineConfig({test:{environment:'node'}});`

- [ ] **Step 2: Write the failing theme test**

```ts
// remotion/src/theme.test.ts
import {describe, it, expect} from 'vitest';
import {genreTheme} from './theme';

const KEYS = ['arabic_pop','arabic_ballad','khaleeji','tarab_classic','arabic_trap',
  'folk_shaabi','hiphop_rap','rnb_soul','pop','rock','edm_electropop','cinematic_ost','generic'];

describe('genreTheme', () => {
  it('returns a full theme for every genre key', () => {
    for (const k of KEYS) {
      const t = genreTheme(k);
      expect(t.grade).toMatch(/contrast|saturate|brightness/);
      expect(t.accent).toMatch(/^#[0-9a-fA-F]{6}$/);
      expect(t.fontFamily.length).toBeGreaterThan(0);
      expect(t.pushInTo).toBeGreaterThan(1);
      expect(t.grainOpacity).toBeGreaterThanOrEqual(0);
      expect(t.letterboxPct).toBeGreaterThan(0);
    }
  });
  it('falls back to generic for unknown keys', () => {
    expect(genreTheme('nope')).toEqual(genreTheme('generic'));
  });
  it('trap is punchier than ballad', () => {
    expect(genreTheme('arabic_trap').pushInTo).toBeGreaterThan(genreTheme('arabic_ballad').pushInTo);
  });
});
```

- [ ] **Step 3: Run test — expect FAIL**

Run: `cd remotion && npm install && npm test`
Expected: FAIL (theme not defined).

- [ ] **Step 4: Implement `props.ts` + `theme.ts`**

```ts
// remotion/src/props.ts
export type LyricLine = {text: string; start: number; end: number};
export type SongProps = {
  coverPath: string; audioPath: string;
  genreKey: string; title: string; artist: string;
  lyrics: LyricLine[]; beatTimes: number[]; tempoBpm: number;
};
```
```ts
// remotion/src/theme.ts
export type Theme = {grade: string; accent: string; fontFamily: string;
  pushInTo: number; grainOpacity: number; letterboxPct: number};
const AMIRI = 'Amiri', INTER = 'Inter';
const THEMES: Record<string, Theme> = {
  arabic_trap: {grade:'contrast(1.15) saturate(1.25) brightness(0.95)', accent:'#00fff7',
    fontFamily:INTER, pushInTo:1.14, grainOpacity:0.10, letterboxPct:7},
  arabic_ballad: {grade:'contrast(1.05) saturate(1.05) brightness(1.0) sepia(0.08)', accent:'#ffd3a8',
    fontFamily:AMIRI, pushInTo:1.08, grainOpacity:0.07, letterboxPct:9},
  tarab_classic: {grade:'contrast(1.08) saturate(0.95) sepia(0.18)', accent:'#f3d98b',
    fontFamily:AMIRI, pushInTo:1.07, grainOpacity:0.09, letterboxPct:10},
  // ... one entry per GENRE_RECIPES key (port palettes/vibe from the OLD
  // pipeline/song_visual_style.py before it is deleted in Task 7) ...
  generic: {grade:'contrast(1.08) saturate(1.1) brightness(1.0)', accent:'#7c5cff',
    fontFamily:INTER, pushInTo:1.10, grainOpacity:0.08, letterboxPct:8},
};
export const genreTheme = (k: string): Theme => THEMES[k] ?? THEMES.generic;
```
Implementer: fill in ALL 13 keys (the test enforces it), porting each genre's palette/vibe from the current `pipeline/song_visual_style.py` (accent from its `accent1`; ballad/tarab warmer + gentler push-in; trap/edm/rock punchier). `Root.tsx`: register a placeholder `SongVideo` composition (real body arrives in Task 5) so `remotion compositions` resolves:
```tsx
// remotion/src/Root.tsx
import {Composition} from 'remotion';
import {SongVideo} from './SongVideo';
export const RemotionRoot = () => (
  <Composition id="SongVideo" component={SongVideo}
    durationInFrames={300} fps={30} width={1080} height={1920}
    defaultProps={{coverPath:'',audioPath:'',genreKey:'generic',title:'',artist:'',lyrics:[],beatTimes:[],tempoBpm:120}} />
);
```
(Task 5 adds `calculateMetadata`. For Task 1, a minimal `SongVideo.tsx` returning `<AbsoluteFill/>` is enough to compile.)

- [ ] **Step 5: Run test — expect PASS**; then **commit**

Run: `cd remotion && npm test` → PASS.
```bash
git add remotion/ && git commit -m "feat(remotion): scaffold project + genre theme"
```

---

### Task 2: CoverBackdrop + treatment layers (Grain, Letterbox, Vignette)

**Files:**
- Create: `remotion/src/CoverBackdrop.tsx`, `remotion/src/Grain.tsx`, `remotion/src/Letterbox.tsx`, `remotion/src/Vignette.tsx`, `remotion/src/motion.ts`
- Test: `remotion/src/motion.test.ts`

**Interfaces:**
- Consumes: `genreTheme` (Task 1), `SongProps`.
- Produces: `pushInScale(frame, durationInFrames, pushInTo, beatTimes, fps): number`; the four backdrop components.

- [ ] **Step 1: Failing test for the pure motion helper**

```ts
// remotion/src/motion.test.ts
import {describe,it,expect} from 'vitest';
import {pushInScale} from './motion';
describe('pushInScale', () => {
  it('eases from 1.0 up to pushInTo across the clip', () => {
    expect(pushInScale(0, 300, 1.1, [], 30)).toBeCloseTo(1.0, 2);
    expect(pushInScale(300, 300, 1.1, [], 30)).toBeCloseTo(1.1, 2);
  });
  it('adds a small beat bump near a beat', () => {
    const base = pushInScale(30, 300, 1.1, [], 30);       // t=1.0s, no beats
    const bumped = pushInScale(30, 300, 1.1, [1.0], 30);  // beat exactly at t=1.0s
    expect(bumped).toBeGreaterThan(base);
    expect(bumped - base).toBeLessThan(0.03);             // subtle
  });
});
```

- [ ] **Step 2: Run — expect FAIL** (`cd remotion && npm test motion`).

- [ ] **Step 3: Implement `motion.ts` + the components**

```ts
// remotion/src/motion.ts
import {interpolate} from 'remotion';
export function pushInScale(frame:number, dur:number, to:number, beats:number[], fps:number):number {
  const base = interpolate(frame, [0, dur], [1.0, to], {extrapolateRight:'clamp'});
  const t = frame / fps;
  let bump = 0;
  for (const b of beats) {
    const d = t - b;
    if (d >= 0 && d < 0.20) { bump = Math.max(bump, 0.012 * (1 - d / 0.20)); }
  }
  return base + bump;
}
```
`CoverBackdrop.tsx`: `<AbsoluteFill>` with `<Img src={coverPath}>` sized to cover, `transform: scale(pushInScale(...))`, `filter: theme.grade`. `Grain.tsx`: `<AbsoluteFill>` an inline SVG `feTurbulence` (seed = `useCurrentFrame()`), `opacity: theme.grainOpacity`, `mixBlendMode:'overlay'`. `Letterbox.tsx`: top+bottom black bars each `theme.letterboxPct%` tall. `Vignette.tsx`: `<AbsoluteFill>` `background: radial-gradient(120% 90% at 50% 45%, transparent 55%, rgba(0,0,0,0.55))`.

- [ ] **Step 4: Run — expect PASS**; **commit**
```bash
git add remotion/src && git commit -m "feat(remotion): cover backdrop + grain/letterbox/vignette"
```

---

### Task 3: LyricCaptions (line fade/slide from timed lyrics)

**Files:**
- Create: `remotion/src/captions.ts`, `remotion/src/LyricCaptions.tsx`
- Test: `remotion/src/captions.test.ts`

**Interfaces:**
- Consumes: `LyricLine[]`, `genreTheme`.
- Produces: `activeLine(lyrics, tSeconds): {line: LyricLine, opacity: number} | null` (pure); `<LyricCaptions>`.

- [ ] **Step 1: Failing test**

```ts
// remotion/src/captions.test.ts
import {describe,it,expect} from 'vitest';
import {activeLine} from './captions';
const L = [{text:'a',start:0,end:2},{text:'b',start:2,end:4}];
describe('activeLine', () => {
  it('picks the line covering t', () => {
    expect(activeLine(L, 1)!.line.text).toBe('a');
    expect(activeLine(L, 3)!.line.text).toBe('b');
  });
  it('fades in at line start and out at line end', () => {
    expect(activeLine(L, 0.05)!.opacity).toBeLessThan(1);   // fading in
    expect(activeLine(L, 1.0)!.opacity).toBeCloseTo(1, 1);  // held
    expect(activeLine(L, 1.95)!.opacity).toBeLessThan(1);   // fading out
  });
  it('returns null in a gap', () => {
    expect(activeLine([{text:'a',start:0,end:1}], 5)).toBeNull();
  });
});
```

- [ ] **Step 2: Run — expect FAIL.**
- [ ] **Step 3: Implement**
```ts
// remotion/src/captions.ts
import type {LyricLine} from './props';
const FADE = 0.3; // seconds
export function activeLine(lyrics: LyricLine[], t: number) {
  const line = lyrics.find(l => t >= l.start && t < l.end);
  if (!line) return null;
  const inA = Math.min(1, (t - line.start) / FADE);
  const outA = Math.min(1, (line.end - t) / FADE);
  return {line, opacity: Math.max(0, Math.min(inA, outA))};
}
```
`LyricCaptions.tsx`: compute `t = useCurrentFrame()/fps`, call `activeLine`; render the line lower-third (`position:absolute; bottom: 16%`), RTL for Arabic, `opacity`, small `translateY` slide (e.g. `${(1-opacity)*12}px`), theme font + `color:#f2ede4`, subtle text-shadow. Restrained size (cover-led): ~40px.

- [ ] **Step 4: Run — expect PASS**; **commit**
```bash
git add remotion/src && git commit -m "feat(remotion): lower-third fade-in lyric captions"
```

---

### Task 4: SongVideo composition (compose + audio + fonts + metadata)

**Files:**
- Modify: `remotion/src/SongVideo.tsx`, `remotion/src/Root.tsx`
- Create: `remotion/src/fonts.ts`; copy `assets/fonts/Amiri-Regular.ttf` + `Inter-Bold.ttf` → `remotion/public/fonts/`
- Test: `remotion/src/songvideo.test.ts` (pure `calculateMetadata` only)

**Interfaces:**
- Consumes: all Task 1-3 exports.
- Produces: `SongVideo` component + `calculateSongMetadata` (durationInFrames from audio).

- [ ] **Step 1: Failing test for metadata math**
```ts
// remotion/src/songvideo.test.ts
import {describe,it,expect} from 'vitest';
import {framesForDuration} from './SongVideo';
describe('framesForDuration', () => {
  it('ceils seconds*fps', () => {
    expect(framesForDuration(10, 30)).toBe(300);
    expect(framesForDuration(10.01, 30)).toBe(301);
  });
});
```

- [ ] **Step 2: Run — expect FAIL.**
- [ ] **Step 3: Implement**
`fonts.ts`: `loadFont` for Amiri + Inter from `staticFile('fonts/…')` wrapped in `delayRender`/`continueRender`. `SongVideo.tsx`:
```tsx
import {AbsoluteFill, Audio, staticFile} from 'remotion';
import {CoverBackdrop} from './CoverBackdrop';
import {Grain} from './Grain'; import {Letterbox} from './Letterbox';
import {Vignette} from './Vignette'; import {LyricCaptions} from './LyricCaptions';
import type {SongProps} from './props';
import './fonts';
export const framesForDuration = (sec:number, fps:number) => Math.ceil(sec*fps);
export const SongVideo: React.FC<SongProps> = (p) => (
  <AbsoluteFill style={{backgroundColor:'#000'}}>
    <CoverBackdrop {...p}/><Grain {...p}/><Vignette/><Letterbox {...p}/>
    <LyricCaptions {...p}/>
    <Audio src={p.audioPath.startsWith('http')?p.audioPath:`file://${p.audioPath}`}/>
  </AbsoluteFill>
);
```
`Root.tsx`: add `calculateMetadata` that reads audio duration via `@remotion/media-utils` `getAudioDurationInSeconds(props.audioPath)` → `durationInFrames = framesForDuration(sec, 30)`. (Add `@remotion/media-utils` to deps.)

- [ ] **Step 4: Run — expect PASS**; **commit**
```bash
git add remotion/ && git commit -m "feat(remotion): SongVideo composition + audio + fonts + metadata"
```

---

### Task 5: Python driver `pipeline/song_remotion.py`

**Files:**
- Create: `pipeline/song_remotion.py`
- Test: `tests/test_song_remotion.py`

**Interfaces:**
- Consumes: `song_assemble.ffprobe_duration`, the run-dir artifacts (`cover.png`, `song.mp3`, `lyrics_timing.json`, `beats.json`).
- Produces: `render_song_video(*, run_dir: Path, genre_key: str, title: str, artist: str | None, out_path: Path) -> Path`; `build_props(run_dir, genre_key, title, artist, fps=30) -> dict`.

- [ ] **Step 1: Failing tests**
```python
# tests/test_song_remotion.py
from __future__ import annotations
import json
from pathlib import Path
import pipeline.song_remotion as sr

def _seed(run_dir: Path):
    (run_dir / "cover.png").write_bytes(b"png")
    (run_dir / "song.mp3").write_bytes(b"mp3")
    (run_dir / "lyrics_timing.json").write_text(json.dumps({"lines":[
        {"kind":"section","text":"Verse 1","start":0,"end":0,"stanza":1},
        {"kind":"line","text":"في ليل","start":1.0,"end":3.0,"stanza":1,"words":[]}]}))
    (run_dir / "beats.json").write_text(json.dumps({"tempo_bpm":96,"beat_times":[0.5,1.0]}))

def test_build_props_shapes_the_contract(monkeypatch, tmp_path):
    _seed(tmp_path)
    monkeypatch.setattr(sr, "ffprobe_duration", lambda p: 10.0)
    props = sr.build_props(tmp_path, "arabic_trap", "T", "Layla")
    assert props["genreKey"] == "arabic_trap"
    assert props["durationInFrames"] == 300  # 10*30
    assert props["lyrics"] == [{"text":"في ليل","start":1.0,"end":3.0}]
    assert props["beatTimes"] == [0.5,1.0] and props["tempoBpm"] == 96
    assert props["coverPath"].endswith("cover.png")

def test_render_invokes_remotion_and_writes_output(monkeypatch, tmp_path):
    _seed(tmp_path); monkeypatch.setattr(sr, "ffprobe_duration", lambda p: 5.0)
    calls = {}
    def fake_run(cmd, **k):
        calls["cmd"] = cmd
        # emulate remotion writing the --output file (last arg after --output)
        out = cmd[cmd.index("--output")+1]; Path(out).write_bytes(b"mp4")
        class R: returncode=0; stderr=b""
        return R()
    monkeypatch.setattr(sr.subprocess, "run", fake_run)
    out = tmp_path / "final.mp4"
    res = sr.render_song_video(run_dir=tmp_path, genre_key="pop", title="T", artist=None, out_path=out)
    assert res == out and out.exists()
    assert "render" in calls["cmd"] and "SongVideo" in calls["cmd"]

def test_render_resumable(monkeypatch, tmp_path):
    out = tmp_path / "final.mp4"; out.write_bytes(b"exists")
    def boom(*a, **k): raise AssertionError("must not render when output exists")
    monkeypatch.setattr(sr.subprocess, "run", boom)
    assert sr.render_song_video(run_dir=tmp_path, genre_key="pop", title="T", artist=None, out_path=out) == out

def test_render_raises_on_nonzero(monkeypatch, tmp_path):
    _seed(tmp_path); monkeypatch.setattr(sr, "ffprobe_duration", lambda p: 5.0)
    class R: returncode=1; stderr=b"boom"
    monkeypatch.setattr(sr.subprocess, "run", lambda cmd, **k: R())
    import pytest
    with pytest.raises(RuntimeError):
        sr.render_song_video(run_dir=tmp_path, genre_key="pop", title="T", artist=None, out_path=tmp_path/"final.mp4")
```

- [ ] **Step 2: Run — expect FAIL** (`uv run pytest tests/test_song_remotion.py -q`).
- [ ] **Step 3: Implement**
```python
# pipeline/song_remotion.py
from __future__ import annotations
import json, os, shutil, subprocess, tempfile
from pathlib import Path
from pipeline.song_assemble import ffprobe_duration

REPO_ROOT = Path(__file__).resolve().parent.parent
REMOTION_DIR = REPO_ROOT / "remotion"
FPS = 30

def build_props(run_dir: Path, genre_key: str, title: str, artist: str | None,
                fps: int = FPS) -> dict:
    timing = json.loads((run_dir / "lyrics_timing.json").read_text())
    lines = [{"text": it["text"], "start": it["start"], "end": it["end"]}
             for it in timing.get("lines", []) if it.get("kind") == "line"]
    beats = json.loads((run_dir / "beats.json").read_text()) if (run_dir / "beats.json").exists() else {}
    sec = ffprobe_duration(run_dir / "song.mp3")
    import math
    return {
        "coverPath": str(run_dir / "cover.png"),
        "audioPath": str(run_dir / "song.mp3"),
        "genreKey": genre_key, "title": title, "artist": artist or "",
        "lyrics": lines, "beatTimes": beats.get("beat_times", []),
        "tempoBpm": beats.get("tempo_bpm", 120),
        "durationInFrames": math.ceil(sec * fps), "fps": fps,
        "width": 1080, "height": 1920,
    }

def render_song_video(*, run_dir: Path, genre_key: str, title: str,
                      artist: str | None, out_path: Path) -> Path:
    if out_path.exists():
        return out_path
    props = build_props(run_dir, genre_key, title, artist)
    props_path = run_dir / "props.json"
    props_path.write_text(json.dumps(props, ensure_ascii=False))
    tmp = Path(tempfile.mkdtemp(prefix="remotion-")) / "final.mp4"
    cmd = ["npx", "remotion", "render", "SongVideo",
           "--props", str(props_path), "--output", str(tmp),
           "--concurrency", str(os.cpu_count() or 2), "--log", "error"]
    r = subprocess.run(cmd, cwd=str(REMOTION_DIR), capture_output=True)
    if r.returncode != 0:
        err = (r.stderr or b"").decode("utf-8", "replace")[-800:]
        raise RuntimeError(f"remotion render failed: {err!r}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(tmp, out_path)
    return out_path
```

- [ ] **Step 4: Run — expect PASS**; **commit**
```bash
git add pipeline/song_remotion.py tests/test_song_remotion.py
git commit -m "feat(song-remotion): props builder + remotion render invocation"
```

---

### Task 6: Wire `animated` → Remotion in run.py (+ retire the procedural path)

**Files:**
- Modify: `run.py` (the `elif video_mode == "animated":` branch, ~lines 1519-1548)
- Test: `tests/test_run_song_mode.py`
- Delete: `pipeline/song_animate.py`, `pipeline/song_kinetic_ass.py`, `pipeline/song_overlays.py`, `pipeline/song_ass_util.py`, `pipeline/song_visual_style.py`, `scripts/gen_overlays.py`, `assets/overlays/`, and their test files (`tests/test_song_animate.py`, `tests/test_song_kinetic_ass.py`, `tests/test_song_overlays.py`, `tests/test_song_visual_style.py`).

**Interfaces:**
- Consumes: `song_remotion.render_song_video` (Task 5). NOTE: `song_ass_util` currently re-exports `_format_ass_time`/`_ass_escape`/`_escape_ffmpeg_filter_path` back INTO `song_assemble`; before deleting `song_ass_util`, move those three helpers BACK into `song_assemble.py` (inline) so `song_assemble`/`song_cinematic` still work.

- [ ] **Step 1: Failing routing tests**
```python
# tests/test_run_song_mode.py (add)
def test_animated_mode_calls_remotion(monkeypatch, tmp_path):
    import run as run_mod
    from pipeline import song_remotion
    called = {}
    monkeypatch.setattr(song_remotion, "render_song_video",
                        lambda **k: called.setdefault("hit", True) or k["out_path"])
    # ... arrange a resumed run_dir with video_mode="animated", song.mp3, cover.png,
    #     lyrics_timing.json, beats.json; monkeypatch align/beats to no-ops that
    #     write those files; invoke the post-approve song path ...
    assert called.get("hit") is True

def test_animated_fallback_sets_downgraded(monkeypatch, tmp_path):
    import run as run_mod
    from pipeline import song_remotion, song_assemble
    monkeypatch.setattr(song_remotion, "render_song_video",
                        lambda **k: (_ for _ in ()).throw(RuntimeError("render failed")))
    seen = {}
    monkeypatch.setattr(song_assemble, "assemble_song_video",
                        lambda **k: seen.setdefault("static", True))
    # ... invoke animated path; assert static fallback ran AND video_downgraded set ...
    assert seen.get("static") is True
```

- [ ] **Step 2: Run — expect FAIL.**
- [ ] **Step 3: Implement**
Replace the `elif video_mode == "animated":` body so it builds no ASS/template and calls Remotion, with a static fallback that sets `video_downgraded`:
```python
        elif video_mode == "animated":
            from pipeline import song_remotion
            try:
                song_remotion.render_song_video(
                    run_dir=run_dir, genre_key=_genre_key_from(script),
                    title=script.title, artist=_artist_name_or_none(...),
                    out_path=final_mp4)
            except Exception as anim_err:
                print(f"[song-post-approve] remotion render failed ({anim_err}); "
                      "falling back to static cover video")
                song_assemble.assemble_song_video(
                    cover_path=final_cover_path, song_mp3=song_mp3, out_mp4=final_mp4,
                    lyrics_json=lyrics_timing_path, title=script.title,
                    share_token=share_token)
                write_state(video_downgraded=True)
```
Match the exact in-scope variable names (`final_mp4`, `song_mp3`, `final_cover_path`, `lyrics_timing_path`, `share_token`, `script.title`) by reading the current static/cinematic branches. Then remove the now-dead `from pipeline import song_animate, song_kinetic_ass, song_visual_style` import in that branch. Move the three ASS helpers from `song_ass_util` back inline into `song_assemble.py`, then delete the superseded modules + their tests + `assets/overlays/`.

- [ ] **Step 4: Run the full suite** (`uv run pytest -q`, clean env) — green, and the deleted modules' tests are gone.
- [ ] **Step 5: Commit**
```bash
git add -A && git commit -m "feat(song): route animated video_mode to Remotion; retire procedural FX path"
```

---

### Task 7: Dockerfile — bundle Node + Chromium + the Remotion project

**Files:**
- Modify: `Dockerfile`

**Interfaces:** Consumes the `remotion/` project (Tasks 1-4) + `pipeline/song_remotion.py` (Task 5).

- [ ] **Step 1: Add Node + the Remotion install + Chromium**

After the existing `apt-get install` block, add Node LTS and the browser, and install the Remotion project. Concretely:
```dockerfile
# Node LTS (for Remotion). Uses nodesource; keep the layer before COPY so it caches.
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Remotion project + production node deps (cached unless remotion/ changes)
COPY remotion/ ./remotion/
RUN cd remotion && npm ci --omit=dev

# Bake the headless Chromium Remotion uses (no runtime download)
RUN cd remotion && npx remotion browser ensure
```
Keep the existing ffmpeg/font apt packages (Remotion muxes via ffmpeg; static/cinematic still need them). Chromium adds Remotion's own required libs — if `remotion browser ensure` reports missing shared libraries, add them to the apt block (Remotion prints the exact `apt-get install` line; common set: `libnss3 libatk-bridge2.0-0 libgtk-3-0 libasound2 libgbm1`).

- [ ] **Step 2: Verify the image builds + renders (manual verification — the ffmpeg-5.1.x-style gate)**

Build locally and run ONE real render end-to-end (this is the spec's manual verification gate; it needs real Chromium so it is NOT a CI test):
```bash
docker build -t faceless:remotion-test .
# inside a container with a seeded run dir (cover.png, song.mp3, lyrics_timing.json, beats.json):
#   uv run python -c "from pipeline.song_remotion import render_song_video; ..."
# Confirm: final.mp4 is produced, ~10-40 MB, Arabic captions render (not tofu),
# and note the render wall-time on the target Cloud Run Job CPU/RAM.
```
Record the render time + memory; if the job OOMs or times out, bump the Cloud Run Job resources (the deploy config) and/or lower `--concurrency`.

- [ ] **Step 3: Commit**
```bash
git add Dockerfile && git commit -m "build: bundle Node + Chromium + Remotion in the render image"
```

---

## Self-Review notes (for the executor)

- Every `GENRE_RECIPES` key must have a theme entry (Task 1 test enforces).
- Font loading (Task 4) is load-bearing — without `delayRender`+`loadFont`, Arabic captions render as tofu. Verify in Task 7's real render.
- The **render-time/memory risk is real** — Task 7 Step 2 measures it on true job resources; treat a too-slow/OOM render as a blocker to resolve (more RAM / lower concurrency / fps 24), not a pass.
- TS unit tests cover pure logic only (theme, motion, captions, metadata math). The composition + full render are verified once, manually, in Task 7 — consistent with the repo's "mock externals, verify the real thing" invariant.
- Deletions (Task 6) happen only after the helper move-back so `song_assemble`/`song_cinematic` keep working; run the full suite to confirm nothing imports the removed modules.
