from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from pipeline.api import (
    _cancel_run_impl,
    _cancel_song_impl,
    _delete_run_impl,
    _delete_song_impl,
)


def test_impls_importable():
    for fn in (_cancel_run_impl, _cancel_song_impl,
               _delete_run_impl, _delete_song_impl):
        assert callable(fn)


# ---------------------------------------------------------------------------
# Super-admin dashboard — service-token-gated cross-user READ endpoints.
#
# Auth pattern (mirrors tests/test_api.py + conftest.client_factory):
#   * service token  → client_factory(user_id="admin", role="service")
#   * normal user    → client_factory(user_id="alice", role="user")
# client_factory installs an app.dependency_overrides[require_user] so the
# endpoints see exactly the role we pass — no real Supabase JWT needed. We
# never touch the env-token `client` fixture here: while the override is
# active a header-less request would fall back to role="user" and 403.
#
# The pipeline.db functions are monkeypatched (handlers do a request-time
# `from pipeline import db`), and pipeline.api._out_root is redirected to a
# tmp dir wherever an endpoint walks the filesystem — so NO real DB / real
# out/ is ever hit.
# ---------------------------------------------------------------------------


def _write_run(user_dir: Path, run_id: str, **state) -> Path:
    """Create out-root/<user>/<run>/api_state.json — the minimal file set
    _summarize/derive_status need without raising."""
    rd = user_dir / run_id
    rd.mkdir(parents=True, exist_ok=True)
    (rd / "api_state.json").write_text(
        json.dumps({"created_at": "2026-08-10T00:00:00+00:00", **state}),
        encoding="utf-8",
    )
    return rd


# --- /admin/overview -------------------------------------------------------

def test_overview_requires_service(client_factory):
    c = client_factory(user_id="alice", role="user")
    assert c.get("/admin/overview").status_code == 403


def test_overview_service_ok(client_factory, monkeypatch, tmp_path):
    out = tmp_path / "out"
    (out / "user-a").mkdir(parents=True)
    (out / "user-b").mkdir(parents=True)
    monkeypatch.setattr("pipeline.api._out_root", lambda: out)
    monkeypatch.setattr(
        "pipeline.db.probe_activation",
        lambda: {"payment_status": True, "rate_events": True},
    )
    c = client_factory(user_id="admin", role="service")
    r = c.get("/admin/overview")
    assert r.status_code == 200
    body = r.json()
    assert set(body) >= {"health", "counts", "activation"}
    assert body["counts"]["user_dirs"] == 2
    assert body["activation"]["payment_status"] is True
    assert "unprobed" in body["activation"]
    assert "writer_tier" in body["health"]


def test_overview_activation_error_branch(client_factory, monkeypatch, tmp_path):
    out = tmp_path / "out"
    out.mkdir(parents=True)
    monkeypatch.setattr("pipeline.api._out_root", lambda: out)

    def _boom():
        raise RuntimeError("supabase down")

    monkeypatch.setattr("pipeline.db.probe_activation", _boom)
    c = client_factory(user_id="admin", role="service")
    r = c.get("/admin/overview")
    assert r.status_code == 200
    assert "error" in r.json()["activation"]


# --- /admin/users ----------------------------------------------------------

def test_users_requires_service(client_factory):
    c = client_factory(user_id="alice", role="user")
    assert c.get("/admin/users").status_code == 403


def test_users_service_merges(client_factory, monkeypatch):
    from pipeline.db import UserProfile

    profiles = [
        UserProfile(
            id="u1", stripe_customer_id=None, current_plan="pro",
            current_period_end=None, payment_status="active",
            tos_accepted_version="2026-08-05",
        ),
        UserProfile(
            id="u2", stripe_customer_id=None, current_plan="free",
            current_period_end=None, payment_status="past_due",
            tos_accepted_version=None,
        ),
    ]
    monkeypatch.setattr(
        "pipeline.db.list_user_profiles", lambda limit, offset: profiles)
    monkeypatch.setattr(
        "pipeline.db.list_balances", lambda: {"u1": 42})
    monkeypatch.setattr(
        "pipeline.db.list_auth_users", lambda: {"u1": "a@x.com", "u2": "b@x.com"})

    c = client_factory(user_id="admin", role="service")
    r = c.get("/admin/users")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 2
    by_id = {row["id"]: row for row in rows}
    assert by_id["u1"]["email"] == "a@x.com"
    assert by_id["u1"]["balance"] == 42
    assert by_id["u1"]["plan"] == "pro"
    assert by_id["u1"]["payment_status"] == "active"
    assert by_id["u1"]["tos_accepted_version"] == "2026-08-05"
    # u2 has no balance row → default 0.
    assert by_id["u2"]["balance"] == 0
    assert by_id["u2"]["email"] == "b@x.com"


