from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pipeline.mastering as m


def _cfg(engine="matchering"):
    return SimpleNamespace(song=SimpleNamespace(master_engine=engine))


def test_matchering_used_when_reference_exists(monkeypatch, tmp_path):
    ref = tmp_path / "arabic_pop.wav"; ref.write_bytes(b"x")
    monkeypatch.setattr(m, "_reference_for", lambda g: ref)
    monkeypatch.setattr(m, "_master_matchering", lambda i, o, r: True)
    monkeypatch.setattr(m, "_master_ffmpeg", lambda i, o: (_ for _ in ()).throw(AssertionError("ffmpeg should not run")))
    assert m.master_track(tmp_path / "in.mp3", tmp_path / "out.mp3",
                          genre_key="arabic_pop", cfg=_cfg()) is True


def test_ffmpeg_fallback_when_no_reference(monkeypatch, tmp_path):
    monkeypatch.setattr(m, "_reference_for", lambda g: None)
    called = {}
    monkeypatch.setattr(m, "_master_ffmpeg", lambda i, o: called.setdefault("ff", True) or True)
    assert m.master_track(tmp_path / "in.mp3", tmp_path / "out.mp3",
                          genre_key="rare", cfg=_cfg()) is True
    assert called.get("ff") is True


def test_master_track_never_raises_returns_false(monkeypatch, tmp_path):
    monkeypatch.setattr(m, "_reference_for", lambda g: (_ for _ in ()).throw(RuntimeError("boom")))
    assert m.master_track(tmp_path / "in.mp3", tmp_path / "out.mp3",
                          genre_key="x", cfg=_cfg()) is False


def test_api_engine_falls_back_to_ffmpeg(monkeypatch, tmp_path):
    monkeypatch.setattr(m, "_master_ffmpeg", lambda i, o: True)
    assert m.master_track(tmp_path / "in.mp3", tmp_path / "out.mp3",
                          genre_key="x", cfg=_cfg(engine="api")) is True
