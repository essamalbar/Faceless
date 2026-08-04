from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import run


def test_effective_user_id_recovers_uuid_from_path(tmp_path):
    out = tmp_path / "out"
    rd = out / "abc-123-uuid" / "2026-08-04-1200"
    assert run._effective_user_id(rd, out) == "abc-123-uuid"


def test_effective_user_id_admin_stays_service(tmp_path):
    out = tmp_path / "out"
    rd = out / "admin" / "2026-08-04-1200"
    assert run._effective_user_id(rd, out) == "admin"


def test_effective_user_id_unexpected_layout_falls_back_to_admin(tmp_path):
    # run_dir not under out_root → ValueError → safe 'admin' (free) fallback
    assert run._effective_user_id(tmp_path / "x" / "y", tmp_path / "other") == "admin"


def test_effective_user_id_run_dir_equals_out_root_falls_back_to_admin(tmp_path):
    # run_dir == out_root → relative_to() succeeds with empty parts → IndexError
    # → safe 'admin' fallback.
    out = tmp_path / "out"
    out.mkdir()
    assert run._effective_user_id(out, out) == "admin"


def test_effective_user_id_deeper_nesting_recovers_top_segment(tmp_path):
    # Locks in parts[0] (top segment = owning user), not parts[-1].
    out = tmp_path / "out"
    rd = out / "uuid-1" / "extra" / "2026-08-04-1200"
    assert run._effective_user_id(rd, out) == "uuid-1"


def test_out_root_follows_faceless_out_root_env(monkeypatch, tmp_path):
    # Regression for the Cloud Run leak: with no --out-root, out_root must
    # follow $FACELESS_OUT_ROOT (what pipeline/api.py's _out_root() reads,
    # and what Cloud Run sets to /mnt/runs) — not the hardcoded local default.
    # Old code (`Path(args.out_root)` with a hardcoded argparse default)
    # would fail this: it always resolved to the local out/ dir regardless
    # of the env var, so a resumed <FACELESS_OUT_ROOT>/<uuid>/<run> dir never
    # matched out_root and _effective_user_id fell back to 'admin'.
    env_root = tmp_path / "mnt" / "runs"
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(env_root))
    ns = SimpleNamespace(out_root=None)
    assert run._resolve_out_root(ns) == env_root


def test_out_root_explicit_flag_overrides_env(monkeypatch, tmp_path):
    # An explicit --out-root must still win (tests like test_run_shorts_smoke.py
    # rely on this to sandbox runs under tmp_path).
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path / "mnt" / "runs"))
    explicit = tmp_path / "explicit-out"
    ns = SimpleNamespace(out_root=str(explicit))
    assert run._resolve_out_root(ns) == explicit
