# Tier-2 Infra Safety Net Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the operator eyes and cost brakes before charging real users — GCP-native error/log visibility, a Cloud Run scale cap, a billing budget, monitoring alerts, and an operator runbook for the console-only pieces.

**Architecture:** A stdlib-only `pipeline/observability.py` emits JSON logs to stdout (Cloud Run → Cloud Logging; ERROR + traceback → Cloud Error Reporting). The FastAPI app gets a catch-all 5xx handler; the worker routes its FAILED + billing-anomaly signals through the same logger. `maxScale` caps the service. Two re-runnable `gcloud` scripts create the billing budget and alert policies. A `docs/TIER2-INFRA.md` runbook covers Supabase PITR + Kie account cap.

**Tech Stack:** Python stdlib `logging`/`json`, FastAPI exception handler, Cloud Run YAML, `gcloud` (billing/monitoring), bash.

**Verification env (IMPORTANT):** run pytest in a CLEAN env — sourcing `.env` flips the failing set. Baseline is **825 passed, 0 failed**:
```
env -u ANTHROPIC_API_KEY -u GROQ_API_KEY -u FACELESS_API_TOKEN -u KIE_API_KEY \
    -u ELEVENLABS_API_KEY -u SUPABASE_URL -u SUPABASE_SERVICE_ROLE_KEY \
    -u STRIPE_SECRET_KEY -u STRIPE_WEBHOOK_SECRET uv run pytest -q
```

---

## File Structure

- **Create** `pipeline/observability.py` — `JsonFormatter`, `setup_logging`, `log_exception`, `get_logger`. Single responsibility: turn Python logging into Cloud-Logging-shaped JSON on stdout.
- **Create** `tests/test_observability.py` — unit tests for the above (capturing handler; no real backend).
- **Modify** `pipeline/api.py` — `setup_logging()` at startup + catch-all `Exception` handler; route billing failure logs.
- **Modify** `tests/test_api.py` — exception-handler test.
- **Modify** `run.py` — `setup_logging()` first thing in `main_with_args`; route the terminal FAILED log + the `[billing]` unbilled-fallback through the structured logger.
- **Modify** `tests/test_run_charging.py` — update the billing-warning test from capsys(stderr) to caplog (logger).
- **Modify** `deploy/cloud-run-service.yaml` — add `maxScale`.
- **Create** `tests/test_deploy_config.py` — guard the `maxScale` annotation.
- **Create** `scripts/setup-billing-budget.sh` — gcloud billing budget (idempotent).
- **Create** `scripts/setup-monitoring-alerts.sh` — gcloud monitoring channel + 3 alert policies (idempotent).
- **Create** `docs/TIER2-INFRA.md` — operator runbook.
- **Modify** `docs/GO-LIVE-READINESS.md` — point Tier-2 rows at the runbook + mark code pieces done.

---

## Task 1: Observability module (`pipeline/observability.py`)

