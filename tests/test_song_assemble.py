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
