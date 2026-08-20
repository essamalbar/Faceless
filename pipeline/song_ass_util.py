"""Shared ASS/ffmpeg string helpers used by both song assemblers
(pipeline.song_assemble, pipeline.song_cinematic) and the kinetic-lyric
ASS builder (pipeline.song_kinetic_ass). Extracted from song_assemble so
the new kinetic builder doesn't duplicate (or drift from) the escaping
and timestamp-formatting logic. Pure string helpers; no I/O, no network.
"""
from __future__ import annotations

from pathlib import Path


def _format_ass_time(t: float) -> str:
    """ASS expects H:MM:SS.cs (centiseconds, not milliseconds)."""
    if t < 0:
        t = 0
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _ass_escape(text: str) -> str:
    """Escape characters that ASS treats specially in a Dialogue line."""
    # ASS uses {} for inline tags and \N for line breaks. Strip them
    # rather than encode — none should occur in clean lyric input, but
    # be defensive. Keep newlines collapsed to spaces.
    return (
        text.replace("\n", " ")
            .replace("{", "(")
            .replace("}", ")")
    )


def _escape_ffmpeg_filter_path(p: Path) -> str:
    """ffmpeg's filtergraph parser treats `:` as a delimiter and `'` /
    `\\` as escape chars. The ass= filter takes its path argument in
    that filtergraph string, so the path needs filtergraph-level
    escaping (NOT shell escaping). On the typical Cloud Run path
    `/mnt/runs/.../lyrics.ass` this matters mainly because of the
    leading `/` is fine but any colon (Windows drive letter, never
    seen on Linux) would otherwise break parsing."""
    s = str(p)
    s = s.replace("\\", "\\\\")
    s = s.replace(":", "\\:")
    s = s.replace("'", "\\'")
    return s
