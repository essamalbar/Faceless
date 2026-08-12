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


def test_users_missing_columns_returns_503_hint(client_factory, monkeypatch):
    """Before the pending migrations, user_profiles lacks payment_status /
    tos_accepted_version, so the SELECT errors. The endpoint must surface an
    actionable 503 pointing to the migration bundle, not an opaque 500."""
    def _boom(limit, offset):
        raise Exception('column user_profiles.payment_status does not exist')

    monkeypatch.setattr("pipeline.db.list_user_profiles", _boom)
    monkeypatch.setattr("pipeline.db.list_balances", lambda: {})
    monkeypatch.setattr("pipeline.db.list_auth_users", lambda: {})

    c = client_factory(user_id="admin", role="service")
    r = c.get("/admin/users")
    assert r.status_code == 503
    assert "APPLY-MIGRATIONS.sql" in r.json()["detail"]


def test_users_unrelated_error_still_raises(client_factory, monkeypatch):
    """A non-schema error must NOT be masked as a migration hint — it
    propagates (the global handler turns it into a 500 in prod), rather than
    being mislabeled as 'apply migrations'."""
    import pytest

    def _boom(limit, offset):
        raise Exception('connection reset by peer')

    monkeypatch.setattr("pipeline.db.list_user_profiles", _boom)
    monkeypatch.setattr("pipeline.db.list_balances", lambda: {})
    monkeypatch.setattr("pipeline.db.list_auth_users", lambda: {})

    c = client_factory(user_id="admin", role="service")
    # TestClient re-raises server exceptions; the point is it is NOT converted
    # to the 503 migration hint.
    with pytest.raises(Exception, match="connection reset by peer"):
        c.get("/admin/users")


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


# ---------------------------------------------------------------------------
# GET /admin — the self-contained dashboard shell.
#
# The HTML page is a static, service-token-driven operator console. The shell
# itself needs no auth (the token is entered in-browser and attached to every
# /admin/* fetch), so a plain unauthenticated GET must return the document.
# ---------------------------------------------------------------------------

def test_admin_dashboard_page_served(client_factory):
    c = client_factory(user_id="alice", role="user")
    r = c.get("/admin")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    body = r.text
    for needle in (
        # New email/password control-panel markers.
        "Control Panel",
        "Sign in",
        "Sign out",
        'type="password"',
        "/admin/login",
        "sessionStorage",
        # The page still drives the data endpoints.
        "/admin/overview",
        "/admin/users",
        "/admin/runs",
        "/admin/transactions",
        # New analytics cards + song audio player.
        "/admin/kpis",
        "/admin/subscriptions",
        "/admin/revenue",
        "/admin/songs/",
        "Listen",
        "createObjectURL",
    ):
        assert needle in body


# ---------------------------------------------------------------------------
# Email/password admin login + FACELESS_ADMIN_EMAILS allowlist gate.
#
# The control panel is now reachable by the service token (CLI/cron) OR by a
# logged-in user whose email is in FACELESS_ADMIN_EMAILS. _is_admin/_require_admin
# encode the gate; /admin/login exchanges email+password for a Supabase session
# but only for allowlisted addresses.
# ---------------------------------------------------------------------------


def test_is_admin_service_user_always_allowed(monkeypatch):
    from pipeline.api import _is_admin
    from pipeline.auth import User

    # Empty allowlist — a service token is admin regardless.
    monkeypatch.delenv("FACELESS_ADMIN_EMAILS", raising=False)
    svc = User(id="admin", email=None, role="service")
    assert _is_admin(svc) is True


def test_is_admin_allowlisted_email(monkeypatch):
    from pipeline.api import _is_admin
    from pipeline.auth import User

    monkeypatch.setenv("FACELESS_ADMIN_EMAILS", "boss@x.com")
    # Case-insensitive + whitespace tolerant.
    u = User(id="u1", email="  BOSS@x.com ", role="user")
    assert _is_admin(u) is True


def test_is_admin_non_allowlisted_email(monkeypatch):
    from pipeline.api import _is_admin
    from pipeline.auth import User

    monkeypatch.setenv("FACELESS_ADMIN_EMAILS", "boss@x.com")
    u = User(id="u2", email="other@x.com", role="user")
    assert _is_admin(u) is False


