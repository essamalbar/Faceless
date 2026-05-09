"""Test that the --user-id CLI argument routes runs into per-user directories."""
from __future__ import annotations

import argparse
from pathlib import Path

from run import _make_run_dir, _resolve_run_dir


def test_make_run_dir_defaults_to_admin(tmp_path: Path):
    run_dir = _make_run_dir(tmp_path)
    assert run_dir.parent.name == "admin"
    assert run_dir.parent.parent == tmp_path


def test_make_run_dir_uses_explicit_user_id(tmp_path: Path):
    run_dir = _make_run_dir(tmp_path, user_id="alice-uuid-123")
    assert run_dir.parent.name == "alice-uuid-123"
    assert run_dir.parent.parent == tmp_path


def test_resolve_run_dir_falls_through_to_user_dir(tmp_path: Path):
    args = argparse.Namespace(
        resume=None,
        run_dir=None,
        user_id="bob-uuid-456",
    )
    rd = _resolve_run_dir(args, tmp_path)
    assert rd.parent.name == "bob-uuid-456"


def test_resolve_run_dir_explicit_run_dir_wins(tmp_path: Path):
    """If --run-dir is given (e.g., when the API spawns run.py), it overrides
    the user_id fallback. This is how the API gets per-user paths today."""
    explicit = tmp_path / "out" / "alice" / "2026-05-10-1234"
    explicit.mkdir(parents=True)
    args = argparse.Namespace(
        resume=None,
        run_dir=str(explicit),
        user_id="bob",  # ignored when run_dir is set
    )
    rd = _resolve_run_dir(args, tmp_path / "out")
    assert rd == explicit.resolve()
