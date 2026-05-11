# B3 — Stripe Subscriptions + Credits Design

**Status:** approved 2026-05-11
**Owner:** Essam
**Phase:** 2 (cloud + auth + billing) — second of B2-B7
**Builds on:** B2 (Supabase Auth + per-user run isolation, live at `https://faceless-api-uplzdtffeq-uc.a.run.app`)

## Goal

Turn the faceless pipeline into a self-serve SaaS: end-users sign up, get
a free trial, then either subscribe monthly or buy credit packs. Every
generated video deducts credits from their balance, refunds on upstream
failure, and the UI surfaces a paywall instead of an error when they run
out.

This unlocks every other future-phase milestone — there's no SaaS until
there's billing.

## Decisions (locked from brainstorm, 2026-05-11)

| Decision | Choice | Why |
|---|---|---|
| Credit unit | **1 credit = 1 second of Veo video** | Matches Kie wholesale cost (~$0.10/sec). User sees "this 30-sec video costs 30 credits" — instantly understandable. |
| Pricing model | **Subscription + top-up packs** | Subscription captures regulars, top-ups catch overage and one-offs. |
| Free trial | **30 credits at signup** | One ~30-sec test video. Cost to us: ~$3 worst case. |
| Deduction timing | **Per-clip at Veo submit, refund on failure** | Failed clips never charge. Charging upfront would refund-storm; charging on completion would race. |
| Balance store | **Supabase Postgres**, append-only ledger | Free tier already provisioned. Append-only avoids race conditions; balance = `SUM(amount)`. |
| Stripe surfaces | **Hosted Checkout + Customer Portal** | We don't build payment UIs. Both are PCI-compliant by default and handle EU/MENA tax. |
| Currency | **USD primary** | Stripe handles per-user FX. |
| Service token | **Exempt from credit checks** | CLI / cron / admin keep working at no cost. |

### Pricing (USD)

| Plan | Price | Credits | $/credit | ~30s videos | Cost to us (Kie @ $0.10/s) |
|---|---|---|---|---|---|
| Free trial | $0 (one-time) | 30 | — | 1 | $3 |
| Starter | $9 / mo | 60 / mo | $0.15 | 1-2 | $6/mo gross → $3/mo profit |
| Creator | $29 / mo | 250 / mo | $0.12 | 5-8 | $25/mo gross → $4/mo profit |
| Pro | $79 / mo | 800 / mo | $0.10 | 15-25 | $80/mo cost → break-even (loss leader for high-volume creators) |
| Top-up pack S | $5 | 30 | $0.17 | overage | $3 cost → $2 profit |
| Top-up pack M | $15 | 100 | $0.15 | overage | $10 cost → $5 profit |
| Top-up pack L | $40 | 300 | $0.13 | overage | $30 cost → $10 profit |

Pro plan is intentionally thin to anchor the price ceiling; top-up packs
keep margins healthy on overage. Adjustable post-launch.

## Architecture

```
                Flutter app
                  │
                  ├──── /billing/balance ────────┐
                  ├──── /billing/plan ───────────┤
                  ├──── /billing/checkout-sub ───┤ (returns Stripe URL)
                  ├──── /billing/checkout-pack ──┤ (returns Stripe URL)
                  └──── /billing/portal ─────────┤ (returns Stripe URL)
                                                  │
                                                  ▼
                                        Cloud Run Service (faceless-api)
                                                  │
                  ┌─── Stripe webhook ────────────┤
                  │                               │
                  │ /stripe/webhook ◀─────────────┘ (no auth; verifies signature)
                  │
                  ▼
            ┌─────────────────────────────────┐
            │  Supabase Postgres              │
            │  ┌──────────────────────────┐   │
            │  │ user_profiles            │   │
            │  │  - id (FK auth.users)    │   │
            │  │  - stripe_customer_id    │   │
            │  │  - current_plan          │   │
            │  │  - current_period_end    │   │
            │  └──────────────────────────┘   │
            │  ┌──────────────────────────┐   │
            │  │ credit_transactions      │   │
            │  │  - user_id, amount, kind │   │
            │  │  - reference_id          │   │
            │  │ (append-only ledger)     │   │
            │  └──────────────────────────┘   │
            │  user_balance VIEW = SUM(amount)│
            └─────────────────────────────────┘
                  ▲
                  │ writes from worker (run.py) — per clip
                  │
            Cloud Run Job (faceless-pipeline)
            pipeline.video.generate_clips_chained:
              for each clip:
                deduct(user_id, ceil(clip_duration_s), run_id, "run_charge")
                submit clip to Veo
                if failed: refund(user_id, ceil(clip_duration_s), run_id, "run_refund")
```

