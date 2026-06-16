from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from PIL import Image

from pipeline.song_scenes import Segment
from pipeline.song_cinematic import build_filter_complex, assemble_cinematic_song_video


def test_filter_complex_references_every_image():
    segs = [Segment(0, 0.0, 4.0, "in"), Segment(1, 4.0, 8.0, "out")]
    fc = build_filter_complex(segments=segs, n_images=2, ass_filter="", has_watermark=False)
    assert "[0:v]" in fc and "[1:v]" in fc   # both pool inputs referenced
    assert fc.strip().endswith("[v]")        # final label


def test_filter_complex_xfade_offsets_match_boundaries():
    segs = [Segment(0, 0.0, 4.0, "in"), Segment(1, 4.0, 9.0, "out")]
    fc = build_filter_complex(segments=segs, n_images=2, ass_filter="", has_watermark=False)
    assert "xfade" in fc
    # The crossfade STARTS _XFADE_S (0.35s) before the 4.0s boundary so the
    # transition completes on the beat: offset = 4.0 - 0.35 = 3.650.
    assert "offset=3.650" in fc


def test_filter_complex_appends_ass_and_watermark():
    segs = [Segment(0, 0.0, 4.0, "in")]
    fc = build_filter_complex(
        segments=segs, n_images=1,
        ass_filter=",ass='/tmp/lyrics.ass'", has_watermark=True,
    )
    assert "ass='/tmp/lyrics.ass'" in fc
    assert "overlay=W-w-28:28" in fc


def test_assemble_cinematic_produces_playable_mp4(tmp_path):
    # Integration smoke -- real ffmpeg on tiny inputs.
    scene_paths = []
    for i, color in enumerate(["red", "green"], start=1):
        p = tmp_path / f"scene_{i:02d}.png"
        Image.new("RGB", (64, 64), color).save(p)
        scene_paths.append(p)
    song = tmp_path / "song.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=4",
         "-c:a", "libmp3lame", str(song)],
        check=True, capture_output=True,
    )
    out = tmp_path / "final.mp4"
    schedule = [Segment(0, 0.0, 2.0, "in"), Segment(1, 2.0, 4.0, "out")]
    assemble_cinematic_song_video(
        scene_paths=scene_paths, song_mp3=song, out_mp4=out,
        schedule=schedule, lyrics_json=None, title="t", share_token=None,
    )
    assert out.exists()
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type",
         "-of", "csv=p=0", str(out)],
        check=True, capture_output=True, text=True,
    ).stdout
    assert "video" in probe and "audio" in probe
