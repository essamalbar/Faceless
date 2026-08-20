from __future__ import annotations

from pipeline.song_style import GENRE_RECIPES
from pipeline.song_visual_style import VisualTemplate, visual_template_for


def test_every_genre_key_resolves_to_a_full_template():
    for key in GENRE_RECIPES:
        t = visual_template_for(key)
        assert isinstance(t, VisualTemplate)
        assert t.genre_key == key
        assert t.bg and t.accent1 and t.text
        assert t.lyric.font_file and t.lyric.karaoke_fill and t.lyric.hook_color
        assert isinstance(t.fx_set, tuple) and t.fx_set  # at least one FX


def test_unknown_key_falls_back_to_generic():
    t = visual_template_for("does-not-exist")
    assert t.genre_key == "generic"


def test_trap_is_high_energy_and_ballad_is_soft():
    trap = visual_template_for("arabic_trap")
    ballad = visual_template_for("arabic_ballad")
    assert "beat_flash" in trap.fx_set and "rgb_glitch" in trap.fx_set
    assert "beat_flash" not in ballad.fx_set  # ballad is bold-but-soft, not strobing
