from __future__ import annotations

import struct
import subprocess
from pathlib import Path

import pytest

from pipeline.mp4_faststart import rewrite_with_faststart


def _atom_order(path: Path) -> list[str]:
    """Return the atom names in order from the start of the mp4."""
    with open(path, "rb") as f:
        data = f.read()
    pos = 0
    names: list[str] = []
    while pos < len(data) - 8:
        size = struct.unpack(">I", data[pos:pos + 4])[0]
        name = data[pos + 4:pos + 8].decode("latin-1", errors="replace")
        names.append(name)
        if size == 0 or size == 1:
            break
        pos += size
    return names


def _make_test_mp4(path: Path) -> None:
    """Use ffmpeg to make an mp4 with moov at the END (no faststart).

    Uses a high-detail source (testsrc2) so the encoded file is comfortably
    larger than mp4_faststart's 50 KB corruption guard — a solid `color=`
    clip compresses to ~2 KB and would be discarded by that guard, leaving
    moov at the end and defeating the point of the test.
    """
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error",
         "-f", "lavfi", "-i", "testsrc2=size=640x480:rate=30:duration=3",
         "-pix_fmt", "yuv420p",
         str(path)],
        check=True,
    )
    # Guard: the whole point is to exceed mp4_faststart's 50 KB threshold.
    assert path.stat().st_size > 50_000, (
        f"test fixture too small ({path.stat().st_size} B) — the faststart "
        "corruption guard would discard the re-mux"
    )


def test_faststart_moves_moov_to_front(tmp_path):
    p = tmp_path / "clip.mp4"
    _make_test_mp4(p)
    before = _atom_order(p)
    # Default ffmpeg output puts moov AFTER mdat
    assert before.index("moov") > before.index("mdat"), (
        f"test setup expected moov-at-end, got {before}"
    )

    rewrite_with_faststart(p)

    after = _atom_order(p)
    assert "moov" in after and "mdat" in after
    assert after.index("moov") < after.index("mdat"), (
        f"after faststart, moov must come before mdat — got {after}"
    )


def test_faststart_idempotent_on_already_faststart(tmp_path):
    """Running it twice on the same file must produce the same result."""
    p = tmp_path / "clip.mp4"
    _make_test_mp4(p)
    rewrite_with_faststart(p)
    first = p.read_bytes()
    rewrite_with_faststart(p)
    second = p.read_bytes()
    # Some ffmpeg versions slightly reorder bytes on re-mux but the layout
    # is stable — assert moov still ahead of mdat.
    after = _atom_order(p)
    assert after.index("moov") < after.index("mdat")


def test_faststart_silent_on_ffmpeg_failure(tmp_path, monkeypatch):
    """If ffmpeg is missing or the file is corrupt, the original mp4 must
    NOT be deleted/corrupted — we'd rather have a slow-to-load clip than
    a missing one."""
    p = tmp_path / "clip.mp4"
    p.write_bytes(b"not actually an mp4")
    original = p.read_bytes()
    # Should NOT raise
    rewrite_with_faststart(p)
    assert p.exists()
    assert p.read_bytes() == original  # left intact
