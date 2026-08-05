# Billing Money-Integrity Hardening — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the 5 Tier-1 money-integrity blockers (unbilled video renders, no refund on song cancel/failure, double-spend race, non-idempotent Stripe grants, no dunning) and green the money/video test path, so it is safe to charge real users.

**Architecture:** Small, surgical fixes on existing code. `run.py` recovers the real user from the run-dir path (one chokepoint). Existing `refund_run_charges` is wired into the song cancel/failure holes. Deduction becomes atomic via a Postgres function called with `.rpc()`. Stripe grants become idempotent via a DB unique index + insert-if-absent. A `payment_status` column + `invoice.payment_failed` handler + Flutter banner add dunning. Three SQL migrations are authored here and **applied to the live Supabase DB by the operator**.

**Tech Stack:** Python 3.11, FastAPI, supabase-py (service role, supports `.rpc()`), Stripe, Flutter, pytest with `unittest.mock` (Supabase/`.rpc()`/Stripe/ffmpeg all mocked — never hit real services).

**Spec:** `docs/superpowers/specs/2026-08-04-billing-money-integrity-design.md`

**Repo invariants:** every `.py` starts with `from __future__ import annotations`; absolute imports; `pathlib.Path`; external services mocked in tests. **Current baseline: 7 pre-existing failures** (`test_api::test_approve_passes_auto_computed_max_spend`, 2× `test_mp4_faststart`, 3× `test_run_shorts_smoke`, `test_llm_groq::test_complete_sends_chat_payload`) — Tasks 1–5 must add no NEW failures; Task 6 greens/triages these 7.

---

## File structure

- `run.py` — `_effective_user_id`; set `args.user_id` from it after resolve; song-failure refund.
- `pipeline/api.py` — `cancel_song` refund; `/billing/plan` exposes `payment_status`; `PlanResponse.payment_status`.
- `pipeline/credits.py` — `check_or_deduct` delegates to atomic rpc.
- `pipeline/db.py` — `deduct_credits_atomic`, `record_grant_once`, `payment_status` on `UserProfile`/`get_user_profile`.
- `pipeline/stripe_billing.py` — idempotent grants; `invoice.payment_failed`→past_due; reset to active on success/cancel.
- `lib/screens/billing_screen.dart` (+ l10n) — past-due banner.
- `supabase/migrations/2026080400000{1,2,3}_*.sql` — 3 new migrations (operator-applied).
- Tests: `tests/test_run_charging.py` (new), `test_credits.py`, `test_db.py` (new or extend), `test_stripe_billing.py`, `test_song_api.py`, `test_api.py`, `test_llm_groq.py`.

---

## Task 1: Charge the real user for video renders (Fix 1)

**Files:** Modify `run.py`. Test: `tests/test_run_charging.py` (new).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_run_charging.py`:

```python
from __future__ import annotations

from pathlib import Path

import run


def test_effective_user_id_recovers_uuid_from_path(tmp_path):
    out = tmp_path / "out"
    rd = out / "abc-123-uuid" / "2026-08-04-1200"
    assert run._effective_user_id(rd, out) == "abc-123-uuid"


def test_effective_user_id_admin_stays_service(tmp_path):
    out = tmp_path / "out"
    rd = out / "admin" / "2026-08-04-1200"
    assert run._effective_user_id(rd, out) == "admin"


def test_effective_user_id_unexpected_layout_falls_back_to_admin(tmp_path):
    # run_dir not under out_root → ValueError → safe 'admin' (free) fallback
    assert run._effective_user_id(tmp_path / "x" / "y", tmp_path / "other") == "admin"
```

- [ ] **Step 2: Run — verify fail**

Run: `uv run pytest tests/test_run_charging.py -v`
Expected: FAIL — `module 'run' has no attribute '_effective_user_id'`.

- [ ] **Step 3: Implement `_effective_user_id` + wire it**

Add near `_resolve_run_dir` in `run.py`:

```python
def _effective_user_id(run_dir: Path, out_root: Path) -> str:
    """The user id owning a run = the path segment directly under out_root
    (runs live at <out_root>/<user_id>/<run_id>). On --resume this recovers
    the REAL user so paid stages charge/refund the right account instead of
    defaulting to the free 'admin' service role. Falls back to 'admin'
    (service/free) if the layout is unexpected — fail safe, never over-charge."""
    try:
        return run_dir.resolve().relative_to(out_root.resolve()).parts[0]
    except (ValueError, IndexError):
        return "admin"
