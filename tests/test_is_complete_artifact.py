"""Regression test for the resumability bug that broke Run A's recovery
(daf8e3d8.../2026-05-15-071522): a 0-byte `final.mp4` left over from a
previous crashed assembly was treated as "already done" by the stage
idempotency check, so /resume short-circuited without re-rendering.

The fix is a single helper, `is_complete_artifact`, that requires both
existence AND non-zero size. Every stage now uses it instead of bare
`path.exists()`.
"""
from __future__ import annotations

from pathlib import Path

from pipeline.types import is_complete_artifact


def test_returns_false_for_missing_file(tmp_path: Path) -> None:
    assert is_complete_artifact(tmp_path / "nope.mp4") is False


def test_returns_false_for_zero_byte_file(tmp_path: Path) -> None:
    """The bug that broke Run A — final.mp4 was 0 bytes, .exists() returned
    True, the assembly stage thought it was done and skipped."""
    p = tmp_path / "empty.mp4"
    p.touch()
    assert p.exists() and p.stat().st_size == 0
    assert is_complete_artifact(p) is False


def test_returns_true_for_non_empty_file(tmp_path: Path) -> None:
    p = tmp_path / "ok.mp4"
    p.write_bytes(b"\x00\x00\x00\x18ftyp")
    assert is_complete_artifact(p) is True


def test_swallows_oserror_on_unreadable_path(tmp_path: Path) -> None:
    """If statting the path raises OSError (broken symlink, permission
    denied, etc.) the helper returns False rather than propagating."""
    # Create a dangling symlink — stat() raises FileNotFoundError on it.
    src = tmp_path / "real"
    link = tmp_path / "broken_link"
    link.symlink_to(src)  # src never gets created
    assert is_complete_artifact(link) is False
