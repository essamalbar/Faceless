"""Tests for pipeline.spawn_backends — pluggable subprocess vs Cloud Run Jobs."""
from __future__ import annotations
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from pipeline.spawn_backends import (
    LocalSubprocessBackend,
    CloudRunJobsBackend,
    select_backend,
)


def test_select_backend_default_is_local(monkeypatch):
    """Without FACELESS_SPAWN_BACKEND set, the default is the local backend."""
    monkeypatch.delenv("FACELESS_SPAWN_BACKEND", raising=False)
    backend = select_backend()
    assert isinstance(backend, LocalSubprocessBackend)


def test_select_backend_local_explicit(monkeypatch):
    monkeypatch.setenv("FACELESS_SPAWN_BACKEND", "local")
    assert isinstance(select_backend(), LocalSubprocessBackend)


def test_select_backend_cloudrun_jobs(monkeypatch):
    monkeypatch.setenv("FACELESS_SPAWN_BACKEND", "cloudrun_jobs")
    monkeypatch.setenv("FACELESS_CLOUD_RUN_JOB_NAME", "faceless-pipeline")
    monkeypatch.setenv("FACELESS_CLOUD_RUN_REGION", "us-central1")
    monkeypatch.setenv("FACELESS_GCP_PROJECT", "test-project")
    backend = select_backend()
    assert isinstance(backend, CloudRunJobsBackend)


def test_select_backend_cloudrun_jobs_missing_config_raises(monkeypatch):
    """Cloud Run backend requires three env vars — fail fast at boot if any are missing."""
    monkeypatch.setenv("FACELESS_SPAWN_BACKEND", "cloudrun_jobs")
    monkeypatch.delenv("FACELESS_CLOUD_RUN_JOB_NAME", raising=False)
    with pytest.raises(RuntimeError):
        select_backend()


def test_select_backend_unknown_raises(monkeypatch):
    monkeypatch.setenv("FACELESS_SPAWN_BACKEND", "totally-not-a-real-backend")
    with pytest.raises(ValueError):
        select_backend()


def test_local_backend_spawns_subprocess(tmp_path, monkeypatch):
    """LocalSubprocessBackend writes to api_subprocess.log + returns a PID
    that's currently alive."""
    # Use a no-op subprocess command so we don't actually run run.py
    from pipeline.spawn_backends import LocalSubprocessBackend

    # Patch the runpy path to a benign shell command instead
    backend = LocalSubprocessBackend()

    captured: dict = {}

    def fake_popen(cmd, *, cwd, stdout, stderr, env, start_new_session):
        class _Proc:
            pid = 99999
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        captured["start_new_session"] = start_new_session
        return _Proc()

    monkeypatch.setattr("pipeline.spawn_backends.subprocess.Popen", fake_popen)

    pid = backend.spawn(
        args=["--shorts", "--theme", "x"],
        run_dir=tmp_path,
        runpy_path=Path("/fake/run.py"),
        repo_root=Path("/fake/repo"),
    )
    assert pid == 99999
    # Check the command structure (sys.executable, run.py path, args)
    assert "--shorts" in captured["cmd"]
    assert str(Path("/fake/run.py")) in captured["cmd"]
    assert captured["cwd"] == "/fake/repo"
    assert captured["start_new_session"] is True
    # Log file was opened
    assert (tmp_path / "api_subprocess.log").exists()


def test_cloudrun_jobs_backend_calls_run_job(tmp_path, monkeypatch):
    """CloudRunJobsBackend calls JobsClient.run_job with the right path and
    overrides, and returns a non-zero pseudo-pid derived from the execution
    resource name.

    The implementation uses google-cloud-run's gRPC client (no `gcloud` CLI
    needed), which picks up the container's workload identity automatically.
    """
    backend = CloudRunJobsBackend(
        job_name="faceless-pipeline",
        region="us-central1",
        project="test-project",
    )

    captured: dict = {}

    class _FakeMetadata:
        name = (
            "projects/test-project/locations/us-central1/"
            "jobs/faceless-pipeline/executions/abc123"
        )

    class _FakeOperation:
        def __init__(self):
            self.metadata = _FakeMetadata()
            self.operation = type("_", (), {"name": "lro/fake-name"})()

    class _FakeJobsClient:
        def run_job(self, *, request):
            captured["request"] = request
            return _FakeOperation()

    from pipeline import spawn_backends as sb_mod

    class _FakeRunV2:
        JobsClient = _FakeJobsClient

        class RunJobRequest:
            def __init__(self, *, name, overrides):
                self.name = name
                self.overrides = overrides

            class Overrides:
                def __init__(self, *, container_overrides):
                    self.container_overrides = container_overrides

                class ContainerOverride:
                    def __init__(self, *, env):
                        self.env = env

        class EnvVar:
            def __init__(self, *, name, value):
                self.name = name
                self.value = value

    monkeypatch.setattr(
        "google.cloud.run_v2", _FakeRunV2, raising=False,
    )
    # The lazy `from google.cloud import run_v2` inside spawn() needs the
    # parent package present; install the fake into sys.modules so the
    # import resolves to our stub.
    import sys
    sys.modules["google.cloud.run_v2"] = _FakeRunV2
    sys.modules["google.cloud"] = type(sb_mod)("google.cloud")
    sys.modules["google.cloud"].run_v2 = _FakeRunV2

    pid = backend.spawn(
        args=["--shorts", "--theme", "folkloric"],
        run_dir=tmp_path,
        runpy_path=Path("/fake/run.py"),
        repo_root=Path("/fake/repo"),
    )

    req = captured["request"]
    assert req.name == (
        "projects/test-project/locations/us-central1/jobs/faceless-pipeline"
    )
    # FACELESS_RUN_ARGS env var carries the args, joined by U+001E
    co = req.overrides.container_overrides[0]
    args_var = next(e for e in co.env if e.name == "FACELESS_RUN_ARGS")
    assert "--shorts" in args_var.value
    assert "folkloric" in args_var.value
    assert "\x1e" in args_var.value  # delimiter intact
    # PID is non-zero (some integer derived from the execution resource name)
    assert pid > 0


