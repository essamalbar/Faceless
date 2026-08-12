"""Scale-hardening guards: global approval rate cap (Fix 2) and the
fail-closed cloud spawn backend (Fix 3).

Fix 1 (refund on spawn failure) is covered in tests/test_song_api.py where
the song approve/reroll fixtures already live.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException


# ---------------------------------------------------------------------------
# Fix 2 — global approval rate cap
# ---------------------------------------------------------------------------


def test_global_approval_rate_off_by_default(monkeypatch):
    """Env unset → no-op, and the DB is never even consulted."""
    monkeypatch.delenv("FACELESS_GLOBAL_APPROVALS_PER_MIN", raising=False)
    from pipeline import api as api_mod, db

    calls: list = []
    monkeypatch.setattr(db, "count_rate_events",
                        lambda *a, **k: calls.append(("count", a)) or 999)
    monkeypatch.setattr(db, "record_rate_event",
                        lambda *a, **k: calls.append(("record", a)))

    api_mod._enforce_global_approval_rate()  # must not raise
    assert calls == []  # limit<=0 short-circuits before touching the DB


def test_global_approval_rate_ignores_invalid_env(monkeypatch):
    """A non-integer env value is treated as OFF, not a crash."""
    monkeypatch.setenv("FACELESS_GLOBAL_APPROVALS_PER_MIN", "not-a-number")
    from pipeline import api as api_mod, db

    monkeypatch.setattr(db, "count_rate_events", lambda *a, **k: 999)
    api_mod._enforce_global_approval_rate()  # must not raise


def test_global_approval_rate_blocks_over_limit(monkeypatch):
    monkeypatch.setenv("FACELESS_GLOBAL_APPROVALS_PER_MIN", "1")
    from pipeline import api as api_mod, db

    seen: dict = {}

    def fake_count(user_id, action, within):
        seen.update(user_id=user_id, action=action, within=within)
        return 1  # >= limit

    recorded: list = []
    monkeypatch.setattr(db, "count_rate_events", fake_count)
    monkeypatch.setattr(db, "record_rate_event",
                        lambda *a, **k: recorded.append(a))

    with pytest.raises(HTTPException) as ei:
        api_mod._enforce_global_approval_rate()
    assert ei.value.status_code == 429

    # Consulted the DB with the fixed sentinel UID (uuid column), not "__global__".
    assert seen["user_id"] == api_mod._GLOBAL_RATE_UID
    assert seen["action"] == "song_approve"
    assert seen["within"] == 60
    # Blocked path must NOT record a new event.
    assert recorded == []


def test_global_approval_rate_records_when_under_limit(monkeypatch):
    monkeypatch.setenv("FACELESS_GLOBAL_APPROVALS_PER_MIN", "5")
    from pipeline import api as api_mod, db

    monkeypatch.setattr(db, "count_rate_events", lambda *a, **k: 0)
    recorded: list = []
    monkeypatch.setattr(
        db, "record_rate_event",
        lambda user_id, action: recorded.append((user_id, action)),
    )

    api_mod._enforce_global_approval_rate()  # under limit → no raise
    assert recorded == [(api_mod._GLOBAL_RATE_UID, "song_approve")]


def test_global_approval_rate_survives_db_read_failure(monkeypatch):
    """A telemetry read failure must never block the paid flow."""
    monkeypatch.setenv("FACELESS_GLOBAL_APPROVALS_PER_MIN", "1")
    from pipeline import api as api_mod, db

    def boom(*a, **k):
        raise RuntimeError("supabase down")

    monkeypatch.setattr(db, "count_rate_events", boom)
    monkeypatch.setattr(db, "record_rate_event", lambda *a, **k: None)
    api_mod._enforce_global_approval_rate()  # must not raise


def test_global_rate_sentinel_is_valid_uuid():
    from pipeline import api as api_mod

    # Parses as a uuid → safe for the rate_events.user_id uuid column.
    assert str(uuid.UUID(api_mod._GLOBAL_RATE_UID)) == api_mod._GLOBAL_RATE_UID


# ---------------------------------------------------------------------------
# Fix 3 — fail-closed spawn backend on Cloud Run
# ---------------------------------------------------------------------------


def test_select_backend_fails_closed_on_cloud_run_when_unset(monkeypatch):
    """Unset backend + K_SERVICE (Cloud Run) → refuse to run every render
    inside the API container."""
    monkeypatch.delenv("FACELESS_SPAWN_BACKEND", raising=False)
    monkeypatch.setenv("K_SERVICE", "faceless-api")
    from pipeline.spawn_backends import select_backend

    with pytest.raises(RuntimeError) as ei:
        select_backend()
    assert "FACELESS_SPAWN_BACKEND" in str(ei.value)
    assert "cloudrun_jobs" in str(ei.value)


def test_select_backend_local_default_off_cloud_run(monkeypatch):
    """Unset backend + no K_SERVICE (local dev) → unchanged local default."""
    monkeypatch.delenv("FACELESS_SPAWN_BACKEND", raising=False)
    monkeypatch.delenv("K_SERVICE", raising=False)
    from pipeline.spawn_backends import select_backend, LocalSubprocessBackend

    assert isinstance(select_backend(), LocalSubprocessBackend)


def test_select_backend_cloudrun_jobs_regardless_of_k_service(monkeypatch):
    """Explicit cloudrun_jobs → jobs backend even with K_SERVICE set."""
    monkeypatch.setenv("K_SERVICE", "faceless-api")
    monkeypatch.setenv("FACELESS_SPAWN_BACKEND", "cloudrun_jobs")
    monkeypatch.setenv("FACELESS_CLOUD_RUN_JOB_NAME", "faceless-pipeline")
    monkeypatch.setenv("FACELESS_CLOUD_RUN_REGION", "us-central1")
    monkeypatch.setenv("FACELESS_GCP_PROJECT", "test-project")
    from pipeline.spawn_backends import select_backend, CloudRunJobsBackend

    assert isinstance(select_backend(), CloudRunJobsBackend)
