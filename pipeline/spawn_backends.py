"""Pluggable spawn backends for the API server.

The API can run pipelines two ways:

  - LocalSubprocessBackend: spawn `run.py` as a child process on the same
    machine. This is the original behavior — used in tests, in local dev,
    and on a single-VM deployment (the user's Mac, Oracle Always-Free, etc.).

  - CloudRunJobsBackend: invoke `gcloud run jobs execute` to run the pipeline
    in a separate Cloud Run Job container. The API's host machine never runs
    `run.py` directly. Used when FACELESS_SPAWN_BACKEND=cloudrun_jobs.

Selection is driven by env var FACELESS_SPAWN_BACKEND (default: 'local').
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from abc import ABC, abstractmethod
from hashlib import sha256
from pathlib import Path


class SpawnBackend(ABC):
    """Common interface — given pipeline args + a run_dir, kick off the
    pipeline somewhere and return an identifier that the API can later use
    to check liveness via _process_alive."""

    @abstractmethod
    def spawn(
        self,
        *,
        args: list[str],
        run_dir: Path,
        runpy_path: Path,
        repo_root: Path,
    ) -> int:
        """Returns a 'pid' integer. For local backends it's the OS pid; for
        cloud backends it's a stable hash of the execution name (the API
        only uses it for boolean `_process_alive` checks)."""


class LocalSubprocessBackend(SpawnBackend):
    """Spawn `run.py` as a child process on the same host. Original behavior."""

    def spawn(self, *, args, run_dir, runpy_path, repo_root) -> int:
        log_path = run_dir / "api_subprocess.log"
        log_fh = open(log_path, "ab")
        try:
            proc = subprocess.Popen(
                [sys.executable, str(runpy_path), *args],
                cwd=str(repo_root),
                stdout=log_fh,
                stderr=subprocess.STDOUT,
                env=os.environ.copy(),
                start_new_session=True,
            )
        finally:
            log_fh.close()
        return proc.pid


class CloudRunJobsBackend(SpawnBackend):
    """Trigger a Cloud Run Job execution via `gcloud run jobs execute`.

    The Job container must already be deployed (see deploy/cloud-run-job.yaml
    or the gcloud commands in docs/DEPLOY-CLOUDRUN.md). It runs the same
    image as the API service, just with `python run.py` as the entrypoint
    instead of uvicorn. Pipeline args are passed via the FACELESS_RUN_ARGS
    env var so the Job's CMD reads them on startup.

    The 'pid' returned is a stable hash of the execution name — there's no
    real OS pid since the work runs in a different VM. The API's
    _process_alive check needs a corresponding cloudrun-aware liveness
    probe (handled separately).
    """

    def __init__(self, *, job_name: str, region: str, project: str) -> None:
        self.job_name = job_name
        self.region = region
        self.project = project

    def spawn(self, *, args, run_dir, runpy_path, repo_root) -> int:
        # Pack args into a single env var the Job's entrypoint reads.
        # We use a delimiter that's unlikely to appear in any of our flags.
        run_args_str = "\x1e".join(args)

        cmd = [
            "gcloud", "run", "jobs", "execute", self.job_name,
            f"--region={self.region}",
            f"--project={self.project}",
            f"--update-env-vars=FACELESS_RUN_ARGS={run_args_str},FACELESS_RUN_DIR={run_dir}",
            "--format=json",
            "--async",  # don't block — return immediately with the execution metadata
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"gcloud run jobs execute failed (rc={result.returncode}): "
                f"{result.stderr.strip() or result.stdout.strip()}"
            )

        # Derive a stable integer "pid" from the execution name so the API's
        # state machine works unchanged. Liveness is checked separately
        # via gcloud (not in this task).
        # The execution name is in the JSON output's metadata.name field.
        try:
            execution = json.loads(result.stdout)
            execution_name = execution.get("metadata", {}).get("name", "")
        except json.JSONDecodeError:
            execution_name = result.stdout.strip()

        # Hash to a non-zero integer
        h = sha256(execution_name.encode()).hexdigest()
        pid = int(h[:8], 16) or 1   # never return 0 (treated as "no process")
        return pid


def select_backend() -> SpawnBackend:
    """Pick the spawn backend based on env vars. Called at API startup."""
    backend_name = os.environ.get("FACELESS_SPAWN_BACKEND", "local").strip().lower()

    if backend_name == "local":
        return LocalSubprocessBackend()

    if backend_name == "cloudrun_jobs":
        job_name = os.environ.get("FACELESS_CLOUD_RUN_JOB_NAME", "").strip()
        region = os.environ.get("FACELESS_CLOUD_RUN_REGION", "").strip()
        project = os.environ.get("FACELESS_GCP_PROJECT", "").strip()
        missing = [
            n for n, v in (
                ("FACELESS_CLOUD_RUN_JOB_NAME", job_name),
                ("FACELESS_CLOUD_RUN_REGION", region),
                ("FACELESS_GCP_PROJECT", project),
            ) if not v
        ]
        if missing:
            raise RuntimeError(
                f"FACELESS_SPAWN_BACKEND=cloudrun_jobs requires env vars: "
                f"{', '.join(missing)}"
            )
        return CloudRunJobsBackend(
            job_name=job_name, region=region, project=project,
        )

    raise ValueError(
        f"unknown FACELESS_SPAWN_BACKEND: {backend_name!r} "
        f"(expected 'local' or 'cloudrun_jobs')"
    )
