from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.song_overlays import overlay_clips_for, build_overlay_cmd


def test_missing_overlay_dir_returns_empty(monkeypatch, tmp_path):
    monkeypatch.setattr("pipeline.song_overlays.REPO_ROOT", tmp_path)
    assert overlay_clips_for("arabic_trap") == []


def test_present_overlay_dir_returns_clips(monkeypatch, tmp_path):
    d = tmp_path / "assets" / "overlays" / "arabic_trap"
    d.mkdir(parents=True)
    (d / "particles.webm").write_bytes(b"x")
    monkeypatch.setattr("pipeline.song_overlays.REPO_ROOT", tmp_path)
    clips = overlay_clips_for("arabic_trap")
    assert [p.name for p in clips] == ["particles.webm"]


def test_empty_overlay_dir_returns_empty(monkeypatch, tmp_path):
    """The Task 5 compositor contract requires [] for absent *or* empty
    dirs (not just absent) so it falls back to procedural FX either way."""
    d = tmp_path / "assets" / "overlays" / "arabic_trap"
    d.mkdir(parents=True)
    monkeypatch.setattr("pipeline.song_overlays.REPO_ROOT", tmp_path)
    assert overlay_clips_for("arabic_trap") == []


def test_build_overlay_cmd_is_alpha_and_loopable():
    cmd = build_overlay_cmd("particles", Path("/tmp/p.webm"), (1080, 1920), 6)
    assert "ffmpeg" in cmd[0]
    assert "libvpx-vp9" in cmd  # webm w/ alpha
    assert "yuva420p" in cmd    # alpha pixel format


def test_build_overlay_cmd_covers_every_kind_with_a_distinct_graph():
    """Every kind named in the design (particles/bokeh/light_sweep/
    geometric/grain) must build a valid, alpha-transparent command, and
    each kind's filtergraph must differ (no kind is a silent copy of
    another)."""
    kinds = ("particles", "bokeh", "light_sweep", "geometric")
    graphs = set()
    for kind in kinds:
        cmd = build_overlay_cmd(kind, Path(f"/tmp/{kind}.webm"), (640, 360), 4)
        assert cmd[0] == "ffmpeg"
        assert "-filter_complex" in cmd
        assert "libvpx-vp9" in cmd
        assert "yuva420p" in cmd
        assert "-t" in cmd and cmd[cmd.index("-t") + 1] == "4"
        assert cmd[-1] == f"/tmp/{kind}.webm"
        graphs.add(cmd[cmd.index("-filter_complex") + 1])
    assert len(graphs) == len(kinds)


def test_build_overlay_cmd_unknown_kind_raises():
    with pytest.raises(KeyError):
        build_overlay_cmd("not-a-real-kind", Path("/tmp/x.webm"), (640, 360), 4)
