# Apply the pending Supabase migrations (one paste)

You have **6 pending migrations** that must be applied to the **live** Supabase
database **before the next code deploy**. Several authenticated endpoints now
`SELECT` the new columns/tables (`payment_status`, `tos_accepted_version`,
`rate_events`) and the deduct/grant/clawback logic depends on the new function +
unique indexes — so if the code deploys first, those endpoints return **500**.

You don't need the Supabase CLI or `psql`. Everything is bundled into one file:
**[`APPLY-MIGRATIONS.sql`](./APPLY-MIGRATIONS.sql)**.

## Steps (Supabase SQL Editor)

1. Open the Supabase Dashboard → your project.
2. Left sidebar → **SQL Editor** → **New query**.
3. Open `docs/operator/APPLY-MIGRATIONS.sql` in this repo, **copy its entire
   contents**, and paste into the editor.
4. Click **Run** (or ⌘/Ctrl-Enter).
5. Expect **Success. No rows returned.** Every statement is additive and
   idempotent (`create or replace` / `if not exists` / `add column if not
   exists`), so nothing breaks if part of it was already applied — you can
   safely re-run the whole file.

## What it creates

| Object | Migration | Why |
|---|---|---|
| `deduct_credits(...)` function | `20260804000001` | atomic per-user check-and-deduct (advisory lock) |
| `uq_credit_grant_ref` unique index | `20260804000002` | Stripe grant idempotency (no double-grant on webhook retry) |
| `user_profiles.payment_status` column | `20260804000003` | dunning flag (`active` / `past_due`) |
| `user_profiles.tos_accepted_version` + `tos_accepted_at` | `20260805000001` | versioned ToS acceptance gate |
| `uq_credit_clawback_ref` unique index | `20260807000001` | chargeback/refund clawback idempotency |
| `rate_events` table + index | `20260807000002` | DB-backed daily song cap + LLM throttle |

## Confirm it worked

Two ways:

- **Super-admin dashboard** → the **Activation & health** card shows
  `payment_status`, `tos_accepted_version`, and `rate_events` as **present**.
  (The function + the two partial-unique indexes aren't probeable via the API;
  the card lists them as *verify in SQL editor* — see below.)
- **SQL Editor**, paste and run:
  ```sql
  select
    to_regprocedure('deduct_credits(uuid,int,text,text,text)') is not null as has_deduct_fn,
    to_regclass('public.rate_events')                          is not null as has_rate_events,
    exists (select 1 from information_schema.columns
            where table_name='user_profiles' and column_name='payment_status')      as has_payment_status,
    exists (select 1 from information_schema.columns
            where table_name='user_profiles' and column_name='tos_accepted_version') as has_tos_cols,
    (select count(*) from pg_indexes
     where indexname in ('uq_credit_grant_ref','uq_credit_clawback_ref'))            as clawback_grant_indexes;
  ```
  All booleans `true` and `clawback_grant_indexes = 2` → fully applied.

## Then

Deploy the current `main` (`scripts/build-and-push.sh`) — **after** this runs,
never before. This is step ① in `docs/GO-LIVE-READINESS.md`.