```

In `main_with_args`, immediately after `run_dir = _resolve_run_dir(args, out_root)` (currently `run.py:693`):

```python
    run_dir = _resolve_run_dir(args, out_root)
    # Recover the owning user from the run-dir path so resumed paid stages
    # charge/refund the real user, not the default 'admin' service role.
    # (Fresh runs already encode args.user_id in the path, so this is a no-op
    # for them; resumes are where it matters.)
    args.user_id = _effective_user_id(run_dir, out_root)
```

This corrects the role at `run.py:511` (video charge) and `run.py:843` (video refund), and gives the song path (Task 2) the real user via `args.user_id`.

- [ ] **Step 4: Run — verify pass**

Run: `uv run pytest tests/test_run_charging.py -v`
Expected: PASS (3).

- [ ] **Step 5: Commit**

```bash
git add run.py tests/test_run_charging.py
git commit -m "$(cat <<'EOF'
fix(billing): charge the real user for video renders (derive user from run-dir path)

Resumed paid stages defaulted --user-id to 'admin' (service role), so
check_or_deduct no-op'd and renders were never billed. Recover the owning
user from the run-dir path at one chokepoint so all spawn paths charge/refund
the real user. Admin/CLI runs (out/admin/...) stay free.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Refund song on cancel; failed render keeps the charge (Fix 2)

> **REVISED during review (policy decision):** a failed render is NOT auto-refunded (that + free `/resume` = free songs). Refund on **cancel** only; failure keeps the charge (resume = free retry). `cancel_song` re-reads state after SIGTERM and skips refund if the run completed in the race window. The steps below that add a worker-failure refund are superseded — the worker's terminal except records `failed` and returns, no refund. See the design spec's Fix 2 for the authoritative version.

**Files:** Modify `pipeline/api.py` (`cancel_song`), `run.py` (`_run_song_post_approve` failure handler). Tests: `tests/test_song_api.py`, `tests/test_run_song_mode.py`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_song_api.py`:

```python
def test_cancel_song_refunds_charges(app, monkeypatch):
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    from pipeline import api as api_mod

    captured = {}
    monkeypatch.setattr(api_mod, "_process_alive", lambda pid, rd: False)
    import pipeline.credits as credits_mod
    monkeypatch.setattr(credits_mod, "refund_run_charges",
                        lambda user, *, run_id, reason: captured.update(run_id=run_id) or 5)
    # also patch the name as imported into api if it re-exports; safest: patch source
    monkeypatch.setattr("pipeline.credits.refund_run_charges",
                        lambda user, *, run_id, reason: captured.update(run_id=run_id) or 5)

    r = client.post("/songs", json={"theme": "x", "language": "ar"},
                    headers={"Authorization": f"Bearer {token}"})
    run_id = r.json()["run_id"]
    rc = client.post(f"/songs/{run_id}/cancel",
                     headers={"Authorization": f"Bearer {token}"})
    assert rc.status_code == 200, rc.text
    assert captured.get("run_id") == run_id
    assert rc.json().get("refunded") == 5
```

Add to `tests/test_run_song_mode.py` a test that a song-worker failure refunds (mock a stage to raise + capture `refund_run_charges`):

```python
def test_song_worker_failure_refunds(tmp_path, monkeypatch):
    import run as run_mod
    from pathlib import Path
    import json as _json
    run_dir = tmp_path / "out" / "user-uuid" / "2026-08-04-1200"
    run_dir.mkdir(parents=True)
    (run_dir / "api_state.json").write_text(_json.dumps(
        {"kind": "song", "status": "generating_song"}))
    (run_dir / "song.json").write_text(_json.dumps(
        {"title": "t", "lyrics": "[Chorus]\nx", "style_prompt": "s",
         "cover_prompt": "c", "language": "ar"}))
    # Force the song stage to raise, and capture the refund.
    refunded = {}
    monkeypatch.setattr("pipeline.credits.refund_run_charges",
                        lambda user, *, run_id, reason: refunded.update(run_id=run_id, user=user.id) or 3)
    monkeypatch.setattr(run_mod.song, "submit_song_job",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("suno boom")))
    monkeypatch.setattr(run_mod.api if hasattr(run_mod, "api") else run_mod,
                        "_build_song_llm", lambda: object(), raising=False)
    rc = run_mod.main_with_args(["--mode", "song", "--resume", str(run_dir)])
    assert rc == 1
    assert refunded.get("run_id") == run_dir.name
    assert refunded.get("user") == "user-uuid"   # real user (Task 1), not admin
