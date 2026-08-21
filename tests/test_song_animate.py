from __future__ import annotations

from pathlib import Path

import pytest

import pipeline.song_animate as sa
from pipeline.song_visual_style import visual_template_for


def test_filtergraph_uses_asplit_when_a_label_is_reused():
    fg = sa.build_filtergraph(template=visual_template_for("arabic_trap"),
                              beats={"beat_times": [0.5, 1.0, 1.5]},
                              has_overlay=True, size=(1080, 1920))
    assert "asplit" in fg or "split" in fg  # no label consumed twice un-split
    assert "ass=" in fg                      # lyrics burned last


def test_beat_flash_enable_exprs_come_from_beat_times():
    fg = sa.build_filtergraph(template=visual_template_for("arabic_trap"),
                              beats={"beat_times": [0.5, 1.0]},
                              has_overlay=False, size=(1080, 1920))
    assert "between(t,0.5" in fg and "between(t,1.0" in fg


def test_build_animated_video_invokes_ffmpeg_and_writes_output(monkeypatch, tmp_path):
    calls = {}
    def fake_run(cmd, **kw):
        calls["cmd"] = cmd
        Path(cmd[-1]).write_bytes(b"mp4")  # emulate ffmpeg writing the temp out
        class R: returncode = 0; stderr = b""
        return R()
    monkeypatch.setattr(sa.subprocess, "run", fake_run)
    monkeypatch.setattr(sa, "overlay_clips_for", lambda k: [])
    out = tmp_path / "final.mp4"
    cover = tmp_path / "cover.png"; cover.write_bytes(b"png")
    song = tmp_path / "song.mp3"; song.write_bytes(b"mp3")
    ass = tmp_path / "k.ass"; ass.write_text("[Script Info]\n")
    res = sa.build_animated_video(backdrop=cover, song_mp3=song, ass_path=ass,
                                  beats={"beat_times": [0.5]},
                                  template=visual_template_for("arabic_trap"),
                                  out_path=out)
    assert res == out and out.exists()


# --- Fontsdir handoff (Task 3 -> Task 5): "Amiri" is bundled at
# assets/fonts, not system-installed, so libass needs fontsdir= or the
# Fontname in the burned ASS never resolves. ---

def test_ass_filter_passes_fontsdir_pointing_at_assets_fonts():
    fg = sa.build_filtergraph(template=visual_template_for("arabic_ballad"),
                              beats={"beat_times": []},
                              has_overlay=False, size=(1080, 1920))
    assert "ass=" in fg
    assert "fontsdir=" in fg
    # Points at the repo's bundled assets/fonts dir, not some placeholder.
    assert "assets" in fg and "fonts" in fg


# --- Overlay alpha-decoder handoff (Task 4 -> Task 5, CRITICAL): ffmpeg's
# default vp9 decoder silently drops WebM alpha; -c:v libvpx-vp9 must be an
# INPUT option immediately before -i <overlay>, or the overlay composites as
# an opaque rectangle. ---

def test_overlay_input_forces_libvpx_vp9_decoder_immediately_before_dash_i(
    monkeypatch, tmp_path
):
    def fake_run(cmd, **kw):
        Path(cmd[-1]).write_bytes(b"mp4")
        class R: returncode = 0; stderr = b""
        return R()
    monkeypatch.setattr(sa.subprocess, "run", fake_run)
    overlay = tmp_path / "particles.webm"; overlay.write_bytes(b"webm")
    monkeypatch.setattr(sa, "overlay_clips_for", lambda k: [overlay])

    captured = {}
    real_run = sa._run
    def spy_run(cmd):
        captured["cmd"] = cmd
        return real_run(cmd)
    monkeypatch.setattr(sa, "_run", spy_run)

    out = tmp_path / "final.mp4"
    cover = tmp_path / "cover.png"; cover.write_bytes(b"png")
    song = tmp_path / "song.mp3"; song.write_bytes(b"mp3")
    ass = tmp_path / "k.ass"; ass.write_text("[Script Info]\n")
    sa.build_animated_video(backdrop=cover, song_mp3=song, ass_path=ass,
                            beats={"beat_times": [0.5]},
                            template=visual_template_for("arabic_trap"),
                            out_path=out)

    cmd = captured["cmd"]
    # The overlay's own -i is found by locating the overlay path and
    # walking back to the preceding -i flag.
    ov_i_idx = cmd.index(str(overlay)) - 1
    assert cmd[ov_i_idx] == "-i"
    assert cmd[ov_i_idx - 2:ov_i_idx] == ["-c:v", "libvpx-vp9"]


