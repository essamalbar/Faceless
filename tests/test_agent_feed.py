"""Tests for Task 8: GET /agent/proposals (the A&R feed) + GET
/songs/{id}/agent-trace (the reasoning-trace read) — spec §7, §9.

Both are read-only, owner-scoped endpoints. `/agent/proposals` must show
the SAME cost figure the approve gate will charge (reuses
`_song_credit_amount`); `/songs/{id}/agent-trace` must never 500 when the
worker was killed before writing the trace file.
"""
from __future__ import annotations

import json
from pathlib import Path


def _user_root(tmp_path: Path, user_id: str) -> Path:
    return tmp_path / "out" / user_id


def _write_song_run(
    tmp_path: Path,
    user_id: str,
    run_id: str,
    *,
    source: str | None = "agent",
    artist_id: str | None = "art_x",
    self_score: float | None = 0.82,
    status: str = "awaiting_approval",
    title: str = "Test Song",
    rationale: str = "test rationale",
    trace_path: str | None = "agent_trace.json",
    video_mode: str = "static",
    quality_tier: str = "standard",
    created_at: str = "2026-09-25T00:00:00+00:00",
) -> Path:
    """Write a run dir directly on disk shaped like `queue_proposal`'s
    output (pipeline/agent.py:_write_state / _queue_proposal) — or, with
    source=None, shaped like a plain human-authored song draft. Mirrors
    tests/test_agent_decisions.py's fixture."""
    run_dir = _user_root(tmp_path, user_id) / run_id
    run_dir.mkdir(parents=True)
    state: dict = {
        "kind": "song",
        "status": status,
        "user_id": user_id,
        "theme": "a test theme",
        "video_mode": video_mode,
        "created_at": created_at,
        "title": title,
    }
    if source is not None:
        state["source"] = source
    if artist_id is not None:
        state["artist_id"] = artist_id
    if source == "agent":
        state["agent_rationale"] = rationale
        state["agent_self_score"] = self_score
        if trace_path is not None:
            state["agent_trace_path"] = trace_path
    (run_dir / "api_state.json").write_text(
        json.dumps(state, ensure_ascii=False), encoding="utf-8")
    (run_dir / "song.json").write_text(json.dumps({
        "title": title,
        "lyrics": "[Verse 1]\nline one\n[Chorus]\nhook",
        "style_prompt": "khaleeji pop, warm strings",
        "cover_prompt": "a desert night",
        "video_mode": video_mode,
        "quality_tier": quality_tier,
    }, ensure_ascii=False), encoding="utf-8")
    return run_dir


# ---------------------------------------------------------------------------
# GET /agent/proposals
# ---------------------------------------------------------------------------

def test_proposals_lists_only_agent_awaiting_approval(
    client_factory, monkeypatch, tmp_path
):
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path / "out"))
    c = client_factory(user_id="u1", role="user")

    # The one real proposal: agent + awaiting_approval.
    _write_song_run(
        tmp_path, "u1", "run-agent-pending", source="agent",
        self_score=0.91, rationale="trend is heating up",
    )
    # A human-authored draft also awaiting_approval — must NOT appear.
    _write_song_run(
        tmp_path, "u1", "run-manual-pending", source=None,
    )
    # An agent run that already moved past awaiting_approval — must NOT
    # appear.
    _write_song_run(
        tmp_path, "u1", "run-agent-done", source="agent", status="complete",
    )

    r = c.get("/agent/proposals")
    assert r.status_code == 200, r.text
    items = r.json()
    assert len(items) == 1
    item = items[0]
    assert item["run_id"] == "run-agent-pending"
    assert item["self_score"] == 0.91
    assert item["rationale"] == "trend is heating up"
    assert item["artist_id"] == "art_x"
    assert "cost_usd" in item
    assert "cost_credits" in item
    # static + standard tier == 1 credit / $0.08 per config.yaml defaults.
    assert item["cost_credits"] == 1
    assert item["cost_usd"] == 0.08


def test_proposals_owner_scoped(client_factory, monkeypatch, tmp_path):
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path / "out"))
    _write_song_run(tmp_path, "u1", "run-belongs-to-u1", source="agent")

    intruder = client_factory(user_id="u2", role="user")
    r = intruder.get("/agent/proposals")
    assert r.status_code == 200, r.text
    assert r.json() == []


