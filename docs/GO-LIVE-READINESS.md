# Go-Live Readiness Plan — Faceless Lab

**Date:** 2026-08-04
**Scope:** Launch the AI song/video system to real, paying, public users.
**Method:** Four parallel code audits — auth/email, Stripe payments, credits ledger, ops/security/cost. Findings below are grounded in the code (file:line), not assumptions.

## Verdict

The engineering **foundation is sound**: per-user Supabase-JWT auth (correctly verified + tested), a **durable** external credit ledger (Supabase Postgres), secrets in Google Secret Manager, an approve-before-spend gate, and a single reconciled Stripe+pipeline ledger. **But it is NOT safe to charge real users today** — there are money-losing bugs (unbilled renders, no refunds on failure, double-spend, webhook double-grants) and missing operational + legal guardrails. Everything here is fixable; none is architectural.

## Reality check — how billing actually works (corrected)

Prior notes were stale. Confirmed against code:

- **No signup / free-trial grant.** Removed 2026-05-13 (`pipeline/credits.py:7-12`; `ensure_signup_grant` never implemented). New users start at **0 credits**; script generation is free, every paid stage requires a subscription. → Confirm launch messaging matches (no "free trial" funnel).
- **Plans:** Starter **12 cr / $9**, Creator **60 cr / $29**, Pro **200 cr / $79** (`pipeline/credits.py:28`, prices via `STRIPE_PRICE_*`). Design doc's 60/250/800 is stale.
- **Top-up packs disabled** (`credits.py:29` `TOPUP_PACKS = {}`); `/billing/checkout-topup` always 400s.
- **Ledger is durable** — Supabase Postgres, provisioned on the API Service and the worker Job. Survives redeploys/restarts. (The feared "ephemeral disk" risk does not apply.)

## What's already solid (do not rebuild)

- Auth: HS256 + ES256/RS256-via-JWKS, correct `alg` pinning, `exp`/`aud`/`sub` checks, admin endpoints gated to the service token. Tested (`tests/test_auth.py`).
- Ledger: append-only `credit_transactions` + `user_balance` view; Stripe grants and pipeline deducts hit the **same** table (no drift); user-visible history via `GET /billing/transactions`.
- Secrets: Secret Manager `secretKeyRef` in prod; `.env`/keys excluded from image; web bundle ships `FACELESS_API_TOKEN=` **empty** (only the public `SUPABASE_ANON_KEY` is baked in).
- Stripe: webhook signature verified on the raw body; metadata plumbed to survive `invoice.payment_succeeded`; defenses against the 2025 Stripe API payload reshape (with regression tests).
- Spend design: approve-before-spend genuinely gates Kie spend; per-user cost bounded by DB balance; Kie calls have real retry/backoff.

---

## TIER 1 — Money-integrity BLOCKERS (fix before ANY paying user)

| # | Gap | Evidence | Fix | Owner |
|---|-----|----------|-----|-------|
| 1 | **Shorts/Veo pipeline never charges users.** Worker spawned without `--user-id` → runs as `admin`/`service` → `check_or_deduct` no-ops → **balance never decrements**. Any user with credits renders unlimited real-money Veo/Kling forever, unbilled. | 13 `_SPAWN_FN` sites in `api.py` pass no `--user-id`; `run.py:596-600` defaults to `"admin"`; `run.py:511-512` → role `service`; `credits.py:59-60` no-ops. | Pass `"--user-id", user.id` in every paid-stage spawn; `_stage_video_chained` + refund block already do the right thing once the id is correct. | Code |
| 2 | **Song cancel leaves the user charged with nothing** (only `/admin/credit-back` could fix it). Credits deducted at approve; `cancel_song` didn't refund. | `api.py` `cancel_song` (no refund). | `cancel_song` refunds via `refund_run_charges` (self-service money-back). **Failure keeps the charge** — resume retries free (auto-refunding failure + free resume = free songs; policy decided in review). | Code |
| 3 | **Double-spend race.** `check_or_deduct` is read→compare→insert with no DB lock; parallel approves both pass the balance check and go negative. File-based concurrency/daily caps are themselves TOCTOU races. | `credits.py:46-71` (no `FOR UPDATE`/`.rpc`); caps `api.py:3120-3132`, `3176-3189`. | Move check-and-deduct into a Postgres function via `.rpc()`: `UPDATE … WHERE balance >= amount RETURNING …` (or advisory lock on `user_id`). | Code |
| 4 | **Stripe webhook not idempotent.** At-least-once delivery; a retried `invoice.payment_succeeded` double-grants credits (no unique constraint on `reference_id`). | `stripe_billing.py:219-231`, `176-183`; schema `…credits.sql:29-46` (reference_id plain text). | Dedup on Stripe `event.id` (unique index or check-before-insert on `(reference_id, kind)`). | Code + DB migration |
| 5 | **No dunning.** Failed renewal card silently shows "active" for days/weeks; no `invoice.payment_failed` handled or subscribed. | `stripe_billing.py:147-155` (no branch); Dashboard event list omits it; UI has no past-due state (`billing_screen.dart:190-206`). | Subscribe to `invoice.payment_failed`; flag `payment_status='past_due'`; surface "update your card" in the app. | Code + Stripe Dashboard |

