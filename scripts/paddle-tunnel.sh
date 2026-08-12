#!/usr/bin/env bash
# Paddle REAL-webhook test tunnel.
#
# Exposes your local /paddle/webhook on a public https URL (Cloudflare quick
# tunnel) so a real Paddle SANDBOX purchase sends a real, Paddle-signed webhook
# to your machine — proving end-to-end that Paddle's signing secret matches your
# PADDLE_WEBHOOK_SECRET and that a payment actually grants credits.
#
# Usage (run in your own terminal; leave it running):
#   ./scripts/paddle-tunnel.sh
# Then: paste the printed URL into Paddle → Sandbox → Developer Tools →
# Notifications (your destination's URL), do a sandbox checkout with test card
# 4242 4242 4242 4242, and watch the log below for POST /paddle/webhook 200.
# Ctrl-C stops both the API and the tunnel.
set -uo pipefail

cd "$(dirname "$0")/.."

if [[ -f .env ]]; then set -a; source .env; set +a; fi
export PADDLE_ENV=sandbox
PORT="${HARNESS_PORT:-8073}"

# --- preflight ---
if ! command -v cloudflared >/dev/null 2>&1; then
  echo "cloudflared is not installed. Install it, then re-run:"
  echo "  macOS:  brew install cloudflared"
  echo "  (or)    https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/"
  exit 3
fi
missing=()
for v in PADDLE_API_KEY PADDLE_WEBHOOK_SECRET PADDLE_PRICE_STARTER PADDLE_PRICE_CREATOR PADDLE_PRICE_PRO; do
  [[ -z "${!v:-}" ]] && missing+=("$v")
done
if (( ${#missing[@]} )); then
  echo "Missing SANDBOX values in .env: ${missing[*]}"
  echo "Add them (see ./scripts/paddle-sandbox-test.sh output) and re-run."
  exit 2
fi

UV_LOG="$(mktemp -t paddle-tunnel-api-XXXX.log)"
CF_LOG="$(mktemp -t paddle-tunnel-cf-XXXX.log)"
UVPID=""; CFPID=""
cleanup() { [[ -n "$CFPID" ]] && kill "$CFPID" 2>/dev/null; [[ -n "$UVPID" ]] && kill "$UVPID" 2>/dev/null; }
trap cleanup EXIT INT TERM

# --- start the API (sandbox) ---
echo "Starting API on :$PORT (PADDLE_ENV=sandbox)…"
uv run uvicorn pipeline.api:app --host 127.0.0.1 --port "$PORT" > "$UV_LOG" 2>&1 &
UVPID=$!
up=0
for _ in $(seq 1 30); do
  if [[ "$(curl -s -o /dev/null -w '%{http_code}' -m 2 "http://127.0.0.1:$PORT/health" 2>/dev/null)" == "200" ]]; then up=1; break; fi
  sleep 1
done
if (( ! up )); then echo "API failed to start:"; tail -20 "$UV_LOG"; exit 1; fi

# --- start the tunnel + capture the public URL ---
echo "Opening Cloudflare tunnel…"
cloudflared tunnel --url "http://localhost:$PORT" > "$CF_LOG" 2>&1 &
CFPID=$!
URL=""
for _ in $(seq 1 40); do
  URL="$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$CF_LOG" 2>/dev/null | head -1)"
  [[ -n "$URL" ]] && break
  sleep 1
done
if [[ -z "$URL" ]]; then echo "Tunnel URL not obtained. cloudflared log:"; tail -20 "$CF_LOG"; exit 1; fi

cat <<EOF

============================================================
  Paddle sandbox webhook is now reachable at:

    ${URL}/paddle/webhook

  1) Paddle → Sandbox → Developer Tools → Notifications:
     set your destination URL to the address above and make sure
     these events are on: transaction.completed, subscription.updated,
     subscription.canceled, subscription.past_due,
     adjustment.created, adjustment.updated
  2) IMPORTANT: the destination's signing secret must equal the
     PADDLE_WEBHOOK_SECRET in your .env (else every event → 400).
  3) Do a sandbox checkout (test card 4242 4242 4242 4242, any
     future expiry / any CVC), or hit "Send test event".

  Watching for incoming webhooks (Ctrl-C to stop):
============================================================
EOF

# Stream API logs; highlight the webhook line so hits are obvious.
tail -n0 -f "$UV_LOG" | grep --line-buffered -E "paddle/webhook|$"
