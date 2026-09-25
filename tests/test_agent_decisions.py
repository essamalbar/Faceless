"""Tests for Task 6: POST /songs/{id}/reject + approve/reject learning-signal
recording into the per-artist agent memory store (spec §5, §7).

`approve_song` is money-adjacent — the regression test in this file
(`test_approve_records_approved_without_changing_spend`) is the load-bearing
check that the new hook is a pure additive side effect and never changes the
deduct/spawn path.
"""
from __future__ import annotations

import json
from pathlib import Path

from pipeline import agent_memory


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
) -> Path:
    """Write a run dir directly on disk shaped like `queue_proposal`'s
    output (pipeline/agent.py:_write_state call at api_state.json) — or, with
    source=None, shaped like a plain human-authored song draft."""
    run_dir = _user_root(tmp_path, user_id) / run_id
    run_dir.mkdir(parents=True)
    state: dict = {
        "kind": "song",
        "status": status,
        "user_id": user_id,
        "theme": "a test theme",
        "video_mode": "static",
        "created_at": "2026-09-25T00:00:00+00:00",
    }
    if source is not None:
        state["source"] = source
    if artist_id is not None:
        state["artist_id"] = artist_id
    if source == "agent":
        state["agent_rationale"] = "test rationale"
        state["agent_self_score"] = self_score
        state["agent_trace_path"] = "agent_trace.json"
    (run_dir / "api_state.json").write_text(
        json.dumps(state, ensure_ascii=False), encoding="utf-8")
    (run_dir / "song.json").write_text(json.dumps({
        "title": "Test Song",
        "lyrics": "[Verse 1]\nline one\n[Chorus]\nhook",
        "style_prompt": "khaleeji pop, warm strings",
        "cover_prompt": "a desert night",
        "video_mode": "static",
        "quality_tier": "standard",
    }, ensure_ascii=False), encoding="utf-8")
    return run_dir


def _read_state(run_dir: Path) -> dict:
    return json.loads((run_dir / "api_state.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# POST /songs/{id}/reject
# ---------------------------------------------------------------------------

def test_reject_marks_rejected_and_records_decision(
    client_factory, monkeypatch, tmp_path
):
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path / "out"))
    c = client_factory(user_id="u1", role="user")
    run_dir = _write_song_run(tmp_path, "u1", "run-reject-1", artist_id="art_x")

    r = c.post(f"/songs/run-reject-1/reject", json={"reason": "too sad"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "rejected"
    assert _read_state(run_dir)["status"] == "rejected"

    mem = agent_memory.load_memory(_user_root(tmp_path, "u1"), "art_x")
    assert mem["decisions"][-1]["decision"] == "rejected"
    assert mem["decisions"][-1]["reason"] == "too sad"
    assert mem["decisions"][-1]["run_id"] == "run-reject-1"
    assert mem["decisions"][-1]["self_score"] == 0.82


def test_reject_with_no_body_defaults_to_empty_reason(
    client_factory, monkeypatch, tmp_path
):
    """Body is optional (spec §7) — a bare POST with no JSON must still
    succeed, rejecting with reason=""."""
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path / "out"))
    c = client_factory(user_id="u1", role="user")
    run_dir = _write_song_run(tmp_path, "u1", "run-reject-nobody", artist_id="art_x")

    r = c.post("/songs/run-reject-nobody/reject")
    assert r.status_code == 200, r.text
    assert _read_state(run_dir)["status"] == "rejected"

    mem = agent_memory.load_memory(_user_root(tmp_path, "u1"), "art_x")
    assert mem["decisions"][-1]["decision"] == "rejected"
    assert mem["decisions"][-1]["reason"] == ""


def test_reject_requires_owner(client_factory, monkeypatch, tmp_path):
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path / "out"))
    run_dir = _write_song_run(tmp_path, "u1", "run-reject-owner", artist_id="art_x")

    intruder = client_factory(user_id="u2", role="user")
    r = intruder.post(f"/songs/run-reject-owner/reject", json={"reason": "nope"})
    assert r.status_code == 404

    # The run must be untouched by the rejected attempt.
    assert _read_state(run_dir)["status"] == "awaiting_approval"
    mem = agent_memory.load_memory(_user_root(tmp_path, "u1"), "art_x")
    assert mem["decisions"] == []


def test_reject_non_agent_run_does_not_write_memory(
    client_factory, monkeypatch, tmp_path
):
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path / "out"))
    c = client_factory(user_id="u1", role="user")
    run_dir = _write_song_run(
        tmp_path, "u1", "run-reject-manual", source=None, artist_id="art_x",
    )

    r = c.post(f"/songs/run-reject-manual/reject", json={"reason": "meh"})
    assert r.status_code == 200, r.text
    assert _read_state(run_dir)["status"] == "rejected"

    mem_path = agent_memory.memory_path(_user_root(tmp_path, "u1"), "art_x")
    assert not mem_path.exists()


