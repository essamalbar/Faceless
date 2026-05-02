"""Last-frame extraction tests."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from pipeline import frames as frames_mod
from pipeline.frames import extract_last_frame


def test_extract_last_frame_invokes_ffmpeg_with_correct_args(monkeypatch, tmp_path: Path):
    captured: dict = {}

    def fake_run(args, check, **kw):
        captured["args"] = args
        Path(args[-1]).write_bytes(b"\x89PNG\r\n\x1a\n")  # PNG magic
        return subprocess.CompletedProcess(args, 0)

    # Make ffprobe return 8.0 sec
    monkeypatch.setattr(frames_mod, "_audio_duration_s", lambda p: 8.0)
    monkeypatch.setattr(subprocess, "run", fake_run)

    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"x")
    out = tmp_path / "last_frame.png"
    extract_last_frame(clip, out)
    assert out.exists()
    args = captured["args"]
    assert args[0] == "ffmpeg"
    # Seek to ~7.9s for an 8s clip (just before the end)
    assert any("7.9" in a for a in args) or any("7.95" in a for a in args)
    assert "-frames:v" in args
    assert "1" in args
