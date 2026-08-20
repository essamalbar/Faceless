"""genre_key -> VisualTemplate. The single place the per-genre animated look
(palette, font, lyric styling, FX set, transition, overlay dir) is defined.
Pure data + a lookup; no I/O."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"


@dataclass(frozen=True)
class LyricStyle:
    font_file: str      # absolute path string under assets/fonts
    karaoke_fill: str   # ASS &HAABBGGRR& color swept in as each word is sung
    karaoke_base: str   # not-yet-sung word color
    hook_color: str     # chorus hook-word color
    outline: str        # outline color
    outline_w: int = 3
    glow: bool = False


@dataclass(frozen=True)
class VisualTemplate:
    genre_key: str
    bg: str            # hex, backdrop grade anchor
    accent1: str
    accent2: str
    text: str
    lyric: LyricStyle
    fx_set: tuple[str, ...]   # ids consumed by song_animate: grade_*, beat_flash, rgb_glitch, light_sweep, grain, vignette, push_in
    overlay_dir: str | None   # "assets/overlays/<genre_key>" or None -> procedural only
    transition: str           # "hardcut" | "dip" | "glitch"


def _font(name: str) -> str:
    return str(_FONT_DIR / name)


# One shared default font that ships with the repo (Task confirms the actual
# filename present in assets/fonts and uses it here for every template).
_DEFAULT_FONT = "Amiri-Regular.ttf"

_TEMPLATES: dict[str, VisualTemplate] = {
    "arabic_pop": VisualTemplate(
        genre_key="arabic_pop", bg="#0d1b2a", accent1="#ff6b6b", accent2="#4ecdc4",
        text="#ffffff",
        lyric=LyricStyle(_font(_DEFAULT_FONT), "&H004CECDC&", "&H80FFFFFF&",
                         "&H006BFF6B&", "&H00000000&", 3, glow=True),
        fx_set=("grade_pop", "beat_flash", "light_sweep", "grain"),
        overlay_dir="assets/overlays/arabic_pop", transition="dip"),
    "arabic_ballad": VisualTemplate(
        genre_key="arabic_ballad", bg="#17060f", accent1="#ffd3a8", accent2="#b8607e",
        text="#ffe3d2",
        lyric=LyricStyle(_font(_DEFAULT_FONT), "&H00D2E3FF&", "&H80D2E3FF&",
                         "&H00A8D3FF&", "&H00000000&", 3, glow=True),
        fx_set=("grade_warm", "push_in", "light_sweep", "grain"),
        overlay_dir="assets/overlays/arabic_ballad", transition="dip"),
    "khaleeji": VisualTemplate(
        genre_key="khaleeji", bg="#1a1410", accent1="#ffd700", accent2="#ff8c42",
        text="#ffeee5",
        lyric=LyricStyle(_font(_DEFAULT_FONT), "&H004288FF&", "&H80FFFFFF&",
                         "&H0042D7FF&", "&H00000000&", 3, glow=True),
        fx_set=("grade_warm", "beat_flash", "light_sweep", "vignette"),
        overlay_dir="assets/overlays/khaleeji", transition="dip"),
    "tarab_classic": VisualTemplate(
        genre_key="tarab_classic", bg="#0f0805", accent1="#d4af37", accent2="#8b4513",
        text="#ffd9b3",
        lyric=LyricStyle(_font(_DEFAULT_FONT), "&H0037AFD4&", "&H80FFFFFF&",
                         "&H0037D4AF&", "&H00000000&", 4, glow=True),
        fx_set=("grade_warm", "push_in", "light_sweep", "vignette"),
        overlay_dir="assets/overlays/tarab_classic", transition="dip"),
    "arabic_trap": VisualTemplate(
        genre_key="arabic_trap", bg="#0b0016", accent1="#ff00e5", accent2="#00fff7",
        text="#ffffff",
        lyric=LyricStyle(_font(_DEFAULT_FONT), "&H00F7FF00&", "&H80FFFFFF&",
                         "&H00E500FF&", "&H00000000&", 4, glow=True),
        fx_set=("grade_neon", "beat_flash", "rgb_glitch", "grain"),
        overlay_dir="assets/overlays/arabic_trap", transition="glitch"),
    "folk_shaabi": VisualTemplate(
        genre_key="folk_shaabi", bg="#1a0a0a", accent1="#ff6347", accent2="#ffa500",
        text="#ffe4e1",
        lyric=LyricStyle(_font(_DEFAULT_FONT), "&H004735FF&", "&H80FFFFFF&",
                         "&H0047FFFF&", "&H00000000&", 3, glow=True),
        fx_set=("grade_warm", "beat_flash", "grain", "vignette"),
        overlay_dir="assets/overlays/folk_shaabi", transition="dip"),
    "hiphop_rap": VisualTemplate(
        genre_key="hiphop_rap", bg="#0a0a0a", accent1="#ffff00", accent2="#ff6600",
        text="#ffffff",
        lyric=LyricStyle(_font(_DEFAULT_FONT), "&H0000FFFF&", "&H80FFFFFF&",
                         "&H0000FF00&", "&H00000000&", 3, glow=False),
        fx_set=("grade_cool", "beat_flash", "rgb_glitch", "grain"),
        overlay_dir="assets/overlays/hiphop_rap", transition="hardcut"),
    "rnb_soul": VisualTemplate(
        genre_key="rnb_soul", bg="#1a1410", accent1="#d4a574", accent2="#8b6f47",
        text="#e6d5c3",
        lyric=LyricStyle(_font(_DEFAULT_FONT), "&H0074A5D4&", "&H80E6D5C3&",
                         "&H00A574D4&", "&H00000000&", 3, glow=True),
        fx_set=("grade_warm", "push_in", "light_sweep", "grain"),
        overlay_dir="assets/overlays/rnb_soul", transition="dip"),
    "pop": VisualTemplate(
        genre_key="pop", bg="#0d0d2b", accent1="#ff1493", accent2="#00d4ff",
        text="#ffffff",
        lyric=LyricStyle(_font(_DEFAULT_FONT), "&H00FFD400&", "&H80FFFFFF&",
                         "&H009314FF&", "&H00000000&", 3, glow=True),
        fx_set=("grade_pop", "beat_flash", "light_sweep", "grain"),
        overlay_dir="assets/overlays/pop", transition="dip"),
    "rock": VisualTemplate(
        genre_key="rock", bg="#1a0a0a", accent1="#dc143c", accent2="#8b0000",
        text="#e0e0e0",
        lyric=LyricStyle(_font(_DEFAULT_FONT), "&H003C14DC&", "&H80E0E0E0&",
                         "&H003CFF14&", "&H00000000&", 4, glow=False),
        fx_set=("grade_cool", "beat_flash", "rgb_glitch", "grain"),
        overlay_dir="assets/overlays/rock", transition="hardcut"),
    "edm_electropop": VisualTemplate(
        genre_key="edm_electropop", bg="#0a0a1f", accent1="#ff00ff", accent2="#00ffff",
        text="#ffffff",
        lyric=LyricStyle(_font(_DEFAULT_FONT), "&H00FFFF00&", "&H80FFFFFF&",
                         "&H00FF00FF&", "&H00000000&", 3, glow=True),
        fx_set=("grade_neon", "beat_flash", "grain", "light_sweep"),
        overlay_dir="assets/overlays/edm_electropop", transition="glitch"),
    "cinematic_ost": VisualTemplate(
        genre_key="cinematic_ost", bg="#0a0a14", accent1="#d4af37", accent2="#4a3f35",
        text="#f5f5f5",
        lyric=LyricStyle(_font(_DEFAULT_FONT), "&H0037AFD4&", "&H80F5F5F5&",
                         "&H0037D7FF&", "&H00000000&", 4, glow=True),
        fx_set=("grade_cool", "push_in", "light_sweep", "vignette"),
        overlay_dir="assets/overlays/cinematic_ost", transition="dip"),
    "generic": VisualTemplate(
        genre_key="generic", bg="#0d0d12", accent1="#7c5cff", accent2="#33e0ff",
        text="#ffffff",
        lyric=LyricStyle(_font(_DEFAULT_FONT), "&H00FFD07C&", "&H80FFFFFF&",
                         "&H00FF5CE0&", "&H00000000&", 3, glow=True),
        fx_set=("grade_cool", "push_in", "light_sweep", "grain"),
        overlay_dir=None, transition="dip"),
}


def visual_template_for(genre_key: str) -> VisualTemplate:
    return _TEMPLATES.get(genre_key, _TEMPLATES["generic"])
