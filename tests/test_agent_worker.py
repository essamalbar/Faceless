"""Tests for `run.py --agent` — the Autonomous Artist Agent worker entry
(spec docs/superpowers/specs/2026-09-25-autonomous-artist-agent-design.md
§3, task-5-brief.md).

Every test stubs `AgentRunner.run_cycle` (monkeypatch) so no real Anthropic
call ever happens — external services are mocked in tests (CLAUDE.md
invariant). `anthropic.Anthropic()` client construction itself is real
(it never makes a network call at construction time), which lets the
"all gates on" test assert the worker actually builds a real client and
wires the right base_url.
"""
from __future__ import annotations

from pathlib import Path

import anthropic

import run as run_mod
from pipeline import artists as artists_mod
from pipeline.agent import AgentRunner


class _FakeAgentCfg:
    def __init__(self, enabled: bool):
        self.enabled = enabled


class _FakeConfig:
    """Minimal stand-in for pipeline.config.Config — _run_agent_cycle only
    ever reads `.agent.enabled` off whatever load_config() returns before
    handing the whole object to the (stubbed) AgentRunner.run_cycle."""
    def __init__(self, enabled: bool):
        self.agent = _FakeAgentCfg(enabled)


def _setup_artist(tmp_path: Path, user_id: str, *, agent_enabled: bool) -> str:
    """Writes a real artists.json under tmp_path/<user_id> (the per-user
    runs root) via the real pipeline.artists API, and returns the artist id
    run.py --agent should be pointed at."""
    user_root = tmp_path / user_id
    artist = artists_mod.new_artist(name="Layl", handle="layl")
    artist["agent_enabled"] = agent_enabled
    artists_mod.save_artists(user_root, [artist])
    return artist["id"]


def _stub_run_cycle(monkeypatch, called: dict):
    def fake(*_a, **_k):
        called["ran"] = True
        return {"queued": [], "iterations": 0, "stopped": "finished"}
    monkeypatch.setattr(AgentRunner, "run_cycle", fake)


# ---------------------------------------------------------------------------
# Gate: FACELESS_AGENT_ENABLED
# ---------------------------------------------------------------------------

def test_agent_worker_noops_when_flag_off(tmp_path, monkeypatch):
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path))
    monkeypatch.delenv("FACELESS_AGENT_ENABLED", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr(run_mod, "load_config", lambda path: _FakeConfig(True))
    artist_id = _setup_artist(tmp_path, "u1", agent_enabled=True)

    called = {"ran": False}
    _stub_run_cycle(monkeypatch, called)

    rc = run_mod.main_with_args(["--agent", "--user", "u1", "--artist", artist_id])

    assert rc == 0
    assert called["ran"] is False  # gated off -> never ran the loop


# ---------------------------------------------------------------------------
# Gate: config.agent.enabled
# ---------------------------------------------------------------------------

def test_agent_worker_noops_when_config_agent_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path))
    monkeypatch.setenv("FACELESS_AGENT_ENABLED", "1")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr(run_mod, "load_config", lambda path: _FakeConfig(False))
    artist_id = _setup_artist(tmp_path, "u1", agent_enabled=True)

    called = {"ran": False}
    _stub_run_cycle(monkeypatch, called)

    rc = run_mod.main_with_args(["--agent", "--user", "u1", "--artist", artist_id])

    assert rc == 0
    assert called["ran"] is False


# ---------------------------------------------------------------------------
# Gate: artist.agent_enabled
# ---------------------------------------------------------------------------

def test_agent_worker_noops_when_artist_agent_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path))
    monkeypatch.setenv("FACELESS_AGENT_ENABLED", "1")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr(run_mod, "load_config", lambda path: _FakeConfig(True))
    artist_id = _setup_artist(tmp_path, "u1", agent_enabled=False)

    called = {"ran": False}
    _stub_run_cycle(monkeypatch, called)

    rc = run_mod.main_with_args(["--agent", "--user", "u1", "--artist", artist_id])

    assert rc == 0
    assert called["ran"] is False


# ---------------------------------------------------------------------------
# Gate: ANTHROPIC_API_KEY presence
# ---------------------------------------------------------------------------

def test_agent_worker_noops_without_anthropic_key(tmp_path, monkeypatch):
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path))
    monkeypatch.setenv("FACELESS_AGENT_ENABLED", "1")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(run_mod, "load_config", lambda path: _FakeConfig(True))
    artist_id = _setup_artist(tmp_path, "u1", agent_enabled=True)

    called = {"ran": False}
    _stub_run_cycle(monkeypatch, called)

    rc = run_mod.main_with_args(["--agent", "--user", "u1", "--artist", artist_id])

    assert rc == 0
    assert called["ran"] is False


