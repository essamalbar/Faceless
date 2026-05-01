"""Assembler tests. FFmpeg run is mocked; we verify the command-line graph."""
from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.assemble import (
    KEN_BURNS_PATTERNS,
    assemble_video,
    build_filter_graph,
    pick_motion_pattern,
)
from pipeline.types import Shot


def _shots(durations_ms: list[int]) -> list[Shot]:
    out: list[Shot] = []
    cursor = 0
    for i, d in enumerate(durations_ms):
        out.append(Shot(
            index=i + 1, start_ms=cursor, end_ms=cursor + d,
            arabic_text="", english_prompt="", negative_prompt="", seed=0,
        ))
        cursor += d
    return out


def test_motion_pattern_cycles():
    assert pick_motion_pattern(0) == KEN_BURNS_PATTERNS[0]
    assert pick_motion_pattern(1) == KEN_BURNS_PATTERNS[1]
    assert pick_motion_pattern(4) == KEN_BURNS_PATTERNS[0]  # cycles


def test_filter_graph_has_one_zoompan_per_shot():
    graph = build_filter_graph(
        shots=_shots([5000, 4000]),
        output_w=1920, output_h=1080,
        crossfade_ms=800,
        burn_caption_ass=None,
    )
    assert graph.count("zoompan=") == 2


def test_filter_graph_includes_xfade_between_shots():
    graph = build_filter_graph(
        shots=_shots([5000, 4000, 3000]),
        output_w=1920, output_h=1080, crossfade_ms=800,
        burn_caption_ass=None,
    )
    # 3 shots → 2 xfade nodes
    assert graph.count("xfade=") == 2


def test_filter_graph_includes_subtitles_when_burn_in_set():
    graph = build_filter_graph(
        shots=_shots([5000]),
        output_w=1920, output_h=1080, crossfade_ms=800,
        burn_caption_ass=Path("/tmp/captions.ass"),
    )
    assert "subtitles=" in graph
    assert "captions.ass" in graph


def test_assemble_invokes_ffmpeg_with_expected_inputs(monkeypatch, tmp_run_dir: Path):
    captured: dict = {}

    def fake_run(args: list[str]):
        captured["args"] = args

    monkeypatch.setattr("pipeline.assemble._run_ffmpeg", fake_run)

    images_dir = tmp_run_dir / "images"
    images_dir.mkdir()
    (images_dir / "01.png").write_bytes(b"x")
    (images_dir / "02.png").write_bytes(b"x")
    narration = tmp_run_dir / "narration.mp3"
    narration.write_bytes(b"x")
    music = tmp_run_dir / "music_track.mp3"
    music.write_bytes(b"x")

    assemble_video(
        shots=_shots([5000, 4000]),
        images_dir=images_dir,
        narration_path=narration,
        music_path=music,
        out_path=tmp_run_dir / "final.mp4",
        burn_caption_ass=None,
        output_width=1920, output_height=1080,
        crossfade_ms=800, music_duck_db=-18, music_silence_db=-8,
        fade_in_s=3, fade_out_s=3,
    )
    args = captured["args"]
    assert "-i" in args
    assert str(narration) in args
    assert str(music) in args
    assert any("01.png" in a for a in args)
    assert any("02.png" in a for a in args)
    assert str(tmp_run_dir / "final.mp4") in args


def test_assemble_skips_when_output_exists(monkeypatch, tmp_run_dir: Path):
    called = {"n": 0}
    monkeypatch.setattr("pipeline.assemble._run_ffmpeg", lambda args: called.update(n=called["n"] + 1))
    out = tmp_run_dir / "final.mp4"
    out.write_bytes(b"existing")
    assemble_video(
        shots=_shots([5000]), images_dir=tmp_run_dir, narration_path=tmp_run_dir / "n.mp3",
        music_path=tmp_run_dir / "m.mp3", out_path=out, burn_caption_ass=None,
        output_width=1920, output_height=1080, crossfade_ms=800,
        music_duck_db=-18, music_silence_db=-8, fade_in_s=3, fade_out_s=3,
    )
    assert called["n"] == 0


# ============================================================================
# Shorts assembler tests
# ============================================================================

def test_shorts_filter_graph_one_scale_per_clip():
    from pipeline.assemble import build_shorts_filter_graph
    g = build_shorts_filter_graph(
        clip_durations_s=[7.0, 7.0, 7.0, 7.0],
        output_w=1080, output_h=1920, crossfade_ms=350,
        burn_caption_ass=None,
    )
    assert g.count("scale=1080:1920") == 4
    # 4 clips → 3 xfade chains
    assert g.count("xfade=") == 3


def test_shorts_filter_graph_includes_caption_burn():
    from pipeline.assemble import build_shorts_filter_graph
    g = build_shorts_filter_graph(
        clip_durations_s=[7.0],
        output_w=1080, output_h=1920, crossfade_ms=350,
        burn_caption_ass=Path("/tmp/x.ass"),
    )
    assert "subtitles=" in g
    assert "x.ass" in g


def test_shorts_filter_graph_audio_mix_three_inputs():
    from pipeline.assemble import build_shorts_filter_graph
    g = build_shorts_filter_graph(
        clip_durations_s=[7.0, 7.0, 7.0, 7.0],
        output_w=1080, output_h=1920, crossfade_ms=350,
        burn_caption_ass=None,
    )
    # narration + music + ambient → amix=inputs=3
    assert "amix=inputs=3" in g
    # narration is at index N=4 (after the 4 video inputs)
    assert "[4:a]" in g
    # music is at index N+1=5
    assert "[5:a]" in g


def test_assemble_shorts_invokes_ffmpeg(monkeypatch, tmp_run_dir: Path):
    from pipeline.assemble import assemble_shorts_video
    captured: dict = {}
    monkeypatch.setattr("pipeline.assemble._run_ffmpeg",
                        lambda args: captured.update(args=args))

    clips_dir = tmp_run_dir / "clips"
    clips_dir.mkdir()
    clip_paths = []
    for i in range(1, 5):
        p = clips_dir / f"{i:02d}.mp4"
        p.write_bytes(b"x")
        clip_paths.append(p)
    narr = tmp_run_dir / "narration.mp3"; narr.write_bytes(b"x")
    music = tmp_run_dir / "music.mp3"; music.write_bytes(b"x")

    assemble_shorts_video(
        clip_paths=clip_paths,
        clip_durations_s=[7.0, 7.0, 7.0, 7.0],
        narration_path=narr, music_path=music,
        out_path=tmp_run_dir / "final.mp4",
        burn_caption_ass=None,
    )
    args = captured["args"]
    assert all(str(p) in args for p in clip_paths)
    assert str(narr) in args
    assert str(music) in args
    assert str(tmp_run_dir / "final.mp4") in args


def test_assemble_shorts_skips_if_output_exists(monkeypatch, tmp_run_dir: Path):
    from pipeline.assemble import assemble_shorts_video
    called = {"n": 0}
    monkeypatch.setattr("pipeline.assemble._run_ffmpeg",
                        lambda args: called.update(n=called["n"] + 1))
    out = tmp_run_dir / "final.mp4"
    out.write_bytes(b"existing")
    assemble_shorts_video(
        clip_paths=[tmp_run_dir / "01.mp4"],
        clip_durations_s=[7.0],
        narration_path=tmp_run_dir / "n.mp3",
        music_path=tmp_run_dir / "m.mp3",
        out_path=out,
        burn_caption_ass=None,
    )
    assert called["n"] == 0
