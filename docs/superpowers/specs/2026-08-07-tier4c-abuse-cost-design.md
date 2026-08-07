# Tier-4C Abuse & Cost Controls — Design

**Date:** 2026-08-07
**Status:** approved to proceed (user: "complete the Tier-4")
**Scope:** Third Tier-4 sub-project. (C1) move the racy file-based **daily** song cap to a DB-backed rate primitive; (C2) **throttle the unmetered LLM draft/regen endpoints** using the same primitive.

## Context (verified 2026-08-07)
- `pipeline/api.py`: the **daily** song cap (`_SONG_DAILY_LIMIT=30`) uses `_rate_limit.json` per user-root (`_load_rate_log`/`_record_song_approval`) — a JSON file on GCS-Fuse, **racy across the (≤4) Cloud Run instances**. The **concurrent** cap (`_count_active_song_runs`) scans real run-state on disk — not file-racy, leave as-is.
- LLM draft/regen endpoints make Anthropic/Gemini calls with **no per-user throttle**: `create_song` (writer pass → `generate_song_script`), `regenerate-lyrics`, `regenerate-cover-prompt`, and the morning-draft generator. A user with ≥1 credit (or the free script-gen) can spam them → unbounded LLM spend.
- Credit ledger + `deduct_credits` (Postgres rpc) already show the DB-primitive pattern; a rate table fits the same shape.

## Architecture — one DB-backed rate primitive, two uses

### Shared primitive
- **Migration** `supabase/migrations/20260807000002_rate_events.sql`:
  ```sql
  create table if not exists public.rate_events (
    id         bigint generated always as identity primary key,
    user_id    uuid not null,
    action     text not null,
    created_at timestamptz not null default now()
  );
  create index if not exists rate_events_lookup
    on public.rate_events (user_id, action, created_at desc);
  ```
- **`pipeline/db.py`**:
  ```python
  def record_rate_event(user_id: str, action: str) -> None:
      _client().table("rate_events").insert({"user_id": user_id, "action": action}).execute()

  def count_rate_events(user_id: str, action: str, within_seconds: int) -> int:
      since = (datetime.now(timezone.utc) - timedelta(seconds=within_seconds)).isoformat()
      resp = (_client().table("rate_events")
              .select("id", count="exact")
              .eq("user_id", user_id).eq("action", action)
              .gte("created_at", since).execute())
      return resp.count or 0
  ```
  (`count="exact"` returns `resp.count`. If the installed supabase-py doesn't populate `.count`, fall back to `len(resp.data or [])` selecting `id` — the implementer picks whichever the version supports; a test pins the behavior.)
  A soft cap: count-then-insert has a tiny race window, harmless for a 30/day bill-shock guard (off-by-one under a race is fine) — and it's now correct across instances (shared DB, not per-instance file).

### C1 — Daily song cap → DB
- Replace `_load_rate_log`/`_record_song_approval`/`_rate_limit_path` usage: `_enforce_daily_song_limit(user)` → `count_rate_events(user.id, "song_approve", 86400) >= _SONG_DAILY_LIMIT` → 429 (same message/limit). Record via `record_rate_event(user.id, "song_approve")` at the same point approvals were logged. Service bypass unchanged. Delete the now-dead file helpers (or leave them unused — prefer delete). `_SONG_DAILY_LIMIT`/env unchanged.

### C2 — LLM draft/regen throttle
- `_LLM_HOURLY_LIMIT = int(os.environ.get("FACELESS_LLM_HOURLY_LIMIT", "30"))`.
- `_enforce_llm_rate_limit(user)` (service bypass): `count_rate_events(user.id, "llm_call", 3600) >= _LLM_HOURLY_LIMIT` → `HTTPException(429, {"code": "llm_rate_limited"})`; else `record_rate_event(user.id, "llm_call")`. Call it at the top of the LLM-heavy endpoints: `create_song` (writer pass), `regenerate-lyrics`, `regenerate-cover-prompt` (locate the exact handlers by grep). (Morning-drafts is an internal/scheduled generator — exempt; it's already idempotent-per-day.) Place AFTER `_require_terms_accepted`/`_require_email_confirmed` so gating order is consistent.

## Testing
- **`tests/test_db.py`**: `record_rate_event` inserts (action+user); `count_rate_events` returns the count for the window (fake_client — assert it filters by user_id/action/created_at and returns the count/len).
- **`tests/test_api.py`** or `tests/test_legal.py`: daily cap → 429 when `count_rate_events` (monkeypatched) ≥ limit, passes under; an LLM endpoint → 429 `llm_rate_limited` when over the hourly cap, records an event under; service bypass for both. (The autouse fixtures keep terms/email transparent.)
- **Baseline:** clean-env suite **875 passed, 0 failed**; no new failures.

## Deploy coupling / operator
- Apply `20260807000002_rate_events.sql` before deploy. No Stripe/console steps. (Optional operator: a retention/cleanup of old `rate_events` rows — folded into Tier-4D's retention TTL.)

## Deferred
- Concurrent cap stays disk-scan (not file-racy). Distributed exactness (advisory-locked count-and-insert) is overkill for a soft bill-shock cap — not done.

## Key invariants
- Service tokens bypass both caps. External services mocked in tests. Migration operator-applied. `db.py` additions use `from __future__ import annotations` + `datetime`/`timedelta` imports.
