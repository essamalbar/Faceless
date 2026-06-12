"""Per-song Open Graph card composer.

Generates a 1200×630 card combining the song's cover art + title +
brand mark. Used as og:image / twitter:image on the public share page
so links pasted into WhatsApp / Twitter / Instagram show the actual
song (rather than a generic Faceless Lab placeholder).

Output path: <run_dir>/og.png. Idempotent — if the file already
exists newer than its inputs (cover.png + title), the render is
skipped.

Composition layout (LTR for English, mirrored for RTL):

    ┌─────────────────────────────────────────────────────────┐
    │  ┌──────────┐                                           │
    │  │          │   FACELESS LAB · AI SONG                  │
    │  │  cover   │                                           │
    │  │  500px²  │   {Song Title}                            │
    │  │          │                                           │
    │  │          │   ──────                                  │
    │  │          │   {teaser line from lyrics}               │
    │  └──────────┘                                           │
    │                                  ▶ Listen on faceless-lab.com
    └─────────────────────────────────────────────────────────┘
"""
from __future__ import annotations

import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

_FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
_W, _H = 1200, 630
_PAD = 56
_COVER_SIZE = 500
_RIGHT_X = _PAD + _COVER_SIZE + 56  # left edge of the text column

_BG_TOP = (19, 26, 42)       # #131a2a
_BG_BOTTOM = (6, 8, 13)      # #06080d
_FG_0 = (243, 245, 251)
_FG_2 = (127, 134, 156)
_FG_3 = (74, 82, 102)
_ACCENT = (215, 180, 106)
_ACCENT_SOFT = (215, 180, 106, 70)


def _font_for(language: str, size: int, weight_axis: int | None = 700) -> ImageFont.FreeTypeFont:
    """Bundled-font selector. Same convention as pipeline/song_cover.py
    (Amiri for RTL, Inter for LTR). Variable-font weight axis applied
    where the file supports it."""
    if language in ("ar", "he", "fa", "ur"):
        font_path = _FONT_DIR / "Amiri-Regular.ttf"
    else:
        font_path = _FONT_DIR / "Inter-Bold.ttf"
    font = ImageFont.truetype(str(font_path), size=size)
    if weight_axis is not None:
        try:
            font.set_variation_by_axes([weight_axis])
        except (OSError, AttributeError):
            pass
    return font


def _vertical_gradient(size: tuple[int, int], top: tuple[int, int, int],
                       bottom: tuple[int, int, int]) -> Image.Image:
    """Synthesize a linear vertical gradient as an RGB image."""
    w, h = size
    img = Image.new("RGB", size, top)
    px = img.load()
    for y in range(h):
        t = y / max(h - 1, 1)
        r = int(top[0] * (1 - t) + bottom[0] * t)
        g = int(top[1] * (1 - t) + bottom[1] * t)
        b = int(top[2] * (1 - t) + bottom[2] * t)
        for x in range(w):
            px[x, y] = (r, g, b)
    return img


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """Wrap on whitespace into lines that fit max_width. Honors hard
    \\n if the source already line-broke."""
    out: list[str] = []
    for paragraph in text.splitlines():
        words = paragraph.split()
        if not words:
            continue
        line = words[0]
        for w in words[1:]:
            candidate = f"{line} {w}"
            if font.getlength(candidate) <= max_width:
                line = candidate
            else:
                out.append(line)
                line = w
        out.append(line)
    return out


def _fit_title(title: str, language: str, max_w: int, max_h: int) -> tuple[ImageFont.FreeTypeFont, list[str]]:
    """Pick the largest font size that wraps the title into <= max_h
    pixels at <= max_w line width. Falls back to a small font if even
    the smallest size overflows (the lines will overflow gracefully —
    PIL doesn't clip)."""
    is_rtl = language in ("ar", "he", "fa", "ur")
    # RTL Amiri reads larger at the same point size, so we start
    # slightly smaller to keep the layouts visually balanced.
    sizes = (78, 70, 64, 58, 52, 46, 40) if is_rtl else (82, 74, 66, 58, 52, 46, 40)
    for size in sizes:
        font = _font_for(language, size, weight_axis=700)
        lines = _wrap_text(title, font, max_w)
        if not lines:
            continue
        line_h = int(size * (1.30 if is_rtl else 1.18))
        if len(lines) * line_h <= max_h:
            return font, lines
    # Smallest font, may overflow but we never crop the rest of the card.
    font = _font_for(language, sizes[-1], weight_axis=700)
    return font, _wrap_text(title, font, max_w)


def _placeholder_cover(size: int) -> Image.Image:
    """Fallback if the run's cover.png is missing — solid gold gradient
    so the OG still composes rather than 500ing."""
    g = _vertical_gradient((size, size), (37, 30, 14), (92, 71, 31))
    return g


