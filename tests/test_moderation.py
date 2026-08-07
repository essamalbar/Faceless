"""Deny-list content moderation (inputs-only). See
docs/superpowers/specs/2026-08-07-tier3-fastfollow-design.md § M.

The seed deny-list is a small, conservative set; these tests exercise the
matching semantics (word-boundary, case-insensitive), the operator file
override, and the assert_clean gate — without enumerating the seed terms."""
from __future__ import annotations

import pytest

from pipeline import moderation
from pipeline.moderation import (
    DENYLIST,
    ModerationError,
    assert_clean,
    find_violations,
)


def _seed_term() -> str:
    """A representative, deterministic term from the seed deny-list."""
    return sorted(DENYLIST)[0]


def test_seed_denylist_is_nonempty_frozenset():
    assert isinstance(DENYLIST, frozenset)
    assert len(DENYLIST) >= 1
    assert all(isinstance(t, str) and t for t in DENYLIST)


def test_find_violations_matches_seeded_term_standalone(monkeypatch):
    # The clean-env pytest command does not unset this var; a stray operator
    # export must not change what the seed loader returns for this test.
    monkeypatch.delenv("FACELESS_MODERATION_DENYLIST", raising=False)
    term = _seed_term()
    hits = find_violations(f"a story about {term} in the woods")
    assert term in hits


def test_find_violations_word_boundary_no_substring_match(monkeypatch):
    monkeypatch.setattr(moderation, "_load_denylist",
                        lambda: frozenset({"grape"}))
    # "grape" is a substring of "grapefruit" but not a standalone word.
    assert find_violations("fresh grapefruit juice") == []
    assert find_violations("I ate a grape today") == ["grape"]


def test_find_violations_case_insensitive(monkeypatch):
    monkeypatch.setattr(moderation, "_load_denylist",
                        lambda: frozenset({"grape"}))
    assert find_violations("GRAPE soda") == ["grape"]
    assert find_violations("GrApE") == ["grape"]


def test_find_violations_clean_text_returns_empty(monkeypatch):
    monkeypatch.delenv("FACELESS_MODERATION_DENYLIST", raising=False)
    assert find_violations("a perfectly innocent bedtime story") == []


def test_find_violations_empty_and_none():
    assert find_violations("") == []
    assert find_violations(None) == []


def test_env_file_unions_extra_terms(monkeypatch, tmp_path):
    extra = tmp_path / "extra-denylist.txt"
    extra.write_text("bannedbeta\nbannedgamma\n\n# a comment line\n",
                     encoding="utf-8")
    monkeypatch.setenv("FACELESS_MODERATION_DENYLIST", str(extra))

    # File terms are matched...
    assert "bannedbeta" in find_violations("this has bannedbeta in it")
    assert "bannedgamma" in find_violations("and bannedgamma too")
    # ...unioned with the seed (seed term still trips).
    term = _seed_term()
    assert term in find_violations(term)


def test_env_file_missing_path_is_ignored(monkeypatch, tmp_path):
    monkeypatch.setenv("FACELESS_MODERATION_DENYLIST",
                       str(tmp_path / "does-not-exist.txt"))
    # A bad override path must not crash — falls back to the seed alone.
    assert find_violations("a perfectly innocent bedtime story") == []
    assert _seed_term() in find_violations(_seed_term())


def test_assert_clean_raises_moderation_error_on_hit(monkeypatch):
    monkeypatch.setattr(moderation, "_load_denylist",
                        lambda: frozenset({"grape"}))
    with pytest.raises(ModerationError) as ei:
        assert_clean("a grape appears here")
    assert "grape" in ei.value.terms


def test_assert_clean_passes_clean_text(monkeypatch):
    monkeypatch.delenv("FACELESS_MODERATION_DENYLIST", raising=False)
    assert assert_clean("totally fine text") is None


def test_assert_clean_skips_none_and_empty(monkeypatch):
    monkeypatch.delenv("FACELESS_MODERATION_DENYLIST", raising=False)
    assert assert_clean(None) is None
    assert assert_clean("") is None
    assert assert_clean("", None, "also fine") is None


def test_assert_clean_aggregates_across_texts(monkeypatch):
    monkeypatch.setattr(moderation, "_load_denylist",
                        lambda: frozenset({"grape", "melon"}))
    with pytest.raises(ModerationError) as ei:
        assert_clean("a grape", None, "a melon")
    assert set(ei.value.terms) == {"grape", "melon"}