**Files:**
- Create: `pipeline/observability.py`
- Test: `tests/test_observability.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_observability.py
from __future__ import annotations

import json
import logging

import pipeline.observability as obs


def _format(record: logging.LogRecord) -> dict:
    return json.loads(obs.JsonFormatter().format(record))


def test_formatter_emits_severity_and_message():
    rec = logging.LogRecord("t", logging.WARNING, __file__, 1, "hello %s", ("world",), None)
    out = _format(rec)
    assert out["severity"] == "WARNING"
    assert out["message"] == "hello world"
    assert out["logger"] == "t"


def test_formatter_maps_each_level():
    for level, name in [(logging.DEBUG, "DEBUG"), (logging.INFO, "INFO"),
                        (logging.WARNING, "WARNING"), (logging.ERROR, "ERROR"),
                        (logging.CRITICAL, "CRITICAL")]:
        rec = logging.LogRecord("t", level, __file__, 1, "m", (), None)
        assert _format(rec)["severity"] == name


def test_formatter_includes_traceback_on_exception():
    try:
        raise ValueError("boom")
    except ValueError:
        import sys
        rec = logging.LogRecord("t", logging.ERROR, __file__, 1, "failed", (), sys.exc_info())
    out = _format(rec)
    assert "Traceback" in out["message"] and "ValueError: boom" in out["message"]


def test_formatter_merges_extra_context_and_hides_reserved():
    rec = logging.LogRecord("t", logging.ERROR, __file__, 1, "m", (), None)
    rec.run_id = "r1"          # simulates extra={"run_id": "r1"}
    rec.user_id = "u1"
    out = _format(rec)
    assert out["run_id"] == "r1" and out["user_id"] == "u1"
    # reserved LogRecord internals must not leak
    assert "args" not in out and "levelno" not in out and "msg" not in out


def test_formatter_is_valid_single_line_json():
    rec = logging.LogRecord("t", logging.INFO, __file__, 1, "line1\nline2", (), None)
    s = obs.JsonFormatter().format(rec)
    assert "\n" not in s.rstrip("\n").replace("\\n", "")  # newlines only inside JSON strings
    json.loads(s)  # parses


def test_setup_logging_idempotent():
    root = logging.getLogger()
    saved, saved_flag = root.handlers[:], obs._CONFIGURED
    try:
        root.handlers.clear()
        obs._CONFIGURED = False
        obs.setup_logging()
        first = len(root.handlers)
        obs.setup_logging()
        assert first == 1 and len(root.handlers) == 1
        assert isinstance(root.handlers[0].formatter, obs.JsonFormatter)
    finally:
        root.handlers[:] = saved
        obs._CONFIGURED = saved_flag


def test_log_exception_emits_error_with_context(caplog):
    with caplog.at_level(logging.ERROR):
        try:
            raise RuntimeError("kaboom")
        except RuntimeError as e:
            obs.log_exception(e, where="unit", run_id="r9")
    rec = [r for r in caplog.records if r.levelno == logging.ERROR][-1]
    assert getattr(rec, "where") == "unit" and getattr(rec, "run_id") == "r9"
    assert rec.exc_info is not None  # traceback attached
```

- [ ] **Step 2: Run — verify fail** (`ModuleNotFoundError`/attribute errors).

Run: `uv run pytest tests/test_observability.py -q` → FAIL.

- [ ] **Step 3: Implement `pipeline/observability.py`**

```python
"""GCP-native structured logging.

Cloud Run ingests container stdout into Cloud Logging; a log entry with
`severity=ERROR` and a stack trace in its payload is auto-grouped by Cloud
Error Reporting. So we need no external SDK — only correctly-shaped JSON on
stdout. stdlib only.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone

_CONFIGURED = False
_LOGGER_NAME = "faceless"

# Standard LogRecord attribute names — never leak these as "context".
_RESERVED = set(vars(logging.makeLogRecord({})).keys()) | {"message", "asctime", "taskName"}


class JsonFormatter(logging.Formatter):
    """One JSON object per line: severity + message (+ full traceback on
    exceptions so Error Reporting groups it) + any extra={...} as top-level
    keys."""

    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage()
        if record.exc_info:
            message = f"{message}\n{self.formatException(record.exc_info)}".strip()
        elif record.exc_text:
            message = f"{message}\n{record.exc_text}".strip()
        payload: dict = {
            "severity": record.levelname,   # Cloud Logging recognizes DEBUG/INFO/WARNING/ERROR/CRITICAL
            "message": message,
            "time": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "logger": record.name,
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging(level: int = logging.INFO) -> None:
    """Idempotent: configure the root logger to emit JSON to stdout exactly
    once. Safe to call from both the API and the worker."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()      # drop any default/basicConfig handler (avoid double logging)
    root.addHandler(handler)
    root.setLevel(level)
    _CONFIGURED = True


def get_logger(name: str = _LOGGER_NAME) -> logging.Logger:
    return logging.getLogger(name)


def log_exception(exc: BaseException, *, where: str, **ctx) -> None:
    """Log an exception at ERROR with its traceback + structured context.
    `ctx` keys must not collide with stdlib LogRecord attributes."""
    get_logger().error("unhandled %s", type(exc).__name__,
                        exc_info=exc, extra={"where": where, **ctx})
```

