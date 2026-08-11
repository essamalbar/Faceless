# Paddle (MoR) Billing Migration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Stripe billing integration with Paddle (Merchant of Record) so a solo individual with no trade license can take real subscription payments, without changing the Flutter app or the credit ledger.

**Architecture:** A new `pipeline/paddle_billing.py` mirrors the public surface of `pipeline/stripe_billing.py` (`create_subscription_checkout`, `create_portal_session`, `handle_webhook`) using a thin `httpx` client against Paddle's REST API. Checkout returns a Paddle-hosted `checkout.url` (redirect pattern, identical to today). Webhooks map Paddle events onto the existing, unchanged credit-ledger functions (`record_grant_once`, `get_grant_by_reference`, `upsert_user_profile`). The API endpoints swap their local import from `stripe_billing` to `paddle_billing`; `stripe_billing.py` stays dormant for rollback.

**Tech Stack:** Python 3.11, FastAPI, `httpx>=0.27` (already a dependency — no new deps), Supabase (Postgres) via existing `pipeline.db`, Paddle Billing REST API.

## Global Constraints

- Every `.py` file starts with `from __future__ import annotations`.
- Imports are absolute from the package root (`from pipeline.x import y`).
- Use `pathlib.Path`, never `os.path`.
- External services are mocked in tests — **no live Paddle calls in any test.** Mock by monkeypatching module-level names in `pipeline.paddle_billing` (mirror `tests/test_stripe_billing.py`).
- Plan credit sizes are fixed: `pipeline.credits.PLAN_GRANTS = {"starter": 12, "creator": 60, "pro": 200}`. Read them from that constant; never hardcode.
- Paddle REST base URL: sandbox `https://sandbox-api.paddle.com`, production `https://api.paddle.com`, selected by env `PADDLE_ENV` (`sandbox` default).
- Paddle webhook signature header is `Paddle-Signature: ts=<unix>;h1=<hex>`, where `h1 = HMAC_SHA256(PADDLE_WEBHOOK_SECRET, b"<ts>:" + raw_body)`.
- All webhook grants/clawbacks stay idempotent via the existing unique indexes `uq_credit_grant_ref` / `uq_credit_clawback_ref` (already migrated). `record_grant_once(...)` returns `False` on a duplicate.
- Money copy stays vendor-agnostic (never name Paddle/Veo/Kie in user-facing strings) — matches the existing convention.

---

### Task 1: Add `paddle_customer_id` to user profiles

Paddle needs its own customer id stored per user (the Stripe column is reused by nothing here). Additive, idempotent migration + read-path plumbing.

**Files:**
- Create: `supabase/migrations/20260811000001_paddle_customer_id.sql`
- Modify: `docs/operator/APPLY-MIGRATIONS.sql` (append the new statement)
- Modify: `pipeline/db.py` — `UserProfile` dataclass (add field) and `get_user_profile` (select + map)
- Test: `tests/test_db_paddle_customer.py`

**Interfaces:**
- Produces: `UserProfile.paddle_customer_id: str | None`; `upsert_user_profile(user_id, paddle_customer_id=...)` writes the new column (generic `**fields` upsert already supports it once the column exists).

- [ ] **Step 1: Write the migration SQL**

Create `supabase/migrations/20260811000001_paddle_customer_id.sql`:
```sql
-- Paddle (Merchant of Record) customer id, analogous to stripe_customer_id.
-- Additive + idempotent so re-running the bundle is safe.
alter table user_profiles
  add column if not exists paddle_customer_id text;
```

- [ ] **Step 2: Append the same statement to the operator bundle**

Add to the end of `docs/operator/APPLY-MIGRATIONS.sql` (before the closing banner comment):
```sql
-- ===== 20260811000001_paddle_customer_id.sql =====
alter table user_profiles
  add column if not exists paddle_customer_id text;
```

- [ ] **Step 3: Write the failing test**

Create `tests/test_db_paddle_customer.py`:
```python
from __future__ import annotations

from types import SimpleNamespace

import pipeline.db as db


def test_get_user_profile_maps_paddle_customer_id(monkeypatch):
    row = {
        "id": "u1", "stripe_customer_id": None, "paddle_customer_id": "ctm_1",
        "current_plan": "free", "current_period_end": None,
        "cancel_at_period_end": False, "payment_status": "active",
    }

    class _Resp:
        data = [row]

    class _Tbl:
        def select(self, *a, **k): return self
        def eq(self, *a, **k): return self
        def limit(self, *a, **k): return self
        def single(self, *a, **k): return self
        def execute(self): return _Resp()

    monkeypatch.setattr(db, "_client", lambda: SimpleNamespace(table=lambda *_: _Tbl()))
    p = db.get_user_profile("u1")
    assert p is not None and p.paddle_customer_id == "ctm_1"
```

- [ ] **Step 4: Run test to verify it fails**

Run: `uv run pytest tests/test_db_paddle_customer.py -v`
Expected: FAIL — `UserProfile` has no `paddle_customer_id` (TypeError) or attribute error.

