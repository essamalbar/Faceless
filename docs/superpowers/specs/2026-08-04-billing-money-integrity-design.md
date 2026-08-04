# Billing Money-Integrity Hardening (Go-Live Phase 0)

**Date:** 2026-08-04
**Status:** Design approved; ready for implementation plan
**Source:** the Tier-1 blockers in `docs/GO-LIVE-READINESS.md` (four-audit synthesis).
**Scope:** the 5 money-integrity blockers that make it unsafe to charge real users, plus greening the money/video test path. One cohesive spec.

## Problem

The credit system's foundation is sound (durable Supabase ledger, per-user JWT auth, single reconciled table), but five defects lose money or corrupt balances the moment real users pay:

1. **The video/shorts pipeline never charges anyone.** Paid-stage workers are spawned without a user id, so `run.py` defaults `--user-id` to `"admin"` → role `service` → `check_or_deduct` no-ops → the balance never decrements. Any user with credits renders unlimited real-money Veo/Kling, unbilled.
2. **Song cancel + song failure never refund.** Song credits are deducted at approve (in the API handler, correctly, for the real user), but `cancel_song` and the song worker's failure handler don't refund — charged, got nothing.
3. **Double-spend race.** `check_or_deduct` reads balance then inserts a debit as two unguarded round-trips; parallel approves both pass the check and drive the balance negative.
4. **Stripe webhook isn't idempotent.** At-least-once delivery + no unique constraint on the grant reference means a retried `invoice.payment_succeeded` double-grants credits.
5. **No dunning.** A failed renewal card is invisible in-app for days (no `invoice.payment_failed` handling).

Plus: **7 pre-existing test failures** sit on the money/video critical path and must be triaged/greened before launch.

## Goals

- Every paid render (video AND song) deducts the correct credits from the **real** user.
- No path charges a user and leaves them with nothing (cancel/failure always refunds net charges).
- Deduction is atomic — no double-spend under concurrency.
- Stripe grants are idempotent — a duplicate webhook never double-grants.
- Failed renewals are visible to the user (dunning).
- The money/video test path is green.

## Non-goals (deferred to later go-live phases)

- Monitoring/alerting, spend caps, backups (Phase 1 — infra/operator).
- Legal/compliance: ToS, DMCA, GDPR delete, moderation (Phase 2).
- Chargeback/dispute handling, Stripe Tax, top-up packs, password reset, email-verification backstop (Tier 4 — post-launch).

---

## Fix 1 — Charge the real user for video renders (`run.py`)

**Root cause:** on `--resume`, `_resolve_run_dir` uses the resume dir directly and `args.user_id` stays `"admin"`; `_stage_video_chained` computes `role = "service" if args.user_id == "admin" else "user"` (`run.py:511`) and the refund block does the same (`run.py:843`) — both wrong, so `_charge_and_submit_clip` / the refund no-op.

**Approach (approved): derive the user from the run-dir path — one forget-proof chokepoint.** The run dir is always `<out_root>/<user_id>/<run_id>` (`_make_run_dir`, `run.py:88-89`). After `_resolve_run_dir` returns `run_dir`, compute the effective user id as the path segment directly under `out_root`:

```python
def _effective_user_id(run_dir: Path, out_root: Path) -> str:
    try:
        return run_dir.resolve().relative_to(out_root.resolve()).parts[0]
    except (ValueError, IndexError):
        return "admin"   # fall back to service (free) if the layout is unexpected
```

Use that value wherever role/user is derived today (`run.py:511-512` video charge, `run.py:843-844` video refund, and the song path in Fix 2). Runs under `out/admin/…` (CLI/cron/service) still resolve to `"admin"` → service → free, exactly as intended. This fixes **all 13 spawn sites at once** without touching `api.py`, and can't be forgotten per-site.

**Behavior change (pre-launch, intended):** after this fix the video pipeline actually enforces credits. There are no real paying users yet (test accounts only), so nothing to migrate; this is the model working as designed before launch.

**Test:** a resumed video run under `out/<uuid>/…` deducts (role `user`); a run under `out/admin/…` does not (role `service`).

