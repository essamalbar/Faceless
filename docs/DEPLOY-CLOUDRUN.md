# Deploy to Google Cloud Run (free tier)

Faceless runs as two Cloud Run services from the same Docker image:

- **`faceless-api`** — Cloud Run **Service**, always-on, serves the FastAPI HTTP backend.
- **`faceless-pipeline`** — Cloud Run **Job**, runs the pipeline (`run.py`) for one video render then exits.

Both share a GCS bucket mounted at `/mnt/runs` for run artifacts.

## Free tier coverage

Cloud Run free tier (per month, all regions combined):
- 2,000,000 requests
- 360,000 GB-seconds memory
- 180,000 vCPU-seconds
- 1 GB outbound from North America

A single pipeline render uses ~600 vCPU-seconds + ~1,200 GB-seconds → **~300 free renders/month**. After that, Cloud Run charges roughly $0.000024/vCPU-second + $0.0000025/GB-second.

GCS Storage free tier: 5 GB (region-dependent). Each run is ~30 MB. Run cleanup recommended after a couple of months.

## One-time setup

You need:

1. **A GCP project** with billing enabled (free tier still requires a billing account).
2. **gcloud CLI** authed locally: `gcloud auth login` then `gcloud config set project <id>`.
3. **Docker buildx** for cross-arch builds: `docker buildx create --use` (one-time).
4. **APIs enabled**: `run.googleapis.com`, `storage.googleapis.com`, `artifactregistry.googleapis.com`, `secretmanager.googleapis.com`. Enable with `gcloud services enable …` if not already.
5. **`.env` file** populated with API keys (will be loaded into Secret Manager):

   ```
   FACELESS_API_TOKEN=<openssl rand -hex 32>
   ANTHROPIC_API_KEY=sk-ant-...
   KIE_API_KEY=...
   ELEVENLABS_API_KEY=...   # optional
   ```

Then run from the repo root:

```bash
./scripts/setup-cloud-run.sh
```

This single command:
1. Creates the GCS bucket
2. Creates the Artifact Registry repo
3. Creates the service account with the right IAM roles
4. Loads `.env` secrets into Secret Manager
5. Builds + pushes the Docker image
6. Deploys both the Service and the Job
7. Prints the public API URL

Re-running it is safe — every step is idempotent.

## Day-to-day: redeploy after code changes

```bash
./scripts/build-and-push.sh
```

This rebuilds the image and rolls out a new revision of both the Service and Job.

## Test the deployment

```bash
SERVICE_URL=$(gcloud run services describe faceless-api \
  --region=us-central1 --format="value(status.url)")

# Liveness — use /health on Cloud Run (the LB reserves /healthz for itself)
curl $SERVICE_URL/health

# Authed list
source .env
curl -H "Authorization: Bearer $FACELESS_API_TOKEN" $SERVICE_URL/runs
```

## How the API and Job talk

The API runs in the Cloud Run **Service** with `FACELESS_SPAWN_BACKEND=cloudrun_jobs`. When the Flutter app posts to `/runs`, the API calls `gcloud run jobs execute faceless-pipeline …` to spawn the Job. The Job receives pipeline arguments via the `FACELESS_RUN_ARGS` env var (set on the execute call) and runs `run.py` to completion. Both write artifacts to the same GCS bucket via the `/mnt/runs` mount, so polling endpoints in the API can read what the Job has written so far.

## Updating secrets

To rotate an API key:

```bash
gcloud secrets versions add anthropic-api-key --data-file=- <<< "$NEW_KEY"
```

The next Service / Job execution picks up the new version automatically.

## Cleanup old runs

```bash
# List runs older than 30 days
gcloud storage ls gs://<bucket>/runs/ | head

# Delete one
gcloud storage rm -r gs://<bucket>/runs/<run-id>/
```

In a future stage we'll automate this via a Cloud Scheduler cron + Cloud Function.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `gcloud run services replace` fails with "permission denied" | Missing `roles/run.developer` on your user | `gcloud projects add-iam-policy-binding <project> --member=user:you@example.com --role=roles/run.developer` |
| Service deploys but `/health` returns 502 | Container crashed on startup — check logs | `gcloud run services logs read faceless-api --region=us-central1` |
| `/healthz` returns 404 from Google's frontend | Cloud Run's load balancer reserves `/healthz` for its own probes | Use `/health` instead — the API exposes both paths and `/health` reaches the container |
| API returns 503 "FACELESS_API_TOKEN not configured" | Secret not mounted | Verify the secret exists: `gcloud secrets versions list faceless-api-token` |
| Job never starts when API calls it | API service account missing `roles/run.developer` | Re-run `setup-cloud-run.sh` (idempotent) |
| `gcsfuse` mount fails | Volume mount only available with `gen2` execution environment | Already set in the YAML; if it errors, re-deploy |
