"""Animated song-video compositor: one ffmpeg filtergraph layering a moving
backdrop + genre procedural FX (beat-synced) + overlay loops + burned kinetic
ASS. ~$0/render (no AI calls, ffmpeg-only). See
docs/superpowers/specs/2026-08-20-animated-genre-song-video-design.md
section 4 ("Genre FX compositor") for the architecture this implements.

Two entry points:
  - `build_filtergraph(...)` -- pure string builder, no I/O. Unit-tested
    directly for construction correctness (asplit/split discipline,
    beat-synced `enable` exprs, fontsdir).
  - `build_animated_video(...)` -- orchestrates ffmpeg: optionally pre-renders
    a beat-cut concat of multiple stills (the "cinematic" backdrop case),
    then runs the compositor filtergraph and writes `out_path`.

Prod-ffmpeg discipline (load-bearing -- see project memory
feedback_ffmpeg_prod_version_and_gcsfuse.md):
  - Validate the emitted `-filter_complex` on Debian ffmpeg 5.1.x (prod) --
    a separate controller gate, not exercised by these mocked-subprocess
    tests. Only filters confirmed present in 5.1.x are used here.
  - Any intermediate label consumed more than once MUST be `split` first
    (referencing a video label twice silently truncates ffmpeg's output).
  - `-loop 1` / `-stream_loop -1` inputs are always paired with `-shortest`
    on the output so an infinitely-looped input can never run away.
  - `+faststart` requires ffmpeg to seek backward on the output file to
    rewrite the moov atom. On a gcsfuse-mounted `out/` directory that seek
    fails outright, so every ffmpeg call in this module writes to a LOCAL
    temp dir; only a final `shutil.copyfile` (pure sequential write, safe
    on Fuse) + `Path.replace()` (same-filesystem atomic rename) touch the
    destination -- the same pattern `pipeline/song_cinematic.py` uses.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from pipeline.song_ass_util import _escape_ffmpeg_filter_path
from pipeline.song_overlays import overlay_clips_for
from pipeline.song_scenes import Segment, build_cut_schedule
from pipeline.song_visual_style import MotionProfile, VisualTemplate

_FONTS_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
# libass resolves the ASS header's Fontname ("Amiri", see song_kinetic_ass.py)
# as a font-FAMILY name via fontconfig. Amiri ships in assets/fonts, not
# system-installed, so the ass= filter must point fontsdir at it explicitly
# -- HANDOFF from Task 3's report, see docstring of build_filtergraph below.
_FONTS_DIR_ESCAPED = _escape_ffmpeg_filter_path(_FONTS_DIR)

_FLASH_DECAY = 0.12        # seconds the eased brightness pop decays over
_FLASH_SAT_K = 0.18        # saturation lift at the beat peak (scaled by the env)
_GLITCH_WINDOW = 0.05      # seconds the rgb-shift glitch holds per beat
_CAM_FPS = 30              # zoompan output rate (defines the `-loop 1` still's rate)
_ZOOM_CEILING = 1.30       # hard cap: a long song can never zoom past this
_OVERLAY_PULSE_SCALE = 0.30  # maps MotionProfile.overlay_pulse (0..1) to eq brightness

# Beat-cut still backdrop (multi-image / "cinematic" mode) render constants.
# Deliberately mirrors pipeline/song_cinematic.py's per-clip pipeline (bounded
# CFR Ken-Burns clip -> concat demuxer -c copy) rather than the single-giant-
# filtergraph-with-xfade approach that module's docstring records as having
# broken prod ffmpeg 5.1.x (looped-still zoompan -> undefined frame rate ->
# xfade rejects it). song_cinematic's own segment_vf/OUTPUT_SIZE are hardcoded
# to a square 1080x1080 canvas, so this module has its own w x h variant
# rather than reusing them directly.
_STILL_FPS = 25
_STILL_UPSCALE_FACTOR = 2  # pre-zoompan upscale to avoid resampling blur
_STILL_ZOOM_END = 1.13
_BACKDROP_ZOOM_CEILING = 1.60  # safe within the 2x upscale (base+KenBurns+punch)


@dataclass(frozen=True)
class Framing:
    """One virtual camera framing of a single cover image: which region to show
    (anchor, normalized 0..1) and how tight (base_zoom). The $0 way to get
    visual variety from ONE still -- the beat-cut backdrop rotates through a
    pool of these so the 'camera explores the frame' instead of freezing on one
    composition (a square cover gives ~horizontal pan room; anchor_y matters
    more for taller covers)."""
    anchor_x: float
    anchor_y: float
    base_zoom: float


def _framing_plan() -> list[Framing]:
    """A tasteful fixed pool of framings a beat-cut backdrop rotates through:
    wide establishing -> tight center -> left -> right -> medium. Real pan +
    zoom variety from one cover."""
    return [
        Framing(0.50, 0.50, 1.00),   # wide establishing, center
        Framing(0.50, 0.42, 1.18),   # tight center (pushes toward the subject)
        Framing(0.25, 0.50, 1.06),   # left region
        Framing(0.75, 0.50, 1.06),   # right region
        Framing(0.50, 0.50, 1.10),   # medium center
    ]


def _beat_grid(beats: dict) -> tuple[float, float] | None:
    """`(offset, period)` seconds for the beat grid, or None if there are no
    beats. `offset` is the first beat so pulses align to the downbeat; `period`
    comes from `tempo_bpm`, else the mean beat gap, else a 120-BPM assumption.
    Shared by every beat-synced expression builder below so they agree on the
    grid (and so a full song's hundreds of beats never enter the filtergraph
    string -- the OOM that once sank the animated render)."""
    bt = beats.get("beat_times") or []
    if not bt:
        return None
    bpm = beats.get("tempo_bpm") or 0
    if bpm and float(bpm) > 0:
        period = 60.0 / float(bpm)
    elif len(bt) >= 2:
        period = (float(bt[-1]) - float(bt[0])) / (len(bt) - 1)
    else:
        period = 0.5  # unknown tempo + single beat -> assume 120 BPM
    return float(bt[0]), period


def _beat_pulse_expr(beats: dict, window: float) -> str | None:
    """A COMPACT periodic enable expression that pulses once per beat on the
    tempo grid -- `lt(mod(t-offset,period),window)` -- instead of enumerating
    one `between(t,...)` term PER BEAT (the per-beat form OOM'd prod ffmpeg at
    parse). None when there are no beats (caller emits a `null` passthrough)."""
    grid = _beat_grid(beats)
    if grid is None:
        return None
    offset, period = grid
    # Plain commas inside enable='...' — same convention the between() form used.
    return f"lt(mod(t-{offset:.3f},{period:.4f}),{window:.3f})"


def _beat_env_expr(beats: dict, *, tvar: str = "t", decay: float,
                   t0: float = 0.0) -> str | None:
    """A COMPACT, CONTINUOUS beat envelope: a value that spikes to ~1 at each
    beat and decays exponentially over `decay` seconds. Expressed in terms of
    the time expression `tvar` -- "t" for eq-style filters, "(on/FPS)" for
    zoompan (which evaluates the output-frame index `on`, not `t`). This is the
    eased replacement for the rectangular `_beat_pulse_expr` gate: brightness/
    zoom driven by it SWELL and FALL (musical) instead of popping on then off
    (strobe). Like the pulse form it stays ONE periodic term regardless of beat
    count, so it never approaches the OOM regime. None when there are no beats.

    `t0` re-anchors the grid when `tvar` resets partway through the song -- a
    backdrop segment's `on` restarts at 0 at the clip start, so passing the
    clip's start time as `t0` keeps its punch locked to the GLOBAL beat grid.
    ffmpeg's mod() is floor-based (verified on 5.1.9 + 8.1), so a negative
    `offset - t0` is handled correctly; no normalization needed."""
    grid = _beat_grid(beats)
    if grid is None:
        return None
    offset, period = grid
    # Emit a clean +/- so a late clip (offset - t0 < 0) never produces a
    # double-minus like "(on/25)--3.5" in the expression.
    shift = offset - t0
    sign, mag = ("-", shift) if shift >= 0 else ("+", -shift)
    return f"exp(-mod({tvar}{sign}{mag:.4f},{period:.4f})/{decay:.4f})"


def _beat_flash(beats: dict, amp: float) -> str:
    """Brightness POP + saturation kick EASED on each beat: an exponential
    swell/decay (reads as a musical hit) instead of the old rectangular on/off
    `enable=` gate (reads as a strobe). `amp` is the per-genre
    MotionProfile.flash_amp. Continuous via eval=frame -- contributes ~0
    between beats, so no `enable` gate is needed. Compact: one envelope term
    regardless of beat count (see _beat_env_expr)."""
    env = _beat_env_expr(beats, tvar="t", decay=_FLASH_DECAY)
    if not env:
        return "null"
    return (f"eq=brightness='{amp:.3f}*({env})':"
            f"saturation='1+{_FLASH_SAT_K:.3f}*({env})':eval=frame")


def _rgb_glitch(beats: dict) -> str:
    """Channel-shift glitch pulsed on each beat (compact periodic enable)."""
    expr = _beat_pulse_expr(beats, _GLITCH_WINDOW)
    return f"rgbashift=rh=4:bh=-4:enable='{expr}'" if expr else "null"


def build_filtergraph(*, template: VisualTemplate, beats: dict,
                      has_overlay: bool, size: tuple[int, int],
                      overlay_count: int = 1,
                      backdrop_is_video: bool = False) -> str:
    """Pure: the `-filter_complex` string for one animated render. No I/O.

    Layered bottom -> top, per the design spec's architecture:
      1. backdrop normalized to `size` (input [0:v])
      2. procedural FX from `template.fx_set` (grade / beat-flash /
         rgb-glitch / grain / light-sweep / vignette / push-in)
      3. genre overlay loops blended on top, iff `has_overlay` (inputs [1:v]...)
      4. kinetic ASS burned last, on top -- via a `{ASS}` placeholder the
         caller substitutes with the escaped `ass_path` (this function has
         no `ass_path` param by design: the interface only asks for a bool
         + a beats dict + a template, and the burn-in font resolution
         (`fontsdir`) doesn't depend on the specific ass_path anyway).

    `grade_neon` needs the backdrop label TWICE (once graded, once blurred
    for a bloom/glow layer, then screen-blended back together) -- the one
    case in this graph where a label is legitimately reused, and so the
    one case requiring `split` first (ffmpeg silently truncates output if a
    video label is referenced by more than one downstream filter without
    an explicit split).
    """
    w, h = size
    fx = template.fx_set

    stmts: list[str] = []
    cur = "base"
    stmts.append(
        f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,"
        f"crop={w}:{h}[base]"
    )

    # Beat-synced camera: a slow continuous drift (push-in) with a zoom PUNCH
    # layered on each beat, both from the per-genre MotionProfile. zoompan is
    # not commandable, so this rides an EXPRESSION -- the proven push_in
    # mechanism -- now center-anchored and beat-reactive, bounded by min() so a
    # long song can never zoom past the ceiling; fps gives the `-loop 1` still a
    # defined output rate. (The legacy "push_in" token is now a no-op.)
    #
    # ONLY for a single-still backdrop. When the backdrop is a pre-rendered
    # framing/concat VIDEO, the per-clip punch already lives inside each segment
    # (see _backdrop_segment_vf) and zoompan d=1 on a looped CFR video is the
    # documented prod-5.1.x failure mode -- so the compositor adds no camera.
    if not backdrop_is_video:
        m = template.motion
        nxt = f"{cur}_cam"
        drift = f"1+{m.drift_rate:.6f}*on"
        punch = _beat_env_expr(beats, tvar=f"(on/{_CAM_FPS})", decay=m.punch_decay)
        z = (f"min({drift}+{m.punch_amp:.3f}*({punch}),{_ZOOM_CEILING:.2f})"
             if punch else f"min({drift},{_ZOOM_CEILING:.2f})")
        stmts.append(
            f"[{cur}]zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d=1:s={w}x{h}:fps={_CAM_FPS}[{nxt}]"
        )
        cur = nxt

    if "grade_neon" in fx:
        # Neon = a saturated base + a soft bloom screen-blended back. The bloom
        # is DAMPED (all_opacity=0.40) and saturation kept moderate so bright
        # frames get a neon glow instead of blowing out to garish magenta (a
        # full-strength screen blend of a sunset still was unusable -- see the
        # grade_neon_bloom regression test).
        a, b, nxt = f"{cur}_a", f"{cur}_b", f"{cur}_grade"
        stmts.append(f"[{cur}]split=2[{a}][{b}]")
        stmts.append(f"[{a}]eq=contrast=1.10:saturation=1.22[{a}g]")
        stmts.append(f"[{b}]gblur=sigma=16,eq=brightness=0.03:saturation=1.12[{b}g]")
        stmts.append(f"[{a}g][{b}g]blend=all_mode=screen:all_opacity=0.40[{nxt}]")
        cur = nxt
    elif "grade_warm" in fx:
        nxt = f"{cur}_grade"
        stmts.append(
            f"[{cur}]eq=saturation=1.18:contrast=1.08,"
            f"colorbalance=rs=0.08:bs=-0.08[{nxt}]"
        )
        cur = nxt
    elif "grade_cool" in fx:
        nxt = f"{cur}_grade"
        stmts.append(
            f"[{cur}]eq=saturation=1.15:contrast=1.10,"
            f"colorbalance=bs=0.10:rs=-0.06[{nxt}]"
        )
        cur = nxt
    elif "grade_pop" in fx:
        nxt = f"{cur}_grade"
        stmts.append(
            f"[{cur}]curves=preset=increase_contrast,eq=saturation=1.25[{nxt}]"
        )
        cur = nxt

    if "beat_flash" in fx:
        nxt = f"{cur}_flash"
        stmts.append(f"[{cur}]{_beat_flash(beats, template.motion.flash_amp)}[{nxt}]")
        cur = nxt

    if "rgb_glitch" in fx:
        nxt = f"{cur}_glitch"
        stmts.append(f"[{cur}]{_rgb_glitch(beats)}[{nxt}]")
        cur = nxt

    if "grain" in fx:
        nxt = f"{cur}_grain"
        stmts.append(f"[{cur}]noise=alls=16:allf=t[{nxt}]")
        cur = nxt

    if "light_sweep" in fx:
        nxt = f"{cur}_sweep"
        # A slow, subtle brightness oscillation reads as a light sweep
        # without a dedicated moving-gradient source; eval=frame makes the
        # eq filter re-evaluate the expression (with the `t` variable) every
        # frame instead of once at init.
        stmts.append(
            f"[{cur}]eq=brightness='0.07*sin(2*PI*t/3)':eval=frame[{nxt}]"
        )
        cur = nxt

    if "vignette" in fx:
        nxt = f"{cur}_vig"
        stmts.append(f"[{cur}]vignette=PI/4[{nxt}]")
        cur = nxt

    if has_overlay:
        # Blend every available genre loop (e.g. Trap particles + geometry),
        # rather than silently discarding all but the first sorted asset.
        # Inputs are decoded from alpha VP9 by the caller and remain bounded
        # by the song audio via -shortest.
        #
        # P2c -- REACTIVE overlays: each loop's brightness breathes with the
        # beat (eq pulse, eval=frame) so the particles/shapes pop on each hit
        # instead of sitting at flat opacity. eq keeps the alpha channel, so the
        # overlay stays semi-transparent (no regression to the opaque-overlay
        # bug). Amplitude is MotionProfile.overlay_pulse, scaled to a tasteful
        # brightness range.
        pulse = _beat_env_expr(beats, tvar="t", decay=_FLASH_DECAY)
        pulse_amp = template.motion.overlay_pulse * _OVERLAY_PULSE_SCALE
        for i in range(max(1, overlay_count)):
            ov, nxt = f"ov{i}", f"bg_ov{i}"
            ov_chain = (
                f"[{i + 1}:v]scale={w}:{h}:force_original_aspect_ratio=increase,"
                f"crop={w}:{h},format=yuva420p"
            )
            if pulse and pulse_amp > 0:
                ov_chain += f",eq=brightness='{pulse_amp:.3f}*({pulse})':eval=frame"
            stmts.append(f"{ov_chain}[{ov}]")
            stmts.append(f"[{cur}][{ov}]overlay=shortest=0[{nxt}]")
            cur = nxt

    stmts.append(f"[{cur}]ass={{ASS}}:fontsdir='{_FONTS_DIR_ESCAPED}'[v]")

    return ";".join(stmts)


def _run(cmd: list[str]) -> None:
    """Run one ffmpeg call, surfacing stderr in the exception. The only
    subprocess surface `build_animated_video` uses -- no ffprobe call is
    made anywhere in this module (unlike song_cinematic's assert_playable);
    keeping the surface to ffmpeg-only calls is what makes it mockable with
    a single `monkeypatch.setattr(sa.subprocess, "run", fake_run)`."""
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        stderr = r.stderr
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", "replace")
        raise RuntimeError(f"song_animate ffmpeg failed: {(stderr or '')[-800:]!r}")


def _backdrop_segment_vf(seg: Segment, framing: Framing, frames: int,
                         w: int, h: int, beats: dict,
                         motion: MotionProfile) -> str:
    """Pure: the -vf chain turning one still into a bounded, constant-frame-rate
    clip at w x h for ONE beat-cut segment. Combines three motions:

      1. FRAMING -- crop to the segment's `framing` (pan to its anchor region +
         base_zoom), so consecutive segments show different compositions of the
         same cover.
      2. Ken-Burns drift -- a slow zoom in/out over the clip (seg.zoom_dir).
      3. BEAT PUNCH -- the per-genre zoom pop on each beat, re-anchored to the
         GLOBAL beat grid via t0=seg.start (the segment's `on` resets to 0, so
         without t0 every clip would punch from its own start, off the music).

    This is where the beat punch lives for the framing/concat backdrop -- NOT
    in the compositor, because zoompan d=1 on the looped CFR concat video is the
    documented prod-5.1.x failure mode (see build_filtergraph). Here each clip
    is a bounded `-loop 1 -t dur` still, exactly what zoompan is proven on.
    """
    delta = _STILL_ZOOM_END - 1.0
    base = framing.base_zoom
    if seg.zoom_dir == "in":
        kb = f"{base:.4f}+{delta:.4f}*on/{frames}"
    else:
        kb = f"{base + delta:.4f}-{delta:.4f}*on/{frames}"
    env = _beat_env_expr(beats, tvar=f"(on/{_STILL_FPS})",
                         decay=motion.punch_decay, t0=seg.start)
    z = (f"min({kb}+{motion.punch_amp:.3f}*({env}),{_BACKDROP_ZOOM_CEILING:.2f})"
         if env else f"min({kb},{_BACKDROP_ZOOM_CEILING:.2f})")
    uw, uh = w * _STILL_UPSCALE_FACTOR, h * _STILL_UPSCALE_FACTOR
    return (
        f"scale={uw}:{uh}:force_original_aspect_ratio=increase,"
        # Pan the crop window to the framing's anchor (clamped by the available
        # over-scan: (iw-ow)*anchor_x). A square cover has horizontal room; the
        # vertical term is 0 and harmless.
        f"crop={uw}:{uh}:x='(iw-{uw})*{framing.anchor_x:.3f}':"
        f"y='(ih-{uh})*{framing.anchor_y:.3f}',"
        f"zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        f"d={frames}:s={w}x{h}:fps={_STILL_FPS},"
        f"setsar=1,format=yuv420p"
    )


def _render_still_backdrop(
    stills: list[Path], beats: dict, size: tuple[int, int],
    motion: MotionProfile, work: Path,
    framings: list[Framing] | None = None,
) -> Path:
    """Beat-cut concat of N stills into ONE bounded, constant-frame-rate
    backdrop clip. Two modes:
      - MULTI-STILL (`framings=None`): rotate a pool of distinct images by
        beat-cut index (the original "cinematic" case).
      - SINGLE-COVER FRAMING (`framings=<plan>`): one image, rotate a pool of
        virtual FRAMINGS (crop + zoom) so the camera "explores the frame" --
        the $0 way to get variety from one cover.
    Both rotate the per-genre beat PUNCH into each segment (via
    `_backdrop_segment_vf`, re-anchored to the global grid).

    Reuses `song_scenes.build_cut_schedule`, the same beat-cut brain
    `song_cinematic` uses. Cuts are hard (concat demuxer); seam transitions
    are a separate pass. `beats` carries no `audio_duration`, so the schedule
    is built over a synthetic duration from the beat grid and the caller wraps
    the result in `-stream_loop -1` so any undershoot is covered by looping.
    """
    w, h = size
    beat_times = list(beats.get("beat_times", []))
    synthetic_duration = (beat_times[-1] + 2.0) if beat_times else 8.0
    # Pool size drives the cut CADENCE: with framings, cut often enough to
    # rotate through the whole framing pool; otherwise one per still.
    pool_size = len(framings) if framings else len(stills)
    schedule = build_cut_schedule(
        beat_times=beat_times, sections=[], pool_size=max(1, pool_size),
        audio_duration=synthetic_duration,
    )
    clips: list[Path] = []
    for i, seg in enumerate(schedule):
        frames = max(1, round((seg.end - seg.start) * _STILL_FPS))
        dur = frames / _STILL_FPS
        clip = work / f"bg_seg_{i:04d}.mp4"
        # NOT seg.image_idx: build_cut_schedule runs with sections=[], so every
        # seg.image_idx is 0. Round-robin by loop index so the still pool (or
        # the framing pool) actually rotates across the beat-cut schedule.
        image = stills[i % len(stills)]
        framing = framings[i % len(framings)] if framings else Framing(0.5, 0.5, 1.0)
        _run([
            "ffmpeg", "-y", "-loop", "1", "-i", str(image),
            "-vf", _backdrop_segment_vf(seg, framing, frames, w, h, beats, motion),
            "-t", f"{dur:.3f}", "-r", str(_STILL_FPS),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-f", "mp4", str(clip),
        ])
        clips.append(clip)

    list_file = work / "bg_concat.txt"
    list_file.write_text(
        "".join(f"file '{c.as_posix()}'\n" for c in clips), encoding="utf-8"
    )
    concatenated = work / "bg_video.mp4"
    _run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
        "-c", "copy", "-f", "mp4", str(concatenated),
    ])
    return concatenated


def build_animated_video(
    *,
    backdrop: Path | list[Path],
    song_mp3: Path,
    ass_path: Path,
    beats: dict,
    template: VisualTemplate,
    out_path: Path,
    size: tuple[int, int] = (1080, 1920),
    framing: bool = True,
) -> Path:
    """Render the genre-adaptive animated song video to `out_path`.

    `framing` (default on): for a SINGLE cover, synthesize a beat-cut backdrop
    of multiple virtual FRAMINGS of that one image (the camera explores the
    frame) instead of freezing on one static composition -- all $0. Pass
    `framing=False` to fall back to the single looped still + in-compositor
    beat camera.

    Resumable: if `out_path` already exists, returns it without touching
    ffmpeg (same pattern as every other pipeline stage).
    """
    if out_path.exists():
        return out_path

    clips = overlay_clips_for(template.genre_key)
    has_overlay = bool(clips)

    if isinstance(backdrop, Path):
        stills: list[Path] = []
        cover = backdrop
    else:
        stills = list(backdrop)
        if not stills:
            # Silently falling through to `cover = None` would reach the
            # ffmpeg invocation as a literal "-i None" -- fail fast at the
            # API boundary instead (2026-08-20 review finding, Minor).
            raise ValueError("backdrop list must not be empty")
        cover = stills[0]

    multi_still = len(stills) > 1
    # Single cover + framing -> synthesize framing variety ($0). Either way a
    # concat VIDEO backdrop already carries all the motion (Ken-Burns + per-clip
    # beat punch), so the compositor must NOT add a zoompan camera on top.
    use_framing = framing and not multi_still
    backdrop_is_video = multi_still or use_framing

    fg = build_filtergraph(
        template=template, beats=beats, has_overlay=has_overlay, size=size,
        overlay_count=len(clips), backdrop_is_video=backdrop_is_video,
    ).replace("{ASS}", _escape_ffmpeg_filter_path(ass_path))

    work = Path(tempfile.mkdtemp(prefix="song-animate-"))
    try:
        if multi_still:
            bg_video = _render_still_backdrop(
                stills, beats, size, template.motion, work)
            input0 = ["-stream_loop", "-1", "-i", str(bg_video)]
        elif use_framing:
            bg_video = _render_still_backdrop(
                [cover], beats, size, template.motion, work,
                framings=_framing_plan())
            input0 = ["-stream_loop", "-1", "-i", str(bg_video)]
        else:
            input0 = ["-loop", "1", "-i", str(cover)]

        cmd = ["ffmpeg", "-y", *input0]
        if has_overlay:
            # CRITICAL (Task 4 handoff): -c:v libvpx-vp9 MUST be an INPUT
            # option immediately before -i <overlay>. ffmpeg's default vp9
            # decoder silently drops WebM alpha -- without this the overlay
            # composites as an OPAQUE rectangle (ffprobe shows yuv420p
            # either way; only a real render reveals the bug).
            for clip in clips:
                cmd += ["-stream_loop", "-1", "-c:v", "libvpx-vp9", "-i", str(clip)]
        cmd += ["-i", str(song_mp3)]

        audio_idx = 1 + len(clips)
        local_out = work / "final.mp4"
        cmd += [
            "-filter_complex", fg,
            "-map", "[v]", "-map", f"{audio_idx}:a",
            # CRF 23 + a hard bitrate ceiling so the file size stays sane
            # (~8 Mbps -> ~150 MB for a 2.5-min 9:16 clip). Without -maxrate a
            # busy/noisy frame could balloon to multi-GB (a temporal-grain
            # filter once produced a 3 GB output). Explicit -r 30 gives the
            # looped-still input a defined output rate.
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-maxrate", "8M", "-bufsize", "16M", "-r", "30",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            # -shortest is what actually bounds the -loop 1 / -stream_loop -1
            # inputs above -- output stops at the audio's (finite) length.
            "-shortest",
            # +faststart rewrites the moov atom by seeking backward on the
            # output -- must happen HERE, on local_out (real local disk),
            # never directly on a gcsfuse-mounted destination.
            "-movflags", "+faststart",
            "-f", "mp4", str(local_out),
        ]
        _run(cmd)

        out_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_dest = Path(str(out_path) + ".tmp")
        if tmp_dest.exists():
            try:
                tmp_dest.unlink()
            except OSError:
                pass
        # Sequential copy (safe on gcsfuse) onto the SAME filesystem as
        # out_path, then an atomic same-filesystem rename -- never an
        # os.rename() straight from the local temp dir, which would raise
        # EXDEV crossing from local disk onto a fuse mount.
        shutil.copyfile(local_out, tmp_dest)
        tmp_dest.replace(out_path)
    finally:
        shutil.rmtree(work, ignore_errors=True)

    return out_path
