# Animated Genre-Adaptive Song Video — Design

**Status:** approved direction (brainstormed 2026-08-20), ready for implementation plan.

## Goal

Replace the near-static song video (single cover + slow Ken Burns) with a
**layered, beat-synced, genre-adaptive animation** so the exported vertical
video is genuinely engaging and shareable — at **~$0 extra per render** (no AI
calls; more ffmpeg work only).

## Locked creative direction

From the visual brainstorm (companion mockups, 2026-08-20):

- **Layered blend**: the AI cover/stills in motion (backdrop) + **kinetic lyric
  typography** + **genre-reactive, beat-synced FX**, composited into one mp4.
- **Genre-adaptive**: the palette, font, lyric motion, transitions, and FX set
  switch on the song's `genre_key`. The **Trap/Mahragan high-energy look is the
  benchmark** — every genre gets its own *bold* treatment (a ballad is warm and
  slow but not sleepy).
- **Kinetic lyrics**: **karaoke (word-by-word highlight) on verses**,
  **hook-word emphasis (one big pulsing keyword) on the chorus**, with
  **line-snap (whole line slams in) as the fallback** whenever word-level timing
  for a line is low-confidence.
- **FX = procedural + a per-genre overlay-loop library.** Procedural ffmpeg does
  color-grade / beat-flash / zoom-parallax / light-sweep / RGB-glitch / grain;
  a bundled per-genre **overlay-loop library** (particles, bokeh, arabesque,
  geometric) is blended on top for extra "wow". Loops are a **one-time asset**,
  reused free on every render.

## Current state we build on (≈80% already exists)

- **Word-level lyric timing** — `pipeline/song_align.py:align_song_lyrics`
  force-aligns lyrics to the real audio via `pipeline/align.py:align_arabic`,
  which returns **per-word** `offset_ms`/`duration_ms`. It is used purely as a
  stopwatch; **Whisper's Arabic transcription is never displayed** (words are
  paired to the user-supplied lyrics by index). Karaoke depends on this and it
  already exists — today it is aggregated to line `start`/`end`.
- **Section labels** — `pipeline/song_lyrics.py` requires + validates Suno
  section tags (`[Verse 1]`, `[Chorus]`, `[Pre-Chorus]`, `[Bridge]`, `[Outro]`),
  so verse-vs-chorus is known deterministically.
- **Beat grid** — `pipeline/song_beats.py:detect_beats` → `{tempo_bpm,
  beat_times}` (librosa, with a fixed-BPM grid fallback). Resumable.
- **ASS + ffmpeg** — `pipeline/song_assemble.py` already burns line captions via
  libass (`ass=` filter) and does zoompan. **ASS natively supports karaoke
  (`\k`) and animated transforms (`\t`)**, so kinetic typography is a richer ASS
  builder, not new rendering tech. Escaping/time helpers are reusable.
- **Genre key** — `pipeline/song_style.py:compose_style` already returns
  `StyleResult.genre_key` (one of ~14 `GENRE_RECIPES` keys). This is the switch.

## Non-goals

- No per-render AI / generative video (that cost profile was explicitly
  rejected — see the pulled "perform" feature).
- Do not remove or change the existing `static` / `cinematic` modes.
- Not a live in-app visualizer — the deliverable is a rendered mp4.
- Not changing lyric or audio generation.

## Architecture

A new `video_mode: "animated"` selects a new orchestrator
`pipeline/song_animate.py`, which composes five units into `final.mp4`:

```
song.mp3 ─┬─ align_song_lyrics (+word timing) ──► lyrics_timing.json
          └─ detect_beats ─────────────────────► beats.json
genre_key ─► visual_template_for() ────────────► VisualTemplate
                                                     │
lyrics_timing + template + sections ─► build_kinetic_ass() ─► lyrics.ass
                                                     │
cover/stills + template + beats + lyrics.ass ─► build_animated_video() ─► final.mp4
```

Each unit is independently testable with a well-defined interface.

### 1. Genre visual-template registry — `pipeline/song_visual_style.py`

