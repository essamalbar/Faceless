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
class MotionProfile:
    """Per-genre MOTION character consumed by song_animate's beat-synced
    camera + FX. This is what makes a ballad drift soft and slow while a trap
    track punches hard on every kick — the character of the motion differs by
    genre, not just the color grade. All amplitudes are deliberately small/
    bounded so the compositor can never produce a wild zoom or a strobe.

    - punch_amp:     beat zoom-punch amplitude (zoom fraction added on each beat)
    - punch_decay:   seconds the punch eases back over (ballad long, trap short)
    - drift_rate:    slow continuous push-in per output frame (parallax feel)
    - flash_amp:     eased beat brightness-pop amplitude
    - overlay_pulse: how much genre-overlay opacity breathes with the beat (P2)
    - cut_bars:      bars between backdrop re-frames (P2)
    """
    punch_amp: float
    punch_decay: float
    drift_rate: float
    flash_amp: float
    overlay_pulse: float
    cut_bars: int


# Three motion archetypes assigned per genre by energy. SOFT = emotional/
# cinematic (gentle, slow, long decay); MID = mainstream pop; HARD = trap/
# EDM/rock (aggressive punch, snaps back fast, denser re-frames).
_MOTION_SOFT = MotionProfile(
    punch_amp=0.014, punch_decay=0.40, drift_rate=0.00003,
    flash_amp=0.08, overlay_pulse=0.20, cut_bars=8)
_MOTION_MID = MotionProfile(
    punch_amp=0.030, punch_decay=0.16, drift_rate=0.00004,
    flash_amp=0.12, overlay_pulse=0.35, cut_bars=5)
_MOTION_HARD = MotionProfile(
    punch_amp=0.060, punch_decay=0.09, drift_rate=0.00005,
    flash_amp=0.16, overlay_pulse=0.50, cut_bars=3)


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
    motion: MotionProfile     # per-genre beat-synced motion character


def _font(name: str) -> str:
    return str(_FONT_DIR / name)


# One shared default font that ships with the repo (Task confirms the actual
# filename present in assets/fonts and uses it here for every template).
_DEFAULT_FONT = "Amiri-Regular.ttf"

