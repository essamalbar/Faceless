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


def test_filter_graph_concats_shots():
    """Previously this was an xfade chain (one fade transition per
    shot boundary), but xfade routinely failed at assembly time with
    "Failed to configure output pad" on perfectly-valid inputs. Now
    we just concat — same number of inputs flow into one concat
    node and out as [vcat]."""
    graph = build_filter_graph(
        shots=_shots([5000, 4000, 3000]),
        output_w=1920, output_h=1080, crossfade_ms=800,
        burn_caption_ass=None,
    )
    # 3 shots → exactly one concat=n=3 node, no xfades
    assert graph.count("concat=n=3:v=1:a=0") == 1
    assert "xfade" not in graph


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


def test_assemble_regenerates_when_output_is_zero_bytes(monkeypatch, tmp_run_dir: Path):
    """Regression for Run A: a 0-byte final.mp4 left by a previous crashed
    assembly used to satisfy `out.exists()` and short-circuit the rerun.
    `is_complete_artifact` now requires non-zero size — the stage must
    actually invoke ffmpeg this time."""
    called = {"n": 0}
    monkeypatch.setattr("pipeline.assemble._run_ffmpeg", lambda args: called.update(n=called["n"] + 1))
    out = tmp_run_dir / "final.mp4"
    out.touch()  # zero bytes
    assert out.exists() and out.stat().st_size == 0
    assemble_video(
        shots=_shots([5000]), images_dir=tmp_run_dir, narration_path=tmp_run_dir / "n.mp3",
        music_path=tmp_run_dir / "m.mp3", out_path=out, burn_caption_ass=None,
        output_width=1920, output_height=1080, crossfade_ms=800,
        music_duck_db=-18, music_silence_db=-8, fade_in_s=3, fade_out_s=3,
    )
    assert called["n"] == 1, "ffmpeg must run when prior output is 0 bytes"


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
    # 4 clips → one concat=n=4 node (was 3 xfades; xfade was replaced
    # with concat because it crashed on real Veo outputs with the
    # opaque "Failed to configure output pad" error)
    assert g.count("concat=n=4:v=1:a=0") == 1
    assert "xfade" not in g


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


def test_shorts_filter_graph_pads_last_frame_when_narration_longer():
    """When narration runs past the video, hold the last frame so -shortest
    trims to narration length instead of cutting the audio off early."""
    from pipeline.assemble import build_shorts_filter_graph
    # 4 clips × 8s = 32s of video (concat, no xfade overlap),
    # narration = 60s, so the tail-pad gap should be 28.0s
    g = build_shorts_filter_graph(
        clip_durations_s=[8.0, 8.0, 8.0, 8.0],
        output_w=1080, output_h=1920, crossfade_ms=350,
        burn_caption_ass=None,
        narration_duration_s=60.0,
    )
    assert "tpad=stop_mode=clone" in g
    assert "stop_duration=28.0" in g


def test_shorts_filter_graph_native_audio_uses_clip_audio_only():
    """Tier-4 path: no narration mp3 is supplied; clip audio (Veo's lip-synced
    dialogue) is the primary track, mixed only with ducked music."""
    from pipeline.assemble import build_shorts_filter_graph
    g = build_shorts_filter_graph(
        clip_durations_s=[8.0, 8.0, 8.0, 8.0],
        output_w=1080, output_h=1920, crossfade_ms=350,
        burn_caption_ass=None,
        native_audio=True,
    )
    # Clip audio concatenated into a [voice_raw] track and asplit-fanned-out
    # so both the sidechain input AND the amix input get the full concat.
    # Without asplit, ffmpeg would silently drop the second reference and the
    # output would truncate to the first clip's duration.
    assert "[voice_raw]" in g
    assert "asplit=2[voice_a][voice_b]" in g
    # Music mixed against the voice via sidechain compress
    assert "sidechaincompress" in g
    # No three-input mix — only voice + ducked music
    assert "amix=inputs=2" in g
    assert "amix=inputs=3" not in g
    # Music is at index N=4 (no narration input shifts the indices down)
    assert "[4:a]aloop" in g
    # Legacy ambient track is not used in native-audio mode
    assert "[ambient]" not in g


def test_assemble_shorts_native_audio_omits_narration_input(monkeypatch, tmp_run_dir: Path):
    """When narration_path is None, the ffmpeg command line includes only
    clip inputs and music — no extra -i for a narration mp3."""
    from pipeline.assemble import assemble_shorts_video
    captured: dict = {}
    monkeypatch.setattr("pipeline.assemble._run_ffmpeg",
                        lambda args: captured.update(args=args))

    clips_dir = tmp_run_dir / "clips"
    clips_dir.mkdir()
    clip_paths = []
    for i in range(1, 4):
        p = clips_dir / f"{i:02d}.mp4"
        p.write_bytes(b"x")
        clip_paths.append(p)
    music = tmp_run_dir / "music.mp3"; music.write_bytes(b"x")

    assemble_shorts_video(
        clip_paths=clip_paths,
        clip_durations_s=[8.0, 8.0, 8.0],
        narration_path=None,           # native-audio mode
        music_path=music,
        out_path=tmp_run_dir / "final.mp4",
        burn_caption_ass=None,
    )
    args = captured["args"]
    # 3 clip inputs + 1 music = 4 -i flags total. With a narration mp3 it'd be 5.
    assert args.count("-i") == 4
    assert str(music) in args


def test_shorts_filter_graph_no_pad_when_video_longer():
    """When the video already covers the audio, no padding is added."""
    from pipeline.assemble import build_shorts_filter_graph
    g = build_shorts_filter_graph(
        clip_durations_s=[8.0, 8.0, 8.0, 8.0],
        output_w=1080, output_h=1920, crossfade_ms=350,
        burn_caption_ass=None,
        narration_duration_s=20.0,
    )
    assert "tpad=" not in g


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
