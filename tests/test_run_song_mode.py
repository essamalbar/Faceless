from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

import run as run_mod
from pipeline import song, song_cover, song_assemble, song_beats, song_cinematic


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

    def fake_submit(client, *, lyrics, style_prompt, title,
                    model=song.SUNO_MODEL_ID, **_extra):
        # **_extra absorbs the optional voice-control kwargs
        # (vocal_gender, persona_id, negative_tags) added after Task 2.
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


def _setup_cinematic_run(tmp_path: Path, monkeypatch):
    """Shared harness for the two cinematic tests below — mirrors
    test_song_post_approve_produces_final_mp4 but with video_mode=cinematic
    + scene_prompts + art_direction in song.json, and stubs the new
    cinematic-path modules (scene pool + beats) so no network/audio
    decode is needed. Returns the run_dir."""
    run_dir = tmp_path / "song-run-cinematic"
    run_dir.mkdir()

    (run_dir / "song.json").write_text(json.dumps({
        "title": "Test",
        "lyrics": "[Verse 1]\nhi\n[Chorus]\nworld",
        "style_prompt": "Arabic pop ballad, slow tempo 72 BPM, oud, male vocal, modern, minor key",
        "cover_prompt": "moonlight over the sea",
        "language": "ar",
        "video_mode": "cinematic",
        "art_direction": "noir music video, teal and orange grade",
        "scene_prompts": ["a desert at dusk", "a lone figure walking"],
    }))
    (run_dir / "api_state.json").write_text(json.dumps({
        "kind": "song", "status": "generating_song",
    }))

    def fake_submit(client, *, lyrics, style_prompt, title,
                    model=song.SUNO_MODEL_ID, **_extra):
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

    # Scene pool — return two real PNG paths (reuse the cover fixture).
    def fake_scenes(*, client, art_direction, scene_prompts, out_dir, cover_fallback):
        scenes_dir = out_dir / "scenes"
        scenes_dir.mkdir(parents=True, exist_ok=True)
        paths = []
        for i, _ in enumerate(scene_prompts, start=1):
            dest = scenes_dir / f"scene_{i:02d}.png"
            shutil.copy(FIXTURE_COVER, dest)
            paths.append(dest)
        return paths
    monkeypatch.setattr(song_cover, "generate_scene_images", fake_scenes)

    # Beat detection — fixed stub so no audio decode / librosa needed.
    def fake_beats(song_mp3, *, out_json, fallback_bpm=120.0):
        return {"tempo_bpm": 120.0, "beat_times": [0.0, 1.0, 2.0], "source": "stub"}
    monkeypatch.setattr(song_beats, "detect_beats", fake_beats)

    monkeypatch.setenv("KIE_API_KEY", "stub")
    return run_dir


def test_cinematic_run_invokes_cinematic_assembler(tmp_path: Path, monkeypatch):
    run_dir = _setup_cinematic_run(tmp_path, monkeypatch)

    called = {}

    def fake_cine(*, scene_paths, song_mp3, out_mp4, schedule,
                  lyrics_json=None, title=None, share_token=None):
        called["scene_paths"] = scene_paths
        called["schedule"] = schedule
        out_mp4.write_bytes(b"fake-mp4")
    monkeypatch.setattr(song_cinematic, "assemble_cinematic_song_video", fake_cine)

    rc = run_mod.main_with_args(["--mode", "song", "--resume", str(run_dir)])

    assert rc == 0
    assert called, "cinematic assembler was not called"
    assert len(called["scene_paths"]) == 2
    assert (run_dir / "final.mp4").exists()
    # scene pool rendered to scenes/ via the stubbed generate_scene_images
    assert (run_dir / "scenes" / "scene_01.png").exists()

    state = json.loads((run_dir / "api_state.json").read_text())
    assert state["status"] == "complete"
    assert not state.get("video_downgraded")


def test_cinematic_render_failure_downgrades_to_static(tmp_path: Path, monkeypatch):
    run_dir = _setup_cinematic_run(tmp_path, monkeypatch)

    def boom(*, scene_paths, song_mp3, out_mp4, schedule,
             lyrics_json=None, title=None, share_token=None):
        raise RuntimeError("ffmpeg blew up")
    monkeypatch.setattr(song_cinematic, "assemble_cinematic_song_video", boom)

    static_called = {}

    def fake_static(*, cover_path, song_mp3, out_mp4,
                    lyrics_json=None, title=None, share_token=None):
        static_called["cover_path"] = cover_path
        out_mp4.write_bytes(b"fake-static-mp4")
    monkeypatch.setattr(song_assemble, "assemble_song_video", fake_static)

    rc = run_mod.main_with_args(["--mode", "song", "--resume", str(run_dir)])

    assert rc == 0
    assert static_called, "static assembler was not called on cinematic failure"
    assert (run_dir / "final.mp4").exists()

    state = json.loads((run_dir / "api_state.json").read_text())
    assert state["video_downgraded"] is True
    assert state["status"] == "complete"


def test_cinematic_empty_scene_pool_downgrades_to_static(tmp_path: Path, monkeypatch):
    """When generate_scene_images returns [] the run falls through to the
    static assembler, but the user was charged the cinematic surcharge.
    video_downgraded must be set so the API can reconcile the refund."""
    run_dir = _setup_cinematic_run(tmp_path, monkeypatch)

    # Override the scene-pool stub to return an empty list.
    monkeypatch.setattr(
        song_cover,
        "generate_scene_images",
        lambda *, client, art_direction, scene_prompts, out_dir, cover_fallback: [],
    )

    static_called = {}

    def fake_static(*, cover_path, song_mp3, out_mp4,
                    lyrics_json=None, title=None, share_token=None):
        static_called["cover_path"] = cover_path
        out_mp4.write_bytes(b"fake-static-mp4")
    monkeypatch.setattr(song_assemble, "assemble_song_video", fake_static)

    rc = run_mod.main_with_args(["--mode", "song", "--resume", str(run_dir)])

    assert rc == 0
    assert static_called, "static assembler was not called for empty scene pool"
    assert (run_dir / "final.mp4").exists()

    state = json.loads((run_dir / "api_state.json").read_text())
    assert state["video_downgraded"] is True
    assert state["status"] == "complete"
