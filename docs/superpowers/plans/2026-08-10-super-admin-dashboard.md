# Super-Admin Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (synchronous subagents — background ones get lost across idle gaps). Two-stage review per task (spec-compliance then code-quality). Design: `docs/superpowers/specs/2026-08-10-super-admin-dashboard-design.md`.

**Goal:** A service-token-gated super-admin web dashboard (served by the FastAPI backend) to track users/runs/ledger/health and manage credits, cancels+refunds, deletes, and song recovery — plus new cross-user read/aggregation endpoints and db helpers to power it.

**Architecture:** New `db.py` aggregation helpers (service-role client). Extract the bodies of `cancel_run`/`cancel_song`/`delete_run`/`delete_song` into reusable `_*_impl(user, run_id)` helpers so admin cross-user variants reuse them with a synthetic **target** `User(role="user")` (so `refund_run_charges` credits the real user, not the no-op service user). New `/admin/*` read + write endpoints, all gated `role != "service" → 403`. A self-contained HTML page at `GET /admin` (inline CSS/JS) served from a new `pipeline/admin_page.py`.

**Tech stack:** FastAPI, supabase-py (mocked in tests), pytest. Python files start with `from __future__ import annotations`; absolute imports from `pipeline.`.

**Verification env (clean-env; baseline 929 passed, 0 failed on 2026-08-10):**
```
env -u ANTHROPIC_API_KEY -u GROQ_API_KEY -u FACELESS_API_TOKEN -u KIE_API_KEY \
    -u ELEVENLABS_API_KEY -u SUPABASE_URL -u SUPABASE_SERVICE_ROLE_KEY \
    -u STRIPE_SECRET_KEY -u STRIPE_WEBHOOK_SECRET uv run pytest -q
```

**Already done (not tasks):** `docs/operator/APPLY-MIGRATIONS.sql` + `.md` (the 6-migration paste bundle).

---

## File structure
- **Modify** `pipeline/db.py` — add `list_user_profiles`, `list_balances`, `list_auth_users`, `list_transactions_all`, `probe_activation`.
- **Modify** `pipeline/api.py` — extract `_cancel_run_impl`/`_cancel_song_impl`/`_delete_run_impl`/`_delete_song_impl`; add `_admin_target_user`; fix `admin_re_assemble_song` traversal; add read endpoints (`/admin/overview`, `/admin/users`, `/admin/runs`, `/admin/transactions`) and write endpoints (`/admin/runs/{uid}/{rid}/cancel`, `/admin/songs/{uid}/{rid}/cancel`, `DELETE /admin/runs/{uid}/{rid}`, `DELETE /admin/songs/{uid}/{rid}`); add `GET /admin` HTML route.
- **Create** `pipeline/admin_page.py` — `ADMIN_HTML: str`.
- **Modify/Create tests** `tests/test_db.py`, `tests/test_admin_dashboard.py`.

---

## Task 1: db.py aggregation helpers — TDD

**Files:** Modify `pipeline/db.py`; Test `tests/test_db.py`.

- [ ] **Step 1 — failing tests.** In `tests/test_db.py`, monkeypatch `pipeline.db._client` to return a fake client whose `.table(...).select(...).order(...).range(...).execute()` / `.limit(...).execute()` chain returns an object with `.data`. Test:
  - `list_user_profiles(limit=2, offset=0)` returns `list[UserProfile]` built from canned rows (id, current_plan, payment_status, tos_accepted_version).
  - `list_balances()` returns `{user_id: balance}` from canned `user_balance` rows.
  - `list_transactions_all(limit=3)` returns newest-first `list[Transaction]`.
  - `list_auth_users()` maps `{id: email}` from a fake `_client().auth.admin.list_users()`; returns `{}` when that call raises.
  - `probe_activation()`: with a fake `_client()` where selecting `payment_status,tos_accepted_version` succeeds and `rate_events` select succeeds → `{"payment_status": True, "tos_accepted_version": True, "rate_events": True}`; when the `rate_events` select raises an exception whose text contains `relation "rate_events" does not exist` / `PGRST205` → that key is `False`; an unrelated error → `None`.

- [ ] **Step 2 — run, verify fail.** `... uv run pytest tests/test_db.py -q` → new tests fail (functions undefined).

