"""Tier-3 legal blocker: versioned Terms-of-Service acceptance gate.

Covers:
  * `_require_terms_accepted(user)` soft-gate (raises 403 with a machine-
    readable code; service tokens bypass; DB is never queried for them).
  * `POST /account/accept-terms` records the current legal version.
  * A gated generation endpoint (`POST /songs`) 403s before any LLM work
    when the caller has not accepted the current version.
  * `GET /billing/plan` surfaces `terms_current`.

These use the shared `client_factory` fixture (see tests/conftest.py), which
overrides the `require_user` dependency so no auth env is needed. Every DB call
is monkeypatched — tests never touch Supabase.
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Guard unit tests — call the function directly (cleanest).
# ---------------------------------------------------------------------------

def test_require_terms_accepted_raises_when_unaccepted(monkeypatch):
    from fastapi import HTTPException
    from pipeline import api as api_mod
    from pipeline.auth import User
    from pipeline.db import UserProfile
    monkeypatch.setattr(
        "pipeline.db.get_user_profile",
        lambda uid: UserProfile(
            id=uid, stripe_customer_id=None,
            current_plan="free", current_period_end=None,
            tos_accepted_version=None,
        ),
    )
    with pytest.raises(HTTPException) as ei:
        api_mod._require_terms_accepted(User(id="u1", email=None, role="user"))
    assert ei.value.status_code == 403
    assert ei.value.detail["code"] == "terms_not_accepted"
    assert ei.value.detail["version"] == api_mod.CURRENT_LEGAL_VERSION


def test_require_terms_accepted_raises_when_stale_version(monkeypatch):
    """A user who accepted an OLD version must be re-prompted."""
    from fastapi import HTTPException
    from pipeline import api as api_mod
    from pipeline.auth import User
    from pipeline.db import UserProfile
    monkeypatch.setattr(
        "pipeline.db.get_user_profile",
        lambda uid: UserProfile(
            id=uid, stripe_customer_id=None,
            current_plan="free", current_period_end=None,
            tos_accepted_version="1970-01-01",
        ),
    )
    with pytest.raises(HTTPException) as ei:
        api_mod._require_terms_accepted(User(id="u1", email=None, role="user"))
    assert ei.value.status_code == 403
    assert ei.value.detail["code"] == "terms_not_accepted"


def test_require_terms_accepted_passes_when_current(monkeypatch):
    from pipeline import api as api_mod
    from pipeline.auth import User
    from pipeline.db import UserProfile
    monkeypatch.setattr(
        "pipeline.db.get_user_profile",
        lambda uid: UserProfile(
            id=uid, stripe_customer_id=None,
            current_plan="free", current_period_end=None,
            tos_accepted_version=api_mod.CURRENT_LEGAL_VERSION,
        ),
    )
    # No raise.
    api_mod._require_terms_accepted(User(id="u1", email=None, role="user"))


def test_require_terms_accepted_service_bypass(monkeypatch):
    """Service tokens never hit the DB and never get gated."""
    from pipeline import api as api_mod
    from pipeline.auth import User

    def _boom(uid):  # pragma: no cover - must never run for a service token
        raise AssertionError("service token must not query the profile DB")

    # Poison get_user_profile so any DB access would fail loudly — a clean
    # return then proves the bypass short-circuits before touching the DB.
    monkeypatch.setattr("pipeline.db.get_user_profile", _boom)
    api_mod._require_terms_accepted(User(id="admin", email=None, role="service"))


# ---------------------------------------------------------------------------
# POST /account/accept-terms — records the current version.
# ---------------------------------------------------------------------------

def test_accept_terms_records_current_version(client_factory, monkeypatch):
    from pipeline import api as api_mod
    captured: dict = {}

    def fake_upsert(user_id, **fields):
        captured["user_id"] = user_id
        captured.update(fields)

    monkeypatch.setattr("pipeline.db.upsert_user_profile", fake_upsert)

    c = client_factory(user_id="alice", role="user")
    r = c.post("/account/accept-terms")
    assert r.status_code == 200
    assert r.json() == {"ok": True, "version": api_mod.CURRENT_LEGAL_VERSION}

    assert captured["user_id"] == "alice"
    assert captured["tos_accepted_version"] == api_mod.CURRENT_LEGAL_VERSION
    assert captured["tos_accepted_at"]  # ISO timestamp set


def test_accept_terms_service_token_does_not_touch_db(client_factory, monkeypatch):
    from pipeline import api as api_mod

    def boom(*a, **k):  # pragma: no cover - must never run
        raise AssertionError("service token must not write a profile")

    monkeypatch.setattr("pipeline.db.upsert_user_profile", boom)

    c = client_factory(user_id="admin", role="service")
    r = c.post("/account/accept-terms")
    assert r.status_code == 200
    assert r.json() == {"ok": True, "version": api_mod.CURRENT_LEGAL_VERSION}


# ---------------------------------------------------------------------------
# Integration: a gated endpoint 403s before any paid/LLM work.
# ---------------------------------------------------------------------------

def test_songs_endpoint_gated_when_terms_unaccepted(client_factory, monkeypatch):
    from pipeline.db import UserProfile
    monkeypatch.setattr(
        "pipeline.db.get_user_profile",
        lambda uid: UserProfile(
            id=uid, stripe_customer_id=None,
            current_plan="free", current_period_end=None,
            tos_accepted_version=None,
        ),
    )
    c = client_factory(user_id="alice", role="user")
    # Minimal valid body; the gate fires before any LLM/spend work so no
    # heavy mocking is needed.
    r = c.post("/songs", json={"theme": "x"})
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "terms_not_accepted"


# ---------------------------------------------------------------------------
# GET /billing/plan — terms_current field.
# ---------------------------------------------------------------------------

def test_billing_plan_terms_current_true_when_accepted(client_factory, monkeypatch):
    from pipeline import api as api_mod
    from pipeline.db import UserProfile
    monkeypatch.setattr(
        "pipeline.db.get_user_profile",
        lambda uid: UserProfile(
            id=uid, stripe_customer_id="cus_1",
            current_plan="creator", current_period_end=None,
            tos_accepted_version=api_mod.CURRENT_LEGAL_VERSION,
        ),
    )
    monkeypatch.setattr("pipeline.db.get_balance", lambda uid: 10)
    c = client_factory(user_id="alice", role="user")
    body = c.get("/billing/plan").json()
    assert body["terms_current"] is True


def test_billing_plan_terms_current_false_when_unaccepted(client_factory, monkeypatch):
    from pipeline.db import UserProfile
    monkeypatch.setattr(
        "pipeline.db.get_user_profile",
        lambda uid: UserProfile(
            id=uid, stripe_customer_id="cus_1",
            current_plan="creator", current_period_end=None,
            tos_accepted_version=None,
        ),
    )
    monkeypatch.setattr("pipeline.db.get_balance", lambda uid: 10)
    c = client_factory(user_id="alice", role="user")
    body = c.get("/billing/plan").json()
    assert body["terms_current"] is False


def test_billing_plan_terms_current_true_for_service_token(client_factory):
    c = client_factory(user_id="admin", role="service")
    body = c.get("/billing/plan").json()
    assert body["terms_current"] is True
