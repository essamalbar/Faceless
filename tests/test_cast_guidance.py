from pipeline.cast_guidance import flux_lineup_override, veo_clip_negation


def test_flux_animal_has_concrete_species_and_negates_fruit():
    s = flux_lineup_override("animal").lower()
    assert "fox" in s and "rabbit" in s
    assert "no lemons" in s
    assert "no blueberries" in s


def test_flux_human_negates_both_fruit_and_animals():
    s = flux_lineup_override("human").lower()
    assert "human" in s
    assert "no lemons" in s
    assert "not animal" in s


def test_flux_fruit_sunstoriz_returns_empty():
    assert flux_lineup_override("fruit_sunstoriz") == ""


def test_flux_ai_choose_returns_empty():
    assert flux_lineup_override("ai_choose") == ""


def test_flux_unknown_or_none_returns_empty():
    assert flux_lineup_override("klingon") == ""
    assert flux_lineup_override(None) == ""
    assert flux_lineup_override("") == ""


def test_veo_animal_has_concrete_species_and_negates_fruit():
    s = veo_clip_negation("animal").lower()
    assert "fox" in s
    assert "blueberries" in s
    assert "strictly not anthropomorphic fruit" in s


def test_veo_human_negates_fruit_and_animals():
    s = veo_clip_negation("human").lower()
    assert "human" in s
    assert "blueberries" in s
    assert "not animals" in s


def test_veo_fruit_sunstoriz_returns_empty():
    assert veo_clip_negation("fruit_sunstoriz") == ""


def test_veo_ai_choose_returns_empty():
    assert veo_clip_negation("ai_choose") == ""
