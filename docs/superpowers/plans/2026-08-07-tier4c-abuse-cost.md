# Tier-4C Abuse & Cost Controls Implementation Plan

> SUB-SKILL: subagent-driven (synchronous). Design: `docs/superpowers/specs/2026-08-07-tier4c-abuse-cost-design.md`.

**Goal:** DB-back the racy daily song cap + throttle the unmetered LLM draft/regen endpoints, via one `rate_events` primitive.

**Verification env:** clean-env pytest. Baseline **875 passed, 0 failed**:
```
env -u ANTHROPIC_API_KEY -u GROQ_API_KEY -u FACELESS_API_TOKEN -u KIE_API_KEY \
    -u ELEVENLABS_API_KEY -u SUPABASE_URL -u SUPABASE_SERVICE_ROLE_KEY \
    -u STRIPE_SECRET_KEY -u STRIPE_WEBHOOK_SECRET uv run pytest -q
```

---

## Task C1 — rate_events table + db helpers (TDD)
**Files:** `supabase/migrations/20260807000002_rate_events.sql`, `pipeline/db.py`, `tests/test_db.py`.
- [ ] Migration per the spec (table + index).
- [ ] Tests: `record_rate_event(user_id, action)` inserts `{user_id, action}` into `rate_events`; `count_rate_events(user_id, action, within_seconds)` filters by user_id+action+created_at≥cutoff and returns the count. Use the `fake_client`/`_FakeQuery` pattern (extend `_FakeQuery` with a `count` attr / `.gte()` recorder if needed — mirror existing).
- [ ] Implement `record_rate_event` + `count_rate_events` per the spec (use `count="exact"` → `resp.count`, falling back to `len(resp.data or [])` if the installed supabase-py doesn't set `.count`; verify which by reading how `get_balance`/`list_transactions` read responses).
- [ ] Clean-env suite green. Commit: `feat(abuse): rate_events table + record/count helpers`.

## Task C2 — daily song cap → DB + LLM throttle (TDD)
**Files:** `pipeline/api.py`; tests `tests/test_api.py` (or `test_legal.py`).
- [ ] **Daily cap → DB:** rewrite `_enforce_daily_song_limit(user)` to use `count_rate_events(user.id, "song_approve", 86400) >= _SONG_DAILY_LIMIT` (429, same message); replace the `_record_song_approval(user)` call site with `record_rate_event(user.id, "song_approve")`. Remove the now-dead `_load_rate_log`/`_record_song_approval`/`_rate_limit_path` (grep to confirm no other callers). Service bypass unchanged.
- [ ] **LLM throttle:** add `_LLM_HOURLY_LIMIT` + `_enforce_llm_rate_limit(user)` (service bypass; 429 `{"code":"llm_rate_limited"}` when `count_rate_events(user.id,"llm_call",3600) >= _LLM_HOURLY_LIMIT`, else `record_rate_event(user.id,"llm_call")`). Call it at the top of the LLM draft/regen handlers — `create_song`, and the `regenerate-lyrics` + `regenerate-cover-prompt` endpoints (`git grep -n '@app.post.*regenerate' pipeline/api.py`) — placed AFTER the existing `_require_terms_accepted`/`_require_email_confirmed` lines. Do NOT throttle the morning-draft generator (internal, day-idempotent).
- [ ] Tests: daily cap 429 when count ≥ limit (monkeypatch `count_rate_events`), passes under, service bypass; LLM endpoint 429 `llm_rate_limited` when over, records under, service bypass.
- [ ] Clean-env suite green (report count). Commit: `feat(abuse): DB-backed daily cap + LLM draft/regen throttle`.

## Task C3 — verify + handoff
- [ ] Full clean-env suite → 0 failed. Append a Tier-4C note to `docs/GO-LIVE-READINESS.md` (apply `20260807000002_rate_events.sql` before deploy; daily cap now cross-instance-correct; LLM endpoints throttled at FACELESS_LLM_HOURLY_LIMIT/hour). Commit.
