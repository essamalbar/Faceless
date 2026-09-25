from __future__ import annotations

from pathlib import Path

from pipeline.artists import new_artist
from pipeline.config import load_config

REPO_ROOT = Path(__file__).parent.parent


def test_new_artist_has_agent_enabled_default_false():
    a = new_artist(name="Salma", handle="salma")
    assert a["agent_enabled"] is False


def test_config_has_agent_block():
    ag = load_config(REPO_ROOT / "config.yaml").agent
    assert ag.enabled is False
    assert ag.model == "claude-opus-5"
    assert ag.worker_model == "claude-sonnet-5"
    assert ag.max_iterations == 12
    assert ag.token_budget == 60000
    assert ag.proposals_per_cycle == 2
    assert ag.daily_global_run_cap == 50
    assert ag.critique_threshold == 0.6


def test_agent_enabled_round_trips_through_artist_api(
        client_factory, monkeypatch, tmp_path):
    """PATCH sets agent_enabled and GET/POST responses must surface it too
    (ArtistSummary is an explicit field whitelist, not a passthrough dict) —
    otherwise a later Flutter toggle can write the flag but never read it."""
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path))
    c = client_factory(user_id="alice")
    r = c.post("/artists", json={"name": "Salma", "handle": "salma"})
    assert r.status_code == 201, r.text
    a = r.json()
    assert a["agent_enabled"] is False

    r = c.patch(f"/artists/{a['id']}", json={"agent_enabled": True})
    assert r.status_code == 200
    assert r.json()["agent_enabled"] is True

    listed = c.get("/artists").json()
    assert listed[0]["agent_enabled"] is True