def test_reject_idempotent_when_not_awaiting_approval(
    client_factory, monkeypatch, tmp_path
):
    """Mirrors approve_song's convention: a call on a run that already moved
    on returns the current state instead of erroring, and never double-writes
    a decision."""
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path / "out"))
    c = client_factory(user_id="u1", role="user")
    run_dir = _write_song_run(
        tmp_path, "u1", "run-already-generating", artist_id="art_x",
        status="generating_song",
    )

    r = c.post(f"/songs/run-already-generating/reject", json={"reason": "late"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "generating_song"
    assert _read_state(run_dir)["status"] == "generating_song"

    mem = agent_memory.load_memory(_user_root(tmp_path, "u1"), "art_x")
    assert mem["decisions"] == []


def test_reject_missing_run_is_404(client_factory, monkeypatch, tmp_path):
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path / "out"))
    c = client_factory(user_id="u1", role="user")
    r = c.post("/songs/does-not-exist/reject", json={"reason": "x"})
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# approve_song hook — MUST NOT change the deduct/spawn path
# ---------------------------------------------------------------------------

def test_approve_records_approved_without_changing_spend(
    client_factory, monkeypatch, tmp_path
):
    from pipeline import api as api_mod, credits

    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path / "out"))
    api_mod.set_spawn_fn(lambda args, run_dir: 424242)

    deduct_calls: list[dict] = []

    def spy_deduct(user, *, amount, run_id, reason):
        deduct_calls.append(
            {"user_id": user.id, "amount": amount, "run_id": run_id,
             "reason": reason})
        return 100 - amount

    monkeypatch.setattr(credits, "get_balance", lambda uid: 100)
    monkeypatch.setattr(credits, "check_or_deduct", spy_deduct)

    c = client_factory(user_id="u1", role="user")
    # A second user for the control (non-agent) approve — the per-user
    # concurrent-song cap (FACELESS_SONG_CONCURRENT_LIMIT=1) would otherwise
    # 429 a second approve for the same user once the first is generating.
    c2 = client_factory(user_id="u2", role="user")

    # Agent-sourced run.
    agent_run_dir = _write_song_run(
        tmp_path, "u1", "run-approve-agent", source="agent",
        artist_id="art_x", self_score=0.7,
    )
    r = c.post("/songs/run-approve-agent/approve")
    assert r.status_code == 200, r.text

    # Plain (non-agent) run — the control case.
    _write_song_run(
        tmp_path, "u2", "run-approve-manual", source=None, artist_id=None,
    )
    r2 = c2.post("/songs/run-approve-manual/approve")
    assert r2.status_code == 200, r2.text

    # KEY assertion: check_or_deduct was called exactly once per approve,
    # and with an IDENTICAL shape (amount, reason) for the agent run vs the
    # plain run — proving the new hook adds nothing to the spend path.
    assert len(deduct_calls) == 2
    agent_call, manual_call = deduct_calls
    assert agent_call["run_id"] == "run-approve-agent"
    assert manual_call["run_id"] == "run-approve-manual"
    assert agent_call["amount"] == manual_call["amount"]
    assert agent_call["reason"] == manual_call["reason"] == "song-spend"

    # The agent run's state landed exactly like the manual run's (both
    # spawned into generating_song) — approve's own behavior is untouched.
    assert _read_state(agent_run_dir)["status"] == "generating_song"

    # The learning signal WAS recorded for the agent run only.
    mem = agent_memory.load_memory(_user_root(tmp_path, "u1"), "art_x")
    assert mem["decisions"][-1]["decision"] == "approved"
    assert mem["decisions"][-1]["run_id"] == "run-approve-agent"
    assert mem["decisions"][-1]["self_score"] == 0.7


def test_approve_non_agent_run_does_not_write_memory(
    client_factory, monkeypatch, tmp_path
):
    from pipeline import api as api_mod, credits

    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path / "out"))
    api_mod.set_spawn_fn(lambda args, run_dir: 424242)
    monkeypatch.setattr(credits, "get_balance", lambda uid: 100)
    monkeypatch.setattr(
        credits, "check_or_deduct",
        lambda user, *, amount, run_id, reason: 100 - amount,
    )

    c = client_factory(user_id="u1", role="user")
    _write_song_run(
        tmp_path, "u1", "run-approve-manual-2", source=None, artist_id="art_x",
    )
    r = c.post("/songs/run-approve-manual-2/approve")
    assert r.status_code == 200, r.text

    mem_path = agent_memory.memory_path(_user_root(tmp_path, "u1"), "art_x")
    assert not mem_path.exists()


def test_approve_memory_write_failure_does_not_fail_approve(
    client_factory, monkeypatch, tmp_path
):
    """Money-adjacent guard: even if agent_memory.record_decision blows up,
    approve must still succeed and the caller must still get their spawn."""
    from pipeline import api as api_mod, credits, agent_memory as am_mod

    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path / "out"))
    api_mod.set_spawn_fn(lambda args, run_dir: 424242)
    monkeypatch.setattr(credits, "get_balance", lambda uid: 100)
    monkeypatch.setattr(
        credits, "check_or_deduct",
        lambda user, *, amount, run_id, reason: 100 - amount,
    )

    def boom(*a, **k):
        raise RuntimeError("disk full")

    monkeypatch.setattr(am_mod, "record_decision", boom)

    c = client_factory(user_id="u1", role="user")
    run_dir = _write_song_run(
        tmp_path, "u1", "run-approve-memfail", source="agent", artist_id="art_x",
    )
    r = c.post("/songs/run-approve-memfail/approve")
    assert r.status_code == 200, r.text
    assert _read_state(run_dir)["status"] == "generating_song"
