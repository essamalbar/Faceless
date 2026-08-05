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
    refund_run_charges,
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

    def fake_list(uid, limit=50):
        # Cheap reverse-chronological order matches the real query
        from types import SimpleNamespace
        rows = [
            SimpleNamespace(
                user_id=t["user_id"], amount=t["amount"], kind=t["kind"],
                reference_id=t["reference_id"], description=t["description"],
                id=str(i), created_at="2026-05-15",
            )
            for i, t in enumerate(state["transactions"])
            if t["user_id"] == uid
        ][:limit]
        return rows

    def fake_deduct_atomic(*, user_id, amount, kind, reference_id, description):
        # Mirror the deduct_credits Postgres function: check balance, return -1
        # if insufficient, otherwise insert the debit and return the new balance.
        if state["balances"].get(user_id, 0) < amount:
            return -1
        fake_record(user_id=user_id, amount=-amount, kind=kind,
                    reference_id=reference_id, description=description)
        return state["balances"][user_id]

    monkeypatch.setattr("pipeline.credits.get_balance", fake_get_balance)
    monkeypatch.setattr("pipeline.credits.record_transaction", fake_record)
    monkeypatch.setattr("pipeline.credits.list_transactions", fake_list)
    monkeypatch.setattr("pipeline.credits.deduct_credits_atomic", fake_deduct_atomic)
    return state


def _user(role="user"):
    return User(id="u1", email="alice@example.com", role=role)


def test_plan_grants_match_locked_pricing():
    """Pricing constants are user-facing — guard against accidental drift."""
    assert PLAN_GRANTS == {"starter": 12, "creator": 60, "pro": 200}


def test_check_or_deduct_uses_atomic_rpc_and_returns_new_balance(monkeypatch):
    from pipeline import credits
    monkeypatch.setattr("pipeline.credits.deduct_credits_atomic",
                        lambda **kw: 7)
    from pipeline.auth import User
    u = User(id="u1", email=None, role="user")
    assert credits.check_or_deduct(u, amount=3, run_id="r1", reason="x") == 7


def test_check_or_deduct_raises_when_atomic_returns_negative(monkeypatch):
    import pytest
    from pipeline import credits
    monkeypatch.setattr("pipeline.credits.deduct_credits_atomic", lambda **kw: -1)
    monkeypatch.setattr("pipeline.credits.get_balance", lambda uid: 2)
    from pipeline.auth import User
    u = User(id="u1", email=None, role="user")
    with pytest.raises(credits.InsufficientCredits):
        credits.check_or_deduct(u, amount=5, run_id="r1", reason="x")


def test_check_or_deduct_service_bypass_skips_rpc(monkeypatch):
    from pipeline import credits
    monkeypatch.setattr("pipeline.credits.deduct_credits_atomic",
                        lambda **kw: (_ for _ in ()).throw(AssertionError("should not call")))
    from pipeline.auth import User
    u = User(id="admin", email=None, role="service")
    assert credits.check_or_deduct(u, amount=99, run_id="r1", reason="x") == 10**9


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


# ---------------------------------------------------------------------------
# refund_run_charges — used when a stage AFTER clip generation fails.
# Real-world bug: user paid for 5 clips, assembly crashed at the xfade
# step, no final.mp4 produced, no refund issued. This helper closes that.
# ---------------------------------------------------------------------------

def test_refund_run_charges_returns_net_charged(mock_db):
    """5 clips charged, no per-clip refunds → refund 5 credits."""
    mock_db["balances"]["u1"] = 100
    check_or_deduct(_user(), amount=5, run_id="run-A", reason="5 clips")
    assert mock_db["balances"]["u1"] == 95

    refunded = refund_run_charges(
        _user(), run_id="run-A", reason="assembly failed",
    )
    assert refunded == 5
    assert mock_db["balances"]["u1"] == 100  # back to start


def test_refund_run_charges_nets_out_existing_refunds(mock_db):
    """If clip 3 already got a Veo-timeout refund, the assembly-failure
    refund only restores the remaining net-charged amount, never the
    full original charge twice."""
    mock_db["balances"]["u1"] = 100
    check_or_deduct(_user(), amount=5, run_id="run-A", reason="5 clips")
    refund(_user(), amount=1, run_id="run-A", reason="clip 3 timed out")
    # User has been net-charged 4 credits at this point
    assert mock_db["balances"]["u1"] == 96

    refunded = refund_run_charges(
        _user(), run_id="run-A", reason="assembly failed",
    )
    assert refunded == 4   # not 5 — clip 3 was already refunded
    assert mock_db["balances"]["u1"] == 100


def test_refund_run_charges_idempotent(mock_db):
    """Calling refund_run_charges twice is safe — the second call sees
    a zero net balance for the run and returns 0."""
    mock_db["balances"]["u1"] = 100
    check_or_deduct(_user(), amount=3, run_id="run-A", reason="")
    assert refund_run_charges(_user(), run_id="run-A", reason="1st") == 3
    assert refund_run_charges(_user(), run_id="run-A", reason="2nd") == 0
    assert mock_db["balances"]["u1"] == 100


def test_refund_run_charges_only_touches_named_run(mock_db):
    """Charges against other run_ids must not be refunded."""
    mock_db["balances"]["u1"] = 100
    check_or_deduct(_user(), amount=4, run_id="run-A", reason="")
    check_or_deduct(_user(), amount=2, run_id="run-B", reason="")

    refunded = refund_run_charges(_user(), run_id="run-A", reason="")
    assert refunded == 4
    # run-B charges untouched
    assert mock_db["balances"]["u1"] == 100 - 2


def test_refund_run_charges_skips_service_user(mock_db):
    refunded = refund_run_charges(
        _user(role="service"), run_id="r", reason="",
    )
    assert refunded == 0
    assert mock_db["transactions"] == []
