# Tier-2 Infra Safety Net — Operator Runbook

Code pieces (merged): GCP-native JSON logging + API 5xx handler
(`pipeline/observability.py`), Cloud Run `maxScale=4`. This runbook covers the
console/CLI steps code can't do. Run them before enabling payments.

## 0. Enable the prerequisite APIs (one-time)

    gcloud services enable billingbudgets.googleapis.com monitoring.googleapis.com \
      logging.googleapis.com --project=<proj>

(Allow a couple of minutes to propagate before the budget script works.)

## 1. Redeploy (activates the structured logging code)

    ./scripts/build-and-push.sh

Then apply the autoscaling cap ONCE (build-and-push does an image-only
`services update`, which does NOT read the yaml's `maxScale` annotation; but an
image-only update PRESERVES an already-set max-instances, so this is one-time):

    gcloud run services update faceless-api --region=us-central1 \
      --project=<proj> --max-instances=4

Verify: `curl <service-url>/health` → `{"ok":true}` (note: the raw run.app
`/healthz` is swallowed by Google's frontend — use `/health`), Console > Cloud
Run > faceless-api shows max instances = 4, and Logs show JSON entries with a
`severity` field (not plain text).

## 2. Billing budget

    GCP_PROJECT_ID=<proj> ALERT_EMAIL=<you> BUDGET_USD=50 ./scripts/setup-billing-budget.sh

Verify: Console > Billing > Budgets & alerts shows "faceless-monthly" with
50/90/100% thresholds. **NOTE:** a budget ALERTS, it does not hard-stop spend —
that's why the Cloud Run maxScale cap (step 1) and the Kie account cap (step 5)
also exist.

## 3. Monitoring alerts

    GCP_PROJECT_ID=<proj> ALERT_EMAIL=<you> ./scripts/setup-monitoring-alerts.sh

First confirm the metric types exist (the script prints the command). Verify:
Console > Monitoring > Alerting shows the 3 policies (`faceless-api 5xx rate`,
`faceless-pipeline job failures`, `faceless billing anomaly`) + the email
channel; and Logging > Logs-based metrics shows `faceless_billing_anomaly`.

## 4. Supabase backups (the credit/payment ledger is the financial system of record)

Dashboard > Database > Backups. Enable PITR (paid) OR scheduled daily backups.

Record the retention window here: __________

## 5. Kie.ai account spend cap

Kie console: keep a bounded prepaid balance with auto-recharge OFF (or set a low
cap). This is the hard ceiling on external render spend that a GCP budget can't
provide.

Record the cap here: __________

## 6. Verify the safety net fires

- Force a 500 (hit a route that errors) → appears in Console > Error Reporting,
  and the `faceless-api 5xx rate` alert emails within ~5 min.
- Run a Job that fails → the `faceless-pipeline job failures` alert emails.
- Trigger a `[billing]` warning (e.g. a run whose `FACELESS_OUT_ROOT` diverges
  from the API's) → the `faceless billing anomaly` alert emails.

## What this does NOT cover (still open before real users)

Tier-3 legal (ToS/Privacy/refund, DMCA/abuse, GDPR delete/export) — a separate
workstream tracked in `docs/GO-LIVE-READINESS.md`.