## Database schema

Three objects in the `public` schema:

```sql
-- 1. App-specific user metadata. The Supabase Auth tables stay in `auth.*`;
-- we only extend with billing-relevant fields.
create table public.user_profiles (
  id                    uuid primary key references auth.users(id) on delete cascade,
  stripe_customer_id    text unique,
  current_plan          text not null default 'free',
                        -- enum: 'free' | 'starter' | 'creator' | 'pro'
  current_period_end    timestamptz,
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now()
);

-- 2. Append-only credit ledger. Never UPDATE or DELETE rows; corrections
-- are new rows with `kind='admin_adjust'`.
create table public.credit_transactions (
  id                    uuid primary key default gen_random_uuid(),
  user_id               uuid not null references auth.users(id) on delete cascade,
  amount                integer not null,
                        -- positive for credit, negative for debit
  kind                  text not null,
                        -- 'signup_grant' | 'subscription_renewal' | 'topup' |
                        -- 'run_charge' | 'run_refund' | 'admin_adjust'
  reference_id          text,
                        -- run_id for run_charge/refund;
                        -- stripe_session_id or invoice_id for renewal/topup
  description           text,
  created_at            timestamptz not null default now()
);
create index credit_transactions_user_id_created_at_idx
  on public.credit_transactions(user_id, created_at desc);

-- 3. Convenience view: current balance per user.
create view public.user_balance as
  select user_id, coalesce(sum(amount), 0)::integer as balance
  from public.credit_transactions
  group by user_id;
```

### Row-Level Security (RLS)

```sql
-- user_profiles: users read/update their own row, server-side writes via service_role
alter table public.user_profiles enable row level security;
create policy "users read own profile" on public.user_profiles
  for select using (auth.uid() = id);

-- credit_transactions: users can read their own ledger; writes only via service_role
alter table public.credit_transactions enable row level security;
create policy "users read own transactions" on public.credit_transactions
  for select using (auth.uid() = user_id);

-- The view inherits via the underlying table RLS.
```

All writes go through the backend (which authenticates as the
service_role key from Secret Manager). The Flutter app never writes
directly to these tables — it goes through the API.

## New backend modules

### `pipeline/db.py` (new)

Thin wrapper around `supabase-py` for app-specific queries:

```python
def get_user_profile(user_id: str) -> UserProfile | None
def upsert_user_profile(user_id: str, **fields) -> UserProfile
def get_balance(user_id: str) -> int
def record_transaction(
    user_id: str, amount: int, kind: str,
    reference_id: str | None = None, description: str | None = None,
) -> None
def list_transactions(user_id: str, limit: int = 50) -> list[Transaction]
```

Connection: uses `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` env vars.
The service role bypasses RLS so the backend can write on behalf of users.

### `pipeline/credits.py` (new)

The credit business logic — sits on top of `db.py`:

```python
SIGNUP_GRANT = 30
PLAN_GRANTS = {'starter': 60, 'creator': 250, 'pro': 800}
TOPUP_PACKS = {'topup_30': 30, 'topup_100': 100, 'topup_300': 300}

def ensure_signup_grant(user: User) -> None:
    """If user_profiles row doesn't exist, create it AND grant 30 credits.
    Idempotent — checked on every authenticated API call (cheap one-row select)."""

def check_or_deduct(user: User, amount: int, run_id: str, reason: str) -> int:
    """Verifies user has >= amount credits, then atomically inserts the debit.
    Returns the new balance. Raises InsufficientCredits if balance < amount.
    Admin/service tokens bypass the check and don't write a transaction."""

def refund(user: User, amount: int, run_id: str, reason: str) -> None:
    """Inserts a positive transaction. Used when a Veo clip fails after
    deduction. No-op for service tokens."""
```

