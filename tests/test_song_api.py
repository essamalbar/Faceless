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


def test_approve_song_deducts_credits_and_spawns(app, monkeypatch):
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    from pipeline import api as api_mod
    spawn_calls = []
    def fake_spawn(args, run_dir):
        spawn_calls.append((args, run_dir))
        return 12345
    api_mod.set_spawn_fn(fake_spawn)

    from pipeline import credits
    monkeypatch.setattr(credits, "get_balance", lambda uid: 100)
    monkeypatch.setattr(
        credits, "check_or_deduct",
        lambda user, amount, run_id, reason: 100 - amount,
    )

    create = client.post(
        "/songs", json={"theme": "x"},
        headers={"Authorization": f"Bearer {token}"},
    )
    run_id = create.json()["run_id"]
    r = client.post(
        f"/songs/{run_id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["run_id"] == run_id
    assert body["balance_after"] == 99

    assert len(spawn_calls) == 1
    args, _ = spawn_calls[0]
    assert "--mode" in args
    assert args[args.index("--mode") + 1] == "song"
    assert "--resume" in args


def test_approve_song_idempotent_after_first_call(app, monkeypatch):
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    from pipeline import credits
    deduction_count = {"n": 0}
    def counted_deduct(user, amount, run_id, reason):
        deduction_count["n"] += 1
        return 100 - amount
    monkeypatch.setattr(credits, "get_balance", lambda uid: 100)
    monkeypatch.setattr(credits, "check_or_deduct", counted_deduct)

    create = client.post(
        "/songs", json={"theme": "x"},
        headers={"Authorization": f"Bearer {token}"},
    )
    run_id = create.json()["run_id"]
    client.post(f"/songs/{run_id}/approve", headers={"Authorization": f"Bearer {token}"})
    client.post(f"/songs/{run_id}/approve", headers={"Authorization": f"Bearer {token}"})
    assert deduction_count["n"] == 1


def test_swap_take_reruns_assembly(app, tmp_path: Path, monkeypatch):
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    create = client.post(
        "/songs", json={"theme": "x"},
        headers={"Authorization": f"Bearer {token}"},
    )
    run_id = create.json()["run_id"]

    run_dir = _find_run_dir(run_id)
    (run_dir / "takes").mkdir(exist_ok=True)
    (run_dir / "takes" / "take_1.mp3").write_bytes(b"\x00" * 100)
    (run_dir / "takes" / "take_2.mp3").write_bytes(b"\x00" * 100)
    (run_dir / "song.mp3").write_bytes(b"\x00" * 100)
    state = json.loads((run_dir / "api_state.json").read_text())
    state["status"] = "complete"
    state["chosen_take"] = 1
    (run_dir / "api_state.json").write_text(json.dumps(state))

    from pipeline import song_assemble
    monkeypatch.setattr(
        song_assemble, "assemble_song_video",
        lambda *, cover_path, song_mp3, out_mp4: out_mp4.write_bytes(b"FAKE"),
    )

    r = client.post(
        f"/songs/{run_id}/swap-take",
        json={"take": 2},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    new_state = json.loads((run_dir / "api_state.json").read_text())
    assert new_state["chosen_take"] == 2


def test_get_audio_serves_chosen_take(app):
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    create = client.post(
        "/songs", json={"theme": "x"},
        headers={"Authorization": f"Bearer {token}"},
    )
    run_id = create.json()["run_id"]
    run_dir = _find_run_dir(run_id)
    (run_dir / "song.mp3").write_bytes(b"\xff\xfb" + b"\x00" * 100)
    r = client.get(
        f"/songs/{run_id}/audio",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.content.startswith(b"\xff\xfb")


def test_get_audio_serves_alternate_take_via_query(app):
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    create = client.post(
        "/songs", json={"theme": "x"},
        headers={"Authorization": f"Bearer {token}"},
    )
    run_id = create.json()["run_id"]
    run_dir = _find_run_dir(run_id)
    (run_dir / "takes").mkdir(exist_ok=True)
    (run_dir / "takes" / "take_2.mp3").write_bytes(b"TAKE2")
    r = client.get(
        f"/songs/{run_id}/audio?take=2",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.content == b"TAKE2"


def test_approve_song_402_when_balance_insufficient(app, monkeypatch):
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    from pipeline import credits
    from pipeline.auth import User, require_user

    # Step 1: create the song as the service user (default fixture
    # auth) so the create-side balance check passes regardless.
    create = client.post(
        "/songs", json={"theme": "x"},
        headers={"Authorization": f"Bearer {token}"},
    )
    run_id = create.json()["run_id"]

    # Step 2: override require_user to a non-service identity with
    # zero balance, then attempt approve. We keep id="admin" so
    # _user_runs_root resolves to the same path the song was created
    # under, but flip role to "user" so the service-bypass guard
    # doesn't skip the balance check.
    monkeypatch.setattr(credits, "get_balance", lambda uid: 0)
    fastapi_app.dependency_overrides[require_user] = lambda: User(
        id="admin", email="t@example.com", role="user",
    )
    try:
        r = client.post(
            f"/songs/{run_id}/approve",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 402
    finally:
        fastapi_app.dependency_overrides.pop(require_user, None)


def test_resume_409_when_worker_already_running(app):
    """Concurrency guard: if a worker is already processing this song
    (status in generating_*/assembling), a second /resume call must
    refuse with 409 instead of spawning another worker. Without this
    guard, a rapid double-tap on Retry races on song.mp3 + final.mp4
    and the output gets truncated."""
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    create = client.post(
        "/songs", json={"theme": "x"},
        headers={"Authorization": f"Bearer {token}"},
    )
    run_id = create.json()["run_id"]

    # Simulate an in-flight worker by writing status directly.
    run_dir = _find_run_dir(run_id)
    for active_status in ("generating_song", "generating_cover", "assembling"):
        state = json.loads((run_dir / "api_state.json").read_text())
        state["status"] = active_status
        (run_dir / "api_state.json").write_text(json.dumps(state))

        r = client.post(
            f"/songs/{run_id}/resume",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 409, (
            f"/resume must refuse while status={active_status!r}, "
            f"got {r.status_code}: {r.text}"
        )
        assert "already processing" in r.text, r.text


def test_resume_409_when_status_is_complete_or_canceled(app):
    """/resume only makes sense for a failed run. Refuse for terminal
    successes too — a 'complete' song should not be re-rendered."""
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    create = client.post(
        "/songs", json={"theme": "x"},
        headers={"Authorization": f"Bearer {token}"},
    )
    run_id = create.json()["run_id"]
    run_dir = _find_run_dir(run_id)
    for terminal_status in ("complete", "canceled", "awaiting_approval"):
        state = json.loads((run_dir / "api_state.json").read_text())
        state["status"] = terminal_status
        (run_dir / "api_state.json").write_text(json.dumps(state))
        r = client.post(
            f"/songs/{run_id}/resume",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 409, (
            f"/resume must refuse while status={terminal_status!r}, "
            f"got {r.status_code}"
        )


def test_resume_succeeds_when_status_is_failed(app):
    """Sanity: /resume DOES proceed from 'failed' state — that's
    the whole point of the endpoint."""
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    create = client.post(
        "/songs", json={"theme": "x"},
        headers={"Authorization": f"Bearer {token}"},
    )
    run_id = create.json()["run_id"]
    run_dir = _find_run_dir(run_id)
    state = json.loads((run_dir / "api_state.json").read_text())
    state["status"] = "failed"
    state["last_error"] = "test failure"
    (run_dir / "api_state.json").write_text(json.dumps(state))

    r = client.post(
        f"/songs/{run_id}/resume",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
