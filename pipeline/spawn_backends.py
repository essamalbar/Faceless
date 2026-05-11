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
    """Trigger a Cloud Run Job execution via the Google Cloud Run REST API.

    The Job container must already be deployed (see deploy/cloud-run-job.yaml
    or scripts/setup-cloud-run.sh). It runs the same image as the API
    service, just with `python run.py` as the entrypoint instead of uvicorn.
    Pipeline args are passed via the FACELESS_RUN_ARGS env var, which the
    entrypoint script splits on U+001E and feeds to run.py.

    Originally this shelled out to `gcloud run jobs execute`, but `gcloud`
    isn't installed in the slim Python image we ship for Cloud Run. The
    google-cloud-run Python client uses gRPC under the hood and picks up
    the container's workload identity automatically — no key file needed.

    The 'pid' returned is a stable hash of the execution name. The API's
    _process_alive check needs a corresponding cloudrun-aware liveness
    probe (separate concern).
    """

    def __init__(self, *, job_name: str, region: str, project: str) -> None:
        self.job_name = job_name
        self.region = region
        self.project = project

    def spawn(self, *, args, run_dir, runpy_path, repo_root) -> int:
        # Lazy import: keeps the dep from being a hard requirement of the
        # local-subprocess path used by tests + dev.
        from google.cloud import run_v2

        run_args_str = "\x1e".join(args)

        client = run_v2.JobsClient()
        job_path = (
            f"projects/{self.project}/locations/{self.region}"
            f"/jobs/{self.job_name}"
        )

        overrides = run_v2.RunJobRequest.Overrides(
            container_overrides=[
                run_v2.RunJobRequest.Overrides.ContainerOverride(
                    env=[
                        run_v2.EnvVar(
                            name="FACELESS_RUN_ARGS",
                            value=run_args_str,
                        ),
                        run_v2.EnvVar(
                            name="FACELESS_RUN_DIR",
                            value=str(run_dir),
                        ),
                    ],
                ),
            ],
        )

        # Fire-and-forget — we don't call operation.result(), which would
        # block until the Job finishes. The returned LRO has metadata
        # containing the execution resource (projects/.../executions/<id>),
        # which we hash into a stable pseudo-pid for the API state machine.
        operation = client.run_job(
            request=run_v2.RunJobRequest(name=job_path, overrides=overrides),
        )

        if operation.metadata and operation.metadata.name:
            execution_name = operation.metadata.name
        else:
            execution_name = operation.operation.name

        h = sha256(execution_name.encode()).hexdigest()
        pid = int(h[:8], 16) or 1
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
