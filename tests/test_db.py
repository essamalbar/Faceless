"""Unit tests for pipeline.db — Supabase-backed credit ledger access."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from pipeline.db import (
    Transaction,
    UserProfile,
    get_balance,
    get_user_profile,
    list_transactions,
    record_transaction,
    upsert_user_profile,
)


class _FakeQuery:
    """Mimics the supabase-py builder; records the calls."""
    def __init__(self, data: list[dict] | dict | None = None):
        self._data = data
        self.calls: list[tuple[str, tuple, dict]] = []

    def _record(self, name, *args, **kwargs):
        self.calls.append((name, args, kwargs))
        return self

    def select(self, *a, **kw): return self._record("select", *a, **kw)
    def eq(self, *a, **kw):     return self._record("eq", *a, **kw)
    def order(self, *a, **kw):  return self._record("order", *a, **kw)
    def limit(self, *a, **kw):  return self._record("limit", *a, **kw)
    def insert(self, *a, **kw): return self._record("insert", *a, **kw)
    def upsert(self, *a, **kw): return self._record("upsert", *a, **kw)
    def single(self, *a, **kw): return self._record("single", *a, **kw)

    def execute(self):
        return _Resp(self._data)


@dataclass
class _Resp:
    data: Any


class _FakeTable:
    def __init__(self, q): self.q = q
    def select(self, *a, **kw):  return self.q.select(*a, **kw)
    def insert(self, *a, **kw):  return self.q.insert(*a, **kw)
    def upsert(self, *a, **kw):  return self.q.upsert(*a, **kw)


class _FakeClient:
    def __init__(self):
        self.tables: dict[str, _FakeQuery] = {}
    def table(self, name: str) -> _FakeTable:
        q = self.tables.setdefault(name, _FakeQuery())
        return _FakeTable(q)


@pytest.fixture
def fake_client(monkeypatch):
    client = _FakeClient()
    monkeypatch.setattr("pipeline.db._client", lambda: client)
    return client


def test_get_user_profile_returns_dataclass_when_found(fake_client):
    fake_client.tables["user_profiles"] = _FakeQuery(data={
        "id": "u1",
        "stripe_customer_id": "cus_x",
        "current_plan": "starter",
        "current_period_end": None,
    })
    p = get_user_profile("u1")
    assert p == UserProfile(
        id="u1",
        stripe_customer_id="cus_x",
        current_plan="starter",
        current_period_end=None,
    )


def test_get_user_profile_returns_none_when_missing(fake_client):
    fake_client.tables["user_profiles"] = _FakeQuery(data=None)
    assert get_user_profile("u1") is None


def test_upsert_user_profile_passes_fields_to_supabase(fake_client):
    upsert_user_profile("u1", stripe_customer_id="cus_xyz", current_plan="creator")
    q = fake_client.tables["user_profiles"]
    upsert_call = next(c for c in q.calls if c[0] == "upsert")
    payload = upsert_call[1][0]
    assert payload["id"] == "u1"
    assert payload["stripe_customer_id"] == "cus_xyz"
    assert payload["current_plan"] == "creator"


def test_get_balance_returns_int_from_view(fake_client):
    fake_client.tables["user_balance"] = _FakeQuery(data={"user_id": "u1", "balance": 137})
    assert get_balance("u1") == 137


def test_get_balance_returns_zero_when_no_transactions(fake_client):
    fake_client.tables["user_balance"] = _FakeQuery(data=None)
    assert get_balance("u1") == 0


def test_record_transaction_writes_payload(fake_client):
    record_transaction(
        user_id="u1", amount=-30, kind="run_charge",
        reference_id="run-abc", description="3 clips × 10s",
    )
    q = fake_client.tables["credit_transactions"]
    insert_call = next(c for c in q.calls if c[0] == "insert")
    payload = insert_call[1][0]
    assert payload == {
        "user_id": "u1",
        "amount": -30,
        "kind": "run_charge",
        "reference_id": "run-abc",
        "description": "3 clips × 10s",
    }


def test_list_transactions_returns_dataclasses_ordered_desc(fake_client):
    fake_client.tables["credit_transactions"] = _FakeQuery(data=[
        {"id": "t1", "user_id": "u1", "amount": 60, "kind": "signup_grant",
         "reference_id": None, "description": None, "created_at": "2026-05-11T00:00:00Z"},
        {"id": "t2", "user_id": "u1", "amount": -10, "kind": "run_charge",
         "reference_id": "r1", "description": "1 clip", "created_at": "2026-05-11T00:01:00Z"},
    ])
    txs = list_transactions("u1", limit=10)
    assert len(txs) == 2
    assert all(isinstance(t, Transaction) for t in txs)
    assert txs[0].kind == "signup_grant"
    assert txs[1].amount == -10
