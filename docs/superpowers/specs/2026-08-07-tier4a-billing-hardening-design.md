# Tier-4A Billing Hardening — Design

**Date:** 2026-08-07
**Status:** approved (brainstorm) — pending spec review → implementation plan
**Scope:** First of four decomposed Tier-4 sub-projects (A billing → B auth → C abuse/cost → D data/ops). **A = two pure-code money-safety items:** (1) chargeback/dispute + refund **credit clawback**, (2) **Stripe API-version pin**. Stripe Tax is deferred (Dashboard registrations + tax-liability decision the operator owns; add the `automatic_tax` hook later).

## Context (verified against code, 2026-08-07)

- Stripe webhook (`pipeline/stripe_billing.py`) dispatches `checkout.session.completed`, `invoice.payment_succeeded`, `invoice.payment_failed`, `customer.subscription.updated/deleted`. **No dispute/refund handling** → a disputed/refunded payment leaves its granted credits spendable (money leak).
- **Grant→source mapping:** topup grant `reference_id = checkout_session.id`, `kind="topup"`; subscription grant `reference_id = invoice.id`, `kind="subscription_renewal"` (`record_grant_once`, `db.py:127`).
- `record_grant_once(*, user_id, amount, kind, reference_id, description) -> bool` is a **generic** insert-if-absent (unique-violation → `False`). A **negative** amount + a clawback kind reuses it directly once the unique index covers that kind.
- Idempotency index today: `uq_credit_grant_ref on credit_transactions(reference_id, kind) where kind in ('subscription_renewal','topup')`.
- **stripe-python 15.1.0**, default `api_version = "2026-04-22.dahlia"`. `stripe.api_key = _api_key()` is set inside each function; **`stripe.api_version` is never set** (unpinned).
- The webhook already tolerates both legacy + 2025 invoice shapes (`_invoice_subscription_id`, `_first_item_period_end`, `_invoice_parent_metadata`), so pinning the version is safe.

## Architecture

### A1 — Chargeback/dispute + refund clawback

- **Migration** `supabase/migrations/20260807000001_clawback_idempotency.sql`:
  ```sql
  create unique index if not exists uq_credit_clawback_ref
    on credit_transactions (reference_id, kind)
    where kind = 'chargeback_clawback';
  ```
- **`pipeline/db.py`** — add `get_grant_by_reference(reference_id: str) -> tuple[str, int] | None`: query `credit_transactions` for the grant row(s) with this `reference_id` and `kind in ('subscription_renewal','topup')`; return `(user_id, total_granted_amount)` or `None`. (Reuse `record_grant_once` for the negative clawback insert — no new writer needed.)
- **`pipeline/stripe_billing.py`** — dispatch two new events in `handle_webhook`:
  - `charge.dispute.created` → `_on_charge_disputed(data)` (the event object is a `dispute`; `dispute.charge` is the charge id, `dispute.amount` in cents).
  - `charge.refunded` → `_on_charge_refunded(data)` (the event object is the `charge`; `charge.refunded` true).
  - Both funnel into one helper `_clawback_for_charge(charge_id, reason) -> WebhookOutcome`:
    1. `charge = stripe.Charge.retrieve(charge_id)`.
    2. Resolve the grant `reference_id`: if `charge.invoice` → that invoice id (subscription grant); elif `charge.payment_intent` → `stripe.checkout.Session.list(payment_intent=charge.payment_intent).data[0].id` (topup grant). If neither resolves → `WebhookOutcome(handled=False, "no grant reference")` (nothing to claw).
    3. `grant = get_grant_by_reference(reference_id)`; if `None` → `handled=True, "no grant to claw back"` (e.g. dispute on a charge that never granted — safe no-op).
    4. `record_grant_once(user_id=grant.user_id, amount=-grant.amount, kind="chargeback_clawback", reference_id=charge_id, description=reason)`. **Idempotent by `(charge_id, 'chargeback_clawback')`** — a re-delivered dispute/refund for the same charge is a no-op. `reference_id = charge_id` (not the grant ref) so dispute-then-refund on the same charge doesn't double-claw either.
    5. Return `WebhookOutcome(True, "clawed back N credits")`.
  - **Balance semantics (decided):** the negative txn drops the balance — below zero if the credits were already spent — and the atomic `deduct_credits` (`check_or_deduct`) then blocks further spend until the user tops up. Honest ledger; no account-flag/unblock state (that was the rejected option).
- **Operator:** subscribe `charge.dispute.created` + `charge.refunded` in the Stripe Dashboard webhook (like `invoice.payment_failed` in Phase 0).

### A2 — Stripe API-version pin

- In `pipeline/stripe_billing.py`, at module import (right after `import stripe`), set:
  ```python
  stripe.api_version = "2026-04-22.dahlia"  # pin: freeze the payload shape the webhook parses
  ```
  Freezes the shape so the next Stripe default bump can't silently reshape `invoice`/`charge`/`subscription` payloads out from under the parser. (The webhook keeps its legacy+new fallbacks as defence-in-depth.)

## Testing

- **`tests/test_stripe_billing.py`** (extend; mocked — never hit real Stripe/DB):
  - `charge.dispute.created` → resolves the charge → `get_grant_by_reference` (mocked to `(u1, 60)`) → a **-60** `chargeback_clawback` txn recorded for `u1`, idempotent (2nd delivery no-ops via the unique-violation → `record_grant_once` False). Drive through `handle_webhook` with monkeypatched `construct_event`, `stripe.Charge.retrieve`, and (topup path) `stripe.checkout.Session.list`.
  - `charge.refunded` → same clawback path.
  - dispute on a charge with **no matching grant** → `handled=True`, no txn (safe no-op).
  - `stripe.api_version` is pinned to the expected string at import.
- **`tests/test_db.py`**: `get_grant_by_reference` returns `(user_id, amount)` for a grant row and `None` when absent (fake_client).
- **Baseline:** clean-env suite is **853 passed, 0 failed** (`env -u <all API-key vars> uv run pytest -q`). No new failures; new tests pass.

## Deploy coupling
Apply `20260807000001_clawback_idempotency.sql` before deploy (additive index; absence would only mean clawbacks aren't deduped, not a crash — but apply it). Subscribe the two Stripe events. Same operator-ordering as prior migrations.

## Deferred (tracked)
- **Stripe Tax** (this sub-project's dropped item): add `automatic_tax={'enabled': True}` + address collection to the checkout sessions once the operator enables Tax + registrations in the Dashboard.
- **Tier-4 B/C/D** sub-projects: auth hardening; abuse/cost controls; data/ops hygiene.

## Key invariants respected
- External services mocked in tests; migration operator-applied (reviewed by reading).
- Clawback reuses the existing `record_grant_once` idempotency pattern (unique index by `(reference_id, kind)`), reference_id = the Stripe charge id.
- Service tokens are irrelevant here (webhook is Stripe-signed, no user bearer); the clawback targets the grant's recorded `user_id`.
- New `db.py` code: `from __future__ import annotations`, absolute imports.