```

(Adapt the mocks to the actual song-worker entry — the implementer confirms `submit_song_job` is the first paid call and that `_build_song_llm` is stubbed as in the existing song-mode tests. If the harness differs, mirror the existing `test_run_song_mode.py` premium test's setup.)

- [ ] **Step 2: Run — verify fail**

Run: `uv run pytest tests/test_song_api.py -k cancel_song_refunds tests/test_run_song_mode.py -k song_worker_failure_refunds -v`
Expected: FAIL (no refund call yet).

- [ ] **Step 3: Wire refund into `cancel_song`**

In `pipeline/api.py` `cancel_song`, replace the tail:

```python
    _write_state(run_dir, status="canceled")
    refunded = 0
    try:
        from pipeline.credits import refund_run_charges
        refunded = refund_run_charges(user, run_id=run_id,
                                      reason="song canceled by user")
    except Exception as e:  # refund telemetry must never fail the cancel
        print(f"[cancel_song] refund failed for {run_id}: {e}")
    return {"ok": True, "refunded": refunded}
```
(`refund_run_charges` is net-safe: a song canceled before approval was never charged → net 0 → refunds 0.)

- [ ] **Step 4: Wire refund into the song-worker failure handler**

In `run.py` `_run_song_post_approve`, the terminal `except Exception as e:` block (currently `run.py:~1532`), before `return 1`, add (using the run dir the function already resolved from `args.resume` — confirm its variable name; below assumes `run_dir`):

```python
        try:
            from pipeline.auth import User as _U
            from pipeline.credits import refund_run_charges
            _role = "service" if args.user_id == "admin" else "user"
            refund_run_charges(
                _U(id=args.user_id, email=None, role=_role),
                run_id=run_dir.name,
                reason=f"song render failed: {type(e).__name__}")
        except Exception as refund_exc:
            print(f"[song-post-approve] REFUND FAILED for {run_dir.name}: "
                  f"{refund_exc}. Manual credit return may be required.",
                  file=_sys.stderr)
```

- [ ] **Step 5: Run — verify pass** (`uv run pytest tests/test_song_api.py tests/test_run_song_mode.py -q`; the two new tests pass, no new failures).

- [ ] **Step 6: Commit**

```bash
git add pipeline/api.py run.py tests/test_song_api.py tests/test_run_song_mode.py
git commit -m "$(cat <<'EOF'
fix(billing): refund song credits on cancel and on worker failure

Song credits are deducted at approve; cancel_song and the song worker's
failure handler never refunded (charged, got nothing). Wire the existing
net-safe refund_run_charges into both.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Atomic deduction (Fix 3)

**Files:** New `supabase/migrations/20260804000001_deduct_credits_fn.sql`; modify `pipeline/db.py`, `pipeline/credits.py`. Tests: `tests/test_db.py` (new/extend), `tests/test_credits.py`.

- [ ] **Step 1: Author the migration**

Create `supabase/migrations/20260804000001_deduct_credits_fn.sql`:

```sql
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
```
(Confirmed: `credit_transactions.user_id` is `uuid` in `20260511000000_credits.sql:31` — keep `p_user_id uuid` as written. The SQL is operator-applied — see Task 7 — so it is reviewed by reading, not unit-tested.)

- [ ] **Step 2: Write the failing tests**

> **Remove the two now-obsolete tests first.** `check_or_deduct` will no longer call `get_balance`+`record_transaction` on the happy path (the DB function does the insert), so the existing `mock_db`-based `test_check_or_deduct_succeeds_when_balance_sufficient` (`tests/test_credits.py:68`) and `test_check_or_deduct_raises_when_balance_insufficient` (`:79`) will BREAK — `mock_db` doesn't stub `deduct_credits_atomic`, so a non-service call would hit the real client. Delete both; the three new tests below supersede them. Keep `test_check_or_deduct_skips_service_user` (`:89`) — the service branch is unchanged (though it's now partly redundant with the new bypass test).

Add to `tests/test_credits.py` (the new tests monkeypatch `pipeline.credits.deduct_credits_atomic` directly — they do NOT use the `mock_db` fixture):

