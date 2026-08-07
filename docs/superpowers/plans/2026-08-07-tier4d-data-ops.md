# Tier-4D Data & Ops Hygiene — Design + Plan

**Date:** 2026-08-07 · **Status:** approved to proceed (user: "complete the Tier-4"). Final Tier-4 sub-project. D is ops-heavy, so this is a combined lean design+plan: code the safe high-value bits, operator-script + hand off the pure-infra items.

## Context (verified 2026-08-07)
- `/healthz` (`healthz()` in `pipeline/api.py`) returns `{"ok": true}` — no writer-tier visibility. `_build_llm()` picks the writer provider by env key order (ANTHROPIC → GEMINI → GROQ) and records runtime fallbacks to `_out_root()/"llm_fallback.json"`. Anthropic-out-of-credits → silent Gemini fallback is invisible today.
- CORS: `allow_origins=["*"]` (hardcoded, `pipeline/api.py:747`). Header-token auth is the real gate, so `*` is low-risk — but hardcoded/unconfigurable.
- `dart analyze lib/main.dart` → **No issues found** (the CLAUDE.md note about `main.dart:31/:105` invalid Dart is **stale** — resolved).
- Retention: a 30-day lazy cleanup of stale FAILED runs exists (`api.py:3462`); COMPLETED artifacts + uploaded reference audio persist indefinitely.

## Scope

### D1 — `writer_tier` in `/healthz` (code)
Add to the `/healthz` (and `/health`) JSON: `writer_tier` = top *configured* provider (`"anthropic"` if `ANTHROPIC_API_KEY` else `"gemini"` if `GEMINI_API_KEY` else `"groq"` else `"none"`), and `writer_degraded: bool` = `(_out_root()/"llm_fallback.json").exists()` (a runtime Anthropic→lower fallback was recorded). Keep `ok: true`. A tiny `_writer_tier_status() -> dict` helper; no new deps, no auth change (healthz is public).

### D2 — CORS env-configurable (code, default `*` — no behavior change)
Replace the hardcoded `allow_origins=["*"]` with `allow_origins=[o.strip() for o in os.environ.get("FACELESS_CORS_ORIGINS", "*").split(",") if o.strip()]`. Default stays `["*"]` (nothing breaks); an operator can restrict to `https://faceless-lab.com,https://app.faceless-lab.com` via the env var. Resolves the "hardcoded/stale justification" finding without breakage risk.

### D3 — Data retention (operator script + handoff)
New `scripts/setup-gcs-lifecycle.sh`: apply a GCS bucket **lifecycle rule** deleting objects older than `RETENTION_DAYS` (default 90) under the runs bucket (`gcloud storage buckets update <bucket> --lifecycle-file=<tmp json>` / `gsutil lifecycle set`). Idempotent (writes the full lifecycle each run). Operator-run (needs the bucket name + gcloud auth). This is the durable retention mechanism; the in-app 30d failed-run cleanup stays.

### D4 — Deploy-hygiene handoff (doc)
Append a Tier-4D note to `docs/GO-LIVE-READINESS.md`: writer_tier now visible in /healthz; CORS configurable via `FACELESS_CORS_ORIGINS`; `flutter analyze`/main.dart resolved (mark the CLAUDE.md note stale); run `scripts/setup-gcs-lifecycle.sh` for retention; **still operator-owned:** CI/CD pipeline, single-region (`us-central1`) redundancy, a documented rollback procedure (`gcloud run services update-traffic --to-revisions=<prev>=100`).

---

## Tasks

### Task D1 — writer_tier + CORS env (TDD)
**Files:** `pipeline/api.py`; tests `tests/test_api.py`.
- [ ] Tests: `/healthz` JSON includes `writer_tier` (`"anthropic"` when `ANTHROPIC_API_KEY` set via monkeypatch.setenv; `"none"` when no LLM keys) and `writer_degraded` (True when a `llm_fallback.json` exists under the out-root, else False). CORS: `allow_origins` reflects `FACELESS_CORS_ORIGINS` when set (assert via the app's CORS middleware config or a helper `_cors_origins()`), defaults to `["*"]` when unset.
- [ ] Implement `_writer_tier_status()` + include it in `healthz()`; a `_cors_origins()` helper feeding `CORSMiddleware(allow_origins=_cors_origins())`.
- [ ] Clean-env suite green (report count). Commit: `feat(ops): writer_tier in /healthz + env-configurable CORS`.

### Task D2 — GCS-lifecycle operator script
**Files:** `scripts/setup-gcs-lifecycle.sh` (new).
- [ ] Write the script (inputs `GCS_BUCKET` or discover, `RETENTION_DAYS` default 90; applies a delete-older-than lifecycle; prints verify command; `set -euo pipefail`; documents it does NOT touch the DB ledger). `bash -n`. `chmod +x`.
- [ ] Commit: `feat(ops): GCS lifecycle retention setup script`.

### Task D3 — verify + handoff
- [ ] Full clean-env suite → 0 failed (report count). `dart analyze lib/main.dart` → 0. `bash -n scripts/setup-gcs-lifecycle.sh`.
- [ ] Append the Tier-4D note to `docs/GO-LIVE-READINESS.md` per D4 above. Commit: `docs: tier-4D data/ops handoff (+ Tier-4 complete)`.