def test_cloudrun_jobs_backend_propagates_run_job_failure(tmp_path, monkeypatch):
    """If the run_job RPC fails, the spawn raises the underlying error."""
    backend = CloudRunJobsBackend(
        job_name="faceless-pipeline",
        region="us-central1",
        project="test-project",
    )

    class _FakeJobsClient:
        def run_job(self, *, request):
            raise RuntimeError("Permission denied (workload identity)")

    class _FakeRunV2:
        JobsClient = _FakeJobsClient

        class RunJobRequest:
            def __init__(self, *, name, overrides):
                self.name = name
                self.overrides = overrides

            class Overrides:
                def __init__(self, *, container_overrides):
                    self.container_overrides = container_overrides

                class ContainerOverride:
                    def __init__(self, *, env):
                        self.env = env

        class EnvVar:
            def __init__(self, *, name, value):
                self.name = name
                self.value = value

    import sys
    sys.modules["google.cloud.run_v2"] = _FakeRunV2
    sys.modules["google.cloud"] = type(sys)("google.cloud")
    sys.modules["google.cloud"].run_v2 = _FakeRunV2

    with pytest.raises(RuntimeError) as exc_info:
        backend.spawn(
            args=["--shorts"],
            run_dir=tmp_path,
            runpy_path=Path("/fake/run.py"),
            repo_root=Path("/fake/repo"),
        )
    assert "Permission denied" in str(exc_info.value)


def test_cloudrun_jobs_is_alive_returns_false_for_completed_execution(tmp_path, monkeypatch):
    """A Cloud Run Job execution that finished (succeeded/failed/cancelled) must
    report is_alive=False. proto-plus converts Timestamp → datetime, breaking
    the old completion_time.seconds check — use the lifecycle counters instead."""
    backend = CloudRunJobsBackend(
        job_name="faceless-pipeline", region="us-central1", project="test",
    )
    # Stash a fake api_state.json
    state_path = tmp_path / "api_state.json"
    state_path.write_text('{"cloudrun_execution_name": "projects/x/locations/us-central1/jobs/y/executions/z"}')

    class _FakeExecution:
        succeeded_count = 1
        failed_count = 0
        cancelled_count = 0

    class _FakeClient:
        def get_execution(self, *, name):
            return _FakeExecution()

    class _FakeRunV2:
        ExecutionsClient = _FakeClient

    import sys
    sys.modules["google.cloud.run_v2"] = _FakeRunV2
    sys.modules["google.cloud"] = type(sys)("google.cloud")
    sys.modules["google.cloud"].run_v2 = _FakeRunV2

    assert backend.is_alive(pid=999, run_dir=tmp_path) is False


def test_cloudrun_jobs_is_alive_returns_true_for_running_execution(tmp_path, monkeypatch):
    """An execution that's still provisioning or running (no terminal counters yet)
    must report is_alive=True — the UI shouldn't flip to 'failed' during cold-start."""
    backend = CloudRunJobsBackend(
        job_name="faceless-pipeline", region="us-central1", project="test",
    )
    state_path = tmp_path / "api_state.json"
    state_path.write_text('{"cloudrun_execution_name": "projects/x/locations/us-central1/jobs/y/executions/z"}')

    class _FakeExecution:
        succeeded_count = 0
        failed_count = 0
        cancelled_count = 0
        # running_count > 0, or just provisioning — either way, no terminal state

    class _FakeClient:
        def get_execution(self, *, name):
            return _FakeExecution()

    class _FakeRunV2:
        ExecutionsClient = _FakeClient

    import sys
    sys.modules["google.cloud.run_v2"] = _FakeRunV2
    sys.modules["google.cloud"] = type(sys)("google.cloud")
    sys.modules["google.cloud"].run_v2 = _FakeRunV2

    assert backend.is_alive(pid=999, run_dir=tmp_path) is True