## Fix 2 — Refund song cancel + song failure (`api.py`, `run.py`)

`refund_run_charges(user, run_id, reason)` already exists and is net-safe (`credits.py:94-131`). Wire it into the two song holes:

- **`cancel_song` (`api.py:3513-3527`)** — has the authenticated `user` via `require_user`; call `refund_run_charges(user, run_id=…, reason="song canceled")` after killing the process. Mirrors the video `cancel_run` (`api.py:2523-2566`).
- **Song worker failure (`run.py` `_run_song_post_approve` catch-all, ~`run.py:1532-1544`)** — on terminal failure, refund the real user (from Fix 1's `_effective_user_id`) via `refund_run_charges`, mirroring the video assembly refund (`run.py:842-865`).

**Test:** approving a song then cancelling refunds the net charge; a song worker exception refunds; a successful run does NOT refund; refund is net-safe (no double-refund if a partial refund already happened).

## Fix 3 — Atomic deduction (`db.py`, `credits.py`, migration)

**Approach (approved): a Postgres function called via `.rpc()`**, so check-and-deduct is one atomic transaction under a per-user advisory lock. Migration `supabase/migrations/<ts>_deduct_credits_fn.sql`:

```sql
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
```
(Match `p_user_id`'s type to the actual `credit_transactions.user_id` column type.)

`db.py` gains `deduct_credits_atomic(user_id, amount, kind, reference_id, description) -> int` calling `_client().rpc("deduct_credits", {...}).execute()` and returning the int. `credits.check_or_deduct` (non-service path) delegates to it: `-1` → `raise InsufficientCredits(...)`; else return the new balance. The old read-then-insert is removed. Two concurrent deducts now serialize on the advisory lock, so the balance can never go negative.

**Test:** `check_or_deduct` calls the rpc and raises `InsufficientCredits` when it returns `-1`, returns the new balance otherwise; service tokens still bypass; the db layer builds the correct rpc call (mocked). (True concurrency is enforced by Postgres, not unit-tested — the mock verifies wiring.)

## Fix 4 — Idempotent Stripe grants (`stripe_billing.py`, `db.py`, migration)

**Approach (approved): a DB unique index makes duplicate grants impossible; the webhook treats a conflict as already-processed.** Migration `supabase/migrations/<ts>_grant_idempotency.sql`:

```sql
create unique index if not exists uq_credit_grant_ref
  on credit_transactions (reference_id, kind)
  where kind in ('subscription_renewal', 'topup');
```
(Use the exact grant `kind` values the webhook writes — confirm in `stripe_billing.py` during implementation.)

`db.py` gains `record_grant_once(...)` that inserts and, on a unique-violation error from Supabase, returns `False` (already granted) instead of raising. The webhook grant handlers (`_on_invoice_paid`, `_on_checkout_completed` topup path) call it and log/skip on `False`. A retried Stripe delivery for the same invoice/session becomes a no-op. (This closes both the retry case and the concurrent-double-delivery race.)

**Test:** a first grant inserts and returns `True`; a second grant with the same `(reference_id, kind)` returns `False` and does not change balance; the webhook handler is idempotent across duplicate events.

## Fix 5 — Dunning: surface failed renewals (`stripe_billing.py`, `db.py`, `api.py`, Flutter, migration)

Migration `supabase/migrations/<ts>_payment_status.sql`:
```sql
alter table user_profiles add column if not exists payment_status text not null default 'active';
```
- **`stripe_billing.py`**: add `invoice.payment_failed` → `_on_invoice_failed` → `upsert_user_profile(user_id, payment_status='past_due')`. On the next successful `invoice.payment_succeeded` (and on `customer.subscription.deleted`), reset `payment_status='active'`.
- **`api.py` `/billing/plan`**: include `payment_status` in the response.
- **Flutter `billing_screen.dart`**: when `payment_status == 'past_due'`, show a banner ("Your last payment failed — update your card") with a button to the Stripe Customer Portal (the existing `/billing/portal` flow).
- **Operator action:** subscribe `invoice.payment_failed` in the Stripe Dashboard (see Operator actions).

**Test:** the `invoice.payment_failed` handler sets `past_due`; a subsequent success resets to `active`; `/billing/plan` surfaces the field; (Flutter banner is a widget-render check if feasible, else manual).

## Fix 6 — Green the money/video test path

The 7 pre-existing failures: `test_api::test_approve_passes_auto_computed_max_spend`, 2× `test_mp4_faststart`, 3× `test_run_shorts_smoke`, `test_llm_groq::test_complete_sends_chat_payload`. Triage:
- **Stale assertions (fix):** `test_approve_passes_auto_computed_max_spend` (asserts a max-spend range that predates the current kling model rate — update to the active model's computed spend); `test_llm_groq` (asserts the old default model name — update to `openai/gpt-oss-120b`).
- **Triage:** `test_mp4_faststart` (2), `test_run_shorts_smoke` (3) — determine if they are real defects or local-ffmpeg-only environment failures. Fix if real; if purely environmental, document precisely (they must pass in the prod Debian-ffmpeg container) and do not paper over.

Any of Fixes 1–5 that touch these paths must not add new failures.

---

## Migrations (operator-applied)

Three SQL migrations land in `supabase/migrations/`: `deduct_credits` function (Fix 3), grant unique index (Fix 4), `payment_status` column (Fix 5). **The code is written and tested here; applying them to the live Supabase database is an operator step** — the CI/deploy does not run migrations. Document the exact `supabase db push` (or SQL editor) command in the plan.

## Operator actions (outside code — for the plan's handoff)

1. Apply the three migrations to the live Supabase DB.
2. Subscribe `invoice.payment_failed` in the Stripe Dashboard webhook config (Fix 5).
3. Redeploy (`scripts/build-and-push.sh`) after code + migrations are in.

## Testing

External services mocked (Supabase `.rpc()`/tables, Stripe, ffmpeg) per the repo invariant. New/updated tests:
- `run.py`: `_effective_user_id` (uuid path → user, admin path → service); resumed-run deducts (Fix 1); song-failure refunds (Fix 2).
- `api.py`: `cancel_song` refunds (Fix 2); `/billing/plan` exposes `payment_status` (Fix 5).
- `credits.py`/`db.py`: `check_or_deduct` via the atomic rpc, insufficient → raise (Fix 3); `record_grant_once` idempotency (Fix 4).
- `stripe_billing.py`: `invoice.payment_failed` → past_due, success → active (Fix 5); duplicate grant is a no-op (Fix 4).
- Green the 6 money/video tests (Fix 6).

## Files touched

- `run.py` — `_effective_user_id`, use it for video charge/refund + song-failure refund.
- `pipeline/credits.py` — `check_or_deduct` delegates to atomic rpc.
- `pipeline/db.py` — `deduct_credits_atomic`, `record_grant_once`.
- `pipeline/stripe_billing.py` — idempotent grants, `invoice.payment_failed`, status resets.
- `pipeline/api.py` — `cancel_song` refund; `/billing/plan` payment_status.
- `lib/screens/billing_screen.dart` (+ l10n) — past-due banner.
- `supabase/migrations/*` — 3 new SQL files.
- `tests/` — `test_credits*`, `test_stripe_billing`, `test_run_song_mode`, `test_song_api`, `test_api`, `test_mp4_faststart`/`test_run_shorts_smoke` triage.

## Rollout & safety

Fixes 2–5 are strictly safer (more refunds, atomic deduct, idempotent grants, visible dunning). Fix 1 *starts* enforcing video credits that were silently free — intended pre-launch, no real users affected. Ship the whole bundle behind the existing deploy; verify with the money end-to-end test (subscribe → render → deduct → cancel → refund → no negative balance) before opening payments.

## Follow-ups (out of scope)

Chargeback/dispute handling, Stripe Tax, API-version pinning, rate-limit move to DB, LLM draft/regen metering, data-retention TTL — all tracked in `docs/GO-LIVE-READINESS.md` (Tier 4).