- [ ] **Step 3 — implement** in `pipeline/db.py`:
```python
def list_user_profiles(limit: int = 100, offset: int = 0) -> list[UserProfile]:
    resp = (
        _client()
        .table("user_profiles")
        .select(
            "id,stripe_customer_id,current_plan,current_period_end,"
            "cancel_at_period_end,payment_status,tos_accepted_version,tos_accepted_at",
        )
        .order("id")
        .range(offset, offset + max(limit, 1) - 1)
        .execute()
    )
    out: list[UserProfile] = []
    for d in (resp.data or []):
        out.append(UserProfile(
            id=d["id"],
            stripe_customer_id=d.get("stripe_customer_id"),
            current_plan=d.get("current_plan", "free"),
            current_period_end=d.get("current_period_end"),
            cancel_at_period_end=bool(d.get("cancel_at_period_end", False)),
            payment_status=d.get("payment_status", "active"),
            tos_accepted_version=d.get("tos_accepted_version"),
            tos_accepted_at=d.get("tos_accepted_at"),
        ))
    return out


def list_balances() -> dict[str, int]:
    resp = _client().table("user_balance").select("user_id,balance").execute()
    return {r["user_id"]: int(r.get("balance", 0)) for r in (resp.data or [])}


def list_auth_users() -> dict[str, str]:
    """{user_id: email} from the Supabase auth admin API. Best-effort — returns
    {} on any failure so the dashboard degrades to 'no email' rather than 500."""
    try:
        res = _client().auth.admin.list_users()
    except Exception:
        return {}
    users = getattr(res, "users", None)
    if users is None:
        users = res if isinstance(res, list) else []
    out: dict[str, str] = {}
    for u in users:
        uid = getattr(u, "id", None) or (u.get("id") if isinstance(u, dict) else None)
        email = getattr(u, "email", None) or (u.get("email") if isinstance(u, dict) else None)
        if uid and email:
            out[str(uid)] = str(email)
    return out


def list_transactions_all(limit: int = 200) -> list[Transaction]:
    resp = (
        _client()
        .table("credit_transactions")
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return [
        Transaction(
            id=r["id"], user_id=r["user_id"], amount=r["amount"], kind=r["kind"],
            reference_id=r.get("reference_id"), description=r.get("description"),
            created_at=r["created_at"],
        )
        for r in (resp.data or [])
    ]


def _probe_ok(fn) -> bool | None:
    """True if the probe select succeeds; False if it fails with a missing
    column/relation signal; None for any other error (indeterminate)."""
    try:
        fn()
        return True
    except Exception as e:
        s = str(e).lower()
        missing = ("does not exist" in s or "could not find" in s
                   or "pgrst204" in s or "pgrst205" in s or "42703" in s or "42p01" in s)
        return False if missing else None


def probe_activation() -> dict[str, bool | None]:
    """Best-effort check of the API-observable migration objects. The
    deduct_credits fn + the two partial-unique indexes are NOT probed here
    (not observable via PostgREST; calling the rpc could mutate the ledger) —
    the endpoint reports those as 'verify_in_sql_editor'."""
    def _cols():
        _client().table("user_profiles").select(
            "payment_status,tos_accepted_version").limit(1).execute()
    def _rate():
        _client().table("rate_events").select("id").limit(1).execute()
    cols = _probe_ok(_cols)
    return {
        "payment_status": cols,
        "tos_accepted_version": cols,
        "rate_events": _probe_ok(_rate),
    }
```

- [ ] **Step 4 — verify pass.** `... uv run pytest tests/test_db.py -q` → pass.

- [ ] **Step 5 — commit.** `git add pipeline/db.py tests/test_db.py && git commit -m "feat(admin): cross-user db aggregation helpers + migration-activation probe"`

---

## Task 2: extract cancel/delete into reusable impls (no behavior change) — TDD

**Files:** Modify `pipeline/api.py`; Test `tests/test_admin_dashboard.py` (new) + existing cancel/delete tests must stay green.

**Read first:** `cancel_run` (`api.py:2770`), `delete_run` (`api.py:2675`), `cancel_song` (`api.py:3810`), `delete_song` (search `def delete_song`). Note each uses `_run_dir(run_id, user)` / `_resolve_song_dir(run_id, user)` and (for cancel) `refund_run_charges(user, …)`.

- [ ] **Step 1 — failing test.** In `tests/test_admin_dashboard.py`, add a test that imports the impl helpers and asserts they exist and are callable with `(user, run_id)`:
  `from pipeline.api import _cancel_run_impl, _cancel_song_impl, _delete_run_impl, _delete_song_impl` — plus a behavior test that calling `_cancel_run_impl(user, run_id)` on a tmp run dir (monkeypatch `_out_root`, write a minimal `api_state.json`, no live pid) returns a `CancelAck` and records the refund via a monkeypatched `refund_run_charges`. (Reuse the existing cancel/delete test fixtures as a template — find them with `grep -n "def test_cancel_run\|def test_delete_run\|def test_cancel_song" tests/`.)

