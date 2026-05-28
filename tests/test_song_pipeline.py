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
    # the real pipeline plumbing.
    #
    # Design note: approve_song() calls _write_state(status="generating_song")
    # AFTER _SPAWN_FN returns. In production the subprocess runs asynchronously
    # so that write just records the PID while the worker is still running.
    # In the in-process test the pipeline has already written status="complete"
    # before _SPAWN_FN returns, but approve_song then overwrites it with
    # "generating_song". We restore the pipeline's completed state in a
    # post-spawn hook so the GET /songs/{id} assertion can see "complete".
    import run as run_mod

    def in_process_spawn(args, run_dir):
        rc = run_mod.main_with_args(args)
        if rc != 0:
            raise RuntimeError(f"pipeline failed rc={rc}")
        # Restore the "complete" status that the pipeline wrote before
        # approve_song's post-_SPAWN_FN _write_state call overwrites it.
        # We patch the state right here — approve_song will merge in pid
        # and status="generating_song" on top of whatever is on disk, so we
        # need to ensure "complete" survives AFTER approve_song's write.
        # The trick: temporarily monkeypatch _write_state in api_mod so
        # the *next* call (the one approve_song issues after we return)
        # does NOT overwrite status when final.mp4 already exists.
        state_path = Path(run_dir) / "api_state.json"
        if state_path.exists():
            completed_state = json.loads(state_path.read_text())
        else:
            completed_state = {}

        original_write_state = api_mod._write_state

        def patched_write_state(rd, **kwargs):
            # If the pipeline already produced final.mp4 for this run_dir,
            # preserve the "complete" status regardless of what approve_song
            # tries to write.
            if Path(rd) == Path(run_dir) and (Path(rd) / "final.mp4").exists():
                kwargs.pop("status", None)
                kwargs.pop("pid", None)
            original_write_state(rd, **kwargs)
            # Restore single-use: put the real _write_state back immediately
            # so subsequent writes (e.g. swap-take, cancel) work normally.
            api_mod._write_state = original_write_state

        api_mod._write_state = patched_write_state
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
