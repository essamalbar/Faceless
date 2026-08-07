# Tier-4A Billing Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (recommended) or executing-plans. Steps use `- [ ]`.

**Goal:** Stop disputed/refunded payments from leaving spendable credits (chargeback/refund → negative clawback txn), and pin the Stripe API version so the next payload reshape can't silently break the webhook.

**Architecture:** Two new webhook events (`charge.dispute.created`, `charge.refunded`) resolve the charge → the grant it funded (invoice.id / topup session.id) → a negative `chargeback_clawback` txn, idempotent by charge id via a new partial unique index (reusing `record_grant_once`). `stripe.api_version` pinned at module init.

**Tech Stack:** FastAPI/Stripe webhook, supabase-py, Postgres partial unique index.

**Verification env (IMPORTANT):** run pytest CLEAN — sourcing `.env` flips the failing set. Baseline **853 passed, 0 failed**:
```
env -u ANTHROPIC_API_KEY -u GROQ_API_KEY -u FACELESS_API_TOKEN -u KIE_API_KEY \
    -u ELEVENLABS_API_KEY -u SUPABASE_URL -u SUPABASE_SERVICE_ROLE_KEY \
    -u STRIPE_SECRET_KEY -u STRIPE_WEBHOOK_SECRET uv run pytest -q
```

---

## File Structure
- Create: `supabase/migrations/20260807000001_clawback_idempotency.sql`
- Modify: `pipeline/db.py` (add `get_grant_by_reference`)
- Modify: `pipeline/stripe_billing.py` (API-version pin + 2 event handlers + `_clawback_for_charge`)
- Modify: `tests/test_db.py`, `tests/test_stripe_billing.py`

---

## Task 1: Clawback idempotency index + `get_grant_by_reference`

**Files:** Create migration; modify `pipeline/db.py`; test `tests/test_db.py`.

