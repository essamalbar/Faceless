# Animated Song-Video Motion & Animation Overhaul — Design

> **Status:** P1 + P2 + P3 shipped (branch `feat/animated-motion-overhaul`)
> **Date:** 2026-11-06
> **Scope owner:** song animated ($0) path
> **Supersedes nothing** — extends `docs/superpowers/specs/2026-08-20-animated-genre-song-video-design.md`.

> **Implementation status (2026-11-06):**
> - **P1 shipped** — §5.0 eased envelope, §5.1 MotionProfile, §5.2 beat camera,
>   §5.4 eased flash; plus acceptance fixes (overlay opacity, tamed neon grade).
>   Verified on prod ffmpeg 5.1.9.
> - **P2 shipped** — §5.3 multi-framing backdrop (framing on by default, no
>   run.py change), §5.5 reactive overlays (per-overlay eq pulse; alpha
>   preserved, verified on 5.1.9), §5.6 dip/glitch seam transitions (in-clip,
>   no xfade). The §5.0 **piecewise drift-fix is SUPERSEDED**: the main path is
>   now the framing/concat backdrop whose per-clip punch is re-anchored to the
>   global grid via `t0=seg.start`, so drift is bounded per short clip; the
>   single-still fallback (`framing=False`) keeps the one-period envelope.
> - **P3 shipped** — §5.7 hero kinetic lyrics: hero font size (84→134), heavy
>   outline (3→6), per-line fade/scale entrances, bigger hook pulse, and the
>   `\r`-cancels-entrance fix. Verified on prod 5.1.9. The **stray glyph-box is
>   NOT in the animated path** — Amiri renders Arabic punctuation cleanly; the
>   `□` is in the CINEMATIC caption path (`captions.ar.ass` uses Cairo-Black,
>   not bundled → libass tofu). Fixing that is a separate caption-path task
>   (bundle the font or switch to a bundled one), out of this spec's scope.

## 1. Goal

Make the **animated song-video path** (`pipeline/song_animate.py` + its
collaborators) produce output that reads as a genuinely high-end, music-video-
grade result — not a static cover with a flash on it. The motion must feel
**locked to the music**, the **character of the motion must change by genre**,
and the **kinetic lyrics must read as the star**. Everything stays
**$0/render, ffmpeg-only, no AI calls**, inside the existing prod-ffmpeg-5.1.x
/ OOM / file-size / gcsfuse discipline.

## 2. Scope

**In scope** — the `video_mode == "animated"` path end-to-end:
- `pipeline/song_animate.py` (compositor filtergraph + orchestration)
- `pipeline/song_visual_style.py` (per-genre templates + a new motion profile)
- `pipeline/song_overlays.py` (overlay opacity reactivity — build-time only)
- `pipeline/song_kinetic_ass.py` (kinetic lyric typography)
- `run.py` animated branch wiring (`~1535–1568`)

**Out of scope (explicit):**
- **The Veo/Kling cinematic tier** — real AI video. Left untouched per owner
  decision. No change to `song_cinematic.py`.
- **Generating additional backdrop images.** `song_cover.generate_scene_images`
  calls Kie's Flux API (**paid, per image**). The animated path has exactly one
  image — `final_cover_path` — and this design keeps it that way. Backdrop
  *variety* is synthesized from that single cover at $0 (§5.3), never by
  generating new stills.
- The static and cover-upload modes.

## 3. Current state & why it caps quality

Today, in production (`run.py:1553`), the animated path renders over a **single
static cover** (`backdrop=final_cover_path`, one `Path`). The multi-still beat-
cut backdrop that `build_animated_video` already supports is never fed. On top
of that one frozen image it applies: a slow monotonic `push_in` zoom, a per-
genre grade, a **rectangular** on/off `beat_flash`, optional `rgb_glitch`, a
`light_sweep` brightness sine, a vignette, constant-opacity overlay loops, and
the kinetic ASS burn.

Concrete quality gaps (impact order):