- [ ] **Step 4: Run — verify pass**

Run: `uv run pytest tests/test_observability.py -q` → PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add pipeline/observability.py tests/test_observability.py
git commit -m "$(cat <<'EOF'
feat(obs): stdlib JSON logging for Cloud Logging / Error Reporting

pipeline/observability.py: JsonFormatter (severity + traceback + extra
context), idempotent setup_logging(stdout), log_exception helper. No external
SDK — Cloud Run stdout -> Cloud Logging, ERROR+traceback -> Error Reporting.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Wire observability into the API (`pipeline/api.py`)

**Files:**
- Modify: `pipeline/api.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write the failing test** (add to `tests/test_api.py`)

```python
def test_unhandled_exception_returns_500_and_is_logged(monkeypatch):
    from fastapi.testclient import TestClient
    from pipeline import api as api_mod

    calls: list[dict] = []
    monkeypatch.setattr(api_mod, "log_exception",
                        lambda exc, **ctx: calls.append(ctx))

    @api_mod.app.get("/__boom_test")
    def _boom():  # pragma: no cover - body raises
        raise RuntimeError("boom")

    try:
        c = TestClient(api_mod.app, raise_server_exceptions=False)
        r = c.get("/__boom_test")
        assert r.status_code == 500
        assert r.json() == {"detail": "internal error"}
        assert calls and calls[0].get("where") == "api"
        assert "/__boom_test" in calls[0].get("path", "")
    finally:
        api_mod.app.router.routes[:] = [
            rt for rt in api_mod.app.router.routes
            if getattr(rt, "path", None) != "/__boom_test"
        ]
```

- [ ] **Step 2: Run — verify fail**

Run: `uv run pytest tests/test_api.py::test_unhandled_exception_returns_500_and_is_logged -q`
Expected: FAIL — no `log_exception` attr on the module and/or the exception propagates (no handler).

- [ ] **Step 3: Implement**

In `pipeline/api.py`, near the top imports add:
```python
from pipeline.observability import setup_logging, log_exception, get_logger
```
(Confirm `from fastapi import Request` and `from fastapi.responses import JSONResponse` are importable — they're already used in the module; if `Request` is not imported, add it.)

Immediately after the `app = FastAPI(...)` construction, add:
```python
setup_logging()


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception):
    # Catch-all for genuinely-unhandled 5xx. FastAPI routes HTTPException /
    # RequestValidationError to their own handlers, so 402/404/409/422 are
    # unaffected — this only fires for real server errors, making them visible
    # in Cloud Error Reporting instead of a bare stack trace.
    log_exception(exc, where="api", path=request.url.path, method=request.method)
    return JSONResponse(status_code=500, content={"detail": "internal error"})
```

Then route the two billing failure logs through the structured logger. In BOTH `cancel_run` and `cancel_song`, the refund `except` block is currently bare (`except Exception:` + `import logging` + `logging.exception(...)`). Bind the exception and replace the body so it emits a **`[billing]`-tokened ERROR** (the alert log-based metric in Task 6 matches `[billing]` / `REFUND FAILED`, so a generic `log_exception` "unhandled …" message would NOT be caught — keep the token):
```python
    except Exception as _e:
        # Refund failure is a billing anomaly — surface it (the alert metric
        # matches "[billing]"). Must still NOT fail the cancel itself.
        get_logger().error("[billing] refund failed during cancel",
                            exc_info=_e, extra={"where": "cancel", "run_id": run_id})
```
Add `get_logger` to the observability import (`from pipeline.observability import setup_logging, log_exception, get_logger`). Keep the surrounding try/except semantics — the refund failure must still NOT fail the cancel.

- [ ] **Step 4: Run — verify pass + no regression on HTTPException codes**

```bash
uv run pytest tests/test_api.py::test_unhandled_exception_returns_500_and_is_logged \
  tests/test_api.py -k "cancel or plan or approve" -q
```
Expected: PASS; existing 402/404/409 assertions unchanged.

- [ ] **Step 5: Commit**

```bash
git add pipeline/api.py tests/test_api.py
git commit -m "$(cat <<'EOF'
feat(obs): API 5xx catch-all handler + structured logging startup