# ---------------------------------------------------------------------------
# Artist / arg resolution no-ops
# ---------------------------------------------------------------------------

def test_agent_worker_noops_when_artist_not_found(tmp_path, monkeypatch):
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path))
    monkeypatch.setenv("FACELESS_AGENT_ENABLED", "1")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr(run_mod, "load_config", lambda path: _FakeConfig(True))

    called = {"ran": False}
    _stub_run_cycle(monkeypatch, called)

    rc = run_mod.main_with_args(
        ["--agent", "--user", "nobody", "--artist", "art_missing"])

    assert rc == 0
    assert called["ran"] is False


def test_agent_worker_noops_without_user_or_artist(tmp_path, monkeypatch):
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path))
    monkeypatch.setenv("FACELESS_AGENT_ENABLED", "1")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

    called = {"ran": False}
    _stub_run_cycle(monkeypatch, called)

    rc = run_mod.main_with_args(["--agent"])  # no --user / --artist

    assert rc == 0
    assert called["ran"] is False


# ---------------------------------------------------------------------------
# All gates on -> the loop actually runs
# ---------------------------------------------------------------------------

def test_agent_worker_runs_when_all_gates_on(tmp_path, monkeypatch):
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path))
    monkeypatch.setenv("FACELESS_AGENT_ENABLED", "1")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
    monkeypatch.setattr(run_mod, "load_config", lambda path: _FakeConfig(True))
    artist_id = _setup_artist(tmp_path, "u1", agent_enabled=True)

    captured = {}

    def fake_run_cycle(self, user_root, artist, *, anthropic_client, config):
        captured["user_root"] = user_root
        captured["artist"] = artist
        captured["client"] = anthropic_client
        captured["config"] = config
        return {"queued": ["r1"], "iterations": 3, "stopped": "finished"}

    monkeypatch.setattr(AgentRunner, "run_cycle", fake_run_cycle)

    rc = run_mod.main_with_args(["--agent", "--user", "u1", "--artist", artist_id])

    assert rc == 0
    # user_root MUST be the PER-USER dir (out_root/<user_id>), not the
    # global out_root — AgentRunner/tools derive user_id from .name.
    assert captured["user_root"] == tmp_path / "u1"
    assert captured["user_root"].name == "u1"
    assert captured["artist"]["id"] == artist_id
    assert captured["config"].agent.enabled is True
    assert isinstance(captured["client"], anthropic.Anthropic)


def test_agent_worker_passes_anthropic_base_url_when_set(tmp_path, monkeypatch):
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path))
    monkeypatch.setenv("FACELESS_AGENT_ENABLED", "1")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://proxy.example.com")
    monkeypatch.setattr(run_mod, "load_config", lambda path: _FakeConfig(True))
    artist_id = _setup_artist(tmp_path, "u1", agent_enabled=True)

    captured = {}

    def fake_run_cycle(self, user_root, artist, *, anthropic_client, config):
        captured["client"] = anthropic_client
        return {"queued": [], "iterations": 1, "stopped": "finished"}

    monkeypatch.setattr(AgentRunner, "run_cycle", fake_run_cycle)

    rc = run_mod.main_with_args(["--agent", "--user", "u1", "--artist", artist_id])

    assert rc == 0
    assert str(captured["client"].base_url).startswith("https://proxy.example.com")


# ---------------------------------------------------------------------------
# Fail-safe: an exception from the loop must never crash the worker
# ---------------------------------------------------------------------------

def test_agent_worker_failsafe_on_exception(tmp_path, monkeypatch):
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path))
    monkeypatch.setenv("FACELESS_AGENT_ENABLED", "1")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr(run_mod, "load_config", lambda path: _FakeConfig(True))
    artist_id = _setup_artist(tmp_path, "u1", agent_enabled=True)

    def boom(self, *_a, **_k):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(AgentRunner, "run_cycle", boom)

    rc = run_mod.main_with_args(["--agent", "--user", "u1", "--artist", artist_id])

    assert rc == 0  # fail-safe: never propagate / never crash-loop the worker


def test_agent_worker_failsafe_on_bad_config(tmp_path, monkeypatch):
    """A load_config() that raises (e.g. a corrupt config.yaml) must also
    fail safe rather than crash the worker."""
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path))
    monkeypatch.setenv("FACELESS_AGENT_ENABLED", "1")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

    def boom(_path):
        raise ValueError("bad yaml")

    monkeypatch.setattr(run_mod, "load_config", boom)
    artist_id = _setup_artist(tmp_path, "u1", agent_enabled=True)

    called = {"ran": False}
    _stub_run_cycle(monkeypatch, called)

    rc = run_mod.main_with_args(["--agent", "--user", "u1", "--artist", artist_id])

    assert rc == 0
    assert called["ran"] is False
