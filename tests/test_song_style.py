from __future__ import annotations

from pipeline.song_style import (
    GENRE_RECIPES,
    SHARED_NEGATIVES,
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


def test_recipe_style_keeps_vocal_spine_and_hint():
    # The vocal-realism spine and a user style_hint are the two things most
    # load-bearing for "not AI" — they must survive the 450-char trim.
    style, _ = _recipe_style(GENRE_RECIPES["arabic_pop"], "f",
                             style_hint="nostalgic 90s Lebanese warmth")
    assert "natural breath and vibrato" in style          # SPINE_VOCAL survived
    assert "nostalgic 90s Lebanese warmth" in style        # user hint survived
    assert len(style) <= 450


def test_recipe_style_all_genres_fit_with_full_spine():
    # Every recipe must fit genre + vocal + both spine blocks within budget
    # (no genre may silently lose its vocal-realism spine).
    for key, recipe in GENRE_RECIPES.items():
        style, _ = _recipe_style(recipe, "m")
        assert "natural breath and vibrato" in style, key
        assert "mixed and mastered" in style, key
        assert len(style) <= 450, key


def test_infer_genre_word_boundary_no_false_positives():
    # short LATIN aliases must not match inside unrelated words
    assert infer_genre("a song about abundance and hope",
                       language="en") != "edm_electropop"   # not "dance" in "abundance"
    assert infer_genre("my husband and me", language="en") != "rock"  # not "band"


def test_infer_genre_matches_inflected_arabic_aliases():
    # Arabic inflects by attaching suffixes/prefixes directly, so alias
    # matching must still catch inflected forms (خليجية ⊃ خليجي, الطرب ⊃ طرب).
    assert infer_genre("أغنية خليجية أصيلة", language="ar") == "khaleeji"
    assert infer_genre("أحب الطرب الأصيل", language="ar") == "tarab_classic"


def test_recipe_remove_negatives_are_valid_tokens():
    shared = {p.strip() for p in SHARED_NEGATIVES.split(",")}
    for recipe in GENRE_RECIPES.values():
        assert set(recipe.remove_negatives) <= shared, recipe.key


import json

from pipeline.song_style import StyleResult, compose_style


class _StubLLM:
    def __init__(self, response=None, raises=False):
        self._response = response
        self._raises = raises

    def complete(self, prompt, system=None):
        if self._raises:
            raise RuntimeError("llm down")
        return self._response


_GOOD_PRODUCER_JSON = json.dumps({
    "style_prompt": ("Arabic pop ballad, cinematic strings and soft piano, "
                     "warm male vocal, professionally mixed and mastered"),
    "negative_tags": "robotic vocal, off-key",
})


def _compose(llm, theme="أغنية حزينة عن الفراق", genre_hint=None):
    # "حزينة" contains the arabic_ballad alias "حزين" (Arabic substring match)
    # → infer_genre returns "arabic_ballad", which the fallback tests assert.
    return compose_style(
        llm, theme=theme, title="عنوان", lyrics="[Verse 1]\nكلمات\n[Chorus]\nلازمة",
        language="ar", dialect=None, style_hint=genre_hint, vocal_gender="m",
    )


def test_compose_style_uses_producer_when_valid():
    res = _compose(_StubLLM(_GOOD_PRODUCER_JSON))
    assert isinstance(res, StyleResult)
    assert res.source.startswith("producer:")
    assert "mixed and mastered" in res.style_prompt
    assert res.negative_tags == "robotic vocal, off-key"


def test_compose_style_falls_back_on_exception():
    res = _compose(_StubLLM(raises=True))
    assert res.source == "fallback:recipe"
    assert "mixed and mastered" in res.style_prompt  # recipe spine present
    assert res.genre_key == "arabic_ballad"


def test_compose_style_falls_back_on_weak_output():
    weak = json.dumps({"style_prompt": "pop song", "negative_tags": ""})
    res = _compose(_StubLLM(weak))
    assert res.source == "fallback:recipe"


def test_compose_style_rejects_leaked_section_tags():
    leaked = json.dumps({
        "style_prompt": ("Arabic pop ballad, cinematic strings, professionally "
                         "mixed and mastered [Chorus]"),
        "negative_tags": "",
    })
    res = _compose(_StubLLM(leaked))
    assert res.source == "fallback:recipe"


def test_compose_style_trims_overlong_producer_output():
    huge = json.dumps({
        "style_prompt": ("professionally mixed and mastered, Arabic pop ballad, "
                         "cinematic strings, ") + ", ".join(["extra tag"] * 200),
        "negative_tags": "",
    })
    res = _compose(_StubLLM(huge))
    assert len(res.style_prompt) <= 450


def test_compose_style_falls_back_on_non_json_text():
    # LLM returned prose, not JSON → JSONDecodeError → fallback, no crash.
    res = _compose(_StubLLM("here is your style: pop, upbeat, fun"))
    assert res.source == "fallback:recipe"


def test_compose_style_falls_back_on_non_object_json():
    # Valid JSON but a list, not an object → ValueError guard → fallback.
    res = _compose(_StubLLM(json.dumps(["pop", "upbeat"])))
    assert res.source == "fallback:recipe"


def test_compose_style_falls_back_on_missing_keys():
    # Object without style_prompt → empty style → weak → fallback.
    res = _compose(_StubLLM(json.dumps({"foo": "bar"})))
    assert res.source == "fallback:recipe"
