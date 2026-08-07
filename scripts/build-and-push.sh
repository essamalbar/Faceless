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

  # -------------------------------------------------------------------------
  # Service-token-leak guard (Tier-4B): the PUBLIC web bundle MUST ship an
  # EMPTY FACELESS_API_TOKEN — real users authenticate via Supabase, and the
  # admin service token must never be embedded in a client anyone can
  # download. BAKED_TOKEN is the value actually compiled into the bundle
  # (empty by design). We guard the BAKED value, not the sourced env var:
  # `source .env` above intentionally loads FACELESS_API_TOKEN for other
  # tooling, so guarding the env var would trip on every normal build. Refuse
  # to proceed if a non-empty token would be baked, unless an operator
  # explicitly opts in with ALLOW_TOKEN_IN_PROD_BUILD=1 (private build only).
  # -------------------------------------------------------------------------
  BAKED_TOKEN=""
  if [ -n "${BAKED_TOKEN}" ] && [ "${ALLOW_TOKEN_IN_PROD_BUILD:-0}" != "1" ]; then
    echo "ERROR: refusing to bake FACELESS_API_TOKEN into the PUBLIC web bundle." >&2
    echo "       The prod build must ship an empty token (users auth via Supabase)." >&2
    echo "       Set ALLOW_TOKEN_IN_PROD_BUILD=1 only for a private/internal build." >&2
    exit 1
  fi

  flutter build web --release \
    --base-href /app/ \
    --dart-define="FACELESS_API_URL=${PROD_API_URL}" \
    --dart-define="FACELESS_API_TOKEN=${BAKED_TOKEN}" \
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

# Resolve :latest to an immutable digest so the Service + Job both
# get pinned to the exact image we just built. Without this, a
# concurrent push from another dev (or a build retry) could shift
# :latest between the build and the rollout, leaving the Service
# running one digest and the Job running another.
echo "-> Resolving image digest"
# gcloud's `tags list --filter=tag=latest` has a deprecated filter
# operator (warns + returns nothing); `images list --filter=tags:latest`
# is the supported equivalent.
DIGEST=$(gcloud artifacts docker images list \
  "${REGION}-docker.pkg.dev/${PROJECT_ID}/faceless/faceless" \
  --include-tags \
  --filter="tags:latest" \
  --format="value(version)" \
  --project="${PROJECT_ID}" 2>/dev/null | head -1)
if [ -z "${DIGEST}" ]; then
  echo "WARN: could not resolve digest for :latest — falling back to tag" >&2
  IMAGE_REF="${IMAGE}"
else
  IMAGE_REF="${REGION}-docker.pkg.dev/${PROJECT_ID}/faceless/faceless@${DIGEST}"
  echo "   pinned to ${DIGEST:0:24}…"
fi

echo "-> Updating Service to roll out the new image"
gcloud run services update faceless-api \
  --region="${REGION}" --project="${PROJECT_ID}" \
  --image="${IMAGE_REF}"

echo "-> Updating Job to roll out the new image"
gcloud run jobs update faceless-pipeline \
  --region="${REGION}" --project="${PROJECT_ID}" \
  --image="${IMAGE_REF}"

URL=$(gcloud run services describe faceless-api \
  --region="${REGION}" --project="${PROJECT_ID}" \
  --format="value(status.url)")
echo
echo "Done. API at: $URL"
echo "  curl $URL/health"
