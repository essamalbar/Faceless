"""Music selector tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline.music import select_music_track


def _seed_bundle(bundle_dir: Path):
    bundle_dir.mkdir(parents=True, exist_ok=True)
    (bundle_dir / "drone-01.mp3").write_bytes(b"drone-content")
    (bundle_dir / "dread-01.mp3").write_bytes(b"dread-content")
    tracks = [
        {"filename": "drone-01.mp3", "duration_s": 300, "mood": "drone",
         "license": "CC0", "source_url": "https://x", "attribution": None},
        {"filename": "dread-01.mp3", "duration_s": 280, "mood": "dread",
         "license": "CC0", "source_url": "https://y", "attribution": None},
    ]
    (bundle_dir / "tracks.json").write_text(json.dumps(tracks))


def test_picks_track_matching_mood(tmp_path: Path, tmp_run_dir: Path):
    bundle = tmp_path / "music"
    _seed_bundle(bundle)
    out = tmp_run_dir / "music_track.mp3"
    select_music_track(bundle_dir=bundle, mood="dread", out_path=out, rng_seed=0)
    assert out.read_bytes() == b"dread-content"


def test_skips_if_already_present(tmp_path: Path, tmp_run_dir: Path):
    bundle = tmp_path / "music"
    _seed_bundle(bundle)
    out = tmp_run_dir / "music_track.mp3"
    out.write_bytes(b"prefilled")
    select_music_track(bundle_dir=bundle, mood="dread", out_path=out, rng_seed=0)
    assert out.read_bytes() == b"prefilled"


def test_raises_if_no_track_for_mood(tmp_path: Path, tmp_run_dir: Path):
    bundle = tmp_path / "music"
    _seed_bundle(bundle)
    out = tmp_run_dir / "music_track.mp3"
    with pytest.raises(RuntimeError):
        select_music_track(bundle_dir=bundle, mood="cosmic", out_path=out, rng_seed=0)


def test_raises_if_bundle_missing(tmp_path: Path, tmp_run_dir: Path):
    out = tmp_run_dir / "music_track.mp3"
    with pytest.raises(FileNotFoundError):
        select_music_track(
            bundle_dir=tmp_path / "doesnotexist",
            mood="dread", out_path=out, rng_seed=0,
        )