_TEMPLATES: dict[str, VisualTemplate] = {
    "arabic_pop": VisualTemplate(
        genre_key="arabic_pop", bg="#0d1b2a", accent1="#ff6b6b", accent2="#4ecdc4",
        text="#ffffff",
        lyric=LyricStyle(_font(_DEFAULT_FONT), "&H006B6BFF&", "&H80FFFFFF&",
                         "&H00C4CD4E&", "&H00000000&", 3, glow=True),
        fx_set=("grade_pop", "beat_flash", "light_sweep"),
        overlay_dir="assets/overlays/arabic_pop", transition="dip",
        motion=_MOTION_MID),
    "arabic_ballad": VisualTemplate(
        genre_key="arabic_ballad", bg="#17060f", accent1="#ffd3a8", accent2="#b8607e",
        text="#ffe3d2",
        lyric=LyricStyle(_font(_DEFAULT_FONT), "&H00D2E3FF&", "&H80D2E3FF&",
                         "&H007E60B8&", "&H00000000&", 3, glow=True),
        fx_set=("grade_warm", "push_in", "light_sweep"),
        overlay_dir="assets/overlays/arabic_ballad", transition="dip",
        motion=_MOTION_SOFT),
    "khaleeji": VisualTemplate(
        genre_key="khaleeji", bg="#1a1410", accent1="#ffd700", accent2="#ff8c42",
        text="#ffeee5",
        lyric=LyricStyle(_font(_DEFAULT_FONT), "&H0000D7FF&", "&H80FFFFFF&",
                         "&H00428CFF&", "&H00000000&", 3, glow=True),
        fx_set=("grade_warm", "beat_flash", "light_sweep", "vignette"),
        overlay_dir="assets/overlays/khaleeji", transition="dip",
        motion=_MOTION_MID),
    "tarab_classic": VisualTemplate(
        genre_key="tarab_classic", bg="#0f0805", accent1="#d4af37", accent2="#8b4513",
        text="#ffd9b3",
        lyric=LyricStyle(_font(_DEFAULT_FONT), "&H003AAFD4&", "&H80FFFFFF&",
                         "&H0013458B&", "&H00000000&", 4, glow=True),
        fx_set=("grade_warm", "push_in", "light_sweep", "vignette"),
        overlay_dir="assets/overlays/tarab_classic", transition="dip",
        motion=_MOTION_SOFT),
    "arabic_trap": VisualTemplate(
        genre_key="arabic_trap", bg="#0b0016", accent1="#ff00e5", accent2="#00fff7",
        text="#ffffff",
        lyric=LyricStyle(_font(_DEFAULT_FONT), "&H00F7FF00&", "&H80FFFFFF&",
                         "&H00E500FF&", "&H00000000&", 4, glow=True),
        fx_set=("grade_neon", "beat_flash", "rgb_glitch"),
        overlay_dir="assets/overlays/arabic_trap", transition="glitch",
        motion=_MOTION_HARD),
    "folk_shaabi": VisualTemplate(
        genre_key="folk_shaabi", bg="#1a0a0a", accent1="#ff6347", accent2="#ffa500",
        text="#ffe4e1",
        lyric=LyricStyle(_font(_DEFAULT_FONT), "&H004763FF&", "&H80FFFFFF&",
                         "&H0000A5FF&", "&H00000000&", 3, glow=True),
        fx_set=("grade_warm", "beat_flash", "vignette"),
        overlay_dir="assets/overlays/folk_shaabi", transition="dip",
        motion=_MOTION_MID),
    "hiphop_rap": VisualTemplate(
        genre_key="hiphop_rap", bg="#0a0a0a", accent1="#ffff00", accent2="#ff6600",
        text="#ffffff",
        lyric=LyricStyle(_font(_DEFAULT_FONT), "&H0000FFFF&", "&H80FFFFFF&",
                         "&H000066FF&", "&H00000000&", 3, glow=False),
        fx_set=("grade_cool", "beat_flash", "rgb_glitch"),
        overlay_dir="assets/overlays/hiphop_rap", transition="hardcut",
        motion=_MOTION_HARD),
    "rnb_soul": VisualTemplate(
        genre_key="rnb_soul", bg="#1a1410", accent1="#d4a574", accent2="#8b6f47",
        text="#e6d5c3",
        lyric=LyricStyle(_font(_DEFAULT_FONT), "&H0074A5D4&", "&H80C3D5E6&",
                         "&H00476F8B&", "&H00000000&", 3, glow=True),
        fx_set=("grade_warm", "push_in", "light_sweep"),
        overlay_dir="assets/overlays/rnb_soul", transition="dip",
        motion=_MOTION_SOFT),
    "pop": VisualTemplate(
        genre_key="pop", bg="#0d0d2b", accent1="#ff1493", accent2="#00d4ff",
        text="#ffffff",
        lyric=LyricStyle(_font(_DEFAULT_FONT), "&H009314FF&", "&H80FFFFFF&",
                         "&H00FFD400&", "&H00000000&", 3, glow=True),
        fx_set=("grade_pop", "beat_flash", "light_sweep"),
        overlay_dir="assets/overlays/pop", transition="dip",
        motion=_MOTION_MID),
    "rock": VisualTemplate(
        genre_key="rock", bg="#1a0a0a", accent1="#dc143c", accent2="#8b0000",
        text="#e0e0e0",
        lyric=LyricStyle(_font(_DEFAULT_FONT), "&H003C14DC&", "&H80E0E0E0&",
                         "&H0000008B&", "&H00000000&", 4, glow=False),
        fx_set=("grade_cool", "beat_flash", "rgb_glitch"),
        overlay_dir="assets/overlays/rock", transition="hardcut",
        motion=_MOTION_HARD),
    "edm_electropop": VisualTemplate(
        genre_key="edm_electropop", bg="#0a0a1f", accent1="#ff00ff", accent2="#00ffff",
        text="#ffffff",
        lyric=LyricStyle(_font(_DEFAULT_FONT), "&H00FF00FF&", "&H80FFFFFF&",
                         "&H00FFFF00&", "&H00000000&", 3, glow=True),
        fx_set=("grade_neon", "beat_flash", "light_sweep"),
        overlay_dir="assets/overlays/edm_electropop", transition="glitch",
        motion=_MOTION_HARD),
    "cinematic_ost": VisualTemplate(
        genre_key="cinematic_ost", bg="#0a0a14", accent1="#d4af37", accent2="#4a3f35",
        text="#f5f5f5",
        lyric=LyricStyle(_font(_DEFAULT_FONT), "&H003AAFD4&", "&H80F5F5F5&",
                         "&H00353F4A&", "&H00000000&", 4, glow=True),
        fx_set=("grade_cool", "push_in", "light_sweep", "vignette"),
        overlay_dir="assets/overlays/cinematic_ost", transition="dip",
        motion=_MOTION_SOFT),
    "generic": VisualTemplate(
        genre_key="generic", bg="#0d0d12", accent1="#7c5cff", accent2="#33e0ff",
        text="#ffffff",
        lyric=LyricStyle(_font(_DEFAULT_FONT), "&H00FF5C7C&", "&H80FFFFFF&",
                         "&H00FFE033&", "&H00000000&", 3, glow=True),
        fx_set=("grade_cool", "push_in", "light_sweep"),
        overlay_dir=None, transition="dip",
        motion=_MOTION_MID),
}


def visual_template_for(genre_key: str) -> VisualTemplate:
    return _TEMPLATES.get(genre_key, _TEMPLATES["generic"])
