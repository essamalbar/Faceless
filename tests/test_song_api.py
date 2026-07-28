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


def test_approve_cinematic_song_deducts_three_credits(app, monkeypatch):
    """Approving a song whose song.json has video_mode='cinematic' must
    charge 3 credits, not the default 1."""
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    from pipeline import api as api_mod, credits

    api_mod.set_spawn_fn(lambda args, run_dir: 12345)
    monkeypatch.setattr(credits, "get_balance", lambda uid: 100)

    captured = {}
    def _capture(user, *, amount, run_id, reason):
        captured["amount"] = amount
        return 100 - amount
    monkeypatch.setattr(credits, "check_or_deduct", _capture)

    create = client.post(
        "/songs", json={"theme": "x"},
        headers={"Authorization": f"Bearer {token}"},
    )
    run_id = create.json()["run_id"]
    run_dir = _find_run_dir(run_id)

    # Inject video_mode=cinematic into the already-written song.json
    song_data = json.loads((run_dir / "song.json").read_text())
    song_data["video_mode"] = "cinematic"
    (run_dir / "song.json").write_text(json.dumps(song_data))

    r = client.post(
        f"/songs/{run_id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    assert captured["amount"] == 3
    assert r.json()["balance_after"] == 97


def test_approve_static_song_deducts_one_credit(app, monkeypatch):
    """Approving a song with video_mode='static' (or unset) must charge
    exactly 1 credit."""
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    from pipeline import api as api_mod, credits

    api_mod.set_spawn_fn(lambda args, run_dir: 12345)
    monkeypatch.setattr(credits, "get_balance", lambda uid: 100)

    captured = {}
    def _capture(user, *, amount, run_id, reason):
        captured["amount"] = amount
        return 100 - amount
    monkeypatch.setattr(credits, "check_or_deduct", _capture)

    create = client.post(
        "/songs", json={"theme": "x"},
        headers={"Authorization": f"Bearer {token}"},
    )
    run_id = create.json()["run_id"]
    run_dir = _find_run_dir(run_id)

    # Explicitly set video_mode=static (also covers the default / omitted case)
    song_data = json.loads((run_dir / "song.json").read_text())
    song_data["video_mode"] = "static"
    (run_dir / "song.json").write_text(json.dumps(song_data))

    r = client.post(
        f"/songs/{run_id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    assert captured["amount"] == 1
    assert r.json()["balance_after"] == 99


def test_reroll_cinematic_song_deducts_three_credits(app, monkeypatch):
    """reroll-takes on a cinematic song must charge 3 credits, not 1."""
    from pipeline import api as api_mod, credits

    api_mod.set_spawn_fn(lambda args, run_dir: 12345)
    monkeypatch.setattr(credits, "get_balance", lambda uid: 100)

    captured = {}
    def _capture(user, *, amount, run_id, reason):
        captured["amount"] = amount
        return 100 - amount
    monkeypatch.setattr(credits, "check_or_deduct", _capture)

    run_id, run_dir, client, token = _setup_complete_song(app, monkeypatch)

    # Inject video_mode=cinematic into song.json
    song_data = json.loads((run_dir / "song.json").read_text())
    song_data["video_mode"] = "cinematic"
    (run_dir / "song.json").write_text(json.dumps(song_data))

    r = client.post(
        f"/songs/{run_id}/reroll-takes",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    assert captured["amount"] == 3


def test_reroll_static_song_deducts_one_credit(app, monkeypatch):
    """reroll-takes on a static song must charge exactly 1 credit, not 3."""
    from pipeline import api as api_mod, credits

    api_mod.set_spawn_fn(lambda args, run_dir: 12345)
    monkeypatch.setattr(credits, "get_balance", lambda uid: 100)

    captured = {}
    def _capture(user, *, amount, run_id, reason):
        captured["amount"] = amount
        return 100 - amount
    monkeypatch.setattr(credits, "check_or_deduct", _capture)

    run_id, run_dir, client, token = _setup_complete_song(app, monkeypatch)

    # Explicitly set video_mode=static (also covers the default / omitted case)
    song_data = json.loads((run_dir / "song.json").read_text())
    song_data["video_mode"] = "static"
    (run_dir / "song.json").write_text(json.dumps(song_data))

    r = client.post(
        f"/songs/{run_id}/reroll-takes",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    assert captured["amount"] == 1


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


def test_swap_take_queues_worker(app, monkeypatch):
    """swap-take now spawns the worker (was synchronous before).
    Verify the spawn is called and state carries swap_to_take +
    status=assembling for the worker to pick up."""
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    from pipeline import api as api_mod
    spawn_calls = []
    def fake_spawn(args, run_dir):
        spawn_calls.append((args, run_dir))
        return 99999
    api_mod.set_spawn_fn(fake_spawn)

    create = client.post(
        "/songs", json={"theme": "x"},
        headers={"Authorization": f"Bearer {token}"},
    )
    run_id = create.json()["run_id"]
    run_dir = _find_run_dir(run_id)
    (run_dir / "takes").mkdir(exist_ok=True)
    (run_dir / "takes" / "take_1.mp3").write_bytes(b"\x00" * 100)
    (run_dir / "takes" / "take_2.mp3").write_bytes(b"\x00" * 100)
    state = json.loads((run_dir / "api_state.json").read_text())
    state["status"] = "complete"
    state["chosen_take"] = 1
    (run_dir / "api_state.json").write_text(json.dumps(state))

    r = client.post(
        f"/songs/{run_id}/swap-take",
        json={"take": 2},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("queued") is True
    assert len(spawn_calls) == 1
    new_state = json.loads((run_dir / "api_state.json").read_text())
    assert new_state["swap_to_take"] == 2
    assert new_state["status"] == "assembling"


def test_swap_take_noop_when_same_take(app):
    """Tapping 'Use Take 1' when chosen_take is already 1 should
    no-op (don't spawn a worker, don't burn ffmpeg time)."""
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    from pipeline import api as api_mod
    spawn_calls = []
    api_mod.set_spawn_fn(lambda args, run_dir: spawn_calls.append(args) or 0)

    create = client.post(
        "/songs", json={"theme": "x"},
        headers={"Authorization": f"Bearer {token}"},
    )
    run_id = create.json()["run_id"]
    run_dir = _find_run_dir(run_id)
    (run_dir / "takes").mkdir(exist_ok=True)
    (run_dir / "takes" / "take_1.mp3").write_bytes(b"\x00" * 100)
    state = json.loads((run_dir / "api_state.json").read_text())
    state["status"] = "complete"
    state["chosen_take"] = 1
    (run_dir / "api_state.json").write_text(json.dumps(state))

    r = client.post(
        f"/songs/{run_id}/swap-take",
        json={"take": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json().get("noop") is True
    assert spawn_calls == []  # no worker spawned


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


# ─────────────── Personas ────────────────────────────────────────────────────

def _setup_complete_song(app, monkeypatch, *, with_audio_ids=True):
    """Fixture helper: create a song, force state to 'complete' with
    suno_task_id + audio_ids. Returns (run_id, run_dir)."""
    from pipeline import song
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    create = client.post(
        "/songs", json={"theme": "x"},
        headers={"Authorization": f"Bearer {token}"},
    )
    run_id = create.json()["run_id"]
    run_dir = _find_run_dir(run_id)
    state = json.loads((run_dir / "api_state.json").read_text())
    state["status"] = "complete"
    state["chosen_take"] = 1
    if with_audio_ids:
        state["suno_task_id"] = "fake-task-123"
        state["take_audio_ids"] = ["audio-id-take-1", "audio-id-take-2"]
    (run_dir / "api_state.json").write_text(json.dumps(state))
    return run_id, run_dir, client, token


def test_save_persona_creates_record(app, monkeypatch):
    from pipeline import song
    monkeypatch.setattr(
        song, "submit_persona_job",
        lambda client, **kw: "persona-uuid-abc",
    )
    run_id, _, client, token = _setup_complete_song(app, monkeypatch)
    r = client.post(
        f"/songs/{run_id}/save-persona",
        json={"name": "Warm Male Ballad", "description": "Arabic baritone, gentle vibrato"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["id"] == "persona-uuid-abc"
    assert body["name"] == "Warm Male Ballad"
    assert body["source_run_id"] == run_id
    assert body["source_take"] == 1


def test_save_persona_409_when_not_complete(app, monkeypatch):
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    create = client.post(
        "/songs", json={"theme": "x"},
        headers={"Authorization": f"Bearer {token}"},
    )
    run_id = create.json()["run_id"]
    # Still awaiting_approval — not complete
    r = client.post(
        f"/songs/{run_id}/save-persona",
        json={"name": "x", "description": "y"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 409


def test_save_persona_409_when_missing_audio_ids(app, monkeypatch):
    """Pre-persona runs (created before suno_task_id was saved) can't
    create personas — surface that clearly."""
    run_id, _, client, token = _setup_complete_song(
        app, monkeypatch, with_audio_ids=False,
    )
    r = client.post(
        f"/songs/{run_id}/save-persona",
        json={"name": "x", "description": "y"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 409
    assert "pre-dates persona support" in r.text


def test_save_persona_422_on_invalid_take(app, monkeypatch):
    from pipeline import song
    monkeypatch.setattr(
        song, "submit_persona_job", lambda client, **kw: "p",
    )
    run_id, _, client, token = _setup_complete_song(app, monkeypatch)
    r = client.post(
        f"/songs/{run_id}/save-persona",
        json={"name": "x", "description": "y", "take": 99},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422


def test_list_personas_returns_saved(app, monkeypatch):
    from pipeline import song
    monkeypatch.setattr(
        song, "submit_persona_job",
        lambda client, **kw: f"persona-{kw['name'][:5]}",
    )
    run_id, _, client, token = _setup_complete_song(app, monkeypatch)
    for n in ("Voice One", "Voice Two"):
        client.post(
            f"/songs/{run_id}/save-persona",
            json={"name": n, "description": "test"},
            headers={"Authorization": f"Bearer {token}"},
        )
    r = client.get("/personas", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 2
    assert {p["name"] for p in body} == {"Voice One", "Voice Two"}


def test_delete_persona_removes_record(app, monkeypatch):
    from pipeline import song
    monkeypatch.setattr(
        song, "submit_persona_job", lambda client, **kw: "persona-to-delete",
    )
    run_id, _, client, token = _setup_complete_song(app, monkeypatch)
    client.post(
        f"/songs/{run_id}/save-persona",
        json={"name": "x", "description": "y"},
        headers={"Authorization": f"Bearer {token}"},
    )
    r = client.delete(
        "/personas/persona-to-delete",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 204
    r2 = client.get("/personas", headers={"Authorization": f"Bearer {token}"})
    assert r2.json() == []


def test_delete_persona_404_when_missing(app):
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    r = client.delete(
        "/personas/never-existed",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404


# ─────────────── DELETE /songs/{id} ──────────────────────────────────────────

def test_delete_song_removes_run_dir(app):
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    create = client.post(
        "/songs", json={"theme": "x"},
        headers={"Authorization": f"Bearer {token}"},
    )
    run_id = create.json()["run_id"]
    run_dir = _find_run_dir(run_id)
    assert run_dir.exists()

    r = client.delete(
        f"/songs/{run_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 204
    assert not run_dir.exists()

    # GET now 404s
    r2 = client.get(f"/songs/{run_id}", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 404


def test_delete_song_409_when_worker_active(app):
    """Don't let users delete a run that's mid-encode — files would
    vanish out from under the worker."""
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    create = client.post(
        "/songs", json={"theme": "x"},
        headers={"Authorization": f"Bearer {token}"},
    )
    run_id = create.json()["run_id"]
    run_dir = _find_run_dir(run_id)
    for active in ("generating_song", "generating_cover", "assembling"):
        state = json.loads((run_dir / "api_state.json").read_text())
        state["status"] = active
        (run_dir / "api_state.json").write_text(json.dumps(state))
        r = client.delete(
            f"/songs/{run_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 409, (
            f"delete must refuse while status={active!r}, got {r.status_code}"
        )
        assert run_dir.exists()


def test_delete_song_404_for_unknown_id(app):
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    r = client.delete(
        "/songs/never-existed",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404


# ─────────────── POST /songs/{id}/regenerate-cover ───────────────────────────

def test_regenerate_cover_sets_flag_and_spawns(app):
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    from pipeline import api as api_mod
    spawn_calls = []
    def fake_spawn(args, run_dir):
        spawn_calls.append((args, run_dir))
        return 99999
    api_mod.set_spawn_fn(fake_spawn)

    create = client.post(
        "/songs", json={"theme": "x"},
        headers={"Authorization": f"Bearer {token}"},
    )
    run_id = create.json()["run_id"]
    run_dir = _find_run_dir(run_id)
    # Force state to complete
    state = json.loads((run_dir / "api_state.json").read_text())
    state["status"] = "complete"
    (run_dir / "api_state.json").write_text(json.dumps(state))

    r = client.post(
        f"/songs/{run_id}/regenerate-cover",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    new_state = json.loads((run_dir / "api_state.json").read_text())
    assert new_state["status"] == "generating_cover"
    assert new_state["regenerate_cover"] is True
    assert len(spawn_calls) == 1


def test_regenerate_cover_409_when_not_complete(app):
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    create = client.post(
        "/songs", json={"theme": "x"},
        headers={"Authorization": f"Bearer {token}"},
    )
    run_id = create.json()["run_id"]
    r = client.post(
        f"/songs/{run_id}/regenerate-cover",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 409


# ─────────────── Sharing ────────────────────────────────────────────────────

def test_share_song_mints_token_and_is_idempotent(app):
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    create = client.post(
        "/songs", json={"theme": "x"},
        headers={"Authorization": f"Bearer {token}"},
    )
    run_id = create.json()["run_id"]
    run_dir = _find_run_dir(run_id)
    state = json.loads((run_dir / "api_state.json").read_text())
    state["status"] = "complete"
    (run_dir / "api_state.json").write_text(json.dumps(state))

    r1 = client.post(
        f"/songs/{run_id}/share",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r1.status_code == 200, r1.text
    body1 = r1.json()
    assert body1["token"]
    assert body1["url"].endswith(f"/p/{body1['token']}")

    # Second call returns the same token (idempotent)
    r2 = client.post(
        f"/songs/{run_id}/share",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.json()["token"] == body1["token"]


def test_share_song_409_when_not_complete(app):
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    create = client.post(
        "/songs", json={"theme": "x"},
        headers={"Authorization": f"Bearer {token}"},
    )
    run_id = create.json()["run_id"]
    r = client.post(
        f"/songs/{run_id}/share",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 409


def test_public_page_serves_without_auth(app):
    """The whole point of share: anyone with the link can view,
    no auth required. Hit /p/{token} with NO Authorization header
    and confirm 200 + correct content type."""
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    create = client.post(
        "/songs", json={"theme": "x"},
        headers={"Authorization": f"Bearer {token}"},
    )
    run_id = create.json()["run_id"]
    run_dir = _find_run_dir(run_id)
    state = json.loads((run_dir / "api_state.json").read_text())
    state["status"] = "complete"
    (run_dir / "api_state.json").write_text(json.dumps(state))

    share = client.post(
        f"/songs/{run_id}/share",
        headers={"Authorization": f"Bearer {token}"},
    )
    share_token = share.json()["token"]

    # NO Authorization header on this request — the public page MUST
    # be reachable anonymously.
    r = client.get(f"/p/{share_token}")
    assert r.status_code == 200, r.text
    assert "text/html" in r.headers["content-type"]
    # Open Graph + Twitter Card markers
    assert 'property="og:title"' in r.text
    assert 'property="og:video"' in r.text
    assert 'name="twitter:card"' in r.text


def test_public_page_404_for_bad_token(app):
    fastapi_app, _ = app
    client = TestClient(fastapi_app)
    r = client.get("/p/totally-bogus-token")
    assert r.status_code == 404


def test_unshare_revokes_link(app):
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    create = client.post(
        "/songs", json={"theme": "x"},
        headers={"Authorization": f"Bearer {token}"},
    )
    run_id = create.json()["run_id"]
    run_dir = _find_run_dir(run_id)
    state = json.loads((run_dir / "api_state.json").read_text())
    state["status"] = "complete"
    (run_dir / "api_state.json").write_text(json.dumps(state))

    share = client.post(
        f"/songs/{run_id}/share",
        headers={"Authorization": f"Bearer {token}"},
    )
    share_token = share.json()["token"]
    # Pre-revocation: public page works
    assert client.get(f"/p/{share_token}").status_code == 200

    # Revoke
    r = client.delete(
        f"/songs/{run_id}/share",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 204

    # Post-revocation: public page is gone
    assert client.get(f"/p/{share_token}").status_code == 404


# ─────────────── Concurrent-runs cap ─────────────────────────────────────────

def test_approve_429_when_another_run_active(app, monkeypatch):
    """A second song's /approve must refuse with 429 while another
    of the user's runs is mid-generation. Prevents N×Suno spend
    from a multi-tap accident."""
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    from pipeline import api as api_mod, credits, db
    from pipeline.auth import User, require_user
    monkeypatch.setattr(credits, "get_balance", lambda uid: 100)
    monkeypatch.setattr(credits, "check_or_deduct",
                        lambda user, amount, run_id, reason: 99)
    monkeypatch.setattr(db, "get_balance", lambda uid: 100)
    api_mod.set_spawn_fn(lambda args, run_dir: 12345)

    # Use a non-service identity so the concurrency cap actually fires
    # (service tokens bypass per _enforce_concurrent_song_limit).
    fastapi_app.dependency_overrides[require_user] = lambda: User(
        id="admin", email="t@example.com", role="user",
    )
    try:
        # Run A → set to generating_song manually (simulates in-flight)
        create_a = client.post("/songs", json={"theme": "a"},
                               headers={"Authorization": f"Bearer {token}"})
        run_a = create_a.json()["run_id"]
        run_a_dir = _find_run_dir(run_a)
        sa = json.loads((run_a_dir / "api_state.json").read_text())
        sa["status"] = "generating_song"
        (run_a_dir / "api_state.json").write_text(json.dumps(sa))

        # Run B is fresh awaiting_approval
        create_b = client.post("/songs", json={"theme": "b"},
                               headers={"Authorization": f"Bearer {token}"})
        run_b = create_b.json()["run_id"]

        # Approve B → must 429
        r = client.post(f"/songs/{run_b}/approve",
                        headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 429, r.text
        assert "in progress" in r.text
    finally:
        fastapi_app.dependency_overrides.pop(require_user, None)


# ─────────────── Downgrade refund ─────────────────────────────────────────────

def test_downgrade_refunds_surcharge_once(app, monkeypatch):
    """GET /songs/{id} on a cinematic run that downgraded to static must
    refund the 2-credit surcharge exactly once, then set surcharge_refunded=True
    so a second GET is a no-op."""
    fastapi_app, token = app
    client = TestClient(fastapi_app)

    # Create a song via the API to get a real run dir under the authed user.
    create = client.post(
        "/songs", json={"theme": "x"},
        headers={"Authorization": f"Bearer {token}"},
    )
    run_id = create.json()["run_id"]
    run_dir = _find_run_dir(run_id)

    # Overwrite api_state.json to look like a complete cinematic run
    # that downgraded to static (video_downgraded=True, no surcharge_refunded).
    state = json.loads((run_dir / "api_state.json").read_text())
    state["status"] = "complete"
    state["video_mode"] = "cinematic"
    state["video_downgraded"] = True
    # surcharge_refunded deliberately absent
    state.pop("surcharge_refunded", None)
    (run_dir / "api_state.json").write_text(json.dumps(state))

    # Update song.json to reflect cinematic video_mode too.
    song_data = json.loads((run_dir / "song.json").read_text())
    song_data["video_mode"] = "cinematic"
    (run_dir / "song.json").write_text(json.dumps(song_data))

    import pipeline.credits as credits_mod
    calls = []
    monkeypatch.setattr(
        credits_mod, "refund",
        lambda user, **kw: calls.append(kw["amount"]),
    )

    # First GET — should trigger refund(amount=2).
    r1 = client.get(f"/songs/{run_id}", headers={"Authorization": f"Bearer {token}"})
    assert r1.status_code == 200, r1.text

    # Second GET — refund must NOT be called again (idempotent).
    r2 = client.get(f"/songs/{run_id}", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200, r2.text

    # Exactly one refund of 2 credits total.
    assert calls == [2], f"expected [2] but got {calls}"

    # The flag must be persisted so future GETs are no-ops.
    final_state = json.loads((run_dir / "api_state.json").read_text())
    assert final_state.get("surcharge_refunded") is True


def test_normal_song_get_does_not_refund(app, monkeypatch):
    """GET /songs/{id} on a normal complete run (no video_downgraded flag)
    must never call credits.refund, regardless of how many times it is called."""
    fastapi_app, token = app
    client = TestClient(fastapi_app)

    # Create a song via the API to get a real run dir under the authed user.
    create = client.post(
        "/songs", json={"theme": "x"},
        headers={"Authorization": f"Bearer {token}"},
    )
    run_id = create.json()["run_id"]
    run_dir = _find_run_dir(run_id)

    # Mark the run complete without any video_downgraded flag — a plain
    # static or cinematic-success run.
    state = json.loads((run_dir / "api_state.json").read_text())
    state["status"] = "complete"
    # Deliberately omit video_downgraded
    state.pop("video_downgraded", None)
    state.pop("surcharge_refunded", None)
    (run_dir / "api_state.json").write_text(json.dumps(state))

    import pipeline.credits as credits_mod
    refund_calls = []
    monkeypatch.setattr(
        credits_mod, "refund",
        lambda user, **kw: refund_calls.append(kw["amount"]),
    )

    r = client.get(f"/songs/{run_id}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text

    assert refund_calls == [], (
        f"credits.refund must not be called for a normal (non-downgraded) song, "
        f"but got calls: {refund_calls}"
    )


def test_post_songs_persists_producer_fields(app):
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    r = client.post(
        "/songs",
        json={"theme": "sad Arabic ballad about the moon", "language": "ar",
              "vocal_gender": "m"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    run_dir = _find_run_dir(r.json()["run_id"])
    song_json = json.loads((run_dir / "song.json").read_text())
    # New producer fields present and JSON-serialisable (no MagicMock leak).
    assert song_json["style_source"] == "fallback:recipe"
    assert song_json["writer_tier"] == "unknown"
    assert "robotic vocal" in song_json["negative_tags"]  # recipe negatives
