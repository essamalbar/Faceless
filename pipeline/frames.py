"""Helpers for extracting frames from video clips.

Used by the Tier-3 video stage to chain image-to-video: last frame of clip N
becomes the first-frame reference for clip N+1.
"""
from __future__ import annotations

import subprocess
from pathlib import Path


def _audio_duration_s(path: Path) -> float:
    out = subprocess.check_output([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "csv=p=0", str(path),
    ], text=True).strip()
    return float(out)


def extract_last_frame(clip_path: Path, out_path: Path) -> None:
    """Pull the very last frame of a video clip and save as PNG.

    Seeks to (duration - 0.05s) and grabs one frame. The 50ms buffer avoids
    "no frame at exact end" issues with some codecs.
    """
    duration = _audio_duration_s(clip_path)
    seek_t = max(duration - 0.05, 0.0)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-ss", f"{seek_t:.2f}",
        "-i", str(clip_path),
        "-frames:v", "1",
        "-q:v", "2",
        str(out_path),
    ], check=True)
