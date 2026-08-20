from __future__ import annotations

import re

from pipeline.song_style import GENRE_RECIPES
from pipeline.song_visual_style import VisualTemplate, visual_template_for, _TEMPLATES


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


def test_lyric_color_format_and_accent_alignment():
    """Regression: lyric colors must be valid ASS format and match template accents.
    Catches transposed-byte-order (BGR vs RGB) bugs where hook_color/karaoke_fill
    don't match the template's intended accent colors."""

    def decode_ass_color(color_str: str) -> tuple[int, int, int]:
        """Decode ASS color &HAABBGGRR& to (R, G, B)."""
        hex_str = color_str[2:-1]  # Remove &H and &, leaves AABBGGRR
        # Skip AA (alpha), extract BB, GG, RR
        b = int(hex_str[2:4], 16)
        g = int(hex_str[4:6], 16)
        r = int(hex_str[6:8], 16)
        return (r, g, b)

    def hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
        """Convert #RRGGBB to (R, G, B)."""
        hex_str = hex_str.lstrip("#")
        r = int(hex_str[0:2], 16)
        g = int(hex_str[2:4], 16)
        b = int(hex_str[4:6], 16)
        return (r, g, b)

    def color_distance(rgb1: tuple[int, int, int], rgb2: tuple[int, int, int]) -> float:
        """Euclidean distance between two RGB colors."""
        return sum((a - b) ** 2 for a, b in zip(rgb1, rgb2)) ** 0.5

    for key, template in _TEMPLATES.items():
        lyric = template.lyric
        accent1 = hex_to_rgb(template.accent1)
        accent2 = hex_to_rgb(template.accent2)

        # Validate ASS color format for all lyric colors
        for color_name, color_str in [
            ("karaoke_fill", lyric.karaoke_fill),
            ("karaoke_base", lyric.karaoke_base),
            ("hook_color", lyric.hook_color),
        ]:
            assert re.match(r"^&H[0-9A-Fa-f]{8}&$", color_str), \
                f"{key}.lyric.{color_name} invalid ASS format: {color_str}"

        # Check karaoke_fill is close to one of the accent colors
        fill_rgb = decode_ass_color(lyric.karaoke_fill)
        dist_a1_fill = color_distance(fill_rgb, accent1)
        dist_a2_fill = color_distance(fill_rgb, accent2)
        min_dist_fill = min(dist_a1_fill, dist_a2_fill)
        assert min_dist_fill < 25, \
            f"{key}.lyric.karaoke_fill {lyric.karaoke_fill} (RGB{fill_rgb}) " \
            f"far from accent1{accent1} (dist={dist_a1_fill:.1f}) and accent2{accent2} (dist={dist_a2_fill:.1f})"

        # Check hook_color is close to one of the accent colors
        hook_rgb = decode_ass_color(lyric.hook_color)
        dist_a1_hook = color_distance(hook_rgb, accent1)
        dist_a2_hook = color_distance(hook_rgb, accent2)
        min_dist_hook = min(dist_a1_hook, dist_a2_hook)
        assert min_dist_hook < 25, \
            f"{key}.lyric.hook_color {lyric.hook_color} (RGB{hook_rgb}) " \
            f"far from accent1{accent1} (dist={dist_a1_hook:.1f}) and accent2{accent2} (dist={dist_a2_hook:.1f})"
