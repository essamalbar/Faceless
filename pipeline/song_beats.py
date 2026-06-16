"""Tempo/beat detection for the cinematic song video.

Wraps librosa's beat tracker. Always succeeds: if librosa raises or
finds no beats, falls back to a fixed-BPM grid over the audio duration
so the cut-schedule builder still has a beat grid to work with.

Idempotent: if beats.json already exists, returns it and skips librosa
(same resumable pattern as the rest of the pipeline).
"""
from __future__ import annotations

import json
from pathlib import Path

from pipeline.align import _audio_duration_s


def _librosa_beat_track(song_mp3: Path) -> tuple[float, list[float]]:
    """Return (tempo_bpm, beat_times_seconds). Isolated so tests can
    monkeypatch it without importing librosa."""
    import librosa  # lazy: heavy import (numba/scipy)
    y, sr = librosa.load(str(song_mp3), mono=True)
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr)
    return float(tempo), [float(t) for t in beat_times]


def _write_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _fixed_grid(song_mp3: Path, bpm: float) -> dict:
    duration = _audio_duration_s(song_mp3)
    step = 60.0 / bpm
    n = max(1, int(duration / step))
    return {
        "tempo_bpm": bpm,
        "beat_times": [round(i * step, 4) for i in range(n)],
        "source": "fallback",
    }


def detect_beats(
    song_mp3: Path,
    *,
    out_json: Path,
    fallback_bpm: float = 120.0,
) -> dict:
    """Detect tempo + beats; write beats.json; return its contents."""
    if out_json.exists():
        return json.loads(out_json.read_text(encoding="utf-8"))

    try:
        tempo, beats = _librosa_beat_track(song_mp3)
        if beats:
            result = {"tempo_bpm": tempo, "beat_times": beats, "source": "librosa"}
        else:
            result = _fixed_grid(song_mp3, fallback_bpm)
    except Exception as e:  # librosa / audio decode failure -- never fail the run
        print(f"[song_beats] detection failed ({e}); using fixed-BPM fallback")
        result = _fixed_grid(song_mp3, fallback_bpm)

    _write_atomic(out_json, result)
    return result