```python
def test_check_or_deduct_uses_atomic_rpc_and_returns_new_balance(monkeypatch):
    from pipeline import credits
    monkeypatch.setattr("pipeline.credits.deduct_credits_atomic",
                        lambda **kw: 7)
    from pipeline.auth import User
    u = User(id="u1", email=None, role="user")
    assert credits.check_or_deduct(u, amount=3, run_id="r1", reason="x") == 7


def test_check_or_deduct_raises_when_atomic_returns_negative(monkeypatch):
    import pytest
    from pipeline import credits
    monkeypatch.setattr("pipeline.credits.deduct_credits_atomic", lambda **kw: -1)
    monkeypatch.setattr("pipeline.credits.get_balance", lambda uid: 2)
    from pipeline.auth import User
    u = User(id="u1", email=None, role="user")
    with pytest.raises(credits.InsufficientCredits):
        credits.check_or_deduct(u, amount=5, run_id="r1", reason="x")


def test_check_or_deduct_service_bypass_skips_rpc(monkeypatch):
    from pipeline import credits
    monkeypatch.setattr("pipeline.credits.deduct_credits_atomic",
                        lambda **kw: (_ for _ in ()).throw(AssertionError("should not call")))
    from pipeline.auth import User
    u = User(id="admin", email=None, role="service")
    assert credits.check_or_deduct(u, amount=99, run_id="r1", reason="x") == 10**9
```

Add to `tests/test_db.py` (**it already exists** — extend it; do NOT recreate). Prefer reusing the existing `fake_client` fixture (which monkeypatches `pipeline.db._client`) by giving `_FakeClient` an `rpc` method, rather than the standalone client below. Either is acceptable as long as it asserts the rpc name + params and returns the scalar:

```python
# Option A — extend the existing _FakeClient with an rpc() that records the call
# and returns a _Resp(data=...), then a test that calls deduct_credits_atomic
# through the fake_client fixture and asserts params + returned scalar.

# Option B — self-contained (if you don't extend the fixture):
import pipeline.db as db


def test_deduct_credits_atomic_returns_rpc_scalar(monkeypatch):
    class _Resp:
        data = 4
    class _Q:
        def execute(self): return _Resp()
    class _Client:
        def rpc(self, name, params):
            assert name == "deduct_credits"
            assert params["p_user_id"] == "u1" and params["p_amount"] == 3
            return _Q()
    monkeypatch.setattr(db, "_client", lambda: _Client())
    assert db.deduct_credits_atomic(user_id="u1", amount=3, kind="run_charge",
                                    reference_id="r1", description="x") == 4
```

- [ ] **Step 3: Run — verify fail** (`ImportError: cannot import name 'deduct_credits_atomic'` / attribute missing).

- [ ] **Step 4: Implement**

In `pipeline/db.py`:

```python
def deduct_credits_atomic(*, user_id: str, amount: int, kind: str,
                          reference_id: str, description: str) -> int:
    """Atomic check-and-deduct via the deduct_credits Postgres function
    (per-user advisory lock). Returns the new balance, or -1 if the balance
    was insufficient (nothing was deducted)."""
    resp = _client().rpc("deduct_credits", {
        "p_user_id": user_id, "p_amount": amount, "p_kind": kind,
        "p_reference_id": reference_id, "p_description": description,
    }).execute()
    return int(resp.data)
```

In `pipeline/credits.py`, add `deduct_credits_atomic` to the `from pipeline.db import (...)` block and replace `check_or_deduct`'s body (keep signature + docstring intent):

```python
    if _is_service(user):
        return 10**9
    new_balance = deduct_credits_atomic(
        user_id=user.id, amount=amount, kind="run_charge",
        reference_id=run_id, description=reason,
    )
    if new_balance < 0:
        raise InsufficientCredits(balance=get_balance(user.id), required=amount)
    return new_balance
```
Update the docstring: remove the "concurrent runs could overspend by one clip — accepted tradeoff" note (now fixed); state it's atomic via the DB function.

- [ ] **Step 5: Run — verify pass** (`uv run pytest tests/test_credits.py tests/test_db.py -v`).

- [ ] **Step 6: Commit**

