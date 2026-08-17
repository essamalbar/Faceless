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
--   20260811000001_paddle_customer_id
--   20260817000001_perform_claims
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


-- ===== 20260811000001_paddle_customer_id.sql =====
-- Paddle (Merchant of Record) customer id, analogous to stripe_customer_id.
-- Additive + idempotent so re-running the bundle is safe.
alter table user_profiles
  add column if not exists paddle_customer_id text;


-- ===== 20260817000001_perform_claims.sql =====
-- "Make me sing this" (perform) double-charge guard. The old O_EXCL file lock
-- on the gcsfuse run dir did not serialize across Cloud Run instances (and pids
-- are meaningless cross-instance), so two concurrent perform requests each
-- deducted a fresh reference and BOTH charged. This moves the claim into one
-- atomic Postgres transaction: exactly one caller holds a run's in-flight
-- perform at a time, across every instance.
create table if not exists public.perform_claims (
  run_id        text primary key,        -- one active claim per run
  user_id       uuid not null references auth.users(id) on delete cascade,
  reference_id  text not null,           -- the {run_id}:perform:{hex} charge ref
  amount        int  not null,
  claimed_at    timestamptz not null default now()
);
alter table public.perform_claims enable row level security;

-- Atomic in-flight guard + charge. Returns jsonb:
--   {ok:true,  balance, stolen_reference_id}
--   {ok:false, reason:'in_flight'}
--   {ok:false, reason:'insufficient', balance, stolen_reference_id}
-- p_stale_seconds: age past which a claim is treated as a crashed render and
-- stolen (caller refunds stolen_reference_id). MUST exceed the whole render
-- ceiling; the caller passes >= 3600.
create or replace function public.claim_perform(
  p_user_id      uuid,
  p_run_id       text,
  p_amount       int,
  p_reference_id text,
  p_description  text,
  p_is_service   boolean,
  p_stale_seconds int
) returns jsonb language plpgsql as $$
declare
  v_existing   public.perform_claims%rowtype;
  v_stolen_ref text := null;
  v_balance    int;
begin
  -- Serialize concurrent claims for THIS run across all instances, then take
  -- the per-user lock so the balance check can't race a concurrent
  -- deduct_credits. Lock order run -> user (deduct takes only user, release
  -- only run) → no cycle.
  perform pg_advisory_xact_lock(hashtext('perform:' || p_run_id));
  perform pg_advisory_xact_lock(hashtext(p_user_id::text));

  select * into v_existing from public.perform_claims where run_id = p_run_id;
  if found then
    if now() - v_existing.claimed_at < make_interval(secs => p_stale_seconds) then
      return jsonb_build_object('ok', false, 'reason', 'in_flight');
    end if;
    v_stolen_ref := v_existing.reference_id;   -- crashed render → steal it
    delete from public.perform_claims where run_id = p_run_id;
  end if;

  if p_is_service then
    insert into public.perform_claims(run_id, user_id, reference_id, amount)
      values (p_run_id, p_user_id, p_reference_id, p_amount);
    return jsonb_build_object(
      'ok', true, 'balance', 1000000000, 'stolen_reference_id', v_stolen_ref);
  end if;

  select coalesce(sum(amount), 0) into v_balance
    from public.credit_transactions where user_id = p_user_id;
  if v_balance < p_amount then
    return jsonb_build_object(
      'ok', false, 'reason', 'insufficient',
      'balance', v_balance, 'stolen_reference_id', v_stolen_ref);
  end if;

  insert into public.credit_transactions(user_id, amount, kind, reference_id, description)
    values (p_user_id, -p_amount, 'run_charge', p_reference_id, p_description);
  insert into public.perform_claims(run_id, user_id, reference_id, amount)
    values (p_run_id, p_user_id, p_reference_id, p_amount);
  return jsonb_build_object(
    'ok', true, 'balance', v_balance - p_amount, 'stolen_reference_id', v_stolen_ref);
end $$;

-- Compare-and-delete by (run_id, reference_id) so a stale-state poll on another
-- instance can't release a newer attempt's live claim.
create or replace function public.release_perform_claim(
  p_run_id text, p_reference_id text
) returns text language plpgsql as $$
declare v_ref text;
begin
  perform pg_advisory_xact_lock(hashtext('perform:' || p_run_id));
  delete from public.perform_claims
    where run_id = p_run_id and reference_id = p_reference_id
    returning reference_id into v_ref;
  return v_ref;
end $$;

-- These functions take the target user id as a PARAMETER; without this an
-- exposed PostgREST /rpc/<name> would let any logged-in user charge/reclaim any
-- account. The backend calls them via the service_role, which is unaffected.
-- deduct_credits has the same shape and latent exposure — lock it too.
revoke execute on function public.claim_perform(uuid, text, int, text, text, boolean, int) from public, anon, authenticated;
revoke execute on function public.release_perform_claim(text, text) from public, anon, authenticated;
revoke execute on function public.deduct_credits(uuid, int, text, text, text) from public, anon, authenticated;

-- =============================================================================
-- End of bundle. Confirm via the super-admin dashboard's Activation card
-- (payment_status / tos_accepted_version / rate_events should all read present),
-- or re-run this file (idempotent) if unsure.
-- =============================================================================
