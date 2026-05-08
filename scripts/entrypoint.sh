#!/usr/bin/env bash
# Container entrypoint — picks mode based on FACELESS_CONTAINER_MODE.
#
#   api    → run uvicorn on port 8000, serving the FastAPI app.
#            This is the Cloud Run Service.
#
#   worker → run python run.py with args from FACELESS_RUN_ARGS env var
#            (delimited by U+001E). This is the Cloud Run Job.
#            On exit the container terminates, freeing all resources.
#
# Default: api (preserves backwards compat for `docker compose up`).
set -euo pipefail

mode="${FACELESS_CONTAINER_MODE:-api}"

case "$mode" in
  api)
    echo "[entrypoint] mode=api — starting uvicorn"
    exec uv run uvicorn pipeline.api:app --host 0.0.0.0 --port "${PORT:-8000}"
    ;;
  worker)
    echo "[entrypoint] mode=worker — running pipeline"
    if [ -z "${FACELESS_RUN_ARGS:-}" ]; then
      echo "[entrypoint] ERROR: FACELESS_RUN_ARGS env var is required in worker mode"
      exit 1
    fi
    # Split the args on U+001E (record separator) — set by CloudRunJobsBackend
    # in pipeline/spawn_backends.py to avoid issues with spaces in args.
    IFS=$'\x1e' read -ra args <<< "$FACELESS_RUN_ARGS"
    echo "[entrypoint] worker args: ${args[*]}"
    exec uv run python run.py "${args[@]}"
    ;;
  *)
    echo "[entrypoint] ERROR: unknown FACELESS_CONTAINER_MODE='$mode' (expected 'api' or 'worker')"
    exit 2
    ;;
esac
