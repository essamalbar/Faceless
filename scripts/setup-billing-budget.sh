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
