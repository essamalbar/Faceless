"""Tests for pipeline.credits — business logic on top of pipeline.db."""
from __future__ import annotations

import pytest

from pipeline.auth import User
from pipeline.credits import (
    InsufficientCredits,
    SIGNUP_GRANT,
    check_or_deduct,
    ensure_signup_grant,
    refund,
)


@pytest.fixture
def mock_db(monkeypatch):
    """Stub out pipeline.db so credits can be tested without Supabase."""
    state = {
        "profiles": {},  # user_id -> {fields}
        "transactions": [],
        "balances": {},  # user_id -> int (set explicitly per test)
    }

    def fake_get_profile(uid):
        d = state["profiles"].get(uid)
        if not d:
            return None
        from pipeline.db import UserProfile
        return UserProfile(
            id=d["id"], stripe_customer_id=d.get("stripe_customer_id"),
            current_plan=d.get("current_plan", "free"),
            current_period_end=d.get("current_period_end"),
        )

    def fake_upsert_profile(uid, **fields):
        state["profiles"].setdefault(uid, {"id": uid})
        state["profiles"][uid].update(fields)

    def fake_get_balance(uid):
        return state["balances"].get(uid, 0)

    def fake_record(*, user_id, amount, kind, reference_id=None, description=None):
        state["transactions"].append({
            "user_id": user_id, "amount": amount, "kind": kind,
            "reference_id": reference_id, "description": description,
        })
        state["balances"][user_id] = state["balances"].get(user_id, 0) + amount

    def fake_has_signup_grant(uid):
        return any(
            t["user_id"] == uid and t["kind"] == "signup_grant"
            for t in state["transactions"]
        )

    monkeypatch.setattr("pipeline.credits.get_user_profile", fake_get_profile)
    monkeypatch.setattr("pipeline.credits.upsert_user_profile", fake_upsert_profile)
    monkeypatch.setattr("pipeline.credits.get_balance", fake_get_balance)
    monkeypatch.setattr("pipeline.credits.record_transaction", fake_record)
    monkeypatch.setattr("pipeline.credits._has_signup_grant", fake_has_signup_grant)
    return state


def _user(role="user"):
    return User(id="u1", email="alice@example.com", role=role)


def test_ensure_signup_grant_creates_profile_and_grants(mock_db):
    ensure_signup_grant(_user())
    assert "u1" in mock_db["profiles"]
    assert mock_db["balances"]["u1"] == SIGNUP_GRANT
    grants = [t for t in mock_db["transactions"] if t["kind"] == "signup_grant"]
    assert len(grants) == 1
    assert grants[0]["amount"] == SIGNUP_GRANT


def test_ensure_signup_grant_is_idempotent(mock_db):
    ensure_signup_grant(_user())
    ensure_signup_grant(_user())
    ensure_signup_grant(_user())
    grants = [t for t in mock_db["transactions"] if t["kind"] == "signup_grant"]
    assert len(grants) == 1  # only the first one wrote


def test_ensure_signup_grant_skips_service_user(mock_db):
    ensure_signup_grant(_user(role="service"))
    assert mock_db["profiles"] == {}
    assert mock_db["transactions"] == []


def test_check_or_deduct_succeeds_when_balance_sufficient(mock_db):
    mock_db["balances"]["u1"] = 100
    new_balance = check_or_deduct(_user(), amount=30, run_id="run-1", reason="3 clips × 10s")
    assert new_balance == 70
    debits = [t for t in mock_db["transactions"] if t["kind"] == "run_charge"]
    assert debits[0] == {
        "user_id": "u1", "amount": -30, "kind": "run_charge",
        "reference_id": "run-1", "description": "3 clips × 10s",
    }


def test_check_or_deduct_raises_when_balance_insufficient(mock_db):
    mock_db["balances"]["u1"] = 20
    with pytest.raises(InsufficientCredits) as exc:
        check_or_deduct(_user(), amount=30, run_id="run-1", reason="")
    assert exc.value.balance == 20
    assert exc.value.required == 30
    # No transaction written
    assert mock_db["transactions"] == []


def test_check_or_deduct_skips_service_user(mock_db):
    # Even with zero balance, service tokens bypass
    assert mock_db["balances"].get("u1", 0) == 0
    new_balance = check_or_deduct(_user(role="service"), amount=999, run_id="r", reason="")
    # Returns a high sentinel so callers don't crash on integer math
    assert new_balance >= 0
    assert mock_db["transactions"] == []


def test_refund_inserts_positive_transaction(mock_db):
    mock_db["balances"]["u1"] = 10
    refund(_user(), amount=20, run_id="run-1", reason="veo clip 2 failed")
    assert mock_db["balances"]["u1"] == 30
    r = [t for t in mock_db["transactions"] if t["kind"] == "run_refund"][0]
    assert r["amount"] == 20
    assert r["reference_id"] == "run-1"


def test_refund_skips_service_user(mock_db):
    refund(_user(role="service"), amount=20, run_id="r", reason="")
    assert mock_db["transactions"] == []


def test_ensure_signup_grant_checks_for_existing_grant_row_not_just_profile(monkeypatch, mock_db):
    """Race fix: ensure_signup_grant must check for an existing signup_grant
    transaction (not just a profile row), because the profile is upserted
    BEFORE the transaction is inserted. Two concurrent first-auth calls can
    both see 'no profile' → both upsert → both insert a grant → 2x credits.
    The fix is to gate on the transaction row, not the profile."""
    state = mock_db
    # Simulate state where the profile exists AND a signup_grant exists.
    state["profiles"]["u1"] = {"id": "u1", "current_plan": "free"}
    state["transactions"].append({
        "user_id": "u1", "amount": 60, "kind": "signup_grant",
        "reference_id": None, "description": "Welcome",
    })
    state["balances"]["u1"] = 60

    # Patch _has_signup_grant to return True (real impl reads from DB).
    monkeypatch.setattr("pipeline.credits._has_signup_grant", lambda uid: True)

    ensure_signup_grant(_user())
    # No NEW signup_grant should have been inserted.
    grants = [t for t in state["transactions"] if t["kind"] == "signup_grant"]
    assert len(grants) == 1


def test_ensure_signup_grant_uses_has_signup_grant_as_guard(monkeypatch, mock_db):
    """When _has_signup_grant returns False, the grant fires. When True, it doesn't."""
    state = mock_db
    calls = {"fired": 0}
    monkeypatch.setattr("pipeline.credits._has_signup_grant", lambda uid: False)
    ensure_signup_grant(_user())
    assert any(t["kind"] == "signup_grant" for t in state["transactions"])
    # Now flip the guard — second call shouldn't double-grant.
    monkeypatch.setattr("pipeline.credits._has_signup_grant", lambda uid: True)
    txs_before = len(state["transactions"])
    ensure_signup_grant(_user())
    assert len(state["transactions"]) == txs_before
