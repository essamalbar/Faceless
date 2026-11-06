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


def _write_marker_err(out: Path, error: str, *, hours_ago: float = 0.5) -> None:
    ts = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)) \
        .isoformat(timespec="seconds")
    (out / "llm_fallback.json").write_text(
        json.dumps({"last_fallback_at": ts, "error": error}), encoding="utf-8")


def test_health_not_degraded_for_transient_provider_overload(client):
    # A TRANSIENT provider overload (503 / "high demand" / "temporary") that
    # recovers on its own must NOT pin the global "Lyric quality reduced"
    # banner — only a persistent failure should. Regression: a one-off 503
    # held the banner up for a full 24h even after the provider recovered.
    c, out = client
    _write_marker_err(
        out,
        "complete failed after 3 attempts: 503 UNAVAILABLE. {'error': "
        "{'code': 503, 'message': 'This model is currently experiencing high "
        "demand. Spikes in demand are usually temporary. Please try again "
        "later.', 'status': 'UNAVAILABLE'}}")
    assert c.get("/health").json()["writer_degraded"] is False


def test_health_degraded_for_persistent_quota_error(client):
    # A PERSISTENT failure (exhausted quota / credits) SHOULD show the banner —
    # the primary writer stays down until the operator acts.
    c, out = client
    _write_marker_err(out, "429 quota exhausted")
    assert c.get("/health").json()["writer_degraded"] is True
