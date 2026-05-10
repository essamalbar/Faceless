#!/usr/bin/env bash
# Zero-config launcher. Reads .env, makes sure the API + Cloudflare Tunnel are
# running, captures the live tunnel URL, and starts Flutter with all secrets
# baked in via --dart-define so the app skips the Settings screen.
#
# Usage:
#   ./scripts/run-app.sh                 # default: chrome web
#   ./scripts/run-app.sh -d <device-id>  # forward to flutter run -d
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# ---------------------------------------------------------------------------
# 1. Load .env
# ---------------------------------------------------------------------------
if [ ! -f .env ]; then
  echo "ERROR: .env not found at $REPO_ROOT/.env" >&2
  echo "       create it with at least:  export FACELESS_API_TOKEN=..." >&2
  exit 1
fi
set -a
# shellcheck disable=SC1091
source .env
set +a

if [ -z "${FACELESS_API_TOKEN:-}" ]; then
  echo "ERROR: FACELESS_API_TOKEN not set in .env" >&2
  echo "       run:  echo \"export FACELESS_API_TOKEN=\$(openssl rand -hex 32)\" >> .env" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# 2. Make sure the API server is running on :8000
# ---------------------------------------------------------------------------
API_PORT=8000
if curl -sf "http://127.0.0.1:${API_PORT}/healthz" >/dev/null 2>&1; then
  echo "[ok]    API already running on :${API_PORT}"
else
  echo "[boot]  starting API on :${API_PORT}"
  nohup uv run uvicorn pipeline.api:app --host 0.0.0.0 --port "${API_PORT}" \
      > /tmp/faceless-api.log 2>&1 &
  # Wait until /healthz answers
  for _ in $(seq 1 20); do
    sleep 1
    curl -sf "http://127.0.0.1:${API_PORT}/healthz" >/dev/null 2>&1 && break
  done
  if ! curl -sf "http://127.0.0.1:${API_PORT}/healthz" >/dev/null 2>&1; then
    echo "ERROR: API server failed to start. Log:" >&2
    tail -20 /tmp/faceless-api.log >&2
    exit 1
  fi
  echo "[ok]    API responding"
fi

# ---------------------------------------------------------------------------
# 3. Pick the public URL.
#
# Resolution order:
#   1. FACELESS_API_URL in .env (e.g. a permanent Tailscale Funnel URL).
#      Best for production use — never changes between launches.
#   2. Active Tailscale Funnel pointing at this port (read from `tailscale
#      funnel status`). Re-uses an existing funnel if one is already on.
#   3. Cloudflare quick tunnel as last-resort fallback.
# ---------------------------------------------------------------------------
TUNNEL_URL=""

if [ -n "${FACELESS_API_URL:-}" ]; then
  TUNNEL_URL="${FACELESS_API_URL%/}"
  echo "[ok]    Using FACELESS_API_URL from .env: ${TUNNEL_URL}"
fi

# Probe Tailscale Funnel even if .env didn't set FACELESS_API_URL
if [ -z "${TUNNEL_URL}" ] && command -v tailscale >/dev/null 2>&1; then
  TS_URL=$(tailscale funnel status 2>/dev/null \
           | grep -oE 'https://[-a-z0-9.]+\.ts\.net' | head -1 || true)
  if [ -n "${TS_URL}" ]; then
    TUNNEL_URL="${TS_URL}"
    echo "[ok]    Tailscale Funnel already up: ${TUNNEL_URL}"
  fi

  # If Tailscale is signed in but Funnel is OFF (typical state after Mac
  # reboot — Tailscale.app starts on login but doesn't restore funnel
  # state), bring it back up automatically.
  if [ -z "${TUNNEL_URL}" ]; then
    TS_LOGGED_IN=$(tailscale status --json 2>/dev/null \
                   | python3 -c "import json,sys; s=json.load(sys.stdin); print('1' if (s.get('Self') or {}).get('Online') else '')" 2>/dev/null || true)
    if [ "${TS_LOGGED_IN}" = "1" ]; then
      echo "[boot]  Tailscale signed in but Funnel is off — re-enabling…"
      tailscale funnel --bg --yes "${API_PORT}" >/dev/null 2>&1 || true
      sleep 1
      TS_URL=$(tailscale funnel status 2>/dev/null \
               | grep -oE 'https://[-a-z0-9.]+\.ts\.net' | head -1 || true)
      if [ -n "${TS_URL}" ]; then
        TUNNEL_URL="${TS_URL}"
        echo "[ok]    Tailscale Funnel up: ${TUNNEL_URL}"
      fi
    fi
  fi
