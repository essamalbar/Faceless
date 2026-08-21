"""Offline generator for the starter overlay-loop library.

Renders each genre's overlay kinds — derived from its `VisualTemplate.fx_set`
(`pipeline/song_visual_style.py`), per the design's per-genre FX — via
`pipeline.song_overlays.build_overlay_cmd`, and writes the resulting webm
loops to `assets/overlays/<genre_key>/<kind>.webm`. No network, no AI: pure
local ffmpeg. Run once; outputs are meant to be committed and reused at
$0/render (see
docs/superpowers/specs/2026-08-20-animated-genre-song-video-design.md,
section 5).

    uv run python scripts/gen_overlays.py                       # every genre with an overlay_dir
    uv run python scripts/gen_overlays.py --genres arabic_trap,arabic_ballad
    uv run python scripts/gen_overlays.py --seconds 4 --width 640 --height 1138

Generating the starter asset library (running this + eyeballing loop
quality/alpha) is a separate human/controller gate; this script only needs
to run cleanly against real ffmpeg — it does not verify its own output.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# scripts/ lives outside the pipeline/ package, and this project isn't
# installed (pyproject.toml: [tool.uv] package = false), so — unlike
# run.py, which sits at the repo root and already sees it — the repo root
# needs to be put on sys.path before the `pipeline.*` absolute imports
# below will resolve.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.song_overlays import REPO_ROOT, build_overlay_cmd  # noqa: E402
from pipeline.song_style import GENRE_RECIPES  # noqa: E402
from pipeline.song_visual_style import visual_template_for  # noqa: E402

DEFAULT_SIZE = (1080, 1920)
DEFAULT_SECONDS = 6


def _kinds_for(fx_set: tuple[str, ...]) -> list[str]:
    """Pick 1-3 overlay kinds for a genre from its VisualTemplate.fx_set:
    light_sweep/grain carry straight across when the genre's procedural FX
    already uses them; neon/glitch genres (the Trap/Mahragan benchmark) get
    particles + geometric for extra "wow"; warm/push-in genres get bokeh;
    cool-graded genres get geometric. Capped at 3 so the starter library
    per genre stays small."""
    kinds: list[str] = [k for k in ("light_sweep", "grain") if k in fx_set]
    if "grade_neon" in fx_set:
        kinds += ["particles", "geometric"]
    elif "rgb_glitch" in fx_set:
        kinds.append("particles")
    if "push_in" in fx_set or "grade_warm" in fx_set:
        kinds.append("bokeh")
    if "grade_cool" in fx_set:
        kinds.append("geometric")
    deduped = list(dict.fromkeys(kinds))
    return deduped[:3] or ["grain"]


def genres_with_overlays() -> list[str]:
    """Every genre_key whose VisualTemplate opts into an overlay dir
    (excludes "generic", which is procedural-FX-only by design)."""
    return [key for key in GENRE_RECIPES if visual_template_for(key).overlay_dir]


def generate(genre_key: str, *, size: tuple[int, int], seconds: int) -> list[Path]:
    """Render every overlay kind for one genre; return the paths written."""
    template = visual_template_for(genre_key)
    out_dir = REPO_ROOT / "assets" / "overlays" / genre_key
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for kind in _kinds_for(template.fx_set):
        out = out_dir / f"{kind}.webm"
        cmd = build_overlay_cmd(kind, out, size, seconds)
        subprocess.run(cmd, check=True)
        written.append(out)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--genres", default="",
        help="comma-separated genre_key list (default: every genre with an overlay_dir)",
    )
    parser.add_argument("--seconds", type=int, default=DEFAULT_SECONDS)
    parser.add_argument("--width", type=int, default=DEFAULT_SIZE[0])
    parser.add_argument("--height", type=int, default=DEFAULT_SIZE[1])
    args = parser.parse_args(argv)

    genres = [g.strip() for g in args.genres.split(",") if g.strip()] or genres_with_overlays()
    size = (args.width, args.height)
    for genre_key in genres:
        paths = generate(genre_key, size=size, seconds=args.seconds)
        names = ", ".join(p.name for p in paths)
        print(f"{genre_key}: {names} -> {paths[0].parent}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