```python
@dataclass(frozen=True)
class LyricStyle:
    font_file: str            # path under assets/fonts
    karaoke_fill: str         # ASS &HBBGGRR& swept-in color (verses)
    karaoke_base: str         # not-yet-sung color
    hook_color: str           # chorus hook-word color
    outline: str; outline_w: int; glow: bool

@dataclass(frozen=True)
class VisualTemplate:
    genre_key: str
    bg: str; accent1: str; accent2: str; text: str   # palette
    lyric: LyricStyle
    fx_set: tuple[str, ...]    # procedural FX ids, e.g. ("grade_neon","beat_flash","rgb_glitch","grain")
    overlay_dir: str | None    # assets/overlays/<genre_key> or None
    transition: str            # cut style between stills ("hardcut","dip","glitch")

def visual_template_for(genre_key: str) -> VisualTemplate: ...
```

- One template per `GENRE_RECIPES` key (trap, arabic_ballad, tarab_classic,
  khaleeji, arabic_pop, arabic_trap, folk_shaabi, hiphop_rap, rnb_soul, pop,
  rock, edm_electropop, cinematic_ost) + a `generic` default that any unknown
  key resolves to. Pure data + a lookup; no I/O.
- This registry **is** the "changes by style" core. It is the single place a
  future genre look is tuned.

### 2. Word-level timing — extend `pipeline/song_align.py`

Extend the `lyrics_timing.json` line schema (backward-compatible — existing
`start`/`end` stay) to carry per-word timings and a per-line confidence:

```jsonc
{"kind":"line","text":"...","start":12.3,"end":17.9,"stanza":1,
 "words":[{"text":"في","start":12.30,"end":12.62},{"text":"ليل","start":12.62,"end":13.10}, ...],
 "align_confidence":0.86}
```

- `words[]` comes straight from the `align_arabic` `word_timings` already
  computed (currently discarded after deriving line bounds).
- `align_confidence` in [0,1] from a coverage heuristic (fraction of line words
  that received a timing before the stream ran out / large-gap detection). Drives
  the line-snap fallback. Whisper transcription is still never surfaced.

### 3. Kinetic-lyric ASS builder — `pipeline/song_kinetic_ass.py`

```python
def build_kinetic_ass(*, lyrics_timing: dict, template: VisualTemplate,
                      out_path: Path, min_confidence: float = 0.6) -> Path: ...
```

- **Verse lines** (section is Verse/Pre-Chorus/Bridge/Outro) → **karaoke**: one
  Dialogue event per line with `{\k<cs>}` before each word (centiseconds from
  `words[]`), styled with `template.lyric` (base vs swept-fill colors).
- **Chorus lines** → **hook-word**: pick the salient content word (longest
  non-stopword, tie-broken by repetition across the chorus); render it large
  with a `\t(...\fscx/\fscy...)` pulse on the beat, the rest small around it.
- **Low confidence** (`align_confidence < min_confidence`) or a line with no
  `words[]` → **line-snap**: whole line, scale+fade in at the line `start`.
- RTL-aware for Arabic; LTR for English. Reuses `_format_ass_time`,
  `_ass_escape`, and the path-escaping helpers already in `song_assemble.py`
  (extract shared helpers to avoid duplication).

### 4. Genre FX compositor — `pipeline/song_animate.py`

```python
def build_animated_video(*, backdrop: Path | list[Path], song_mp3: Path,
                         ass_path: Path, beats: dict, template: VisualTemplate,
                         out_path: Path, size=(1080,1920)) -> Path: ...
```

Builds one ffmpeg filtergraph, layered bottom→top:

1. **Backdrop motion** — static cover → zoompan/parallax push-in; cinematic
   stills → beat-timed cuts (reuse the cut-schedule logic) with
   `template.transition`.
2. **Procedural FX** from `template.fx_set` — color grade (`curves`/`eq`),
   **beat-flash** (`drawbox`/`eq` brightness `enable`'d on `beat_times`,
   e.g. `enable='between(t,B,B+0.08)'` generated per beat), animated **light
   sweep** (moving gradient overlay), **rgb-glitch** (`rgbashift`/`chromashift`
   pulsed on beats), **grain** (`noise`), **vignette**.
3. **Overlay loops** — if `template.overlay_dir` has clips, `-stream_loop` the
   genre loop, scale to frame, and blend (`blend=screen`/`overlay`) at a tuned
   opacity. Absent → skip (procedural only).
4. **Burn kinetic lyrics** — `ass=<lyrics.ass>` last, on top.

