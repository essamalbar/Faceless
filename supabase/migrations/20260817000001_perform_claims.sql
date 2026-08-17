-- "Make me sing this" (perform) double-charge guard.
--
-- The perform endpoint used to guard its charge->spawn critical section with an
-- O_EXCL file lock on the gcsfuse run dir. That lock does NOT hold across Cloud
-- Run instances, and _process_alive(pid) is meaningless cross-instance, so two
-- concurrent/rapid POST /songs/{id}/perform requests each deducted a fresh
-- per-attempt reference and BOTH charged. This migration moves the claim into a
-- single atomic Postgres transaction so exactly one caller can hold a run's
-- in-flight perform at a time, across every instance.
--
-- Model:
--   * perform_claims holds at most ONE row per run_id = the in-flight marker.
--   * claim_perform() atomically: takes a per-run advisory lock, refuses if a
--     live claim exists, steals a stale (crashed-worker) claim, checks balance,
--     inserts the run_charge, and inserts the claim row — all or nothing.
--   * release_perform_claim() deletes the claim, but ONLY when the caller's
--     reference matches (compare-and-delete) so a stale-state poll on another
--     instance can never release a newer attempt's live claim.

-- ---------------------------------------------------------------------------
-- 1. perform_claims: one active perform per run (the cross-instance mutex).
-- ---------------------------------------------------------------------------
create table if not exists public.perform_claims (
  run_id        text primary key,        -- one active claim per run
  user_id       uuid not null references auth.users(id) on delete cascade,
  reference_id  text not null,           -- the {run_id}:perform:{hex} charge ref
  amount        int  not null,
  claimed_at    timestamptz not null default now()
);

-- Backend writes go through the service_role (bypasses RLS). Enable RLS with no
-- user-facing policy so a leaked anon/authenticated JWT cannot read or write it.
alter table public.perform_claims enable row level security;

-- ---------------------------------------------------------------------------
-- 2. claim_perform: atomic in-flight guard + charge.
--
-- Returns jsonb:
--   { ok:true,  balance:<int>, stolen_reference_id:<text|null> }
--   { ok:false, reason:'in_flight' }
--   { ok:false, reason:'insufficient', balance:<int>, stolen_reference_id:<text|null> }
--
-- stolen_reference_id is the ref of a stale (crashed) claim this call reclaimed;
-- the caller refunds it (idempotent) so the abandoned render's charge is undone.
--
-- p_stale_seconds: age past which a claim is treated as an abandoned/crashed
-- render and stolen. MUST exceed the worker's whole render ceiling (render poll
-- timeout + uploads + queue + spawn latency), NOT the old 120s charge->spawn
-- window — stealing a claim whose worker is still alive re-opens two concurrent
-- renders and two charges. Caller passes >= 3600.
-- ---------------------------------------------------------------------------
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
  -- Serialize concurrent claims for THIS run across all instances (the
  -- cross-instance guard the O_EXCL file lock could not provide on gcsfuse).
  perform pg_advisory_xact_lock(hashtext('perform:' || p_run_id));
  -- Also take the per-user lock so the balance check below cannot race a
  -- concurrent deduct_credits (song approve) into a negative balance — the
  -- same race deduct_credits' own user lock exists to close. Lock order is
  -- run -> user here; deduct_credits takes only user, release takes only run,
  -- so no cycle can form.
  perform pg_advisory_xact_lock(hashtext(p_user_id::text));

  select * into v_existing from public.perform_claims where run_id = p_run_id;
  if found then
    if now() - v_existing.claimed_at < make_interval(secs => p_stale_seconds) then
      return jsonb_build_object('ok', false, 'reason', 'in_flight');
    end if;
    -- Stale claim: the prior render is definitively abandoned (older than the
    -- whole render ceiling). Steal it and hand its ref back for refund.
    v_stolen_ref := v_existing.reference_id;
    delete from public.perform_claims where run_id = p_run_id;
  end if;

  if p_is_service then
    -- Service tokens bypass the ledger (mirrors credits.check_or_deduct) but
    -- STILL take the claim so a service redo cannot double-spawn a render.
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

-- ---------------------------------------------------------------------------
-- 3. release_perform_claim: compare-and-delete by (run_id, reference_id).
--
-- Ref-scoped so a poll that read a STALE api_state.json on another instance
-- (older attempt's ref) cannot delete a NEWER attempt's live claim. Returns the
-- reference_id it deleted, or null if nothing matched (stale/no-op release).
-- ---------------------------------------------------------------------------
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

-- ---------------------------------------------------------------------------
-- 4. Lock the new functions down to the service_role.
--
-- Postgres grants EXECUTE on new functions to PUBLIC by default, and PostgREST
-- exposes them to the anon/authenticated roles at /rpc/<name>. Because these
-- take the target user id as a PARAMETER, an exposed function would let any
-- logged-in user charge or reclaim any account. Revoke from the client roles;
-- the backend calls them via the service_role, which is unaffected.
--
-- deduct_credits has the same shape and the same latent exposure — lock it too.
revoke execute on function public.claim_perform(uuid, text, int, text, text, boolean, int) from public, anon, authenticated;
revoke execute on function public.release_perform_claim(text, text) from public, anon, authenticated;
revoke execute on function public.deduct_credits(uuid, int, text, text, text) from public, anon, authenticated;
