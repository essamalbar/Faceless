# Paddle (Merchant-of-Record) billing migration — design

**Date:** 2026-08-11
**Status:** approved (design), pending implementation plan
**Author:** pairing session (operator: essam)

## Problem

Real payments must go live. Stripe is not usable: Stripe UAE requires a trade
license / freelancer permit for the account holder, and the operator is a solo
individual with no registered business and does not want to create a license,
permit, or company. Stripe onboarding is therefore a hard wall.

The fix is a **Merchant of Record (MoR)** — a platform that is legally the
*seller*, so the operator needs no trade license and no company. **Paddle** is
the chosen MoR: it accepts individuals/sole proprietors (no KYB), charges
~5% + $0.50 per sale with $0 upfront and no monthly fee, and handles global
VAT/tax. Verification is personal ID + a reviewed website (`faceless-lab.com`),
not a license.

## Current state (what we're replacing)

- `pipeline/stripe_billing.py` — the only module that imports `stripe`. Two
  jobs: build Stripe-hosted Checkout URLs, and verify + dispatch Stripe
  webhooks. Public surface used by `pipeline/api.py`:
  `create_subscription_checkout`, `create_topup_checkout`,
  `create_portal_session`, `handle_webhook`.
- The **credit ledger is provider-agnostic** and stays exactly as-is:
  `record_grant_once`, `deduct_credits` (Postgres RPC), `get_grant_by_reference`,
  `get_balance`, `upsert_user_profile`. Plan sizes live in
  `pipeline.credits.PLAN_GRANTS = {"starter":12, "creator":60, "pro":200}`.
- Prod Stripe is **test mode only** — there are **no real subscribers**, so this
  is a clean cutover with no data migration.
- Top-up packs are already disabled (empty price env vars) and stay disabled.

## Goals / non-goals

**Goals**
- Take real subscription payments ($9 / $29 / $79 per month → 12 / 60 / 200
  credits) through Paddle, with credits granted on payment and clawed back on
  refund/chargeback.
- Zero change to the Flutter app and zero change to the credit ledger.

**Non-goals (YAGNI)**
- Top-up one-time packs (stay disabled).
- Migrating any existing subscriber (none exist).
- A generic multi-provider billing abstraction. We port to Paddle directly.
- Paddle.js in-app overlay checkout (rejected in favor of hosted redirect).

## Design

### New module: `pipeline/paddle_billing.py`

Mirrors `stripe_billing.py`'s public surface so `pipeline/api.py` changes are
minimal (swap the import + the webhook signature-header name). Talks to Paddle
via a **thin `httpx` client against Paddle's REST API** (no heavy SDK dependency;
easy to mock in tests per the "external services mocked in tests" invariant).

Public functions:
- `create_subscription_checkout(user, plan, success_url, cancel_url) -> str`
  1. Resolve/create the Paddle **customer** for the user (store
     `paddle_customer_id` on the user profile, analogous to today's
     `stripe_customer_id`).
  2. `POST /transactions` with `items=[{price_id, quantity:1}]`,
     `customer_id`, and `custom_data={"user_id": ..., "plan": ...}`.
     **Critical:** the same `custom_data` must land on the *subscription*, not
     just this first transaction — Paddle auto-generates each renewal
     transaction from the subscription and copies the subscription's
     `custom_data` onto it. If `user_id` lived only on the initial transaction,
     month-2 renewals would arrive with no user to credit. (This mirrors the
     "must duplicate metadata onto the subscription" note in the Stripe code.)
     For a subscription-mode transaction Paddle propagates the transaction's
     `custom_data` to the created subscription; the implementation must verify
     this and, if not automatic, set it explicitly once the subscription exists.
  3. Return the transaction's `checkout.url` (Paddle-hosted checkout page).
     Requires a **Default Payment Link** configured in the Paddle dashboard
     pointing at Paddle's hosted checkout; `success_url` is set as the
     post-purchase redirect back to `app.faceless-lab.com`.
