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
from pathlib import Path

from pipeline.song_ass_util import _escape_ffmpeg_filter_path
from pipeline.song_overlays import overlay_clips_for
from pipeline.song_scenes import Segment, build_cut_schedule
from pipeline.song_visual_style import VisualTemplate

_FONTS_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
# libass resolves the ASS header's Fontname ("Amiri", see song_kinetic_ass.py)
# as a font-FAMILY name via fontconfig. Amiri ships in assets/fonts, not
# system-installed, so the ass= filter must point fontsdir at it explicitly
# -- HANDOFF from Task 3's report, see docstring of build_filtergraph below.
_FONTS_DIR_ESCAPED = _escape_ffmpeg_filter_path(_FONTS_DIR)

_BEAT_FLASH_WINDOW = 0.08  # seconds the brightness pop holds per beat
_GLITCH_WINDOW = 0.05      # seconds the rgb-shift glitch holds per beat

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


def _beat_pulse_expr(beats: dict, window: float) -> str | None:
    """A COMPACT periodic enable expression that pulses once per beat on the
    tempo grid -- `lt(mod(t-offset,period),window)` -- instead of enumerating
    one `between(t,...)` term PER BEAT.

    A full song has hundreds of beats; enumerating them all built a
    -filter_complex string so large that prod ffmpeg failed at PARSE with
    "Cannot allocate memory", and the animated render silently fell back to a
    static cover. `period` comes from tempo_bpm (or the mean beat gap); `offset`
    is the first beat so the pulse aligns to the downbeat. None when there are
    no beats (caller emits a `null` passthrough)."""
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
    offset = float(bt[0])
    # Plain commas inside enable='...' — same convention the between() form used.
    return f"lt(mod(t-{offset:.3f},{period:.4f}),{window:.3f})"


def _beat_flash(beats: dict) -> str:
    """Brightness POP + saturation kick on each beat -- short window so it reads
    as a hit, not a fade. Compact periodic enable (see _beat_pulse_expr)."""
    expr = _beat_pulse_expr(beats, _BEAT_FLASH_WINDOW)
    return (f"eq=brightness=0.14:saturation=1.12:enable='{expr}'"
            if expr else "null")


def _rgb_glitch(beats: dict) -> str:
    """Channel-shift glitch pulsed on each beat (compact periodic enable)."""
    expr = _beat_pulse_expr(beats, _GLITCH_WINDOW)
    return f"rgbashift=rh=4:bh=-4:enable='{expr}'" if expr else "null"


