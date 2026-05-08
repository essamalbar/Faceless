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


def test_cloudrun_jobs_backend_calls_gcloud(tmp_path, monkeypatch):
    """CloudRunJobsBackend invokes gcloud run jobs execute with the right args.

    The spawn returns a fake 'pid' (actually the GCP execution name's hash) so
    the API state machine doesn't need to know the difference. _process_alive
    checks via gcloud rather than os.kill — but that's a separate concern; this
    test only validates the gcloud invocation."""
    backend = CloudRunJobsBackend(
        job_name="faceless-pipeline",
        region="us-central1",
        project="test-project",
    )

    captured: dict = {}

    def fake_run(cmd, capture_output, text, check, timeout):
        captured["cmd"] = cmd
        # Return mock execution
        class _R:
            stdout = '{"metadata": {"name": "faceless-pipeline-abc123"}}\n'
            stderr = ""
            returncode = 0
        return _R()

    monkeypatch.setattr("pipeline.spawn_backends.subprocess.run", fake_run)

    pid = backend.spawn(
        args=["--shorts", "--theme", "folkloric"],
        run_dir=tmp_path,
        runpy_path=Path("/fake/run.py"),
        repo_root=Path("/fake/repo"),
    )
    cmd = captured["cmd"]
    assert "gcloud" in cmd[0]
    assert "run" in cmd
    assert "jobs" in cmd
    assert "execute" in cmd
    assert "faceless-pipeline" in cmd  # job name
    assert "--region=us-central1" in cmd or "us-central1" in cmd
    assert "--project=test-project" in cmd or "test-project" in cmd
    # Args are passed via --update-env-vars or similar
    cmd_str = " ".join(cmd)
    assert "--theme" in cmd_str or "FACELESS_RUN_ARGS" in cmd_str
    # PID is non-zero (some integer derived from the execution name)
    assert pid > 0


def test_cloudrun_jobs_backend_handles_gcloud_failure(tmp_path, monkeypatch):
    """If gcloud returns non-zero, raise an informative error."""
    backend = CloudRunJobsBackend(
        job_name="faceless-pipeline",
        region="us-central1",
        project="test-project",
    )

    def fake_run(cmd, capture_output, text, check, timeout):
        class _R:
            stdout = ""
            stderr = "ERROR: Permission denied"
            returncode = 1
        return _R()

    monkeypatch.setattr("pipeline.spawn_backends.subprocess.run", fake_run)

    with pytest.raises(RuntimeError) as exc_info:
        backend.spawn(
            args=["--shorts"],
            run_dir=tmp_path,
            runpy_path=Path("/fake/run.py"),
            repo_root=Path("/fake/repo"),
        )
    assert "Permission denied" in str(exc_info.value) or "gcloud" in str(exc_info.value).lower()
