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
    to check liveness via `is_alive`."""

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
        cloud backends it's a stable hash of the execution name."""

    @abstractmethod
    def is_alive(self, *, pid: int | None, run_dir: Path) -> bool:
        """Is the spawned worker still running?

        `run_dir` is passed so backends can read additional state they wrote
        during spawn (e.g. the Cloud Run execution resource name stored in
        api_state.json).
        """


class LocalSubprocessBackend(SpawnBackend):
    """Spawn `run.py` as a child process on the same host. Original behavior."""

    def is_alive(self, *, pid, run_dir) -> bool:
        if not pid:
            return False
        # On Linux + macOS, OS pids are signed int (pid_t), max ~2**31-1.
        # Cloud-run-jobs backend writes a 64-bit hash of the execution
        # name as its "pid" — that overflows os.waitpid / os.kill with
        # an OverflowError that crashes /delete and /cancel endpoints
        # (real production bug). Refuse anything out of int range.
        if not isinstance(pid, int) or pid <= 0 or pid > 2**31 - 1:
            return False
        try:
            # WNOHANG = don't block. Reaps any single zombie child we own.
            os.waitpid(pid, os.WNOHANG)
        except (ChildProcessError, OSError, OverflowError):
            pass
        try:
            os.kill(pid, 0)
            return True
        except (OSError, OverflowError):
            return False

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

        # Persist the execution resource name in api_state.json so is_alive
        # can query the Cloud Run Executions API later. Merge — don't clobber
        # any state the API has already written (or might write right after
        # we return).
        self._stash_execution_name(run_dir, execution_name)

        h = sha256(execution_name.encode()).hexdigest()
        pid = int(h[:8], 16) or 1
        return pid

    @staticmethod
    def _stash_execution_name(run_dir: Path, execution_name: str) -> None:
        """Merge `cloudrun_execution_name` into api_state.json."""
        state_path = run_dir / "api_state.json"
        state: dict = {}
        if state_path.exists():
            try:
                state = json.loads(state_path.read_text(encoding="utf-8"))
            except Exception:
                state = {}
        state["cloudrun_execution_name"] = execution_name
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def is_alive(self, *, pid, run_dir) -> bool:
        """Query the Cloud Run Executions API to see if the worker is
        still going. The `pid` is ignored — we use the resource name
        stashed in api_state.json instead, because the pid is a hash."""
        state_path = run_dir / "api_state.json"
        if not state_path.exists():
            return False
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except Exception:
            return False
        exec_name = state.get("cloudrun_execution_name")
        if not exec_name:
            return False

        from google.cloud import run_v2
        client = run_v2.ExecutionsClient()
        try:
            execution = client.get_execution(name=exec_name)
        except Exception:
            # API call failed — be conservative and assume it's still alive
            # so we don't show "failed" for a transient API hiccup. The next
            # poll will re-check.
            return True

        # Use the lifecycle counters, not completion_time. Reason: proto-plus
        # auto-converts Timestamp to `datetime`, which has no `.seconds` attr —
        # our old `getattr(completion, "seconds", None) == None` check then
        # incorrectly returned True for every completed execution.
        # The terminal-state counters are robust across proto-plus versions:
        # any of succeeded/failed/cancelled being >0 means the worker is done.
        succeeded = getattr(execution, "succeeded_count", 0) or 0
        failed = getattr(execution, "failed_count", 0) or 0
        cancelled = getattr(execution, "cancelled_count", 0) or 0
        if succeeded > 0 or failed > 0 or cancelled > 0:
            return False
        # Otherwise: provisioning, pending, or actively running. All count
        # as alive — we don't want to flip the UI to "failed" during cold-start.
        return True


def select_backend() -> SpawnBackend:
    """Pick the spawn backend based on env vars. Called at API startup."""
    raw = os.environ.get("FACELESS_SPAWN_BACKEND")
    if raw is None:
        # Unset. On Cloud Run (K_SERVICE is set) the in-container `local`
        # backend would spawn every user's render inside the single API
        # container — one OOM/crash takes everyone down. Fail closed and force
        # an explicit choice rather than silently defaulting to `local`.
        if os.environ.get("K_SERVICE"):
            raise RuntimeError(
                "FACELESS_SPAWN_BACKEND is unset on Cloud Run "
                "(K_SERVICE detected). Refusing to run renders inside the API "
                "container. Set FACELESS_SPAWN_BACKEND=cloudrun_jobs."
            )
        return LocalSubprocessBackend()

    backend_name = raw.strip().lower()

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
