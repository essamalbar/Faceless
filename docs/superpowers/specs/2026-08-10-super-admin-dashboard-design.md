# Super-Admin Dashboard — Design

**Date:** 2026-08-10
**Status:** approved (brainstorm; decisions locked with the user 2026-08-10) — spec for the implementation plan.
**Scope:** A single super-admin cockpit to **track** (users, credit balances/ledger, runs across all users, system health, migration-activation status) and **manage** (grant/adjust credits, cancel+refund a run/song, delete a run/song, recover a broken song) — served by the existing FastAPI backend. Plus an operator convenience: a paste-ready bundle of the 6 pending Supabase migrations.

## Locked decisions (from the brainstorm)
- **Delivery vehicle:** a self-contained HTML page served by the API at `GET /admin` (inline CSS/JS, no external deps → works behind the Cloudflare tunnel + any CSP). *Not* a Flutter screen — the service token is all-powerful (it also HMAC-signs share tokens, `api.py:4893`) and must not live in the consumer app; Flutter tooling here is painful; prod is currently down so a Flutter screen couldn't be exercised anyway.
- **Management scope:** grant/adjust credits, cancel+refund run/song, delete run/song, recover (re-assemble) song. (User: "everything for management should be in dashboard.")
- **No new DB migrations.** Six are already unapplied and are the operator's bottleneck; this feature adds zero. Moderation has no table (log-lines only) → the dashboard shows it as "log-based, not queryable" rather than inventing a table.

## Context (verified 2026-08-10)
- **Admin identity** = whoever holds `FACELESS_API_TOKEN`. `require_user` (`auth.py:134`) returns `User(id="admin", role="service")` for that bearer; every other valid token is a Supabase JWT → `role="user"`. Admin gating everywhere is a runtime `if user.role != "service": raise HTTPException(403, …)` (`api.py:1058, 2481, 2543`). No admin-user model, no allowlist.
- **Existing `/admin/*`:** `POST /admin/run-morning-drafts` (out-root sweep), `POST /admin/credit-back` (positive `admin_credit` txn for any `user_id`), `POST /admin/re-assemble-song/{user_id}/{run_id}`. The latter two are the only cross-user reach points.
- **Storage:** runs live at `_out_root()/<user_id>/<run_id>/` (`api.py:764,768`). Status is derived from artifacts by `derive_status()` (`api.py:336`); per-run summary is `_summarize()` (`api.py:1640`). `list_runs` (`api.py:1286`) is caller-scoped only — no cross-user listing exists.
- **DB (`pipeline/db.py`)** is all get-by-id: `get_user_profile`, `get_balance` (reads the `user_balance` view), `list_transactions(user_id, limit)`, `record_transaction`. No list-all-users / cross-user ledger. Service-role client `_client()`; `SUPABASE_URL`+`SUPABASE_SERVICE_ROLE_KEY` required or it raises.
- **Refund** = `credits.refund_run_charges(user, run_id, reason)` (`credits.py:93`): net-safe, computes net charges for `(user.id, run_id)`, inserts a single positive txn; **no-ops for service tokens** (`:113`). So an admin cancel must pass a synthetic **target** `User(role="user")`, not the admin's own service user, or the refund silently no-ops.
- **Cancel/delete internals:** `cancel_run` (`api.py:2770`, complete-guard + kill + re-check + refund), `delete_run` (`api.py:2675`, stop worker + `rmtree`), `cancel_song` (`api.py:3810`, complete-guard + SIGTERM + refund), `delete_song` (`api.py:4423`). All caller-scoped via `_run_dir`/`_resolve_song_dir`.
- **Traversal:** `_run_dir(run_id, user)` (`api.py:788`) validates `run_id` against `_RUN_ID_RE = ^[A-Za-z0-9_\-]+$` and scopes to the user root. **`admin_re_assemble_song` builds `_out_root()/user_id/run_id` with NO validation of `user_id`** (`api.py:2548`) — a latent traversal gap to fix.
- **HTML serving already exists:** public artist/share pages via `HTMLResponse`; the Flutter SPA is mounted at `/app` (`api.py:6767`); `GET /` redirects there. Adding an `/admin` HTML route fits cleanly.
- **Health:** `GET /health` → `{ok, writer_tier, writer_degraded}` (`api.py:1275`, `_writer_tier_status` `api.py:856`).
- **CORS** defaults `["*"]`, `allow_credentials=False` (`api.py:754`). The admin page is same-origin, so CORS is irrelevant to it.

## Architecture

### Auth model for the dashboard
- Every `/admin/*` **data and write** endpoint is gated `user.role != "service" → 403`, identical to the three existing ones. So the only credential that works is the raw `FACELESS_API_TOKEN`.
- The **HTML shell** at `GET /admin` is itself harmless — it contains **no data and no embedded token**; it's a static page with a token field + JS. Serving the shell unauthenticated matches the other HTMLResponse pages. All data arrives via the gated JSON endpoints.
- The page holds the token in **`sessionStorage`** (cleared when the tab closes) and sends it as `Authorization: Bearer …` on every fetch. **Never** `?token=` — this token unlocks everything and would leak into request logs. Same-origin fetch, so no CORS concern.

