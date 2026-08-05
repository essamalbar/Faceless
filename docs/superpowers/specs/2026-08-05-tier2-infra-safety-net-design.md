# Tier-2 Infra Safety Net — Design

**Date:** 2026-08-05
**Status:** approved (brainstorm) — pending spec review → implementation plan
**Scope:** Close the Tier-2 "can't-operate-blind" go-live blockers (`docs/GO-LIVE-READINESS.md` items 6/7/8): no monitoring/alerting/error-tracking, no infra spend ceiling, no ledger backup. Decisions: **GCP-native** observability (no external SaaS); deliver **code + gcloud scripts + an operator checklist** for console-only steps.

## Context (verified against code, 2026-08-05)

- `deploy/cloud-run-service.yaml`: `containerConcurrency: 80`, `timeoutSeconds: 60`, cpu 1 / 1Gi, `run.googleapis.com/cpu-throttling: "true"` — **no `maxScale`** (→ Cloud Run default 100 instances).
- `deploy/cloud-run-job.yaml`: cpu 2 / 4Gi, `timeoutSeconds: 3600`.
- Observability: **none** — grep for sentry/structured-logging/error-reporting/metrics is empty. All `print()` / per-run `RunLog` file.
- Spend controls that DO exist: per-run `max_spend_usd` + `BudgetExceededError` (`pipeline/video.py`), the per-user Supabase credit ledger, and the approve-before-spend gate. **Missing:** any global/daily ceiling, a GCP billing budget, a Kie account cap.

Cloud Run ingests container **stdout/stderr into Cloud Logging automatically**, and Cloud **Error Reporting** auto-groups log entries that have `severity=ERROR` and a stack trace in the payload — so GCP-native observability needs **no external SDK**, only correctly-shaped JSON logs.

## Architecture (four components, one plan)

### A. Observability — `pipeline/observability.py` (new) + wiring

A small stdlib-only module (no new deps). All Python files start with `from __future__ import annotations`.

