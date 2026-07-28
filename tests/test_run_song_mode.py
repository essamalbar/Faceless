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


def test_import_analyze_stage_writes_script(tmp_path: Path, monkeypatch):
    """YouTube-import pre-stage: a run in status 'analyzing' with a
    youtube_url and NO song.json yet must download + analyse the reference,
    write an ORIGINAL song.json, transition to awaiting_approval, and EXIT
    before any Suno generation. The reference transcript must never touch
    disk."""
    run_dir = tmp_path / "song-run-import"
    run_dir.mkdir()

    # Import-mode run dir: api_state.json only — NO song.json.
    (run_dir / "api_state.json").write_text(json.dumps({
        "kind": "song",
        "status": "analyzing",
        "youtube_url": "https://youtu.be/abc123",
        "import_instruction": "make it sadder",
        "video_mode": "static",
        "language": "ar",
    }))

    import pipeline.song_import as si
    from pipeline.song_lyrics import SongScript

    monkeypatch.setattr(si, "download_audio", lambda url, d: d / "reference.m4a")
    monkeypatch.setattr(
        si, "analyze_reference",
        lambda audio, *, llm, language: (
            {"bpm": 90, "genre": "pop", "mood": "sad",
             "instrumentation": "oud", "language": "ar",
             "one_line_theme": "loss", "section_structure": "V,C"},
            "synthetic reference transcript"),
    )
    monkeypatch.setattr(
        si, "build_inspired_script",
        lambda **kw: SongScript(
            title="ليل", lyrics="[Verse 1]\nx\n\n[Chorus]\ny\n",
            style_prompt="pop, 90 BPM", cover_prompt="c",
            language="ar", art_direction="moonlit",
            scene_prompts=["a", "b"], negative_tags="robotic vocal, off-key"),
    )

    # Stub the LLM builder so _build_song_llm() doesn't reach for real keys.
    import pipeline.api as api
    monkeypatch.setattr(api, "_build_song_llm", lambda: object())

    rc = run_mod.main_with_args(["--mode", "song", "--resume", str(run_dir)])

    assert rc == 0
    assert (run_dir / "song.json").exists()
    song_json = json.loads((run_dir / "song.json").read_text())
    # Producer-pass negatives persist on the import path so they reach Suno.
    assert song_json["negative_tags"] == "robotic vocal, off-key"
    state = json.loads((run_dir / "api_state.json").read_text())
    assert state["status"] == "awaiting_approval"
    assert state["title"] == "ليل"

    # The reference transcript must NOT be persisted anywhere.
    assert "synthetic reference transcript" not in (run_dir / "song.json").read_text()
    if (run_dir / "analysis.json").exists():
        assert "synthetic reference transcript" not in (run_dir / "analysis.json").read_text()


def test_import_analyze_fetch_error_fails_run(tmp_path: Path, monkeypatch):
    """YouTube-import pre-stage: when download_audio raises ImportFetchError
    the run must transition to status='failed', failure_stage='analyzing',
    exit with rc=1, and NOT write song.json."""
    run_dir = tmp_path / "song-run-import"
    run_dir.mkdir()

    # Import-mode run dir: api_state.json only — NO song.json.
    (run_dir / "api_state.json").write_text(json.dumps({
        "kind": "song",
        "status": "analyzing",
        "youtube_url": "https://youtu.be/abc123",
        "import_instruction": "make it sadder",
        "video_mode": "static",
        "language": "ar",
    }))

    import pipeline.song_import as si
    import pipeline.api as api

    monkeypatch.setattr(api, "_build_song_llm", lambda: object())

    def boom(url, d):
        raise si.ImportFetchError("Couldn't fetch that link")

    monkeypatch.setattr(si, "download_audio", boom)

    rc = run_mod.main_with_args(["--mode", "song", "--resume", str(run_dir)])

    state = json.loads((run_dir / "api_state.json").read_text())
    assert rc == 1
    assert state["status"] == "failed"
    assert state["failure_stage"] == "analyzing"
    assert not (run_dir / "song.json").exists()