```bash
git add supabase/migrations/20260804000001_deduct_credits_fn.sql pipeline/db.py pipeline/credits.py tests/test_credits.py tests/test_db.py
git commit -m "$(cat <<'EOF'
fix(billing): atomic credit deduction via Postgres advisory-lock function

check_or_deduct was read-then-insert (racy — parallel approves could go
negative). Delegate to a deduct_credits() Postgres function called via rpc,
serialized per-user with an advisory lock. Migration is operator-applied.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Idempotent Stripe grants (Fix 4)

**Files:** New `supabase/migrations/20260804000002_grant_idempotency.sql`; modify `pipeline/db.py`, `pipeline/stripe_billing.py`. Tests: `tests/test_db.py`, `tests/test_stripe_billing.py`.

- [ ] **Step 1: Author the migration**

Create `supabase/migrations/20260804000002_grant_idempotency.sql`:

```sql
-- A given Stripe invoice/session grants credits exactly once. A retried
-- webhook delivery then hits this unique index and is a no-op.
create unique index if not exists uq_credit_grant_ref
  on credit_transactions (reference_id, kind)
  where kind in ('subscription_renewal', 'topup');
```

- [ ] **Step 2: Write the failing tests**

`tests/test_db.py`:

```python
def test_record_grant_once_inserts_then_dedups(monkeypatch):
    calls = {"n": 0}
    class _Q:
        def execute(self):
            calls["n"] += 1
            if calls["n"] > 1:
                raise Exception('duplicate key value violates unique constraint '
                                '"uq_credit_grant_ref" (code 23505)')
            class R: data = [{}]
            return R()
    class _T:
        def insert(self, payload): return _Q()
    class _Client:
        def table(self, name): return _T()
    monkeypatch.setattr(db, "_client", lambda: _Client())
    assert db.record_grant_once(user_id="u", amount=60, kind="subscription_renewal",
                                reference_id="inv_1", description="x") is True
    assert db.record_grant_once(user_id="u", amount=60, kind="subscription_renewal",
                                reference_id="inv_1", description="x") is False
```

`tests/test_stripe_billing.py` (**exists** — extend). Two gaps verified against code, must be handled or the suite breaks:
- Its `mock_db` fixture currently monkeypatches `pipeline.stripe_billing.record_transaction`. After the refactor both grant sites call `record_grant_once` instead, so the fixture must stub `pipeline.stripe_billing.record_grant_once` (default return `True`); the `record_transaction` stub target will no longer exist once the import is dropped (see Step 3). Update the fixture accordingly.
- The existing grant-asserting tests read `mock_db["transactions"][-1]` (e.g. `test_handle_webhook_subscription_renewal_grants:124-126` asserts `amount==60`, `kind=="subscription_renewal"`). LEAST-INVASIVE fix: make the fixture's `record_grant_once` stub **append to the same `mock_db["transactions"]` list** (mirroring the existing `fake_record`) and return `True` — then those assertions pass unchanged and you don't rewrite them. The per-test dedup test below overrides the stub locally. (`test_handle_webhook_uses_item_period_end_for_newer_stripe` / `..._reads_parent_subscription_details` also land a grant — the same fixture change keeps them green.)

New test: a duplicate `invoice.payment_succeeded` grants once — mock `record_grant_once` to return True then False and assert the second call yields a "duplicate invoice, no-op" note (no second grant).

- [ ] **Step 3: Implement**

In `pipeline/db.py`:

```python
def _is_unique_violation(exc: Exception) -> bool:
    s = str(exc).lower()
    return "23505" in s or "duplicate key" in s or "unique constraint" in s


def record_grant_once(*, user_id: str, amount: int, kind: str,
                      reference_id: str | None, description: str | None) -> bool:
    """Insert a grant transaction idempotently. Returns False (no-op) if a grant
    with the same (reference_id, kind) already exists — the unique index rejects
    it — so a duplicate Stripe webhook delivery never double-grants."""
    try:
        _client().table("credit_transactions").insert({
            "user_id": user_id, "amount": amount, "kind": kind,
            "reference_id": reference_id, "description": description,
        }).execute()
        return True
    except Exception as e:
        if _is_unique_violation(e):
            return False
        raise
