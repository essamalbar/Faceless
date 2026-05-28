from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

import run as run_mod
from pipeline import song, song_cover


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_COVER = REPO_ROOT / "tests" / "fixtures" / "song" / "cover.png"
FIXTURE_SONG = REPO_ROOT / "tests" / "fixtures" / "song" / "short_song.mp3"


def test_song_post_approve_produces_final_mp4(tmp_path: Path, monkeypatch):
    run_dir = tmp_path / "song-run-1"
    run_dir.mkdir()

    # Pre-populated by the API writer pass:
    (run_dir / "song.json").write_text(json.dumps({
        "title": "Test",
        "lyrics": "[Verse 1]\nhi\n[Chorus]\nworld",
        "style_prompt": "Arabic pop ballad, slow tempo 72 BPM, oud, male vocal, modern, minor key",
        "cover_prompt": "moonlight over the sea",
        "language": "ar",
    }))
    (run_dir / "api_state.json").write_text(json.dumps({
        "kind": "song", "status": "generating_song",
    }))

    def fake_submit(client, *, lyrics, style_prompt, title, model=song.SUNO_MODEL_ID):
        return "fake-task"
    def fake_wait(client, task_id, *, poll_interval_s=5, timeout_s=600):
        return [
            song.SongTake(url="https://kie.ai/t1.mp3", duration_s=3.0),
            song.SongTake(url="https://kie.ai/t2.mp3", duration_s=2.8),
        ]
    def fake_download(client, url, out_path):
        shutil.copy(FIXTURE_SONG, out_path)

    monkeypatch.setattr(song, "submit_song_job", fake_submit)
    monkeypatch.setattr(song, "wait_for_song", fake_wait)
    monkeypatch.setattr(song, "download_take", fake_download)

    def fake_cover(*, client, cover_prompt, out_dir):
        out = out_dir / "cover_raw.png"
        shutil.copy(FIXTURE_COVER, out)
        return out
    monkeypatch.setattr(song_cover, "generate_cover_image", fake_cover)

    monkeypatch.setenv("KIE_API_KEY", "stub")

    rc = run_mod.main_with_args([
        "--mode", "song", "--resume", str(run_dir),
    ])

    assert rc == 0
    assert (run_dir / "final.mp4").exists()
    assert (run_dir / "cover.png").exists()
    assert (run_dir / "takes" / "take_1.mp3").exists()
    assert (run_dir / "takes" / "take_2.mp3").exists()
    assert (run_dir / "song.mp3").exists()

    state = json.loads((run_dir / "api_state.json").read_text())
    assert state["status"] == "complete"
    assert state["chosen_take"] == 1  # longer of 3.0 vs 2.8