setup_logging() at startup; @app.exception_handler(Exception) logs unhandled
errors (path/method) via log_exception and returns a clean 500 — surfaces
5xx in Cloud Error Reporting. HTTPException handling untouched. Route the
cancel refund-failure logs through log_exception.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Wire observability into the worker (`run.py`)

**Files:**
- Modify: `run.py`
- Test: `tests/test_run_charging.py`

- [ ] **Step 1: Update the existing billing-warning test to expect a log record** (replace `test_effective_user_id_warns_loudly_on_divergence` and `test_effective_user_id_legit_admin_run_stays_quiet` in `tests/test_run_charging.py`)

```python
def test_effective_user_id_warns_loudly_on_divergence(tmp_path, caplog):
    import logging
    with caplog.at_level(logging.WARNING):
        assert run._effective_user_id(tmp_path / "x" / "y", tmp_path / "other") == "admin"
    hits = [r for r in caplog.records
            if r.levelno == logging.WARNING and "[billing]" in r.getMessage()]
    assert hits, "unbilled-fallback must log a [billing] WARNING"
    assert "will NOT be" in hits[-1].getMessage()


def test_effective_user_id_legit_admin_run_stays_quiet(tmp_path, caplog):
    import logging
    out = tmp_path / "out"
    with caplog.at_level(logging.WARNING):
        assert run._effective_user_id(out / "admin" / "2026-08-04-1200", out) == "admin"
    assert not [r for r in caplog.records if "[billing]" in r.getMessage()]
```

- [ ] **Step 2: Run — verify fail** (`run.py` still `print`s to stderr, so caplog sees no record).

Run: `uv run pytest tests/test_run_charging.py -q` → the two updated tests FAIL.

- [ ] **Step 3: Implement**

In `run.py` top-level imports add:
```python
from pipeline.observability import setup_logging, get_logger
```
As the FIRST statement inside `main_with_args(argv)` (before `_resolve_out_root` / `_effective_user_id`):
```python
    setup_logging()
```
Replace the `print(...[billing] WARNING...file=sys.stderr)` block in `_effective_user_id` with a logger call (keep the `[billing]` token stable — the alert log-based metric matches it):
```python
        get_logger().warning(
            "[billing] could not derive run owner from run_dir=%s under "
            "out_root=%s (%s: %s); falling back to 'admin' (service/free) — this "
            "render will NOT be billed. Verify FACELESS_OUT_ROOT matches between "
            "the API and the worker.",
            run_dir, out_root, type(e).__name__, e,
        )
```
Also route the worker's terminal FAILED log (in `main_with_args`'s outer `except Exception as exc`) so it emits at ERROR with a traceback in addition to the per-run `RunLog`:
```python
    except Exception as exc:
        log.error(f"FAILED: {type(exc).__name__}: {exc}")
        get_logger().error("run failed", exc_info=exc, extra={"where": "worker"})
        return 1
```
(Keep the existing `log.error(...)` RunLog line — the new line adds Cloud Logging / Error Reporting visibility. `get_logger`/`log_exception` both fine; using `get_logger().error(..., exc_info=exc)` keeps it one import.)

Note: `_effective_user_id` may be called before `setup_logging()` in a fresh run path? No — it is only called inside `main_with_args`, after the `setup_logging()` first-line call. Python logging also has a lastResort handler, so even an un-setup logger still surfaces the warning; tests use `caplog` which captures regardless.

- [ ] **Step 4: Run — verify pass**

```bash
uv run pytest tests/test_run_charging.py tests/test_run_shorts_smoke.py -q
```
Expected: PASS (billing-warning tests now green; shorts smoke unaffected).

- [ ] **Step 5: Commit**