```

In `pipeline/stripe_billing.py`, add `record_grant_once` to the `from pipeline.db import (...)` line (line 21). After swapping BOTH grant sites below, `record_transaction` is no longer used in this module — **remove it from that import** (grep to confirm no other use) so there's no dead import. In `_on_invoice_paid`, replace the grant `record_transaction(...)` with:

```python
    granted = record_grant_once(
        user_id=user_id, amount=PLAN_GRANTS[plan], kind="subscription_renewal",
        reference_id=invoice.get("id"), description=f"{plan.capitalize()} plan renewal")
    upsert_user_profile(user_id, current_plan=plan,
                        current_period_end=_iso(period_end_unix),
                        cancel_at_period_end=bool(subscription.get("cancel_at_period_end", False)))
    note = f"+{PLAN_GRANTS[plan]} for {plan}" if granted else "duplicate invoice, no-op"
    return WebhookOutcome("invoice.payment_succeeded", True, note)
```
And in `_on_checkout_completed` topup path, swap `record_transaction(kind="topup", ...)` → `record_grant_once(... kind="topup", reference_id=session.get("id") ...)`.
(The `payment_status="active"` reset is added to this same upsert in Task 5, once the column exists — Task 4 leaves it out so it can ship/deploy independently of the Task 5 migration.)

- [ ] **Step 4: Run — verify pass** (`uv run pytest tests/test_db.py tests/test_stripe_billing.py -v`).

- [ ] **Step 5: Commit** — `fix(billing): idempotent Stripe grants (unique index + insert-if-absent)` (+ trailer).

---

## Task 5: Dunning — surface failed renewals (Fix 5)

**Files:** New `supabase/migrations/20260804000003_payment_status.sql`; modify `pipeline/db.py`, `pipeline/stripe_billing.py`, `pipeline/api.py`, `lib/screens/billing_screen.dart` (+ l10n). Tests: `tests/test_stripe_billing.py`, `tests/test_song_api.py`/`test_api.py`.

- [ ] **Step 1: Author the migration**

`supabase/migrations/20260804000003_payment_status.sql`:
```sql
alter table user_profiles
  add column if not exists payment_status text not null default 'active';
```

- [ ] **Step 2: Write the failing tests**

`tests/test_stripe_billing.py`. **There is NO `handle_webhook_event(et, data)` — the only entry is `handle_webhook(raw_body, signature)`.** Test through it exactly like the existing handler tests (`test_handle_webhook_subscription_deleted_resets_plan:130-140`): monkeypatch `stripe.Webhook.construct_event` to return a fake event dict, use the `stripe_env` + `mock_db` fixtures, and assert on `mock_db["profiles"]` (the fixture's `upsert_user_profile` stub writes there):
```python
def test_handle_webhook_invoice_failed_marks_past_due(stripe_env, mock_db, monkeypatch):
    mock_db["profiles"]["u1"] = {"current_plan": "creator"}
    fake_event = {
        "type": "invoice.payment_failed",
        "data": {"object": {"subscription": "sub_1"}},
    }
    monkeypatch.setattr("pipeline.stripe_billing.stripe.Subscription.retrieve",
                        lambda sid: {"id": sid, "metadata": {"user_id": "u1"}})
    monkeypatch.setattr("pipeline.stripe_billing.stripe.Webhook.construct_event",
                        lambda **kw: fake_event)
    outcome = handle_webhook(b"{}", "sig")
    assert outcome.handled
    assert mock_db["profiles"]["u1"]["payment_status"] == "past_due"
```
(Confirm the `mock_db` fixture's `upsert_user_profile` stub merges `**fields` into `mock_db["profiles"][uid]` — the existing subscription-deleted test relies on that, so it does.)

Add an `api` test that `/billing/plan` returns `payment_status`.

- [ ] **Step 3: Implement**

- `pipeline/db.py`: add `payment_status: str = "active"` to `UserProfile`; add `payment_status` to the `get_user_profile` `.select(...)` list and the constructed dataclass (`payment_status=d.get("payment_status", "active")`).
- `pipeline/stripe_billing.py`: add to the dispatch table `if et == "invoice.payment_failed": return _on_invoice_failed(data)`; implement:
```python
def _on_invoice_failed(invoice) -> WebhookOutcome:
    sub_id = invoice.get("subscription") or _invoice_subscription_id(invoice)
    user_id = None
    if sub_id:
        raw = stripe.Subscription.retrieve(sub_id)
        sub = raw.to_dict() if hasattr(raw, "to_dict") else dict(raw)
        user_id = (sub.get("metadata") or {}).get("user_id")
    user_id = user_id or _invoice_parent_metadata(invoice).get("user_id")
    if not user_id:
        return WebhookOutcome("invoice.payment_failed", False, "no user_id")
    upsert_user_profile(user_id, payment_status="past_due")
    return WebhookOutcome("invoice.payment_failed", True, "marked past_due")