- [ ] **Step 2 — run, verify fail** (ImportError).

- [ ] **Step 3 — refactor.** Move each route body into a module-level function, leaving the route as a thin wrapper. Pattern (do the same for all four):
```python
def _cancel_run_impl(user: "User", run_id: str) -> "CancelAck":
    # ... the exact current body of cancel_run, unchanged ...

@app.post("/runs/{run_id}/cancel", response_model=CancelAck,
          dependencies=[Depends(require_user)])
def cancel_run(run_id: str, user: User = Depends(require_user)):
    return _cancel_run_impl(user, run_id)
```
  - `_cancel_run_impl(user, run_id) -> CancelAck` (from `cancel_run`).
  - `_delete_run_impl(user, run_id) -> DeleteAck` (from `delete_run`).
  - `_cancel_song_impl(user, run_id) -> dict` (from `cancel_song`; keep the `{"ok": True, "refunded": …}` return).
  - `_delete_song_impl(user, run_id) -> <existing return type>` (from `delete_song`).
  Keep every guard, the kill-then-refund ordering, and the `get_logger().error("[billing] …")` telemetry EXACTLY as-is. The only change is where the code lives.

- [ ] **Step 4 — verify.** Run the new import/behavior test AND the existing cancel/delete tests: `... uv run pytest tests/test_admin_dashboard.py tests/ -q -k "cancel or delete"` → all green (proves no behavior change).

- [ ] **Step 5 — commit.** `git add pipeline/api.py tests/test_admin_dashboard.py && git commit -m "refactor(api): extract cancel/delete run+song into reusable _*_impl helpers"`

---

## Task 3: admin read endpoints + target-user helper + traversal fix — TDD

**Files:** Modify `pipeline/api.py`; Test `tests/test_admin_dashboard.py`.

- [ ] **Step 1 — failing tests.** Using the app's TestClient pattern already in `tests/test_api.py` (find how it sets a service token: `grep -n "FACELESS_API_TOKEN\|role=\"service\"\|def client" tests/test_api.py`), add tests:
  - `GET /admin/overview` with a **normal user** token → 403; with the **service** token → 200 with keys `health`, `counts`, `activation` (monkeypatch `db.probe_activation` + `db.list_user_profiles`).
  - `GET /admin/users` service → 200 list merging profile+balance+email (monkeypatch the three db helpers); normal user → 403; `limit` clamped.
  - `GET /admin/runs` service → 200; create two tmp user dirs each with a run dir (monkeypatch `_out_root`); assert both users' runs appear, each tagged with its `user_id`; `limit=1` returns exactly 1; `user_id=` filter restricts to one user.
  - `GET /admin/transactions` service → 200 (monkeypatch `db.list_transactions_all`); `user_id=` path uses `db.list_transactions`.
  - `_admin_target_user("../etc")` raises `HTTPException(400)`; `_admin_target_user("abc-123")` returns `User(id="abc-123", role="user")`.
  - `admin_re_assemble_song` with `user_id="../x"` → 400 (traversal fix).

- [ ] **Step 2 — run, verify fail.**

- [ ] **Step 3 — implement** in `pipeline/api.py`:
```python
def _admin_target_user(user_id: str) -> "User":
    """Validate a cross-user path param against traversal and wrap it as a
    role='user' target so refund logic credits the real user (a service user
    would no-op). Same allowlist as _run_dir's run_id check."""
    if not _RUN_ID_RE.fullmatch(user_id):
        raise HTTPException(400, "invalid user_id")
    return User(id=user_id, email=None, role="user")
```
  - Add `if not _RUN_ID_RE.fullmatch(user_id): raise HTTPException(400, "invalid user_id")` at the top of `admin_re_assemble_song` (before building `run_dir`).
  - `GET /admin/overview` (service-gated): `health = _writer_tier_status()`; count user dirs under `_out_root()`; `activation`: `try: {**db.probe_activation(), "unprobed": ["deduct_credits_fn","uq_credit_grant_ref","uq_credit_clawback_ref"]}` / `except Exception as e: {"error": str(e)}`. Return `{"health": health, "counts": {...}, "activation": ...}`.
  - `GET /admin/users?limit=&offset=` (service-gated): clamp `limit` to `[1,200]`, `offset>=0`; `profiles=db.list_user_profiles(limit,offset)`; `balances=db.list_balances()`; `emails=db.list_auth_users()`; return per-profile dicts merging them (`balance=balances.get(p.id,0)`, `email=emails.get(p.id)`).
  - `GET /admin/runs?limit=&offset=&user_id=` (service-gated): clamp `limit` to `[1,200]` (default 50). Iterate `sorted(_out_root().iterdir())` user dirs (skip non-dirs; if `user_id` given, only that one). For each, iterate its run dirs; build `(created_at, user_id, summary)` tuples. **Cap the walk**: stop collecting once you have `offset+limit` items after sorting per-user newest-first — do NOT summarize every run in prod. Simple safe approach: collect lightweight `(mtime, uid, run_dir)` first, sort desc by mtime, slice `[offset:offset+limit]`, THEN call `_summarize` only on the slice. Return `[{**summary.dict(), "user_id": uid, "kind": <state kind>}]`.
  - `GET /admin/transactions?limit=&user_id=` (service-gated): clamp `limit` to `[1,500]` (default 200). `user_id` given → `db.list_transactions(user_id, limit)`, else `db.list_transactions_all(limit)`. Return list of dicts.
  All four start with `if user.role != "service": raise HTTPException(403, "admin endpoint — service token required")`.

