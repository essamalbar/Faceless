from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from pipeline import song_assemble


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_COVER = REPO_ROOT / "tests" / "fixtures" / "song" / "cover.png"
FIXTURE_SONG = REPO_ROOT / "tests" / "fixtures" / "song" / "short_song.mp3"


def _ffprobe(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json",
         "-show_streams", "-show_format", str(path)],
        capture_output=True, text=True, check=True,
    )
    return json.loads(out.stdout)


def test_ffprobe_duration_reads_real_mp3():
    d = song_assemble.ffprobe_duration(FIXTURE_SONG)
    assert 2.5 < d < 3.5  # fixture is 3 seconds


def test_assemble_song_video_writes_mp4(tmp_path: Path):
    cover = tmp_path / "cover.png"
    shutil.copy(FIXTURE_COVER, cover)
    song = tmp_path / "song.mp3"
    shutil.copy(FIXTURE_SONG, song)
    out = tmp_path / "final.mp4"
    song_assemble.assemble_song_video(cover_path=cover, song_mp3=song, out_mp4=out)
    assert out.exists()
    assert out.stat().st_size > 1000


def test_assemble_output_has_video_and_audio_streams(tmp_path: Path):
    out = tmp_path / "final.mp4"
    song_assemble.assemble_song_video(
        cover_path=FIXTURE_COVER, song_mp3=FIXTURE_SONG, out_mp4=out,
    )
    info = _ffprobe(out)
    streams = info["streams"]
    video = next((s for s in streams if s["codec_type"] == "video"), None)
    audio = next((s for s in streams if s["codec_type"] == "audio"), None)
    assert video is not None
    assert audio is not None


def test_assemble_output_is_1080x1080_at_25fps(tmp_path: Path):
    out = tmp_path / "final.mp4"
    song_assemble.assemble_song_video(
        cover_path=FIXTURE_COVER, song_mp3=FIXTURE_SONG, out_mp4=out,
    )
    info = _ffprobe(out)
    video = next(s for s in info["streams"] if s["codec_type"] == "video")
    assert video["width"] == 1080
    assert video["height"] == 1080
    fps = video["r_frame_rate"]
    assert fps in ("25/1", "25")


def test_assemble_audio_is_aac_for_browser_compat(tmp_path: Path):
    """Browsers (Chrome, Safari, Firefox) reject MP3 audio in MP4
    container with MEDIA_ERR_SRC_NOT_SUPPORTED. Audio MUST be AAC
    in the output. Suno's source is MP3 (the fixture mirrors this);
    we transcode at 192k which is high-quality and broswer-compatible."""
    out = tmp_path / "final.mp4"
    song_assemble.assemble_song_video(
        cover_path=FIXTURE_COVER, song_mp3=FIXTURE_SONG, out_mp4=out,
    )
    info = _ffprobe(out)
    audio = next(s for s in info["streams"] if s["codec_type"] == "audio")
    assert audio["codec_name"] == "aac", (
        f"expected AAC for MP4 browser compat, got {audio['codec_name']}"
    )


def test_assemble_video_has_faststart_moov_at_front(tmp_path: Path):
    """`-movflags +faststart` puts moov atom at the front for streaming."""
    out = tmp_path / "final.mp4"
    song_assemble.assemble_song_video(
        cover_path=FIXTURE_COVER, song_mp3=FIXTURE_SONG, out_mp4=out,
    )
    head = out.read_bytes()[:64 * 1024]
    moov_pos = head.find(b"moov")
    mdat_pos = head.find(b"mdat")
    assert moov_pos != -1, "moov atom not found in first 64KB"
    if mdat_pos != -1:
        assert moov_pos < mdat_pos, "moov atom must precede mdat (faststart)"


from types import SimpleNamespace

from pipeline.song_assemble import maybe_master


def test_maybe_master_noop_when_flag_off(tmp_path):
    mp3 = tmp_path / "song.mp3"
    mp3.write_bytes(b"fake")
    cfg = SimpleNamespace(song=SimpleNamespace(master_pass=False))
    assert maybe_master(mp3, cfg) is False


