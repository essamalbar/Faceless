from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from pipeline.song_scenes import Segment
from pipeline.song_cinematic import (
    segment_vf,
    _final_filter,
    assemble_cinematic_song_video,
)


def test_segment_vf_in_zooms_up_out_zooms_down():
    vf_in = segment_vf(Segment(0, 0.0, 4.0, "in"), frames=100)
    vf_out = segment_vf(Segment(0, 0.0, 4.0, "out"), frames=100)
    # "in" starts at 1.0 and grows; "out" starts at ZOOM_END and shrinks.
    assert "zoompan=z='1+" in vf_in
    assert "zoompan=z='1.13" in vf_out
    # Both pin SAR + pixel format so the concat demuxer joins clips cleanly.
    assert "setsar=1" in vf_in and "format=yuv420p" in vf_in


def test_final_filter_with_watermark_and_ass():
    fc = _final_filter(",ass='/tmp/lyrics.ass'", has_watermark=True)
    assert "ass='/tmp/lyrics.ass'" in fc
    assert "overlay=W-w-28:28" in fc
    assert "[2:v]scale=240:55[wm]" in fc   # watermark is input index 2
    assert fc.strip().endswith("[v]")


def test_final_filter_without_watermark():
    fc = _final_filter("", has_watermark=False)
    assert "overlay" not in fc
    assert fc.strip().endswith("[v]")


def test_assemble_cinematic_produces_playable_mp4(tmp_path):
    # Integration smoke -- real ffmpeg, per-clip render + concat + final mux.
    scene_paths = []
    for i, color in enumerate(["red", "green", "blue"], start=1):
        p = tmp_path / f"scene_{i:02d}.png"
        Image.new("RGB", (64, 64), color).save(p)
        scene_paths.append(p)
    song = tmp_path / "song.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=6",
         "-c:a", "libmp3lame", str(song)],
        check=True, capture_output=True,
    )
    out = tmp_path / "final.mp4"
    # 3 segments cycling 3 images -> exercises render + concat + final mux.
    schedule = [
        Segment(0, 0.0, 2.0, "in"),
        Segment(1, 2.0, 4.0, "out"),
        Segment(2, 4.0, 6.0, "in"),
    ]
    assemble_cinematic_song_video(
        scene_paths=scene_paths, song_mp3=song, out_mp4=out,
        schedule=schedule, lyrics_json=None, title="t", share_token=None,
    )
    assert out.exists()
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_type:format=duration", "-of", "json", str(out)],
        check=True, capture_output=True, text=True,
    ).stdout
    data = json.loads(probe)
    kinds = {s["codec_type"] for s in data["streams"]}
    assert "video" in kinds and "audio" in kinds
    # bounded clips -> ~6s, NOT a runaway (the old looped-zoompan bug
    # produced multi-hour streams).
    assert 5.0 <= float(data["format"]["duration"]) <= 7.0


def test_assemble_cinematic_rejects_empty_schedule(tmp_path):
    song = tmp_path / "song.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
         "-c:a", "libmp3lame", str(song)],
        check=True, capture_output=True,
    )
    with pytest.raises(ValueError):
        assemble_cinematic_song_video(
            scene_paths=[tmp_path / "x.png"], song_mp3=song,
            out_mp4=tmp_path / "o.mp4", schedule=[],
        )