```
Now that the column exists, add `payment_status="active"` to the `upsert_user_profile(...)` calls in `_on_invoice_paid` and `_on_subscription_deleted` (so a successful payment or a clean cancel clears any prior `past_due`).
- `pipeline/api.py`: add `payment_status: str = "active"` to `PlanResponse`; populate it in `get_plan_endpoint` from `profile.payment_status` (service branch → `"active"`).
- `lib/screens/billing_screen.dart` (+ new l10n keys en/ar, regen with `flutter gen-l10n`): when the plan's `payment_status == 'past_due'`, render a warning banner ("Your last payment failed — update your card") with a button that opens the existing `/billing/portal` flow. Parse `payment_status` in the plan model in `lib/api/models.dart`.

- [ ] **Step 4: Run — verify pass** (targeted stripe + api tests; then `flutter analyze lib/screens/billing_screen.dart lib/api/models.dart` → 0 errors).

- [ ] **Step 5: Commit** — `feat(billing): dunning — invoice.payment_failed marks past_due + app banner` (+ trailer).

---

## Task 6: Green the money/video test path (Fix 6)

**Files:** `tests/test_api.py`, `tests/test_llm_groq.py`, and triage of `tests/test_mp4_faststart.py`, `tests/test_run_shorts_smoke.py`.

- [ ] **Step 1: Diagnose all 7**

Run each and read the error: `uv run pytest tests/test_api.py::test_approve_passes_auto_computed_max_spend tests/test_llm_groq.py::test_complete_sends_chat_payload tests/test_mp4_faststart.py tests/test_run_shorts_smoke.py -v`. Classify each as (a) stale assertion, (b) real defect, (c) local-ffmpeg-only environment failure.

> **Diagnosis already done (2026-08-05, evidence captured) — start from this, re-confirm, don't re-derive:**
> - `test_approve_passes_auto_computed_max_spend` → **(a) stale assertion.** Actual max-spend = **12.98**; asserts `24 < spend < 30`. Formula reverse-engineered and confirmed: `24 beats × 8 s × $0.05 (kling/v2-1-pro) × 1.30 buffer + 0.50 pad = 12.98`. Fix per Step 2.
> - `test_complete_sends_chat_payload` → **(a) stale assertion.** Asserts model `"llama-3.3-70b-versatile"`; actual default `"openai/gpt-oss-120b"`. One-line update.
> - `test_mp4_faststart` (2 tests) → **NOT a prod defect and NOT an ffmpeg-version issue — it's a too-small test fixture.** Confirmed empirically: local ffmpeg 8.1 DOES faststart correctly (a real re-mux yields atom order `['ftyp','moov','free','mdat']` — moov first). The test's `_make_test_mp4` produces a **1849-byte** clip (64×64, 1 s, solid color). `pipeline/mp4_faststart.py:51` has a safety guard `if out_size < max(50_000, in_size*0.5): return` (refuse to overwrite the original with suspiciously-tiny output — a real corruption guard). 1849 < 50000 → the guard trips → the faststart'd temp is discarded, the original (moov-at-end) is left in place → the test sees `['ftyp','free','mdat','moov']` and fails. **Fix in Step 3: enlarge the test clip past the 50 KB floor (real Veo clips are MBs, so this is the realistic case) — e.g. `testsrc2=size=640x480:rate=30:duration=3` (high-detail source doesn't compress to near-nothing the way solid `color=` does; verify the produced file is > 50 KB). Do NOT weaken the 50 KB guard and do NOT skip the test — the moov-first invariant must still be asserted.** Expected order after faststart on a >50 KB clip: moov before mdat.
> - `test_run_shorts_smoke` (3 tests) → **environment/ordering-sensitive, NOT a hard failure.** They PASS when run in isolation (`uv run pytest tests/test_run_shorts_smoke.py`, with `.env` sourced) but were reported failing in the full-suite run. Step 3: reproduce by running the FULL suite (`uv run pytest -q`), read the actual failure (likely test-ordering shared state or a missing env/tool only in the full run), then fix the isolation cause or add a precise env-guarded skip — do not weaken assertions.

- [ ] **Step 2: Fix the two stale assertions**

- `tests/test_api.py::test_approve_passes_auto_computed_max_spend` asserts `24 < spend < 30` (a $0.10/s Veo assumption); the active model (`kling/v2-1-pro`, $0.05/s) yields ≈$12.98. Make it robust — compute the expected from the active model rate instead of a hardcoded range:
```python
    from pipeline import api as api_mod
    rate = api_mod._cost_per_second_for_model(api_mod._active_video_model())
    expected = 24 * 8 * rate * 1.30 + 0.50   # match the backend's beats×dur×rate×buffer+pad
    assert abs(spend - expected) < 1.0, f"unexpected max-spend: {spend} vs {expected}"
