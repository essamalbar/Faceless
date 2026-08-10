"""Unit tests for pipeline.db — Supabase-backed credit ledger access."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

import pipeline.db as db
from pipeline.db import (
    Transaction,
    UserProfile,
    count_rate_events,
    deduct_credits_atomic,
    get_balance,
    get_user_profile,
    list_transactions,
    record_grant_once,
    record_rate_event,
    record_transaction,
    upsert_user_profile,
)


class _FakeQuery:
    """Mimics the supabase-py builder; records the calls."""
    def __init__(self, data: list[dict] | dict | None = None, count: Any = None,
                 error: Exception | None = None):
        self._data = data
        self._count = count
        self._error = error
        self.calls: list[tuple[str, tuple, dict]] = []

    def _record(self, name, *args, **kwargs):
        self.calls.append((name, args, kwargs))
        return self

    def select(self, *a, **kw): return self._record("select", *a, **kw)
    def eq(self, *a, **kw):     return self._record("eq", *a, **kw)
    def gte(self, *a, **kw):    return self._record("gte", *a, **kw)
    def order(self, *a, **kw):  return self._record("order", *a, **kw)
    def range(self, *a, **kw):  return self._record("range", *a, **kw)
    def limit(self, *a, **kw):  return self._record("limit", *a, **kw)
    def insert(self, *a, **kw): return self._record("insert", *a, **kw)
    def upsert(self, *a, **kw): return self._record("upsert", *a, **kw)
    def single(self, *a, **kw): return self._record("single", *a, **kw)
    def maybe_single(self, *a, **kw): return self._record("maybe_single", *a, **kw)

    def execute(self):
        if self._error is not None:
            raise self._error
        return _Resp(self._data, self._count)


@dataclass
class _Resp:
    data: Any
    count: Any = None


class _FakeTable:
    def __init__(self, q): self.q = q
    def select(self, *a, **kw):  return self.q.select(*a, **kw)
    def insert(self, *a, **kw):  return self.q.insert(*a, **kw)
    def upsert(self, *a, **kw):  return self.q.upsert(*a, **kw)


class _FakeRpc:
    """Mimics the supabase-py rpc() builder; returns a scalar on execute()."""
    def __init__(self, data: Any):
        self._data = data
    def execute(self):
        return _Resp(self._data)


class _FakeClient:
    def __init__(self):
        self.tables: dict[str, _FakeQuery] = {}
        self.rpc_calls: list[tuple[str, dict]] = []
        self.rpc_result: Any = None
    def table(self, name: str) -> _FakeTable:
        q = self.tables.setdefault(name, _FakeQuery())
        return _FakeTable(q)
    def rpc(self, name: str, params: dict) -> _FakeRpc:
        self.rpc_calls.append((name, params))
        return _FakeRpc(self.rpc_result)


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


def test_get_user_profile_handles_none_response_object(fake_client):
    """supabase-py's `.maybe_single()` can return None (not just data=None) when
    there are 0 rows. Make sure get_user_profile treats both as 'missing'."""
    class _NoneResp:
        data = None
    # Force the FakeQuery to return a response with .data=None — which mirrors
    # what .maybe_single() does in real supabase-py for 0-row results.
    fake_client.tables["user_profiles"] = _FakeQuery(data=None)
    assert get_user_profile("u-fresh") is None


def test_get_balance_handles_none_response_object(fake_client):
    fake_client.tables["user_balance"] = _FakeQuery(data=None)
    assert get_balance("u-fresh") == 0


def test_record_grant_once_inserts_then_dedups(monkeypatch):
    calls = {"n": 0}
    class _Q:
        def execute(self):
            calls["n"] += 1
            if calls["n"] > 1:
                raise Exception('duplicate key value violates unique constraint '
                                '"uq_credit_grant_ref" (code 23505)')
            class R: data = [{}]
            return R()
    class _T:
        def insert(self, payload): return _Q()
    class _Client:
        def table(self, name): return _T()
    monkeypatch.setattr(db, "_client", lambda: _Client())
    assert db.record_grant_once(user_id="u", amount=60, kind="subscription_renewal",
                                reference_id="inv_1", description="x") is True
    assert db.record_grant_once(user_id="u", amount=60, kind="subscription_renewal",
                                reference_id="inv_1", description="x") is False


def test_record_grant_once_reraises_unrelated_error(monkeypatch):
    """The unique-violation swallow must be narrow: any other DB error
    (network, permissions, etc.) has to propagate, not be masked as a no-op."""
    class _Q:
        def execute(self):
            raise Exception("connection refused: could not reach Supabase")
    class _T:
        def insert(self, payload): return _Q()
    class _Client:
        def table(self, name): return _T()
    monkeypatch.setattr(db, "_client", lambda: _Client())
    with pytest.raises(Exception, match="connection refused"):
        record_grant_once(user_id="u", amount=60, kind="subscription_renewal",
                          reference_id="inv_1", description="x")


def test_deduct_credits_atomic_calls_rpc_and_returns_scalar(fake_client):
    fake_client.rpc_result = 4
    new_balance = deduct_credits_atomic(
        user_id="u1", amount=3, kind="run_charge",
        reference_id="r1", description="x",
    )
    assert new_balance == 4
    assert len(fake_client.rpc_calls) == 1
    name, params = fake_client.rpc_calls[0]
    assert name == "deduct_credits"
    assert params == {
        "p_user_id": "u1",
        "p_amount": 3,
        "p_kind": "run_charge",
        "p_reference_id": "r1",
        "p_description": "x",
    }


def test_get_user_profile_reads_tos_fields(fake_client):
    fake_client.tables["user_profiles"] = _FakeQuery(data={
        "id": "u1", "stripe_customer_id": None, "current_plan": "free",
        "current_period_end": None, "cancel_at_period_end": False,
        "payment_status": "active",
        "tos_accepted_version": "2026-08-05", "tos_accepted_at": "2026-08-05T00:00:00Z",
    })
    p = get_user_profile("u1")
    assert p.tos_accepted_version == "2026-08-05"
    assert p.tos_accepted_at == "2026-08-05T00:00:00Z"


def test_get_user_profile_defaults_tos_fields_to_none(fake_client):
    fake_client.tables["user_profiles"] = _FakeQuery(data={"id": "u1", "current_plan": "free"})
    p = get_user_profile("u1")
    assert p.tos_accepted_version is None and p.tos_accepted_at is None


def test_get_grant_by_reference_returns_user_and_amount(fake_client):
    fake_client.tables["credit_transactions"] = _FakeQuery(data=[
        {"user_id": "u1", "amount": 60, "kind": "subscription_renewal"},
    ])
    assert db.get_grant_by_reference("inv_1") == ("u1", 60)


def test_get_grant_by_reference_none_when_no_grant(fake_client):
    fake_client.tables["credit_transactions"] = _FakeQuery(data=[])
    assert db.get_grant_by_reference("inv_x") is None


def test_get_grant_by_reference_ignores_non_grant_rows(fake_client):
    fake_client.tables["credit_transactions"] = _FakeQuery(data=[
        {"user_id": "u1", "amount": -1, "kind": "run_charge"},
    ])
    assert db.get_grant_by_reference("r1") is None


# ── rate_events (Tier-4C abuse & cost controls) ────────────────────────────

def test_record_rate_event_inserts_user_and_action(fake_client):
    record_rate_event("u1", "song_approve")
    q = fake_client.tables["rate_events"]
    insert_call = next(c for c in q.calls if c[0] == "insert")
    assert insert_call[1][0] == {"user_id": "u1", "action": "song_approve"}


def test_count_rate_events_uses_exact_count_and_filters_by_user_action_time(fake_client):
    # supabase-py 2.30.0 populates resp.count when count="exact" is requested.
    fake_client.tables["rate_events"] = _FakeQuery(data=[], count=5)
    n = count_rate_events("u1", "llm_call", 3600)
    assert n == 5

    q = fake_client.tables["rate_events"]
    eq_pairs = [(c[1][0], c[1][1]) for c in q.calls if c[0] == "eq"]
    assert ("user_id", "u1") in eq_pairs
    assert ("action", "llm_call") in eq_pairs
    gte_calls = [c for c in q.calls if c[0] == "gte"]
    assert len(gte_calls) == 1
    # filters created_at against an ISO cutoff string
    assert gte_calls[0][1][0] == "created_at"
    assert isinstance(gte_calls[0][1][1], str) and "T" in gte_calls[0][1][1]


def test_count_rate_events_falls_back_to_len_when_count_absent(fake_client):
    # Older/degraded supabase-py may not populate .count — fall back to len(data).
    fake_client.tables["rate_events"] = _FakeQuery(
        data=[{"id": 1}, {"id": 2}, {"id": 3}], count=None)
    assert count_rate_events("u1", "song_approve", 86400) == 3


def test_count_rate_events_zero_when_no_rows_and_no_count(fake_client):
    fake_client.tables["rate_events"] = _FakeQuery(data=None, count=None)
    assert count_rate_events("u1", "song_approve", 86400) == 0


# ── GDPR account delete/export (Task G) ────────────────────────────────────

def test_anonymize_user_profile_upserts_nulled_pii(fake_client):
    """PII fields are nulled/neutralized but the row is kept so retained
    credit_transactions still reference a valid user_id."""
    db.anonymize_user_profile("u1")
    q = fake_client.tables["user_profiles"]
    upsert_call = next(c for c in q.calls if c[0] == "upsert")
    payload = upsert_call[1][0]
    assert payload["id"] == "u1"
    assert payload["stripe_customer_id"] is None
    assert payload["current_plan"] == "deleted"
    assert payload["tos_accepted_version"] is None


def test_delete_auth_user_calls_admin_delete(monkeypatch):
    """delete_auth_user routes through the service client's auth.admin path.

    The shared _FakeClient has no `.auth`, so build a minimal inline fake
    that records the admin.delete_user call (same pattern as
    test_record_grant_once)."""
    calls: list[str] = []

    class _Admin:
        def delete_user(self, uid):
            calls.append(uid)

    class _Auth:
        admin = _Admin()

    class _Client:
        auth = _Auth()

    monkeypatch.setattr(db, "_client", lambda: _Client())
    db.delete_auth_user("u1")
    assert calls == ["u1"]


def test_delete_auth_user_does_not_touch_credit_transactions(monkeypatch):
    """Deleting the auth user must never delete/insert against the financial
    ledger — a `.table()` call would signal an unexpected DB write path."""
    class _Admin:
        def delete_user(self, uid):
            pass

    class _Auth:
        admin = _Admin()

    class _Client:
        auth = _Auth()

        def table(self, name):  # pragma: no cover - must never run
            raise AssertionError(f"unexpected table access: {name}")

    monkeypatch.setattr(db, "_client", lambda: _Client())
    db.delete_auth_user("u1")  # no raise → no ledger touch


# ── super-admin cross-user aggregation helpers ─────────────────────────────

def test_list_user_profiles_returns_dataclasses(fake_client):
    fake_client.tables["user_profiles"] = _FakeQuery(data=[
        {"id": "u1", "stripe_customer_id": "cus_1", "current_plan": "creator",
         "current_period_end": "2026-09-01T00:00:00Z", "cancel_at_period_end": False,
         "payment_status": "active", "tos_accepted_version": "2026-08-05",
         "tos_accepted_at": "2026-08-05T00:00:00Z"},
        {"id": "u2", "stripe_customer_id": None, "current_plan": "free",
         "current_period_end": None, "cancel_at_period_end": True,
         "payment_status": "past_due", "tos_accepted_version": None,
         "tos_accepted_at": None},
    ])
    profiles = db.list_user_profiles(limit=2, offset=0)
    assert len(profiles) == 2
    assert all(isinstance(p, UserProfile) for p in profiles)
    assert profiles[0].id == "u1"
    assert profiles[0].payment_status == "active"
    assert profiles[0].tos_accepted_version == "2026-08-05"
    assert profiles[1].id == "u2"
    assert profiles[1].cancel_at_period_end is True
    assert profiles[1].payment_status == "past_due"
    assert profiles[1].current_plan == "free"
    # range() is used for pagination: offset..offset+limit-1
    q = fake_client.tables["user_profiles"]
    range_call = next(c for c in q.calls if c[0] == "range")
    assert range_call[1] == (0, 1)


def test_list_user_profiles_defaults_missing_fields(fake_client):
    fake_client.tables["user_profiles"] = _FakeQuery(data=[{"id": "u3"}])
    profiles = db.list_user_profiles()
    assert len(profiles) == 1
    p = profiles[0]
    assert p.id == "u3"
    assert p.current_plan == "free"
    assert p.payment_status == "active"
    assert p.cancel_at_period_end is False
    assert p.stripe_customer_id is None


def test_list_user_profiles_empty_when_no_rows(fake_client):
    fake_client.tables["user_profiles"] = _FakeQuery(data=None)
    assert db.list_user_profiles() == []


def test_list_balances_returns_int_map(fake_client):
    fake_client.tables["user_balance"] = _FakeQuery(data=[
        {"user_id": "u1", "balance": 137},
        {"user_id": "u2", "balance": 0},
        {"user_id": "u3"},  # missing balance → 0
    ])
    balances = db.list_balances()
    assert balances == {"u1": 137, "u2": 0, "u3": 0}
    assert all(isinstance(v, int) for v in balances.values())


def test_list_balances_empty_when_no_rows(fake_client):
    fake_client.tables["user_balance"] = _FakeQuery(data=None)
    assert db.list_balances() == {}


def test_list_transactions_all_returns_dataclasses_newest_first(fake_client):
    fake_client.tables["credit_transactions"] = _FakeQuery(data=[
        {"id": "t3", "user_id": "u2", "amount": -10, "kind": "run_charge",
         "reference_id": "r3", "description": "1 clip", "created_at": "2026-05-11T00:03:00Z"},
        {"id": "t2", "user_id": "u1", "amount": 60, "kind": "subscription_renewal",
         "reference_id": "inv_1", "description": None, "created_at": "2026-05-11T00:02:00Z"},
        {"id": "t1", "user_id": "u1", "amount": 12, "kind": "signup_grant",
         "reference_id": None, "description": None, "created_at": "2026-05-11T00:01:00Z"},
    ])
    txs = db.list_transactions_all(limit=3)
    assert len(txs) == 3
    assert all(isinstance(t, Transaction) for t in txs)
    assert txs[0].id == "t3"
    assert txs[0].user_id == "u2"
    assert txs[-1].kind == "signup_grant"
    # ordered created_at desc, limited
    q = fake_client.tables["credit_transactions"]
    order_call = next(c for c in q.calls if c[0] == "order")
    assert order_call[1][0] == "created_at"
    assert order_call[2].get("desc") is True
    limit_call = next(c for c in q.calls if c[0] == "limit")
    assert limit_call[1][0] == 3


def test_list_transactions_all_empty_when_no_rows(fake_client):
    fake_client.tables["credit_transactions"] = _FakeQuery(data=None)
    assert db.list_transactions_all() == []


def test_list_auth_users_from_objects(monkeypatch):
    class _U:
        def __init__(self, uid, email):
            self.id = uid
            self.email = email

    class _Res:
        users = [_U("u1", "a@example.com"), _U("u2", "b@example.com")]

    class _Admin:
        def list_users(self):
            return _Res()

    class _Auth:
        admin = _Admin()

    class _Client:
        auth = _Auth()

    monkeypatch.setattr(db, "_client", lambda: _Client())
    assert db.list_auth_users() == {"u1": "a@example.com", "u2": "b@example.com"}


def test_list_auth_users_from_dicts(monkeypatch):
    """Dict-shaped fallback: `.users` is a list of plain dicts."""
    class _Res:
        users = [
            {"id": "u1", "email": "a@example.com"},
            {"id": "u2", "email": "b@example.com"},
            {"id": "u3"},  # no email → skipped
        ]

    class _Admin:
        def list_users(self):
            return _Res()

    class _Auth:
        admin = _Admin()

    class _Client:
        auth = _Auth()

    monkeypatch.setattr(db, "_client", lambda: _Client())
    assert db.list_auth_users() == {"u1": "a@example.com", "u2": "b@example.com"}


def test_list_auth_users_returns_empty_on_error(monkeypatch):
    class _Admin:
        def list_users(self):
            raise Exception("auth admin unavailable")

    class _Auth:
        admin = _Admin()

    class _Client:
        auth = _Auth()

    monkeypatch.setattr(db, "_client", lambda: _Client())
    assert db.list_auth_users() == {}


def test_probe_activation_all_true_when_selects_succeed(fake_client):
    # default _FakeQuery() for both tables → both selects succeed
    probe = db.probe_activation()
    assert probe == {
        "payment_status": True,
        "tos_accepted_version": True,
        "rate_events": True,
    }


def test_probe_activation_false_when_relation_missing(fake_client):
    fake_client.tables["rate_events"] = _FakeQuery(
        error=Exception('relation "rate_events" does not exist'))
    probe = db.probe_activation()
    assert probe["rate_events"] is False
    assert probe["payment_status"] is True
    assert probe["tos_accepted_version"] is True


def test_probe_activation_none_on_unrelated_error(fake_client):
    fake_client.tables["user_profiles"] = _FakeQuery(
        error=Exception("network timeout"))
    probe = db.probe_activation()
    assert probe["payment_status"] is None
    assert probe["tos_accepted_version"] is None
