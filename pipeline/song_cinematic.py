"""Cinematic (beat-synced) song-video assembler -- Approach A.

ONE ffmpeg invocation: each pool image is scaled + zoompan'd on its
segment, the segments are chained with xfade, then the existing karaoke
.ass and brand watermark are composited on top. No intermediate files
(GCS-Fuse-safe): write to .tmp, then atomic rename -- same pattern as
song_assemble.assemble_song_video.

See docs/superpowers/specs/2026-06-16-beat-synced-song-video-design.md.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from pipeline.song_assemble import (
    FPS,
    OUTPUT_SIZE,
    UPSCALE_SIZE,
    ZOOM_END,
    _escape_ffmpeg_filter_path,
    _write_ass_subtitles,
    build_metadata_args,
    resolve_watermark,
)
from pipeline.song_scenes import Segment

_XFADE_S = 0.35  # crossfade duration on each cut (matches assemble shot crossfade)


def assert_playable(mp4: Path) -> None:
    """Raise if the output has no video+audio stream or zero duration.
    Cheap guard against the MEDIA_ERR_SRC_NOT_SUPPORTED failure class."""
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_type:format=duration", "-of", "json", str(mp4)],
        capture_output=True, text=True, check=True,
    )
    try:
        data = json.loads(probe.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"ffprobe returned non-JSON output for {mp4}") from exc
    kinds = {s.get("codec_type") for s in data.get("streams", [])}
    duration = float(data.get("format", {}).get("duration", 0.0) or 0.0)
    if "video" not in kinds or "audio" not in kinds or duration <= 0.0:
        raise RuntimeError(f"output not playable: streams={kinds} duration={duration}")


def build_filter_complex(
    *,
    segments: list[Segment],
    n_images: int,
    ass_filter: str,
    has_watermark: bool,
) -> str:
    """Pure: turn a cut schedule into one ffmpeg -filter_complex string.

    Inputs are the N pool images ([0:v]..[N-1:v]); audio is a separate
    input mapped later. Each segment trims its image to its duration with
    a zoompan, then segments are xfade-chained in order."""
    # Caller contract: every segment after the first must be longer than
    # _XFADE_S so the chained xfade offsets stay monotonically increasing
    # (ffmpeg treats non-monotonic offsets as undefined). song_scenes'
    # min_segment_s (default 0.6) satisfies this.
    if any((s.end - s.start) <= _XFADE_S for s in segments[1:]):
        raise ValueError(
            f"all segments after the first must be longer than _XFADE_S={_XFADE_S}s "
            f"to keep xfade offsets monotonic"
        )

    parts: list[str] = []
    seg_labels: list[str] = []

    for i, seg in enumerate(segments):
        dur = max(0.1, seg.end - seg.start)
        frames = max(1, int(dur * FPS))
        if seg.zoom_dir == "in":
            z = f"1+{(ZOOM_END - 1.0):.6f}*on/{frames}"
        else:
            z = f"{ZOOM_END:.6f}-{(ZOOM_END - 1.0):.6f}*on/{frames}"
        label = f"s{i}"
        parts.append(
            f"[{seg.image_idx}:v]scale={UPSCALE_SIZE}:{UPSCALE_SIZE},"
            f"zoompan=z='{z}':d={frames}:s={OUTPUT_SIZE}x{OUTPUT_SIZE}:fps={FPS},"
            f"trim=duration={dur:.3f},setpts=PTS-STARTPTS[{label}]"
        )
        seg_labels.append(label)

    if len(seg_labels) == 1:
        chain_out = seg_labels[0]
    else:
        prev = seg_labels[0]
        acc = segments[0].end - segments[0].start
        for i in range(1, len(seg_labels)):
            out = f"x{i}"
            offset = max(0.0, acc - _XFADE_S)
            parts.append(
                f"[{prev}][{seg_labels[i]}]"
                f"xfade=transition=fade:duration={_XFADE_S}:offset={offset:.3f}[{out}]"
            )
            acc += (segments[i].end - segments[i].start) - _XFADE_S
            prev = out
        chain_out = prev

    tail = f"[{chain_out}]format=yuv420p{ass_filter}"
    if has_watermark:
        wm_idx = n_images + 1
        return (
            ";".join(parts) + ";" +
            tail + "[vsub];" +
            f"[{wm_idx}:v]scale=240:55[wm];" +
            "[vsub][wm]overlay=W-w-28:28[v]"
        )
    return ";".join(parts) + ";" + tail + "[v]"


def assemble_cinematic_song_video(
    *,
    scene_paths: list[Path],
    song_mp3: Path,
    out_mp4: Path,
    schedule: list[Segment],
    lyrics_json: Path | None = None,
    title: str | None = None,
    share_token: str | None = None,
) -> None:
    """Render the beat-synced video in one ffmpeg call. Raises
    RuntimeError on ffmpeg failure (message includes ffmpeg stderr) or if
    the result fails the playability gate."""
    ass_filter = ""
    if lyrics_json is not None and lyrics_json.exists():
        try:
            data = json.loads(lyrics_json.read_text(encoding="utf-8"))
            ass_path = lyrics_json.with_name("lyrics.ass")
            if _write_ass_subtitles(data, ass_path):
                ass_filter = f",ass='{_escape_ffmpeg_filter_path(ass_path)}'"
        except (OSError, json.JSONDecodeError, ValueError):
            ass_filter = ""

    has_watermark, watermark_png = resolve_watermark()
    filter_complex = build_filter_complex(
        segments=schedule, n_images=len(scene_paths),
        ass_filter=ass_filter, has_watermark=has_watermark,
    )

    cmd = ["ffmpeg", "-y"]
    for p in scene_paths:                       # inputs 0..N-1 : pool images
        cmd += ["-loop", "1", "-i", str(p)]
    cmd += ["-i", str(song_mp3)]                # input N : audio
    if has_watermark:
        cmd += ["-loop", "1", "-i", str(watermark_png)]   # input N+1 : watermark
    cmd += [
        "-filter_complex", filter_complex,
        "-map", "[v]", "-map", f"{len(scene_paths)}:a",
        *build_metadata_args(title, share_token),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        "-movflags", "+faststart",
        "-threads", "0",
        "-f", "mp4",
        str(out_mp4) + ".tmp",
    ]
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = Path(str(out_mp4) + ".tmp")
    if tmp_path.exists():
        try:
            tmp_path.unlink()
        except OSError:
            try:
                tmp_path.write_bytes(b"")
            except OSError:
                pass
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode("utf-8", "replace") if exc.stderr else ""
        raise RuntimeError(
            f"ffmpeg failed (exit {exc.returncode}): {stderr[-2000:]}"
        ) from exc
    tmp_path.replace(out_mp4)
    assert_playable(out_mp4)