`InsufficientCredits` is a typed exception so the API can map it to a
402 Payment Required response with the user-friendly hint.

### `pipeline/stripe_billing.py` (new)

Stripe-facing logic — kept in its own module so the rest of the
codebase doesn't import Stripe:

```python
PLAN_PRICE_IDS = {
    'starter': os.environ['STRIPE_PRICE_STARTER'],
    'creator': os.environ['STRIPE_PRICE_CREATOR'],
    'pro':     os.environ['STRIPE_PRICE_PRO'],
}
PACK_PRICE_IDS = {
    'topup_30':  os.environ['STRIPE_PRICE_TOPUP_30'],
    'topup_100': os.environ['STRIPE_PRICE_TOPUP_100'],
    'topup_300': os.environ['STRIPE_PRICE_TOPUP_300'],
}

def ensure_customer(user: User) -> str:
    """Returns Stripe customer_id for the user, creating one on first call.
    Stores it in user_profiles.stripe_customer_id."""

def create_subscription_checkout(user: User, plan: str, success_url: str) -> str:
    """Returns a Stripe Checkout URL for a new subscription."""

def create_topup_checkout(user: User, pack: str, success_url: str) -> str:
    """Returns a Stripe Checkout URL for a one-time top-up pack."""

def create_portal_session(user: User, return_url: str) -> str:
    """Returns a Stripe Customer Portal URL — handles upgrade, downgrade,
    cancel, view invoices."""

def handle_webhook(raw_body: bytes, signature: str) -> None:
    """Verifies the Stripe-Signature header, decodes the event, and routes
    to the right handler. Raises on bad signature."""
```

## New API endpoints

All require Supabase auth (via existing `require_user`) except the webhook:

| Method | Path | Body | Returns | Notes |
|---|---|---|---|---|
| GET  | `/billing/balance` | — | `{balance: int}` | Cheap, used by UI on every screen |
| GET  | `/billing/plan` | — | `{plan, period_end, balance}` | Combined dashboard query |
| GET  | `/billing/transactions` | `?limit=50` | `[{...}]` | Ledger view |
| POST | `/billing/checkout-subscription` | `{plan, success_url}` | `{url}` | Redirects user to Stripe |
| POST | `/billing/checkout-topup` | `{pack, success_url}` | `{url}` | Redirects user to Stripe |
| POST | `/billing/portal` | `{return_url}` | `{url}` | Cancel/upgrade/invoices |
| POST | `/stripe/webhook` | Stripe event | `{received: true}` | **No auth**, verifies signature |

The existing `/runs/freeform` and `/runs/from-script` endpoints gain a
pre-flight credit check: compute estimated cost from `req` (sum of
clip durations, default 8s × beat count), reject with **402 Payment
Required** + the existing user-friendly hint if balance < estimate.

## Worker changes

`run.py` (CLI orchestrator, already accepts `--user-id` from B2) gains
two new things:

1. **Per-clip credit deduction** before each Veo `submit_video_job` call,
   refund on `KieError` / unsuccessful clip. New module `pipeline/credits.py`
   handles this; `_stage_video_chained` passes the per-clip duration in.

2. **Service-token bypass**: when `--user-id admin` (the CLI default), all
   credit operations are no-ops. The CLI keeps working at no in-database
   cost.

## Frontend changes

### New screen: `lib/screens/billing_screen.dart`
- Shows current balance, plan, period_end
- Three subscription tier cards with "Subscribe" buttons → calls
  `/billing/checkout-subscription` → opens returned URL in a new browser tab
- Three top-up pack cards
- "Manage subscription" button → `/billing/portal`
- Transactions list (last 50)

