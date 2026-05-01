"""Shared pytest fixtures and fakes for pipeline tests."""
from __future__ import annotations

import pytest
from pathlib import Path


@pytest.fixture
def tmp_run_dir(tmp_path: Path) -> Path:
    """A temporary per-run output directory."""
    run_dir = tmp_path / "run-test"
    run_dir.mkdir()
    return run_dir


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"
