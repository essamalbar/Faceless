"""Tests for Task 7: `POST /admin/run-agent` — the scheduler sweep that
dispatches an agent worker per opted-in artist (spec
docs/superpowers/specs/2026-09-25-autonomous-artist-agent-design.md §3).

Mirrors `run_morning_drafts` (pipeline/api.py:1220-1302): service-auth only,
sweeps every user dir under `_out_root()`, filters opted-in artists, is
idempotent per artist per day, and isolates per-artist errors. The extra
wrinkle here is the `daily_global_run_cap` (config.agent) and the dispatch
mechanism — a background worker (`run.py --agent --user <id> --artist <id>`)
via `_spawn`, never run inline.

`_spawn` is monkeypatched directly (not `set_spawn_fn`/`_SPAWN_FN`) in every
test — external services (here: a subprocess/Cloud-Run-Job dispatch) are
mocked per the CLAUDE.md invariant, and a real spawn must never happen from
this test module.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pipeline import artists as artists_mod


def _user_dir(tmp_path: Path, user_id: str) -> Path:
    return tmp_path / user_id


def _make_artist(user_dir: Path, *, name: str, agent_enabled: bool) -> dict:
    artists = artists_mod.load_artists(user_dir)
    a = artists_mod.new_artist(name=name, handle=name.lower().replace(" ", "-"))
    a["agent_enabled"] = agent_enabled
    artists.append(a)
    artists_mod.save_artists(user_dir, artists)
    return a


def _write_agent_run(
    user_dir: Path,
    run_id: str,
    *,
    artist_id: str,
    status: str = "awaiting_approval",
    created_at: str | None = None,
) -> Path:
    """Writes a run dir on disk shaped like `queue_proposal`'s output —
    source="agent", the given status, created "today" by default."""
    run_dir = user_dir / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "api_state.json").write_text(json.dumps({
        "kind": "song",
        "status": status,
        "user_id": user_dir.name,
        "source": "agent",
        "artist_id": artist_id,
        "created_at": created_at or datetime.now(timezone.utc).isoformat(
            timespec="seconds"),
    }, ensure_ascii=False), encoding="utf-8")
    return run_dir


class _FakeAgentCfg:
    def __init__(self, cap: int):
        self.daily_global_run_cap = cap
        self.enabled = True


class _FakeConfig:
    """Minimal stand-in for pipeline.config.Config — run_agent only ever
    reads `.agent.daily_global_run_cap`."""
    def __init__(self, cap: int):
        self.agent = _FakeAgentCfg(cap)


def _patch_cap(monkeypatch, cap: int) -> None:
    monkeypatch.setattr("pipeline.config.load_config",
                         lambda path: _FakeConfig(cap))


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def test_sweep_requires_service_auth(client_factory, monkeypatch, tmp_path):
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path))
    c = client_factory(user_id="alice", role="user")
    assert c.post("/admin/run-agent").status_code == 403


# ---------------------------------------------------------------------------
# Filter: only agent_enabled artists get dispatched
# ---------------------------------------------------------------------------

def test_sweep_dispatches_only_agent_enabled_artists(client_factory, monkeypatch, tmp_path):
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path))
    spawns: list[list[str]] = []
    monkeypatch.setattr("pipeline.api._spawn",
                         lambda args, **k: spawns.append(list(args)))

    user_dir = _user_dir(tmp_path, "alice")
    on = _make_artist(user_dir, name="On", agent_enabled=True)
    _make_artist(user_dir, name="Off", agent_enabled=False)

    c = client_factory(user_id="admin", role="service")
    r = c.post("/admin/run-agent")
    assert r.status_code == 200, r.text
    body = r.json()

    assert len(spawns) == 1
    assert "--agent" in spawns[0] and "--artist" in spawns[0]
    assert "--user" in spawns[0]
    assert spawns[0][spawns[0].index("--user") + 1] == "alice"
    assert spawns[0][spawns[0].index("--artist") + 1] == on["id"]

    assert body["dispatched"] == 1
    assert body["skipped"] == 0
    assert body["capped"] == 0


def test_sweep_no_users_returns_zeroed_summary(client_factory, monkeypatch, tmp_path):
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path / "does-not-exist"))
    spawns: list[list[str]] = []
    monkeypatch.setattr("pipeline.api._spawn",
                         lambda args, **k: spawns.append(list(args)))
    c = client_factory(user_id="admin", role="service")
    r = c.post("/admin/run-agent")
    assert r.status_code == 200
    assert r.json() == {"dispatched": 0, "skipped": 0, "capped": 0, "details": []}
    assert spawns == []


# ---------------------------------------------------------------------------
# Idempotency — _has_agent_run_today
# ---------------------------------------------------------------------------

def test_sweep_idempotent_skips_already_run_today(client_factory, monkeypatch, tmp_path):
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path))
    spawns: list[list[str]] = []
    monkeypatch.setattr("pipeline.api._spawn",
                         lambda args, **k: spawns.append(list(args)))

    user_dir = _user_dir(tmp_path, "alice")
    a = _make_artist(user_dir, name="Layl", agent_enabled=True)
    _write_agent_run(user_dir, "run-already-today", artist_id=a["id"],
                      status="awaiting_approval")

    c = client_factory(user_id="admin", role="service")
    body = c.post("/admin/run-agent").json()

    assert spawns == []
    assert body["dispatched"] == 0
    assert body["skipped"] == 1
    assert body["capped"] == 0


def test_sweep_treats_writing_lyrics_and_rejected_as_already_ran(
        client_factory, monkeypatch, tmp_path):
    """Transient (writing_lyrics) and terminal-but-non-failed (rejected)
    states both count as "already ran today" — only `failed` doesn't."""
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path))
    spawns: list[list[str]] = []
    monkeypatch.setattr("pipeline.api._spawn",
                         lambda args, **k: spawns.append(list(args)))

    user_dir = _user_dir(tmp_path, "alice")
    a1 = _make_artist(user_dir, name="A1", agent_enabled=True)
    a2 = _make_artist(user_dir, name="A2", agent_enabled=True)
    _write_agent_run(user_dir, "run-writing", artist_id=a1["id"],
                      status="writing_lyrics")
    _write_agent_run(user_dir, "run-rejected", artist_id=a2["id"],
                      status="rejected")

    c = client_factory(user_id="admin", role="service")
    body = c.post("/admin/run-agent").json()

    assert spawns == []
    assert body["dispatched"] == 0
    assert body["skipped"] == 2