### New widget: `lib/widgets/paywall_dialog.dart`
- Shown when a /runs/* call returns 402
- "You need N credits, you have M. Subscribe or buy a top-up?"
- Buttons that route to the billing screen

### Home screen + Run detail: balance badge
- Top-right corner: "🪙 124 credits"
- Tapping it opens the billing screen
- Polled on screen-load and after returning from Stripe Checkout

### Settings screen
- Add a "Billing" row that opens the billing screen
- (Sign-out button from B2 stays as-is)

### `lib/api/client.dart`
- Add five new methods: `getBalance()`, `getPlan()`, `createSubscriptionCheckout()`, `createTopupCheckout()`, `createPortalSession()`
- 402 responses surface as a typed `InsufficientCreditsException` so the UI can route to the paywall

## Cloud Run config

New env vars + secrets:

| Var | Source | On Service? | On Job? |
|---|---|---|---|
| `SUPABASE_SERVICE_ROLE_KEY` | already in Secret Manager (B2) | ✅ | ✅ (for worker DB writes) |
| `STRIPE_SECRET_KEY` | new Secret Manager entry | ✅ | ❌ |
| `STRIPE_WEBHOOK_SECRET` | new Secret Manager entry | ✅ | ❌ |
| `STRIPE_PRICE_*` | new env vars (public IDs) | ✅ | ❌ |

The webhook endpoint accepts unauthenticated POSTs (Stripe → us). The
Service's `allUsers → roles/run.invoker` already allows this.

## Stripe-side setup (one-time, manual)

Done in the Stripe dashboard before first deploy:

1. **Products + prices**:
   - 3 recurring products: Starter ($9/mo), Creator ($29/mo), Pro ($79/mo)
   - 3 one-time products: Pack S ($5), Pack M ($15), Pack L ($40)
2. **Customer Portal config**: enable cancel + upgrade/downgrade + invoice view
3. **Webhook endpoint**:
   `https://faceless-api-uplzdtffeq-uc.a.run.app/stripe/webhook`
   Listen for: `customer.subscription.created`, `customer.subscription.updated`,
   `customer.subscription.deleted`, `invoice.payment_succeeded`,
   `checkout.session.completed`

Copy the webhook signing secret + price IDs into `.env` and run
`setup-cloud-run.sh` to push them to Secret Manager.

## Webhook handler logic

```
event = stripe.Webhook.construct_event(body, sig, STRIPE_WEBHOOK_SECRET)
match event.type:
  case 'checkout.session.completed':
    if mode == 'subscription':
      # First-time subscriber. Stripe will fire invoice.payment_succeeded too,
      # but we set the customer_id mapping here.
      upsert_user_profile(user_id, stripe_customer_id=customer)
    elif mode == 'payment':
      # One-time top-up
      pack = session.metadata['pack']
      record_transaction(user_id, +TOPUP_PACKS[pack], 'topup', session.id)

  case 'invoice.payment_succeeded':
    # Subscription renewal (also fires for the first cycle).
    plan = derive_plan_from_subscription(subscription_id)
    record_transaction(user_id, +PLAN_GRANTS[plan], 'subscription_renewal', invoice.id)
    upsert_user_profile(user_id, current_plan=plan,
                        current_period_end=subscription.current_period_end)

  case 'customer.subscription.updated':
    # Upgrade/downgrade. Plan change only — no credit grant (handled by
    # the invoice.payment_succeeded fired on plan change with proration).
    upsert_user_profile(user_id, current_plan=derive_plan(...))

  case 'customer.subscription.deleted':
    upsert_user_profile(user_id, current_plan='free', current_period_end=None)
```

**user_id resolution**: Stripe metadata is the single source of truth.
When we create the Checkout session we set it in **two** places:

```python
stripe.checkout.Session.create(
    ...
    customer=customer_id,
    metadata={'user_id': user.id},                     # on Session
    subscription_data={'metadata': {'user_id': user.id}},  # on the eventual Subscription
)
```

Setting `subscription_data.metadata` is the Stripe footgun — without it,
the Subscription object created downstream has no metadata, so
`invoice.payment_succeeded` (which references a subscription, not a
session) can't find the user. The webhook reads metadata directly from
the event object and never has to round-trip through `customer_id`.

**Plan upgrade behavior**: we grant the full `PLAN_GRANTS[plan]` on every
`invoice.payment_succeeded` event, regardless of whether it's a fresh
renewal or a mid-period upgrade. This is deliberately simple — a user who
upgrades from Starter to Creator mid-month gets the full 250 Creator
credits added to their balance (alongside any unused Starter credits).
Generous, but it removes a class of refund/proration bugs and the
expected churn is low.

**Cancel behavior**: when the user cancels via the Customer Portal,
Stripe fires `customer.subscription.deleted` at the end of the paid
period (not immediately). We flip `current_plan` to `'free'` at that
point. Existing credits in the ledger are untouched — they don't expire
on cancellation.

## Out of scope for B3

- Marketing landing page → **B5**
- Annual billing (with discount) → can add later, Stripe handles the price config
- Multi-currency display in the app
- Team / organization accounts
- Referral codes / discount codes (Stripe supports it natively if we want it later)
- Detailed admin analytics dashboard
- Email receipts beyond what Stripe sends automatically
- Refunding more than the failed clip (full-run refunds via admin tools — out of scope)

## Risks + mitigations

| Risk | Mitigation |
|---|---|
| Webhook delivery race (user back in app before Stripe → us) | UI polls `/billing/balance` for 30 sec after returning from Checkout; Stripe retries failed webhooks for 3 days regardless |
| User cancels mid-period, credits remain | Documented behavior — credits don't expire on cancel. Re-subscribing adds fresh credits on next renewal. |
| Concurrent run starts → double-spend | DB-level — the ledger insert is a single statement; balance check happens in a transaction with `SELECT … FOR UPDATE` on the lock row. Cheaper alternative: optimistic insert, accept that two parallel runs from the same user might transiently overspend by one Veo clip ($0.10). Picking the cheaper path for v1. |
| Stripe webhook signature spoofing | Mandatory — never skip `Webhook.construct_event` |
| Test mode vs live mode keys mixed | Use separate Stripe accounts (or `sk_test_…` vs `sk_live_…` env vars enforced by setup-cloud-run.sh check) |
| Worker can't write to DB (no service-role on Job) | Already in Secret Manager — extend the Job YAML in T6 of the plan to mount it |
| Veo failure refund races with worker timeout | Refund is the LAST thing the worker does on a failed clip; if the container dies mid-refund, the credit is lost. Acceptable — operator can reconcile via the admin endpoint. |
| User signs up but never triggers `ensure_signup_grant` (e.g. their first API call is 5xx) | Idempotency: every authenticated request runs `ensure_signup_grant`, which is a one-row SELECT with `EXISTS`. Cheap. |

## Acceptance criteria

1. New user signs up via the Flutter app → on first API call, 30 credits land in their ledger.
2. User generates a 30-second video → 30 credits deducted (after Veo success); UI balance shows -30.
3. User generates a video that fails on clip 4 of 6 → 30 credits charged (3 successful × 10s), 30 refunded (3 failed × 10s), net 0 change for the failed half.
4. User runs out of credits → POST `/runs/freeform` returns 402; Flutter shows the paywall dialog.
5. User clicks "Subscribe Starter" → Stripe Checkout opens → on success, balance shows 60 credits and `plan = 'starter'`.
6. User clicks "Buy 30 credits" → Stripe Checkout opens → on success, balance shows +30.
7. User cancels their subscription via the Customer Portal → plan flips to 'free'; existing credits survive.
8. Service token (`Authorization: Bearer $FACELESS_API_TOKEN`) bypasses credit checks (CLI keeps working).
9. Webhook with bad signature returns 400.
10. The full pytest suite stays green (≥ 373 passing).

## Stretch (optional, only if cheap to add)

- "Top up" button surfaces directly in the paywall dialog (no detour to billing screen)
- Show pricing comparison in the paywall ("$5 for 30 credits, $9/mo for 60")
- Email when balance < 10 credits (cron + Supabase auth.users.email)