def compose_og_image(
    *,
    cover_path: Path,
    title: str,
    language: str,
    teaser: str,
    out_path: Path,
    brand: str = "Faceless Lab",
) -> Path:
    """Compose the 1200×630 OG card and write it to `out_path`.

    Idempotent — if out_path is newer than cover_path it returns
    immediately. Title + language are baked into the rendered image,
    so changes to either invalidate the cache; the caller is expected
    to also bump file mtime (or delete) when the title is edited.
    """
    if out_path.exists() and cover_path.exists():
        try:
            if out_path.stat().st_mtime >= cover_path.stat().st_mtime:
                return out_path
        except OSError:
            pass

    is_rtl = language in ("ar", "he", "fa", "ur")

    # 1. Background — radial-ish gradient (top brighter, bottom darker)
    canvas = _vertical_gradient((_W, _H), _BG_TOP, _BG_BOTTOM).convert("RGBA")

    # 2. Cover thumbnail with a soft gold rim
    if cover_path.exists():
        try:
            cover = Image.open(cover_path).convert("RGB")
        except (OSError, ValueError):
            cover = _placeholder_cover(_COVER_SIZE)
    else:
        cover = _placeholder_cover(_COVER_SIZE)
    cover = cover.resize((_COVER_SIZE, _COVER_SIZE), Image.LANCZOS)

    # Build a rounded mask for the cover so corners aren't sharp.
    mask = Image.new("L", (_COVER_SIZE, _COVER_SIZE), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, _COVER_SIZE, _COVER_SIZE), radius=28, fill=255,
    )
    # Drop shadow under the cover
    shadow = Image.new("RGBA", (_COVER_SIZE + 80, _COVER_SIZE + 80), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        (40, 50, 40 + _COVER_SIZE, 50 + _COVER_SIZE),
        radius=28, fill=(0, 0, 0, 170),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(24))

    cover_x = _W - _PAD - _COVER_SIZE if is_rtl else _PAD
    canvas.alpha_composite(shadow, dest=(cover_x - 40, (_H - _COVER_SIZE) // 2 - 30))
    canvas.paste(cover, (cover_x, (_H - _COVER_SIZE) // 2), mask)

    # Gold rim (1px) around the cover
    rim = Image.new("RGBA", (_COVER_SIZE, _COVER_SIZE), (0, 0, 0, 0))
    ImageDraw.Draw(rim).rounded_rectangle(
        (0, 0, _COVER_SIZE - 1, _COVER_SIZE - 1),
        radius=28, outline=_ACCENT_SOFT[:3] + (180,), width=1,
    )
    canvas.alpha_composite(rim, dest=(cover_x, (_H - _COVER_SIZE) // 2))

    # 3. Text column
    text_x = _PAD if is_rtl else _RIGHT_X
    text_w = (_W - 2 * _PAD - _COVER_SIZE - 56)  # available text column width
    draw = ImageDraw.Draw(canvas)

    # Eyebrow: "FACELESS LAB · AI SONG"
    eyebrow_font = _font_for("en", 22, weight_axis=600)
    eyebrow = f"{brand.upper()}  ·  AI SONG"
    eyebrow_y = 124
    draw.text(
        (text_x, eyebrow_y), eyebrow,
        font=eyebrow_font, fill=_ACCENT,
        anchor=("rt" if is_rtl else "lt"),
    )

    # Title block
    title_max_h = 260
    title_font, title_lines = _fit_title(title, language, text_w, title_max_h)
    title_y = eyebrow_y + 50
    line_h = int(title_font.size * (1.30 if is_rtl else 1.18))
    for i, ln in enumerate(title_lines):
        draw.text(
            (text_x, title_y + i * line_h), ln,
            font=title_font, fill=_FG_0,
            anchor="rt" if is_rtl else "lt",
        )

    # Gold separator
    sep_y = title_y + len(title_lines) * line_h + 28
    sep_w = 96
    if is_rtl:
        draw.line([(text_x - sep_w, sep_y), (text_x, sep_y)], fill=_ACCENT, width=3)
    else:
        draw.line([(text_x, sep_y), (text_x + sep_w, sep_y)], fill=_ACCENT, width=3)

    # Teaser (1–2 lines of lyrics, cleaned)
    teaser_clean = re.sub(r"\s+", " ", teaser or "").strip()
    if teaser_clean:
        teaser_font = _font_for(language, 28, weight_axis=400)
        teaser_lines = _wrap_text(teaser_clean, teaser_font, text_w)[:2]
        for i, ln in enumerate(teaser_lines):
            draw.text(
                (text_x, sep_y + 24 + i * int(teaser_font.size * 1.25)), ln,
                font=teaser_font, fill=_FG_2,
                anchor="rt" if is_rtl else "lt",
            )

    # 4. Footer mark — "▶  faceless-lab.com"
    foot_font = _font_for("en", 22, weight_axis=600)
    foot_y = _H - 60
    foot_text = "▶  faceless-lab.com"
    draw.text(
        (text_x, foot_y), foot_text,
        font=foot_font, fill=_FG_2,
        anchor="rt" if is_rtl else "lt",
    )

    # 5. Write atomically — .tmp + replace so a concurrent reader
    # never sees a half-written PNG (matches the rest of the
    # pipeline's hand-rolled atomicity).
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(out_path.suffix + ".tmp")
    canvas.convert("RGB").save(tmp, "PNG", optimize=True)
    tmp.replace(out_path)
    return out_path