def test_proposals_skips_agent_dispatch_bookkeeping_dir(
    client_factory, monkeypatch, tmp_path
):
    """The `_agent_dispatch/` scheduler-bookkeeping subtree has no top-level
    api_state.json — `_read_state` on it returns {} and must be skipped,
    never raise."""
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path / "out"))
    c = client_factory(user_id="u1", role="user")
    _write_song_run(tmp_path, "u1", "run-agent-pending", source="agent")

    dispatch_dir = _user_root(tmp_path, "u1") / "_agent_dispatch"
    dispatch_dir.mkdir(parents=True)
    (dispatch_dir / "some-artist-20260101-000000").mkdir()

    r = c.get("/agent/proposals")
    assert r.status_code == 200, r.text
    ids = [it["run_id"] for it in r.json()]
    assert ids == ["run-agent-pending"]


def test_proposals_empty_when_no_runs(client_factory, monkeypatch, tmp_path):
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path / "out"))
    c = client_factory(user_id="u1", role="user")
    r = c.get("/agent/proposals")
    assert r.status_code == 200, r.text
    assert r.json() == []


# ---------------------------------------------------------------------------
# GET /songs/{id}/agent-trace
# ---------------------------------------------------------------------------

def test_agent_trace_returns_stored_trace(client_factory, monkeypatch, tmp_path):
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path / "out"))
    c = client_factory(user_id="u1", role="user")
    run_dir = _write_song_run(tmp_path, "u1", "run-with-trace", source="agent")
    trace = {"tool_calls": [{"tool": "get_trends", "result": "ok"}]}
    (run_dir / "agent_trace.json").write_text(
        json.dumps(trace), encoding="utf-8")

    r = c.get("/songs/run-with-trace/agent-trace")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["available"] is True
    assert body["trace"] == trace


def test_agent_trace_missing_file_is_graceful(client_factory, monkeypatch, tmp_path):
    """The trace path is set in state but the worker was killed before
    writing the file — must NOT 500."""
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path / "out"))
    c = client_factory(user_id="u1", role="user")
    _write_song_run(tmp_path, "u1", "run-no-trace-file", source="agent")

    r = c.get("/songs/run-no-trace-file/agent-trace")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["available"] is False
    assert body["trace"] is None


def test_agent_trace_missing_path_field_is_graceful(
    client_factory, monkeypatch, tmp_path
):
    """No agent_trace_path in state at all (e.g. an older proposal) —
    still graceful, never 500."""
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path / "out"))
    c = client_factory(user_id="u1", role="user")
    _write_song_run(
        tmp_path, "u1", "run-no-trace-field", source="agent", trace_path=None,
    )

    r = c.get("/songs/run-no-trace-field/agent-trace")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["available"] is False
    assert body["trace"] is None


def test_agent_trace_owner_scoped(client_factory, monkeypatch, tmp_path):
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path / "out"))
    owner = client_factory(user_id="u1", role="user")
    run_dir = _write_song_run(tmp_path, "u1", "run-trace-owner", source="agent")
    (run_dir / "agent_trace.json").write_text(
        json.dumps({"ok": True}), encoding="utf-8")

    intruder = client_factory(user_id="u2", role="user")
    r = intruder.get("/songs/run-trace-owner/agent-trace")
    assert r.status_code == 404

    # Positive control: the owner CAN read it — the intruder's 404 is real
    # ownership scoping, not a missing/broken route.
    r_owner = owner.get("/songs/run-trace-owner/agent-trace")
    assert r_owner.status_code == 200, r_owner.text
    assert r_owner.json()["available"] is True


def test_agent_trace_non_agent_run_is_not_found(
    client_factory, monkeypatch, tmp_path
):
    """A plain human-authored song has no agent-trace concept at all —
    404, distinct from the 200/available:false "not written yet" case."""
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path / "out"))
    c = client_factory(user_id="u1", role="user")
    _write_song_run(tmp_path, "u1", "run-manual", source=None)

    r = c.get("/songs/run-manual/agent-trace")
    assert r.status_code == 404


def test_agent_trace_missing_run_is_404(client_factory, monkeypatch, tmp_path):
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path / "out"))
    c = client_factory(user_id="u1", role="user")
    r = c.get("/songs/does-not-exist/agent-trace")
    assert r.status_code == 404
