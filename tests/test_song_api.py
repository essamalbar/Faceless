from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app(monkeypatch, tmp_path: Path):
    """Build the FastAPI app with a fake out-root and no-op spawn."""
    token = "test-token-123"
    monkeypatch.setenv("FACELESS_API_TOKEN", token)
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path / "out"))
    monkeypatch.setenv("KIE_API_KEY", "stub")
    from pipeline import api as api_mod
    api_mod.set_spawn_fn(lambda args, run_dir: 999999)
    canned = json.dumps({
        "title": "Test Song",
        "lyrics": "[Verse 1]\nline\n[Chorus]\nhook\n[Verse 2]\nline\n[Chorus]\nhook",
        "style_prompt": "Arabic pop ballad, slow tempo 72 BPM, oud + strings, male vocal, modern 2020s, melancholic minor key",
        "cover_prompt": "moonlight over the sea",
    })
    fake_llm = MagicMock()
    fake_llm.complete = MagicMock(return_value=canned)
    monkeypatch.setattr(api_mod, "_build_song_llm", lambda: fake_llm)
    return api_mod.app, token


def _find_run_dir(run_id: str) -> Path:
    root = os.environ["FACELESS_OUT_ROOT"]
    for d_root, _, _ in os.walk(root):
        if Path(d_root).name == run_id:
            return Path(d_root)
    raise FileNotFoundError(f"no run dir for {run_id}")


def test_post_songs_creates_run_and_returns_awaiting_approval(app):
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    r = client.post(
        "/songs",
        json={"theme": "sad Arabic ballad about the moon", "language": "ar"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert "run_id" in body
    assert body["status"] == "awaiting_approval"


def test_post_songs_writes_song_json_to_disk(app):
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    r = client.post(
        "/songs",
        json={"theme": "x", "language": "ar"},
        headers={"Authorization": f"Bearer {token}"},
    )
    run_id = r.json()["run_id"]
    run_dir = _find_run_dir(run_id)
    song_json = json.loads((run_dir / "song.json").read_text())
    assert song_json["title"] == "Test Song"
    assert "[Verse 1]" in song_json["lyrics"]
    assert "BPM" in song_json["style_prompt"]
    state = json.loads((run_dir / "api_state.json").read_text())
    assert state["kind"] == "song"
    assert state["status"] == "awaiting_approval"


def test_post_songs_requires_auth(app):
    fastapi_app, _ = app
    client = TestClient(fastapi_app)
    r = client.post("/songs", json={"theme": "x"})
    assert r.status_code == 401


def test_post_songs_honors_custom_lyrics_passthrough(app):
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    custom = "[Verse 1]\nmy own words\n[Chorus]\nverbatim"
    r = client.post(
        "/songs",
        json={"theme": "x", "custom_lyrics": custom, "language": "en"},
        headers={"Authorization": f"Bearer {token}"},
    )
    run_id = r.json()["run_id"]
    run_dir = _find_run_dir(run_id)
    song_json = json.loads((run_dir / "song.json").read_text())
    assert song_json["lyrics"] == custom


def test_get_song_returns_summary(app):
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    create = client.post(
        "/songs", json={"theme": "x"},
        headers={"Authorization": f"Bearer {token}"},
    )
    run_id = create.json()["run_id"]
    r = client.get(f"/songs/{run_id}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == run_id
    assert body["kind"] == "song"
    assert body["status"] == "awaiting_approval"
    assert body["title"] == "Test Song"


def test_get_song_404_for_unknown_id(app):
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    r = client.get("/songs/nope", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 404


def test_get_song_script_returns_full_payload(app):
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    create = client.post(
        "/songs", json={"theme": "x", "language": "ar"},
        headers={"Authorization": f"Bearer {token}"},
    )
    run_id = create.json()["run_id"]
    r = client.get(
        f"/songs/{run_id}/script",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "Test Song"
    assert "[Chorus]" in body["lyrics"]
    assert body["style_prompt"]
    assert body["cover_prompt"]
    assert body["language"] == "ar"
    assert body["cost_credits"] >= 1
    assert body["cost_usd"] > 0


def test_list_songs_returns_only_song_runs(app):
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    for _ in range(2):
        client.post(
            "/songs", json={"theme": "x"},
            headers={"Authorization": f"Bearer {token}"},
        )
    r = client.get("/songs", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 2
    assert all(s["kind"] == "song" for s in body)


def test_regenerate_lyrics_only_pre_approval(app):
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    create = client.post(
        "/songs", json={"theme": "x"},
        headers={"Authorization": f"Bearer {token}"},
    )
    run_id = create.json()["run_id"]
    # Allowed in awaiting_approval
    r = client.post(
        f"/songs/{run_id}/regenerate-lyrics",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    # Simulate post-approval by writing state directly
    run_dir = _find_run_dir(run_id)
    state = json.loads((run_dir / "api_state.json").read_text())
    state["status"] = "generating_song"
    (run_dir / "api_state.json").write_text(json.dumps(state))
    # Now regen must 409
    r = client.post(
        f"/songs/{run_id}/regenerate-lyrics",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 409


def test_edit_validates_lyrics_length(app):
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    create = client.post(
        "/songs", json={"theme": "x"},
        headers={"Authorization": f"Bearer {token}"},
    )
    run_id = create.json()["run_id"]
    big = "x" * 4001
    r = client.post(
        f"/songs/{run_id}/edit",
        json={"lyrics": big},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422


def test_edit_patches_fields(app):
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    create = client.post(
        "/songs", json={"theme": "x"},
        headers={"Authorization": f"Bearer {token}"},
    )
    run_id = create.json()["run_id"]
    new_lyrics = "[Verse 1]\nedited\n[Chorus]\nnew hook"
    r = client.post(
        f"/songs/{run_id}/edit",
        json={"lyrics": new_lyrics},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    r2 = client.get(
        f"/songs/{run_id}/script",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.json()["lyrics"] == new_lyrics


def test_cancel_pre_approval_sets_canceled_status(app):
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    create = client.post(
        "/songs", json={"theme": "x"},
        headers={"Authorization": f"Bearer {token}"},
    )
    run_id = create.json()["run_id"]
    r = client.post(
        f"/songs/{run_id}/cancel",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    r2 = client.get(f"/songs/{run_id}", headers={"Authorization": f"Bearer {token}"})
    assert r2.json()["status"] == "canceled"
