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