- [ ] **Step 4 — verify pass.** `... uv run pytest tests/test_admin_dashboard.py -q`.

- [ ] **Step 5 — commit.** `git add pipeline/api.py tests/test_admin_dashboard.py && git commit -m "feat(admin): cross-user read endpoints (overview/users/runs/transactions) + traversal-safe target-user helper"`

---

## Task 4: admin write endpoints (cross-user cancel/delete) — TDD

**Files:** Modify `pipeline/api.py`; Test `tests/test_admin_dashboard.py`. Depends on Tasks 2 + 3.

- [ ] **Step 1 — failing tests.**
  - `POST /admin/runs/{uid}/{rid}/cancel`: normal user → 403; service → 200; monkeypatch `refund_run_charges` and assert it was called with a `User` whose `.id == uid` and `.role == "user"` (NOT `"admin"`/service) — this is the load-bearing correctness check.
  - `POST /admin/songs/{uid}/{rid}/cancel`: same target-user assertion.
  - `DELETE /admin/runs/{uid}/{rid}`: service → deletes the target user's run dir (tmp `_out_root`), asserts the dir is gone; normal user → 403; monkeypatch/spy that no `credit_transactions` delete happens (ledger retained).
  - `DELETE /admin/songs/{uid}/{rid}`: same.
  - `uid="../evil"` on each → 400.

- [ ] **Step 2 — run, verify fail.**

- [ ] **Step 3 — implement** (service-gated; each builds the target then delegates):
```python
@app.post("/admin/runs/{user_id}/{run_id}/cancel", response_model=CancelAck,
          dependencies=[Depends(require_user)])
def admin_cancel_run(user_id: str, run_id: str, user: User = Depends(require_user)):
    if user.role != "service":
        raise HTTPException(403, "admin endpoint — service token required")
    return _cancel_run_impl(_admin_target_user(user_id), run_id)

@app.post("/admin/songs/{user_id}/{run_id}/cancel",
          dependencies=[Depends(require_user)])
def admin_cancel_song(user_id: str, run_id: str, user: User = Depends(require_user)):
    if user.role != "service":
        raise HTTPException(403, "admin endpoint — service token required")
    return _cancel_song_impl(_admin_target_user(user_id), run_id)

@app.delete("/admin/runs/{user_id}/{run_id}", response_model=DeleteAck,
            dependencies=[Depends(require_user)])
def admin_delete_run(user_id: str, run_id: str, user: User = Depends(require_user)):
    if user.role != "service":
        raise HTTPException(403, "admin endpoint — service token required")
    return _delete_run_impl(_admin_target_user(user_id), run_id)

@app.delete("/admin/songs/{user_id}/{run_id}",
            dependencies=[Depends(require_user)])
def admin_delete_song(user_id: str, run_id: str, user: User = Depends(require_user)):
    if user.role != "service":
        raise HTTPException(403, "admin endpoint — service token required")
    return _delete_song_impl(_admin_target_user(user_id), run_id)
```

- [ ] **Step 4 — verify pass.** `... uv run pytest tests/test_admin_dashboard.py -q`.

- [ ] **Step 5 — commit.** `git add pipeline/api.py tests/test_admin_dashboard.py && git commit -m "feat(admin): cross-user cancel/delete run+song (refund credits the target user)"`

---

## Task 5: the /admin dashboard page — TDD

**Files:** Create `pipeline/admin_page.py`; Modify `pipeline/api.py`; Test `tests/test_admin_dashboard.py`.

- [ ] **Step 1 — failing test.** `GET /admin` → 200, `content-type` starts `text/html`, body contains the markers `Super Admin`, `sessionStorage`, `/admin/overview`, `/admin/users`, `/admin/runs`, `/admin/transactions`. No auth required for the shell.

