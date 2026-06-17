from __future__ import annotations

import json
from pathlib import Path

import pipeline.song_beats as song_beats


def test_detect_beats_writes_json_and_parses(tmp_path, monkeypatch):
    def fake_track(path):
        return 123.4, [0.0, 0.5, 1.0, 1.5]
    monkeypatch.setattr(song_beats, "_librosa_beat_track", fake_track)
    out = tmp_path / "beats.json"
    result = song_beats.detect_beats(tmp_path / "song.mp3", out_json=out)
    assert result["tempo_bpm"] == 123.4
    assert result["beat_times"] == [0.0, 0.5, 1.0, 1.5]
    assert result["source"] == "librosa"
    assert json.loads(out.read_text()) == result


def test_detect_beats_idempotent(tmp_path, monkeypatch):
    out = tmp_path / "beats.json"
    out.write_text(json.dumps({"tempo_bpm": 90.0, "beat_times": [0.0], "source": "cached"}))
    def boom(path):
        raise AssertionError("should not be called when beats.json exists")
    monkeypatch.setattr(song_beats, "_librosa_beat_track", boom)
    result = song_beats.detect_beats(tmp_path / "song.mp3", out_json=out)
    assert result["source"] == "cached"


def test_detect_beats_fallback_on_error(tmp_path, monkeypatch):
    def boom(path):
        raise RuntimeError("librosa exploded")
    monkeypatch.setattr(song_beats, "_librosa_beat_track", boom)
    monkeypatch.setattr(song_beats, "_audio_duration_s", lambda p: 10.0)
    out = tmp_path / "beats.json"
    result = song_beats.detect_beats(tmp_path / "song.mp3", out_json=out,
                                     fallback_bpm=120.0)
    assert result["source"] == "fallback"
    assert result["tempo_bpm"] == 120.0
    # 120 BPM over 10s = 2 beats/s -> ~20 beats
    assert len(result["beat_times"]) == 20
    assert result["beat_times"][0] == 0.0


def test_detect_beats_fallback_on_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(song_beats, "_librosa_beat_track", lambda p: (0.0, []))
    monkeypatch.setattr(song_beats, "_audio_duration_s", lambda p: 4.0)
    out = tmp_path / "beats.json"
    result = song_beats.detect_beats(tmp_path / "song.mp3", out_json=out)
    assert result["source"] == "fallback"


def test_to_bpm_handles_array_and_scalar():
    import numpy as np
    from pipeline.song_beats import _to_bpm
    assert _to_bpm(np.array([161.5])) == 161.5   # librosa 0.10+ shape
    assert _to_bpm(np.float64(120.0)) == 120.0    # numpy scalar
    assert _to_bpm(95.0) == 95.0                   # plain float