def test_sweep_retries_when_todays_agent_run_failed(client_factory, monkeypatch, tmp_path):
    """A `failed` run today does NOT block a retry."""
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path))
    spawns: list[list[str]] = []
    monkeypatch.setattr("pipeline.api._spawn",
                         lambda args, **k: spawns.append(list(args)))

    user_dir = _user_dir(tmp_path, "alice")
    a = _make_artist(user_dir, name="Layl", agent_enabled=True)
    _write_agent_run(user_dir, "run-failed-today", artist_id=a["id"],
                      status="failed")

    c = client_factory(user_id="admin", role="service")
    body = c.post("/admin/run-agent").json()

    assert len(spawns) == 1
    assert body["dispatched"] == 1
    assert body["skipped"] == 0


def test_sweep_ignores_stale_runs_from_a_previous_day(client_factory, monkeypatch, tmp_path):
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path))
    spawns: list[list[str]] = []
    monkeypatch.setattr("pipeline.api._spawn",
                         lambda args, **k: spawns.append(list(args)))

    user_dir = _user_dir(tmp_path, "alice")
    a = _make_artist(user_dir, name="Layl", agent_enabled=True)
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(
        timespec="seconds")
    _write_agent_run(user_dir, "run-yesterday", artist_id=a["id"],
                      status="awaiting_approval", created_at=yesterday)

    c = client_factory(user_id="admin", role="service")
    body = c.post("/admin/run-agent").json()

    assert len(spawns) == 1
    assert body["dispatched"] == 1
    assert body["skipped"] == 0


# ---------------------------------------------------------------------------
# Global daily cap
# ---------------------------------------------------------------------------

def test_sweep_respects_daily_global_cap(client_factory, monkeypatch, tmp_path):
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path))
    _patch_cap(monkeypatch, 2)
    spawns: list[list[str]] = []
    monkeypatch.setattr("pipeline.api._spawn",
                         lambda args, **k: spawns.append(list(args)))

    user_dir = _user_dir(tmp_path, "alice")
    for i in range(4):
        _make_artist(user_dir, name=f"A{i}", agent_enabled=True)

    c = client_factory(user_id="admin", role="service")
    body = c.post("/admin/run-agent").json()

    assert len(spawns) == 2
    assert body["dispatched"] == 2
    assert body["capped"] == 2
    assert body["skipped"] == 0