- [ ] **Step 5: Add the field + select + mapping in `pipeline/db.py`**

In the `UserProfile` dataclass (around line 19-21) add after `stripe_customer_id`:
```python
    paddle_customer_id: str | None
```
In `get_user_profile` update the `.select(...)` string (around line 61) to include `paddle_customer_id`, e.g. `"id,stripe_customer_id,paddle_customer_id,current_plan,..."`, and in the `UserProfile(...)` construction (around line 74) add:
```python
        paddle_customer_id=d.get("paddle_customer_id"),
```
Do the same for the OTHER place that builds a `UserProfile` and selects columns (around lines 252 and 263 — the second reader). Add `paddle_customer_id` to both its select string and its `UserProfile(...)` kwargs, and add `paddle_customer_id=None` to the default-profile constructor around line 214.

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest tests/test_db_paddle_customer.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add supabase/migrations/20260811000001_paddle_customer_id.sql docs/operator/APPLY-MIGRATIONS.sql pipeline/db.py tests/test_db_paddle_customer.py
git commit -m "feat(billing): add paddle_customer_id column + read-path plumbing"
```

---

### Task 2: Paddle module foundation — config, REST client, signature verification

**Files:**
- Create: `pipeline/paddle_billing.py`
- Test: `tests/test_paddle_billing.py`

**Interfaces:**
- Produces:
  - `PaddleSignatureError(Exception)`
  - `_api_key() -> str`, `_webhook_secret() -> str`, `_plan_price_id(plan: str) -> str`
  - `_base_url() -> str` (`https://sandbox-api.paddle.com` unless `PADDLE_ENV=production`)
  - `_request(method: str, path: str, *, json: dict | None = None, params: dict | None = None) -> dict` — returns the parsed JSON `data`/body; raises on non-2xx
  - `_verify_signature(raw_body: bytes, signature_header: str, max_age_s: int = 300) -> None`
  - `@dataclass(frozen=True) WebhookOutcome(event_type: str, handled: bool, note: str)`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_paddle_billing.py`:
```python
"""Tests for pipeline.paddle_billing — Paddle REST wrapper, all mocked."""
from __future__ import annotations

import hashlib
import hmac
import time
from types import SimpleNamespace

import pytest

import pipeline.paddle_billing as pb


@pytest.fixture
def paddle_env(monkeypatch):
    monkeypatch.setenv("PADDLE_API_KEY", "pdl_test_key")
    monkeypatch.setenv("PADDLE_WEBHOOK_SECRET", "pdl_ntfset_secret")
    monkeypatch.setenv("PADDLE_PRICE_STARTER", "pri_starter")
    monkeypatch.setenv("PADDLE_PRICE_CREATOR", "pri_creator")
    monkeypatch.setenv("PADDLE_PRICE_PRO", "pri_pro")
    monkeypatch.delenv("PADDLE_ENV", raising=False)


def _sign(secret: str, raw: bytes, ts: str) -> str:
    mac = hmac.new(secret.encode(), f"{ts}:".encode() + raw, hashlib.sha256).hexdigest()
    return f"ts={ts};h1={mac}"


def test_base_url_defaults_to_sandbox(paddle_env):
    assert pb._base_url() == "https://sandbox-api.paddle.com"


def test_base_url_production(paddle_env, monkeypatch):
    monkeypatch.setenv("PADDLE_ENV", "production")
    assert pb._base_url() == "https://api.paddle.com"


def test_plan_price_id_reads_env(paddle_env):
    assert pb._plan_price_id("creator") == "pri_creator"


