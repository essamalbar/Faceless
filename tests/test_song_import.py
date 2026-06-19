from __future__ import annotations

import pytest

import pipeline.song_import as si
from pipeline.song_import import ImportFetchError, download_audio


def test_download_audio_returns_path(tmp_path, monkeypatch):
    # Fake yt-dlp: pretend it wrote the output file.
    out = tmp_path / "reference.m4a"
    def fake_run(url, out_template):
        out.write_bytes(b"\x00\x00")  # stand-in audio bytes
        return str(out)
    monkeypatch.setattr(si, "_ytdlp_download", fake_run)
    p = download_audio("https://www.youtube.com/watch?v=abc123", tmp_path)
    assert p.exists() and p.name == "reference.m4a"


def test_download_audio_raises_clear_error(tmp_path, monkeypatch):
    def boom(url, out_template):
        raise RuntimeError("Video unavailable")
    monkeypatch.setattr(si, "_ytdlp_download", boom)
    with pytest.raises(ImportFetchError):
        download_audio("https://youtu.be/abc123", tmp_path)
