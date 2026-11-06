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


def test_beat_flash_is_an_eased_envelope_not_a_rectangular_strobe():
    # P1: the beat-flash SWELLS and DECAYS with an exponential envelope instead
    # of the old rectangular `enable='lt(mod(...),window)'` gate. khaleeji has
    # beat_flash but no rgb_glitch, so it isolates the flash (no other filter
    # contributes an lt/mod gate).
    fg = sa.build_filtergraph(template=visual_template_for("khaleeji"),
                              beats={"beat_times": [0.5, 1.0], "tempo_bpm": 120},
                              has_overlay=False, size=(1080, 1920))
    assert "exp(-mod(t-0.500" in fg   # eased decay from each beat drives the flash
    assert "eval=frame" in fg          # re-evaluated per frame (continuous)
    assert "lt(mod(" not in fg         # no rectangular on/off gate anywhere here
    assert "between(t," not in fg


def test_beat_filtergraph_does_not_grow_with_beat_count():
    """Regression: a real ~2.5-min song has hundreds of beats. Enumerating one
    `between(t,...)` term per beat built a -filter_complex so large that prod
    ffmpeg failed at parse with 'Cannot allocate memory' and the animated render
    silently fell back to a static cover. Every beat-synced expression stays a
    single periodic/envelope term, so the filtergraph is IDENTICAL whether the
    song has 4 beats or 399 (same tempo) -- the strongest statement of the
    'does not grow with beat count' invariant."""
    tpl = visual_template_for("arabic_trap")
    few = sa.build_filtergraph(template=tpl, size=(1080, 1920), has_overlay=False,
                               beats={"beat_times": [0.5, 1.0], "tempo_bpm": 120})
    many = sa.build_filtergraph(template=tpl, size=(1080, 1920), has_overlay=False,
                                beats={"beat_times": [0.5 * n for n in range(1, 400)],
                                       "tempo_bpm": 120})
    assert many == few                 # byte-identical regardless of beat count
    assert "between(t," not in many    # no per-beat enumeration
    assert len(many) < 3000            # bounded


def test_beat_env_expr_is_an_eased_decay_not_a_rectangular_gate():
    # P1: the beat envelope SWELLS and DECAYS (reads musical) instead of the
    # old rectangular on/off `lt(mod(...),window)` gate (reads as a strobe).
    expr = sa._beat_env_expr({"beat_times": [0.5, 1.0], "tempo_bpm": 120}, decay=0.1)
    assert expr is not None
    assert "exp(-mod(t-0.500" in expr   # exponential decay from each beat
    assert "lt(mod(" not in expr         # not a rectangular gate
    assert ",0.5000)" in expr            # period = 60/120 = 0.5s


def test_beat_env_expr_supports_a_custom_time_variable_for_zoompan():
    # zoompan evaluates the output-frame index `on`, not `t`; the helper must
    # emit the pulse in terms of a caller-supplied time expression so the same
    # envelope drives both eq (t) and zoompan (on/fps).
    expr = sa._beat_env_expr({"beat_times": [0.5], "tempo_bpm": 120},
                             tvar="(on/30)", decay=0.1)
    assert expr is not None
    assert "mod((on/30)-0.500" in expr


def test_beat_env_expr_is_none_without_beats():
    assert sa._beat_env_expr({"beat_times": []}, decay=0.1) is None


def test_grade_neon_bloom_is_damped_not_full_strength():
    # Regression: grade_neon's FULL-strength screen-blend bloom (+1.4/1.5
    # saturation) blew bright frames into garish, washed-out magenta (a real
    # render of a sunset still was unusable). The bloom must be PARTIAL
    # (all_opacity < 1) so it adds a neon glow without blowing highlights.
    fg = sa.build_filtergraph(template=visual_template_for("arabic_trap"),
                              beats={"beat_times": [0.5]}, has_overlay=False,
                              size=(1080, 1920))
    assert "blend=all_mode=screen:all_opacity=" in fg   # bloom is damped, not full


def test_camera_is_beat_synced_center_anchored_and_bounded_for_every_genre():
    # P1: the camera is ALWAYS on (not gated on a push_in token) and PUNCHES on
    # the beat via the on-based envelope, center-anchored and bounded. Even trap
    # (which has no push_in token) now gets a living, beat-reactive camera.
    fg = sa.build_filtergraph(template=visual_template_for("arabic_trap"),
                              beats={"beat_times": [0.5, 1.0], "tempo_bpm": 120},
                              has_overlay=False, size=(1080, 1920))
    assert "zoompan" in fg
    assert "exp(-mod((on/30)-0.500" in fg   # beat punch via the frame-indexed envelope
    assert "iw/2-(iw/zoom/2)" in fg          # center-anchored zoom (not top-left)
    assert "min(" in fg                       # bounded -> no runaway zoom


def test_camera_drifts_gently_without_beats_and_adds_no_punch():
    # arabic_ballad has no beat_flash, so with an empty beat grid NOTHING emits
    # an exp envelope -- the camera is a pure gentle drift.
    fg = sa.build_filtergraph(template=visual_template_for("arabic_ballad"),
                              beats={"beat_times": []},
                              has_overlay=False, size=(1080, 1920))
    assert "zoompan" in fg          # still a continuous drift (push-in)
    assert "exp(-mod(" not in fg    # but no beat punch when there are no beats


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