- `handle_webhook(raw_body, signature) -> WebhookOutcome`
  Verify the `Paddle-Signature` header (format `ts=<unix>;h1=<hmac>`, where
  `h1 = HMAC_SHA256(secret, f"{ts}:{raw_body}")`; reject if the computed HMAC
  doesn't match or `ts` is too old), decode JSON, dispatch on `event_type`.
- `create_portal_session(user, return_url) -> str` — Paddle customer portal URL
  (self-serve manage/cancel), analogous to the Stripe billing portal.

### Webhook event mapping

`user_id` and `plan` travel in the transaction/subscription `custom_data` we set
at checkout, so handlers never need an extra lookup to identify the user.

| Paddle event | Handler action (existing ledger calls) |
|---|---|
| `transaction.completed` | grant plan credits — `record_grant_once(user_id, PLAN_GRANTS[plan], kind="subscription_renewal", reference_id=transaction_id)`; set profile `current_plan`, `current_period_end` (from subscription `next_billed_at`), `payment_status="active"`. Idempotent on `transaction_id`. |
| `subscription.updated` | `upsert_user_profile(current_plan, current_period_end=next_billed_at, cancel_at_period_end = (scheduled_change.action == "cancel"))`. |
| `subscription.canceled` | `upsert_user_profile(current_plan="free", current_period_end=None, cancel_at_period_end=False, payment_status="active")`. |
| `subscription.past_due` | `upsert_user_profile(payment_status="past_due")`. |
| `adjustment.created` (refund or chargeback) | clawback: resolve the adjustment's `transaction_id` → the grant it funded via `get_grant_by_reference`, then `record_grant_once(-amount, kind="chargeback_clawback", reference_id=adjustment_id)`. Idempotent on `adjustment_id`. |
| anything else | ignored (`handled=False`). |

Idempotency is unchanged: the `uq_credit_grant_ref` / `uq_credit_clawback_ref`
unique indexes (just migrated) make duplicate webhook deliveries no-ops.

### Config (replaces the `STRIPE_*` env)

New env, added to `.env`, Secret Manager, and `deploy/cloud-run-service.yaml`:
- `PADDLE_API_KEY` (secret) — server API key.
- `PADDLE_WEBHOOK_SECRET` (secret) — endpoint signing secret.
- `PADDLE_PRICE_STARTER`, `PADDLE_PRICE_CREATOR`, `PADDLE_PRICE_PRO` — live price
  ids (env, non-secret).
- `PADDLE_ENV` = `sandbox` | `production` — selects the API base URL
  (`https://sandbox-api.paddle.com` vs `https://api.paddle.com`).

New route `POST /paddle/webhook` (no auth; trust via signature), alongside the
existing `/stripe/webhook` which becomes dormant. The `/billing/checkout`
endpoint switches to `paddle_billing.create_subscription_checkout`.

`stripe_billing.py` and its env are left in place but unused (dormant), to avoid
churn and keep an easy rollback.

### Error handling

- Bad webhook signature → handler raises; the route returns **400** (Paddle
  retries). Never 500 on a signature failure.
- Unknown/ignored event → **200** with `handled=False` (so Paddle doesn't retry
  a well-formed event we simply don't act on).
- Missing `user_id`/`plan` in `custom_data`, or unknown plan → **200** +
  `handled=False` note (logged), not a 500 — a retry won't help.
- Paddle API errors during checkout creation → surface as HTTP 502/503 to the
  app with a user-facing "couldn't start checkout, try again" message.

## Testing

Per the repo invariant, **no live Paddle calls in tests.** The `httpx` client is
injected/monkeypatched so unit tests feed canned Paddle JSON:
- checkout: asserts we POST the right price id + `custom_data`, and return the
  `checkout.url`.
- webhook signature: a known secret + body produces a matching `h1`; tampered
  body / stale `ts` is rejected.
- each event handler: `transaction.completed` grants exactly once (second
  delivery is a no-op), `subscription.canceled` resets to free,
  `adjustment.created` claws back the funded grant, unknown event → ignored.

Live **sandbox** dress-rehearsal (operator + assistant, later): subscribe with a
Paddle sandbox card → credits granted once → song approve deducts → issue a
sandbox refund → clawback fires.

## Cutover plan

1. Build + unit-test `paddle_billing.py` (mocked) — can happen now, before
   Paddle signup completes.
2. Operator: create Paddle account (personal ID + `faceless-lab.com` review),
   create the 3 subscription products/prices, and a **sandbox** to test against.
3. Assistant: sandbox dress-rehearsal end-to-end.
4. Go live: put live `PADDLE_API_KEY` / `PADDLE_WEBHOOK_SECRET` into Secret
   Manager (operator, never pasted in chat), set live `PADDLE_PRICE_*` +
   `PADDLE_ENV=production`, create the live webhook endpoint (all mapped events)
   pointing at `https://api.faceless-lab.com/paddle/webhook`, redeploy.
5. Live smoke test: a real $9 Starter on the operator's own account → credits
   granted → song approve works → refund it → confirm clawback.

The paywall UX fix already staged (route 402 → PaywallDialog) ships in the same
redeploy.