```bash
git add run.py tests/test_run_charging.py
git commit -m "$(cat <<'EOF'
feat(obs): worker structured logging for FAILED + unbilled-fallback

setup_logging() at main_with_args start; the [billing] unbilled-fallback and
the terminal FAILED now emit structured ERROR/WARNING (with traceback) to
Cloud Logging / Error Reporting, not just the per-run RunLog file. Tests
assert via caplog. [billing] token kept stable for the alert metric.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Cloud Run `maxScale` (`deploy/cloud-run-service.yaml`)

**Files:**
- Modify: `deploy/cloud-run-service.yaml`
- Test: `tests/test_deploy_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_deploy_config.py
from __future__ import annotations

from pathlib import Path

_SVC = Path(__file__).parent.parent / "deploy" / "cloud-run-service.yaml"


def test_service_sets_max_scale():
    """Runaway-cost guard: the service must cap autoscaling (default is 100)."""
    text = _SVC.read_text(encoding="utf-8")
    assert "autoscaling.knative.dev/maxScale" in text, "maxScale annotation missing"
    # extract the value and assert it's a small, sane cap
    import re
    m = re.search(r'autoscaling\.knative\.dev/maxScale:\s*"?(\d+)"?', text)
    assert m and 1 <= int(m.group(1)) <= 10, f"maxScale should be a small cap, got {m and m.group(1)}"
```

- [ ] **Step 2: Run — verify fail** (`uv run pytest tests/test_deploy_config.py -q`).

- [ ] **Step 3: Implement** — in `deploy/cloud-run-service.yaml`, in the template metadata `annotations:` block (where `run.googleapis.com/cpu-throttling: "true"` lives), add:
```yaml
        autoscaling.knative.dev/maxScale: "4"
```

- [ ] **Step 4: Run — verify pass** (`uv run pytest tests/test_deploy_config.py -q`).

- [ ] **Step 5: Commit**

```bash
git add deploy/cloud-run-service.yaml tests/test_deploy_config.py
git commit -m "$(cat <<'EOF'
fix(infra): cap Cloud Run service autoscaling (maxScale=4)

The API service had no maxScale (Cloud Run default 100). The API is I/O-light
and spawns credit-gated Cloud Run Jobs for the actual render, so 4 instances
is ample and caps runaway scale-out cost. Guard test asserts the annotation.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Billing-budget script (`scripts/setup-billing-budget.sh`)

**Files:**
- Create: `scripts/setup-billing-budget.sh`

No unit test (operator-applied gcloud). Validate with `bash -n` and review-by-reading. Model the flag/style conventions on `scripts/setup-cloud-run.sh`.

- [ ] **Step 1: Write the script**

```bash
#!/usr/bin/env bash
# Create/update a GCP billing budget for the faceless project with threshold
# email alerts. Re-runnable (idempotent by display-name).
#
# NOTE: A GCP budget ALERTS on spend thresholds; it does NOT hard-stop billing.
# Pair it with the Cloud Run maxScale cap and the Kie account cap (see
# docs/TIER2-INFRA.md).
#
# Usage:
#   GCP_PROJECT_ID=... ALERT_EMAIL=you@example.com BUDGET_USD=50 \
#     ./scripts/setup-billing-budget.sh
set -euo pipefail

: "${GCP_PROJECT_ID:?set GCP_PROJECT_ID}"
: "${ALERT_EMAIL:?set ALERT_EMAIL}"
BUDGET_USD="${BUDGET_USD:-50}"
DISPLAY_NAME="faceless-monthly"

BILLING_ACCOUNT_ID="${GCP_BILLING_ACCOUNT_ID:-}"
if [[ -z "${BILLING_ACCOUNT_ID}" ]]; then
  BILLING_ACCOUNT_ID="$(gcloud beta billing projects describe "${GCP_PROJECT_ID}" \
    --format='value(billingAccountName)' | sed 's#billingAccounts/##')"
fi
: "${BILLING_ACCOUNT_ID:?could not resolve billing account; set GCP_BILLING_ACCOUNT_ID}"

echo "Billing account: ${BILLING_ACCOUNT_ID}  project: ${GCP_PROJECT_ID}  cap: \$${BUDGET_USD}/mo"

EXISTING="$(gcloud billing budgets list --billing-account="${BILLING_ACCOUNT_ID}" \
  --filter="displayName=${DISPLAY_NAME}" --format='value(name)' 2>/dev/null | head -n1 || true)"

COMMON_ARGS=(
  --display-name="${DISPLAY_NAME}"
  --budget-amount="${BUDGET_USD}USD"
  --filter-projects="projects/${GCP_PROJECT_ID}"
  --threshold-rule=percent=0.5
  --threshold-rule=percent=0.9
  --threshold-rule=percent=1.0
)

if [[ -n "${EXISTING}" ]]; then
  echo "Updating existing budget: ${EXISTING}"
  gcloud billing budgets update "${EXISTING}" \
    --billing-account="${BILLING_ACCOUNT_ID}" "${COMMON_ARGS[@]}"
else
  echo "Creating budget ${DISPLAY_NAME}"
  gcloud billing budgets create \
    --billing-account="${BILLING_ACCOUNT_ID}" "${COMMON_ARGS[@]}"
fi

echo "Done. Verify in Console > Billing > Budgets & alerts."
echo "Threshold emails go to the billing account's Billing Admins by default;"
echo "to also email ${ALERT_EMAIL}, add it as a Billing Account User or wire a"
echo "Pub/Sub topic (see docs/TIER2-INFRA.md)."
```