def test_maybe_master_noop_when_flag_on_not_yet_implemented(tmp_path, monkeypatch):
    # Approach B is now built (pipeline.mastering.master_track); this locks
    # the graceful-degradation contract instead: if the delegate can't
    # produce a master (e.g. no reference + ffmpeg unavailable), maybe_master
    # must still return False and never raise — mp3_path stays untouched.
    monkeypatch.setattr("pipeline.mastering.master_track", lambda i, o, **k: False)
    mp3 = tmp_path / "song.mp3"
    mp3.write_bytes(b"fake")
    cfg = SimpleNamespace(song=SimpleNamespace(master_pass=True, master_engine="ffmpeg"))
    assert maybe_master(mp3, cfg) is False
    assert mp3.read_bytes() == b"fake"  # untouched on failure


def test_maybe_master_handles_missing_song_config(tmp_path):
    mp3 = tmp_path / "song.mp3"
    mp3.write_bytes(b"fake")
    assert maybe_master(mp3, SimpleNamespace(song=None)) is False


def test_maybe_master_never_shells_out_even_when_flag_on(tmp_path, monkeypatch):
    # Contract flip (Approach B is now built): maybe_master itself no longer
    # shells out directly — it delegates entirely to mastering.master_track.
    # Lock that seam: master_track is called with the right args, and
    # maybe_master's OWN frame never touches subprocess directly (mastering
    # is free to shell out internally; that's covered by test_mastering.py).
    import subprocess
    def _boom(*a, **k):
        raise AssertionError("maybe_master must not shell out directly")
    monkeypatch.setattr(subprocess, "run", _boom)
    monkeypatch.setattr(subprocess, "Popen", _boom)

    calls = {}
    def _fake_master_track(in_path, out_path, *, genre_key, cfg):
        calls["args"] = (Path(in_path), Path(out_path), genre_key)
        Path(out_path).write_bytes(b"mastered")
        return True
    monkeypatch.setattr("pipeline.mastering.master_track", _fake_master_track)

    mp3 = tmp_path / "song.mp3"
    mp3.write_bytes(b"fake")
    cfg = SimpleNamespace(song=SimpleNamespace(master_pass=True, master_engine="ffmpeg"))
    assert maybe_master(mp3, cfg, genre_key="arabic_pop") is True
    assert calls["args"][0] == mp3
    assert calls["args"][2] == "arabic_pop"
    assert mp3.read_bytes() == b"mastered"


def test_maybe_master_delegates_when_flag_on(tmp_path, monkeypatch):
    mp3 = tmp_path / "song.mp3"; mp3.write_bytes(b"orig")
    monkeypatch.setattr("pipeline.mastering.master_track",
                        lambda i, o, **k: (Path(o).write_bytes(b"mastered"), True)[1])
    cfg = SimpleNamespace(song=SimpleNamespace(master_pass=True, master_engine="ffmpeg"))
    assert maybe_master(mp3, cfg, genre_key="arabic_pop") is True
    assert mp3.read_bytes() == b"mastered"


def test_maybe_master_masters_premium_even_without_flag(tmp_path, monkeypatch):
    # Premium tier masters by default (part of the surcharge), even with
    # master_pass off — this is what the approve-gate "+ master" promises.
    mp3 = tmp_path / "song.mp3"; mp3.write_bytes(b"orig")
    monkeypatch.setattr("pipeline.mastering.master_track",
                        lambda i, o, **k: (Path(o).write_bytes(b"mastered"), True)[1])
    cfg = SimpleNamespace(song=SimpleNamespace(master_pass=False, master_engine="ffmpeg"))
    assert maybe_master(mp3, cfg, genre_key="arabic_pop", quality_tier="premium") is True
    assert mp3.read_bytes() == b"mastered"


def test_maybe_master_skips_standard_without_flag(tmp_path):
    # Standard tier with master_pass off must NOT master (spec: premium-only).
    mp3 = tmp_path / "song.mp3"; mp3.write_bytes(b"orig")
    cfg = SimpleNamespace(song=SimpleNamespace(master_pass=False, master_engine="ffmpeg"))
    assert maybe_master(mp3, cfg, genre_key="x", quality_tier="standard") is False
    assert mp3.read_bytes() == b"orig"