**Prod-ffmpeg discipline (load-bearing — see memory):**
- Validate the real filtergraph in a **Debian ffmpeg 5.1.x container** (prod
  parity), not local 8.x.
- Use `asplit`/`split` to fan out any intermediate label consumed more than once
  (referencing a label twice silently truncates output).
- Guard against `zoompan`/`-loop` runaway (bound frame counts / durations).
- Write `final.mp4` to a local temp then move onto the gcsfuse mount; do
  `+faststart` off-Fuse.

### 5. Overlay-loop library + generators — `assets/overlays/`, `scripts/gen_overlays.py`

- `scripts/gen_overlays.py` renders a **starter loop set** offline (particles,
  bokeh, light-sweep, geometric shapes, grain) and writes them to
  `assets/overlays/<genre_key>/*.webm` (alpha, seamlessly loopable). Run once;
  the outputs are committed as assets and reused at $0/render.
- **Convention:** `build_animated_video` looks up `assets/overlays/<genre_key>/`;
  genres without a bespoke loop get **procedural-only** FX (graceful). Premium /
  sourced / AI loops can be dropped into the same folders later with no code
  change.

### 6. Wiring

- The **per-song `video_mode`** (stored in `song.json`, read as
  `script.get("video_mode", "static")` — not a `SongConfig` field) gains
  `"animated"` as an allowed value alongside `static`/`cinematic`, selected in
  the create flow. Update any allowed-values validation accordingly. Recommend
  making `animated` the **default for new songs** once validated (keep
  static/cinematic selectable).
- `run.py` / `pipeline/api.py`: when `video_mode == "animated"`, route song
  assembly to `song_animate.build_animated_video` (after align + beats). Same
  resumable-artifact pattern (skip if `final.mp4` exists).
- **Cost:** ~$0 extra (no AI); render time increases modestly. No budget-guard
  changes (that guard is for Kie/Veo spend, which this doesn't touch).

## Data flow

`song.mp3` + `lyrics(+section tags)` + `genre_key`
→ `align_song_lyrics` (word timing + confidence) + `detect_beats` (beat grid)
→ `visual_template_for(genre_key)`
→ `build_kinetic_ass` (karaoke verses / hook-word chorus / line-snap fallback)
→ `build_animated_video` (backdrop motion + procedural FX + overlay loops + burned ASS)
→ `final.mp4`.

## Error handling / fallbacks

- Per-line `align_confidence < min_confidence` or missing `words[]` → **line-snap**.
- No `assets/overlays/<genre_key>/` → **procedural FX only**.
- librosa beat failure → **fixed-BPM grid** (existing behavior).
- No `[Chorus]` present → treat all sung lines as verse karaoke (hook-word skipped).
- Missing font → libass default (log a warning).
- ffmpeg filtergraph error → fail the stage and surface the error; never emit a
  silently-broken video. Stage is resumable.
- All external tools (ffmpeg, librosa, align) are mocked in tests — never hit
  real services (repo invariant).

## Testing

- **Unit:** `visual_template_for` (every `GENRE_RECIPES` key resolves; unknown →
  `generic`); word-timing schema + `align_confidence` heuristic; ASS builder
  (karaoke `\k` count == word count; hook-word selection; line-snap triggers on
  low confidence and on missing words; RTL vs LTR); filtergraph construction
  (asplit present when a label is reused; beat-flash `enable` exprs generated
  from `beat_times`; overlay blend present iff loop dir exists).
- **Integration:** with ffmpeg/librosa/align mocked, assert `final.mp4` is
  produced and the stage is skipped on resume.
- **Prod parity:** validate the actual filtergraph once against a Debian ffmpeg
  5.1.x container before shipping.

## Risks & mitigations

- **Arabic word-alignment accuracy** (karaoke drift) → confidence gate +
  line-snap fallback; tune `min_confidence` on real songs.
- **ffmpeg filtergraph complexity / prod-version drift** → 5.1.x validation +
  strict `asplit` discipline + zoompan/-loop bounds + faststart-off-Fuse.
- **Offline-generated loop quality** → procedural fallback guarantees a good
  baseline; drop-in convention lets better loops replace generated ones later.
- **Render-time increase** → acceptable (no AI cost); can cap FX complexity per
  genre if a render gets too slow.
