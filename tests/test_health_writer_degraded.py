from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch, tmp_path: Path):
    """A TestClient with a fresh, empty out-root (where the LLM-fallback
    marker lives). ANTHROPIC key set so writer_tier reads 'anthropic'."""
    out = tmp_path / "out"
    out.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(out))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "stub-anthropic")
    from pipeline import api as api_mod
    return TestClient(api_mod.app), out


def _write_marker(out: Path, *, hours_ago: float) -> None:
    ts = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)) \
        .isoformat(timespec="seconds")
    (out / "llm_fallback.json").write_text(
        json.dumps({"last_fallback_at": ts, "error": "429 quota exhausted"}),
        encoding="utf-8",
    )


def test_health_writer_degraded_false_when_no_marker(client):
    c, _out = client
    r = c.get("/health")
    assert r.status_code == 200
    assert r.json()["writer_degraded"] is False


def test_health_writer_degraded_true_for_recent_fallback(client):
    c, out = client
    _write_marker(out, hours_ago=1)
    assert c.get("/health").json()["writer_degraded"] is True


def test_health_writer_degraded_false_for_stale_fallback(client):
    # A marker older than the 24h window must NOT keep /health degraded.
    # This is the bug: /health used a bare .exists() check with no age gate,
    # so a one-off fallback pinned the service to degraded forever.
    c, out = client
    _write_marker(out, hours_ago=48)
    assert c.get("/health").json()["writer_degraded"] is False
