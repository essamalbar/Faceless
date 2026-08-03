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


def test_matchering_error_falls_back_to_ffmpeg(monkeypatch, tmp_path):
    # A reference exists but matchering raises → must fall back to ffmpeg,
    # not degrade straight to unmastered (spec: ffmpeg when Matchering errors).
    ref = tmp_path / "arabic_pop.wav"; ref.write_bytes(b"x")
    monkeypatch.setattr(m, "_reference_for", lambda g: ref)
    def _raise(i, o, r):
        raise RuntimeError("pcm16 mp3 fail")
    monkeypatch.setattr(m, "_master_matchering", _raise)
    called = {}
    monkeypatch.setattr(m, "_master_ffmpeg",
                        lambda i, o: called.setdefault("ff", True) or True)
    assert m.master_track(tmp_path / "in.mp3", tmp_path / "out.mp3",
                          genre_key="arabic_pop", cfg=_cfg()) is True
    assert called.get("ff") is True


def test_master_matchering_renders_wav_then_transcodes(monkeypatch, tmp_path):
    # matchering must target a WAV (pcm16 rejects mp3), then transcode to mp3.
    import sys
    import types as _t
    calls = {}
    def _pcm16(p):
        calls["pcm16"] = p
        return ("R", p)
    fake_mg = _t.SimpleNamespace(
        pcm16=_pcm16,
        process=lambda target, reference, results: Path(results[0][1]).write_bytes(b"wav"),
    )
    monkeypatch.setitem(sys.modules, "matchering", fake_mg)
    monkeypatch.setattr(m.subprocess, "run",
                        lambda *a, **k: Path(a[0][-1]).write_bytes(b"mp3"))
    out = tmp_path / "out.mp3"
    ok = m._master_matchering(tmp_path / "in.mp3", out, tmp_path / "ref.wav")
    assert ok is True
    assert out.read_bytes() == b"mp3"            # transcoded to the mp3 container
    assert calls["pcm16"].endswith(".wav")        # matchering rendered to WAV, not mp3
