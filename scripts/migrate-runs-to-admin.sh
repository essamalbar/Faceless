#!/usr/bin/env bash
# scripts/migrate-runs-to-admin.sh — one-shot mover for legacy out/<timestamp>/
# directories into the new per-user layout (out/admin/<timestamp>/).
#
# Background (B2): every endpoint now scopes file paths under
# /mnt/runs/{user.id}/{run_id}/. The CLI and old API runs were created at
# out/<timestamp>/ — those become invisible to the API after the upgrade
# unless they're nested under out/admin/.
#
# Idempotent: re-runs skip directories that are already nested under
# out/admin/, out/tests/, or any other per-user directory.
set -euo pipefail

OUT_ROOT="${FACELESS_OUT_ROOT:-out}"

if [ ! -d "$OUT_ROOT" ]; then
  echo "No $OUT_ROOT/ directory found — nothing to migrate."
  exit 0
fi

mkdir -p "$OUT_ROOT/admin"

moved=0
for d in "$OUT_ROOT"/*/; do
  [ -d "$d" ] || continue
  name=$(basename "$d")
  # Skip per-user dirs and known non-run dirs
  case "$name" in
    admin|tests|.*) continue ;;
  esac
  # Only move directories whose name starts with 4 digits (timestamp like 2026-)
  if [[ "$name" =~ ^[0-9]{4} ]]; then
    mv "$d" "$OUT_ROOT/admin/$name"
    echo "  -> moved $name"
    moved=$((moved + 1))
  fi
done

echo "Migrated $moved runs into $OUT_ROOT/admin/."
