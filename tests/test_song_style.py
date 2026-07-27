from __future__ import annotations

from pipeline.song_style import (
    GENRE_RECIPES,
    SPINE_PRODUCTION,
    build_negatives,
    infer_genre,
    _recipe_style,
    _trim_to_last_comma,
)


def test_infer_genre_by_style_hint():
    assert infer_genre("a love song", style_hint="khaleeji pop") == "khaleeji"


def test_infer_genre_keyword_scan_arabic():
    assert infer_genre("a hard trap banger with 808s", language="ar") == "arabic_trap"


def test_infer_genre_dialect_tiebreak():
    # No genre keyword in the theme → dialect bias decides.
    assert infer_genre("song about home", language="ar", dialect="khaleeji") == "khaleeji"


def test_infer_genre_language_gate_excludes_arabic_recipes():
    # "love" is an arabic_ballad alias, but for an English song the Arabic-only
    # recipes are not candidates, so it must fall back to global pop.
    assert infer_genre("a love song", language="en") == "pop"


def test_infer_genre_arabic_language_fallback():
    assert infer_genre("لا يوجد نوع واضح", language="ar") == "arabic_pop"


def test_recipe_style_contains_spine_and_gender_and_length():
    style, neg = _recipe_style(GENRE_RECIPES["arabic_ballad"], "m")
    assert "male vocal" in style
    assert "mixed and mastered" in style
    assert "BPM" in style
    assert len(style) <= 450


def test_recipe_style_female_gender():
    style, _ = _recipe_style(GENRE_RECIPES["arabic_ballad"], "f")
    assert "female vocal" in style


def test_build_negatives_trap_removes_autotune():
    neg = build_negatives(GENRE_RECIPES["arabic_trap"])
    assert "autotune artifacts" not in neg
    assert "robotic vocal" in neg


def test_build_negatives_ballad_keeps_autotune():
    neg = build_negatives(GENRE_RECIPES["arabic_ballad"])
    assert "autotune artifacts" in neg


def test_trim_to_last_comma_lands_on_boundary():
    long = ", ".join(["descriptor number %d" % i for i in range(100)])
    out = _trim_to_last_comma(long, limit=60)
    assert len(out) <= 60
    assert not out.endswith(",")
    # trimmed at a comma boundary → the last kept token is whole
    assert out.split(", ")[-1] in long.split(", ")