def test_users_limit_clamped(client_factory, monkeypatch):
    seen: dict[str, int] = {}

    def _fake(limit, offset):
        seen["limit"] = limit
        seen["offset"] = offset
        return []

    monkeypatch.setattr("pipeline.db.list_user_profiles", _fake)
    monkeypatch.setattr("pipeline.db.list_balances", lambda: {})
    monkeypatch.setattr("pipeline.db.list_auth_users", lambda: {})

    c = client_factory(user_id="admin", role="service")
    r = c.get("/admin/users", params={"limit": 9999, "offset": -5})
    assert r.status_code == 200
    assert seen["limit"] == 200      # clamped to max
    assert seen["offset"] == 0       # clamped to >= 0


# --- /admin/runs -----------------------------------------------------------

def test_runs_requires_service(client_factory, monkeypatch, tmp_path):
    out = tmp_path / "out"
    out.mkdir(parents=True)
    monkeypatch.setattr("pipeline.api._out_root", lambda: out)
    c = client_factory(user_id="alice", role="user")
    assert c.get("/admin/runs").status_code == 403


def test_runs_lists_all_users_tagged(client_factory, monkeypatch, tmp_path):
    out = tmp_path / "out"
    _write_run(out / "user-a", "run-a1")
    _write_run(out / "user-b", "run-b1")
    monkeypatch.setattr("pipeline.api._out_root", lambda: out)

    c = client_factory(user_id="admin", role="service")
    r = c.get("/admin/runs")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 2
    tagged = {(row["user_id"], row["id"]) for row in rows}
    assert tagged == {("user-a", "run-a1"), ("user-b", "run-b1")}


def test_runs_limit_one(client_factory, monkeypatch, tmp_path):
    out = tmp_path / "out"
    _write_run(out / "user-a", "run-a1")
    _write_run(out / "user-b", "run-b1")
    monkeypatch.setattr("pipeline.api._out_root", lambda: out)

    c = client_factory(user_id="admin", role="service")
    r = c.get("/admin/runs", params={"limit": 1})
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_runs_filter_by_user(client_factory, monkeypatch, tmp_path):
    out = tmp_path / "out"
    _write_run(out / "user-a", "run-a1")
    _write_run(out / "user-b", "run-b1")
    monkeypatch.setattr("pipeline.api._out_root", lambda: out)

    c = client_factory(user_id="admin", role="service")
    r = c.get("/admin/runs", params={"user_id": "user-a"})
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["user_id"] == "user-a"


def test_runs_traversal_user_id(client_factory, monkeypatch, tmp_path):
    out = tmp_path / "out"
    out.mkdir(parents=True)
    monkeypatch.setattr("pipeline.api._out_root", lambda: out)
    c = client_factory(user_id="admin", role="service")
    r = c.get("/admin/runs", params={"user_id": "../x"})
    assert r.status_code == 400


# --- /admin/transactions ---------------------------------------------------

def test_transactions_requires_service(client_factory):
    c = client_factory(user_id="alice", role="user")
    assert c.get("/admin/transactions").status_code == 403


def test_transactions_all(client_factory, monkeypatch):
    from pipeline.db import Transaction

    txns = [
        Transaction(
            id="t1", user_id="u1", amount=-8, kind="veo_spend",
            reference_id="run-1", description="a render",
            created_at="2026-08-10T00:00:00+00:00",
        ),
    ]
    monkeypatch.setattr("pipeline.db.list_transactions_all", lambda limit: txns)

    c = client_factory(user_id="admin", role="service")
    r = c.get("/admin/transactions")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["id"] == "t1"
    assert rows[0]["user_id"] == "u1"
    assert rows[0]["amount"] == -8
    assert rows[0]["kind"] == "veo_spend"


