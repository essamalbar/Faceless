#!/usr/bin/env bash
# scripts/build-and-push.sh — rebuild the image + redeploy Cloud Run.
# Used for ongoing dev; setup-cloud-run.sh is the first-time provisioner.
set -euo pipefail

PROJECT_ID="${GCP_PROJECT:-$(gcloud config get-value project)}"
REGION="${GCP_REGION:-us-central1}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/faceless/faceless:latest"

# ---------------------------------------------------------------------------
# Build the Flutter web bundle BEFORE submitting to Cloud Build so the
# resulting image can serve the SPA at /app/* on the same origin as the
# API. Skipped if the Flutter SDK isn't on PATH — the image still builds,
# just without the SPA (the @app.get('/') handler in pipeline/api.py
# detects the missing bundle and returns a JSON breadcrumb instead).
#
# Public-facing dart-defines:
#   FACELESS_API_URL    — the deployed Cloud Run URL so same image works
#                         from any origin (custom domains route through it)
#   FACELESS_API_TOKEN  — empty: public users authenticate via Supabase,
#                         never bake in the admin service token
#   SUPABASE_URL        — from .env
#   SUPABASE_ANON_KEY   — from .env (anon key is designed to be public)
# ---------------------------------------------------------------------------
if command -v flutter >/dev/null 2>&1; then
  echo "-> Building Flutter web bundle"
  set -a
  # shellcheck disable=SC1091
  source .env 2>/dev/null || true
  set +a

  PROD_API_URL=$(gcloud run services describe faceless-api \
    --region="${REGION}" --project="${PROJECT_ID}" \
    --format="value(status.url)" 2>/dev/null || true)

  flutter build web --release \
    --base-href /app/ \
    --dart-define="FACELESS_API_URL=${PROD_API_URL}" \
    --dart-define="FACELESS_API_TOKEN=" \
    --dart-define="SUPABASE_URL=${SUPABASE_URL:-}" \
    --dart-define="SUPABASE_ANON_KEY=${SUPABASE_ANON_KEY:-}"
  echo "-> Flutter web bundle ready at build/web"
else
  echo "WARN: flutter not on PATH — image will not include the web app"
fi

echo "-> Building + pushing ${IMAGE} via Cloud Build (server-side)"
# Cloud Build uploads the source tarball (~24 MB) and builds the image inside
# Google's datacenter on an 8-vCPU machine, then pushes to Artifact Registry
# over the internal network. Avoids the gigabyte-scale upload of a local
# `docker buildx --push`, which stalls on slow/mobile connections.
gcloud builds submit \
  --tag "${IMAGE}" \
  --machine-type=e2-highcpu-8 \
  --timeout=30m \
  --project="${PROJECT_ID}" \
  .

echo "-> Updating Service to roll out the new image"
gcloud run services update faceless-api \
  --region="${REGION}" --project="${PROJECT_ID}" \
  --image="${IMAGE}"

echo "-> Updating Job to roll out the new image"
gcloud run jobs update faceless-pipeline \
  --region="${REGION}" --project="${PROJECT_ID}" \
  --image="${IMAGE}"

URL=$(gcloud run services describe faceless-api \
  --region="${REGION}" --project="${PROJECT_ID}" \
  --format="value(status.url)")
echo
echo "Done. API at: $URL"
echo "  curl $URL/health"
