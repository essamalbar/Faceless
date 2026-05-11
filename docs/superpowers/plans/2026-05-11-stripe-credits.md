# Stripe Credits Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a per-user credit ledger backed by Stripe — users sign up with 60 free credits, subscribe or buy top-up packs, and each generated video deducts credits per Veo clip (auto-refund on failure).

**Architecture:** Supabase Postgres holds the append-only ledger; balance = `SUM(credit_transactions.amount)`. Stripe-hosted Checkout + Customer Portal handle payments. The FastAPI backend gains 7 new endpoints (3 read, 3 checkout-creator, 1 webhook); the worker (`run.py`) deducts/refunds per-clip via a thin `pipeline/credits.py` business layer. Service tokens (admin/CLI) bypass all credit checks. Spec: `docs/superpowers/specs/2026-05-11-stripe-credits-design.md`.

**Tech Stack:** `stripe` Python SDK, `supabase` Python client, Supabase Postgres (RLS), FastAPI, the existing Cloud Run + Supabase Auth from B2.

**Important context for implementers:**
- All Python files start with `from __future__ import annotations`. Use `pathlib.Path`, never `os.path`.
- Run `uv run pytest tests/test_<file>.py -v` for one file; `uv run pytest -q` for the suite. Baseline at the start of this plan: **373 passing**.
- External services (Stripe, Supabase, Anthropic, Kie) are mocked in tests; never hit them for real.
- Frequent commits — every task ends with a commit. Conventional Commits style (`feat:`, `fix:`, `test:`).
- Project: `project-affccfbf-a37c-4648-a0b`. Cloud Run service: `faceless-api`, region `us-central1`. Bucket: `${PROJECT_ID}-faceless-runs`.
- Supabase project: `eorpqwvjbljsjlzvmvom`. The service role key is already in Secret Manager as `supabase-service-role-key` (from B2).
- `User` dataclass (from `pipeline/auth.py`): `User(id, email, role)`. `role == "service"` is the admin/CLI sentinel — every credit operation must early-return when it sees this.

**Pricing locked from the spec:**
```python
SIGNUP_GRANT = 60
PLAN_GRANTS = {'starter': 60, 'creator': 250, 'pro': 800}
TOPUP_PACKS = {'topup_30': 30, 'topup_100': 100, 'topup_300': 300}
```

---

## File Structure

| File | Purpose | Status |
|---|---|---|
| `supabase/migrations/20260511000000_credits.sql` | DB schema: user_profiles, credit_transactions, user_balance view, RLS | **NEW** |
| `pipeline/db.py` | Thin supabase-py wrapper — `get_user_profile`, `upsert_user_profile`, `get_balance`, `record_transaction`, `list_transactions` | **NEW** |
| `tests/test_db.py` | Unit tests for db.py (mocked Supabase client) | **NEW** |
| `pipeline/credits.py` | Business logic: `ensure_signup_grant`, `check_or_deduct`, `refund`, `InsufficientCredits` exception | **NEW** |
| `tests/test_credits.py` | Unit tests for credits.py | **NEW** |
| `pipeline/stripe_billing.py` | Stripe SDK wrapper — checkout creators, portal, webhook handler | **NEW** |
| `tests/test_stripe_billing.py` | Unit tests for stripe_billing.py (mocked Stripe SDK) | **NEW** |
| `pipeline/auth.py` | Modify `require_user` to call `ensure_signup_grant` on every authed request | MODIFY |
| `pipeline/api.py` | Add 7 billing endpoints; pre-flight credit check on `/runs/freeform` + `/runs/from-script` | MODIFY |
| `tests/test_api.py` | New tests for billing endpoints + credit pre-flight | MODIFY |
| `run.py` | Worker: per-clip deduct/refund in `_stage_video_chained` | MODIFY |
| `pyproject.toml` | Add `stripe>=10`, `supabase>=2` | MODIFY |
| `deploy/cloud-run-service.yaml` | Mount `STRIPE_*` secrets + `SUPABASE_SERVICE_ROLE_KEY` env on the Service | MODIFY |
| `deploy/cloud-run-job.yaml` | Mount `SUPABASE_SERVICE_ROLE_KEY` env on the Job (worker writes ledger) | MODIFY |
| `scripts/setup-cloud-run.sh` | Push new Stripe secrets to Secret Manager | MODIFY |
| `lib/api/client.dart` | Add billing methods + `InsufficientCreditsException` | MODIFY |
| `lib/api/models.dart` | Add `Balance`, `Plan`, `Transaction` models | MODIFY |
| `lib/screens/billing_screen.dart` | Plan cards + top-up packs + transactions list | **NEW** |
| `lib/widgets/paywall_dialog.dart` | Shown on 402 — links to billing screen | **NEW** |
| `lib/screens/home_screen.dart` | Add balance badge top-right | MODIFY |
| `lib/screens/settings_screen.dart` | Add "Billing" row that opens billing screen | MODIFY |

---

## Task 1: Postgres schema — user_profiles + credit_transactions + RLS

**Files:**
- Create: `supabase/migrations/20260511000000_credits.sql`

This is a **one-way migration** — once applied to Supabase, future tasks read from these tables.

- [ ] **Step 1.1: Create the migration file**

Create `supabase/migrations/20260511000000_credits.sql`:

```sql
-- B3: per-user credit ledger + Stripe customer mapping.
-- See docs/superpowers/specs/2026-05-11-stripe-credits-design.md

-- ---------------------------------------------------------------------------
-- 1. user_profiles: lightweight per-user app metadata.
-- ---------------------------------------------------------------------------
create table public.user_profiles (
  id                    uuid primary key references auth.users(id) on delete cascade,
  stripe_customer_id    text unique,
  current_plan          text not null default 'free'
                        check (current_plan in ('free','starter','creator','pro')),
  current_period_end    timestamptz,
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now()
);

create or replace function public.touch_user_profiles_updated_at()
returns trigger language plpgsql as $$
begin new.updated_at := now(); return new; end;
$$;
create trigger user_profiles_touch_updated_at
  before update on public.user_profiles
  for each row execute function public.touch_user_profiles_updated_at();

-- ---------------------------------------------------------------------------
-- 2. credit_transactions: append-only ledger.
--    Never UPDATE or DELETE rows. Corrections = new rows with kind='admin_adjust'.
-- ---------------------------------------------------------------------------
create table public.credit_transactions (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null references auth.users(id) on delete cascade,
  amount        integer not null,
                -- positive = credit, negative = debit
  kind          text not null
                check (kind in (
                  'signup_grant',
                  'subscription_renewal',
                  'topup',
                  'run_charge',
                  'run_refund',
                  'admin_adjust'
                )),
  reference_id  text,   -- run_id for run_charge/refund; stripe id for billing events
  description   text,
  created_at    timestamptz not null default now()
);
create index credit_transactions_user_id_created_at_idx
  on public.credit_transactions(user_id, created_at desc);

-- Convenience: balance = sum(amount). Used by API and tests.
create view public.user_balance as
  select user_id,
         coalesce(sum(amount), 0)::integer as balance
  from public.credit_transactions
  group by user_id;

-- ---------------------------------------------------------------------------
-- 3. Row-Level Security.
-- ---------------------------------------------------------------------------
alter table public.user_profiles      enable row level security;
alter table public.credit_transactions enable row level security;

-- Users can read their own profile + ledger. All writes go via service_role.
create policy "users read own profile" on public.user_profiles
  for select using (auth.uid() = id);

create policy "users read own transactions" on public.credit_transactions
  for select using (auth.uid() = user_id);

-- service_role bypasses RLS by default — backend writes are unrestricted.
```

- [ ] **Step 1.2: Apply the migration via Supabase SQL editor**

The Supabase CLI isn't set up in this repo (we run schema changes through the dashboard). Manual step:

1. Open https://supabase.com/dashboard/project/eorpqwvjbljsjlzvmvom/sql/new
2. Paste the contents of `supabase/migrations/20260511000000_credits.sql`
3. Click **Run** — should succeed with "Success. No rows returned."
4. Verify in **Table Editor**: `user_profiles` and `credit_transactions` exist; both have RLS enabled (lock icon visible).

