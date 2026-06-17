"""Cinematic (beat-synced) song-video assembler — robust per-clip pipeline.

History: the first implementation built ONE giant ffmpeg filtergraph that
fed each pool image to `zoompan` as an infinite `-loop 1` input and chained
the segments with `xfade`. That proved fragile in the production ffmpeg
(Debian 5.1.x): a looped still gives `zoompan` an undefined output frame
rate (1/0), which `xfade` rejects ("inputs needs to be a constant frame
rate"), and the looped input also produces a runaway, time-distorted stream.
Newer ffmpeg (8.x) hides both, so unit tests + a local smoke test passed
while production fell back to the static cover (a single photo).

This version is deliberately boring and robust:

  1. Render each beat segment as a SELF-CONTAINED, bounded, constant-frame-
     rate Ken-Burns clip on LOCAL disk (`-loop 1 -i img` + `-t {dur}` so the
     clip is exactly `dur` seconds — no runaway, defined rate).
  2. Join the clips with the concat demuxer (`-c copy`) — hard cuts on the
     beat, the canonical beat-synced look, and far more robust than xfade.
  3. One final pass muxes audio + burns the karaoke `.ass` + composites the
     watermark, written to LOCAL disk then copied to the destination. Writing
     the +faststart output locally avoids GCS-Fuse's backward-seek failure
     (BufferedWriteHandler.OutOfOrderError) on the moov-atom rewrite.

See docs/superpowers/specs/2026-06-16-beat-synced-song-video-design.md.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
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


def _run(cmd: list[str]) -> None:
    """Run ffmpeg, surfacing stderr in the exception for debuggability."""
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode("utf-8", "replace") if exc.stderr else ""
        raise RuntimeError(
            f"ffmpeg failed (exit {exc.returncode}): {stderr[-2000:]}"
        ) from exc


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


def segment_vf(seg: Segment, frames: int) -> str:
    """Pure: the -vf chain that turns one still into a bounded Ken-Burns clip.

    `setsar=1` + the fixed `fps` (from the bounded `-loop 1 -t` input) keep the
    clip constant-frame-rate so the concat demuxer joins clips cleanly."""
    if seg.zoom_dir == "in":
        z = f"1+{(ZOOM_END - 1.0):.6f}*on/{frames}"
    else:
        z = f"{ZOOM_END:.6f}-{(ZOOM_END - 1.0):.6f}*on/{frames}"
    return (
        f"scale={UPSCALE_SIZE}:{UPSCALE_SIZE},"
        f"zoompan=z='{z}':d={frames}:s={OUTPUT_SIZE}x{OUTPUT_SIZE}:fps={FPS},"
        f"setsar=1,format=yuv420p"
    )


def _render_segment(scene_path: Path, seg: Segment, out_clip: Path) -> None:
    """Render one bounded Ken-Burns clip. `-t {dur}` bounds the looped input
    so zoompan produces exactly `frames` frames at a defined rate."""
    frames = max(1, round((seg.end - seg.start) * FPS))
    dur = frames / FPS
    _run([
        "ffmpeg", "-y", "-loop", "1", "-i", str(scene_path),
        "-vf", segment_vf(seg, frames),
        "-t", f"{dur:.3f}", "-r", str(FPS),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p", "-f", "mp4", str(out_clip),
    ])


def _final_filter(ass_filter: str, has_watermark: bool) -> str:
    """Pure: the final-pass filtergraph (input 0 = concatenated video,
    input 1 = audio, input 2 = watermark if present)."""
    if has_watermark:
        return (
            f"[0:v]format=yuv420p{ass_filter}[vs];"
            "[2:v]scale=240:55[wm];"
            "[vs][wm]overlay=W-w-28:28[v]"
        )
    return f"[0:v]format=yuv420p{ass_filter}[v]"


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
    """Render the beat-synced video via the per-clip pipeline. Raises
    RuntimeError on ffmpeg failure (message includes ffmpeg stderr) or if the
    result fails the playability gate."""
    if not schedule:
        raise ValueError("schedule is empty")

    work = Path(tempfile.mkdtemp(prefix="cine-"))
    try:
        # 1) one bounded CFR clip per segment (local disk)
        clips: list[Path] = []
        for i, seg in enumerate(schedule):
            clip = work / f"seg_{i:04d}.mp4"
            _render_segment(scene_paths[seg.image_idx], seg, clip)
            clips.append(clip)

        # 2) concat (stream copy) — hard cuts on the beat
        list_file = work / "concat.txt"
        list_file.write_text(
            "".join(f"file '{c.as_posix()}'\n" for c in clips), encoding="utf-8"
        )
        video = work / "video.mp4"
        _run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
            "-c", "copy", "-f", "mp4", str(video),
        ])

        # 3) final pass: karaoke + watermark + audio, +faststart, LOCAL disk
        ass_filter = ""
        if lyrics_json is not None and lyrics_json.exists():
            try:
                data = json.loads(lyrics_json.read_text(encoding="utf-8"))
                ass_path = work / "lyrics.ass"
                if _write_ass_subtitles(data, ass_path):
                    ass_filter = f",ass='{_escape_ffmpeg_filter_path(ass_path)}'"
            except (OSError, json.JSONDecodeError, ValueError):
                ass_filter = ""

        has_watermark, watermark_png = resolve_watermark()
        final_local = work / "final.mp4"
        cmd = ["ffmpeg", "-y", "-i", str(video), "-i", str(song_mp3)]
        if has_watermark:
            cmd += ["-loop", "1", "-i", str(watermark_png)]
        cmd += [
            "-filter_complex", _final_filter(ass_filter, has_watermark),
            "-map", "[v]", "-map", "1:a",
            *build_metadata_args(title, share_token),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-shortest",
            "-movflags", "+faststart",
            "-threads", "0",
            "-f", "mp4", str(final_local),
        ]
        _run(cmd)
        assert_playable(final_local)

        # 4) publish: copy local result to the destination. A plain sequential
        # copy (no backward seeks) is GCS-Fuse-safe, unlike ffmpeg's in-place
        # +faststart write.
        out_mp4.parent.mkdir(parents=True, exist_ok=True)
        tmp_dest = Path(str(out_mp4) + ".tmp")
        if tmp_dest.exists():
            try:
                tmp_dest.unlink()
            except OSError:
                try:
                    tmp_dest.write_bytes(b"")
                except OSError:
                    pass
        shutil.copyfile(final_local, tmp_dest)
        tmp_dest.replace(out_mp4)
    finally:
        shutil.rmtree(work, ignore_errors=True)