- **`setup_logging(level: int = logging.INFO) -> None`** — idempotent (guarded by a module flag so repeated calls don't stack handlers). Attaches ONE `StreamHandler(sys.stdout)` to the root logger with a `JsonFormatter`. Safe to call at both API startup and worker start.
- **`JsonFormatter(logging.Formatter)`** — emits a single-line JSON object per record with the keys Cloud Logging recognizes:
  - `severity`: mapped from the record level (`DEBUG`→DEBUG, `INFO`→INFO, `WARNING`→WARNING, `ERROR`→ERROR, `CRITICAL`→CRITICAL).
  - `message`: the formatted message; when the record has exception info, the **full traceback is appended to `message`** (so Error Reporting detects + groups it).
  - `time`: ISO-8601 (from the record; note: must not rely on wall-clock in tests — use the record's `created`).
  - any structured context passed via `extra={...}` is merged as top-level keys (skipping the reserved LogRecord attributes).
- **`log_exception(exc: BaseException, *, where: str, **ctx) -> None`** — logs at `ERROR` with `exc_info=exc` and `extra={"where": where, **ctx}`, so the traceback lands in `message` and the context (e.g. request path, run_id, user_id) is queryable in Cloud Logging.
- **`get_logger(name: str) -> logging.Logger`** — thin `logging.getLogger` convenience.

**Wiring:**
- `pipeline/api.py`:
  - call `setup_logging()` at module import / app startup.
  - register a catch-all `@app.exception_handler(Exception)` that calls `log_exception(exc, where="api", path=request.url.path, method=request.method)` and returns `JSONResponse(500, {"detail": "internal error"})`. FastAPI routes `HTTPException`/`RequestValidationError` to their own handlers, so this fires **only for genuinely-unhandled 5xx** — existing 402/404/409 behavior is untouched.
  - route the existing billing-relevant failure logs (Stripe webhook failures, the `refund_run_charges failed` `logging.exception` in `cancel_run`/`cancel_song`) through the structured logger at ERROR with context. (Several already call `logging.exception(...)`; once root logging is JSON-configured these emit structured entries — verify they carry enough context.)
- `run.py`:
  - call `setup_logging()` early in `main_with_args`.
  - route the worker's terminal `FAILED` log and the `[billing] WARNING` unbilled-fallback in `_effective_user_id` through the structured logger at ERROR / WARNING (in addition to the existing per-run `RunLog` file), so they surface in Cloud Logging / Error Reporting.

**Scoped deliberately:** only the error + billing-anomaly signals are converted — NOT a wholesale `print()`→logger migration (that's a follow-up, and the per-run `RunLog` file stays).

### B. Cost ceilings

- **`deploy/cloud-run-service.yaml`** — add `autoscaling.knative.dev/maxScale: "4"` to the template metadata annotations (alongside `cpu-throttling`). Rationale: the API is I/O-light and its job is to spawn Cloud Run **Jobs**, where the actual (already credit-gated) rendering runs; 4 instances is ample for a solo product and caps runaway scale-out from the default 100.
- **`scripts/setup-billing-budget.sh`** (new) — re-runnable. Inputs via env/args: `GCP_PROJECT_ID`, `GCP_BILLING_ACCOUNT_ID` (or auto-discover via `gcloud billing accounts list`), `BUDGET_USD` (default `50`), `ALERT_EMAIL`. Creates a project-scoped budget named `faceless-monthly` with 50% / 90% / 100% threshold email alerts (`gcloud billing budgets create ... --budget-amount=<USD>USD --threshold-rule=percent=0.5 ...`). Idempotent: `gcloud billing budgets list` by display-name → update instead of duplicate. **Documents the GCP limitation:** budgets alert, they do NOT hard-stop spend.
- Verify (note in the plan, not a code change): the Job's retry behavior — confirm `cloud-run-job.yaml` doesn't allow cost-amplifying retries beyond intent.

### C. Alerting — `scripts/setup-monitoring-alerts.sh` (new)

Re-runnable `gcloud monitoring` script. Inputs: `GCP_PROJECT_ID`, `ALERT_EMAIL`, service name (`faceless-api`), job name (`faceless-pipeline`).
1. Ensure an **email notification channel** (`gcloud monitoring channels create --type=email --channel-labels=email_address=$ALERT_EMAIL`); reuse if one with that email exists; capture its id.
2. **Alert policy — API 5xx**: on `run.googleapis.com/request_count` filtered to the service with `response_code_class="5xx"`, condition = rate above a small threshold over a 5-minute window.
3. **Alert policy — Job failures**: on `run.googleapis.com/job/completed_execution_count` filtered `result="failed"` for the job (or a log-based alert on the job's error logs), condition = any failure.
4. **Alert policy — billing anomaly**: create a **log-based metric** counting entries matching `[billing] WARNING` (unbilled-render fallback) OR `REFUND FAILED`, then an alert policy firing when its count > 0.

Policies are applied from generated temp policy JSON files (`gcloud monitoring policies create --policy-from-file=...`), idempotent by display-name (list → skip/update). All temp files written under the OS temp dir and cleaned up.

### D. Operator checklist — `docs/TIER2-INFRA.md` (new)

A runbook for what code can't do:
1. Redeploy so `maxScale` takes effect (`scripts/build-and-push.sh`).
2. Run `scripts/setup-billing-budget.sh` (with args); verify the budget + thresholds in the Billing console.
3. Run `scripts/setup-monitoring-alerts.sh` (with args); verify the channel + 3 policies in Monitoring.
4. **Supabase**: enable PITR (paid tier) or scheduled daily backups (Dashboard → Database → Backups); record the retention window. The credit/payment ledger is the financial system of record.
5. **Kie.ai**: set an account-level spend cap / keep a bounded prepaid balance with auto-recharge OFF (console); record the cap.
6. **Verify alerts fire**: force a test 5xx, a failed Job, and emit a `[billing] WARNING`; confirm each alert emails and the 5xx appears in Error Reporting.

## Testing

- **`tests/test_observability.py`** (new, mocked — no real logging backend, no external calls):
  - `JsonFormatter` produces valid single-line JSON with the correct `severity` for each level.
  - a record with exception info includes the traceback text in `message`.
  - `extra={...}` context appears as top-level JSON keys; reserved LogRecord attrs are not leaked.
  - `setup_logging()` is idempotent — calling twice does not add a second handler.
  - `log_exception(exc, where=..., **ctx)` emits one ERROR record carrying the traceback + context (assert via `caplog` / a capturing handler).
- **API exception-handler test** (in `tests/test_api.py`): a temporary route (or an existing endpoint monkeypatched to raise a non-HTTP exception) returns 500 and produces one ERROR log with the request path. Must not alter existing HTTPException status codes (a 402/404/409 test still passes).
- **Shell scripts**: `bash -n` syntax check in CI/local + reviewed by reading (operator-applied, like the migrations — not unit-tested against real gcloud).
- **maxScale**: a lightweight test asserting the annotation is present in `deploy/cloud-run-service.yaml` (guards against a silent revert), plus reading.
- **Baseline**: the clean-env suite is currently **825 passed, 0 failed** (`env -u <all API-key vars> uv run pytest -q`). No new failures; new tests pass. `flutter` is untouched.

## Out of scope / deferred (tracked in GO-LIVE-READINESS.md)

- A code-level **global/daily spend ceiling** — the per-user ledger + per-run cap + GCP budget + Kie account cap already bound spend from four angles; revisit only if those prove insufficient.
- A full `print()`→structured-logger migration (only error/billing paths converted now).
- **Sentry** / any external error SaaS.
- Cloud Run Job parallelism/concurrency tuning beyond confirming retry cost.
- Tier 3 legal (ToS/Privacy/DMCA/GDPR) — separate workstream.

## Key invariants respected

- External services are **mocked in tests** — observability tests use a capturing log handler; scripts are operator-run, never invoked in tests.
- All new Python files start with `from __future__ import annotations`; `pathlib.Path` for paths; absolute imports from the package root.
- Scripts are re-runnable/idempotent, matching `scripts/setup-cloud-run.sh` conventions.
