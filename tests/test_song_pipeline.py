from __future__ import annotations

import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_COVER = REPO_ROOT / "tests" / "fixtures" / "song" / "cover.png"
FIXTURE_SONG = REPO_ROOT / "tests" / "fixtures" / "song" / "short_song.mp3"


@pytest.fixture
def wired_app(monkeypatch, tmp_path: Path):
    token = "e2e-token"
    monkeypatch.setenv("FACELESS_API_TOKEN", token)
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path / "out"))
    monkeypatch.setenv("KIE_API_KEY", "stub")

    from pipeline import api as api_mod, song, song_cover, credits

    # Lyrics LLM
    canned = json.dumps({
        "title": "Test",
        "lyrics": "[Verse 1]\nline\n[Chorus]\nhook\n[Verse 2]\nline\n[Chorus]\nhook",
        "style_prompt": "Arabic pop ballad, slow tempo 72 BPM, oud + strings, male vocal, modern 2020s, melancholic minor key",
        "cover_prompt": "moonlight",
    })
    fake_llm = MagicMock()
    fake_llm.complete = MagicMock(return_value=canned)
    monkeypatch.setattr(api_mod, "_build_song_llm", lambda: fake_llm)

    # Credits — always allow
    monkeypatch.setattr(credits, "get_balance", lambda uid: 100)
    monkeypatch.setattr(credits, "check_or_deduct",
                        lambda user, amount, run_id, reason: 99)

    # Suno + cover stubs
    monkeypatch.setattr(song, "submit_song_job",
                        lambda client, **kw: "fake-task")
    monkeypatch.setattr(
        song, "wait_for_song",
        lambda client, task_id, **kw: [
            song.SongTake(url="https://x/t1.mp3", duration_s=3.0),
            song.SongTake(url="https://x/t2.mp3", duration_s=2.8),
        ],
    )
    monkeypatch.setattr(
        song, "download_take",
        lambda client, url, out_path: shutil.copy(FIXTURE_SONG, out_path),
    )

    def fake_cover(*, client, cover_prompt, out_dir):
        out = out_dir / "cover_raw.png"
        shutil.copy(FIXTURE_COVER, out)
        return out
    monkeypatch.setattr(song_cover, "generate_cover_image", fake_cover)

    # In-process spawn: run main_with_args directly so the test executes
    # the real pipeline plumbing. approve_song now writes
    # status="generating_song" BEFORE calling _SPAWN_FN and only writes
    # `pid` afterwards (without clobbering the worker's status), so no
    # patching of _write_state is required.
    import run as run_mod

    def in_process_spawn(args, run_dir):
        rc = run_mod.main_with_args(args)
        if rc != 0:
            raise RuntimeError(f"pipeline failed rc={rc}")
        return 99999

    api_mod.set_spawn_fn(in_process_spawn)

    return api_mod.app, token


def test_full_song_pipeline(wired_app):
    fastapi_app, token = wired_app
    client = TestClient(fastapi_app)

    # 1. Writer pass
    r = client.post("/songs", json={"theme": "moon"},
                    headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 201
    run_id = r.json()["run_id"]

    # 2. Get script
    r = client.get(f"/songs/{run_id}/script",
                   headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert "[Chorus]" in r.json()["lyrics"]

    # 3. Approve (runs in-process spawn which executes the post-approve subprocess)
    r = client.post(f"/songs/{run_id}/approve",
                    headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200

    # 4. After in-process spawn, the run should be complete
    r = client.get(f"/songs/{run_id}",
                   headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "complete", body
    assert body["has_video"] is True

    # 5. Video streams back
    r = client.get(f"/songs/{run_id}/video",
                   headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.headers["content-type"] == "video/mp4"
    assert len(r.content) > 1000