- [ ] **Step 2: Syntax check + perms**

```bash
bash -n scripts/setup-billing-budget.sh
chmod +x scripts/setup-billing-budget.sh
```
Expected: no output (valid).

- [ ] **Step 3: Commit**

```bash
git add scripts/setup-billing-budget.sh
git commit -m "$(cat <<'EOF'
feat(infra): re-runnable GCP billing-budget setup script

gcloud billing budget for the project with 50/90/100% threshold alerts,
idempotent by display-name. Documents that budgets alert but do not hard-stop.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Monitoring-alerts script (`scripts/setup-monitoring-alerts.sh`)

**Files:**
- Create: `scripts/setup-monitoring-alerts.sh`

No unit test. `bash -n` + review. The operator MUST confirm metric type strings against `gcloud monitoring metrics-descriptors list` for their project/gcloud version before relying on the alerts (the exact identifiers can drift); the script prints that reminder.

- [ ] **Step 1: Write the script**

```bash
#!/usr/bin/env bash
# Create an email notification channel + 3 Cloud Monitoring alert policies for
# the faceless backend. Re-runnable (idempotent by display-name).
#
# Policies: (1) API 5xx rate, (2) Cloud Run Job failures, (3) billing anomaly
# (a log-based metric on the '[billing]' unbilled-fallback + 'REFUND FAILED').
#
# Usage:
#   GCP_PROJECT_ID=... ALERT_EMAIL=you@example.com \
#     [SERVICE=faceless-api] [JOB=faceless-pipeline] \
#     ./scripts/setup-monitoring-alerts.sh
set -euo pipefail

: "${GCP_PROJECT_ID:?set GCP_PROJECT_ID}"
: "${ALERT_EMAIL:?set ALERT_EMAIL}"
SERVICE="${SERVICE:-faceless-api}"
JOB="${JOB:-faceless-pipeline}"
gcloud config set project "${GCP_PROJECT_ID}" >/dev/null

echo ">> Verify these metric types exist for your project/gcloud version:"
echo "   gcloud monitoring metrics-descriptors list --filter=\"metric.type~run.googleapis.com\""
echo

# 1) Email notification channel (reuse if one with this email already exists)
CHANNEL="$(gcloud beta monitoring channels list \
  --filter="type=email AND labels.email_address=${ALERT_EMAIL}" \
  --format='value(name)' | head -n1 || true)"
if [[ -z "${CHANNEL}" ]]; then
  CHANNEL="$(gcloud beta monitoring channels create --type=email \
    --display-name="faceless-alerts" \
    --channel-labels="email_address=${ALERT_EMAIL}" \
    --format='value(name)')"
fi
echo "Notification channel: ${CHANNEL}"

TMP="$(mktemp -d)"
trap 'rm -rf "${TMP}"' EXIT