def test_transactions_by_user_calls_scoped(client_factory, monkeypatch):
    from pipeline.db import Transaction

    seen: dict[str, object] = {}

    def _fake(user_id, limit):
        seen["user_id"] = user_id
        seen["limit"] = limit
        return [
            Transaction(
                id="t9", user_id=user_id, amount=5, kind="admin_credit",
                reference_id=None, description="x",
                created_at="2026-08-10T00:00:00+00:00",
            ),
        ]

    monkeypatch.setattr("pipeline.db.list_transactions", _fake)
    # This should NOT be called on the scoped path.
    monkeypatch.setattr(
        "pipeline.db.list_transactions_all",
        lambda limit: (_ for _ in ()).throw(AssertionError("wrong path")),
    )

    c = client_factory(user_id="admin", role="service")
    r = c.get("/admin/transactions", params={"user_id": "u1", "limit": 5})
    assert r.status_code == 200
    assert seen["user_id"] == "u1"
    assert seen["limit"] == 5
    assert r.json()[0]["id"] == "t9"


# --- _admin_target_user helper --------------------------------------------

def test_admin_target_user_traversal():
    from pipeline.api import _admin_target_user

    with pytest.raises(HTTPException) as exc:
        _admin_target_user("../etc")
    assert exc.value.status_code == 400


def test_admin_target_user_valid():
    from pipeline.api import _admin_target_user

    u = _admin_target_user("abc-123")
    assert u.id == "abc-123"
    assert u.role == "user"


# --- admin_re_assemble_song traversal fix ---------------------------------

def test_re_assemble_song_traversal_user_id():
    from pipeline.api import admin_re_assemble_song
    from pipeline.auth import User

    svc = User(id="admin", email=None, role="service")
    with pytest.raises(HTTPException) as exc:
        admin_re_assemble_song(user_id="../x", run_id="r", user=svc)
    assert exc.value.status_code == 400


# ---------------------------------------------------------------------------
# Super-admin dashboard — service-token-gated cross-user WRITE endpoints.
#
# The load-bearing property: an admin cancel must refund the TARGET user's
# ledger, never the service caller's. _admin_target_user wraps the path
# user_id as a role="user" User, and the *_impl functions pass that user
# straight into refund_run_charges — so the spy must observe a User whose
# .id == the path user_id and .role == "user" (NOT "service"/"admin").
#
# refund_run_charges is imported INSIDE the impls (`from pipeline.credits
# import refund_run_charges`), which re-binds from the module at call time,
# so monkeypatching "pipeline.credits.refund_run_charges" reaches it.
# ---------------------------------------------------------------------------


def _refund_spy():
    """Returns (spy, calls) — spy matches refund_run_charges' real signature
    (user positional, run_id/reason keyword-only, returns an int the impls
    interpolate) and records the User it was handed."""
    calls: list = []

    def spy(user, *, run_id, reason):
        calls.append(user)
        return 0

    return spy, calls


# --- POST /admin/runs/{uid}/{rid}/cancel -----------------------------------

def test_admin_cancel_run_requires_service(client_factory):
    c = client_factory(user_id="alice", role="user")
    assert c.post("/admin/runs/target/run-x/cancel").status_code == 403


def test_admin_cancel_run_refunds_target_user(client_factory, monkeypatch, tmp_path):
    out = tmp_path / "out"
    # Target user's run dir — no final.mp4 (not complete), no pid (not alive).
    _write_run(out / "target-user", "run-x")
    monkeypatch.setattr("pipeline.api._out_root", lambda: out)

    spy, calls = _refund_spy()
    monkeypatch.setattr("pipeline.credits.refund_run_charges", spy)

    c = client_factory(user_id="admin", role="service")
    r = c.post("/admin/runs/target-user/run-x/cancel")
    assert r.status_code == 200
    assert r.json()["run_id"] == "run-x"
    # THE critical assertion: refund landed on the TARGET user, role="user".
    assert len(calls) == 1
    assert calls[0].id == "target-user"
    assert calls[0].role == "user"


