from __future__ import annotations

import json
import zipfile

import pytest

from pipeline.release import (
    ReleaseNotReady,
    build_release_package,
    derive_genre,
    song_slug,
    strip_section_tags,
    upscale_cover,
)


def test_song_slug_latin_and_arabic():
    assert song_slug("Midnight Dream!") == "midnight-dream"
    assert song_slug("حلم في الليل") == "song"  # cosmetic fallback


def test_strip_section_tags():
    lyrics = "[Verse 1]\nline one\nline two\n\n[Chorus]\nhook\n"
    out = strip_section_tags(lyrics)
    assert "[Verse 1]" not in out and "[Chorus]" not in out
    assert "line one" in out and "hook" in out


def test_derive_genre():
    assert derive_genre("Arabic pop ballad, 88 BPM, oud") == "Arabic pop ballad"
    assert derive_genre("") == "World"


def test_upscale_cover_produces_3000_jpeg(tmp_path):
    from PIL import Image
    src = tmp_path / "cover.png"
    Image.new("RGB", (1080, 1080), (40, 120, 200)).save(src)
    dest = tmp_path / "cover.jpg"
    upscale_cover(src, dest)
    with Image.open(dest) as im:
        assert im.size == (3000, 3000)
        assert im.format == "JPEG"


def _make_run(tmp_path, *, with_cover=True):
    run = tmp_path / "run"
    run.mkdir()
    (run / "song.json").write_text(json.dumps({
        "title": "حلم في الليل",
        "lyrics": "[Verse 1]\nكلمات\n[Chorus]\nلازمة",
        "style_prompt": "Arabic pop, 92 BPM, oud",
        "language": "ar",
    }), encoding="utf-8")
    (run / "song.mp3").write_bytes(b"\x00fake-mp3")
    if with_cover:
        from PIL import Image
        Image.new("RGB", (1080, 1080), (10, 10, 10)).save(run / "cover.png")
    return run


def test_build_release_package_full(tmp_path):
    run = _make_run(tmp_path)
    artist = {"name": "ليل", "handle": "layl"}
    out = build_release_package(run, artist, run / "release.zip")
    with zipfile.ZipFile(out) as z:
        names = set(z.namelist())
        assert names == {"audio.mp3", "cover.jpg", "metadata.json",
                         "metadata.txt", "lyrics.txt", "README.txt"}
        meta = json.loads(z.read("metadata.json"))
        assert meta["artist_name"] == "ليل"
        assert meta["artist_handle"] == "layl"
        assert meta["genre"] == "Arabic pop"
        assert meta["release_type"] == "single"
        assert "[Chorus]" not in z.read("lyrics.txt").decode()


def test_build_release_package_without_artist_defaults(tmp_path):
    run = _make_run(tmp_path)
    out = build_release_package(run, None, run / "release.zip")
    with zipfile.ZipFile(out) as z:
        meta = json.loads(z.read("metadata.json"))
        assert meta["artist_name"] == "Faceless Artist"


def test_build_release_package_degrades_without_cover(tmp_path):
    run = _make_run(tmp_path, with_cover=False)
    out = build_release_package(run, None, run / "release.zip")
    with zipfile.ZipFile(out) as z:
        assert "cover.jpg" not in z.namelist()
        assert "NOTE: cover.jpg" in z.read("README.txt").decode()


def test_build_release_package_missing_audio_raises(tmp_path):
    run = _make_run(tmp_path)
    (run / "song.mp3").unlink()
    with pytest.raises(ReleaseNotReady) as e:
        build_release_package(run, None, run / "release.zip")
    assert "song.mp3" in e.value.missing