If the migration fails, do NOT proceed to Task 2 — fix the SQL first. Common issues: `gen_random_uuid()` requires the `pgcrypto` extension (it's enabled by default on Supabase, but worth confirming via `Extensions → pgcrypto → enabled`).

- [ ] **Step 1.3: Commit the migration file**

```bash
git add supabase/migrations/20260511000000_credits.sql
git commit -m "feat(db): credits ledger schema (user_profiles, credit_transactions, RLS)"
```

---

## Task 2: `pipeline/db.py` — Supabase-py wrapper

**Files:**
- Modify: `pyproject.toml`
- Create: `pipeline/db.py`
- Create: `tests/test_db.py`

- [ ] **Step 2.1: Add `supabase` to dependencies**

In `pyproject.toml`, in the `dependencies = [...]` array, add right after `"pyjwt[crypto]>=2.8",`:

```toml
    # supabase-py: server-side client for the Postgres ledger. Uses
    # SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY (already in Secret Manager
    # from B2) to bypass RLS for ledger writes.
    "supabase>=2.6",
```

Then run:

```bash
uv lock
uv sync
```

- [ ] **Step 2.2: Write failing tests in `tests/test_db.py`**

The Supabase client is mocked so tests don't hit the network. Pattern: monkeypatch `pipeline.db._client()` to return a stub.

```python
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
```

- [ ] **Step 2.3: Run tests — they should fail**

```bash
uv run pytest tests/test_db.py -v
```

Expected: ModuleNotFoundError on `pipeline.db`.

- [ ] **Step 2.4: Implement `pipeline/db.py`**

```python
"""Supabase-backed access for the credit ledger and user_profiles.

The backend uses the *service role* key (already in Secret Manager from B2)
so it can bypass RLS for ledger inserts. End users never touch this module
directly — they hit the FastAPI endpoints, which scope queries by their
authenticated user id.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from supabase import Client, create_client


@dataclass(frozen=True)
class UserProfile:
    id: str
    stripe_customer_id: str | None
    current_plan: str
    current_period_end: str | None  # ISO timestamp as Supabase returns it


@dataclass(frozen=True)
class Transaction:
    id: str
    user_id: str
    amount: int
    kind: str
    reference_id: str | None
    description: str | None
    created_at: str


@lru_cache(maxsize=1)
def _client() -> Client:
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set for db access",
        )
    return create_client(url, key)


def get_user_profile(user_id: str) -> UserProfile | None:
    resp = (
        _client()
        .table("user_profiles")
        .select("id,stripe_customer_id,current_plan,current_period_end")
        .eq("id", user_id)
        .single()
        .execute()
    )
    if not resp.data:
        return None
    d = resp.data
    return UserProfile(
        id=d["id"],
        stripe_customer_id=d.get("stripe_customer_id"),
        current_plan=d.get("current_plan", "free"),
        current_period_end=d.get("current_period_end"),
    )


def upsert_user_profile(user_id: str, **fields) -> None:
    payload = {"id": user_id, **fields}
    _client().table("user_profiles").upsert(payload).execute()


def get_balance(user_id: str) -> int:
    resp = (
        _client()
        .table("user_balance")
        .select("user_id,balance")
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    if not resp.data:
        return 0
    return int(resp.data.get("balance", 0))


def record_transaction(
    *,
    user_id: str,
    amount: int,
    kind: str,
    reference_id: str | None = None,
    description: str | None = None,
) -> None:
    payload = {
        "user_id": user_id,
        "amount": amount,
        "kind": kind,
        "reference_id": reference_id,
        "description": description,
    }
    _client().table("credit_transactions").insert(payload).execute()


def list_transactions(user_id: str, limit: int = 50) -> list[Transaction]:
    resp = (
        _client()
        .table("credit_transactions")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return [
        Transaction(
            id=r["id"], user_id=r["user_id"], amount=r["amount"],
            kind=r["kind"], reference_id=r.get("reference_id"),
            description=r.get("description"), created_at=r["created_at"],
        )
        for r in (resp.data or [])
    ]
```

Note: `record_transaction` uses keyword-only args (`*,`) so callers can't accidentally swap `amount` and `kind`.

- [ ] **Step 2.5: Run tests — they should pass**

```bash
uv run pytest tests/test_db.py -v
```

Expected: 7 passed.

- [ ] **Step 2.6: Run full suite — confirm no regressions**

```bash
uv run pytest -q
```

Expected: 380 passed (was 373 + 7 new).

- [ ] **Step 2.7: Commit**

```bash
git add pyproject.toml uv.lock pipeline/db.py tests/test_db.py
git commit -m "feat(db): supabase-py wrapper for user_profiles + credit_transactions"
```

---

## Task 3: `pipeline/credits.py` — business logic + `ensure_signup_grant` hook

**Files:**
- Create: `pipeline/credits.py`
- Create: `tests/test_credits.py`
- Modify: `pipeline/auth.py` (call `ensure_signup_grant` from `require_user`)

- [ ] **Step 3.1: Write failing tests in `tests/test_credits.py`**

```python
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
```

- [ ] **Step 3.2: Run tests — should fail with ImportError**

```bash
uv run pytest tests/test_credits.py -v
```

Expected: ModuleNotFoundError on `pipeline.credits`.

- [ ] **Step 3.3: Implement `pipeline/credits.py`**

```python
"""Credit ledger business logic.

Thin layer on top of pipeline.db that adds:
  - The "service-token bypass" rule (admin/CLI never spends credits)
  - Idempotent signup-grant on first authenticated request
  - Raises InsufficientCredits when a deduction would push the balance below zero

Every entry point takes a `User` (from pipeline.auth) — never a bare user_id —
so the bypass check happens in one place.
"""
from __future__ import annotations

from dataclasses import dataclass

from pipeline.auth import User
from pipeline.db import (
    get_balance,
    get_user_profile,
    record_transaction,
    upsert_user_profile,
)

SIGNUP_GRANT = 60
PLAN_GRANTS = {"starter": 60, "creator": 250, "pro": 800}
TOPUP_PACKS = {"topup_30": 30, "topup_100": 100, "topup_300": 300}


@dataclass(frozen=True)
class InsufficientCredits(Exception):
    """Raised when a deduction would push the balance below zero."""
    balance: int
    required: int

    def __str__(self) -> str:
        return f"insufficient credits: have {self.balance}, need {self.required}"


def _is_service(user: User) -> bool:
    return user.role == "service"


def ensure_signup_grant(user: User) -> None:
    """If user_profiles row doesn't exist yet, create it AND grant SIGNUP_GRANT
    credits. Idempotent — safe to call on every authenticated request."""
    if _is_service(user):
        return
    if get_user_profile(user.id) is not None:
        return  # already provisioned
    upsert_user_profile(user.id, current_plan="free")
    record_transaction(
        user_id=user.id,
        amount=SIGNUP_GRANT,
        kind="signup_grant",
        description="Welcome — 60 free credits",
    )


def check_or_deduct(
    user: User,
    *,
    amount: int,
    run_id: str,
    reason: str,
) -> int:
    """Verify the user has at least `amount` credits, then deduct.
    Returns the new balance. Service tokens bypass entirely.

    Note: this is the simple non-locked variant — concurrent runs from the same
    user could transiently overspend by one clip (~$0.10). The spec calls this
    out as an accepted tradeoff for v1.
    """
    if _is_service(user):
        return 10**9  # sentinel — callers won't divide by this
    balance = get_balance(user.id)
    if balance < amount:
        raise InsufficientCredits(balance=balance, required=amount)
    record_transaction(
        user_id=user.id,
        amount=-amount,
        kind="run_charge",
        reference_id=run_id,
        description=reason,
    )
    return balance - amount


def refund(
    user: User,
    *,
    amount: int,
    run_id: str,
    reason: str,
) -> None:
    """Insert a positive transaction. Used when a Veo clip fails after deduction.
    No-op for service tokens."""
    if _is_service(user):
        return
    record_transaction(
        user_id=user.id,
        amount=amount,
        kind="run_refund",
        reference_id=run_id,
        description=reason,
    )
```

- [ ] **Step 3.4: Wire `ensure_signup_grant` into `require_user`**

In `pipeline/auth.py`, find the `require_user` function (added in B2). Currently it does service-token check then JWT verify, returning a `User`. We want to call `ensure_signup_grant` on every successful authentication of a non-service user.

The cleanest way: add the hook at the end of `require_user`, just before the return on the JWT-verified path. Edit:

```python
    if jwt_secret:
        try:
            user = verify_supabase_jwt(token, jwt_secret, supabase_url=supabase_url)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {e}",
            ) from None
        # Lazy-init: ensures the user has a profile + signup grant the first time
        # they hit any authenticated endpoint. Cheap (one SELECT for repeat users).
        # Imported lazily to avoid a cycle (credits → auth.User).
        from pipeline.credits import ensure_signup_grant
        try:
            ensure_signup_grant(user)
        except Exception:
            # If the DB is unreachable, don't block auth — log it and continue.
            # The user just won't have their grant; we can backfill later.
            pass
        return user
```

(Find the existing `return verify_supabase_jwt(...)` line — wrap it as shown.)

- [ ] **Step 3.5: Add an integration test in `tests/test_auth.py`**

Append at the bottom of `tests/test_auth.py`:

```python
def test_require_user_calls_ensure_signup_grant(monkeypatch):
    """A successful JWT verification triggers the signup-grant hook exactly once."""
    _setenv(monkeypatch, FACELESS_API_TOKEN="svc-secret",
            SUPABASE_JWT_SECRET=SECRET)
    called: list[str] = []
    def fake_grant(user):
        called.append(user.id)
    monkeypatch.setattr("pipeline.credits.ensure_signup_grant", fake_grant)
    token = _encode(GOOD_PAYLOAD)
    user = require_user(authorization=f"Bearer {token}")
    assert called == [user.id]


def test_require_user_swallows_db_errors_in_signup_grant(monkeypatch):
    """If the DB is down, auth must still succeed (with no grant)."""
    _setenv(monkeypatch, FACELESS_API_TOKEN="svc-secret",
            SUPABASE_JWT_SECRET=SECRET)
    def fake_grant(user):
        raise RuntimeError("supabase down")
    monkeypatch.setattr("pipeline.credits.ensure_signup_grant", fake_grant)
    token = _encode(GOOD_PAYLOAD)
    # Should not raise
    user = require_user(authorization=f"Bearer {token}")
    assert user.id == GOOD_PAYLOAD["sub"]
```

- [ ] **Step 3.6: Run tests**

```bash
uv run pytest tests/test_credits.py tests/test_auth.py -v
```

Expected: 8 (credits) + 15 (auth = 13 prior + 2 new) = 23 passed.

Full suite:
```bash
uv run pytest -q
```

Expected: 390 passed (was 380 + 8 + 2 = 390).

- [ ] **Step 3.7: Commit**

```bash
git add pipeline/credits.py tests/test_credits.py pipeline/auth.py tests/test_auth.py
git commit -m "feat(credits): business logic + signup-grant hook on auth"
```

---

## Task 4: API endpoints — `/billing/balance`, `/billing/plan`, `/billing/transactions`

**Files:**
- Modify: `pipeline/api.py`
- Modify: `tests/test_api.py`

These three GETs are read-only and easy. They unblock the Flutter side to start consuming a balance API even before Stripe is wired.

- [ ] **Step 4.1: Add Pydantic response models in `pipeline/api.py`**

Find the section near the existing `class RunSummary(BaseModel):` (the existing response models). Add the new ones nearby:

```python
class BalanceResponse(BaseModel):
    balance: int


class PlanResponse(BaseModel):
    plan: str                         # 'free' | 'starter' | 'creator' | 'pro'
    current_period_end: str | None    # ISO timestamp, null on 'free'
    balance: int


class TransactionRow(BaseModel):
    id: str
    amount: int
    kind: str
    reference_id: str | None
    description: str | None
    created_at: str
```

- [ ] **Step 4.2: Add the three endpoints**

After the `list_runs` endpoint in `pipeline/api.py`, add:

```python
@app.get(
    "/billing/balance",
    response_model=BalanceResponse,
    dependencies=[Depends(require_user)],
)
def get_balance_endpoint(user: User = Depends(require_user)):
    from pipeline.db import get_balance
    return BalanceResponse(balance=get_balance(user.id))


@app.get(
    "/billing/plan",
    response_model=PlanResponse,
    dependencies=[Depends(require_user)],
)
def get_plan_endpoint(user: User = Depends(require_user)):
    from pipeline.db import get_balance, get_user_profile
    profile = get_user_profile(user.id)
    return PlanResponse(
        plan=(profile.current_plan if profile else "free"),
        current_period_end=(profile.current_period_end if profile else None),
        balance=get_balance(user.id),
    )


@app.get(
    "/billing/transactions",
    response_model=list[TransactionRow],
    dependencies=[Depends(require_user)],
)
def get_transactions_endpoint(
    user: User = Depends(require_user),
    limit: int = 50,
):
    from pipeline.db import list_transactions
    rows = list_transactions(user.id, limit=min(limit, 200))
    return [
        TransactionRow(
            id=t.id, amount=t.amount, kind=t.kind,
            reference_id=t.reference_id, description=t.description,
            created_at=t.created_at,
        )
        for t in rows
    ]
```

Imports are lazy (inside the function) to keep module-level fast even when `SUPABASE_SERVICE_ROLE_KEY` isn't set (e.g. in unit tests).

- [ ] **Step 4.3: Add tests in `tests/test_api.py`**

Append to `tests/test_api.py`:

```python
def test_get_balance_returns_db_value(client_factory, monkeypatch):
    monkeypatch.setattr("pipeline.api.get_balance",
                       lambda uid: 137 if uid == "alice" else 0)
    # Inline import path that the endpoint uses
    monkeypatch.setattr("pipeline.db.get_balance",
                       lambda uid: 137 if uid == "alice" else 0)
    c = client_factory(user_id="alice")
    r = c.get("/billing/balance")
    assert r.status_code == 200
    assert r.json() == {"balance": 137}


def test_get_plan_falls_back_to_free_for_new_users(client_factory, monkeypatch):
    monkeypatch.setattr("pipeline.db.get_user_profile", lambda uid: None)
    monkeypatch.setattr("pipeline.db.get_balance", lambda uid: 0)
    c = client_factory(user_id="alice")
    r = c.get("/billing/plan")
    assert r.status_code == 200
    body = r.json()
    assert body["plan"] == "free"
    assert body["current_period_end"] is None
    assert body["balance"] == 0


def test_get_plan_returns_subscription_for_existing_user(client_factory, monkeypatch):
    from pipeline.db import UserProfile
    monkeypatch.setattr(
        "pipeline.db.get_user_profile",
        lambda uid: UserProfile(
            id=uid, stripe_customer_id="cus_1",
            current_plan="creator", current_period_end="2026-06-11T00:00:00Z",
        ),
    )
    monkeypatch.setattr("pipeline.db.get_balance", lambda uid: 234)
    c = client_factory(user_id="alice")
    body = c.get("/billing/plan").json()
    assert body == {
        "plan": "creator",
        "current_period_end": "2026-06-11T00:00:00Z",
        "balance": 234,
    }


def test_get_transactions_returns_list(client_factory, monkeypatch):
    from pipeline.db import Transaction
    monkeypatch.setattr(
        "pipeline.db.list_transactions",
        lambda uid, limit: [
            Transaction(id="t1", user_id=uid, amount=60, kind="signup_grant",
                        reference_id=None, description=None,
                        created_at="2026-05-11T00:00:00Z"),
            Transaction(id="t2", user_id=uid, amount=-10, kind="run_charge",
                        reference_id="r1", description="1 clip",
                        created_at="2026-05-11T00:01:00Z"),
        ],
    )
    c = client_factory(user_id="alice")
    body = c.get("/billing/transactions").json()
    assert len(body) == 2
    assert body[0]["kind"] == "signup_grant"
    assert body[1]["amount"] == -10
```

- [ ] **Step 4.4: Run tests**

```bash
uv run pytest tests/test_api.py -k billing -v
```

Expected: 4 passed.

Full suite:
```bash
uv run pytest -q
```

Expected: 394 passed (390 + 4 new).

- [ ] **Step 4.5: Commit**

```bash
git add pipeline/api.py tests/test_api.py
git commit -m "feat(api): /billing/{balance,plan,transactions} endpoints"
```

---

## Task 5: Per-clip credit deduction in the worker

**Files:**
- Modify: `pipeline/video.py` (where `generate_clips_chained` lives)
- Modify: `run.py` (pass user_id into the video stage)
- Modify: `tests/test_video.py` (if it exists; otherwise create credit-flow tests in a new file)

**Context:** The worker container has access to `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` (env vars to be added in Task 10). It can write the ledger via the same `pipeline.db` + `pipeline.credits` modules as the API.

- [ ] **Step 5.1: Find the current Veo-submission loop**

```bash
grep -n "submit_video_job\|submit_and_wait_with_retry" pipeline/video.py | head -20
```

You're looking for the function that loops over beats and submits each clip to Kie. Per the spec, deduction happens **per clip, just before submit**.

- [ ] **Step 5.2: Write the failing test in `tests/test_credits_integration.py` (new file)**

```python
"""Integration test for per-clip credit deduction in the worker."""
from __future__ import annotations

import math
from unittest.mock import MagicMock

import pytest

from pipeline.auth import User
from pipeline.credits import InsufficientCredits


def test_per_clip_deduct_then_refund_on_failure(monkeypatch):
    """When a 6-clip run has clip 4 fail, 3 charges + 3 refunds land in the ledger
    — net zero credit change for the failed half, charged for the 3 that worked."""
    user = User(id="u1", email="alice@example.com", role="user")

    deducted: list[int] = []
    refunded: list[int] = []
    monkeypatch.setattr(
        "pipeline.credits.check_or_deduct",
        lambda u, *, amount, run_id, reason: deducted.append(amount) or 999,
    )
    monkeypatch.setattr(
        "pipeline.credits.refund",
        lambda u, *, amount, run_id, reason: refunded.append(amount),
    )

    # Pretend pipeline.video has a helper that walks the beats and does
    # deduct → submit → (refund on raise) per clip.
    from pipeline.video import _charge_and_submit_clip

    submit_results = [True, True, True, False, True, True]  # clip 4 fails
    submit_calls = iter(submit_results)
    def fake_submit(beat, *args, **kwargs):
        ok = next(submit_calls)
        if not ok:
            raise RuntimeError("submit failed")
        return {"url": "https://kie/clip"}

    beats = [{"clip_duration_s": 10.0} for _ in range(6)]
    successes = 0
    for i, beat in enumerate(beats):
        try:
            _charge_and_submit_clip(
                user=user, run_id="run-x", beat=beat, clip_index=i,
                submit_fn=fake_submit,
            )
            successes += 1
        except RuntimeError:
            pass

    assert successes == 5  # clips 1,2,3,5,6 succeed; 4 fails
    assert deducted == [10, 10, 10, 10, 10, 10]  # all 6 deducted up front
    assert refunded == [10]  # only the failed clip refunded


def test_per_clip_charges_use_ceil_of_seconds(monkeypatch):
    """A 9.5-second clip charges 10 credits (ceil), matching how Kie bills."""
    user = User(id="u1", email="alice@example.com", role="user")
    charged: list[int] = []
    monkeypatch.setattr(
        "pipeline.credits.check_or_deduct",
        lambda u, *, amount, run_id, reason: charged.append(amount) or 999,
    )
    monkeypatch.setattr("pipeline.credits.refund", lambda *a, **kw: None)

    from pipeline.video import _charge_and_submit_clip
    _charge_and_submit_clip(
        user=user, run_id="r", beat={"clip_duration_s": 9.5},
        clip_index=0, submit_fn=lambda *a, **kw: {"url": "x"},
    )
    assert charged == [10]
```

- [ ] **Step 5.3: Run — should fail (no `_charge_and_submit_clip` yet)**

```bash
uv run pytest tests/test_credits_integration.py -v
```

Expected: ImportError on `_charge_and_submit_clip`.

- [ ] **Step 5.4: Implement `_charge_and_submit_clip` in `pipeline/video.py`**

At the top of `pipeline/video.py` (near the other helpers), add:

```python
import math
from pipeline.auth import User
from pipeline.credits import check_or_deduct, refund


def _charge_and_submit_clip(
    *,
    user: User,
    run_id: str,
    beat: dict,
    clip_index: int,
    submit_fn,
):
    """Deduct credits for one clip, submit to Veo, refund on failure.

    Charge amount = ceil(clip_duration_s) — matches Kie's "9.5s billed as 10s"
    quirk. Caller passes `submit_fn` so this function is independently testable
    without hitting Kie.
    """
    seconds = math.ceil(float(beat.get("clip_duration_s", 8.0)))
    check_or_deduct(
        user,
        amount=seconds,
        run_id=run_id,
        reason=f"clip {clip_index + 1} ({seconds}s)",
    )
    try:
        return submit_fn(beat, clip_index=clip_index)
    except Exception:
        refund(
            user,
            amount=seconds,
            run_id=run_id,
            reason=f"clip {clip_index + 1} failed",
        )
        raise
```

- [ ] **Step 5.5: Wire `_charge_and_submit_clip` into `generate_clips_chained`**

Find the inner loop in `pipeline/video.generate_clips_chained` that calls `submit_and_wait_with_retry`. Wrap it with `_charge_and_submit_clip`. Concretely:

Before:
```python
for i, beat in enumerate(beats):
    ...
    url = submit_and_wait_with_retry(...)
```

After:
```python
for i, beat in enumerate(beats):
    ...
    url = _charge_and_submit_clip(
        user=user,
        run_id=run_id,
        beat=beat,
        clip_index=i,
        submit_fn=lambda b, clip_index: submit_and_wait_with_retry(...),
    )
```

The exact call site varies (the lambda needs the actual `submit_and_wait_with_retry` args from the caller's scope). Read the function and adapt — the test from Step 5.2 demonstrates the contract.

`generate_clips_chained` needs `user: User` and `run_id: str` parameters added (currently missing). Update its signature and update the one caller (in `run.py`'s `_stage_video_chained`).

- [ ] **Step 5.6: Wire `--user-id` arg through to the video stage**

In `run.py`, find `_stage_video_chained`. It receives `args` (the argparse Namespace). Pass `args.user_id` through:

```python
def _stage_video_chained(...):
    ...
    user = User(id=args.user_id, email=None, role=("service" if args.user_id == "admin" else "user"))
    generate_clips_chained(
        ...,
        user=user,
        run_id=run_dir.name,
    )
```

Add the import at top of `run.py`:
```python
from pipeline.auth import User
```

- [ ] **Step 5.7: Run tests**

```bash
uv run pytest tests/test_credits_integration.py tests/test_video.py -v
```

Expected: 2 (new) + existing test_video tests pass.

Full suite:
```bash
uv run pytest -q
```

Expected: 396 passed (394 + 2).

- [ ] **Step 5.8: Commit**

```bash
git add pipeline/video.py run.py tests/test_credits_integration.py
git commit -m "feat(worker): per-clip credit deduct + refund on Veo failure"
```

---

## Task 6: API pre-flight credit check on run creation (402 + paywall hint)

**Files:**
- Modify: `pipeline/api.py`
- Modify: `tests/test_api.py`

The two endpoints that kick off a paid run are `/runs/freeform` (creates from a premise) and `/runs/from-script` (creates from pasted text). Before spawning the worker, estimate the cost from the request body and reject with **402 Payment Required** if the user can't afford it.

- [ ] **Step 6.1: Add a cost estimator near the existing `_cost_estimate_usd` helper**

In `pipeline/api.py`, near the existing cost estimator, add:

```python
def _estimate_credits_for_request(req) -> int:
    """Estimate the credits a request will consume.

    For freeform requests we use `max_beats * default_clip_seconds` (8s)
    since we don't have a concrete script yet. For from-script requests
    we sum the parsed beat durations. Caller treats this as a worst-case
    pre-flight; actual charge happens per-clip in the worker.
    """
    import math
    if hasattr(req, "beats") and req.beats:
        return sum(math.ceil(float(getattr(b, "clip_duration_s", 8.0)))
                   for b in req.beats)
    max_beats = getattr(req, "max_beats", None) or 8
    return int(max_beats) * 8
```

- [ ] **Step 6.2: Add a 402 helper that surfaces the paywall hint**

Near `_hint_for_error`, add:

```python
def _raise_402_insufficient_credits(balance: int, required: int) -> None:
    """Raise an HTTPException with the user-friendly hint we already use
    elsewhere when upstream credits run out."""
    raise HTTPException(
        status_code=status.HTTP_402_PAYMENT_REQUIRED,
        detail={
            "code": "insufficient_credits",
            "message": (
                "You don't have enough credits for this video. "
                "Top up your plan to continue — your script and characters "
                "will be saved."
            ),
            "balance": balance,
            "required": required,
        },
    )
```

- [ ] **Step 6.3: Apply the check in both run-creation endpoints**

In `create_freeform_run` and `create_run_from_script`, add at the top of the function body (after the request validation, before any disk writes or `_SPAWN_FN` calls):

```python
    # Skip the credit check for the service token / CLI users.
    if user.role != "service":
        from pipeline.db import get_balance
        required = _estimate_credits_for_request(req)
        balance = get_balance(user.id)
        if balance < required:
            _raise_402_insufficient_credits(balance, required)
```

- [ ] **Step 6.4: Add tests**

Append to `tests/test_api.py`:

```python
def test_freeform_run_returns_402_when_user_has_no_credits(client_factory, monkeypatch):
    """A non-service user with zero credits hits the paywall instead of spawning the worker."""
    monkeypatch.setattr("pipeline.db.get_balance", lambda uid: 0)
    # Spawn must NOT be called
    spawned: list = []
    monkeypatch.setattr(
        "pipeline.api._SPAWN_FN",
        lambda args, run_dir: spawned.append(args) or 999,
    )
    c = client_factory(user_id="alice", role="user")
    r = c.post("/runs/freeform", json={
        "theme": "folkloric",
        "premise": "بئر قديم",
        "max_beats": 8,
    })
    assert r.status_code == 402
    detail = r.json()["detail"]
    assert detail["code"] == "insufficient_credits"
    assert detail["balance"] == 0
    assert detail["required"] == 64  # 8 beats × 8s default
    assert spawned == []


def test_freeform_run_passes_when_balance_sufficient(client_factory, monkeypatch, tmp_path):
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path))
    monkeypatch.setattr("pipeline.db.get_balance", lambda uid: 100)
    spawned: list = []
    monkeypatch.setattr(
        "pipeline.api._SPAWN_FN",
        lambda args, run_dir: spawned.append(args) or 4242,
    )
    c = client_factory(user_id="alice", role="user")
    r = c.post("/runs/freeform", json={
        "theme": "folkloric",
        "premise": "بئر قديم",
        "max_beats": 8,
    })
    assert r.status_code == 200
    assert len(spawned) == 1


def test_freeform_run_bypasses_credit_check_for_service_token(client_factory, monkeypatch, tmp_path):
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path))
    # Even if we say balance=0, the service token should pass through.
    monkeypatch.setattr("pipeline.db.get_balance", lambda uid: 0)
    monkeypatch.setattr("pipeline.api._SPAWN_FN", lambda args, run_dir: 4242)
    c = client_factory(user_id="admin", role="service")
    r = c.post("/runs/freeform", json={
        "theme": "folkloric",
        "premise": "بئر قديم",
        "max_beats": 8,
    })
    assert r.status_code == 200
```

- [ ] **Step 6.5: Run + commit**

```bash
uv run pytest tests/test_api.py -k "402 or credit_check or service_token" -v
```

Expected: 3 passed (plus any related).

Full suite:
```bash
uv run pytest -q
```

Expected: 399 passed (396 + 3).

```bash
git add pipeline/api.py tests/test_api.py
git commit -m "feat(api): pre-flight credit check on /runs/freeform + /runs/from-script (402)"
```

---

## Task 7: `pipeline/stripe_billing.py` — Stripe SDK wrapper

**Files:**
- Modify: `pyproject.toml`
- Create: `pipeline/stripe_billing.py`
- Create: `tests/test_stripe_billing.py`

- [ ] **Step 7.1: Add `stripe` to dependencies**

In `pyproject.toml`, in the `dependencies` array, add (after `supabase>=2.6`):

```toml
    # Stripe Python SDK for Hosted Checkout, Customer Portal, and webhook
    # signature verification. We never build payment UIs ourselves — Stripe
    # hosts all card collection / 3DS / SCA flows.
    "stripe>=10.0",
```

Then `uv lock && uv sync`.

- [ ] **Step 7.2: Implement `pipeline/stripe_billing.py`**

```python
"""Stripe SDK wrapper.

Two responsibilities:
  1. Build Stripe-hosted Checkout / Portal URLs that the Flutter app opens
     in a new tab to collect payment.
  2. Verify + dispatch incoming Stripe webhooks (no auth on that endpoint;
     trust is via the Stripe-Signature header).

The rest of the codebase never imports `stripe` directly — it goes through
this module.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import stripe

from pipeline.auth import User
from pipeline.credits import PLAN_GRANTS, TOPUP_PACKS
from pipeline.db import get_user_profile, record_transaction, upsert_user_profile


# Price IDs come from the Stripe dashboard. setup-cloud-run.sh pushes them
# to Secret Manager from .env; read lazily so tests can patch.

def _api_key() -> str:
    key = os.environ.get("STRIPE_SECRET_KEY", "").strip()
    if not key:
        raise RuntimeError("STRIPE_SECRET_KEY not configured")
    return key


def _webhook_secret() -> str:
    s = os.environ.get("STRIPE_WEBHOOK_SECRET", "").strip()
    if not s:
        raise RuntimeError("STRIPE_WEBHOOK_SECRET not configured")
    return s


def _plan_price_id(plan: str) -> str:
    env_key = f"STRIPE_PRICE_{plan.upper()}"
    pid = os.environ.get(env_key, "").strip()
    if not pid:
        raise RuntimeError(f"{env_key} not configured")
    return pid


def _pack_price_id(pack: str) -> str:
    env_key = f"STRIPE_PRICE_{pack.upper()}"  # e.g. STRIPE_PRICE_TOPUP_30
    pid = os.environ.get(env_key, "").strip()
    if not pid:
        raise RuntimeError(f"{env_key} not configured")
    return pid


def ensure_customer(user: User) -> str:
    """Return the Stripe customer_id for this user, creating one on first call."""
    stripe.api_key = _api_key()
    profile = get_user_profile(user.id)
    if profile and profile.stripe_customer_id:
        return profile.stripe_customer_id
    customer = stripe.Customer.create(
        email=user.email or None,
        metadata={"user_id": user.id},
    )
    upsert_user_profile(user.id, stripe_customer_id=customer.id)
    return customer.id


def create_subscription_checkout(user: User, plan: str, success_url: str, cancel_url: str) -> str:
    """Returns a Stripe Checkout URL for a new subscription."""
    if plan not in PLAN_GRANTS:
        raise ValueError(f"unknown plan: {plan!r}")
    stripe.api_key = _api_key()
    customer_id = ensure_customer(user)
    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        line_items=[{"price": _plan_price_id(plan), "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"user_id": user.id, "plan": plan},
        # CRITICAL: must duplicate metadata onto the subscription so the
        # invoice.payment_succeeded webhook can find the user.
        subscription_data={"metadata": {"user_id": user.id, "plan": plan}},
    )
    return session.url


def create_topup_checkout(user: User, pack: str, success_url: str, cancel_url: str) -> str:
    """Returns a Stripe Checkout URL for a one-time top-up pack."""
    if pack not in TOPUP_PACKS:
        raise ValueError(f"unknown pack: {pack!r}")
    stripe.api_key = _api_key()
    customer_id = ensure_customer(user)
    session = stripe.checkout.Session.create(
        mode="payment",
        customer=customer_id,
        line_items=[{"price": _pack_price_id(pack), "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"user_id": user.id, "pack": pack},
    )
    return session.url


def create_portal_session(user: User, return_url: str) -> str:
    """Returns a Stripe Customer Portal URL for self-serve subscription management."""
    stripe.api_key = _api_key()
    customer_id = ensure_customer(user)
    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=return_url,
    )
    return session.url


@dataclass(frozen=True)
class WebhookOutcome:
    event_type: str
    handled: bool
    note: str


def handle_webhook(raw_body: bytes, signature: str) -> WebhookOutcome:
    """Verify the Stripe-Signature header, decode, and dispatch.

    Raises stripe.SignatureVerificationError on bad signatures (caller should
    return 400). Logs and returns for unhandled event types.
    """
    stripe.api_key = _api_key()
    event = stripe.Webhook.construct_event(
        payload=raw_body,
        sig_header=signature,
        secret=_webhook_secret(),
    )
    et = event["type"]
    data = event["data"]["object"]

    if et == "checkout.session.completed":
        return _on_checkout_completed(data)
    if et == "invoice.payment_succeeded":
        return _on_invoice_paid(data)
    if et == "customer.subscription.updated":
        return _on_subscription_updated(data)
    if et == "customer.subscription.deleted":
        return _on_subscription_deleted(data)
    return WebhookOutcome(event_type=et, handled=False, note="ignored")


def _on_checkout_completed(session) -> WebhookOutcome:
    user_id = (session.get("metadata") or {}).get("user_id")
    mode = session.get("mode")
    if not user_id:
        return WebhookOutcome("checkout.session.completed", False, "no user_id metadata")

    if mode == "subscription":
        # First-time subscriber — link the customer id (already done by ensure_customer,
        # but safe to refresh). Credit grant happens on invoice.payment_succeeded.
        customer_id = session.get("customer")
        if customer_id:
            upsert_user_profile(user_id, stripe_customer_id=customer_id)
        return WebhookOutcome("checkout.session.completed", True, "subscription linked")

    if mode == "payment":
        pack = (session.get("metadata") or {}).get("pack")
        if pack not in TOPUP_PACKS:
            return WebhookOutcome("checkout.session.completed", False, f"unknown pack {pack!r}")
        record_transaction(
            user_id=user_id,
            amount=TOPUP_PACKS[pack],
            kind="topup",
            reference_id=session.get("id"),
            description=f"Top-up pack ({pack})",
        )
        return WebhookOutcome("checkout.session.completed", True, f"+{TOPUP_PACKS[pack]} credits")

    return WebhookOutcome("checkout.session.completed", False, f"unknown mode {mode!r}")


def _on_invoice_paid(invoice) -> WebhookOutcome:
    # Invoices for subscription renewals carry subscription metadata via the
    # `subscription` field — but we already echo user_id onto subscription
    # metadata at checkout time, so we can read it from the invoice's
    # `lines.data[0].metadata`. Stripe also surfaces it on the subscription
    # itself; resolve from the subscription object for robustness.
    sub_id = invoice.get("subscription")
    if not sub_id:
        return WebhookOutcome("invoice.payment_succeeded", False, "no subscription id")
    subscription = stripe.Subscription.retrieve(sub_id)
    user_id = (subscription.get("metadata") or {}).get("user_id")
    plan = (subscription.get("metadata") or {}).get("plan")
    if not user_id or plan not in PLAN_GRANTS:
        return WebhookOutcome("invoice.payment_succeeded", False,
                              f"missing user_id or plan (plan={plan!r})")

    record_transaction(
        user_id=user_id,
        amount=PLAN_GRANTS[plan],
        kind="subscription_renewal",
        reference_id=invoice.get("id"),
        description=f"{plan.capitalize()} plan renewal",
    )
    upsert_user_profile(
        user_id,
        current_plan=plan,
        current_period_end=_iso(subscription.get("current_period_end")),
    )
    return WebhookOutcome("invoice.payment_succeeded", True,
                          f"+{PLAN_GRANTS[plan]} for {plan}")


def _on_subscription_updated(subscription) -> WebhookOutcome:
    user_id = (subscription.get("metadata") or {}).get("user_id")
    plan = (subscription.get("metadata") or {}).get("plan")
    if not user_id:
        return WebhookOutcome("customer.subscription.updated", False, "no user_id metadata")
    upsert_user_profile(
        user_id,
        current_plan=(plan if plan in PLAN_GRANTS else "free"),
        current_period_end=_iso(subscription.get("current_period_end")),
    )
    return WebhookOutcome("customer.subscription.updated", True, f"plan={plan}")


def _on_subscription_deleted(subscription) -> WebhookOutcome:
    user_id = (subscription.get("metadata") or {}).get("user_id")
    if not user_id:
        return WebhookOutcome("customer.subscription.deleted", False, "no user_id metadata")
    upsert_user_profile(user_id, current_plan="free", current_period_end=None)
    return WebhookOutcome("customer.subscription.deleted", True, "plan reset to free")


def _iso(unix_ts) -> str | None:
    if not unix_ts:
        return None
    from datetime import datetime, timezone
    return datetime.fromtimestamp(int(unix_ts), tz=timezone.utc).isoformat()
```

- [ ] **Step 7.3: Write tests in `tests/test_stripe_billing.py`**

```python
"""Tests for pipeline.stripe_billing — Stripe SDK wrapper, all mocked."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from pipeline.auth import User
from pipeline.stripe_billing import (
    create_portal_session,
    create_subscription_checkout,
    create_topup_checkout,
    ensure_customer,
    handle_webhook,
)


@pytest.fixture
def stripe_env(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_x")
    monkeypatch.setenv("STRIPE_PRICE_STARTER", "price_starter")
    monkeypatch.setenv("STRIPE_PRICE_CREATOR", "price_creator")
    monkeypatch.setenv("STRIPE_PRICE_PRO", "price_pro")
    monkeypatch.setenv("STRIPE_PRICE_TOPUP_30", "price_t30")
    monkeypatch.setenv("STRIPE_PRICE_TOPUP_100", "price_t100")
    monkeypatch.setenv("STRIPE_PRICE_TOPUP_300", "price_t300")


@pytest.fixture
def mock_db(monkeypatch):
    db_state = {"profiles": {}, "transactions": []}
    monkeypatch.setattr(
        "pipeline.stripe_billing.get_user_profile",
        lambda uid: SimpleNamespace(
            id=uid,
            stripe_customer_id=db_state["profiles"].get(uid, {}).get("stripe_customer_id"),
            current_plan=db_state["profiles"].get(uid, {}).get("current_plan", "free"),
            current_period_end=None,
        ) if uid in db_state["profiles"] else None,
    )
    monkeypatch.setattr(
        "pipeline.stripe_billing.upsert_user_profile",
        lambda uid, **f: db_state["profiles"].setdefault(uid, {}).update(f) or None,
    )
    monkeypatch.setattr(
        "pipeline.stripe_billing.record_transaction",
        lambda **kw: db_state["transactions"].append(kw),
    )
    return db_state


def _user():
    return User(id="u1", email="alice@example.com", role="user")


def test_ensure_customer_creates_when_missing(stripe_env, mock_db, monkeypatch):
    fake_customer = SimpleNamespace(id="cus_new")
    monkeypatch.setattr("pipeline.stripe_billing.stripe.Customer.create",
                       lambda **kw: fake_customer)
    cid = ensure_customer(_user())
    assert cid == "cus_new"
    assert mock_db["profiles"]["u1"]["stripe_customer_id"] == "cus_new"


def test_ensure_customer_reuses_existing(stripe_env, mock_db, monkeypatch):
    mock_db["profiles"]["u1"] = {"stripe_customer_id": "cus_old"}
    monkeypatch.setattr("pipeline.stripe_billing.stripe.Customer.create",
                       lambda **kw: pytest.fail("should not create"))
    assert ensure_customer(_user()) == "cus_old"


def test_create_subscription_checkout_url(stripe_env, mock_db, monkeypatch):
    monkeypatch.setattr("pipeline.stripe_billing.stripe.Customer.create",
                       lambda **kw: SimpleNamespace(id="cus_x"))
    captured = {}
    def fake_create(**kw):
        captured.update(kw)
        return SimpleNamespace(url="https://checkout.stripe.com/x")
    monkeypatch.setattr("pipeline.stripe_billing.stripe.checkout.Session.create", fake_create)

    url = create_subscription_checkout(_user(), "starter",
                                       "https://app/success", "https://app/cancel")
    assert url == "https://checkout.stripe.com/x"
    assert captured["mode"] == "subscription"
    assert captured["line_items"][0]["price"] == "price_starter"
    # Critical: metadata must be on the subscription too
    assert captured["subscription_data"]["metadata"]["user_id"] == "u1"


def test_create_subscription_checkout_rejects_unknown_plan(stripe_env, mock_db):
    with pytest.raises(ValueError, match="unknown plan"):
        create_subscription_checkout(_user(), "elite", "u1", "u2")


def test_create_topup_checkout_url(stripe_env, mock_db, monkeypatch):
    monkeypatch.setattr("pipeline.stripe_billing.stripe.Customer.create",
                       lambda **kw: SimpleNamespace(id="cus_x"))
    captured = {}
    def fake_create(**kw):
        captured.update(kw)
        return SimpleNamespace(url="https://checkout.stripe.com/y")
    monkeypatch.setattr("pipeline.stripe_billing.stripe.checkout.Session.create", fake_create)

    url = create_topup_checkout(_user(), "topup_100",
                                "https://app/success", "https://app/cancel")
    assert url == "https://checkout.stripe.com/y"
    assert captured["mode"] == "payment"
    assert captured["line_items"][0]["price"] == "price_topup_100"


def test_handle_webhook_topup_grants_credits(stripe_env, mock_db, monkeypatch):
    fake_event = {
        "type": "checkout.session.completed",
        "data": {"object": {
            "id": "cs_abc",
            "mode": "payment",
            "metadata": {"user_id": "u1", "pack": "topup_30"},
        }},
    }
    monkeypatch.setattr("pipeline.stripe_billing.stripe.Webhook.construct_event",
                       lambda **kw: fake_event)
    outcome = handle_webhook(b"{}", "sig=anything")
    assert outcome.handled
    assert mock_db["transactions"][-1] == {
        "user_id": "u1", "amount": 30, "kind": "topup",
        "reference_id": "cs_abc", "description": "Top-up pack (topup_30)",
    }


def test_handle_webhook_subscription_renewal_grants(stripe_env, mock_db, monkeypatch):
    fake_event = {
        "type": "invoice.payment_succeeded",
        "data": {"object": {"id": "inv_1", "subscription": "sub_1"}},
    }
    monkeypatch.setattr(
        "pipeline.stripe_billing.stripe.Subscription.retrieve",
        lambda sid: {
            "id": sid,
            "metadata": {"user_id": "u1", "plan": "creator"},
            "current_period_end": 1788000000,
        },
    )
    monkeypatch.setattr("pipeline.stripe_billing.stripe.Webhook.construct_event",
                       lambda **kw: fake_event)
    outcome = handle_webhook(b"{}", "sig")
    assert outcome.handled
    last_tx = mock_db["transactions"][-1]
    assert last_tx["amount"] == 250  # PLAN_GRANTS["creator"]
    assert last_tx["kind"] == "subscription_renewal"
    assert mock_db["profiles"]["u1"]["current_plan"] == "creator"


def test_handle_webhook_subscription_deleted_resets_plan(stripe_env, mock_db, monkeypatch):
    mock_db["profiles"]["u1"] = {"current_plan": "starter"}
    fake_event = {
        "type": "customer.subscription.deleted",
        "data": {"object": {"metadata": {"user_id": "u1"}}},
    }
    monkeypatch.setattr("pipeline.stripe_billing.stripe.Webhook.construct_event",
                       lambda **kw: fake_event)
    outcome = handle_webhook(b"{}", "sig")
    assert outcome.handled
    assert mock_db["profiles"]["u1"]["current_plan"] == "free"


def test_handle_webhook_unknown_event_is_ignored(stripe_env, mock_db, monkeypatch):
    monkeypatch.setattr("pipeline.stripe_billing.stripe.Webhook.construct_event",
                       lambda **kw: {"type": "ping", "data": {"object": {}}})
    outcome = handle_webhook(b"{}", "sig")
    assert outcome.handled is False
```

- [ ] **Step 7.4: Run + commit**

```bash
uv run pytest tests/test_stripe_billing.py -v
```

Expected: 9 passed.

Full suite:
```bash
uv run pytest -q
```

Expected: 408 passed (399 + 9).

```bash
git add pyproject.toml uv.lock pipeline/stripe_billing.py tests/test_stripe_billing.py
git commit -m "feat(stripe): SDK wrapper — checkout, portal, webhook handler"
```

---

## Task 8: API endpoints — `/billing/checkout-subscription`, `/billing/checkout-topup`, `/billing/portal`

**Files:**
- Modify: `pipeline/api.py`
- Modify: `tests/test_api.py`

- [ ] **Step 8.1: Add request models in `pipeline/api.py`**

Near the other Pydantic models:

```python
class CheckoutSubscriptionRequest(BaseModel):
    plan: str = Field(..., description="'starter' | 'creator' | 'pro'")
    success_url: str
    cancel_url: str


class CheckoutTopupRequest(BaseModel):
    pack: str = Field(..., description="'topup_30' | 'topup_100' | 'topup_300'")
    success_url: str
    cancel_url: str


class PortalRequest(BaseModel):
    return_url: str


class CheckoutResponse(BaseModel):
    url: str
```

- [ ] **Step 8.2: Add the three endpoints**

After the existing `/billing/transactions` endpoint:

```python
@app.post(
    "/billing/checkout-subscription",
    response_model=CheckoutResponse,
    dependencies=[Depends(require_user)],
)
def billing_checkout_subscription(
    req: CheckoutSubscriptionRequest,
    user: User = Depends(require_user),
):
    if user.role == "service":
        raise HTTPException(400, "service tokens have no subscription")
    from pipeline.stripe_billing import create_subscription_checkout
    try:
        url = create_subscription_checkout(user, req.plan, req.success_url, req.cancel_url)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    return CheckoutResponse(url=url)


@app.post(
    "/billing/checkout-topup",
    response_model=CheckoutResponse,
    dependencies=[Depends(require_user)],
)
def billing_checkout_topup(
    req: CheckoutTopupRequest,
    user: User = Depends(require_user),
):
    if user.role == "service":
        raise HTTPException(400, "service tokens have no top-ups")
    from pipeline.stripe_billing import create_topup_checkout
    try:
        url = create_topup_checkout(user, req.pack, req.success_url, req.cancel_url)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    return CheckoutResponse(url=url)


@app.post(
    "/billing/portal",
    response_model=CheckoutResponse,
    dependencies=[Depends(require_user)],
)
def billing_portal(req: PortalRequest, user: User = Depends(require_user)):
    if user.role == "service":
        raise HTTPException(400, "service tokens have no portal")
    from pipeline.stripe_billing import create_portal_session
    url = create_portal_session(user, req.return_url)
    return CheckoutResponse(url=url)
```

- [ ] **Step 8.3: Add tests**

Append to `tests/test_api.py`:

```python
def test_checkout_subscription_returns_url(client_factory, monkeypatch):
    monkeypatch.setattr(
        "pipeline.stripe_billing.create_subscription_checkout",
        lambda user, plan, s, c: f"https://checkout/{plan}",
    )
    c = client_factory(user_id="alice", role="user")
    r = c.post("/billing/checkout-subscription", json={
        "plan": "starter",
        "success_url": "https://app/success",
        "cancel_url": "https://app/cancel",
    })
    assert r.status_code == 200
    assert r.json() == {"url": "https://checkout/starter"}


def test_checkout_topup_returns_url(client_factory, monkeypatch):
    monkeypatch.setattr(
        "pipeline.stripe_billing.create_topup_checkout",
        lambda user, pack, s, c: f"https://checkout/pack/{pack}",
    )
    c = client_factory(user_id="alice", role="user")
    r = c.post("/billing/checkout-topup", json={
        "pack": "topup_100",
        "success_url": "https://app/success",
        "cancel_url": "https://app/cancel",
    })
    assert r.status_code == 200
    assert r.json()["url"].endswith("/pack/topup_100")


def test_portal_returns_url(client_factory, monkeypatch):
    monkeypatch.setattr(
        "pipeline.stripe_billing.create_portal_session",
        lambda user, return_url: f"https://portal?return={return_url}",
    )
    c = client_factory(user_id="alice", role="user")
    r = c.post("/billing/portal", json={"return_url": "https://app/home"})
    assert r.status_code == 200
    assert "portal" in r.json()["url"]


def test_billing_endpoints_reject_service_tokens(client_factory):
    c = client_factory(user_id="admin", role="service")
    for path, body in [
        ("/billing/checkout-subscription",
         {"plan": "starter", "success_url": "x", "cancel_url": "y"}),
        ("/billing/checkout-topup",
         {"pack": "topup_30", "success_url": "x", "cancel_url": "y"}),
        ("/billing/portal", {"return_url": "x"}),
    ]:
        r = c.post(path, json=body)
        assert r.status_code == 400, f"{path} should reject service token"
```

- [ ] **Step 8.4: Run + commit**

```bash
uv run pytest tests/test_api.py -k "checkout or portal or service_token" -v
```

Expected: 4 (new) + existing.

Full suite:
```bash
uv run pytest -q
```

Expected: 412 passed (408 + 4).

```bash
git add pipeline/api.py tests/test_api.py
git commit -m "feat(api): /billing/{checkout-*,portal} endpoints"
```

---

## Task 9: `/stripe/webhook` endpoint

**Files:**
- Modify: `pipeline/api.py`
- Modify: `tests/test_api.py`

This endpoint has **no auth dependency** — Stripe → us, identity proved by the `Stripe-Signature` header. We read the raw request body (not JSON-decoded by FastAPI) because the signature is computed over the exact bytes.

- [ ] **Step 9.1: Add the endpoint**

In `pipeline/api.py`, add (near the bottom of the route definitions, after `/billing/portal`):

```python
from fastapi import Request

@app.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    """Stripe → us. No bearer auth; signature is the proof.

    Returns 200 even for ignored event types so Stripe doesn't keep retrying;
    400 only for bad signatures (treat as malicious / misconfigured).
    """
    raw = await request.body()
    signature = request.headers.get("stripe-signature", "")
    from pipeline.stripe_billing import handle_webhook
    import stripe as _stripe
    try:
        outcome = handle_webhook(raw, signature)
    except _stripe.SignatureVerificationError:
        raise HTTPException(400, "invalid signature")
    return {"received": True, "handled": outcome.handled, "note": outcome.note}
```

- [ ] **Step 9.2: Add tests**

Append to `tests/test_api.py`:

```python
def test_stripe_webhook_calls_handler(client_factory, monkeypatch):
    captured = {}
    from pipeline.stripe_billing import WebhookOutcome
    def fake_handle(raw, sig):
        captured["raw"] = raw
        captured["sig"] = sig
        return WebhookOutcome(event_type="checkout.session.completed",
                              handled=True, note="ok")
    monkeypatch.setattr("pipeline.stripe_billing.handle_webhook", fake_handle)
    # No auth needed for the webhook
    from fastapi.testclient import TestClient
    from pipeline.api import app
    c = TestClient(app)
    r = c.post("/stripe/webhook",
               content=b'{"event":"x"}',
               headers={"stripe-signature": "sig=test"})
    assert r.status_code == 200
    assert r.json()["received"] is True
    assert r.json()["handled"] is True
    assert captured["raw"] == b'{"event":"x"}'
    assert captured["sig"] == "sig=test"


def test_stripe_webhook_rejects_bad_signature(client_factory, monkeypatch):
    import stripe
    def fake_handle(raw, sig):
        raise stripe.SignatureVerificationError("bad sig", sig)
    monkeypatch.setattr("pipeline.stripe_billing.handle_webhook", fake_handle)
    from fastapi.testclient import TestClient
    from pipeline.api import app
    c = TestClient(app)
    r = c.post("/stripe/webhook", content=b"{}", headers={"stripe-signature": "wrong"})
    assert r.status_code == 400
```

- [ ] **Step 9.3: Run + commit**

```bash
uv run pytest tests/test_api.py::test_stripe_webhook_calls_handler tests/test_api.py::test_stripe_webhook_rejects_bad_signature -v
```

Expected: 2 passed.

```bash
uv run pytest -q
```

Expected: 414 passed (412 + 2).

```bash
git add pipeline/api.py tests/test_api.py
git commit -m "feat(api): /stripe/webhook endpoint (signature-verified, no bearer auth)"
```

---

## Task 10: Cloud Run config — Stripe secrets + service-role key on Job

**Files:**
- Modify: `deploy/cloud-run-service.yaml`
- Modify: `deploy/cloud-run-job.yaml`
- Modify: `scripts/setup-cloud-run.sh`

**Stripe-side prereq (MANUAL — do this before Step 10.4):** Set up your Stripe account in **test mode** for now:

1. Sign in at https://dashboard.stripe.com (use Test mode toggle, top-left)
2. **Products → Add product** — create 3 recurring products:
   - "Faceless Starter" — recurring, $9/month, copy the **price ID** (`price_...`)
   - "Faceless Creator" — recurring, $29/month
   - "Faceless Pro" — recurring, $79/month
3. **Products → Add product** — create 3 one-time products:
   - "Faceless Pack S" — one-time, $5, copy price ID
   - "Faceless Pack M" — one-time, $15
   - "Faceless Pack L" — one-time, $40
4. **Settings → Billing → Customer Portal** — toggle on: cancel subscription, switch plans, view invoices. Save.
5. **Developers → Webhooks → Add endpoint**:
   - Endpoint URL: `https://faceless-api-uplzdtffeq-uc.a.run.app/stripe/webhook`
   - Events to send: `checkout.session.completed`, `invoice.payment_succeeded`, `customer.subscription.updated`, `customer.subscription.deleted`
   - Copy the **signing secret** (`whsec_...`)
6. **Developers → API keys** — copy the **secret key** (`sk_test_...`)

Paste all 8 values into `.env`:

```bash
export STRIPE_SECRET_KEY=sk_test_...
export STRIPE_WEBHOOK_SECRET=whsec_...
export STRIPE_PRICE_STARTER=price_...
export STRIPE_PRICE_CREATOR=price_...
export STRIPE_PRICE_PRO=price_...
export STRIPE_PRICE_TOPUP_30=price_...
export STRIPE_PRICE_TOPUP_100=price_...
export STRIPE_PRICE_TOPUP_300=price_...
```

- [ ] **Step 10.1: Update `scripts/setup-cloud-run.sh` to push new secrets**

Find the block in `scripts/setup-cloud-run.sh` that lists `write_secret ...` calls (currently has 5 entries from B2). Add:

```bash
write_secret "stripe-secret-key" "${STRIPE_SECRET_KEY:-}"
write_secret "stripe-webhook-secret" "${STRIPE_WEBHOOK_SECRET:-}"
```

The price IDs are not secrets (they're prefixed `price_` and freely visible in Stripe dashboard / API responses). Leave them as plain env vars in the YAML.

- [ ] **Step 10.2: Update `deploy/cloud-run-service.yaml`**

In the `env:` block of the container, add (after the existing `SUPABASE_JWT_SECRET` entry):

```yaml
            - name: SUPABASE_SERVICE_ROLE_KEY
              valueFrom:
                secretKeyRef:
                  name: supabase-service-role-key
                  key: latest
            - name: STRIPE_SECRET_KEY
              valueFrom:
                secretKeyRef:
                  name: stripe-secret-key
                  key: latest
            - name: STRIPE_WEBHOOK_SECRET
              valueFrom:
                secretKeyRef:
                  name: stripe-webhook-secret
                  key: latest
            - name: STRIPE_PRICE_STARTER
              value: ${STRIPE_PRICE_STARTER}
            - name: STRIPE_PRICE_CREATOR
              value: ${STRIPE_PRICE_CREATOR}
            - name: STRIPE_PRICE_PRO
              value: ${STRIPE_PRICE_PRO}
            - name: STRIPE_PRICE_TOPUP_30
              value: ${STRIPE_PRICE_TOPUP_30}
            - name: STRIPE_PRICE_TOPUP_100
              value: ${STRIPE_PRICE_TOPUP_100}
            - name: STRIPE_PRICE_TOPUP_300
              value: ${STRIPE_PRICE_TOPUP_300}
```

Add `${STRIPE_PRICE_*}` substitution to `scripts/setup-cloud-run.sh`'s `sed` command for the YAML — find the block:

```bash
sed -e "s|\\\${PROJECT_ID}|${PROJECT_ID}|g" \
    -e "s|\\\${BUCKET_NAME}|${BUCKET_NAME}|g" \
    deploy/cloud-run-service.yaml > "$tmpdir/service.yaml"
```

Extend it to substitute the price IDs:

```bash
sed -e "s|\\\${PROJECT_ID}|${PROJECT_ID}|g" \
    -e "s|\\\${BUCKET_NAME}|${BUCKET_NAME}|g" \
    -e "s|\\\${STRIPE_PRICE_STARTER}|${STRIPE_PRICE_STARTER:-}|g" \
    -e "s|\\\${STRIPE_PRICE_CREATOR}|${STRIPE_PRICE_CREATOR:-}|g" \
    -e "s|\\\${STRIPE_PRICE_PRO}|${STRIPE_PRICE_PRO:-}|g" \
    -e "s|\\\${STRIPE_PRICE_TOPUP_30}|${STRIPE_PRICE_TOPUP_30:-}|g" \
    -e "s|\\\${STRIPE_PRICE_TOPUP_100}|${STRIPE_PRICE_TOPUP_100:-}|g" \
    -e "s|\\\${STRIPE_PRICE_TOPUP_300}|${STRIPE_PRICE_TOPUP_300:-}|g" \
    deploy/cloud-run-service.yaml > "$tmpdir/service.yaml"
```

- [ ] **Step 10.3: Update `deploy/cloud-run-job.yaml`**

The worker only needs the Supabase service-role key (to write the ledger). It does NOT need Stripe. Add to the Job's `env:` block:

```yaml
              - name: SUPABASE_URL
                value: https://eorpqwvjbljsjlzvmvom.supabase.co
              - name: SUPABASE_SERVICE_ROLE_KEY
                valueFrom:
                  secretKeyRef:
                    name: supabase-service-role-key
                    key: latest
```

- [ ] **Step 10.4: Deploy via `./scripts/build-and-push.sh`**

```bash
./scripts/build-and-push.sh
```

Expected: build + push + service replace + job replace, all succeed. Service URL printed at the end.

- [ ] **Step 10.5: Smoke test against the deployed service**

```bash
SERVICE_URL=https://faceless-api-uplzdtffeq-uc.a.run.app
set -a && source .env && set +a

# 1) Balance with service token — should be 0 (admin has no profile + no ledger)
curl -s -H "Authorization: Bearer $FACELESS_API_TOKEN" $SERVICE_URL/billing/balance

# 2) Plan with service token
curl -s -H "Authorization: Bearer $FACELESS_API_TOKEN" $SERVICE_URL/billing/plan
```

Expected:
- `/billing/balance` returns `{"balance": 0}` (since `admin` has no rows in `credit_transactions`).
- `/billing/plan` returns `{"plan": "free", "current_period_end": null, "balance": 0}`.

- [ ] **Step 10.6: Commit**

```bash
git add deploy/cloud-run-service.yaml deploy/cloud-run-job.yaml scripts/setup-cloud-run.sh
git commit -m "feat(deploy): wire Stripe secrets + Supabase service-role onto Cloud Run"
```

---

## Task 11: Flutter API client — billing methods + InsufficientCreditsException

**Files:**
- Modify: `lib/api/client.dart`
- Modify: `lib/api/models.dart`

- [ ] **Step 11.1: Add models in `lib/api/models.dart`**

```dart
class Balance {
  final int balance;
  Balance({required this.balance});
  factory Balance.fromJson(Map<String, dynamic> j) => Balance(balance: j['balance'] as int);
}

class PlanInfo {
  final String plan;            // 'free' | 'starter' | 'creator' | 'pro'
  final String? currentPeriodEnd;
  final int balance;
  PlanInfo({required this.plan, required this.currentPeriodEnd, required this.balance});
  factory PlanInfo.fromJson(Map<String, dynamic> j) => PlanInfo(
    plan: j['plan'] as String,
    currentPeriodEnd: j['current_period_end'] as String?,
    balance: j['balance'] as int,
  );
}

class CreditTx {
  final String id;
  final int amount;
  final String kind;
  final String? referenceId;
  final String? description;
  final String createdAt;
  CreditTx({required this.id, required this.amount, required this.kind,
            this.referenceId, this.description, required this.createdAt});
  factory CreditTx.fromJson(Map<String, dynamic> j) => CreditTx(
    id: j['id'] as String, amount: j['amount'] as int, kind: j['kind'] as String,
    referenceId: j['reference_id'] as String?, description: j['description'] as String?,
    createdAt: j['created_at'] as String,
  );
}
```

- [ ] **Step 11.2: Add the new exception + methods in `lib/api/client.dart`**

Near the existing `FacelessApiException`, add:

```dart
class InsufficientCreditsException extends FacelessApiException {
  final int balance;
  final int required;
  InsufficientCreditsException({required this.balance, required this.required})
      : super('Insufficient credits: have $balance, need $required', status: 402);
}
```

Update `_parse` to recognize 402:

```dart
T _parse<T>(http.Response r, T Function(dynamic) decode) {
  if (r.statusCode == 402) {
    try {
      final body = jsonDecode(r.body);
      final d = body is Map ? (body['detail'] ?? body) : body;
      if (d is Map && d['code'] == 'insufficient_credits') {
        throw InsufficientCreditsException(
          balance: (d['balance'] ?? 0) as int,
          required: (d['required'] ?? 0) as int,
        );
      }
    } catch (e) {
      if (e is InsufficientCreditsException) rethrow;
      // fall through to generic handling
    }
  }
  if (r.statusCode >= 400) {
    String detail;
    try {
      final body = jsonDecode(r.body);
      detail = body is Map && body['detail'] != null
          ? body['detail'].toString()
          : r.body;
    } catch (_) {
      detail = r.body;
    }
    throw FacelessApiException(detail, status: r.statusCode);
  }
  return decode(jsonDecode(utf8.decode(r.bodyBytes)));
}
```

Add the five billing methods (anywhere in `FacelessApiClient`):

```dart
Future<Balance> getBalance() async {
  final r = await _http.get(await _uri('/billing/balance'), headers: await _headers());
  return _parse(r, (j) => Balance.fromJson(j as Map<String, dynamic>));
}

Future<PlanInfo> getPlan() async {
  final r = await _http.get(await _uri('/billing/plan'), headers: await _headers());
  return _parse(r, (j) => PlanInfo.fromJson(j as Map<String, dynamic>));
}

Future<List<CreditTx>> getTransactions({int limit = 50}) async {
  final r = await _http.get(
    await _uri('/billing/transactions?limit=$limit'),
    headers: await _headers(),
  );
  return _parse(r, (j) => (j as List)
      .map((x) => CreditTx.fromJson(x as Map<String, dynamic>))
      .toList());
}

Future<String> createSubscriptionCheckout({
  required String plan,
  required String successUrl,
  required String cancelUrl,
}) async {
  final r = await _http.post(
    await _uri('/billing/checkout-subscription'),
    headers: {...await _headers(), 'Content-Type': 'application/json'},
    body: jsonEncode({'plan': plan, 'success_url': successUrl, 'cancel_url': cancelUrl}),
  );
  return _parse(r, (j) => (j as Map)['url'] as String);
}

Future<String> createTopupCheckout({
  required String pack,
  required String successUrl,
  required String cancelUrl,
}) async {
  final r = await _http.post(
    await _uri('/billing/checkout-topup'),
    headers: {...await _headers(), 'Content-Type': 'application/json'},
    body: jsonEncode({'pack': pack, 'success_url': successUrl, 'cancel_url': cancelUrl}),
  );
  return _parse(r, (j) => (j as Map)['url'] as String);
}

Future<String> createPortalSession({required String returnUrl}) async {
  final r = await _http.post(
    await _uri('/billing/portal'),
    headers: {...await _headers(), 'Content-Type': 'application/json'},
    body: jsonEncode({'return_url': returnUrl}),
  );
  return _parse(r, (j) => (j as Map)['url'] as String);
}
```

- [ ] **Step 11.3: Verify the build**

```bash
flutter analyze 2>&1 | grep -E "error" | head -10
```

Expected: no `error` lines in client.dart or models.dart.

- [ ] **Step 11.4: Commit**

```bash
git add lib/api/client.dart lib/api/models.dart
git commit -m "feat(flutter): API client — billing methods + InsufficientCreditsException"
```

---

## Task 12: Billing screen

**Files:**
- Create: `lib/screens/billing_screen.dart`

This is the biggest Flutter task. It shows: current balance + plan, three subscription tier cards (highlight current), three top-up packs, "Manage subscription" button, recent transactions list.

- [ ] **Step 12.1: Implement `lib/screens/billing_screen.dart`**

```dart
import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../api/client.dart';
import '../api/models.dart';
import '../api/settings.dart';
import '../theme.dart';

class BillingScreen extends StatefulWidget {
  const BillingScreen({super.key});

  @override
  State<BillingScreen> createState() => _BillingScreenState();
}

class _BillingScreenState extends State<BillingScreen> {
  late final FacelessApiClient _api;
  PlanInfo? _plan;
  List<CreditTx> _txs = [];
  bool _loading = true;
  String? _error;

  static const _plans = [
    ('starter', 'Starter', r'$9 / month', '60 credits / month'),
    ('creator', 'Creator', r'$29 / month', '250 credits / month'),
    ('pro',     'Pro',     r'$79 / month', '800 credits / month'),
  ];
  static const _packs = [
    ('topup_30',  'Pack S', r'$5',  '30 credits'),
    ('topup_100', 'Pack M', r'$15', '100 credits'),
    ('topup_300', 'Pack L', r'$40', '300 credits'),
  ];

  @override
  void initState() {
    super.initState();
    _api = FacelessApiClient(FacelessSettings());
    _load();
  }

  Future<void> _load() async {
    setState(() { _loading = true; _error = null; });
    try {
      final plan = await _api.getPlan();
      final txs = await _api.getTransactions(limit: 50);
      if (mounted) setState(() { _plan = plan; _txs = txs; _loading = false; });
    } catch (e) {
      if (mounted) setState(() { _error = e.toString(); _loading = false; });
    }
  }

  Future<void> _subscribe(String plan) async {
    final base = Uri.base.toString();
    try {
      final url = await _api.createSubscriptionCheckout(
        plan: plan, successUrl: base, cancelUrl: base,
      );
      await launchUrl(Uri.parse(url), webOnlyWindowName: '_blank');
    } catch (e) {
      _toast(e.toString());
    }
  }

  Future<void> _topup(String pack) async {
    final base = Uri.base.toString();
    try {
      final url = await _api.createTopupCheckout(
        pack: pack, successUrl: base, cancelUrl: base,
      );
      await launchUrl(Uri.parse(url), webOnlyWindowName: '_blank');
    } catch (e) {
      _toast(e.toString());
    }
  }

  Future<void> _portal() async {
    final base = Uri.base.toString();
    try {
      final url = await _api.createPortalSession(returnUrl: base);
      await launchUrl(Uri.parse(url), webOnlyWindowName: '_blank');
    } catch (e) {
      _toast(e.toString());
    }
  }

  void _toast(String msg) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Billing'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'Refresh',
            onPressed: _loading ? null : _load,
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(child: Text(_error!, style: const TextStyle(color: FacelessTheme.danger)))
              : ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    _BalanceCard(plan: _plan!),
                    const SizedBox(height: 24),
                    Text('Subscriptions',
                         style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: 8),
                    for (final p in _plans)
                      _PlanCard(
                        id: p.$1, title: p.$2, price: p.$3, credits: p.$4,
                        current: _plan!.plan == p.$1,
                        onSubscribe: () => _subscribe(p.$1),
                      ),
                    const SizedBox(height: 24),
                    Text('Top-up packs',
                         style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: 8),
                    for (final p in _packs)
                      _PackCard(
                        id: p.$1, title: p.$2, price: p.$3, credits: p.$4,
                        onBuy: () => _topup(p.$1),
                      ),
                    const SizedBox(height: 24),
                    if (_plan!.plan != 'free')
                      OutlinedButton.icon(
                        icon: const Icon(Icons.open_in_new),
                        label: const Text('Manage subscription (Stripe)'),
                        onPressed: _portal,
                      ),
                    const SizedBox(height: 24),
                    Text('Recent transactions',
                         style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: 8),
                    if (_txs.isEmpty)
                      const Text('No transactions yet.',
                                 style: TextStyle(color: FacelessTheme.textSecondary)),
                    for (final t in _txs) _TxRow(tx: t),
                  ],
                ),
    );
  }
}

class _BalanceCard extends StatelessWidget {
  final PlanInfo plan;
  const _BalanceCard({required this.plan});
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: FacelessTheme.cardGradient(),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('Balance', style: TextStyle(color: FacelessTheme.textSecondary)),
              const SizedBox(height: 4),
              Text('${plan.balance} credits',
                   style: const TextStyle(color: FacelessTheme.accent,
                                          fontSize: 28, fontWeight: FontWeight.w700)),
              const SizedBox(height: 4),
              Text('Plan: ${plan.plan}',
                   style: const TextStyle(color: FacelessTheme.textPrimary)),
              if (plan.currentPeriodEnd != null)
                Text('Renews ${plan.currentPeriodEnd!.substring(0, 10)}',
                     style: const TextStyle(color: FacelessTheme.textSecondary, fontSize: 12)),
            ],
          ),
          const Icon(Icons.monetization_on, color: FacelessTheme.accent, size: 40),
        ],
      ),
    );
  }
}

class _PlanCard extends StatelessWidget {
  final String id, title, price, credits;
  final bool current;
  final VoidCallback onSubscribe;
  const _PlanCard({
    required this.id, required this.title, required this.price,
    required this.credits, required this.current, required this.onSubscribe,
  });
  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(
          color: current ? FacelessTheme.accent : Colors.transparent,
          width: 1.5,
        ),
      ),
      child: ListTile(
        title: Text('$title — $price'),
        subtitle: Text(credits),
        trailing: current
            ? const Chip(label: Text('current'), backgroundColor: FacelessTheme.surface2)
            : FilledButton(onPressed: onSubscribe, child: const Text('Subscribe')),
      ),
    );
  }
}

class _PackCard extends StatelessWidget {
  final String id, title, price, credits;
  final VoidCallback onBuy;
  const _PackCard({
    required this.id, required this.title, required this.price,
    required this.credits, required this.onBuy,
  });
  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        title: Text('$title — $price'),
        subtitle: Text(credits),
        trailing: OutlinedButton(onPressed: onBuy, child: const Text('Buy')),
      ),
    );
  }
}

class _TxRow extends StatelessWidget {
  final CreditTx tx;
  const _TxRow({required this.tx});
  @override
  Widget build(BuildContext context) {
    final positive = tx.amount > 0;
    return ListTile(
      dense: true,
      leading: Icon(
        positive ? Icons.add_circle_outline : Icons.remove_circle_outline,
        color: positive ? FacelessTheme.success : FacelessTheme.danger,
      ),
      title: Text(tx.description ?? tx.kind),
      subtitle: Text(tx.createdAt.substring(0, 16).replaceFirst('T', ' ')),
      trailing: Text(
        '${positive ? '+' : ''}${tx.amount}',
        style: TextStyle(
          color: positive ? FacelessTheme.success : FacelessTheme.danger,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}
```

`url_launcher` is already a dependency in `pubspec.yaml` (used elsewhere in the app — verify with `grep url_launcher pubspec.yaml`; if missing, add `url_launcher: ^6.2.0` and run `flutter pub get`).

- [ ] **Step 12.2: Verify the build**

```bash
flutter analyze 2>&1 | grep -E "error" | head -10
```

Expected: no `error` lines in billing_screen.dart.

- [ ] **Step 12.3: Commit**

```bash
git add lib/screens/billing_screen.dart pubspec.yaml pubspec.lock
git commit -m "feat(flutter): billing screen — plans, top-ups, transactions"
```

---

## Task 13: Paywall dialog + 402 routing

**Files:**
- Create: `lib/widgets/paywall_dialog.dart`
- Modify: `lib/screens/new_run_screen.dart` (or wherever the "Generate" button calls /runs/freeform — grep to confirm)

- [ ] **Step 13.1: Find the call site that creates a run**

```bash
grep -rn "createFreeformRun\|createRunFromScript\|/runs/freeform" lib/
```

There should be one or two screens that call `_api.createFreeformRun(...)` (or similar). Take note.

- [ ] **Step 13.2: Implement `lib/widgets/paywall_dialog.dart`**

```dart
import 'package:flutter/material.dart';

import '../screens/billing_screen.dart';
import '../theme.dart';

class PaywallDialog extends StatelessWidget {
  final int balance;
  final int required;
  const PaywallDialog({super.key, required this.balance, required this.required});

  static Future<void> show(BuildContext context, {required int balance, required int required}) {
    return showDialog(
      context: context,
      builder: (_) => PaywallDialog(balance: balance, required: required),
    );
  }

  @override
  Widget build(BuildContext context) {
    final missing = required - balance;
    return AlertDialog(
      icon: const Icon(Icons.monetization_on, color: FacelessTheme.accent, size: 36),
      title: const Text('Out of credits'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            'This video needs $required credits. You have $balance — '
            '$missing more to go. Top up to keep generating.',
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 16),
          const Text(
            'Your script and characters are saved. After topping up, '
            'tap Resume on this run to continue.',
            textAlign: TextAlign.center,
            style: TextStyle(color: FacelessTheme.textSecondary, fontSize: 13),
          ),
        ],
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        FilledButton.icon(
          icon: const Icon(Icons.shopping_cart),
          label: const Text('Top up'),
          onPressed: () {
            Navigator.of(context).pop();
            Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const BillingScreen()),
            );
          },
        ),
      ],
    );
  }
}
```

- [ ] **Step 13.3: Wire it into the new-run screen**

In whichever screen calls `_api.createFreeformRun(...)` (per Step 13.1), wrap the call in `try/on InsufficientCreditsException`. Example pattern (adapt to actual file/state-class names):

```dart
import '../api/client.dart';
import '../widgets/paywall_dialog.dart';

// ... inside the submit handler:
try {
  final run = await _api.createFreeformRun(...);
  // existing success path
} on InsufficientCreditsException catch (e) {
  if (mounted) {
    PaywallDialog.show(context, balance: e.balance, required: e.required);
  }
} catch (e) {
  if (mounted) _showError(e.toString());
}
```

Do the same wrap for any other run-creating call (e.g. paste-script flow).

- [ ] **Step 13.4: Verify the build**

```bash
flutter analyze 2>&1 | grep -E "error" | head -10
```

Expected: zero `error` lines.

- [ ] **Step 13.5: Commit**

```bash
git add lib/widgets/paywall_dialog.dart lib/screens/new_run_screen.dart
git commit -m "feat(flutter): paywall dialog + 402 routing on run creation"
```

---

## Task 14: Balance badge on home / run detail + Settings entry

**Files:**
- Modify: `lib/screens/home_screen.dart`
- Modify: `lib/screens/settings_screen.dart`

- [ ] **Step 14.1: Add a `_BalanceBadge` widget at the top of `lib/screens/home_screen.dart`**

```dart
class _BalanceBadge extends StatefulWidget {
  const _BalanceBadge();
  @override
  State<_BalanceBadge> createState() => _BalanceBadgeState();
}

class _BalanceBadgeState extends State<_BalanceBadge> {
  int? _balance;

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  Future<void> _refresh() async {
    try {
      final b = await FacelessApiClient(FacelessSettings()).getBalance();
      if (mounted) setState(() => _balance = b.balance);
    } catch (_) {
      // Silent on error — non-critical, just don't show a stale badge
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_balance == null) return const SizedBox.shrink();
    return GestureDetector(
      onTap: () => Navigator.of(context).push(
        MaterialPageRoute(builder: (_) => const BillingScreen()),
      ),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        decoration: BoxDecoration(
          color: FacelessTheme.surface2,
          borderRadius: BorderRadius.circular(20),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.monetization_on, color: FacelessTheme.accent, size: 16),
            const SizedBox(width: 6),
            Text('$_balance', style: const TextStyle(fontWeight: FontWeight.w600)),
          ],
        ),
      ),
    );
  }
}
```

Required imports at the top of the file (add the ones not already present):
```dart
import 'billing_screen.dart';
import '../api/client.dart';
import '../api/settings.dart';
import '../theme.dart';
```

- [ ] **Step 14.2: Place the badge in the home screen's AppBar**

Find the existing `AppBar(...)` in `home_screen.dart`. Add to its `actions:` list (before any existing action buttons):

```dart
actions: [
  const Padding(
    padding: EdgeInsets.only(right: 12),
    child: Center(child: _BalanceBadge()),
  ),
  // existing actions...
],
```

- [ ] **Step 14.3: Add a "Billing" row in Settings**

In `lib/screens/settings_screen.dart`, find the build method. Add a ListTile (before or after the Sign Out button):

```dart
ListTile(
  leading: const Icon(Icons.monetization_on),
  title: const Text('Billing'),
  trailing: const Icon(Icons.chevron_right),
  onTap: () => Navigator.of(context).push(
    MaterialPageRoute(builder: (_) => const BillingScreen()),
  ),
),
```

Add the import: `import 'billing_screen.dart';`.

- [ ] **Step 14.4: Verify the build**

```bash
flutter analyze 2>&1 | grep -E "error" | head -10
```

Expected: zero `error` lines.

- [ ] **Step 14.5: Commit**

```bash
git add lib/screens/home_screen.dart lib/screens/settings_screen.dart
git commit -m "feat(flutter): balance badge on home + Billing entry in Settings"
```

---

## Task 15: End-to-end smoke test

**Files:** none — manual verification.

**Prerequisite:** all of Tasks 1-14 are committed. The Stripe dashboard is in test mode with the products + webhook configured (Task 10 manual step).

- [ ] **Step 15.1: Deploy the final stack**

```bash
./scripts/build-and-push.sh
```

- [ ] **Step 15.2: Launch the app**

```bash
./scripts/run-app.sh
```

The app should boot to the LoginScreen.

- [ ] **Step 15.3: Sign up a fresh test user**

In the LoginScreen, sign up with `essam+b3a@<yourdomain>` / password (8+ chars).

In a separate terminal, verify the signup grant landed:

```bash
SERVICE_URL=https://faceless-api-uplzdtffeq-uc.a.run.app
source .env
# Get the user's JWT — easier path: just check the API state directly via service token
# (the new user's user_id is visible in the Cloud Run logs from the auth event).
gcloud logging read \
  "resource.type=\"cloud_run_revision\" AND textPayload:\"signup_grant\"" \
  --limit=1 --format="value(textPayload)" --freshness=10m
```

You should see a recent `signup_grant` of 60 credits.

- [ ] **Step 15.4: Confirm balance in the UI**

In the running app, observe the balance badge top-right: **60 credits**.

Tap it → land on the Billing screen → balance = 60, plan = free, no transactions yet other than the signup grant.

- [ ] **Step 15.5: Try to create a 6×8s run (48 credits, fits)**

Tap **New Run**. Enter premise + theme. Submit.

Expected: run is created, status flips to `creating` → `awaiting_approval`. Balance dropped only after Veo runs (per-clip), so right after submit it's still 60.

- [ ] **Step 15.6: Try to create an oversized run that won't fit**

Click New Run again. Set max_beats to 20 (= 20×8 = 160 estimated credits). Submit.

Expected: **paywall dialog appears** — "needs 160 credits, you have 60-something". Tap **Top up**.

- [ ] **Step 15.7: Subscribe to Starter via Stripe test mode**

On the Billing screen, tap **Subscribe** under "Starter — $9 / month".

A new browser tab opens Stripe Checkout. Use test card `4242 4242 4242 4242`, any future expiry, any CVC. Complete.

Expected:
- Stripe redirects back to your app
- Within ~10 seconds (webhook), balance refreshes to original + 60 (Starter renewal grant). Tap the refresh icon on the Billing screen to force-check.
- Plan = "starter", `current_period_end` ~30 days out.

- [ ] **Step 15.8: Try the oversized run again — should now go through (or get a smaller 402)**

Depending on your balance, either it goes through (spawn worker) or you still need a top-up. Try a top-up pack ($5 / 30 credits) via the Billing screen if needed.

- [ ] **Step 15.9: Cancel the subscription via Stripe Portal**

Billing screen → **Manage subscription (Stripe)** → cancel.

Expected:
- Stripe fires `customer.subscription.updated` immediately (plan stays starter until period end)
- At period end (in test mode, the next minute or so depending on Stripe's test clock), Stripe fires `customer.subscription.deleted` → app shows plan = free
- Existing credits remain (no clawback).

- [ ] **Step 15.10: Service token / CLI bypass check**

```bash
# Service token still works without credits in the ledger
SERVICE_URL=https://faceless-api-uplzdtffeq-uc.a.run.app
source .env
curl -s -w "\nHTTP %{http_code}\n" \
  -H "Authorization: Bearer $FACELESS_API_TOKEN" \
  $SERVICE_URL/billing/balance
# Expected: {"balance": 0} HTTP 200

# Service token can POST a run even with 0 balance
curl -s -w "\nHTTP %{http_code}\n" \
  -H "Authorization: Bearer $FACELESS_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"theme":"folkloric","premise":"بئر قديم","max_beats":4}' \
  $SERVICE_URL/runs/freeform | head -c 200
# Expected: HTTP 200 (or 5xx if upstream Kie issues — but NOT 402)
```

If all 10 steps pass, B3 is done.

---

## What the human reviewer should verify after all tasks complete

1. `grep -rn 'os.environ.get\("STRIPE' pipeline/` — only `pipeline/stripe_billing.py` reads Stripe env. The rest of the codebase never imports `stripe` directly.
2. `grep -rn 'check_or_deduct\|refund' pipeline/` — only `pipeline/credits.py` defines them; only `pipeline/video.py` calls them.
3. `uv run pytest -q` — at least 414 + integration tests pass; no skips.
4. A fresh user gets `signup_grant=60` exactly once (idempotent on repeated auth).
5. A failed Veo clip in a 6-clip run produces 6 charges + 1 refund (net -50 for a 10s/clip job).
6. Stripe test-mode subscription with card 4242 produces a `subscription_renewal=60` row in `credit_transactions`.
7. Cancelling the subscription flips `current_plan` to `'free'` and leaves the ledger untouched.
8. `/stripe/webhook` with a bad signature returns 400.
9. `/stripe/webhook` with an unknown event type returns 200 with `handled: false` (so Stripe doesn't retry forever).