def test_api_key_missing_raises(monkeypatch):
    monkeypatch.delenv("PADDLE_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="PADDLE_API_KEY"):
        pb._api_key()


def test_verify_signature_accepts_valid(paddle_env):
    raw = b'{"event_type":"x"}'
    ts = str(int(time.time()))
    pb._verify_signature(raw, _sign("pdl_ntfset_secret", raw, ts))  # no raise


def test_verify_signature_rejects_tampered_body(paddle_env):
    ts = str(int(time.time()))
    header = _sign("pdl_ntfset_secret", b'{"a":1}', ts)
    with pytest.raises(pb.PaddleSignatureError):
        pb._verify_signature(b'{"a":2}', header)


def test_verify_signature_rejects_stale(paddle_env):
    raw = b"{}"
    ts = str(int(time.time()) - 10_000)
    with pytest.raises(pb.PaddleSignatureError):
        pb._verify_signature(raw, _sign("pdl_ntfset_secret", raw, ts))


def test_verify_signature_rejects_malformed_header(paddle_env):
    with pytest.raises(pb.PaddleSignatureError):
        pb._verify_signature(b"{}", "garbage")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_paddle_billing.py -v`
Expected: FAIL — `No module named 'pipeline.paddle_billing'`.

- [ ] **Step 3: Write the module foundation**

Create `pipeline/paddle_billing.py`:
```python
"""Paddle Billing (Merchant of Record) wrapper.

Mirrors pipeline.stripe_billing's public surface so the rest of the app is
provider-agnostic:
  1. Build Paddle-hosted Checkout URLs the Flutter app opens in a new tab.
  2. Verify + dispatch incoming Paddle webhooks (no bearer auth on that
     endpoint; trust is the Paddle-Signature HMAC).

Talks to Paddle's REST API via a thin httpx client — no heavyweight SDK — so
tests can monkeypatch _request() with canned JSON.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import time
from dataclasses import dataclass

import httpx

from pipeline.auth import User
from pipeline.credits import PLAN_GRANTS
from pipeline.db import (
    get_grant_by_reference,
    get_user_profile,
    record_grant_once,
    upsert_user_profile,
)


class PaddleSignatureError(Exception):
    """Raised when a webhook's Paddle-Signature header fails verification."""


def _api_key() -> str:
    key = os.environ.get("PADDLE_API_KEY", "").strip()
    if not key:
        raise RuntimeError("PADDLE_API_KEY not configured")
    return key


def _webhook_secret() -> str:
    s = os.environ.get("PADDLE_WEBHOOK_SECRET", "").strip()
    if not s:
        raise RuntimeError("PADDLE_WEBHOOK_SECRET not configured")
    return s


def _plan_price_id(plan: str) -> str:
    env_key = f"PADDLE_PRICE_{plan.upper()}"
    pid = os.environ.get(env_key, "").strip()
    if not pid:
        raise RuntimeError(f"{env_key} not configured")
    return pid


def _base_url() -> str:
    if os.environ.get("PADDLE_ENV", "sandbox").strip().lower() == "production":
        return "https://api.paddle.com"
    return "https://sandbox-api.paddle.com"


def _request(method: str, path: str, *, json: dict | None = None,
             params: dict | None = None) -> dict:
    """One REST round-trip. Returns the parsed JSON body (Paddle wraps the
    resource under a top-level "data" key). Raises httpx.HTTPStatusError on
    non-2xx."""
    resp = httpx.request(
        method,
        f"{_base_url()}{path}",
        headers={"Authorization": f"Bearer {_api_key()}",
                 "Content-Type": "application/json"},
        json=json,
        params=params,
        timeout=30.0,
    )
    resp.raise_for_status()
    return resp.json()


def _verify_signature(raw_body: bytes, signature_header: str,
                      max_age_s: int = 300) -> None:
    """Verify Paddle-Signature: 'ts=<unix>;h1=<hex>' where
    h1 = HMAC_SHA256(secret, b'<ts>:' + raw_body). Raises PaddleSignatureError
    on malformed header, mismatch, or a timestamp older than max_age_s."""
    parts = dict(p.split("=", 1) for p in signature_header.split(";") if "=" in p)
    ts, h1 = parts.get("ts"), parts.get("h1")
    if not ts or not h1:
        raise PaddleSignatureError("malformed Paddle-Signature header")
    signed = f"{ts}:".encode() + raw_body
    expected = hmac.new(_webhook_secret().encode(), signed, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, h1):
        raise PaddleSignatureError("signature mismatch")
    try:
        if abs(time.time() - int(ts)) > max_age_s:
            raise PaddleSignatureError("timestamp outside tolerance")
    except ValueError:
        raise PaddleSignatureError("non-numeric timestamp")


@dataclass(frozen=True)
class WebhookOutcome:
    event_type: str
    handled: bool
    note: str
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_paddle_billing.py -v`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add pipeline/paddle_billing.py tests/test_paddle_billing.py
git commit -m "feat(billing): paddle_billing foundation — config, REST client, sig verify"
```

---

### Task 3: Checkout + customer + portal

**Files:**
- Modify: `pipeline/paddle_billing.py`
- Test: `tests/test_paddle_billing.py` (append)

**Interfaces:**
- Consumes: `_request`, `_plan_price_id`, `PLAN_GRANTS`, `get_user_profile`, `upsert_user_profile`.
- Produces:
  - `ensure_customer(user: User) -> str` (returns `ctm_...`, stores `paddle_customer_id`)
  - `create_subscription_checkout(user: User, plan: str, success_url: str, cancel_url: str) -> str` (returns hosted `checkout.url`)
  - `create_portal_session(user: User, return_url: str) -> str`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_paddle_billing.py`:
```python
def _user():
    return User(id="u1", email="alice@example.com", role="user")


@pytest.fixture
def mock_db(monkeypatch):
    state = {"profiles": {}, "grants": []}
    monkeypatch.setattr(pb, "get_user_profile",
        lambda uid: (SimpleNamespace(id=uid, paddle_customer_id=state["profiles"][uid].get("paddle_customer_id"))
                     if uid in state["profiles"] else None))
    monkeypatch.setattr(pb, "upsert_user_profile",
        lambda uid, **f: state["profiles"].setdefault(uid, {}).update(f) or None)
    monkeypatch.setattr(pb, "record_grant_once",
        lambda **kw: (state["grants"].append(kw), True)[1])
    return state


def test_ensure_customer_creates_when_missing(paddle_env, mock_db, monkeypatch):
    calls = {}
    def fake_request(method, path, *, json=None, params=None):
        calls.update(method=method, path=path, json=json, params=params)
        if method == "GET":
            return {"data": []}       # no existing customer for this email
        return {"data": {"id": "ctm_new"}}
    monkeypatch.setattr(pb, "_request", fake_request)
    assert pb.ensure_customer(_user()) == "ctm_new"
    assert mock_db["profiles"]["u1"]["paddle_customer_id"] == "ctm_new"


def test_ensure_customer_reuses_stored(paddle_env, mock_db, monkeypatch):
    mock_db["profiles"]["u1"] = {"paddle_customer_id": "ctm_old"}
    monkeypatch.setattr(pb, "_request",
        lambda *a, **k: pytest.fail("should not hit Paddle when id is stored"))
    assert pb.ensure_customer(_user()) == "ctm_old"


def test_create_subscription_checkout_returns_hosted_url(paddle_env, mock_db, monkeypatch):
    mock_db["profiles"]["u1"] = {"paddle_customer_id": "ctm_x"}
    captured = {}
    def fake_request(method, path, *, json=None, params=None):
        captured.update(method=method, path=path, json=json)
        return {"data": {"id": "txn_1",
                         "checkout": {"url": "https://pay.paddle.io/txn_1"}}}
    monkeypatch.setattr(pb, "_request", fake_request)
    url = pb.create_subscription_checkout(_user(), "creator",
                                          "https://app/success", "https://app/cancel")
    assert url == "https://pay.paddle.io/txn_1"
    assert captured["path"] == "/transactions"
    assert captured["json"]["items"][0]["price_id"] == "pri_creator"
    # Critical: user_id + plan ride in custom_data so renewal transactions
    # (which inherit the subscription's custom_data) can find the user.
    assert captured["json"]["custom_data"] == {"user_id": "u1", "plan": "creator"}


def test_create_subscription_checkout_rejects_unknown_plan(paddle_env, mock_db):
    with pytest.raises(ValueError, match="unknown plan"):
        pb.create_subscription_checkout(_user(), "elite", "s", "c")


def test_create_portal_session_returns_url(paddle_env, mock_db, monkeypatch):
    mock_db["profiles"]["u1"] = {"paddle_customer_id": "ctm_x"}
    monkeypatch.setattr(pb, "_request",
        lambda *a, **k: {"data": {"urls": {"general": {"overview": "https://portal/x"}}}})
    assert pb.create_portal_session(_user(), "https://app/back") == "https://portal/x"
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_paddle_billing.py -k "customer or checkout or portal" -v`
Expected: FAIL — functions not defined.

- [ ] **Step 3: Implement**

Append to `pipeline/paddle_billing.py`:
```python
def ensure_customer(user: User) -> str:
    """Return the Paddle customer id for this user, creating one on first call.

    Paddle rejects a duplicate email on create, so look one up by email first;
    otherwise create with user_id in custom_data."""
    profile = get_user_profile(user.id)
    if profile and getattr(profile, "paddle_customer_id", None):
        return profile.paddle_customer_id
    if user.email:
        found = _request("GET", "/customers", params={"email": user.email})
        rows = found.get("data") or []
        if rows:
            cid = rows[0]["id"]
            upsert_user_profile(user.id, paddle_customer_id=cid)
            return cid
    created = _request("POST", "/customers",
                       json={"email": user.email, "custom_data": {"user_id": user.id}})
    cid = created["data"]["id"]
    upsert_user_profile(user.id, paddle_customer_id=cid)
    return cid


def create_subscription_checkout(user: User, plan: str,
                                 success_url: str, cancel_url: str) -> str:
    """Create a Paddle transaction for a subscription and return its
    hosted checkout URL (the app opens it in a new tab)."""
    if plan not in PLAN_GRANTS:
        raise ValueError(f"unknown plan: {plan!r}")
    customer_id = ensure_customer(user)
    resp = _request("POST", "/transactions", json={
        "items": [{"price_id": _plan_price_id(plan), "quantity": 1}],
        "customer_id": customer_id,
        # custom_data set here is copied by Paddle onto the subscription this
        # transaction creates, so renewal transactions inherit it.
        "custom_data": {"user_id": user.id, "plan": plan},
        "checkout": {"url": success_url},
    })
    return resp["data"]["checkout"]["url"]


def create_portal_session(user: User, return_url: str) -> str:
    """Return a Paddle customer-portal URL for self-serve manage/cancel."""
    customer_id = ensure_customer(user)
    resp = _request("POST", f"/customers/{customer_id}/portal-sessions", json={})
    return resp["data"]["urls"]["general"]["overview"]
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_paddle_billing.py -k "customer or checkout or portal" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/paddle_billing.py tests/test_paddle_billing.py
git commit -m "feat(billing): paddle checkout + customer + portal"
```

---

### Task 4: Webhook dispatch + transaction/subscription handlers

**Files:**
- Modify: `pipeline/paddle_billing.py`
- Test: `tests/test_paddle_billing.py` (append)

**Interfaces:**
- Consumes: `_verify_signature`, `record_grant_once`, `upsert_user_profile`, `PLAN_GRANTS`, `WebhookOutcome`.
- Produces: `handle_webhook(raw_body: bytes, signature: str) -> WebhookOutcome`; internal `_on_transaction_completed`, `_on_subscription_updated`, `_on_subscription_canceled`, `_on_subscription_past_due`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_paddle_billing.py`:
```python
import json as _json


def _wrap(event_type: str, data: dict, secret="pdl_ntfset_secret"):
    raw = _json.dumps({"event_type": event_type, "data": data}).encode()
    ts = str(int(time.time()))
    return raw, _sign(secret, raw, ts)


def test_webhook_transaction_completed_grants(paddle_env, mock_db, monkeypatch):
    raw, sig = _wrap("transaction.completed", {
        "id": "txn_1",
        "custom_data": {"user_id": "u1", "plan": "creator"},
        "billing_period": {"ends_at": "2026-09-11T00:00:00Z"},
    })
    out = pb.handle_webhook(raw, sig)
    assert out.handled
    g = mock_db["grants"][-1]
    assert g["amount"] == 60 and g["kind"] == "subscription_renewal"
    assert g["reference_id"] == "txn_1"
    prof = mock_db["profiles"]["u1"]
    assert prof["current_plan"] == "creator"
    assert prof["current_period_end"] == "2026-09-11T00:00:00Z"
    assert prof["payment_status"] == "active"


def test_webhook_transaction_completed_dedupes(paddle_env, mock_db, monkeypatch):
    calls = {"n": 0}
    def grant(**kw):
        calls["n"] += 1
        return calls["n"] == 1
    monkeypatch.setattr(pb, "record_grant_once", grant)
    raw, sig = _wrap("transaction.completed", {
        "id": "txn_dup", "custom_data": {"user_id": "u1", "plan": "starter"},
        "billing_period": {"ends_at": "2026-09-11T00:00:00Z"}})
    first = pb.handle_webhook(raw, sig)
    second = pb.handle_webhook(raw, sig)
    assert first.handled and "+12" in first.note
    assert second.handled and "no-op" in second.note
    assert calls["n"] == 2


def test_webhook_subscription_updated_persists_cancel(paddle_env, mock_db):
    raw, sig = _wrap("subscription.updated", {
        "id": "sub_1", "custom_data": {"user_id": "u1", "plan": "starter"},
        "current_billing_period": {"ends_at": "2026-09-11T00:00:00Z"},
        "scheduled_change": {"action": "cancel", "effective_at": "2026-09-11T00:00:00Z"},
    })
    out = pb.handle_webhook(raw, sig)
    assert out.handled
    prof = mock_db["profiles"]["u1"]
    assert prof["current_plan"] == "starter"
    assert prof["cancel_at_period_end"] is True
    assert prof["current_period_end"] == "2026-09-11T00:00:00Z"


def test_webhook_subscription_canceled_resets_free(paddle_env, mock_db):
    mock_db["profiles"]["u1"] = {"current_plan": "pro"}
    raw, sig = _wrap("subscription.canceled",
                     {"id": "sub_1", "custom_data": {"user_id": "u1"}})
    out = pb.handle_webhook(raw, sig)
    assert out.handled
    assert mock_db["profiles"]["u1"]["current_plan"] == "free"
    assert mock_db["profiles"]["u1"]["cancel_at_period_end"] is False


def test_webhook_subscription_past_due_marks_dunning(paddle_env, mock_db):
    mock_db["profiles"]["u1"] = {"current_plan": "creator"}
    raw, sig = _wrap("subscription.past_due",
                     {"id": "sub_1", "custom_data": {"user_id": "u1"}})
    out = pb.handle_webhook(raw, sig)
    assert out.handled
    assert mock_db["profiles"]["u1"]["payment_status"] == "past_due"


def test_webhook_bad_signature_raises(paddle_env):
    raw = _json.dumps({"event_type": "transaction.completed", "data": {}}).encode()
    with pytest.raises(pb.PaddleSignatureError):
        pb.handle_webhook(raw, "ts=123;h1=deadbeef")
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_paddle_billing.py -k webhook -v`
Expected: FAIL — `handle_webhook` not defined.

- [ ] **Step 3: Implement**

Append to `pipeline/paddle_billing.py`:
```python
import json


def handle_webhook(raw_body: bytes, signature: str) -> WebhookOutcome:
    """Verify the Paddle-Signature header, decode, and dispatch.

    Raises PaddleSignatureError on a bad signature (caller returns 400).
    Returns handled=False (still HTTP 200) for events we intentionally ignore.
    """
    _verify_signature(raw_body, signature)
    event = json.loads(raw_body)
    et = event.get("event_type", "")
    data = event.get("data") or {}

    if et == "transaction.completed":
        return _on_transaction_completed(data)
    if et == "subscription.updated":
        return _on_subscription_updated(data)
    if et == "subscription.canceled":
        return _on_subscription_canceled(data)
    if et == "subscription.past_due":
        return _on_subscription_past_due(data)
    if et == "adjustment.created":
        return _on_adjustment_created(data)
    return WebhookOutcome(event_type=et, handled=False, note="ignored")


def _cd(data: dict) -> dict:
    return data.get("custom_data") or {}


def _on_transaction_completed(data: dict) -> WebhookOutcome:
    cd = _cd(data)
    user_id, plan = cd.get("user_id"), cd.get("plan")
    if not user_id or plan not in PLAN_GRANTS:
        return WebhookOutcome("transaction.completed", False,
                              f"missing user_id or plan (plan={plan!r})")
    granted = record_grant_once(
        user_id=user_id, amount=PLAN_GRANTS[plan], kind="subscription_renewal",
        reference_id=data.get("id"), description=f"{plan.capitalize()} plan renewal")
    period_end = (data.get("billing_period") or {}).get("ends_at")
    upsert_user_profile(
        user_id, current_plan=plan, current_period_end=period_end,
        payment_status="active")
    note = f"+{PLAN_GRANTS[plan]} for {plan}" if granted else "duplicate transaction, no-op"
    return WebhookOutcome("transaction.completed", True, note)


def _on_subscription_updated(data: dict) -> WebhookOutcome:
    cd = _cd(data)
    user_id, plan = cd.get("user_id"), cd.get("plan")
    if not user_id:
        return WebhookOutcome("subscription.updated", False, "no user_id")
    scheduled = data.get("scheduled_change") or {}
    period_end = ((data.get("current_billing_period") or {}).get("ends_at")
                  or data.get("next_billed_at"))
    upsert_user_profile(
        user_id,
        current_plan=(plan if plan in PLAN_GRANTS else "free"),
        current_period_end=period_end,
        cancel_at_period_end=(scheduled.get("action") == "cancel"))
    return WebhookOutcome("subscription.updated", True, f"plan={plan}")


def _on_subscription_canceled(data: dict) -> WebhookOutcome:
    user_id = _cd(data).get("user_id")
    if not user_id:
        return WebhookOutcome("subscription.canceled", False, "no user_id")
    upsert_user_profile(
        user_id, current_plan="free", current_period_end=None,
        cancel_at_period_end=False, payment_status="active")
    return WebhookOutcome("subscription.canceled", True, "plan reset to free")


def _on_subscription_past_due(data: dict) -> WebhookOutcome:
    user_id = _cd(data).get("user_id")
    if not user_id:
        return WebhookOutcome("subscription.past_due", False, "no user_id")
    upsert_user_profile(user_id, payment_status="past_due")
    return WebhookOutcome("subscription.past_due", True, "marked past_due")
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_paddle_billing.py -k webhook -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/paddle_billing.py tests/test_paddle_billing.py
git commit -m "feat(billing): paddle webhook dispatch + transaction/subscription handlers"
```

---

### Task 5: Refund/chargeback clawback (`adjustment.created`) + ignore path

**Files:**
- Modify: `pipeline/paddle_billing.py`
- Test: `tests/test_paddle_billing.py` (append)

**Interfaces:**
- Consumes: `get_grant_by_reference`, `record_grant_once`.
- Produces: `_on_adjustment_created(data: dict) -> WebhookOutcome`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_paddle_billing.py`:
```python
def test_webhook_adjustment_claws_back(paddle_env, monkeypatch):
    clawed = {}
    monkeypatch.setattr(pb, "get_grant_by_reference", lambda ref: ("u1", 60))
    monkeypatch.setattr(pb, "record_grant_once",
                        lambda **kw: (clawed.update(kw), True)[1])
    raw, sig = _wrap("adjustment.created", {
        "id": "adj_1", "action": "refund", "transaction_id": "txn_1", "status": "approved"})
    out = pb.handle_webhook(raw, sig)
    assert out.handled
    assert clawed["amount"] == -60 and clawed["kind"] == "chargeback_clawback"
    assert clawed["user_id"] == "u1" and clawed["reference_id"] == "adj_1"


def test_webhook_adjustment_no_grant_is_safe_noop(paddle_env, monkeypatch):
    called = {"n": 0}
    monkeypatch.setattr(pb, "get_grant_by_reference", lambda ref: None)
    monkeypatch.setattr(pb, "record_grant_once",
                        lambda **kw: called.__setitem__("n", called["n"] + 1))
    raw, sig = _wrap("adjustment.created",
                     {"id": "adj_2", "action": "refund", "transaction_id": "txn_none"})
    out = pb.handle_webhook(raw, sig)
    assert out.handled and called["n"] == 0


def test_webhook_unknown_event_ignored(paddle_env):
    raw, sig = _wrap("report.created", {"id": "rep_1"})
    out = pb.handle_webhook(raw, sig)
    assert out.handled is False
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_paddle_billing.py -k "adjustment or unknown" -v`
Expected: FAIL — `_on_adjustment_created` not defined (unknown-event test may already pass).

- [ ] **Step 3: Implement**

Append to `pipeline/paddle_billing.py`:
```python
def _on_adjustment_created(data: dict) -> WebhookOutcome:
    """A refund or chargeback. Resolve the funded transaction back to the grant
    and record an idempotent negative clawback keyed on the adjustment id."""
    action = data.get("action")
    if action not in ("refund", "chargeback", "chargeback_reverse"):
        return WebhookOutcome("adjustment.created", False, f"ignored action {action!r}")
    txn_id = data.get("transaction_id")
    if not txn_id:
        return WebhookOutcome("adjustment.created", False, "no transaction_id")
    grant = get_grant_by_reference(txn_id)
    if grant is None:
        return WebhookOutcome("adjustment.created", True, "no grant to claw back")
    user_id, amount = grant
    record_grant_once(user_id=user_id, amount=-amount, kind="chargeback_clawback",
                      reference_id=data.get("id"), description=f"{action} clawback")
    return WebhookOutcome("adjustment.created", True, f"clawed back {amount} from {user_id}")
```

- [ ] **Step 4: Run to verify pass, then the whole module suite**

Run: `uv run pytest tests/test_paddle_billing.py -v`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add pipeline/paddle_billing.py tests/test_paddle_billing.py
git commit -m "feat(billing): paddle refund/chargeback clawback + ignore path"
```

---

### Task 6: Rewire API endpoints to Paddle

**Files:**
- Modify: `pipeline/api.py` (lines ~1651-1666, ~1689-1698, and add a route after ~1716)
- Test: `tests/test_paddle_webhook_route.py`

**Interfaces:**
- Consumes: `paddle_billing.create_subscription_checkout`, `create_portal_session`, `handle_webhook`, `PaddleSignatureError`.
- Produces: `POST /paddle/webhook` route; `/billing/checkout-subscription` and `/billing/portal` now backed by Paddle.

- [ ] **Step 1: Write the failing test**

Create `tests/test_paddle_webhook_route.py`:
```python
from __future__ import annotations

import hashlib
import hmac
import json
import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("PADDLE_WEBHOOK_SECRET", "pdl_ntfset_secret")
    monkeypatch.setenv("FACELESS_API_TOKEN", "t")
    import pipeline.api as api
    return TestClient(api.app)


def _signed(body: dict):
    raw = json.dumps(body).encode()
    ts = str(int(time.time()))
    mac = hmac.new(b"pdl_ntfset_secret", f"{ts}:".encode() + raw, hashlib.sha256).hexdigest()
    return raw, f"ts={ts};h1={mac}"


def test_paddle_webhook_ok(client, monkeypatch):
    raw, sig = _signed({"event_type": "report.created", "data": {}})
    r = client.post("/paddle/webhook", content=raw, headers={"Paddle-Signature": sig})
    assert r.status_code == 200
    assert r.json()["handled"] is False


def test_paddle_webhook_bad_sig_returns_400(client):
    raw, _ = _signed({"event_type": "transaction.completed", "data": {}})
    r = client.post("/paddle/webhook", content=raw,
                    headers={"Paddle-Signature": "ts=1;h1=bad"})
    assert r.status_code == 400
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_paddle_webhook_route.py -v`
Expected: FAIL — 404 (no `/paddle/webhook` route).

- [ ] **Step 3: Rewire the endpoints**

In `pipeline/api.py`:

(a) In `/billing/checkout-subscription` (around line 1661), change the import line from:
```python
    from pipeline.stripe_billing import create_subscription_checkout
```
to:
```python
    from pipeline.paddle_billing import create_subscription_checkout
```

(b) In `/billing/portal` (around line 1696), change:
```python
    from pipeline.stripe_billing import create_portal_session
```
to:
```python
    from pipeline.paddle_billing import create_portal_session
```

(c) Add a new route immediately after the existing `stripe_webhook` function (after line 1716):
```python
@app.post("/paddle/webhook")
async def paddle_webhook(request: Request):
    """Paddle → us. No bearer auth; the Paddle-Signature HMAC is the proof.

    200 (even for ignored events) so Paddle stops retrying; 400 only for a
    bad signature.
    """
    raw = await request.body()
    signature = request.headers.get("paddle-signature", "")
    from pipeline.paddle_billing import PaddleSignatureError, handle_webhook
    try:
        outcome = handle_webhook(raw, signature)
    except PaddleSignatureError:
        raise HTTPException(400, "invalid signature")
    return {"received": True, "handled": outcome.handled, "note": outcome.note}
```

Leave `/stripe/webhook` and the `stripe_billing` import for `/billing/checkout-topup` in place (dormant — top-ups stay disabled, and Stripe is the rollback path).

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_paddle_webhook_route.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/api.py tests/test_paddle_webhook_route.py
git commit -m "feat(billing): route subscription checkout + portal + webhook through Paddle"
```

---

### Task 7: Deploy config + env (Cloud Run + .env)

**Files:**
- Modify: `deploy/cloud-run-service.yaml`
- Modify: `.env` (local, if present) — add the new keys with sandbox values
- Modify: `CLAUDE.md` (Tier-3/env section) — document the new env vars

**Interfaces:** none (config only). No code test; verified by a config lint + a smoke import.

- [ ] **Step 1: Add Paddle env to the Cloud Run service**

In `deploy/cloud-run-service.yaml`, in the container `env:` list, add (mirroring the existing secret + value patterns):
```yaml
            - name: PADDLE_ENV
              value: production
            - name: PADDLE_PRICE_STARTER
              value: ${PADDLE_PRICE_STARTER}
            - name: PADDLE_PRICE_CREATOR
              value: ${PADDLE_PRICE_CREATOR}
            - name: PADDLE_PRICE_PRO
              value: ${PADDLE_PRICE_PRO}
            - name: PADDLE_API_KEY
              valueFrom:
                secretKeyRef:
                  name: paddle-api-key
                  key: latest
            - name: PADDLE_WEBHOOK_SECRET
              valueFrom:
                secretKeyRef:
                  name: paddle-webhook-secret
                  key: latest
```

- [ ] **Step 2: Document the secret-creation commands (operator step, do NOT run with real values here)**

Add to `CLAUDE.md` under a new "Paddle billing (MoR)" note:
```bash
# Create the Paddle secrets in Secret Manager (operator runs these):
printf '%s' 'pdl_live_xxx'      | gcloud secrets create paddle-api-key --data-file=- || \
printf '%s' 'pdl_live_xxx'      | gcloud secrets versions add paddle-api-key --data-file=-
printf '%s' 'pdl_ntfset_xxx'    | gcloud secrets create paddle-webhook-secret --data-file=- || \
printf '%s' 'pdl_ntfset_xxx'    | gcloud secrets versions add paddle-webhook-secret --data-file=-
# Grant the runtime service account access to both (once):
#   gcloud secrets add-iam-policy-binding paddle-api-key \
#     --member=serviceAccount:faceless-runtime@$PROJECT.iam.gserviceaccount.com \
#     --role=roles/secretmanager.secretAccessor
```
And list `PADDLE_ENV`, `PADDLE_PRICE_STARTER/CREATOR/PRO` as required deploy-substitution vars.

- [ ] **Step 3: Add sandbox keys to local `.env` (if `.env` exists)**

Append (sandbox values, filled once the operator has a Paddle sandbox):
```bash
export PADDLE_ENV=sandbox
export PADDLE_API_KEY=
export PADDLE_WEBHOOK_SECRET=
export PADDLE_PRICE_STARTER=
export PADDLE_PRICE_CREATOR=
export PADDLE_PRICE_PRO=
```

- [ ] **Step 4: Verify the module imports clean + full suite is green**

Run: `uv run python -c "import pipeline.paddle_billing"` → no error.
Run: `uv run pytest tests/test_paddle_billing.py tests/test_paddle_webhook_route.py tests/test_db_paddle_customer.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add deploy/cloud-run-service.yaml CLAUDE.md .env
git commit -m "chore(billing): Paddle env + secrets wiring for Cloud Run"
```

---

## Post-plan: live cutover (not code — operator + assistant, tracked separately)

1. Operator finishes Paddle account verification (ID + `faceless-lab.com`) and creates 3 subscription prices + a **sandbox**.
2. Assistant runs the sandbox dress-rehearsal against the deployed API: subscribe (test card) → `transaction.completed` grants once → song approve deducts → issue a sandbox refund → `adjustment.created` claws back.
3. Operator puts **live** `PADDLE_API_KEY` / `PADDLE_WEBHOOK_SECRET` into Secret Manager (never in chat), sets live `PADDLE_PRICE_*` + `PADDLE_ENV=production`, creates the live webhook endpoint (subscribe it to `transaction.completed`, `subscription.updated`, `subscription.canceled`, `subscription.past_due`, `adjustment.created`) pointing at `https://api.faceless-lab.com/paddle/webhook`.
4. Redeploy (`./scripts/build-and-push.sh`) — this also ships the already-staged paywall UX fix.
5. Live smoke test: real $9 Starter on the operator's own account → credits granted → song approve works → refund → clawback confirmed.

## Self-review notes

- **Spec coverage:** checkout (Task 3), all five webhook events (Tasks 4-5), signature verify (Task 2), config (Task 7), schema for the customer id (Task 1), cutover (post-plan). ✓
- **Idempotency:** grant + clawback both keyed on Paddle ids and covered by dedupe tests. ✓
- **No app change:** endpoints keep their paths and response model (`CheckoutResponse`); only the backing module changes. ✓
- **Type consistency:** `WebhookOutcome(event_type, handled, note)`, `ensure_customer -> str`, `create_subscription_checkout -> str`, handlers all return `WebhookOutcome`. ✓
- **Field-path caveat:** Paddle event field paths (`billing_period.ends_at`, `current_billing_period.ends_at`, `scheduled_change.action`, `adjustment.action/transaction_id`) are encoded from Paddle Billing's documented shapes; confirm against a real sandbox event during the Task-4/5 sandbox rehearsal and adjust the accessor if a path differs. Handlers already fail safe (return `handled=False`/no-op) rather than 500 on a missing field.