def build_filtergraph(*, template: VisualTemplate, beats: dict,
                      has_overlay: bool, size: tuple[int, int]) -> str:
    """Pure: the `-filter_complex` string for one animated render. No I/O.

    Layered bottom -> top, per the design spec's architecture:
      1. backdrop normalized to `size` (input [0:v])
      2. procedural FX from `template.fx_set` (grade / beat-flash /
         rgb-glitch / grain / light-sweep / vignette / push-in)
      3. overlay loop blended on top, iff `has_overlay` (input [1:v])
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

    if "push_in" in fx:
        nxt = f"{cur}_zoom"
        # z=... bounded by min(...) so a long song can't zoom past 1.25x;
        # fps=30 gives the zoompan filter (fed by an otherwise-undefined-
        # rate `-loop 1` still) a defined output rate.
        stmts.append(
            f"[{cur}]zoompan=z='min(1.0+0.0009*on,1.30)':d=1:"
            f"s={w}x{h}:fps=30[{nxt}]"
        )
        cur = nxt

    if "grade_neon" in fx:
        a, b, nxt = f"{cur}_a", f"{cur}_b", f"{cur}_grade"
        stmts.append(f"[{cur}]split=2[{a}][{b}]")
        stmts.append(f"[{a}]eq=contrast=1.18:saturation=1.4[{a}g]")
        stmts.append(f"[{b}]gblur=sigma=14,eq=brightness=0.08:saturation=1.5[{b}g]")
        stmts.append(f"[{a}g][{b}g]blend=all_mode=screen[{nxt}]")
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
        stmts.append(f"[{cur}]{_beat_flash(beats)}[{nxt}]")
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
        stmts.append(
            f"[1:v]scale={w}:{h}:force_original_aspect_ratio=increase,"
            f"crop={w}:{h},format=yuva420p[ov]"
        )
        stmts.append(f"[{cur}][ov]overlay=shortest=0[bg_ov]")
        cur = "bg_ov"

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


def _backdrop_segment_vf(seg: Segment, frames: int, w: int, h: int) -> str:
    """Pure: the -vf chain turning one still into a bounded, constant-frame-
    rate Ken-Burns clip at w x h. (song_cinematic.segment_vf is hardcoded to
    a square 1080x1080 canvas -- this is the vertical w x h variant.)"""
    if seg.zoom_dir == "in":
        z = f"1+{(_STILL_ZOOM_END - 1.0):.6f}*on/{frames}"
    else:
        z = f"{_STILL_ZOOM_END:.6f}-{(_STILL_ZOOM_END - 1.0):.6f}*on/{frames}"
    uw, uh = w * _STILL_UPSCALE_FACTOR, h * _STILL_UPSCALE_FACTOR
    return (
        f"scale={uw}:{uh}:force_original_aspect_ratio=increase,crop={uw}:{uh},"
        f"zoompan=z='{z}':d={frames}:s={w}x{h}:fps={_STILL_FPS},"
        f"setsar=1,format=yuv420p"
    )


def _render_still_backdrop(
    stills: list[Path], beats: dict, size: tuple[int, int], work: Path
) -> Path:
    """Beat-cut concat of N stills into ONE bounded, constant-frame-rate
    backdrop clip -- the multi-still ("cinematic") backdrop case. Reuses
    `song_scenes.build_cut_schedule`, the same beat-cut brain
    `song_cinematic` uses, rather than reinventing cut timing.

    All genres render as hard cuts via the concat demuxer in v1 regardless
    of `template.transition` -- xfade on a looped/zoompanned still is
    exactly what broke prod ffmpeg 5.1.x per song_cinematic's module
    docstring, so dip/glitch transitions are deferred (see task-5-report.md).

    `beats` carries no `audio_duration`, and probing one via ffprobe would
    add a second subprocess surface this module deliberately avoids (see
    `_run`'s docstring) -- so the schedule is built over a synthetic
    duration derived from the beat grid, and the caller wraps the result in
    `-stream_loop -1` so any undershoot of the real song length is covered
    by looping rather than freezing on the last frame.
    """
    w, h = size
    beat_times = list(beats.get("beat_times", []))
    synthetic_duration = (beat_times[-1] + 2.0) if beat_times else 8.0
    schedule = build_cut_schedule(
        beat_times=beat_times, sections=[], pool_size=len(stills),
        audio_duration=synthetic_duration,
    )
    clips: list[Path] = []
    for i, seg in enumerate(schedule):
        frames = max(1, round((seg.end - seg.start) * _STILL_FPS))
        dur = frames / _STILL_FPS
        clip = work / f"bg_seg_{i:04d}.mp4"
        # NOT stills[seg.image_idx]: build_cut_schedule is called with
        # sections=[] (this interface has no section-timing input), so
        # song_scenes._image_for_time always returns imgs[0] and every
        # seg.image_idx is 0 -- using it here would pin every segment to
        # stills[0], leaving stills[1:] dead weight (2026-08-20 review
        # finding). Round-robin over the beat-cut schedule by loop index
        # instead so the pool actually rotates.
        _run([
            "ffmpeg", "-y", "-loop", "1", "-i", str(stills[i % len(stills)]),
            "-vf", _backdrop_segment_vf(seg, frames, w, h),
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
) -> Path:
    """Render the genre-adaptive animated song video to `out_path`.

    Resumable: if `out_path` already exists, returns it without touching
    ffmpeg (same pattern as every other pipeline stage -- see CLAUDE.md's
    "All artifacts go through out/<run-timestamp>/... resumable" invariant).
    """
    if out_path.exists():
        return out_path

    clips = overlay_clips_for(template.genre_key)
    has_overlay = bool(clips)

    fg = build_filtergraph(
        template=template, beats=beats, has_overlay=has_overlay, size=size
    ).replace("{ASS}", _escape_ffmpeg_filter_path(ass_path))

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
    use_concat_bg = len(stills) > 1

    work = Path(tempfile.mkdtemp(prefix="song-animate-"))
    try:
        if use_concat_bg:
            bg_video = _render_still_backdrop(stills, beats, size, work)
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
            cmd += ["-stream_loop", "-1", "-c:v", "libvpx-vp9", "-i", str(clips[0])]
        cmd += ["-i", str(song_mp3)]

        audio_idx = 2 if has_overlay else 1
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
