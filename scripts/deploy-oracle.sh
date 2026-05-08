#!/usr/bin/env bash
# Deploy (or redeploy) the faceless backend on the Oracle Always-Free VM.
#
# Run this from the Oracle VM after the first `git clone`. Safe to run again
# to deploy the latest commit — idempotent.
#
# Prerequisites:
#   - .env present in the repo root with all required API keys
#   - Docker + docker compose installed (see docs/DEPLOY-ORACLE.md Step 2)
#   - CLOUDFLARE_TUNNEL_TOKEN set in .env (see docs/DEPLOY-ORACLE.md Step 3)
#
# Usage:
#   ./scripts/deploy-oracle.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# ---------------------------------------------------------------------------
# 1. Sanity checks
# ---------------------------------------------------------------------------
if [ ! -f .env ]; then
    echo "ERROR: .env not found at $REPO_ROOT/.env"
    echo "       Create it with the required keys — see docs/DEPLOY-ORACLE.md"
    exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
    echo "ERROR: docker not found. Install it first — see docs/DEPLOY-ORACLE.md Step 2"
    exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
    echo "ERROR: 'docker compose' (V2 plugin) not found."
    echo "       Install docker-compose-plugin via apt — see docs/DEPLOY-ORACLE.md Step 2"
    exit 1
fi

# ---------------------------------------------------------------------------
# 2. Pull latest code
# ---------------------------------------------------------------------------
echo "→ Pulling latest code from git"
git pull

# ---------------------------------------------------------------------------
# 3. Build + start containers (prod overlay)
# ---------------------------------------------------------------------------
echo "→ Building image and starting containers (prod overlay)"
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# ---------------------------------------------------------------------------
# 4. Wait for healthcheck
# ---------------------------------------------------------------------------
echo "→ Waiting for API healthcheck to pass (up to 60s)..."
for i in $(seq 1 60); do
    status=$(docker compose exec -T api \
        curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/healthz 2>/dev/null || echo "000")
    if [ "$status" = "200" ]; then
        echo "   healthy after ${i}s"
        break
    fi
    sleep 1
done

if [ "${status:-000}" != "200" ]; then
    echo "WARN: API did not respond healthy within 60s — check logs below"
fi

# ---------------------------------------------------------------------------
# 5. Status summary
# ---------------------------------------------------------------------------
echo ""
echo "→ Container status"
docker compose ps

echo ""
echo "→ Last 20 lines of API log"
docker compose logs api --tail 20

echo ""
echo "Done."
echo "  Check full logs : docker compose logs api -f"
echo "  Stop containers : docker compose -f docker-compose.yml -f docker-compose.prod.yml down"
echo "  Verify remotely : curl https://api.yourdomain.com/healthz"