def test_cover_analyze_stage_writes_script(tmp_path: Path, monkeypatch):
    """Upload-cover pre-stage: a run in status 'analyzing' with mode='cover'
    and an uploaded reference on disk (NO song.json) must analyse the audio,
    build a cover script that KEEPS the words, write song.json carrying
    mode='cover' + reference_filename, and transition to awaiting_approval."""
    run_dir = tmp_path / "song-run-cover"
    run_dir.mkdir()
    (run_dir / "reference.mp3").write_bytes(b"\x00\x01\x02")
    (run_dir / "api_state.json").write_text(json.dumps({
        "kind": "song", "status": "analyzing", "mode": "cover",
        "reference_filename": "reference.mp3",
        "import_instruction": "warmer", "video_mode": "static", "language": "ar",
    }))

    import pipeline.song_import as si
    from pipeline.song_lyrics import SongScript

    seen = {}
    def fake_analyze(audio, *, llm, language):
        seen["audio"] = Path(audio).name
        return ({"bpm": 100, "genre": "pop", "mood": "warm",
                 "instrumentation": "oud", "language": "ar",
                 "one_line_theme": "home", "section_structure": "V,C"},
                "the original sung words")
    monkeypatch.setattr(si, "analyze_reference", fake_analyze)
    def fake_cover_script(*, llm, analysis, transcript, instruction, language):
        seen["transcript"] = transcript
        return SongScript(
            title="عودة", lyrics="[Verse 1]\nthe original sung words\n[Chorus]\nhome\n",
            style_prompt="pop, 100 BPM", cover_prompt="c",
            language="ar", art_direction="", scene_prompts=[])
    monkeypatch.setattr(si, "build_cover_script", fake_cover_script)

    import pipeline.api as api
    monkeypatch.setattr(api, "_build_song_llm", lambda: object())

    rc = run_mod.main_with_args(["--mode", "song", "--resume", str(run_dir)])

    assert rc == 0
    assert seen["audio"] == "reference.mp3"   # analysed the uploaded file
    song_json = json.loads((run_dir / "song.json").read_text())
    assert song_json["mode"] == "cover"
    assert song_json["reference_filename"] == "reference.mp3"
    state = json.loads((run_dir / "api_state.json").read_text())
    assert state["status"] == "awaiting_approval"
    assert state["title"] == "عودة"
    # Transcript (raw words) must NOT be persisted to analysis.json.
    if (run_dir / "analysis.json").exists():
        assert "the original sung words" not in (run_dir / "analysis.json").read_text()


def test_cover_post_approve_uses_cover_endpoint(tmp_path: Path, monkeypatch):
    """Cover-mode post-approve must route to submit_cover_job (upload-cover),
    upload the reference, and NEVER call the text→song submit_song_job."""
    run_dir = tmp_path / "song-run-cover2"
    run_dir.mkdir()
    (run_dir / "reference.mp3").write_bytes(b"\x00\x01")
    (run_dir / "song.json").write_text(json.dumps({
        "title": "Cover", "lyrics": "[Verse 1]\nhi\n[Chorus]\nworld",
        "style_prompt": "Arabic pop, 100 BPM", "cover_prompt": "moonlight",
        "language": "ar", "mode": "cover", "reference_filename": "reference.mp3",
        "vocal_gender": "f",
    }))
    (run_dir / "api_state.json").write_text(json.dumps({
        "kind": "song", "status": "generating_song", "mode": "cover",
        "reference_filename": "reference.mp3",
    }))

    calls = {"cover": 0, "song": 0, "upload": 0}
    def fake_cover_submit(client, *, upload_url, lyrics, style_prompt, title,
                          model=song.SUNO_MODEL_ID, **_extra):
        calls["cover"] += 1
        assert upload_url == "https://uguu.se/ref.mp3"
        return "cover-task"
    def fake_song_submit(client, **kw):
        calls["song"] += 1
        return "song-task"
    def fake_wait(client, task_id, *, poll_interval_s=5, timeout_s=600):
        return [song.SongTake(url="https://kie.ai/t1.mp3", duration_s=3.0),
                song.SongTake(url="https://kie.ai/t2.mp3", duration_s=2.8)]
    def fake_download(client, url, out_path):
        shutil.copy(FIXTURE_SONG, out_path)
    def fake_cover_img(*, client, cover_prompt, out_dir):
        out = out_dir / "cover_raw.png"; shutil.copy(FIXTURE_COVER, out); return out

    monkeypatch.setattr(song, "submit_cover_job", fake_cover_submit)
    monkeypatch.setattr(song, "submit_song_job", fake_song_submit)
    monkeypatch.setattr(song, "wait_for_song", fake_wait)
    monkeypatch.setattr(song, "download_take", fake_download)
    monkeypatch.setattr(song_cover, "generate_cover_image", fake_cover_img)
    from pipeline import video as video_mod
    def fake_upload(path, *, content_type):
        calls["upload"] += 1
        return "https://uguu.se/ref.mp3"
    monkeypatch.setattr(video_mod, "_upload_file_get_url", fake_upload)
    monkeypatch.setenv("KIE_API_KEY", "stub")

    rc = run_mod.main_with_args(["--mode", "song", "--resume", str(run_dir)])

    assert rc == 0
    assert calls["cover"] == 1 and calls["song"] == 0  # cover endpoint, not generate
    assert calls["upload"] == 1                         # reference uploaded
    assert (run_dir / "final.mp4").exists()
    state = json.loads((run_dir / "api_state.json").read_text())
    assert state["status"] == "complete"