1. **No beat-synced motion.** `push_in` ignores the beat. The signature music-
   video move — a frame "punch" on each kick that eases back — is absent.
2. **One frozen backdrop.** A single image for the whole song; the frame never
   re-frames or changes.
3. **Rectangular beat response.** `_beat_pulse_expr` gates effects fully on then
   fully off (`lt(mod(t,period),window)`) — reads as a strobe, not a musical hit.
4. **Beat grid drifts.** The pulse uses one constant `period = 60/bpm` and only
   `beat_times[0]`; the real `beat_times` are discarded, so on any tempo drift
   the pulse slides off the beat after ~20–30 s.
5. **Flat overlays.** Loops play at constant opacity; they don't breathe with
   the track.
6. **Motion is genre-uniform.** A ballad and a trap track get structurally
   identical motion — only the grade color differs.
7. **Transitions ignored.** `VisualTemplate.transition` (`dip`/`glitch`) is
   declared per genre but everything hard-cuts.
8. **Kinetic lyrics are underpowered**, and a real **stray glyph-box (`□`)**
   was observed in a rendered caption (§5.7).

## 4. Verified feasibility (de-risking the core)

The riskiest new primitive — a beat-synced eased **zoom-punch** — was rendered
locally and confirmed (frames `scratchpad/frames/punch_compare.jpg`): an
expression-driven `zoompan` with an `on`-based eased pulse produces a clean,
center-anchored punch with no artifacts.

- Mechanism: `zoompan=z='1 + A*exp(-mod(on - on0, P)/τ)'` with center
  `x='iw/2-(iw/zoom/2)'`, `y='ih/2-(ih/zoom/2)'`, `d=1`, `fps=30`.
  This is the **same filter already shipping in prod** (`push_in` uses
  `zoompan` with an `on`-based expression), so it is within proven territory.
- `sendcmd`/commands-file was investigated and **rejected**: `zoompan` is **not
  commandable** (verified `ffmpeg -h filter=zoompan`), so motion must be
  expression-driven regardless. This also keeps the beat list out of the graph.
- **OOM safety preserved:** all beat-sync stays a *compact periodic expression*
  (a handful of terms), never per-beat enumeration — the thing that OOM'd prod.

## 5. Design

### 5.0 Shared primitive: the eased beat envelope

Add one pure helper that returns a **continuous** 0→1 pulse expression, easing
in and decaying after each beat, in terms of a caller-chosen time variable
(`t` for `eq`-style filters, `on`/`fps` for `zoompan`):

```
env(var, period, attack, decay) =
  clamp over phase = mod(var - offset, period):
    rising  edge  (phase < attack):      phase/attack
    falling edge  (phase >= attack):     exp(-(phase-attack)/decay)
```

- Replaces the rectangular `lt(mod(...),window)` gate everywhere.
- **Drift mitigation without OOM (§3.4 fix):** instead of one global `period`,
  split the song into a small number of **constant-tempo spans** derived from
  `beat_times` (e.g. re-anchor every section boundary, or every 8 bars) and emit
  a *piecewise* expression — a few nested `if(lt(var,b_k),…)` terms, each with
  its own `period_k`/`offset_k`. Still compact; drift is bounded per span
  instead of accumulating across the whole song. Span count is capped
  (e.g. ≤ 8) so the expression never approaches the OOM regime.
- Lives in `song_animate.py` (pure, unit-tested on string shape + phase math).

### 5.1 `MotionProfile` — per-genre motion character (`song_visual_style.py`)

New frozen dataclass carried on `VisualTemplate`:

```python
@dataclass(frozen=True)
class MotionProfile:
    punch_amp: float      # beat zoom amplitude, e.g. 0.015 (ballad) … 0.06 (trap)
    punch_decay: float    # seconds the punch eases over
    drift_rate: float     # slow continuous pan/zoom speed (parallax feel)
    flash_amp: float      # eased brightness-pop amplitude
    overlay_pulse: float  # how much overlay opacity breathes with the beat (0..1)
    cut_bars: int         # bars per backdrop re-frame (§5.3)
    transition: str       # "hardcut" | "dip" | "glitch" (moves here from template)
```