- [ ] **Step 1: Migration** `supabase/migrations/20260807000001_clawback_idempotency.sql`:
```sql
-- A given disputed/refunded charge claws back credits exactly once. A retried
-- charge.dispute.created / charge.refunded then hits this index and is a no-op.
create unique index if not exists uq_credit_clawback_ref
  on credit_transactions (reference_id, kind)
  where kind = 'chargeback_clawback';
```
(Operator-applied before deploy; absence only means clawbacks aren't deduped, not a crash.)

- [ ] **Step 2: Failing tests** (append to `tests/test_db.py`):
```python
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
```
(If `tests/test_db.py` imports db as `import pipeline.db as db`, keep that; else adapt. `_FakeQuery`/`fake_client` already exist in the file.)

- [ ] **Step 3: Run — verify fail.**

- [ ] **Step 4: Implement** in `pipeline/db.py` (near `record_grant_once`):
```python
def get_grant_by_reference(reference_id: str) -> tuple[str, int] | None:
    """(user_id, total granted credits) for the grant(s) recorded under this
    reference_id (subscription_renewal / topup), or None. Sizes a clawback."""
    resp = (
        _client()
        .table("credit_transactions")
        .select("user_id,amount,kind")
        .eq("reference_id", reference_id)
        .execute()
    )
    rows = [r for r in (resp.data or [])
            if r.get("kind") in ("subscription_renewal", "topup")]
    if not rows:
        return None
    return rows[0]["user_id"], sum(int(r["amount"]) for r in rows)
```

- [ ] **Step 5: Run — verify pass**; full clean-env suite → 856 passed (853 + 3), 0 failed.

- [ ] **Step 6: Commit** — `feat(billing): clawback idempotency index + get_grant_by_reference` (+ trailer).

---

## Task 2: Dispute/refund clawback handlers + Stripe API-version pin

**Files:** `pipeline/stripe_billing.py`; test `tests/test_stripe_billing.py`.

- [ ] **Step 1: Failing tests** (append to `tests/test_stripe_billing.py`; use the existing `stripe_env` + `mock_db` fixtures + the `monkeypatch construct_event` pattern from `test_handle_webhook_invoice_failed_marks_past_due`):
```python
def test_stripe_api_version_is_pinned():
    import pipeline.stripe_billing  # noqa: F401  (import applies the pin)
    import stripe
    assert stripe.api_version == "2026-04-22.dahlia"


def test_charge_dispute_claws_back_grant(stripe_env, monkeypatch):
    import pipeline.stripe_billing as sb
    clawed = {}
    monkeypatch.setattr("pipeline.db.get_grant_by_reference", lambda ref: ("u1", 60))
    monkeypatch.setattr("pipeline.db.record_grant_once",
                        lambda **kw: (clawed.update(kw), True)[1])
    monkeypatch.setattr("pipeline.stripe_billing.stripe.Charge.retrieve",
                        lambda cid: {"id": cid, "invoice": "inv_1"})
    monkeypatch.setattr("pipeline.stripe_billing.stripe.Webhook.construct_event",
                        lambda **kw: {"type": "charge.dispute.created",
                                      "data": {"object": {"charge": "ch_1"}}})
    out = sb.handle_webhook(b"{}", "sig")
    assert out.handled
    assert clawed["amount"] == -60 and clawed["kind"] == "chargeback_clawback"
    assert clawed["user_id"] == "u1" and clawed["reference_id"] == "ch_1"


def test_charge_refunded_claws_back_grant(stripe_env, monkeypatch):
    import pipeline.stripe_billing as sb
    clawed = {}
    monkeypatch.setattr("pipeline.db.get_grant_by_reference", lambda ref: ("u1", 12))
    monkeypatch.setattr("pipeline.db.record_grant_once",
                        lambda **kw: (clawed.update(kw), True)[1])
    monkeypatch.setattr("pipeline.stripe_billing.stripe.Charge.retrieve",
                        lambda cid: {"id": cid, "invoice": "inv_2"})
    monkeypatch.setattr("pipeline.stripe_billing.stripe.Webhook.construct_event",
                        lambda **kw: {"type": "charge.refunded",
                                      "data": {"object": {"id": "ch_2", "refunded": True}}})
    out = sb.handle_webhook(b"{}", "sig")
    assert out.handled and clawed["amount"] == -12 and clawed["reference_id"] == "ch_2"


def test_charge_dispute_no_grant_is_safe_noop(stripe_env, monkeypatch):
    import pipeline.stripe_billing as sb
    called = {"n": 0}
    monkeypatch.setattr("pipeline.db.get_grant_by_reference", lambda ref: None)
    monkeypatch.setattr("pipeline.db.record_grant_once",
                        lambda **kw: called.__setitem__("n", called["n"] + 1))
    monkeypatch.setattr("pipeline.stripe_billing.stripe.Charge.retrieve",
                        lambda cid: {"id": cid, "invoice": "inv_none"})
    monkeypatch.setattr("pipeline.stripe_billing.stripe.Webhook.construct_event",
                        lambda **kw: {"type": "charge.dispute.created",
                                      "data": {"object": {"charge": "ch_3"}}})
    out = sb.handle_webhook(b"{}", "sig")
    assert out.handled and called["n"] == 0  # nothing clawed
```

- [ ] **Step 2: Run — verify fail.**

- [ ] **Step 3: Implement** in `pipeline/stripe_billing.py`:

At module top, right after `import stripe`:
```python
stripe.api_version = "2026-04-22.dahlia"  # pin: freeze the payload shape the webhook parses
```
In `handle_webhook`'s dispatch, before the final `return WebhookOutcome(..., "ignored")`:
```python
    if et == "charge.dispute.created":
        return _on_charge_disputed(data)
    if et == "charge.refunded":
        return _on_charge_refunded(data)
```
Add the handlers (near the other `_on_*`):
```python
def _on_charge_disputed(dispute) -> WebhookOutcome:
    charge_id = dispute.get("charge")
    if not charge_id:
        return WebhookOutcome("charge.dispute.created", False, "no charge id")
    return _clawback_for_charge(charge_id, "chargeback (dispute) clawback")


def _on_charge_refunded(charge) -> WebhookOutcome:
    charge_id = charge.get("id")
    if not charge_id:
        return WebhookOutcome("charge.refunded", False, "no charge id")
    return _clawback_for_charge(charge_id, "refund clawback")


def _clawback_for_charge(charge_id: str, reason: str) -> WebhookOutcome:
    """Resolve the charge to the grant it funded and record a negative,
    idempotent clawback (unique on (charge_id, chargeback_clawback))."""
    from pipeline.db import get_grant_by_reference, record_grant_once
    raw = stripe.Charge.retrieve(charge_id)
    charge = raw.to_dict() if hasattr(raw, "to_dict") else dict(raw)
    reference_id = charge.get("invoice")
    if not reference_id and charge.get("payment_intent"):
        sessions = stripe.checkout.Session.list(payment_intent=charge["payment_intent"])
        data = sessions.get("data") if isinstance(sessions, dict) else getattr(sessions, "data", [])
        if data:
            s0 = data[0]
            reference_id = s0.get("id") if isinstance(s0, dict) else getattr(s0, "id", None)
    if not reference_id:
        return WebhookOutcome("charge.clawback", False, "no grant reference resolved")
    grant = get_grant_by_reference(reference_id)
    if grant is None:
        return WebhookOutcome("charge.clawback", True, "no grant to claw back")
    user_id, amount = grant
    record_grant_once(user_id=user_id, amount=-amount, kind="chargeback_clawback",
                      reference_id=charge_id, description=reason)
    return WebhookOutcome("charge.clawback", True, f"clawed back {amount} from {user_id}")
```
(`_clawback_for_charge` retrieves the charge uniformly for both events so there's one resolution path; the extra retrieve on the refund event is harmless.)

- [ ] **Step 4: Run — verify pass** (`tests/test_stripe_billing.py`); full clean-env suite → no new failures (report count).

- [ ] **Step 5: Commit** — `feat(billing): chargeback/refund clawback + pin Stripe API version` (+ trailer).

---

## Task 3: Verification + operator handoff

**Files:** none (verification) + append to `docs/GO-LIVE-READINESS.md`.

- [ ] **Step 1: Full clean-env suite** → report exact count, 0 failed.
- [ ] **Step 2: Offline smoke** — `env -u SUPABASE_URL -u SUPABASE_SERVICE_ROLE_KEY uv run python -c "import pipeline.stripe_billing as sb, stripe; print('api_version', stripe.api_version); print('handlers', bool(sb._clawback_for_charge))"` → prints the pinned version + True.
- [ ] **Step 3: Operator handoff** — append a Tier-4A note to `docs/GO-LIVE-READINESS.md`: subscribe `charge.dispute.created` + `charge.refunded` in the Stripe Dashboard webhook; apply `20260807000001_clawback_idempotency.sql` before deploy; note a clawback can drive a balance negative (intended — blocks further spend until top-up). Note Stripe Tax still deferred + Tier-4 B/C/D still pending.
- [ ] **Step 4: Commit** — `docs: tier-4A billing hardening operator handoff` (+ trailer).