fi

# Cloudflare quick-tunnel fallback
TUNNEL_LOG=/tmp/cloudflared.log
if [ -z "${TUNNEL_URL}" ]; then
  if pgrep -f "cloudflared tunnel.*:${API_PORT}" >/dev/null 2>&1; then
    TUNNEL_URL=$(grep -oE 'https://[-a-z0-9]+\.trycloudflare\.com' "${TUNNEL_LOG}" 2>/dev/null | tail -1 || true)
    [ -n "${TUNNEL_URL}" ] && echo "[ok]    Cloudflare Tunnel already up: ${TUNNEL_URL}"
  fi
fi

if [ -z "${TUNNEL_URL}" ]; then
  if ! command -v cloudflared >/dev/null 2>&1; then
    echo "ERROR: no tunnel configured. Either:" >&2
    echo "  1. Set FACELESS_API_URL in .env to a permanent URL (Tailscale Funnel recommended)" >&2
    echo "  2. Install cloudflared:  brew install cloudflared" >&2
    exit 1
  fi
  echo "[boot]  starting Cloudflare quick tunnel (fallback)..."
  pkill -f "cloudflared tunnel.*:${API_PORT}" 2>/dev/null || true
  sleep 1
  # Truncate the log so we don't grep up a stale URL from a previous tunnel
  : > "${TUNNEL_LOG}"
  nohup cloudflared tunnel --url "http://localhost:${API_PORT}" \
      > "${TUNNEL_LOG}" 2>&1 &
  for _ in $(seq 1 30); do
    sleep 1
    TUNNEL_URL=$(grep -oE 'https://[-a-z0-9]+\.trycloudflare\.com' "${TUNNEL_LOG}" | tail -1 || true)
    [ -n "${TUNNEL_URL}" ] && break
  done
  if [ -z "${TUNNEL_URL:-}" ]; then
    echo "ERROR: cloudflared did not produce a URL. Log:" >&2
    tail -20 "${TUNNEL_LOG}" >&2
    exit 1
  fi
  echo "[ok]    Cloudflare Tunnel up: ${TUNNEL_URL}"
fi

# ---------------------------------------------------------------------------
# 4. Verify the tunnel actually reaches the API (auth round-trip)
# ---------------------------------------------------------------------------
if ! curl -sf -H "Authorization: Bearer ${FACELESS_API_TOKEN}" \
       "${TUNNEL_URL}/runs" >/dev/null; then
  echo "WARN:   tunnel→API auth check failed; the app may show a connection error" >&2
else
  echo "[ok]    Tunnel→API authenticated round-trip works"
fi

# ---------------------------------------------------------------------------
# 5. Run Flutter with secrets baked in via --dart-define
# ---------------------------------------------------------------------------
DEVICE="chrome"
EXTRA_ARGS=()
while [ $# -gt 0 ]; do
  case "$1" in
    -d|--device-id)
      DEVICE="$2"; shift 2 ;;
    *)
      EXTRA_ARGS+=("$1"); shift ;;
  esac
done

echo "[boot]  flutter run -d ${DEVICE}"
echo "        URL:        ${TUNNEL_URL}"
echo "        Service token: ${FACELESS_API_TOKEN:0:8}… (legacy/CLI fallback)"
if [ -n "${SUPABASE_URL:-}" ] && [ -n "${SUPABASE_ANON_KEY:-}" ]; then
  echo "        Supabase:   ${SUPABASE_URL} (sign-in screen will load)"
else
  echo "        Supabase:   not configured — set SUPABASE_URL + SUPABASE_ANON_KEY in .env"
fi
# `${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}` is a bash idiom for "expand the array
# only if it has elements" — necessary under `set -u` since an empty array
# is treated as unbound and would otherwise abort.
exec flutter run -d "${DEVICE}" \
  --dart-define="FACELESS_API_URL=${TUNNEL_URL}" \
  --dart-define="FACELESS_API_TOKEN=${FACELESS_API_TOKEN}" \
  --dart-define="SUPABASE_URL=${SUPABASE_URL:-}" \
  --dart-define="SUPABASE_ANON_KEY=${SUPABASE_ANON_KEY:-}" \
  ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}