## TIER 2 — Can't-operate-blind BLOCKERS (fix before launch)

| # | Gap | Evidence | Fix | Owner |
|---|-----|----------|-----|-------|
| 6 | **No monitoring / alerting / error tracking.** All `print()`. Failed renders, Kie outages, the double-grant above — all invisible until a user complains. | No Sentry/structured logging/metrics anywhere (grep clean). | Add Sentry (or equivalent) + Cloud Monitoring alerts on 5xx, Job failure, and billing anomalies. | Infra |
| 7 | **No infra spend ceiling.** Cloud Run `maxScale` unset (defaults 100) + no GCP billing budget + no Kie account cap, on an app that spends per request. | `deploy/cloud-run-service.yaml` (no maxScale); `setup-cloud-run.sh:208-210` public invoker. | Set `autoscaling.knative.dev/maxScale`; add a GCP Billing Budget with alerts; set a hard Kie.ai spend cap. | Infra |
| 8 | **No Supabase backup** of the credit/payment ledger (financial system of record). | Nothing in-repo backs up Supabase. | Enable Supabase PITR / scheduled backups. | Infra |
| 9 | **7 failing tests on the money/video path.** | `test_api::test_approve_passes_auto_computed_max_spend`, 2× `test_mp4_faststart`, 3× `test_run_shorts_smoke`, `test_llm_groq` stale model. | Green the spend-gate + faststart tests (fix or update stale assertions) before launch. | Code |

> **Tier-2 status (2026-08-05):** the CODE pieces are done — GCP-native structured logging + API 5xx catch-all handler (`pipeline/observability.py`, wired into `pipeline/api.py` + `run.py`) and Cloud Run `autoscaling.knative.dev/maxScale: "4"`. Item 9 (the 7 failing tests) was greened in Phase 0. The remaining operator steps — billing budget, monitoring alerts, Supabase PITR, Kie account cap — are scripted (`scripts/setup-billing-budget.sh`, `scripts/setup-monitoring-alerts.sh`) and checklisted in **`docs/TIER2-INFRA.md`**. Chosen approach: GCP-native (no Sentry).

## TIER 3 — Legal/compliance BLOCKERS (Stripe + app stores require; copyright exposure)

| # | Gap | Fix | Owner |
|---|-----|-----|-------|
| 10 | **No Terms of Service / Privacy Policy / refund policy** (site or app). Stripe + app stores mandate them. | Publish ToS + Privacy + refund policy; add acceptance at signup/checkout; footer links. | Legal + Code (routes) |
| 11 | **No content moderation + copyrighted-cover generation.** `upload-cover` + YouTube-`import` make "faithful covers" of any audio → feed Spotify/Apple distribution, no ownership check. | Ownership-attestation gate on cover/import; basic moderation on themes/lyrics/uploads. | Legal + Code |
| 12 | **No DMCA/takedown process or abuse contact.** | Publish a takedown/abuse process + contact. | Legal |
| 13 | **No GDPR deletion/export path** (EU users; ledger append-only, no `/account/delete`). | Add `/account/delete` (Supabase admin API) + data export; cookie consent for EU. | Code + Legal |