- [ ] **Step 2 — run, verify fail** (404).

- [ ] **Step 3 — implement.**
  - Create `pipeline/admin_page.py` starting with `from __future__ import annotations` and a module-level `ADMIN_HTML: str = """…"""`. Requirements for the HTML (self-contained, inline `<style>`+`<script>`, NO external requests):
    - **Token bar:** an input for the service token + Save button → `sessionStorage.setItem('faceless_admin_token', …)`; all fetches send `Authorization: Bearer <token>`; a Clear button. On load, prefill from sessionStorage. Show a red "no token set" hint when empty.
    - **Activation & health card:** calls `GET /admin/overview`; renders `writer_tier`, `writer_degraded`, user/run counts, and the activation probe (payment_status / tos_accepted_version / rate_events as ✓/✗/?, plus the `unprobed` list as "verify in SQL editor"). If `activation.error`, show it without breaking the rest.
    - **Users table:** `GET /admin/users` → columns id, email, balance, plan, payment_status, ToS. Each row has a **Grant** control (number + reason → `POST /admin/credit-back` with `{user_id,amount,reason}`) that refreshes the row's balance on success.
    - **Runs feed:** `GET /admin/runs` (with an optional user_id filter box) → columns owner(user_id), id, kind, status, created. Per-row buttons: **Cancel** (`POST /admin/runs|songs/{uid}/{rid}/cancel` by kind), **Delete** (`DELETE /admin/runs|songs/{uid}/{rid}` by kind), and **Re-assemble** (songs only → `POST /admin/re-assemble-song/{uid}/{rid}`). Destructive buttons call `confirm()` first; show the JSON result / error inline.
    - **Ledger table:** `GET /admin/transactions` (optional user_id filter) → created, user_id, kind, amount (signed, red/green), description.
    - **Styling:** light theme (pastel background, white cards, dark text, green + charcoal accents — consistent with the app), responsive, wide tables wrapped in `overflow-x:auto`. A single `apiGet/apiSend` helper that injects the bearer header and surfaces non-2xx bodies. Fail visibly (never silently) on 401/403.
  - In `pipeline/api.py`, near the other HTMLResponse routes (before the SPA mount at the bottom is fine), add:
```python
@app.get("/admin", include_in_schema=False)
def admin_dashboard():
    from pipeline.admin_page import ADMIN_HTML
    return HTMLResponse(ADMIN_HTML)
```
  (Confirm `HTMLResponse` is already imported — it is, used by artist/share pages.)

- [ ] **Step 4 — verify pass.** `... uv run pytest tests/test_admin_dashboard.py -q`.

- [ ] **Step 5 — commit.** `git add pipeline/admin_page.py pipeline/api.py tests/test_admin_dashboard.py && git commit -m "feat(admin): self-contained super-admin dashboard page at GET /admin"`

---

## Task 6: verify + docs

- [ ] **Step 1 — full clean-env suite.** Run the full command above → **0 failed**; report the new passed count (should be 929 + the new tests).
- [ ] **Step 2 — GO-LIVE note.** Append a short "Super-admin dashboard" subsection to `docs/GO-LIVE-READINESS.md`: what shipped (dashboard at `/admin`, cross-user admin endpoints, migration bundle at `docs/operator/APPLY-MIGRATIONS.{sql,md}`), how to open it (paste `FACELESS_API_TOKEN`), and that it is NOT a go-live gate — the standing blockers (GCP billing closed / 6 migrations / Stripe events / Kie cap / legal copy) remain.
- [ ] **Step 3 — commit.** `git add docs/GO-LIVE-READINESS.md && git commit -m "docs: super-admin dashboard note in go-live readiness"`

---

## Self-review (author check before execution)
- **Spec coverage:** vehicle (Task 5), read tracking (Tasks 1,3), all four manage actions — grant (reuse in Task 5 UI), cancel+refund (Tasks 2,4), delete (Tasks 2,4), recover (reuse in Task 5 UI); activation card (Tasks 1,3,5); migration bundle (done). ✓
- **Target-user correctness:** the refund-credits-the-target assertion is an explicit test in Task 4 — the one bug that would silently make admin cancels no-op the refund. ✓
- **Traversal:** `_admin_target_user` + the `admin_re_assemble_song` fix, both tested. ✓
- **No new migrations.** ✓  **Runs walk capped** (summarize only the sliced page). ✓  **Token never in URL.** ✓
- **Type consistency:** impls return the same types the routes already declare (`CancelAck`, `DeleteAck`, dict); admin routes reuse those response_models. ✓