def _setup_autopublish_run(tmp_path, monkeypatch, *, toggle_on, with_token):
    """A minimal complete-ready static song run whose artist may have the
    YouTube auto-publish toggle; mocks Suno/cover like the other tests."""
    from pipeline import artists as artists_mod
    from pipeline import youtube as yt

    user_root = tmp_path
    run_dir = user_root / "song-run-autopub"
    run_dir.mkdir()
    artist = artists_mod.new_artist(name="ليل", handle="layl")
    artist["auto_publish_youtube"] = toggle_on
    artists_mod.save_artists(user_root, [artist])
    if with_token:
        yt.save_token(user_root, {"refresh_token": "rt", "channel_title": "TV"})

    (run_dir / "song.json").write_text(json.dumps({
        "title": "Test", "lyrics": "[Verse 1]\nhi\n[Chorus]\nworld",
        "style_prompt": "Arabic pop, 72 BPM", "cover_prompt": "sea",
        "language": "ar"}))
    (run_dir / "api_state.json").write_text(json.dumps({
        "kind": "song", "status": "generating_song",
        "artist_id": artist["id"]}))

    def fake_submit(client, **kw):
        return "fake-task"
    def fake_wait(client, task_id, *, poll_interval_s=5, timeout_s=600):
        return [song.SongTake(url="https://kie.ai/t1.mp3", duration_s=3.0),
                song.SongTake(url="https://kie.ai/t2.mp3", duration_s=2.8)]
    def fake_download(client, url, out_path):
        shutil.copy(FIXTURE_SONG, out_path)
    def fake_cover(*, client, cover_prompt, out_dir):
        out = out_dir / "cover_raw.png"; shutil.copy(FIXTURE_COVER, out); return out
    monkeypatch.setattr(song, "submit_song_job", fake_submit)
    monkeypatch.setattr(song, "wait_for_song", fake_wait)
    monkeypatch.setattr(song, "download_take", fake_download)
    monkeypatch.setattr(song_cover, "generate_cover_image", fake_cover)
    monkeypatch.setenv("KIE_API_KEY", "stub")
    return run_dir


def test_autopublish_fires_when_toggle_on(tmp_path, monkeypatch):
    run_dir = _setup_autopublish_run(tmp_path, monkeypatch,
                                     toggle_on=True, with_token=True)
    calls = {}
    def fake_publish(rd, ur, artist):
        calls["run"] = rd.name
        return "vid-7", "https://youtu.be/vid-7"
    import pipeline.api as api
    monkeypatch.setattr(api, "_publish_song_to_youtube", fake_publish)

    rc = run_mod.main_with_args(["--mode", "song", "--resume", str(run_dir)])
    assert rc == 0
    assert calls["run"] == "song-run-autopub"
    state = json.loads((run_dir / "api_state.json").read_text())
    assert state["status"] == "complete"
    assert state["youtube_url"] == "https://youtu.be/vid-7"


def test_autopublish_skipped_when_toggle_off(tmp_path, monkeypatch):
    run_dir = _setup_autopublish_run(tmp_path, monkeypatch,
                                     toggle_on=False, with_token=True)
    import pipeline.api as api
    monkeypatch.setattr(api, "_publish_song_to_youtube",
                        lambda *a: (_ for _ in ()).throw(AssertionError("must not publish")))
    rc = run_mod.main_with_args(["--mode", "song", "--resume", str(run_dir)])
    assert rc == 0
    state = json.loads((run_dir / "api_state.json").read_text())
    assert "youtube_url" not in state or state["youtube_url"] is None