def test_is_admin_none_email(monkeypatch):
    from pipeline.api import _is_admin
    from pipeline.auth import User

    monkeypatch.setenv("FACELESS_ADMIN_EMAILS", "boss@x.com")
    u = User(id="u3", email=None, role="user")
    assert _is_admin(u) is False


def test_require_admin_raises_403_for_non_admin(monkeypatch):
    from pipeline.api import _require_admin
    from pipeline.auth import User

    monkeypatch.setenv("FACELESS_ADMIN_EMAILS", "boss@x.com")
    with pytest.raises(HTTPException) as exc:
        _require_admin(User(id="u", email="other@x.com", role="user"))
    assert exc.value.status_code == 403


def test_require_admin_allows_service_and_allowlisted(monkeypatch):
    from pipeline.api import _require_admin
    from pipeline.auth import User

    monkeypatch.setenv("FACELESS_ADMIN_EMAILS", "boss@x.com")
    # Neither call raises.
    _require_admin(User(id="admin", email=None, role="service"))
    _require_admin(User(id="u", email="boss@x.com", role="user"))


# --- /admin/overview through the allowlist ---------------------------------

def _overview_env(monkeypatch, tmp_path):
    out = tmp_path / "out"
    (out / "user-a").mkdir(parents=True)
    monkeypatch.setattr("pipeline.api._out_root", lambda: out)
    monkeypatch.setattr(
        "pipeline.db.probe_activation",
        lambda: {"payment_status": True, "rate_events": True},
    )


def test_overview_allowlisted_jwt_user_ok(client_factory, monkeypatch, tmp_path):
    _overview_env(monkeypatch, tmp_path)
    monkeypatch.setenv("FACELESS_ADMIN_EMAILS", "boss@x.com")
    c = client_factory(user_id="boss", role="user", email="boss@x.com")
    assert c.get("/admin/overview").status_code == 200


def test_overview_non_allowlisted_jwt_user_403(client_factory, monkeypatch, tmp_path):
    _overview_env(monkeypatch, tmp_path)
    monkeypatch.setenv("FACELESS_ADMIN_EMAILS", "boss@x.com")
    c = client_factory(user_id="eve", role="user", email="eve@x.com")
    assert c.get("/admin/overview").status_code == 403


def test_overview_service_token_still_ok(client_factory, monkeypatch, tmp_path):
    _overview_env(monkeypatch, tmp_path)
    # Empty allowlist — service token still gets in (backward compat).
    monkeypatch.delenv("FACELESS_ADMIN_EMAILS", raising=False)
    c = client_factory(user_id="admin", role="service")
    assert c.get("/admin/overview").status_code == 200


# --- POST /admin/login -----------------------------------------------------

def test_admin_login_success(client_factory, monkeypatch):
    monkeypatch.setenv("FACELESS_ADMIN_EMAILS", "boss@x.com")
    monkeypatch.setattr(
        "pipeline.api._supabase_password_login",
        lambda email, password: {
            "access_token": "jwt123",
            "expires_in": 3600,
            "user": {"email": "boss@x.com"},
        },
    )
    c = client_factory(user_id="alice", role="user")
    r = c.post("/admin/login", json={"email": "boss@x.com", "password": "x"})
    assert r.status_code == 200
    body = r.json()
    assert body["access_token"] == "jwt123"
    assert body["email"] == "boss@x.com"
    assert body["expires_in"] == 3600


def test_admin_login_non_allowlisted_email_403_no_network(client_factory, monkeypatch):
    monkeypatch.setenv("FACELESS_ADMIN_EMAILS", "boss@x.com")

    def _must_not_call(email, password):
        raise AssertionError("password login must not run for a non-admin email")

    monkeypatch.setattr("pipeline.api._supabase_password_login", _must_not_call)
    c = client_factory(user_id="alice", role="user")
    r = c.post("/admin/login", json={"email": "nobody@x.com", "password": "x"})
    assert r.status_code == 403


def test_admin_login_bad_credentials_401(client_factory, monkeypatch):
    monkeypatch.setenv("FACELESS_ADMIN_EMAILS", "boss@x.com")

    def _boom(email, password):
        raise RuntimeError("login failed: 400")

    monkeypatch.setattr("pipeline.api._supabase_password_login", _boom)
    c = client_factory(user_id="alice", role="user")
    r = c.post("/admin/login", json={"email": "boss@x.com", "password": "wrong"})
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Admin analytics — subscriptions / revenue / kpis (control-panel cards).
#
# All three are gated by _require_admin (service token OR FACELESS_ADMIN_EMAILS
# allowlisted JWT). The positive paths below exercise the allowlisted-JWT
# flavor the task specifies; non-admin (role="user", no email) → 403. The
# pipeline.db aggregation calls are monkeypatched (handlers do a request-time
# `from pipeline import db`), and _plan_price_usd is monkeypatched so no
# Stripe / real DB is ever hit.
# ---------------------------------------------------------------------------


