#!/usr/bin/env bash
# scripts/setup-gcs-lifecycle.sh — apply an object-retention lifecycle rule
# to the GCS bucket that holds generated run artifacts.
#
# What it does: sets a single lifecycle rule that DELETES any object older
# than RETENTION_DAYS (default 90). This is the durable retention mechanism
# for generated artifacts (scripts, images, clips, final.mp4). The in-app
# 30-day cleanup of FAILED runs stays as-is; this covers everything else,
# including COMPLETED artifacts that otherwise persist indefinitely.
#
# IMPORTANT: this ONLY affects generated artifacts in the GCS bucket. It does
# NOT touch the Supabase ledger (credits / billing), which is the financial
# system of record and must be retained independently. Deleting old rendered
# artifacts never deletes or alters a single ledger row.
#
# Idempotent: re-running writes the full lifecycle config each time, so it is
# safe to run repeatedly (it replaces, not appends).
#
# Usage:
#   GCS_BUCKET=my-bucket ./scripts/setup-gcs-lifecycle.sh
#   GCS_BUCKET=my-bucket RETENTION_DAYS=30 ./scripts/setup-gcs-lifecycle.sh
#
# Inputs (env):
#   GCS_BUCKET      required — bucket name (a leading gs:// is stripped). If
#                   unset, discovered from FACELESS_OUT_ROOT (when it is a
#                   gs:// URL) or from the active gcloud project as
#                   "<project>-faceless-runs".
#   RETENTION_DAYS  optional — positive integer, default 90.
#
# Prereqs: gcloud authed (`gcloud auth login`) with storage admin on the bucket.
set -euo pipefail

RETENTION_DAYS="${RETENTION_DAYS:-90}"

# ---------- validate RETENTION_DAYS ----------
if ! [[ "${RETENTION_DAYS}" =~ ^[1-9][0-9]*$ ]]; then
  echo "ERROR: RETENTION_DAYS must be a positive integer (got '${RETENTION_DAYS}')." >&2
  exit 1
fi

# ---------- resolve the bucket name ----------
if [[ -z "${GCS_BUCKET:-}" ]]; then
  out_root="${FACELESS_OUT_ROOT:-}"
  if [[ "${out_root}" == gs://* ]]; then
    # gs://bucket/some/prefix -> bucket
    GCS_BUCKET="${out_root#gs://}"
    GCS_BUCKET="${GCS_BUCKET%%/*}"
  else
    project="$(gcloud config get-value project 2>/dev/null || true)"
    if [[ -n "${project}" ]]; then
      GCS_BUCKET="${project}-faceless-runs"
    fi
  fi
fi

# Strip a leading gs:// (and any trailing path) so we never build gs://gs://…
GCS_BUCKET="${GCS_BUCKET#gs://}"
GCS_BUCKET="${GCS_BUCKET%%/*}"

if [[ -z "${GCS_BUCKET:-}" ]]; then
  echo "ERROR: could not determine the bucket. Set GCS_BUCKET explicitly, e.g." >&2
  echo "  GCS_BUCKET=my-project-faceless-runs ./scripts/setup-gcs-lifecycle.sh" >&2
  exit 1
fi

echo "Bucket:          gs://${GCS_BUCKET}"
echo "Retention:       delete objects older than ${RETENTION_DAYS} days"
echo

# ---------- write the lifecycle JSON to a temp file ----------
tmp="$(mktemp)"
trap 'rm -f "${tmp}"' EXIT

cat > "${tmp}" <<JSON
{
  "rule": [
    {
      "action": { "type": "Delete" },
      "condition": { "age": ${RETENTION_DAYS} }
    }
  ]
}
JSON

# ---------- apply ----------
gcloud storage buckets update "gs://${GCS_BUCKET}" --lifecycle-file="${tmp}"

echo
echo "Lifecycle rule applied to gs://${GCS_BUCKET}."
echo "Verify with:"
echo "  gcloud storage buckets describe gs://${GCS_BUCKET} --format=\"json(lifecycle)\""