def test_no_overlay_does_not_force_libvpx_vp9_on_cover_input(monkeypatch, tmp_path):
    def fake_run(cmd, **kw):
        Path(cmd[-1]).write_bytes(b"mp4")
        class R: returncode = 0; stderr = b""
        return R()
    monkeypatch.setattr(sa.subprocess, "run", fake_run)
    monkeypatch.setattr(sa, "overlay_clips_for", lambda k: [])

    captured = {}
    real_run = sa._run
    def spy_run(cmd):
        captured["cmd"] = cmd
        return real_run(cmd)
    monkeypatch.setattr(sa, "_run", spy_run)

    out = tmp_path / "final.mp4"
    cover = tmp_path / "cover.png"; cover.write_bytes(b"png")
    song = tmp_path / "song.mp3"; song.write_bytes(b"mp3")
    ass = tmp_path / "k.ass"; ass.write_text("[Script Info]\n")
    sa.build_animated_video(backdrop=cover, song_mp3=song, ass_path=ass,
                            beats={"beat_times": [0.5]},
                            template=visual_template_for("arabic_trap"),
                            out_path=out)

    cmd = captured["cmd"]
    assert "libvpx-vp9" not in cmd
    cover_i_idx = cmd.index(str(cover)) - 1
    assert cmd[cover_i_idx] == "-i"
    assert cmd[cover_i_idx - 2:cover_i_idx] != ["-c:v", "libvpx-vp9"]


# --- faststart-off-Fuse: the ffmpeg call that does +faststart must write to
# a LOCAL temp dir, never directly at out_path's own directory (which may be
# a gcsfuse mount where the backward seek for the moov-atom rewrite fails).

def test_ffmpeg_render_target_is_a_different_directory_than_out_path(
    monkeypatch, tmp_path
):
    captured = {}
    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        Path(cmd[-1]).write_bytes(b"mp4")
        class R: returncode = 0; stderr = b""
        return R()
    monkeypatch.setattr(sa.subprocess, "run", fake_run)
    monkeypatch.setattr(sa, "overlay_clips_for", lambda k: [])

    out_dir = tmp_path / "out_mount"
    out_dir.mkdir()
    out = out_dir / "final.mp4"
    cover = tmp_path / "cover.png"; cover.write_bytes(b"png")
    song = tmp_path / "song.mp3"; song.write_bytes(b"mp3")
    ass = tmp_path / "k.ass"; ass.write_text("[Script Info]\n")
    res = sa.build_animated_video(backdrop=cover, song_mp3=song, ass_path=ass,
                                  beats={"beat_times": [0.5]},
                                  template=visual_template_for("arabic_trap"),
                                  out_path=out)

    render_target = Path(captured["cmd"][-1])
    assert render_target.parent != out.parent
    assert "+faststart" in captured["cmd"]
    assert "-shortest" in captured["cmd"]
    assert res == out and out.exists()
    assert out.read_bytes() == b"mp4"


# --- Resumable: existing out_path short-circuits before any ffmpeg call.

