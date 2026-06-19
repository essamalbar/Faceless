"""YouTube song import: fetch a reference track and turn it into an ORIGINAL
inspired song script.

The reference is used for inspiration only — tempo, genre, mood, theme and
section structure. The verbatim transcript is transient and is never stored,
displayed, or used to reproduce/paraphrase the source. See
docs/superpowers/specs/2026-06-19-youtube-song-import-design.md.
"""
from __future__ import annotations

import re
from pathlib import Path


class ImportFetchError(RuntimeError):
    """Raised when the reference audio can't be fetched (private, region-
    locked, age-restricted, network, or a datacenter-IP block)."""


def _ytdlp_download(url: str, out_template: str) -> str:
    """Download bestaudio to out_template via yt-dlp. Isolated so tests can
    monkeypatch it without invoking the network/binary."""
    import yt_dlp
    opts = {
        "format": "bestaudio/best",
        "outtmpl": out_template,
        "quiet": True,
        "noplaylist": True,
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "m4a"}
        ],
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])
    return out_template


def download_audio(url: str, out_dir: Path) -> Path:
    """Fetch the reference audio to out_dir/reference.m4a. Raises
    ImportFetchError with a clear message on any failure."""
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / "reference.m4a"
    try:
        _ytdlp_download(url, str(dest))
    except Exception as e:  # yt-dlp raises many error types
        raise ImportFetchError(
            f"Couldn't fetch that link — it may be private, region-locked, "
            f"or blocked. ({e})"
        ) from e
    if not dest.exists():
        raise ImportFetchError("Couldn't fetch that link — no audio downloaded.")
    return dest
