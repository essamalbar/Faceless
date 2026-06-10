"""ffmpeg assembly: cover.png + song.mp3 → final.mp4.

Quality gates (do not silently optimize away — see spec section
"Assembly (ffmpeg)"):
  - `-c:a copy` preserves Suno's mastering bit-for-bit. Do NOT re-encode.
  - No loudnorm/dynaudnorm filters — Suno is already at -14 LUFS.
  - `-movflags +faststart` puts moov atom at the front so the Flutter
    `<video>` player streams immediately.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

FPS = 25
OUTPUT_SIZE = 1080
UPSCALE_SIZE = 2160  # pre-zoompan upscale to avoid resampling blur
ZOOM_END = 1.13  # target zoom at end of song


def ffprobe_duration(path: Path) -> float:
    """Authoritative duration in seconds (Suno's job metadata is sometimes off)."""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json",
         "-show_format", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(json.loads(out.stdout)["format"]["duration"])


def assemble_song_video(*, cover_path: Path, song_mp3: Path, out_mp4: Path) -> None:
    """Build the music-video MP4. Raises subprocess.CalledProcessError on failure."""
    duration_s = ffprobe_duration(song_mp3)
    total_frames = max(1, int(duration_s * FPS))
    zoom_step = (ZOOM_END - 1.0) / total_frames

    filter_complex = (
        f"[0:v]scale={UPSCALE_SIZE}:{UPSCALE_SIZE},"
        f"zoompan=z='1+{zoom_step:.10f}*on':"
        f"d={total_frames}:s={OUTPUT_SIZE}x{OUTPUT_SIZE}:fps={FPS}[v]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(cover_path),
        "-i", str(song_mp3),
        "-filter_complex", filter_complex,
        "-map", "[v]", "-map", "1:a",
        # preset=veryfast: a still cover with slow zoompan has zero
        # motion-compensation benefit from slower presets. On Cloud Run's
        # 2 vCPU, `slow` was taking 15-40 min per song; `veryfast` does
        # the same in 1-2 min with imperceptible visual difference.
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        # Audio MUST be AAC inside an MP4 container — browsers (Chrome,
        # Safari, Firefox) reject MP3 audio in MP4 with
        # MEDIA_ERR_SRC_NOT_SUPPORTED. Suno's output is MP3, so we
        # transcode here. The earlier `-c:a copy` design was wrong;
        # it produced files that wouldn't play in the Flutter video
        # player. At 192k AAC the loss from MP3→AAC is imperceptible.
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        "-movflags", "+faststart",
        "-threads", "0",  # use all available vCPUs
        # Force MP4 muxer — ffmpeg infers format from the output
        # file extension, but we're writing to "<name>.mp4.tmp" so
        # the autodetect fails. -f mp4 makes the format explicit.
        "-f", "mp4",
        # Write to a temp file then atomic-rename. Without this, a
        # killed worker or a crashed ffmpeg leaves a half-written
        # final.mp4 on disk that the API happily serves as broken
        # video. Two concurrent assemblers also corrupt each other.
        str(out_mp4) + ".tmp",
    ]
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = Path(str(out_mp4) + ".tmp")
    subprocess.run(cmd, check=True, capture_output=True)
    # Atomic rename — POSIX guarantees readers see either the old
    # file or the new one, never a torn read. GCS Fuse supports
    # atomic rename on objects without the .tmp prefix conflict.
    tmp_path.replace(out_mp4)