Each of the 13 templates gets a profile tuned to its genre: ballad/tarab/
cinematic → low amp, slow drift, long decay, dip transitions; trap/EDM/rock →
high amp, fast decay, glitch transitions; pop/khaleeji → mid. `generic` gets a
sensible mid default. This is the unit that makes motion differ by genre, not
just color.

### 5.2 Beat-synced camera (`build_filtergraph`)

Replace the monotonic `push_in` with a **composite camera**:
- a slow continuous drift (gentle pan + micro-zoom) at `drift_rate` for life, +
- a beat **punch** = `1 + punch_amp * env(on-grid)` layered on the drift zoom,
  all in one `zoompan` z-expression (center-anchored).
- Bounded by `min(...)` so a long song can never zoom past a hard ceiling
  (keeps the existing runaway guard).

### 5.3 Backdrop variety from one cover — $0 (`song_animate.py`)

Since new stills cost money (§2), synthesize variety from `final_cover_path`:
re-frame the **same** image on section/bar boundaries (per `cut_bars`) — wide
establishing framing, tighter framings on different regions (upper/face/detail
crops), alternating drift directions — joined by §5.6 transitions. This reuses
the existing `_render_still_backdrop` beat-cut scaffolding but drives it from
**one** image with N *virtual framings* (crop rectangles + Ken-Burns direction)
instead of N distinct files. Reads as "the camera explores the frame," the
standard single-image lyric-video technique. `run.py` keeps passing one cover;
the framing pool is generated internally.

### 5.4 Eased beat-flash (replaces rectangular)

`_beat_flash` switches from `enable='lt(mod(...),window)'` to a continuous
`eq=brightness='flash_amp*env(t)':eval=frame` (+ a small saturation lift
scaled the same way). Swells and falls on the beat; no strobe.

### 5.5 Beat-reactive overlay opacity

Overlay opacity breathes with the beat. Two candidate mechanics, decided at
implementation after a prod-5.1.x check (both compact, no OOM):
- (a) drive the overlay `format=yuva420p,colorchannelmixer=aa='base+overlay_pulse*env(t)':eval=frame`, or
- (b) a `blend`/`overlay` alpha expression.
Baseline opacity stays near today's so quiet passages don't go flat.

### 5.6 Transitions between framings (`dip` / `glitch`)

Honor `MotionProfile.transition` at backdrop re-frames (§5.3). Because `xfade`
on looped/zoompanned stills is what broke prod 5.1.x (documented in
`song_cinematic`), transitions are implemented **inside each bounded per-framing
clip** (fade from/to black at the seam for `dip`; a 1–2 frame rgbashift +
brightness kick at the seam for `glitch`) rather than via a cross-clip `xfade`.
Hard-cut remains the fallback and the default where a profile says so.

### 5.7 Kinetic lyrics upgrade (`song_kinetic_ass.py`)

- **Fix the stray `□` glyph-box** observed before a caption. Reproduce in the
  *animated* (kinetic ASS) path first, then fix at the source — likely a bidi/
  leading-punctuation or an un-shaped character reaching libass; confirm the
  Amiri `fontsdir` resolves and the offending codepoint is handled (strip/normalize
  rather than render tofu).
- **Richer entrances/emphasis:** per-line fade+scale entrance, stronger hook-
  word pulse on chorus, karaoke fill timing unchanged (the `\k` gap-absorption
  logic is correct and stays). Positioning/margins reviewed for the 1080×1920
  frame so lyrics read as the hero element, clear of OS chrome.
- Keep the confidence-first fallback ladder intact.

### 5.8 `run.py` wiring

Minimal: pass the chosen `MotionProfile` through (via the template) to
`build_animated_video`. No new paid stages, no new inputs. The animated branch
stays a single `build_animated_video(...)` call with the same signature shape.

## 6. Interfaces & data flow

