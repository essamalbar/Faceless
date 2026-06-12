"""Faceless Lab watermark PNG composer.

Renders a small horizontal brand pill used as the burned-in watermark on
every assembled MP4. Replaces the earlier plain ffmpeg drawtext approach
("▶ faceless-lab.com" in flat white) with a designed brand mark that
matches the rest of the product:

  * Gold sparkle constellation on a brushed-gold disc — same layout as
    the SparkleLogo on the marketing site and the in-app brand widget,
    so the watermark reads instantly as the platform's mark.
  * "FACELESS LAB" wordmark in Inter Bold all-caps with 0.08em tracking
    in pure white.
  * Compact "AI STUDIO" eyebrow underneath in muted gold.
  * Dark navy pill background at 70% opacity with a 1px gold rim and a
    soft drop shadow so the mark stays legible on any cover-art color.

The PNG is rendered once at module import via render_watermark_png()
and cached at assets/watermark.png. The Dockerfile already ships
assets/ into the container so no runtime regeneration is needed —
this is a "create on local dev, commit, deploy" asset.

The 2x source resolution (480 × 110) lets ffmpeg overlay scale the
mark down crisply to 240 × 55 on the 1080 × 1080 video without
sampling artifacts. Subjectively small enough to not crowd the song
content, large enough to be unambiguous attribution at preview size.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

# Output dimensions tuned for the final overlay at 240 × 55 on a
# 1080 × 1080 frame. Source rendered at 2x for retina-grade resampling.
_W, _H = 480, 110

# Brand palette — matches the share page and the marketing site.
_PILL_FILL = (8, 11, 18, 178)           # rgba navy ~70% opacity
_PILL_BORDER = (215, 180, 106, 90)      # accent at 35% opacity
_DISC_HOT = (231, 181, 60, 255)         # accent (hot end of gradient)
_DISC_COLD = (176, 127, 31, 255)        # accent dark (cold end)
_SPARKLE = (10, 14, 26, 255)            # bg-0; sparkles "cut" out of the disc
_TEXT = (243, 245, 251, 240)            # near-white, 94% alpha
_EYEBROW = (215, 180, 106, 220)         # gold accent for the AI tag


def _font_path() -> Path:
    """Inter Bold ships with the repo for cover-art + ASS subtitles.
    Reused here so the watermark font matches the rest of the brand."""
    return Path(__file__).resolve().parent.parent / "assets" / "fonts" / "Inter-Bold.ttf"


def _load_font(size: int, weight: int = 700) -> ImageFont.FreeTypeFont:
    font = ImageFont.truetype(str(_font_path()), size=size)
    try:
        font.set_variation_by_axes([weight])
    except (OSError, AttributeError):
        pass
    return font


def _sparkle_path(cx: float, cy: float, r: float) -> list[tuple[float, float]]:
    """Constellation sparkle: two crossed pinched diamonds (vertical +
    horizontal) sharing a center. Same proportions as the SparkleLogo
    SVG on the marketing site / the in-app widget, so the watermark
    reads as the same brand mark across surfaces."""
    pinch = r * 0.18
    return [
        # Vertical pinched diamond
        (cx, cy - r), (cx + pinch, cy), (cx, cy + r), (cx - pinch, cy),
        # Horizontal pinched diamond joined to close the path; we draw
        # the two diamonds as separate polygons via two .polygon calls.
    ]


def _draw_sparkle(draw: ImageDraw.ImageDraw, cx: float, cy: float, r: float,
                  fill: tuple) -> None:
    """Render a single sparkle (two crossed diamonds) onto draw."""
    pinch = r * 0.18
    # Vertical
    draw.polygon([
        (cx, cy - r), (cx + pinch, cy), (cx, cy + r), (cx - pinch, cy),
    ], fill=fill)
    # Horizontal
    draw.polygon([
        (cx - r, cy), (cx, cy + pinch), (cx + r, cy), (cx, cy - pinch),
    ], fill=fill)


def _vertical_gradient_disc(diameter: int, top: tuple, bottom: tuple) -> Image.Image:
    """Round gold disc with a top-to-bottom gradient — same as the
    SparkleLogo background fill on the marketing nav."""
    img = Image.new("RGBA", (diameter, diameter), (0, 0, 0, 0))
    px = img.load()
    cx = cy = diameter / 2
    rr = (diameter / 2) ** 2
    for y in range(diameter):
        t = y / max(diameter - 1, 1)
        r = int(top[0] * (1 - t) + bottom[0] * t)
        g = int(top[1] * (1 - t) + bottom[1] * t)
        b = int(top[2] * (1 - t) + bottom[2] * t)
        for x in range(diameter):
            dx = x - cx
            dy = y - cy
            if dx * dx + dy * dy <= rr:
                px[x, y] = (r, g, b, 255)
    return img


def render_watermark_png(out_path: Path) -> Path:
    """Render the watermark to out_path. Idempotent — overwrites
    any existing file. Returns out_path."""
    canvas = Image.new("RGBA", (_W, _H), (0, 0, 0, 0))

    # 1. Soft drop shadow behind the pill — gives the watermark
    #    separation from the underlying video frame at any background.
    shadow_layer = Image.new("RGBA", (_W + 40, _H + 40), (0, 0, 0, 0))
    ImageDraw.Draw(shadow_layer).rounded_rectangle(
        (20, 24, _W + 20, _H + 20), radius=_H // 2, fill=(0, 0, 0, 110),
    )
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(8))
    canvas_with_shadow = Image.new("RGBA", (_W + 40, _H + 40), (0, 0, 0, 0))
    canvas_with_shadow.alpha_composite(shadow_layer)

    # 2. Pill background — fully rounded rect.
    pill = Image.new("RGBA", (_W, _H), (0, 0, 0, 0))
    pdraw = ImageDraw.Draw(pill)
    pdraw.rounded_rectangle((0, 0, _W, _H), radius=_H // 2, fill=_PILL_FILL)
    # Thin gold rim (1.5px effective)
    pdraw.rounded_rectangle(
        (1, 1, _W - 1, _H - 1), radius=_H // 2 - 1,
        outline=_PILL_BORDER, width=2,
    )
    canvas_with_shadow.alpha_composite(pill, dest=(20, 16))
    canvas = canvas_with_shadow.crop((20, 16, _W + 20, _H + 16))

    # 3. Brand mark — gold disc with sparkle constellation.
    disc_d = 64
    disc_xy = (28, (_H - disc_d) // 2)
    disc = _vertical_gradient_disc(disc_d, _DISC_HOT[:3], _DISC_COLD[:3])
    canvas.alpha_composite(disc, dest=disc_xy)

    # 4. Sparkles on top of the disc, navy-cut. Geometry mirrors the
    #    SVG SparkleLogo: hero sparkle slightly off-center, two
    #    satellites at corners.
    draw_constellation_layer = Image.new("RGBA", (_W, _H), (0, 0, 0, 0))
    ddraw = ImageDraw.Draw(draw_constellation_layer)
    cx = disc_xy[0] + disc_d / 2
    cy = disc_xy[1] + disc_d / 2
    rad = disc_d / 2
    # hero
    _draw_sparkle(ddraw,
                  cx - rad * 0.06, cy + rad * 0.02,
                  rad * 0.5, _SPARKLE)
    # satellite 1 (top-right)
    _draw_sparkle(ddraw,
                  cx + rad * 0.42, cy - rad * 0.42,
                  rad * 0.2, _SPARKLE)
    # satellite 2 (bottom-right)
    _draw_sparkle(ddraw,
                  cx + rad * 0.45, cy + rad * 0.4,
                  rad * 0.15, _SPARKLE)
    canvas.alpha_composite(draw_constellation_layer)

    # 5. Wordmark — FACELESS LAB / AI STUDIO. Stacked, left-aligned.
    text_x = disc_xy[0] + disc_d + 22
    title_font = _load_font(26, weight=700)
    eyebrow_font = _load_font(11, weight=600)

    tdraw = ImageDraw.Draw(canvas)
    title = "FACELESS LAB"
    tdraw.text((text_x, _H // 2 - 22), title, font=title_font, fill=_TEXT)
    # Letter-spaced eyebrow under the wordmark
    eyebrow = "A I   S T U D I O"  # double-spaced visually
    tdraw.text((text_x + 1, _H // 2 + 12), eyebrow, font=eyebrow_font,
               fill=_EYEBROW)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(out_path.suffix + ".tmp")
    canvas.save(tmp, "PNG", optimize=True)
    tmp.replace(out_path)
    return out_path


if __name__ == "__main__":
    target = Path(__file__).resolve().parent.parent / "assets" / "watermark.png"
    render_watermark_png(target)
    print(f"wrote {target}")