# --- GET /admin/subscriptions ----------------------------------------------

def test_subscriptions_requires_admin(client_factory):
    c = client_factory(user_id="alice", role="user")
    assert c.get("/admin/subscriptions").status_code == 403


def test_subscriptions_counts(client_factory, monkeypatch):
    monkeypatch.setenv("FACELESS_ADMIN_EMAILS", "boss@x.com")
    # 2 pro active, 1 creator active, 1 pro past_due, 1 free active; one pro
    # flagged cancel_at_period_end.
    profiles = [
        {"id": "u1", "current_plan": "pro", "payment_status": "active",
         "cancel_at_period_end": False},
        {"id": "u2", "current_plan": "pro", "payment_status": "active",
         "cancel_at_period_end": True},
        {"id": "u3", "current_plan": "creator", "payment_status": "active",
         "cancel_at_period_end": False},
        {"id": "u4", "current_plan": "pro", "payment_status": "past_due",
         "cancel_at_period_end": False},
        {"id": "u5", "current_plan": "free", "payment_status": "active",
         "cancel_at_period_end": False},
    ]
    monkeypatch.setattr("pipeline.db.list_all_user_profiles_min", lambda: profiles)

    c = client_factory(user_id="boss", role="user", email="boss@x.com")
    r = c.get("/admin/subscriptions")
    assert r.status_code == 200
    body = r.json()
    assert body["by_plan"] == {"starter": 0, "creator": 1, "pro": 3,
                               "free": 1, "other": 0}
    assert body["active"] == 4
    assert body["past_due"] == 1
    assert body["cancel_at_period_end"] == 1
    assert body["total_profiles"] == 5


def test_subscriptions_other_and_deleted_bucketing(client_factory, monkeypatch):
    monkeypatch.setenv("FACELESS_ADMIN_EMAILS", "boss@x.com")
    profiles = [
        {"id": "u1", "current_plan": "deleted", "payment_status": "active",
         "cancel_at_period_end": False},        # deleted → free bucket
        {"id": "u2", "current_plan": None, "payment_status": "active",
         "cancel_at_period_end": False},        # None → free bucket
        {"id": "u3", "current_plan": "legacy_gold", "payment_status": "active",
         "cancel_at_period_end": False},        # unknown → other bucket
    ]
    monkeypatch.setattr("pipeline.db.list_all_user_profiles_min", lambda: profiles)

    c = client_factory(user_id="boss", role="user", email="boss@x.com")
    body = c.get("/admin/subscriptions").json()
    assert body["by_plan"]["free"] == 2
    assert body["by_plan"]["other"] == 1


def test_subscriptions_missing_columns_returns_503_hint(client_factory, monkeypatch):
    """Before the pending migrations, user_profiles lacks payment_status, so the
    aggregate SELECT errors. Surface a 503 pointing at the migration bundle, not
    an opaque 500 (mirrors /admin/users)."""
    monkeypatch.setenv("FACELESS_ADMIN_EMAILS", "boss@x.com")

    def _boom():
        raise Exception('column user_profiles.payment_status does not exist')

    monkeypatch.setattr("pipeline.db.list_all_user_profiles_min", _boom)
    c = client_factory(user_id="boss", role="user", email="boss@x.com")
    r = c.get("/admin/subscriptions")
    assert r.status_code == 503
    assert "APPLY-MIGRATIONS.sql" in r.json()["detail"]


# --- GET /admin/revenue ----------------------------------------------------

def test_revenue_requires_admin(client_factory):
    c = client_factory(user_id="alice", role="user")
    assert c.get("/admin/revenue").status_code == 403