```
run.py (animated branch)
  └─ visual_template_for(genre)  → VisualTemplate{ …, motion: MotionProfile }
  └─ build_kinetic_ass(...)      → lyrics.ass           (§5.7)
  └─ build_animated_video(backdrop=cover, beats, template, …)
        ├─ _framing_plan(cover, beats, motion)          (§5.3)  [new, pure]
        ├─ _render_framing_backdrop(...)                (§5.3/5.6) [ffmpeg]
        └─ build_filtergraph(template, beats, …)        [pure]
              ├─ env(...) eased pulse                   (§5.0)  [new, pure]
              ├─ beat-synced zoompan camera             (§5.2)
              ├─ eased beat-flash / grade / glitch      (§5.4)
              ├─ beat-reactive overlays                 (§5.5)
              └─ ass burn                               (last layer)
```

Pure, independently unit-testable units: `env()`, the piecewise span builder,
`_framing_plan()`, and `build_filtergraph()` (string shape). ffmpeg-touching
units stay mockable behind the single `subprocess.run` surface.

## 7. Prod constraints preserved (non-negotiable)

- **OOM:** every beat-synced value is a compact periodic/piecewise expression;
  span count capped; **no per-beat enumeration**, ever.
- **ffmpeg 5.1.x:** only filters confirmed present in 5.1.x; new work rides on
  `zoompan`/`eq`/`overlay`/`colorchannelmixer`/`rgbashift` already used here.
  Final graph validated on the Debian 5.1.x container gate (§8), not local 8.1.
- **File size:** keep `-crf 23 -maxrate 8M -bufsize 16M`; no grain reintroduced;
  verify a full-song render stays ≈ 9 MB (regression check vs the old 3 GB bug).
- **gcsfuse/faststart:** unchanged — render to local temp, `copyfile` + atomic
  `replace()` to the destination.
- **Resumability & graceful fallback:** `out_path` short-circuit preserved; any
  ffmpeg failure still falls back to the static cover video (`run.py`).

## 8. Verification

1. **Unit tests** (mocked subprocess): `env()` phase/shape, piecewise span
   builder (drift bound, cap), `_framing_plan` determinism, `build_filtergraph`
   construction (split discipline, enable→continuous exprs, overlay count,
   fontsdir). Target: existing 1127-test suite stays green + new cases.
2. **Prod-ffmpeg 5.1.x gate:** emit the real `-filter_complex` and validate it
   renders on the Debian 5.1.x container (the standing controller gate) before
   calling it done — local 8.1 success is necessary, not sufficient.
3. **Visual spot-check:** render one song per motion archetype (ballad / pop /
   trap), extract on-beat vs off-beat frames, confirm punch + flash + overlay
   pulse land on beats and the file size holds.

## 9. Risks & mitigations

- **Single-cover variety has a ceiling.** Re-framing one image is not the same
  as distinct scenes; it is the honest $0 maximum. Mitigated by combining it
  with motion + overlays + transitions + hero lyrics. (True scene variety needs
  paid Flux — out of scope by decision.)
- **Piecewise expression vs OOM.** Mitigated by the hard span cap and reusing
  the proven compact-expression form.
- **Transition-at-seam on 5.1.x.** Mitigated by doing transitions *inside*
  bounded per-framing clips (no cross-clip `xfade`), per the documented 5.1.x
  failure mode.
- **Glyph-box fix** may be bidi-shaping, not font — treat as investigate-then-
  fix, reproduced in the animated path first.

## 10. Phasing (for the implementation plan)

- **P1 — motion core (biggest wow):** §5.0 env + §5.2 beat camera + §5.4 eased
  flash + §5.1 MotionProfile. Ships the beat-locked, genre-differentiated feel.
- **P2 — depth:** §5.5 reactive overlays + §5.3 multi-framing backdrop + §5.6
  transitions.
- **P3 — hero lyrics:** §5.7 kinetic typography + glyph-box fix.

Each phase is independently shippable and leaves the pipeline green and $0.
```