# 3) Log-based metric for billing anomalies (create if absent)
if ! gcloud logging metrics describe faceless_billing_anomaly >/dev/null 2>&1; then
  gcloud logging metrics create faceless_billing_anomaly \
    --description="Unbilled-render fallback or refund failure" \
    --log-filter='severity>=WARNING AND (textPayload:"[billing]" OR jsonPayload.message:"[billing]" OR textPayload:"REFUND FAILED" OR jsonPayload.message:"REFUND FAILED")'
fi

create_policy () {  # $1=display-name  $2=policy-json-file
  local name="$1" file="$2"
  local existing
  existing="$(gcloud alpha monitoring policies list \
    --filter="displayName=${name}" --format='value(name)' | head -n1 || true)"
  if [[ -n "${existing}" ]]; then
    echo "Policy '${name}' exists (${existing}); skipping (delete to recreate)."
  else
    gcloud alpha monitoring policies create --policy-from-file="${file}" \
      --notification-channels="${CHANNEL}"
    echo "Created policy '${name}'."
  fi
}

# Policy 1 — API 5xx rate
cat > "${TMP}/p1.json" <<JSON
{
  "displayName": "faceless-api 5xx rate",
  "combiner": "OR",
  "conditions": [{
    "displayName": "5xx > 0 over 5m",
    "conditionThreshold": {
      "filter": "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"${SERVICE}\" AND metric.type=\"run.googleapis.com/request_count\" AND metric.labels.response_code_class=\"5xx\"",
      "comparison": "COMPARISON_GT",
      "thresholdValue": 0,
      "duration": "300s",
      "aggregations": [{"alignmentPeriod": "300s", "perSeriesAligner": "ALIGN_RATE"}]
    }
  }]
}
JSON
create_policy "faceless-api 5xx rate" "${TMP}/p1.json"

# Policy 2 — Cloud Run Job failures
cat > "${TMP}/p2.json" <<JSON
{
  "displayName": "faceless-pipeline job failures",
  "combiner": "OR",
  "conditions": [{
    "displayName": "failed executions > 0",
    "conditionThreshold": {
      "filter": "resource.type=\"cloud_run_job\" AND resource.labels.job_name=\"${JOB}\" AND metric.type=\"run.googleapis.com/job/completed_execution_count\" AND metric.labels.result=\"failed\"",
      "comparison": "COMPARISON_GT",
      "thresholdValue": 0,
      "duration": "0s",
      "aggregations": [{"alignmentPeriod": "300s", "perSeriesAligner": "ALIGN_SUM"}]
    }
  }]
}
JSON
create_policy "faceless-pipeline job failures" "${TMP}/p2.json"

# Policy 3 — billing anomaly (on the log-based metric above)
cat > "${TMP}/p3.json" <<JSON
{
  "displayName": "faceless billing anomaly",
  "combiner": "OR",
  "conditions": [{
    "displayName": "unbilled-fallback / refund failure logged",
    "conditionThreshold": {
      "filter": "resource.type=\"cloud_run_revision\" AND metric.type=\"logging.googleapis.com/user/faceless_billing_anomaly\"",
      "comparison": "COMPARISON_GT",
      "thresholdValue": 0,
      "duration": "0s",
      "aggregations": [{"alignmentPeriod": "300s", "perSeriesAligner": "ALIGN_SUM"}]
    }
  }]
}
JSON
create_policy "faceless billing anomaly" "${TMP}/p3.json"

echo "Done. Verify in Console > Monitoring > Alerting."
```

- [ ] **Step 2: Syntax check + perms**

```bash
bash -n scripts/setup-monitoring-alerts.sh
chmod +x scripts/setup-monitoring-alerts.sh
```

- [ ] **Step 3: Commit**

```bash
git add scripts/setup-monitoring-alerts.sh
git commit -m "$(cat <<'EOF'
feat(infra): re-runnable Cloud Monitoring alerts setup script

Email channel + 3 alert policies (API 5xx, Job failures, billing-anomaly
log-based metric on [billing]/REFUND FAILED). Idempotent by display-name;
prints a reminder to verify metric-type strings for the gcloud version.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Operator runbook (`docs/TIER2-INFRA.md`)