def test_sweep_cap_counts_runs_already_dispatched_earlier_today(
        client_factory, monkeypatch, tmp_path):
    """The cap is a running daily total, not reset per sweep call: a run
    that already exists today (e.g. from an earlier sweep, or an artist that
    has since been toggled off) still counts against today's budget."""
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path))
    _patch_cap(monkeypatch, 2)
    spawns: list[list[str]] = []
    monkeypatch.setattr("pipeline.api._spawn",
                         lambda args, **k: spawns.append(list(args)))

    user_dir = _user_dir(tmp_path, "alice")
    already_ran = _make_artist(user_dir, name="AlreadyRan", agent_enabled=False)
    _write_agent_run(user_dir, "run-earlier-today", artist_id=already_ran["id"],
                      status="awaiting_approval")
    a1 = _make_artist(user_dir, name="A1", agent_enabled=True)
    a2 = _make_artist(user_dir, name="A2", agent_enabled=True)

    c = client_factory(user_id="admin", role="service")
    body = c.post("/admin/run-agent").json()

    # cap=2, 1 already spent today -> only 1 more dispatch allowed.
    assert len(spawns) == 1
    assert body["dispatched"] == 1
    assert body["capped"] == 1


# ---------------------------------------------------------------------------
# Per-artist error isolation
# ---------------------------------------------------------------------------

def test_sweep_isolates_per_artist_error(client_factory, monkeypatch, tmp_path):
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path))

    user_dir = _user_dir(tmp_path, "alice")
    boom = _make_artist(user_dir, name="Boom", agent_enabled=True)
    ok = _make_artist(user_dir, name="Ok", agent_enabled=True)

    def flaky_spawn(args, **k):
        if boom["id"] in args:
            raise RuntimeError("cloud run jobs API hiccup")
        return 424242

    monkeypatch.setattr("pipeline.api._spawn", flaky_spawn)

    c = client_factory(user_id="admin", role="service")
    r = c.post("/admin/run-agent")
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["dispatched"] == 1
    error_details = [d for d in body["details"] if d.get("error")]
    assert len(error_details) == 1
    assert ok["id"] not in [d.get("artist_id") for d in error_details]


def test_sweep_ignores_non_run_subdirs_like_agent_memory_store(
        client_factory, monkeypatch, tmp_path):
    """Task 6's per-artist agent memory store lives at
    `<user_root>/agent/<artist_id>.json` — a non-run subdirectory of the
    same user root the sweep scans. It must be silently skipped, not crash
    the sweep (`_read_state` on a dir with no api_state.json returns {})."""
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path))
    spawns: list[list[str]] = []
    monkeypatch.setattr("pipeline.api._spawn",
                         lambda args, **k: spawns.append(list(args)))

    user_dir = _user_dir(tmp_path, "alice")
    a = _make_artist(user_dir, name="Layl", agent_enabled=True)
    agent_memory_dir = user_dir / "agent"
    agent_memory_dir.mkdir(parents=True)
    (agent_memory_dir / f"{a['id']}.json").write_text(
        json.dumps({"artist_id": a["id"], "decisions": []}), encoding="utf-8")

    c = client_factory(user_id="admin", role="service")
    r = c.post("/admin/run-agent")
    assert r.status_code == 200, r.text
    assert len(spawns) == 1
    assert r.json()["dispatched"] == 1


def test_sweep_dispatches_per_user_across_multiple_users(client_factory, monkeypatch, tmp_path):
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path))
    spawns: list[list[str]] = []
    monkeypatch.setattr("pipeline.api._spawn",
                         lambda args, **k: spawns.append(list(args)))

    _make_artist(_user_dir(tmp_path, "alice"), name="A", agent_enabled=True)
    _make_artist(_user_dir(tmp_path, "bob"), name="B", agent_enabled=True)

    c = client_factory(user_id="admin", role="service")
    body = c.post("/admin/run-agent").json()

    assert body["dispatched"] == 2
    users_dispatched = {s[s.index("--user") + 1] for s in spawns}
    assert users_dispatched == {"alice", "bob"}