def test_resumable_skips_render_when_out_path_already_exists(monkeypatch, tmp_path):
    def boom(cmd, **kw):
        raise AssertionError("ffmpeg should not run when out_path already exists")
    monkeypatch.setattr(sa.subprocess, "run", boom)

    out = tmp_path / "final.mp4"
    out.write_bytes(b"already-there")
    cover = tmp_path / "cover.png"; cover.write_bytes(b"png")
    song = tmp_path / "song.mp3"; song.write_bytes(b"mp3")
    ass = tmp_path / "k.ass"; ass.write_text("[Script Info]\n")
    res = sa.build_animated_video(backdrop=cover, song_mp3=song, ass_path=ass,
                                  beats={"beat_times": [0.5]},
                                  template=visual_template_for("arabic_trap"),
                                  out_path=out)
    assert res == out
    assert out.read_bytes() == b"already-there"


# --- Multi-still ("cinematic") backdrop: beat-cut concat, not just
# backdrop[0] -- the interface declares `backdrop: Path | list[Path]` and
# the design spec calls for reusing the beat-cut schedule for stills.

def test_still_list_backdrop_renders_beat_cut_concat_then_composites(
    monkeypatch, tmp_path
):
    seen_cmds = []
    def fake_run(cmd, **kw):
        seen_cmds.append(cmd)
        Path(cmd[-1]).write_bytes(b"mp4")
        class R: returncode = 0; stderr = b""
        return R()
    monkeypatch.setattr(sa.subprocess, "run", fake_run)
    monkeypatch.setattr(sa, "overlay_clips_for", lambda k: [])

    stills = []
    for i in range(3):
        p = tmp_path / f"still_{i}.png"
        p.write_bytes(b"png")
        stills.append(p)
    out = tmp_path / "final.mp4"
    song = tmp_path / "song.mp3"; song.write_bytes(b"mp3")
    ass = tmp_path / "k.ass"; ass.write_text("[Script Info]\n")

    # Dense beat grid (48 beats, 0.5s apart, up to 24.0s) so
    # build_cut_schedule's default bars_per_cut=4/beats_per_bar=4 (cut every
    # 16 beats) actually yields 3 segments -- one per still in the pool.
    # The original 8-beat grid here collapsed to a single segment after
    # _merge_short, which meant the round-robin fix below was never
    # exercised (stills[1]/stills[2] would "pass" even if dead code).
    beat_times = [0.5 * n for n in range(1, 49)]

    res = sa.build_animated_video(
        backdrop=stills, song_mp3=song, ass_path=ass,
        beats={"beat_times": beat_times},
        template=visual_template_for("arabic_trap"), out_path=out,
    )

    assert res == out and out.exists()
    # A concat-demuxer pass ran (hard cuts, not xfade -- see module docstring).
    assert any("concat" in c for cmd in seen_cmds for c in cmd)
    # The final compositor call loops the concatenated backdrop rather than
    # -loop 1'ing a single still.
    final_cmd = seen_cmds[-1]
    assert "-stream_loop" in final_cmd
    assert str(stills[0]) not in final_cmd  # not fed directly as input 0

    # The beat-cut schedule must actually ROTATE through the still pool --
    # every still in a multi-still backdrop should be fed to some ffmpeg
    # call as an -i input, not just stills[0]. (Regression check for the
    # song_scenes.build_cut_schedule(sections=[]) bug where every segment's
    # image_idx was 0, so stills[1:] were never rendered at all.)
    for still in stills:
        assert any(str(still) in cmd for cmd in seen_cmds), (
            f"{still} was never used as an ffmpeg input -- backdrop pool "
            "did not rotate"
        )


def test_empty_still_list_backdrop_raises_value_error(monkeypatch, tmp_path):
    monkeypatch.setattr(sa, "overlay_clips_for", lambda k: [])

    def boom(cmd, **kw):
        raise AssertionError("ffmpeg should not run for an empty backdrop list")
    monkeypatch.setattr(sa.subprocess, "run", boom)

    out = tmp_path / "final.mp4"
    song = tmp_path / "song.mp3"; song.write_bytes(b"mp3")
    ass = tmp_path / "k.ass"; ass.write_text("[Script Info]\n")

    with pytest.raises(ValueError):
        sa.build_animated_video(
            backdrop=[], song_mp3=song, ass_path=ass,
            beats={"beat_times": [0.5]},
            template=visual_template_for("arabic_trap"), out_path=out,
        )
