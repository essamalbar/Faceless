from __future__ import annotations

from pipeline.artists import (
    ARTIST_HANDLE_RE,
    find_by_handle,
    find_by_id,
    load_artists,
    new_artist,
    save_artists,
    slugify_handle,
    unique_handle,
)


def test_slugify_latin_name():
    assert slugify_handle("Cool Artist!", "abc123") == "cool-artist"


def test_slugify_arabic_falls_back_to_artist_id():
    # Arabic-only names slug to empty → deterministic fallback keeps the
    # public URL working.
    assert slugify_handle("ليل", "abc123") == "artist-abc123"


def test_slugify_respects_handle_regex():
    for name in ("Cool Artist!", "ليل", "x" * 100, "--A--"):
        s = slugify_handle(name, "abcd1234")
        assert ARTIST_HANDLE_RE.match(s), s


def test_unique_handle_suffixes_on_collision():
    assert unique_handle("layl", set()) == "layl"
    assert unique_handle("layl", {"layl"}) == "layl-2"
    assert unique_handle("layl", {"layl", "layl-2"}) == "layl-3"


def test_new_artist_fills_id_and_created_at():
    a = new_artist(name="ليل", handle="layl")
    assert a["id"].startswith("art_") and len(a["id"]) == 12
    assert a["created_at"]
    assert a["persona_id"] is None
    assert a["default_language"] == "ar"


def test_save_load_round_trip(tmp_path):
    a = new_artist(name="ليل", handle="layl", default_style="arabic pop")
    save_artists(tmp_path, [a])
    loaded = load_artists(tmp_path)
    assert loaded == [a]


def test_load_missing_or_corrupt_returns_empty(tmp_path):
    assert load_artists(tmp_path) == []
    (tmp_path / "artists.json").write_text("{not json", encoding="utf-8")
    assert load_artists(tmp_path) == []


def test_find_helpers():
    a = new_artist(name="A", handle="aa")
    b = new_artist(name="B", handle="bb")
    assert find_by_id([a, b], b["id"]) == b
    assert find_by_handle([a, b], "aa") == a
    assert find_by_id([a, b], "nope") is None