def test_revenue_aggregates(client_factory, monkeypatch):
    from datetime import datetime, timezone

    from pipeline.db import Transaction

    # All renewals dated TODAY (UTC) so revenue_usd_mtd == revenue_usd_total
    # and by_day collapses to one deterministic bucket — independent of the
    # machine clock.
    now_iso = datetime.now(timezone.utc).isoformat()
    rows = [
        Transaction(id="t1", user_id="u1", amount=200, kind="subscription_renewal",
                    reference_id="inv1", description=None, created_at=now_iso),
        Transaction(id="t2", user_id="u2", amount=60, kind="subscription_renewal",
                    reference_id="inv2", description=None, created_at=now_iso),
        Transaction(id="t3", user_id="u3", amount=12, kind="subscription_renewal",
                    reference_id="inv3", description=None, created_at=now_iso),
    ]
    monkeypatch.setattr("pipeline.db.list_transactions_by_kinds",
                        lambda kinds, limit=5000: list(rows))
    monkeypatch.setattr("pipeline.db.list_balances", lambda: {"u1": 100, "u2": 50})
    monkeypatch.setattr("pipeline.api._plan_price_usd",
                        lambda: {"starter": 9.0, "creator": 29.0, "pro": 79.0})

    c = client_factory(user_id="admin", role="service")
    r = c.get("/admin/revenue")
    assert r.status_code == 200
    body = r.json()
    assert body["prices"] == {"starter": 9.0, "creator": 29.0, "pro": 79.0}
    assert body["renewals_by_plan"] == {"starter": 1, "creator": 1, "pro": 1}
    assert body["revenue_usd_total"] == pytest.approx(117.0)   # 79 + 29 + 9
    assert body["revenue_usd_mtd"] == pytest.approx(117.0)     # all dated today
    assert body["credits_granted"] == 272                      # 200 + 60 + 12
    assert body["credits_outstanding"] == 150                  # 100 + 50
    # by_day: exactly one bucket (today), 3 renewals, full revenue.
    assert len(body["by_day"]) == 1
    day = body["by_day"][0]
    assert day["date"] == now_iso[:10]
    assert day["renewals"] == 3
    assert day["revenue_usd"] == pytest.approx(117.0)


def test_revenue_unknown_grant_amount_counts_generic_only(client_factory, monkeypatch):
    from datetime import datetime, timezone

    from pipeline.db import Transaction

    now_iso = datetime.now(timezone.utc).isoformat()
    rows = [
        Transaction(id="t1", user_id="u1", amount=60, kind="subscription_renewal",
                    reference_id="inv1", description=None, created_at=now_iso),
        # Unknown grant amount (e.g. legacy promo): counts in by_day.renewals
        # but not in renewals_by_plan or dollars.
        Transaction(id="t2", user_id="u2", amount=999, kind="subscription_renewal",
                    reference_id="inv2", description=None, created_at=now_iso),
    ]
    monkeypatch.setattr("pipeline.db.list_transactions_by_kinds",
                        lambda kinds, limit=5000: list(rows))
    monkeypatch.setattr("pipeline.db.list_balances", lambda: {})
    monkeypatch.setattr("pipeline.api._plan_price_usd",
                        lambda: {"starter": 9.0, "creator": 29.0, "pro": 79.0})

    c = client_factory(user_id="admin", role="service")
    body = c.get("/admin/revenue").json()
    assert body["renewals_by_plan"] == {"starter": 0, "creator": 1, "pro": 0}
    assert body["revenue_usd_total"] == pytest.approx(29.0)
    assert body["by_day"][0]["renewals"] == 2   # both counted generically
    assert body["credits_outstanding"] == 0


# --- GET /admin/kpis -------------------------------------------------------

def test_kpis_requires_admin(client_factory):
    c = client_factory(user_id="alice", role="user")
    assert c.get("/admin/kpis").status_code == 403


def test_kpis_ok(client_factory, monkeypatch):
    monkeypatch.setattr("pipeline.db.list_auth_users",
                        lambda: {"u1": "a@x.com", "u2": "b@x.com"})
    profiles = [
        {"id": "u1", "current_plan": "pro", "payment_status": "active",
         "cancel_at_period_end": False},
        {"id": "u2", "current_plan": "free", "payment_status": "active",
         "cancel_at_period_end": False},
    ]
    monkeypatch.setattr("pipeline.db.list_all_user_profiles_min", lambda: profiles)
    monkeypatch.setattr("pipeline.db.list_balances", lambda: {"u1": 10, "u2": 5})
    monkeypatch.setattr("pipeline.db.list_transactions_by_kinds",
                        lambda kinds, limit=5000: [])
    monkeypatch.setattr("pipeline.api._plan_price_usd",
                        lambda: {"starter": 9.0, "creator": 29.0, "pro": 79.0})

    c = client_factory(user_id="admin", role="service")
    r = c.get("/admin/kpis")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"total_users", "active_subscribers",
                         "credits_outstanding", "revenue_usd_mtd"}
    assert body["total_users"] == 2
    assert body["active_subscribers"] == 1     # only u1 (paid + active)
    assert body["credits_outstanding"] == 15
    assert body["revenue_usd_mtd"] == pytest.approx(0.0)  # no renewals