### New `db.py` helpers (read/aggregation; service-role client; mocked in tests)
- `list_user_profiles(limit: int = 100, offset: int = 0) -> list[UserProfile]` — `select(...) .order("id") .range(offset, offset+limit-1)` on `user_profiles`.
- `list_balances() -> dict[str, int]` — one select on the `user_balance` view → `{user_id: balance}` (avoids N per-user round-trips).
- `list_auth_users() -> dict[str, str]` — `_client().auth.admin.list_users()` → `{id: email}` (emails live in auth, not `user_profiles`). Best-effort; returns `{}` on failure so the dashboard degrades to "no email" rather than 500.
- `list_transactions_all(limit: int = 200) -> list[Transaction]` — cross-user ledger, `order("created_at", desc=True).limit(limit)`.
- `probe_activation() -> dict[str, bool | None]` — best-effort check of the API-observable migration objects: `payment_status` + `tos_accepted_version` columns (one `select` on `user_profiles`) and the `rate_events` table (one `select`). Each key is `True` (present), `False` (a PostgREST "missing column/relation" error), or `None` (indeterminate — some other error). The three non-observable objects (the `deduct_credits` fn + the two partial-unique indexes) are reported by the endpoint as `"verify_in_sql_editor"`, never probed (calling the rpc with dummy args could mutate the ledger).

### New backend endpoints (all in `pipeline/api.py`, all service-gated)

**Read:**
- `GET /admin/overview` → `{health: {...}, counts: {users, runs}, activation: {payment_status, tos_accepted_version, rate_events, unprobed: [...]}}`. Wraps `_writer_tier_status()`, counts user dirs under `_out_root()` and rows via `list_user_profiles`, and `db.probe_activation()`. Never 500 on a DB outage — catch and return `activation: {"error": "..."}` so the page still renders health.
- `GET /admin/users?limit=&offset=` → per user: `{id, email, balance, plan, payment_status, tos_accepted_version}`, merging `list_user_profiles` + `list_balances` + `list_auth_users`. `limit` clamped to `[1, 200]`.
- `GET /admin/runs?limit=&offset=&user_id=` → walks `_out_root()` (reusing the `run_morning_drafts` iteration pattern), summarizing each run via `_summarize` + tagging its owner `user_id` and `kind` (from state). **Capped**: at most `limit` runs returned (default 50, max 200), newest-first; the walk stops once `offset+limit` runs are collected so prod's GCS-Fuse root is never fully traversed. Optional `user_id` filter restricts to one user's dir.
- `GET /admin/transactions?limit=&user_id=` → cross-user ledger via `list_transactions_all`, or `list_transactions(user_id)` when `user_id` is given. `limit` clamped `[1, 500]`.

**Manage (write):**
- `POST /admin/credit-back` — **reused unchanged**.
- `POST /admin/re-assemble-song/{user_id}/{run_id}` — **reused unchanged** (but its `user_id` traversal gap is fixed, see below).
- `POST /admin/runs/{user_id}/{run_id}/cancel` — cross-user cancel+refund for a **video** run. Builds `target = User(id=user_id, email=None, role="user")` and delegates to a shared `_cancel_run_impl(target, run_id)` (extracted from `cancel_run`). The refund lands on the target user's ledger (synthetic role="user" → refund is NOT a no-op).
- `POST /admin/songs/{user_id}/{run_id}/cancel` — same, delegating to `_cancel_song_impl(target, run_id)`.
- `DELETE /admin/runs/{user_id}/{run_id}` — cross-user delete of a **video** run; delegates to `_delete_run_impl(target, run_id)` (extracted from `delete_run`). Ledger retained (delete never touches `credit_transactions`).
- `DELETE /admin/songs/{user_id}/{run_id}` — cross-user delete of a **song**; delegates to `_delete_song_impl(target, run_id)`.

### Refactor: extract-and-reuse (no behavior change to existing routes)
`cancel_run`, `cancel_song`, `delete_run`, `delete_song` each get their body moved into a module-level `_*_impl(user: User, run_id: str)` helper. The existing routes become thin wrappers calling the impl with the authenticated caller — so existing user-facing behavior and tests are unchanged — and the admin routes call the same impl with the synthetic target user. This keeps the complete-guard, kill-then-refund ordering, and traversal validation in exactly one place per action.

### Traversal safety
A new `_admin_target_user(user_id: str) -> User` helper validates `user_id` against `_RUN_ID_RE` (blocks `..`, `/`, NUL, etc.) and returns `User(id=user_id, email=None, role="user")`, raising `HTTPException(400, "invalid user_id")` otherwise. Every new admin `{user_id}` route uses it, and **`admin_re_assemble_song` is updated to validate `user_id` the same way** (closing the existing gap). `run_id` continues to be validated by the reused `_run_dir`/`_resolve_song_dir` (which the impls call).

