#!/usr/bin/env bash
# Paddle sandbox smoke test harness.
#
# Once you've put your SANDBOX Paddle values in .env:
#   PADDLE_API_KEY, PADDLE_WEBHOOK_SECRET,
#   PADDLE_PRICE_STARTER, PADDLE_PRICE_CREATOR, PADDLE_PRICE_PRO
# run:  ./scripts/paddle-sandbox-test.sh
#
# It starts the API locally with PADDLE_ENV=sandbox, runs scripts/paddle_sandbox_test.py
# (checkout against Paddle sandbox + a signed webhook), and tears the server down.
# No real credits are minted; no tunnel needed.
set -uo pipefail

cd "$(dirname "$0")/.."
REPO="$(pwd)"

# --- load env ---
if [[ -f .env ]]; then set -a; source .env; set +a; fi
export PADDLE_ENV=sandbox
PORT="${HARNESS_PORT:-8073}"
export HARNESS_PORT="$PORT"

# --- preflight: the 5 required vars ---
missing=()
for v in PADDLE_API_KEY PADDLE_WEBHOOK_SECRET PADDLE_PRICE_STARTER PADDLE_PRICE_CREATOR PADDLE_PRICE_PRO; do
  [[ -z "${!v:-}" ]] && missing+=("$v")
done
if (( ${#missing[@]} )); then
  echo "Not ready — these SANDBOX values are missing from .env:"
  for v in "${missing[@]}"; do echo "  - $v"; done
  echo
  echo "Add them (Paddle dashboard → Sandbox), e.g.:"
  echo "  echo 'export PADDLE_API_KEY=...' >> .env"
  echo "  echo 'export PADDLE_WEBHOOK_SECRET=...' >> .env"
  echo "  echo 'export PADDLE_PRICE_STARTER=pri_...' >> .env"
  echo "  echo 'export PADDLE_PRICE_CREATOR=pri_...' >> .env"
  echo "  echo 'export PADDLE_PRICE_PRO=pri_...' >> .env"
  echo "then re-run this script."
  exit 2
fi

if [[ -z "${SUPABASE_URL:-}" || -z "${SUPABASE_SERVICE_ROLE_KEY:-}" ]]; then
  echo "WARN: SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set — the checkout test's"
  echo "      customer lookup needs Supabase. Make sure .env has them."
fi

LOG="$(mktemp -t paddle-harness-XXXX.log)"
echo "Starting API on :$PORT (PADDLE_ENV=sandbox), log → $LOG"
uv run uvicorn pipeline.api:app --host 127.0.0.1 --port "$PORT" > "$LOG" 2>&1 &
UVPID=$!
cleanup() { kill "$UVPID" 2>/dev/null; }
trap cleanup EXIT

# wait for health
up=0
for _ in $(seq 1 30); do
  if [[ "$(curl -s -o /dev/null -w '%{http_code}' -m 2 "http://127.0.0.1:$PORT/health" 2>/dev/null)" == "200" ]]; then up=1; break; fi
  sleep 1
done
if (( ! up )); then
  echo "API failed to start — last log lines:"; tail -20 "$LOG"; exit 1
fi
echo

uv run python scripts/paddle_sandbox_test.py
code=$?
echo
echo "(server stopped; log at $LOG)"
exit $code
