"""Confirms test infrastructure is wired up."""
from __future__ import annotations


def test_pytest_runs():
    assert 1 + 1 == 2


def test_package_importable():
    import pipeline  # noqa: F401