def test_kpis_nulls_failed_field(client_factory, monkeypatch):
    """One failing source must not 500 the whole card — the failed field is
    null and the others still populate."""
    def _boom():
        raise RuntimeError("auth admin unavailable")

    monkeypatch.setattr("pipeline.db.list_auth_users", _boom)
    monkeypatch.setattr("pipeline.db.list_all_user_profiles_min", lambda: [])
    monkeypatch.setattr("pipeline.db.list_balances", lambda: {"u1": 7})
    monkeypatch.setattr("pipeline.db.list_transactions_by_kinds",
                        lambda kinds, limit=5000: [])
    monkeypatch.setattr("pipeline.api._plan_price_usd",
                        lambda: {"starter": 9.0, "creator": 29.0, "pro": 79.0})

    c = client_factory(user_id="admin", role="service")
    body = c.get("/admin/kpis").json()
    assert body["total_users"] is None            # failed source → null
    assert body["active_subscribers"] == 0
    assert body["credits_outstanding"] == 7


# --- _plan_price_usd fallback ----------------------------------------------

def test_plan_price_usd_fallback_when_stripe_absent(monkeypatch):
    import pipeline.api as api

    # Reset the module cache and strip every Stripe env var so the retrieve
    # loop short-circuits (empty api_key) — no network, pure fallback.
    monkeypatch.setattr(api, "_PLAN_PRICE_CACHE", {})
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    monkeypatch.delenv("STRIPE_PRICE_STARTER", raising=False)
    monkeypatch.delenv("STRIPE_PRICE_CREATOR", raising=False)
    monkeypatch.delenv("STRIPE_PRICE_PRO", raising=False)

    prices = api._plan_price_usd()
    assert prices == {"starter": 9.0, "creator": 29.0, "pro": 79.0}


# ---------------------------------------------------------------------------
# Admin cross-user media streaming — GET /admin/songs/{uid}/{rid}/audio + cover
#
# The control panel plays any user's song by fetching WITH the bearer header
# (fetch → blob → <audio>). Header auth via require_user is correct; NO
# ?token= query auth (keeps the admin token out of URLs). Both endpoints gate
# on _require_admin first, then validate BOTH path params against _RUN_ID_RE.
#
# Traversal is exercised by calling the handler directly (httpx normalizes
# `../` out of URL paths before the request is sent, so an HTTP traversal test
# would silently hit a normalized 404 path instead of the intended 400 branch).
# The tmp out-root is keyed by the TARGET user_id from the URL path, not the
# caller's id — that's the whole point of a cross-user endpoint.
# ---------------------------------------------------------------------------


# --- GET /admin/songs/{uid}/{rid}/audio ------------------------------------

def test_admin_song_audio_requires_admin(client_factory):
    # Non-allowlisted, role="user", email=None → 403 regardless of env.
    c = client_factory(user_id="alice", role="user")
    assert c.get("/admin/songs/target/run-x/audio").status_code == 403


def test_admin_song_audio_email_admin_ok(client_factory, monkeypatch, tmp_path):
    out = tmp_path / "out"
    rd = out / "target-user" / "run-x"
    rd.mkdir(parents=True)
    data = b"ID3fake-mp3-bytes\x00\x01\x02"
    (rd / "song.mp3").write_bytes(data)
    monkeypatch.setattr("pipeline.api._out_root", lambda: out)
    monkeypatch.setenv("FACELESS_ADMIN_EMAILS", "boss@x.com")

    c = client_factory(user_id="boss", role="user", email="boss@x.com")
    r = c.get("/admin/songs/target-user/run-x/audio")
    assert r.status_code == 200
    assert r.content == data
    assert r.headers["content-type"].startswith("audio/mpeg")


