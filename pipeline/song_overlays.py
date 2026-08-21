"""Per-genre overlay-loop lookup + the ffmpeg command that renders them.

`overlay_clips_for` is what the Task 5 FX compositor
(`pipeline/song_animate.py`) calls to find pre-rendered, alpha-transparent
motion loops (particles/bokeh/light-sweep/geometric/grain) for a song's
genre. If `assets/overlays/<genre_key>/` is absent or has no `.webm` files,
it returns `[]` and the compositor falls back to procedural-only FX — never
an error (see design spec: "No assets/overlays/<genre_key>/ -> procedural
FX only").

`build_overlay_cmd` builds the ffmpeg argv used by `scripts/gen_overlays.py`
to *render* those loops once, offline (no network, no AI, no real ffmpeg
execution in tests — only argv construction is unit-tested here). `_LAVFI`
holds one lavfi-filtergraph builder per overlay `kind`; each renders a
`seconds`-long, alpha-transparent (`yuva420p`) loop at `size`.
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def overlay_clips_for(genre_key: str) -> list[Path]:
    """Existing pre-rendered overlay clips for a genre, or `[]`.

    `[]` whenever `assets/overlays/<genre_key>/` doesn't exist or has no
    `.webm` files in it — genres without a bespoke loop library get
    procedural-only FX (graceful fallback, never an error).
    """
    d = REPO_ROOT / "assets" / "overlays" / genre_key
    return sorted(d.glob("*.webm")) if d.is_dir() else []


def _particles(w: int, h: int, seconds: int) -> str:
    """Sparkle field: a Conway's-life cellular automaton, black keyed to
    transparent. Life's cell pattern is frame-to-frame decorrelated, so the
    loop seam (last frame -> first frame on repeat) isn't perceptible."""
    return (
        f"life=size={w}x{h}:mold=3:rate=25:ratio=0.04:stitch=1:"
        f"life_color=white:death_color=black:mold_color=black,"
        f"gblur=sigma=2,"
        f"colorkey=color=black:similarity=0.16:blend=0.05,"
        f"format=rgba,colorchannelmixer=aa=0.7,"
        f"format=yuva420p"
    )


def _bokeh(w: int, h: int, seconds: int) -> str:
    """Soft out-of-focus color blobs: a rotating radial gradient, heavily
    blurred, held at a low constant opacity."""
    return (
        f"gradients=size={w}x{h}:rate=25:duration={seconds}:type=radial:"
        f"nb_colors=3:speed=0.02,"
        f"gblur=sigma=40,"
        f"format=rgba,colorchannelmixer=aa=0.45,"
        f"format=yuva420p"
    )


def _light_sweep(w: int, h: int, seconds: int) -> str:
    """A soft light band sweeping across frame: a rotating linear gradient
    at low opacity."""
    return (
        f"gradients=size={w}x{h}:rate=25:duration={seconds}:type=linear:"
        f"nb_colors=2:c0=black:c1=white:speed=0.05,"
        f"format=rgba,colorchannelmixer=aa=0.55,"
        f"format=yuva420p"
    )


def _geometric(w: int, h: int, seconds: int) -> str:
    """Rotating angular gradient bands, black keyed to transparent, for a
    faceted/arabesque-adjacent shape look."""
    return (
        f"gradients=size={w}x{h}:rate=25:duration={seconds}:type=square:"
        f"nb_colors=4:speed=0.03,"
        f"colorkey=color=black:similarity=0.12:blend=0,"
        f"format=yuva420p"
    )


# kind -> callable(w, h, seconds) -> ffmpeg -filter_complex lavfi graph.
# Each entry renders a seamless, alpha-transparent loop for one overlay
# "kind" (see docs/superpowers/specs/2026-08-20-animated-genre-song-video-design.md,
# section 5: "particles, bokeh, light-sweep, geometric shapes, grain").
_LAVFI: dict[str, Callable[[int, int, int], str]] = {
    "particles": _particles,
    "bokeh": _bokeh,
    "light_sweep": _light_sweep,
    "geometric": _geometric,
}


def build_overlay_cmd(
    kind: str, out: Path, size: tuple[int, int], seconds: int
) -> list[str]:
    """ffmpeg argv that renders one seamless, alpha-transparent overlay
    loop of `kind` (a key of `_LAVFI`) to `out`, at `size` for `seconds`.

    Not run here — `scripts/gen_overlays.py` is the only caller that
    actually executes this against real ffmpeg.
    """
    w, h = size
    src = _LAVFI[kind](w, h, seconds)
    return [
        "ffmpeg", "-y", "-filter_complex", src, "-t", str(seconds),
        # VP9 constant-quality at an aggressive CRF. Overlays are soft,
        # semi-transparent, and scaled up at composite time, so heavy
        # compression is invisible — but it keeps each loop small (a full-res
        # default-CRF particle loop was ~37 MB, which ballooned the final
        # video). -an: overlays are video-only.
        "-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "42",
        "-pix_fmt", "yuva420p", "-an", str(out),
    ]
