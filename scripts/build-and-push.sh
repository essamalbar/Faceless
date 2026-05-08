#!/usr/bin/env bash
# scripts/build-and-push.sh — rebuild the image + redeploy Cloud Run.
# Used for ongoing dev; setup-cloud-run.sh is the first-time provisioner.
set -euo pipefail

PROJECT_ID="${GCP_PROJECT:-$(gcloud config get-value project)}"
REGION="${GCP_REGION:-us-central1}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/faceless/faceless:latest"

echo "-> Building + pushing ${IMAGE}"
docker buildx build --platform linux/amd64 -t "${IMAGE}" --push .

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
echo "  curl $URL/healthz"