def test_admin_song_audio_service_token_ok(client_factory, monkeypatch, tmp_path):
    out = tmp_path / "out"
    rd = out / "target-user" / "run-x"
    rd.mkdir(parents=True)
    data = b"service-token-can-fetch"
    (rd / "song.mp3").write_bytes(data)
    monkeypatch.setattr("pipeline.api._out_root", lambda: out)

    c = client_factory(user_id="admin", role="service")
    r = c.get("/admin/songs/target-user/run-x/audio")
    assert r.status_code == 200
    assert r.content == data


def test_admin_song_audio_missing_file_404(client_factory, monkeypatch, tmp_path):
    out = tmp_path / "out"
    (out / "target-user" / "run-x").mkdir(parents=True)  # dir exists, no mp3
    monkeypatch.setattr("pipeline.api._out_root", lambda: out)

    c = client_factory(user_id="admin", role="service")
    assert c.get("/admin/songs/target-user/run-x/audio").status_code == 404


def test_admin_song_audio_traversal_user_id():
    from pipeline.api import admin_song_audio
    from pipeline.auth import User

    svc = User(id="admin", email=None, role="service")
    with pytest.raises(HTTPException) as exc:
        admin_song_audio(user_id="../evil", run_id="run-x", user=svc)
    assert exc.value.status_code == 400


def test_admin_song_audio_traversal_run_id():
    from pipeline.api import admin_song_audio
    from pipeline.auth import User

    svc = User(id="admin", email=None, role="service")
    # Valid user_id so the run_id check is the one that fires (#3).
    with pytest.raises(HTTPException) as exc:
        admin_song_audio(user_id="target-user", run_id="../evil", user=svc)
    assert exc.value.status_code == 400


# --- GET /admin/songs/{uid}/{rid}/cover ------------------------------------

def test_admin_song_cover_requires_admin(client_factory):
    c = client_factory(user_id="alice", role="user")
    assert c.get("/admin/songs/target/run-x/cover").status_code == 403


def test_admin_song_cover_png_ok(client_factory, monkeypatch, tmp_path):
    out = tmp_path / "out"
    rd = out / "target-user" / "run-x"
    rd.mkdir(parents=True)
    png = b"\x89PNG\r\n\x1a\nfake"
    (rd / "cover.png").write_bytes(png)
    monkeypatch.setattr("pipeline.api._out_root", lambda: out)

    c = client_factory(user_id="admin", role="service")
    r = c.get("/admin/songs/target-user/run-x/cover")
    assert r.status_code == 200
    assert r.content == png
    assert r.headers["content-type"].startswith("image/png")


def test_admin_song_cover_thumb_fallback(client_factory, monkeypatch, tmp_path):
    out = tmp_path / "out"
    rd = out / "target-user" / "run-x"
    rd.mkdir(parents=True)
    jpg = b"\xff\xd8\xff\xe0fake-jpeg"
    (rd / "cover_thumb.jpg").write_bytes(jpg)  # only the thumb exists
    monkeypatch.setattr("pipeline.api._out_root", lambda: out)

    c = client_factory(user_id="admin", role="service")
    r = c.get("/admin/songs/target-user/run-x/cover")
    assert r.status_code == 200
    assert r.content == jpg
    assert r.headers["content-type"].startswith("image/jpeg")


def test_admin_song_cover_missing_404(client_factory, monkeypatch, tmp_path):
    out = tmp_path / "out"
    (out / "target-user" / "run-x").mkdir(parents=True)  # dir but no cover
    monkeypatch.setattr("pipeline.api._out_root", lambda: out)

    c = client_factory(user_id="admin", role="service")
    assert c.get("/admin/songs/target-user/run-x/cover").status_code == 404


def test_admin_song_cover_traversal_user_id():
    from pipeline.api import admin_song_cover
    from pipeline.auth import User

    svc = User(id="admin", email=None, role="service")
    with pytest.raises(HTTPException) as exc:
        admin_song_cover(user_id="../evil", run_id="run-x", user=svc)
    assert exc.value.status_code == 400


def test_admin_song_cover_traversal_run_id():
    from pipeline.api import admin_song_cover
    from pipeline.auth import User

    svc = User(id="admin", email=None, role="service")
    with pytest.raises(HTTPException) as exc:
        admin_song_cover(user_id="target-user", run_id="../evil", user=svc)
    assert exc.value.status_code == 400