> **Tier-3 status (2026-08-07):** the two hard-blocker CODE mechanisms (#10 acceptance gate, #11 ownership attestation) are done on branch `feat/tier3-legal` (spec `docs/superpowers/specs/2026-08-05-tier3-legal-blockers-design.md`): versioned ToS acceptance (`user_profiles.tos_accepted_version`, `POST /account/accept-terms`, `_require_terms_accepted` 403-soft-gate on the 7 paid/generation endpoints, `terms_current` on `/billing/plan`, Flutter signup checkbox + placeholder `legal_screen.dart` + in-app "I Accept" flow), and ownership attestation (`ownership_attested` required on `POST /songs`, `/songs/import`, `/songs/upload-cover` → 400 `ownership_not_attested`, recorded in run state; Flutter checkbox). Clean-env suite 852/0; `dart analyze` clean.
>
> **Operator actions to activate (Tier-3):**
> 1. Apply migration `supabase/migrations/20260805000001_tos_acceptance.sql` to live Supabase **BEFORE** the code deploys (`get_user_profile` now SELECTs `tos_accepted_version`/`_at`; the SELECT 400s if the columns are absent — same ordering as the dunning/payment_status column).
> 2. **Replace the placeholder legal copy** in `lib/screens/legal_screen.dart` with lawyer-reviewed ToS / Privacy / refund text before launch (it is clearly marked non-binding placeholder). The mechanism is legally inert until you do.
> 3. Bump `CURRENT_LEGAL_VERSION` in `pipeline/api.py` whenever the terms change — it forces every user to re-accept via the same gate/flow.
>
> **Tier-3 fast-follow (items #11 moderation, #12 DMCA, #13 GDPR) — DONE on branch `feat/tier3-fastfollow`** (spec `2026-08-07-tier3-fastfollow-design.md`): (M) `pipeline/moderation.py` deny-list — word-boundary, case-insensitive, operator-extensible via `FACELESS_MODERATION_DENYLIST` — screens user inputs on the song/video create + regenerate-lyrics endpoints (`400 content_rejected`, applies to all callers, logs a `[moderation]` count-only warning); (G) `GET /account/export` + `POST /account/delete` (typed `confirm=="DELETE"`; purge artifacts + `anonymize_user_profile` PII scrub + `auth.admin.delete_user`; **retains `credit_transactions`**; service tokens can't self-delete; NOT gated behind terms/email so GDPR rights always work) + Flutter Danger-zone (export-to-clipboard + delete-with-typed-confirm); (D) a placeholder DMCA/abuse-contact section in `legal_screen.dart`. Clean-env suite 925/0; `dart analyze` clean.
> **Operator:** extend the moderation deny-list via `FACELESS_MODERATION_DENYLIST` (a private file of terms); fill the real DMCA/abuse contact in `legal_screen.dart`; verify `auth.admin.delete_user` works with the prod service-role key.

## TIER 4 — IMPORTANT (right after launch / before scaling or marketing)

- **Email confirmation not enforced server-side** — trusts a Supabase dashboard toggle, no code backstop (`auth.py:45-111`). Add a claim check; soft-gate spend if unconfirmed.
- **No password-reset flow** (`lib/` has no `resetPasswordForEmail`). Add reset + confirmation screen.
- **Anthropic out of credits → silent Gemini fallback** (lower-quality lyrics + slow ~70s writer pass; the Anthropic→Gemini hop shows no banner). Fund Anthropic; surface `writer_tier` in `/health`.
- **No chargeback/dispute handling** (`charge.dispute.created` / `charge.refunded` unhandled) — disputed credits stay spendable.
- ~~**No Stripe Tax**~~ **CODE DONE (env-gated, OFF by default)**: `_tax_session_kwargs()` adds `automatic_tax`/`billing_address_collection`/`customer_update` to both checkout sessions when `FACELESS_STRIPE_TAX=1`. Ships inert (default off) because `automatic_tax` errors at checkout until Tax is activated. **Operator to enable:** activate Stripe Tax + add tax registrations in the Dashboard, then set `FACELESS_STRIPE_TAX=1` — or leave off + accept liability explicitly.
- **Stripe API version unpinned** — next Stripe reshape can silently break the webhook again.
- **Rate/concurrency caps are file-based and racy** across Cloud Run instances (`_rate_limit.json` on GCS-Fuse). Move to the DB.
- **LLM draft/regen endpoints unmetered/unthrottled** (`create_song`, `regenerate-lyrics`, morning-drafts) — unbounded Anthropic/Gemini spend for any user with ≥1 credit.
- **Indefinite data retention** — generated songs/videos + uploaded reference audio persist forever (only failed song runs purge at 30d). Add a TTL / GCS lifecycle rule.
- **Service token can leak into a public web build** via `run-app.sh --dart-define` — keep that launcher strictly local/dev; add a guard that refuses a non-empty token in a public build.
- **Deploy hygiene:** no CI/CD (laptop deploy silently ships without the web app if `flutter` off PATH); single region (`us-central1`); no documented rollback; `flutter analyze` failing on the UI; CORS `allow_origins=["*"]` (low risk given header auth, but stale justification).

> **Tier-4 is being tackled as 4 decomposed sub-projects: A billing → B auth → C abuse/cost → D data/ops** (specs/plans under `docs/superpowers/`).
>
> **Tier-4A (billing hardening) — DONE on branch `feat/tier4a-billing`** (spec `2026-08-07-tier4a-billing-hardening-design.md`): chargeback/dispute + refund **credit clawback** (`charge.dispute.created`/`charge.refunded` → resolve the charge to its funded grant → negative `chargeback_clawback` txn, idempotent by charge id) and **Stripe API-version pin** (`stripe.api_version="2026-04-22.dahlia"`). Clean-env suite 860/0.
> **Operator to activate:** (1) apply `supabase/migrations/20260807000001_clawback_idempotency.sql` before deploy; (2) subscribe `charge.dispute.created` + `charge.refunded` in the Stripe Dashboard webhook. Note: a clawback can drive a balance NEGATIVE if the credits were already spent — intended; the atomic deduct then blocks further spend until top-up.
> **Still deferred/pending:** Stripe Tax (operator Dashboard config + `automatic_tax` hook); Tier-4 **B** (email-confirm enforce, password reset, service-token guard), **C** (rate-limit→DB, LLM metering), **D** (retention TTL, `writer_tier` in `/health`, deploy hygiene).
>
> **Tier-4B (auth hardening) — DONE on branch `feat/tier4b-auth`** (spec `2026-08-07-tier4b-auth-hardening-design.md`). Closes the three Tier-4 auth bullets above (email confirmation, password reset, service-token leak):
> - **Email-confirmation backstop** (commit `656674b`): a code layer *atop* the Supabase project "Confirm email" toggle (which stays the primary control). `verify_supabase_jwt` sets `User.email_confirmed`, and `_require_email_confirmed` soft-gates the same 10 paid/generation endpoints as the ToS gate (403 `email_not_confirmed`; service tokens bypass). **Conservative default-allow** — only an *explicit* unconfirmed JWT signal (`email_confirmed_at` present-and-null, or `email_verified:false`) blocks; an absent claim stays confirmed, so a legit user is never locked out if the toggle is off. Surfaced on `GET /billing/plan` as `email_confirmed`.
> - **Password-reset flow** (commit `9b15a9f`, Flutter-only, no backend): login screen "Forgot password?" → `auth.resetPasswordForEmail`; `AuthChangeEvent.passwordRecovery` routes to a new `reset_password_screen.dart` → `auth.updateUser`. Supabase handles the email + recovery token.
> - **Service-token-leak build guard** (commit `4128dc9`): `build-and-push.sh` refuses to bake a non-empty token into the public web bundle (guards the compiled `BAKED_TOKEN`, empty by design; escape hatch `ALLOW_TOKEN_IN_PROD_BUILD=1`); `run-app.sh` header marks it LOCAL-DEV ONLY.
>
> Clean-env suite **875/0**; `dart analyze` clean.
> **Operator to activate (Tier-4B):** no migration, no Stripe/webhook change. Keep the Supabase project "Confirm email" toggle ON (the backstop is defense-in-depth, not a replacement) and configure the Supabase Auth password-reset redirect URL to the app deep link so recovery links return to the app.
>
> **Tier-4C (abuse & cost controls) — DONE on branch `feat/tier4c-abuse`** (spec `2026-08-07-tier4c-abuse-cost-design.md`). One DB-backed rate primitive (`rate_events` table + `db.record_rate_event`/`count_rate_events`), two uses:
> - **Daily song cap → DB** (`_enforce_daily_song_limit`): was a per-user JSON file on GCS-Fuse — **racy across the ≤4 Cloud Run instances**. Now `count_rate_events(user.id, "song_approve", 86400) >= _SONG_DAILY_LIMIT` (same 30/24h limit + message), recorded on approve and cover-regen. **Cross-instance-correct.** The old file helpers (`_load_rate_log`/`_record_song_approval`/`_rate_limit_path`) are deleted. The concurrent-runs cap stays a disk scan (not file-racy — left as-is).
> - **LLM draft/regen throttle** (`_enforce_llm_rate_limit`): the writer-pass/regen endpoints (`create_song`, `regenerate-lyrics`, `regenerate-cover-prompt`) made Anthropic/Gemini calls with **no per-user throttle** → an account with the free script-gen could spam them into unbounded LLM spend. Now soft-capped at **`FACELESS_LLM_HOURLY_LIMIT`/hour (default 30)** per user via `count_rate_events(..., "llm_call", 3600)` (429 `{"code":"llm_rate_limited"}`). The image cover-regen (Flux, not LLM) and the internal morning-draft generator are exempt. Both caps: **service tokens bypass** (no count, no record).
>
> Clean-env suite **890/0**.
> **Operator to activate (Tier-4C):** apply `supabase/migrations/20260807000002_rate_events.sql` to live Supabase **BEFORE** the code deploys (the enforcers SELECT/INSERT `rate_events` for every non-service caller; the query errors if the table is absent — same ordering as the ToS/payment_status/clawback migrations). No Stripe/webhook change. Optional: `FACELESS_LLM_HOURLY_LIMIT` env override (default 30). Retention/cleanup of old `rate_events` rows folds into Tier-4D's retention TTL.
>
> **Tier-4D (data & ops hygiene) — DONE on branch `feat/tier4d-ops`** (design+plan `docs/superpowers/plans/2026-08-07-tier4d-data-ops.md`). Three items, code the safe high-value bits + operator-script the pure infra:
> - **`writer_tier` in `/healthz`** (and the `/health` alias): the public probe now returns `writer_tier` (top *configured* LLM provider — `anthropic`/`gemini`/`groq`/`none`, mirroring `_build_llm()`'s env-key order) and `writer_degraded` (True when a runtime `llm_fallback.json` marker exists under the out-root). Makes a silent Anthropic→lower fallback (e.g. exhausted credits) observable without a paid render. No auth change (healthz stays public).
> - **CORS env-configurable** (`_cors_origins()`): the hardcoded `allow_origins=["*"]` is replaced by a helper reading `FACELESS_CORS_ORIGINS` (comma-separated; blanks/whitespace stripped). **Default stays `["*"]` — no behavior change**; an operator can lock it down to e.g. `https://faceless-lab.com,https://app.faceless-lab.com`.
> - **GCS retention** (`scripts/setup-gcs-lifecycle.sh`): the durable retention mechanism — applies a lifecycle rule deleting bucket objects older than `RETENTION_DAYS` (default 90). Idempotent (rewrites the full lifecycle). **Only touches generated artifacts in the bucket — NEVER the Supabase ledger** (financial system of record). The in-app 30-day FAILED-run cleanup stays. Operator-run: `GCS_BUCKET=<bucket> ./scripts/setup-gcs-lifecycle.sh`.
> - **`flutter analyze` / `main.dart` resolved:** `dart analyze lib/main.dart` → **No issues found**. The CLAUDE.md note about invalid Dart at `main.dart:31`/`:105` is **stale** — those lines are valid; use `dart analyze <files>` (`flutter analyze` hangs in this env).
>
> Clean-env suite **901/0**.
> **Operator to activate (Tier-4D):** no migration, no Stripe/webhook change. Run `scripts/setup-gcs-lifecycle.sh` (needs the bucket name + gcloud auth) for retention; optionally set `FACELESS_CORS_ORIGINS` to restrict origins. **Still operator-owned (pure infra, out of code scope):** a CI/CD pipeline; single-region (`us-central1`) redundancy; and a documented rollback procedure — `gcloud run services update-traffic --to-revisions=<prev-revision>=100`.
>
> **Tier-4 is COMPLETE — A (billing) + B (auth) + C (abuse/cost) + D (data/ops) all DONE.**

## TIER 5 — NICE-TO-HAVE
OAuth (Google/Apple) sign-in; `.env.example` template; finish or remove the disabled top-up packs; fix the secret-rotation doc (`latest` needs redeploy); cache headers on `main.dart.js`/canvaskit + delete the dead `inject-sw-skip-waiting.sh` reference; update stale design-doc numbers (plan credits, PLAN_GRANTS) to match code.

---

## Launch sequence

**Phase 0 — Code (money bugs). Blocks everything. → engineering (can start now)**
Fix #1 (unbilled Veo — highest priority, active loss), #2 (song cancel/failure refunds), #3 (atomic deduct), #4 (webhook idempotency + migration), #5 (dunning), #9 (green the 7 tests). Ship behind the existing shadow flags; verify with the same TDD + review flow used for the last two features.

**Phase 1 — Infra safety net. → operator (~1 day, parallel with Phase 0)**
GCP billing budget + `maxScale` + Kie spend cap (#7); Sentry + alerts (#6); Supabase backups (#8); fund Anthropic (Tier 4).

**Phase 2 — Legal/compliance. → operator + a little code**
ToS/Privacy/refund (#10), DMCA/abuse contact (#12), ownership-attestation gate + moderation (#11), GDPR delete/export (#13).

**Phase 3 — Soft launch.** Enable payments for a small invited cohort. Watch dashboards (spend, failed renders, webhook events, balances). Confirm: a real subscription grants the right credits, a real render deducts them, a cancel/failure refunds, and no balance goes negative. Then open to the public.

## Launch-day go/no-go checklist
- [ ] Tier 1 (#1–5) fixed + tested; full suite green on the money/video path.
- [ ] GCP billing budget alert + `maxScale` + Kie cap live.
- [ ] Sentry receiving events; alert on failed render / 5xx / billing anomaly.
- [ ] Supabase backups on.
- [ ] ToS + Privacy + refund published and linked; acceptance at signup/checkout.
- [ ] DMCA/abuse contact + ownership-attestation gate on cover/import.
- [ ] GDPR delete path.
- [ ] Anthropic funded; `writer_tier` reads `anthropic` in prod.
- [ ] End-to-end money test on live Stripe (subscribe → render → deduct → cancel → refund) with a real test user.
- [ ] Stripe: `invoice.payment_failed` subscribed; API version pinned; Tax decision made; receipts email on.

## Post-launch watch (first 2 weeks)
Balance-never-negative invariant; webhook delivery/idempotency; failed-render refund rate; Anthropic/Kie balances; abuse (mass renders, copyrighted covers); support volume on auth (reset/confirmation).

---

## Operator actions — Phase 0 (money-integrity fixes) — READY 2026-08-05

Phase-0 code is complete on branch `billing-money-integrity` (Tasks 1–7). The code is **inert until the operator completes these steps** — the new SQL objects/columns don't exist in the live DB and the new Stripe event isn't subscribed until you act. Do them in order.

**Commits (in order):** `77056a9` charge real user for video · `e87fca0` out-root leak · `81e53f1` song refund policy · `109ffcf` atomic deduct · `b554633` idempotent grants · `173e5d7` dunning · `755e1bb` green test path · `4b5e672` loud warning when owner-derivation falls back to admin (observability, from the final holistic review).

### 1. Apply the 3 migrations to live Supabase — BEFORE the code deploy
Task 5's `get_user_profile` SELECTs `payment_status`, which errors if the column is absent, so migrations must land first. All three are additive and safe on the running DB.
```bash
supabase db push
# — or paste each, IN ORDER, into the Supabase SQL editor:
#   supabase/migrations/20260804000001_deduct_credits_fn.sql   (deduct_credits() advisory-lock fn)
#   supabase/migrations/20260804000002_grant_idempotency.sql   (uq_credit_grant_ref partial unique index)
#   supabase/migrations/20260804000003_payment_status.sql      (user_profiles.payment_status column)
```
Verify:
```sql
select proname from pg_proc where proname = 'deduct_credits';                 -- 1 row
select indexname from pg_indexes where indexname = 'uq_credit_grant_ref';     -- 1 row
select column_name from information_schema.columns
  where table_name = 'user_profiles' and column_name = 'payment_status';      -- 1 row
```

### 2. Stripe Dashboard — subscribe the new webhook event
Developers → Webhooks → (existing endpoint) → **Add event** → `invoice.payment_failed`. Without it, dunning never fires (no `past_due` flag is ever set).

### 3. Redeploy backend + app
```bash
./scripts/build-and-push.sh
```
(Confirm `flutter` is on PATH so the web app bundle rebuilds with the past-due banner + gen-l10n keys.)

### 4. Post-deploy money test (real Stripe test-mode, one throwaway user)
1. Fresh signup → balance starts at **0** (no signup grant).
2. Subscribe (Stripe test card) → credits granted **once**; re-send the webhook from the dashboard → balance does NOT double (idempotency).
3. Render a video → balance **decrements** (real user charged, not `admin`).
4. Cancel a song mid-run → charge **refunded** (self-service).
5. Fail a render then `/resume` → **not** re-charged, **not** auto-refunded (resume = free retry; failure keeps the charge).
6. Force a failed renewal (Stripe test card) → app shows the **past-due banner**; a later successful payment clears it.
7. Throughout: **no balance ever goes negative** (atomic deduction).

### Verification captured at handoff (Task 7, 2026-08-05)
- Full suite in a clean env (`env -u <all API-key vars> uv run pytest -q`): **821 passed, 0 failed** (819 after Task 6 + 2 observability tests from `4b5e672`). The pre-Phase-0 baseline of 7 failures is fully greened; none were assertion-weakened (max-spend now derives from the active model rate; faststart exercises a realistic >50 KB clip with the corruption guard intact; shorts-smoke mocks the ElevenLabs boundary per the "mock all external services" invariant).
- Offline smoke: service-bypass `check_or_deduct` returns the sentinel and `refund_run_charges`/`deduct_credits_atomic`/`record_grant_once` import cleanly — no traceback.
- NOTE for future test runs: **run pytest in a clean env** — sourcing `.env` flips the failing set (see `reference_test_suite_verification` memory). **`flutter analyze` hangs in this env; use `dart analyze <files>`.**

### What is NOT in Phase 0 (still required before charging real users — Tiers 2–3 above)
Monitoring/alerting, infra spend ceiling (`maxScale` + GCP budget + Kie cap), Supabase backups, ToS/Privacy/refund policy, DMCA/abuse contact, ownership-attestation gate, GDPR delete/export. Phase 0 closes only the **money-integrity code** blockers (Tier 1). ~~Also deferred: the video pipeline shares the same free-resume leak fixed for songs in Task 2~~ — **FIXED 2026-08-05 (commit `c27c6c0`)**: the shorts/video assembly-failure auto-refund was removed (failure keeps the charge; `/resume` = free retry; `cancel_run` = refund path, re-ordered to refund after reaping the worker). So both the song and video pipelines now follow the same cancel-refunds/failure-keeps-charge policy.