```
(Confirm the backend's exact buffer constants at the approve max-spend computation and mirror them; the point is to derive from the active rate, not hardcode a Veo-era range.)
- `tests/test_llm_groq.py::test_complete_sends_chat_payload`: `assert ... == "llama-3.3-70b-versatile"` → the current `GroqClient` default (`"openai/gpt-oss-120b"` — confirm by reading `pipeline/llm_groq.py`).

- [ ] **Step 3: Fix-or-document the ffmpeg tests**

For `test_mp4_faststart` (2) + `test_run_shorts_smoke` (3): if they are real defects (e.g. a broken filtergraph, a code path that produces a non-faststart mp4), fix the code. If they fail only due to the local ffmpeg/environment (verify the exact error) and pass in the prod Debian-ffmpeg container, add a precise skip/marker guarded on the environment cause with a comment — **do not** weaken the assertion; the invariant must still be checked where ffmpeg works. Report the classification + what you did for each.

- [ ] **Step 4: Run — verify** (`uv run pytest tests/test_api.py tests/test_llm_groq.py tests/test_mp4_faststart.py tests/test_run_shorts_smoke.py -v`) and report the new baseline.

- [ ] **Step 5: Commit** — `test(billing): green money/video test path (max-spend, groq model, ffmpeg triage)` (+ trailer).

---

## Task 7: Full-suite verification + operator handoff

**Files:** none (verification) + append an "Operator actions" note to `docs/GO-LIVE-READINESS.md`.

- [ ] **Step 1: Full suite** — `uv run pytest -q`. Confirm the count is at or below the corrected baseline (the 2 stale tests now green; the 3 idempotency/atomic/dunning areas green; no new failures). Report the exact failing set (should be only genuinely-environmental ffmpeg tests, if any, documented in Task 6).

- [ ] **Step 2: Offline smoke — refund + atomic wiring never crash**
```bash
uv run python -c "
from pipeline import credits
from pipeline.auth import User
# service bypass path still returns the sentinel without any DB call
print('service deduct =', credits.check_or_deduct(User(id='admin', email=None, role='service'), amount=5, run_id='r', reason='x'))
print('refund_run_charges import OK:', bool(credits.refund_run_charges))
"
```
Expected: prints the sentinel + import OK, no traceback.

- [ ] **Step 3: Write the operator handoff**

Append to `docs/GO-LIVE-READINESS.md` an "Operator actions — Phase 0" section listing exactly:
1. Apply the 3 migrations to live Supabase: `supabase db push` (or paste each `supabase/migrations/2026080400000{1,2,3}_*.sql` into the Supabase SQL editor, in order). Verify: `deduct_credits` function exists, `uq_credit_grant_ref` index exists, `user_profiles.payment_status` column exists.
2. Stripe Dashboard → Webhooks → add event `invoice.payment_failed` to the existing endpoint.
3. Redeploy: `scripts/build-and-push.sh`.
4. Post-deploy money test: subscribe (Stripe test card) → render a video → confirm balance decrements → cancel a song → confirm refund → confirm no negative balance.

- [ ] **Step 4: Commit** — `docs+test: phase-0 operator handoff + full-suite verification` (+ trailer).

---

## Follow-ups (out of scope — in `docs/GO-LIVE-READINESS.md`)
Chargeback/dispute handling, Stripe Tax, API-version pinning, moving the file-based rate/concurrency caps to the DB, LLM draft/regen metering, data-retention TTL, and all Tier 2/3 launch items (monitoring, spend caps, backups, legal). The migrations here are additive and safe to apply before the code deploy (the new function/index/column are unused until the new code ships).
