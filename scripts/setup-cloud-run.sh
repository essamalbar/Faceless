#!/usr/bin/env bash
# scripts/setup-cloud-run.sh — provision the Cloud Run deployment.
#
# Run this ONCE on your Mac to create:
#   1. A GCS bucket for run artifacts
#   2. An Artifact Registry repo for the Docker image
#   3. A service account with the right IAM roles
#   4. Secrets in Secret Manager (loaded from your .env)
#   5. The Cloud Run Service (API)
#   6. The Cloud Run Job (pipeline worker)
#
# Re-running is safe — every step is idempotent (creates if missing, skips otherwise).
#
# Prereqs: gcloud authed (`gcloud auth login`), docker installed, .env populated.
set -euo pipefail

# ---------- config ----------
PROJECT_ID="${GCP_PROJECT:-$(gcloud config get-value project 2>/dev/null)}"
REGION="${GCP_REGION:-us-central1}"
BUCKET_NAME="${BUCKET_NAME:-${PROJECT_ID}-faceless-runs}"
REGISTRY_NAME="faceless"
SERVICE_ACCOUNT_NAME="faceless-runtime"
SERVICE_NAME="faceless-api"
JOB_NAME="faceless-pipeline"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REGISTRY_NAME}/faceless:latest"

if [ -z "$PROJECT_ID" ]; then
  echo "ERROR: no GCP project set. Run \`gcloud config set project <id>\` first."
  exit 1
fi

if [ ! -f .env ]; then
  echo "ERROR: .env not found in $(pwd). Need API keys to load into Secret Manager."
  exit 1
fi

# shellcheck disable=SC1091
set -a
source .env
set +a

echo "==================================================="
echo " Cloud Run setup for project: ${PROJECT_ID}"
echo " Region: ${REGION}"
echo " Bucket: gs://${BUCKET_NAME}"
echo " Image:  ${IMAGE}"
echo "==================================================="

# ---------- 1. GCS bucket ----------
echo
echo "[1/6] Creating GCS bucket if it does not exist..."
if ! gcloud storage buckets describe "gs://${BUCKET_NAME}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud storage buckets create "gs://${BUCKET_NAME}" \
    --project="${PROJECT_ID}" \
    --location="${REGION}" \
    --uniform-bucket-level-access
  echo "  -> created gs://${BUCKET_NAME}"
else
  echo "  -> already exists"
fi

# ---------- 2. Artifact Registry ----------
echo
echo "[2/6] Creating Artifact Registry repo if it does not exist..."
if ! gcloud artifacts repositories describe "${REGISTRY_NAME}" \
       --project="${PROJECT_ID}" --location="${REGION}" >/dev/null 2>&1; then
  gcloud artifacts repositories create "${REGISTRY_NAME}" \
    --project="${PROJECT_ID}" \
    --location="${REGION}" \
    --repository-format=docker \
    --description="Faceless backend images"
  echo "  -> created"
else
  echo "  -> already exists"
fi

# Configure docker auth for the registry
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

# ---------- 3. Service account ----------
echo
echo "[3/6] Creating service account if it does not exist..."
SA_EMAIL="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
if ! gcloud iam service-accounts describe "${SA_EMAIL}" \
       --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud iam service-accounts create "${SERVICE_ACCOUNT_NAME}" \
    --project="${PROJECT_ID}" \
    --display-name="Faceless runtime" \
    --description="Runs the Cloud Run Service and Job"
  echo "  -> created"
else
  echo "  -> already exists"
fi

echo "  -> granting IAM roles to ${SA_EMAIL}"
for role in \
    roles/storage.objectAdmin \
    roles/run.invoker \
    roles/run.developer \
    roles/secretmanager.secretAccessor; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="${role}" \
    --condition=None \
    --quiet >/dev/null
done
echo "  -> done"

# ---------- 4. Secret Manager ----------
echo
echo "[4/6] Loading secrets into Secret Manager..."
write_secret() {
  local name="$1"
  local value="$2"
  if [ -z "${value:-}" ]; then
    echo "  -> ${name}: SKIPPED (empty in .env)"
    return
  fi
  if ! gcloud secrets describe "${name}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
    printf '%s' "$value" | gcloud secrets create "${name}" \
      --project="${PROJECT_ID}" \
      --replication-policy="automatic" \
      --data-file=- >/dev/null
    echo "  -> ${name}: created"
  else
    printf '%s' "$value" | gcloud secrets versions add "${name}" \
      --project="${PROJECT_ID}" \
      --data-file=- >/dev/null
    echo "  -> ${name}: new version added"
  fi
}

write_secret "faceless-api-token" "${FACELESS_API_TOKEN:-}"
write_secret "anthropic-api-key" "${ANTHROPIC_API_KEY:-}"
write_secret "kie-api-key" "${KIE_API_KEY:-}"
write_secret "elevenlabs-api-key" "${ELEVENLABS_API_KEY:-}"

# ---------- 5. Build + push image ----------
echo
echo "[5/6] Building + pushing Docker image..."
echo "  -> image: ${IMAGE}"
docker buildx build \
  --platform linux/amd64 \
  -t "${IMAGE}" \
  --push \
  .

# ---------- 6. Deploy Service + Job ----------
echo
echo "[6/6] Deploying Cloud Run Service + Job..."

# Substitute env vars in the YAML files
tmpdir=$(mktemp -d)
trap "rm -rf $tmpdir" EXIT

sed -e "s|\\\${PROJECT_ID}|${PROJECT_ID}|g" \
    -e "s|\\\${BUCKET_NAME}|${BUCKET_NAME}|g" \
    deploy/cloud-run-service.yaml > "$tmpdir/service.yaml"
sed -e "s|\\\${PROJECT_ID}|${PROJECT_ID}|g" \
    -e "s|\\\${BUCKET_NAME}|${BUCKET_NAME}|g" \
    deploy/cloud-run-job.yaml > "$tmpdir/job.yaml"

# Service first — replace creates or updates
gcloud run services replace "$tmpdir/service.yaml" \
  --region="${REGION}" --project="${PROJECT_ID}" --quiet

# Allow public unauthenticated calls to the service (auth is via bearer token)
gcloud run services add-iam-policy-binding "${SERVICE_NAME}" \
  --region="${REGION}" --project="${PROJECT_ID}" \
  --member="allUsers" --role="roles/run.invoker" --quiet >/dev/null

# Job
gcloud run jobs replace "$tmpdir/job.yaml" \
  --region="${REGION}" --project="${PROJECT_ID}" --quiet

# Get the public service URL
SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" \
  --region="${REGION}" --project="${PROJECT_ID}" \
  --format="value(status.url)")

echo
echo "==================================================="
echo " Deployment complete"
echo
echo "   API service URL:  ${SERVICE_URL}"
echo "   Healthcheck:      ${SERVICE_URL}/healthz"
echo
echo " Test from your Mac:"
echo "   curl ${SERVICE_URL}/healthz"
echo "   curl -H \"Authorization: Bearer \$FACELESS_API_TOKEN\" ${SERVICE_URL}/runs"
echo "==================================================="
