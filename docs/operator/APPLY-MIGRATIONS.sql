-- =============================================================================
-- FACELESS — pending Supabase migrations, bundled for one-paste application.
--
-- GENERATED FILE. Do not edit here — edit the source files under
-- supabase/migrations/ and regenerate. This is a convenience copy so an
-- operator without the Supabase CLI / psql can apply all pending migrations
-- in a single paste via the Supabase SQL Editor.
--
-- Apply this BEFORE the next code deploy: several authed endpoints SELECT the
-- new columns/tables and will 500 until these objects exist.
--
-- All statements are additive and idempotent (create-or-replace / if-not-exists
-- / add-column-if-not-exists), so re-running this file is safe.
--
-- Order matches supabase/migrations filename order:
--   20260804000001_deduct_credits_fn
--   20260804000002_grant_idempotency
--   20260804000003_payment_status
--   20260805000001_tos_acceptance
--   20260807000001_clawback_idempotency
--   20260807000002_rate_events
-- =============================================================================


-- ===== 20260804000001_deduct_credits_fn.sql =====
-- Atomic check-and-deduct: serialize per-user via an advisory lock so two
-- concurrent runs can't both pass the balance check and overspend.
create or replace function deduct_credits(
  p_user_id uuid, p_amount int, p_kind text,
  p_reference_id text, p_description text
) returns int language plpgsql as $$
declare v_balance int;
begin
  perform pg_advisory_xact_lock(hashtext(p_user_id::text));
  select coalesce(sum(amount), 0) into v_balance
    from credit_transactions where user_id = p_user_id;
  if v_balance < p_amount then
    return -1;  -- insufficient; caller raises InsufficientCredits
  end if;
  insert into credit_transactions(user_id, amount, kind, reference_id, description)
    values (p_user_id, -p_amount, p_kind, p_reference_id, p_description);
  return v_balance - p_amount;
end $$;


-- ===== 20260804000002_grant_idempotency.sql =====
-- A given Stripe invoice/session grants credits exactly once. A retried
-- webhook delivery then hits this unique index and is a no-op.
create unique index if not exists uq_credit_grant_ref
  on credit_transactions (reference_id, kind)
  where kind in ('subscription_renewal', 'topup');


-- ===== 20260804000003_payment_status.sql =====
alter table user_profiles
  add column if not exists payment_status text not null default 'active';


-- ===== 20260805000001_tos_acceptance.sql =====
alter table user_profiles
  add column if not exists tos_accepted_version text,
  add column if not exists tos_accepted_at timestamptz;


-- ===== 20260807000001_clawback_idempotency.sql =====
-- A given disputed/refunded charge claws back credits exactly once. A retried
-- charge.dispute.created / charge.refunded then hits this index and is a no-op.
create unique index if not exists uq_credit_clawback_ref
  on credit_transactions (reference_id, kind)
  where kind = 'chargeback_clawback';


-- ===== 20260807000002_rate_events.sql =====
-- Tier-4C abuse & cost controls: one DB-backed rate primitive.
-- Backs (a) the daily song-approve cap (was a per-instance JSON file on
-- GCS-Fuse, racy across Cloud Run instances) and (b) the per-user hourly
-- throttle on the unmetered LLM draft/regen endpoints.
create table if not exists public.rate_events (
  id         bigint generated always as identity primary key,
  user_id    uuid not null,
  action     text not null,
  created_at timestamptz not null default now()
);

create index if not exists rate_events_lookup
  on public.rate_events (user_id, action, created_at desc);

-- =============================================================================
-- End of bundle. Confirm via the super-admin dashboard's Activation card
-- (payment_status / tos_accepted_version / rate_events should all read present),
-- or re-run this file (idempotent) if unsure.
-- =============================================================================
