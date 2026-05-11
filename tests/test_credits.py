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

    monkeypatch.setattr("pipeline.credits.get_user_profile", fake_get_profile)
    monkeypatch.setattr("pipeline.credits.upsert_user_profile", fake_upsert_profile)
    monkeypatch.setattr("pipeline.credits.get_balance", fake_get_balance)
    monkeypatch.setattr("pipeline.credits.record_transaction", fake_record)
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
