"""Run logger tests."""
from __future__ import annotations

from pathlib import Path

from pipeline.runlog import RunLog


def test_writes_to_log_file(tmp_run_dir: Path):
    log = RunLog(tmp_run_dir)
    log.info("starting")
    log.close()
    text = (tmp_run_dir / "run.log").read_text()
    assert "starting" in text


def test_stage_context_records_duration(tmp_run_dir: Path):
    log = RunLog(tmp_run_dir)
    with log.stage("script"):
        pass
    log.close()
    text = (tmp_run_dir / "run.log").read_text()
    assert "stage start: script" in text
    assert "stage end: script" in text
    assert "duration_ms=" in text


def test_stage_records_failure_with_exception(tmp_run_dir: Path):
    import pytest
    log = RunLog(tmp_run_dir)
    with pytest.raises(RuntimeError):
        with log.stage("voice"):
            raise RuntimeError("boom")
    log.close()
    text = (tmp_run_dir / "run.log").read_text()
    assert "stage failed: voice" in text
    assert "RuntimeError: boom" in text