### The dashboard page (`GET /admin`)
- Served by a new route returning `HTMLResponse` with a module-level HTML string kept in a new file **`pipeline/admin_page.py`** (`ADMIN_HTML: str`) so `api.py` stays readable. `api.py` imports it and returns `HTMLResponse(ADMIN_HTML)`.
- Self-contained: inline `<style>` + `<script>`, no external fetches, so it renders under a strict CSP and offline of any CDN. Light theme consistent with the app's look (pastel bg, white cards, dark text, green/charcoal accents — matches the existing light-theme redesign), responsive, and horizontal-scrolls wide tables inside their own container.
- **Sections:** (1) token bar + **Activation & health** card (writer tier, degraded flag, migration probe N/observable, prod note); (2) **Users** table (id, email, balance, plan, payment_status, ToS) with a per-row **Grant credits** action (amount + reason → `POST /admin/credit-back`); (3) **Runs** feed (owner, id, kind, status, created) with per-row **Cancel**, **Delete**, and **Re-assemble** (songs) actions, filterable by `user_id`; (4) **Ledger** table (cross-user or filtered) showing signed amounts. Destructive actions (cancel/delete) require a JS `confirm()`.

### Operator convenience: migrations bundle (docs only, no code)
- `docs/operator/APPLY-MIGRATIONS.sql` — the 6 pending migrations concatenated **in filename order** (`20260804000001` → `20260807000002`), each preceded by a `-- ===== <filename> =====` banner. Verified additive/idempotent-safe to run as one transaction-less paste (they are `ADD COLUMN`/`CREATE INDEX`/`CREATE TABLE`/`CREATE FUNCTION`, additive). A leading comment states it's generated — edit the source migrations, not this file.
- `docs/operator/APPLY-MIGRATIONS.md` — the exact Supabase SQL-editor click-path (Dashboard → SQL Editor → New query → paste → Run), a note that it must be applied **before** the next code deploy, and how to confirm via the dashboard's activation card.

## Testing (repo invariant: external services mocked; clean-env suite)
- **`tests/test_db.py`** (extend): `list_user_profiles`, `list_balances`, `list_transactions_all`, `list_auth_users`, `probe_activation` — each with a monkeypatched `_client()` returning canned resp objects (present-column vs missing-column error for the probe).
- **`tests/test_api.py`/`test_admin_dashboard.py`** (new): for every new endpoint — `403` for a normal user (JWT), `200` + shape for a service token; `/admin/runs` respects `limit`/`offset` and the cap; `/admin/runs/{uid}/{rid}/cancel` refunds the **target** user (assert a positive txn recorded for `uid`, not `"admin"`); `DELETE /admin/runs/{uid}/{rid}` rmtrees the target dir and records **no** `credit_transactions` delete; a `user_id="../foo"` → `400`; `admin_re_assemble_song` with a bad `user_id` → `400`. `GET /admin` → `200 text/html` containing a known marker string, no auth required.
- **Env-absent parity:** with Supabase env unset, the new data endpoints behave like the existing DB-backed ones (the `_client()` RuntimeError surfaces the same way `/billing/*` does today) — assert they don't crash the app import and that tests mock `db.*` directly rather than needing live creds.
- **Refactor safety:** existing `cancel_run`/`cancel_song`/`delete_run`/`delete_song` tests must stay green unchanged (proves the extract-and-reuse preserved behavior).
- **Baseline:** clean-env suite **929 passed, 0 failed** (2026-08-10). No regressions; new tests add to the count.

## Deploy / operator
- **No migration** for this feature. After deploy, open `https://<api-host>/admin`, paste `FACELESS_API_TOKEN`. Optionally lock `FACELESS_CORS_ORIGINS` (irrelevant to the same-origin admin page but good hygiene).
- The dashboard is **not** a go-live gate — after it ships, the standing blockers remain: GCP billing closed (prod down), the 6 migrations unapplied, Stripe webhook events, Kie cap, placeholder legal copy. The migrations bundle removes friction from the first of those.

## Key invariants
- Admin power = the service token; all `/admin/*` data+write endpoints gate `role != "service" → 403`. The token never enters a URL/log; the HTML shell embeds no token and no data.
- Cross-user refund uses a synthetic **target** `User(role="user")` so `refund_run_charges` actually credits the user (service-user would no-op).
- Cross-user deletes retain `credit_transactions` (financial system of record).
- All `{user_id}` path params validated against `_RUN_ID_RE` (traversal); `admin_re_assemble_song`'s pre-existing gap is closed as part of this work.
- Extract-and-reuse must not change existing route behavior. New Python files start with `from __future__ import annotations`; imports absolute from `pipeline.`.