def test_admin_cancel_run_traversal_user_id():
    from pipeline.api import admin_cancel_run
    from pipeline.auth import User

    svc = User(id="admin", email=None, role="service")
    with pytest.raises(HTTPException) as exc:
        admin_cancel_run(user_id="../evil", run_id="r", user=svc)
    assert exc.value.status_code == 400


# --- POST /admin/songs/{uid}/{rid}/cancel ----------------------------------

def test_admin_cancel_song_requires_service(client_factory):
    c = client_factory(user_id="alice", role="user")
    assert c.post("/admin/songs/target/run-x/cancel").status_code == 403


def test_admin_cancel_song_refunds_target_user(client_factory, monkeypatch, tmp_path):
    out = tmp_path / "out"
    # A song run that isn't complete and has no live worker.
    _write_run(out / "target-user", "run-s", kind="song", status="awaiting_approval")
    monkeypatch.setattr("pipeline.api._out_root", lambda: out)

    spy, calls = _refund_spy()
    monkeypatch.setattr("pipeline.credits.refund_run_charges", spy)

    c = client_factory(user_id="admin", role="service")
    r = c.post("/admin/songs/target-user/run-s/cancel")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    # Same load-bearing property for songs.
    assert len(calls) == 1
    assert calls[0].id == "target-user"
    assert calls[0].role == "user"


def test_admin_cancel_song_traversal_user_id():
    from pipeline.api import admin_cancel_song
    from pipeline.auth import User

    svc = User(id="admin", email=None, role="service")
    with pytest.raises(HTTPException) as exc:
        admin_cancel_song(user_id="../evil", run_id="r", user=svc)
    assert exc.value.status_code == 400


# --- DELETE /admin/runs/{uid}/{rid} ----------------------------------------

def test_admin_delete_run_requires_service(client_factory):
    c = client_factory(user_id="alice", role="user")
    assert c.delete("/admin/runs/target/run-x").status_code == 403


def test_admin_delete_run_removes_target_dir(client_factory, monkeypatch, tmp_path):
    out = tmp_path / "out"
    rd = _write_run(out / "target-user", "run-x")  # no pid → not alive
    monkeypatch.setattr("pipeline.api._out_root", lambda: out)

    # Light ledger check: delete must NEVER touch the credit ledger. Patch
    # refund with a spy that must stay untouched.
    spy, calls = _refund_spy()
    monkeypatch.setattr("pipeline.credits.refund_run_charges", spy)

    assert rd.exists()
    c = client_factory(user_id="admin", role="service")
    r = c.delete("/admin/runs/target-user/run-x")
    assert r.status_code == 200
    assert r.json()["deleted"] is True
    assert not rd.exists()
    # Delete does no refund / ledger mutation.
    assert calls == []


def test_admin_delete_run_traversal_user_id():
    from pipeline.api import admin_delete_run
    from pipeline.auth import User

    svc = User(id="admin", email=None, role="service")
    with pytest.raises(HTTPException) as exc:
        admin_delete_run(user_id="../evil", run_id="r", user=svc)
    assert exc.value.status_code == 400


# --- DELETE /admin/songs/{uid}/{rid} ---------------------------------------

def test_admin_delete_song_requires_service(client_factory):
    c = client_factory(user_id="alice", role="user")
    assert c.delete("/admin/songs/target/run-s").status_code == 403


def test_admin_delete_song_removes_target_dir(client_factory, monkeypatch, tmp_path):
    out = tmp_path / "out"
    # Song run in a terminal (non-active) status so delete is allowed.
    rd = _write_run(out / "target-user", "run-s", kind="song", status="failed")
    monkeypatch.setattr("pipeline.api._out_root", lambda: out)

    assert rd.exists()
    c = client_factory(user_id="admin", role="service")
    r = c.delete("/admin/songs/target-user/run-s")
    assert r.status_code == 204
    assert not rd.exists()


def test_admin_delete_song_traversal_user_id():
    from pipeline.api import admin_delete_song
    from pipeline.auth import User

    svc = User(id="admin", email=None, role="service")
    with pytest.raises(HTTPException) as exc:
        admin_delete_song(user_id="../evil", run_id="r", user=svc)
    assert exc.value.status_code == 400
