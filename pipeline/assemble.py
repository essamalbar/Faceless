"""Stage 8: video assembly via FFmpeg."""
from __future__ import annotations

import subprocess
from pathlib import Path

from pipeline.types import Shot

# Ken Burns motion patterns. zoompan filter syntax:
# (z, x, y) — z is zoom factor, x/y are crop offsets within the source.
# Each pattern returns (z, x, y) expressions over normalized progress t (0→1).
KEN_BURNS_PATTERNS: list[tuple[str, str, str]] = [
    # 0: zoom in, hold center
    ("1.0+0.10*on/d", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),
    # 1: zoom out + pan right
    ("1.10-0.10*on/d", "(iw-iw/zoom)*on/d", "ih/2-(ih/zoom/2)"),
    # 2: zoom in + pan left
    ("1.0+0.10*on/d", "(iw-iw/zoom)*(1-on/d)", "ih/2-(ih/zoom/2)"),
    # 3: zoom in + pan down
    ("1.0+0.10*on/d", "iw/2-(iw/zoom/2)", "(ih-ih/zoom)*on/d"),
]


def pick_motion_pattern(shot_index_zero_based: int) -> tuple[str, str, str]:
    return KEN_BURNS_PATTERNS[shot_index_zero_based % len(KEN_BURNS_PATTERNS)]


def build_filter_graph(
    shots: list[Shot],
    output_w: int,
    output_h: int,
    crossfade_ms: int,
    burn_caption_ass: Path | None,
) -> str:
    """Build the FFmpeg -filter_complex graph string.

    Inputs (in order):
      [0:v]…[N-1:v]: still images, one per shot
      [N:a] narration mp3
      [N+1:a] music mp3
    Output:
      [vout] [aout]
    """
    parts: list[str] = []
    # Per-shot zoompan + scale to output resolution.
    # NOTE: FFmpeg's zoompan filter does NOT expose `d` (the duration param) as a
    # variable inside z/x/y expressions. We substitute the literal frame count
    # so the generated filter uses e.g. `1.0+0.10*on/120` instead of `.../d`.
    # Replace `/d` (the only place `d` appears in our patterns) with `/<frames>`.
    import re as _re
    for i, shot in enumerate(shots):
        duration_s = max((shot.end_ms - shot.start_ms) / 1000.0, 0.2)
        z_template, x_template, y_template = pick_motion_pattern(i)
        d_frames = max(int(duration_s * 30), 1)
        # Word-boundary substitution: only `d` as a standalone variable, not within other words.
        sub = lambda s: _re.sub(r"\bd\b", str(d_frames), s)
        z, x, y = sub(z_template), sub(x_template), sub(y_template)
        parts.append(
            f"[{i}:v]scale={output_w * 2}:{output_h * 2},"
            f"zoompan=z='{z}':x='{x}':y='{y}':d={d_frames}:s={output_w}x{output_h}:fps=30,"
            f"setpts=PTS-STARTPTS,format=yuv420p[v{i}]"
        )
    # Crossfade chain: v0 + v1 → vab; vab + v2 → vabc; ...
    crossfade_s = crossfade_ms / 1000.0
    if len(shots) == 1:
        last_label = "v0"
    else:
        cumulative = (shots[0].end_ms - shots[0].start_ms) / 1000.0
        last_label = "v0"
        for i in range(1, len(shots)):
            new_label = f"vx{i}"
            offset = max(cumulative - crossfade_s, 0.0)
            parts.append(
                f"[{last_label}][v{i}]xfade=transition=fade:"
                f"duration={crossfade_s}:offset={offset:.3f}[{new_label}]"
            )
            cumulative += (shots[i].end_ms - shots[i].start_ms) / 1000.0 - crossfade_s
            last_label = new_label

    # Optional subtitle burn-in.
    if burn_caption_ass is not None:
        # Escape colon and backslash for ffmpeg filter arg.
        ass_path = str(burn_caption_ass).replace("\\", "\\\\").replace(":", r"\:")
        parts.append(f"[{last_label}]subtitles='{ass_path}'[vout]")
    else:
        parts.append(f"[{last_label}]copy[vout]")

    # Audio: narration is [N:a]; music is [N+1:a]. Sidechain ducks music by narration.
    n = len(shots)
    parts.append(
        f"[{n+1}:a]aloop=loop=-1:size=2e+09[mloop];"
        f"[mloop][{n}:a]sidechaincompress=threshold=0.05:ratio=8:attack=20:release=300[ducked];"
        f"[{n}:a][ducked]amix=inputs=2:duration=first:dropout_transition=0[aout]"
    )
    return ";".join(parts)


def _run_ffmpeg(args: list[str]) -> None:
    """Replaceable in tests via monkeypatch."""
    subprocess.run(args, check=True)


def assemble_video(
    shots: list[Shot],
    images_dir: Path,
    narration_path: Path,
    music_path: Path,
    out_path: Path,
    burn_caption_ass: Path | None,
    output_width: int,
    output_height: int,
    crossfade_ms: int,
    music_duck_db: int,
    music_silence_db: int,
    fade_in_s: int,
    fade_out_s: int,
) -> None:
    """Resumable: skips if out_path already exists."""
    if out_path.exists():
        return
    out_path.parent.mkdir(parents=True, exist_ok=True)

    args: list[str] = ["ffmpeg", "-y"]
    # Image inputs — each shot is a still input with a -loop 1 flag and matching duration.
    for shot in shots:
        duration_s = max((shot.end_ms - shot.start_ms) / 1000.0, 0.2)
        args += [
            "-loop", "1",
            "-t", f"{duration_s:.3f}",
            "-i", str(images_dir / f"{shot.index:02d}.png"),
        ]
    args += ["-i", str(narration_path)]
    args += ["-i", str(music_path)]

    graph = build_filter_graph(
        shots=shots, output_w=output_width, output_h=output_height,
        crossfade_ms=crossfade_ms, burn_caption_ass=burn_caption_ass,
    )
    args += [
        "-filter_complex", graph,
        "-map", "[vout]",
        "-map", "[aout]",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        str(out_path),
    ]
    _run_ffmpeg(args)
