"""Tests for pipeline.credits — business logic on top of pipeline.db.

Pricing model (locked 2026-05-13): 1 credit = 1 clip. No signup_grant; users
get credits ONLY by subscribing. Script generation is free; the paywall fires
in /runs/{id}/approve.
"""
from __future__ import annotations

import pytest

from pipeline.auth import User
from pipeline.credits import (
    InsufficientCredits,
    PLAN_GRANTS,
    check_or_deduct,
    refund,
)


@pytest.fixture
def mock_db(monkeypatch):
    """Stub out pipeline.db so credits can be tested without Supabase."""
    state = {
        "transactions": [],
        "balances": {},
    }

    def fake_get_balance(uid):
        return state["balances"].get(uid, 0)

    def fake_record(*, user_id, amount, kind, reference_id=None, description=None):
        state["transactions"].append({
            "user_id": user_id, "amount": amount, "kind": kind,
            "reference_id": reference_id, "description": description,
        })
        state["balances"][user_id] = state["balances"].get(user_id, 0) + amount

    monkeypatch.setattr("pipeline.credits.get_balance", fake_get_balance)
    monkeypatch.setattr("pipeline.credits.record_transaction", fake_record)
    return state


def _user(role="user"):
    return User(id="u1", email="alice@example.com", role=role)


def test_plan_grants_match_locked_pricing():
    """Pricing constants are user-facing — guard against accidental drift."""
    assert PLAN_GRANTS == {"starter": 12, "creator": 60, "pro": 200}


def test_check_or_deduct_succeeds_when_balance_sufficient(mock_db):
    mock_db["balances"]["u1"] = 10
    new_balance = check_or_deduct(_user(), amount=3, run_id="run-1", reason="3 clips")
    assert new_balance == 7
    debits = [t for t in mock_db["transactions"] if t["kind"] == "run_charge"]
    assert debits[0] == {
        "user_id": "u1", "amount": -3, "kind": "run_charge",
        "reference_id": "run-1", "description": "3 clips",
    }


def test_check_or_deduct_raises_when_balance_insufficient(mock_db):
    mock_db["balances"]["u1"] = 2
    with pytest.raises(InsufficientCredits) as exc:
        check_or_deduct(_user(), amount=3, run_id="run-1", reason="")
    assert exc.value.balance == 2
    assert exc.value.required == 3
    # No transaction written
    assert mock_db["transactions"] == []


def test_check_or_deduct_skips_service_user(mock_db):
    # Even with zero balance, service tokens bypass.
    new_balance = check_or_deduct(_user(role="service"), amount=999, run_id="r", reason="")
    assert new_balance >= 0
    assert mock_db["transactions"] == []


def test_refund_inserts_positive_transaction(mock_db):
    mock_db["balances"]["u1"] = 1
    refund(_user(), amount=1, run_id="run-1", reason="clip 2 failed")
    assert mock_db["balances"]["u1"] == 2
    r = [t for t in mock_db["transactions"] if t["kind"] == "run_refund"][0]
    assert r["amount"] == 1
    assert r["reference_id"] == "run-1"


def test_refund_skips_service_user(mock_db):
    refund(_user(role="service"), amount=1, run_id="r", reason="")
    assert mock_db["transactions"] == []