**Files:**
- Create: `docs/TIER2-INFRA.md`
- Modify: `docs/GO-LIVE-READINESS.md`

- [ ] **Step 1: Write `docs/TIER2-INFRA.md`** — with these exact sections:

```markdown
# Tier-2 Infra Safety Net — Operator Runbook

Code pieces (merged): GCP-native JSON logging + API 5xx handler
(`pipeline/observability.py`), Cloud Run `maxScale=4`. This runbook covers the
console/CLI steps code can't do. Run them before enabling payments.

## 1. Redeploy (activates maxScale + structured logging)
    ./scripts/build-and-push.sh
Verify: Console > Cloud Run > faceless-api > Revisions shows max instances = 4.

## 2. Billing budget
    GCP_PROJECT_ID=<proj> ALERT_EMAIL=<you> BUDGET_USD=50 ./scripts/setup-billing-budget.sh
Verify: Console > Billing > Budgets & alerts shows "faceless-monthly" with
50/90/100% thresholds. NOTE: a budget ALERTS, it does not hard-stop spend.

## 3. Monitoring alerts
    GCP_PROJECT_ID=<proj> ALERT_EMAIL=<you> ./scripts/setup-monitoring-alerts.sh
First confirm metric types exist (the script prints the command). Verify:
Console > Monitoring > Alerting shows the 3 policies + the email channel; and
Logs Explorer > Log-based metrics shows `faceless_billing_anomaly`.

## 4. Supabase backups (financial system of record)
Dashboard > Database > Backups. Enable PITR (paid) OR scheduled daily backups.
Record the retention window here: __________

## 5. Kie.ai account spend cap
Kie console: keep a bounded prepaid balance, auto-recharge OFF (or a low cap).
Record the cap here: __________

## 6. Verify the safety net fires
- Force a 500 (hit a route that errors) -> appears in Console > Error Reporting,
  and the 5xx alert emails within ~5 min.
- Run a Job that fails -> the job-failure alert emails.
- Trigger a `[billing]` warning (e.g. a run whose out_root diverges) -> the
  billing-anomaly alert emails.
```

- [ ] **Step 2: Update `docs/GO-LIVE-READINESS.md`** — under the Tier-2 table, add a note after the table:
```markdown
> **Tier-2 status (2026-08-05):** code pieces done — GCP-native structured
> logging + API 5xx handler (`pipeline/observability.py`) and Cloud Run
> `maxScale=4`. Operator steps (billing budget, monitoring alerts, Supabase
> PITR, Kie cap) are scripted/checklisted in `docs/TIER2-INFRA.md`.
```

- [ ] **Step 3: Commit**

```bash
git add docs/TIER2-INFRA.md docs/GO-LIVE-READINESS.md
git commit -m "$(cat <<'EOF'
docs(infra): Tier-2 operator runbook + go-live status

docs/TIER2-INFRA.md: redeploy for maxScale, run the budget + alerts scripts,
enable Supabase PITR, set the Kie account cap, and verify each alert fires.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Full-suite verification

**Files:** none (verification).

- [ ] **Step 1: Full suite (clean env)**
```bash
env -u ANTHROPIC_API_KEY -u GROQ_API_KEY -u FACELESS_API_TOKEN -u KIE_API_KEY \
    -u ELEVENLABS_API_KEY -u SUPABASE_URL -u SUPABASE_SERVICE_ROLE_KEY \
    -u STRIPE_SECRET_KEY -u STRIPE_WEBHOOK_SECRET uv run pytest -q
```
Expected: baseline 825 + new tests (observability 7, api 1, deploy 1; the run_charging billing tests were updated not added) — report the exact count; **0 failed**.

- [ ] **Step 2: Script syntax gate**
```bash
bash -n scripts/setup-billing-budget.sh && bash -n scripts/setup-monitoring-alerts.sh && echo OK
```

- [ ] **Step 3: Offline import smoke**
```bash
uv run python -c "import pipeline.observability as o; o.setup_logging(); o.get_logger().info('smoke'); print('obs OK')"
```
Expected: one JSON line + `obs OK`.