def test_autopublish_failure_never_fails_the_run(tmp_path, monkeypatch):
    run_dir = _setup_autopublish_run(tmp_path, monkeypatch,
                                     toggle_on=True, with_token=True)
    import pipeline.api as api
    def boom(*a):
        raise RuntimeError("quota exceeded")
    monkeypatch.setattr(api, "_publish_song_to_youtube", boom)
    rc = run_mod.main_with_args(["--mode", "song", "--resume", str(run_dir)])
    assert rc == 0  # run still succeeds
    state = json.loads((run_dir / "api_state.json").read_text())
    assert state["status"] == "complete"
    assert "quota exceeded" in state["youtube_publish_error"]


def test_cover_post_approve_passes_audio_weight(tmp_path: Path, monkeypatch):
    """The faithfulness knob stored at upload time reaches submit_cover_job."""
    run_dir = tmp_path / "song-run-cover-w"
    run_dir.mkdir()
    (run_dir / "reference.mp3").write_bytes(b"\x00")
    (run_dir / "song.json").write_text(json.dumps({
        "title": "Cover", "lyrics": "[Chorus]\nx", "style_prompt": "s",
        "cover_prompt": "c", "language": "ar", "mode": "cover",
        "reference_filename": "reference.mp3"}))
    (run_dir / "api_state.json").write_text(json.dumps({
        "kind": "song", "status": "generating_song", "mode": "cover",
        "reference_filename": "reference.mp3", "audio_weight": 0.8}))

    seen = {}
    def fake_cover_submit(client, *, upload_url, lyrics, style_prompt, title,
                          model=song.SUNO_MODEL_ID, **extra):
        seen.update(extra)
        return "cover-task"
    monkeypatch.setattr(song, "submit_cover_job", fake_cover_submit)
    monkeypatch.setattr(song, "wait_for_song", lambda *a, **k: [
        song.SongTake(url="https://kie.ai/t1.mp3", duration_s=3.0),
        song.SongTake(url="https://kie.ai/t2.mp3", duration_s=2.8)])
    monkeypatch.setattr(song, "download_take",
                        lambda c, u, p: shutil.copy(FIXTURE_SONG, p))
    monkeypatch.setattr(song_cover, "generate_cover_image",
                        lambda *, client, cover_prompt, out_dir:
                        (shutil.copy(FIXTURE_COVER, out_dir / "cover_raw.png"),
                         out_dir / "cover_raw.png")[1])
    from pipeline import video as video_mod
    monkeypatch.setattr(video_mod, "_upload_file_get_url",
                        lambda p, *, content_type: "https://u/r.mp3")
    monkeypatch.setenv("KIE_API_KEY", "stub")

    rc = run_mod.main_with_args(["--mode", "song", "--resume", str(run_dir)])
    assert rc == 0
    assert seen.get("audio_weight") == 0.8


def test_song_post_approve_passes_default_negative_tags(tmp_path: Path, monkeypatch):
    """Both Suno branches must carry the quality negative tags."""
    run_dir = tmp_path / "song-run-negtags"
    run_dir.mkdir()
    (run_dir / "song.json").write_text(json.dumps({
        "title": "Test", "lyrics": "[Verse 1]\nhi\n[Chorus]\nworld",
        "style_prompt": "s", "cover_prompt": "sea", "language": "ar"}))
    (run_dir / "api_state.json").write_text(json.dumps({
        "kind": "song", "status": "generating_song"}))

    seen = {}
    def fake_submit(client, *, lyrics, style_prompt, title,
                    model=song.SUNO_MODEL_ID, **extra):
        seen.update(extra)
        return "fake-task"
    monkeypatch.setattr(song, "submit_song_job", fake_submit)
    monkeypatch.setattr(song, "wait_for_song", lambda *a, **k: [
        song.SongTake(url="https://kie.ai/t1.mp3", duration_s=3.0),
        song.SongTake(url="https://kie.ai/t2.mp3", duration_s=2.8)])
    monkeypatch.setattr(song, "download_take",
                        lambda c, u, p: shutil.copy(FIXTURE_SONG, p))
    monkeypatch.setattr(song_cover, "generate_cover_image",
                        lambda *, client, cover_prompt, out_dir:
                        (shutil.copy(FIXTURE_COVER, out_dir / "cover_raw.png"),
                         out_dir / "cover_raw.png")[1])
    monkeypatch.setenv("KIE_API_KEY", "stub")

    rc = run_mod.main_with_args(["--mode", "song", "--resume", str(run_dir)])
    assert rc == 0
    assert "robotic vocal" in seen.get("negative_tags", "")
