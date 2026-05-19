# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

This repo holds two unrelated codebases coexisting:

1. **Python pipeline** at the repo root (`pipeline/`, `tests/`, `run.py`, `pyproject.toml`) — the active MVP. Generates Arabic horror videos end-to-end (script → narration → images → assembly). See `docs/superpowers/specs/2026-05-01-arabic-horror-faceless-system-design.md` for design and `docs/superpowers/plans/2026-05-01-arabic-horror-faceless-system.md` for the build plan.
2. **Flutter app scaffold** (`lib/`, `pubspec.yaml`, `android/`, `ios/`, etc.) — untouched in MVP. Will become the dashboard in Phase 2+.

**Phase 1 (MVP):** isolation rule applied — Python pipeline and Flutter scaffold lived as separate codebases. **Phase 2 (active now):** they're integrated through `pipeline/api.py`. Cross-stack work is expected when adding mobile-app features. The Flutter `lib/` will consume the FastAPI endpoints documented below.

## Common commands (Python pipeline)

```bash
uv sync                                 # install Python deps
uv run pytest                           # run all tests
uv run pytest tests/test_seed.py -v     # single test file
uv run pytest -k test_chunk             # tests matching pattern
uv run python run.py --theme folkloric --seed "بئر قديم"   # run pipeline manually
uv run python run.py --skip-images      # dry-run with placeholder PNGs (fast)
```

## Tier-3 environment variables (Shorts mode)

```bash
# Required
export KIE_API_KEY=<your kie.ai key>
export GROQ_API_KEY=<your groq key>
export ELEVENLABS_API_KEY=<your elevenlabs key>

# Optional — only if your network blocks aiquickdraw.com (UAE etc.)
export KIE_DOWNLOAD_PROXY=https://your-worker.workers.dev
export KIE_DOWNLOAD_PROXY_SECRET=<shared secret>
```

## Video provider selection

`config.yaml > kie.model` picks the video generator. Costs are auto-mapped
per model in `pipeline/api.py:_COST_BY_MODEL` — the approve-gate dollar
figure and the budget guard both follow the active model:

| Model id                       | Rate     | Notes |
|--------------------------------|----------|-------|
| `veo3_fast` (default)          | $0.10/s  | Veo Fast with native lip-synced Arabic audio. `native_audio: true` required. |
| `veo3`                         | $0.40/s  | Cinematic Veo. 4× cost of Fast. |
| `kling/v2-1-standard`          | $0.025/s | 4× cheaper than Veo Fast. No native audio — set `native_audio: false` AND keep ELEVENLABS_API_KEY in env. |
| `kling/v2-1-pro`               | $0.05/s  | Same caveats as Standard. 1080p output. |
| `kling-2.6/image-to-video`     | $0.056/s | Newer family. Optional native audio (extra cost). |

Switching from Veo → Kling: edit `config.yaml`, set `model:` to the
chosen kling id AND `native_audio: false`. The pipeline auto-routes to
the right endpoint (`/api/v1/veo/generate` vs `/api/v1/jobs/createTask`)
based on the model id prefix; no other changes needed.

Image uploads (for Veo image-to-video chaining) use 0x0.st by default — anonymous,
no API key needed. Override `pipeline.video._upload_image_get_url` if you'd
rather use Cloudflare R2 / imgbb / your own bucket.

Run a tier-3 video:

```bash
source .env
uv run python run.py --shorts --theme folkloric --seed "أم فقيرة..."
```

## Backend API (Phase 2 — controls the pipeline from a mobile app)

The HTTP API in `pipeline/api.py` wraps the orchestrator so a Flutter app can:
trigger a run, review the script before paying, approve it, and resume after
failures. Auth is a single bearer token (solo-user software).

### Zero-config launcher (recommended)

`scripts/run-app.sh` does everything in one command — checks the API is up
(starts it if not), checks the Cloudflare Tunnel is up (starts it if not),
captures the live tunnel URL, and runs `flutter` with the URL and token
baked in via `--dart-define` so the app skips the Settings screen entirely.

```bash
# One-time setup: pick a token and put it in .env
echo "export FACELESS_API_TOKEN=$(openssl rand -hex 32)" >> .env

# Then every launch:
./scripts/run-app.sh                  # default: chrome web
./scripts/run-app.sh -d <device-id>   # ios/android — see `flutter devices`
```

### Manual mode (debugging)

If you want to start each piece yourself:

```bash
# 1) API server
source .env && uv run uvicorn pipeline.api:app --host 0.0.0.0 --port 8000

# 2) Cloudflare Tunnel (separate terminal)
cloudflared tunnel --url http://localhost:8000

# 3) Flutter app (separate terminal) — pass URL+token via --dart-define
flutter run -d chrome \
  --dart-define=FACELESS_API_URL=https://xyz.trycloudflare.com \
  --dart-define=FACELESS_API_TOKEN="$FACELESS_API_TOKEN"
```

In manual mode you can also skip the dart-defines and configure the app from
its first-launch Settings screen.

API endpoints (all require `Authorization: Bearer $FACELESS_API_TOKEN`
except `/healthz`):

| Method | Path | Purpose |
|---|---|---|
| GET | `/healthz` | liveness, no auth |
| GET | `/runs` | list past runs with status + thumbnails |
| POST | `/runs` | start new run (writer pass only — pauses for approval) |
| GET | `/runs/{id}` | full status |
| GET | `/runs/{id}/script` | Arabic script + cost estimate |
| POST | `/runs/{id}/approve` | green-light Veo spend |
| POST | `/runs/{id}/resume` | retry after a transient failure |
| POST | `/runs/{id}/cancel` | kill running subprocess + refund |
| POST | `/runs/{id}/test-assemble` | $0 smoke test — runs music/captions/assemble with `--skip-video` placeholder clips |
| GET | `/runs/{id}/video` | stream final.mp4 |
| GET | `/runs/{id}/thumbnail` | poster image |
| GET | `/runs/{id}/log?lines=N` | tail subprocess log |
| POST | `/admin/credit-back` | service-token only — credit a user's ledger after a failed render |

## Common commands (Flutter app — Phase 2 frontend)

```bash
flutter pub get
flutter analyze
flutter test
flutter run -d chrome
```

The Flutter scaffold is being upgraded into the dashboard that talks to the
backend API above. Cross-stack work is now expected.

Note: `lib/main.dart:31` and `:105` have invalid Dart (missing type names on `.fromSeed(...)` and `.center`) — `flutter analyze` will fail until these are fixed. Not blocking the Python work.

## Docker / Cloud deployment

The backend runs as a Docker container — locally for testing or on Oracle Cloud Always-Free for production.

### Local Docker test (Mac)

```bash
# Build image and start the API on localhost:8000
docker compose up --build

# Verify health
curl http://localhost:8000/healthz   # → {"ok":true}

# Authenticated endpoint check (should return 200 with runs list)
source .env
curl -s -H "Authorization: Bearer $FACELESS_API_TOKEN" http://localhost:8000/runs

# Stop
docker compose down
```

Artifacts in `out/` are bind-mounted so they survive `docker compose down/up`.
Whisper models are cached in a named Docker volume (`whisper-cache`) so they
are not re-downloaded on every rebuild.

### Production deployment to Oracle Always-Free

Full step-by-step guide: `docs/DEPLOY-ORACLE.md`

Quick version (on the Oracle VM after `git clone` + `.env` setup):

```bash
./scripts/deploy-oracle.sh
```

The prod overlay (`docker-compose.prod.yml`) adds a `cloudflare/cloudflared`
container that creates a named Cloudflare Tunnel so the API is reachable at
`https://api.yourdomain.com` without opening any VM firewall ports.

```bash
# Start with prod overlay (Cloudflare Tunnel)
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Update after a git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

### Multi-arch image build

The image targets `linux/arm64` by default (Mac Apple Silicon + Oracle Ampere A1
are both ARM64). To push a multi-arch image to a registry:

```bash
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t ghcr.io/<you>/faceless:latest \
  --push .
```

### Production deployment to Google Cloud Run (free tier)

Single command from your Mac (re-runnable, idempotent):

```bash
./scripts/setup-cloud-run.sh
```

Provisions: GCS bucket + Artifact Registry + service account + secrets +
Cloud Run Service (API) + Cloud Run Job (pipeline worker).

Daily redeploys after code changes:

```bash
./scripts/build-and-push.sh
```

Full guide: `docs/DEPLOY-CLOUDRUN.md`. Free-tier capacity: ~300 video
renders/month before any cost.

## Key invariants

- **External services are mocked in tests.** Every external API (Gemini, Edge TTS, mflux, FFmpeg) is wrapped behind a small interface; tests replace the function via `monkeypatch`. Never hit real APIs in tests.
- **All artifacts go through `out/<run-timestamp>/`.** Stages are resumable: if an artifact exists, the stage skips itself.
- **All Python files start with `from __future__ import annotations`.** Use `pathlib.Path` for paths; never `os.path`.
- **Imports are absolute from the package root** (`from pipeline.script import …`).
