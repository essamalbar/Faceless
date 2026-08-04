from __future__ import annotations

from pathlib import Path

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
