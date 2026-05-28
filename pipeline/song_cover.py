"""Song-cover generation: Kie.ai Flux Kontext Max + Pillow title overlay.

Quality gate: this uses Kie.ai's `flux-kontext-max` model (their
highest-quality Flux variant) because the cover is the only visual the
viewer sees for the entire song. See spec section "Cover generation."

The 'leave space at top-right' hint is intentional — the title is
painted in the top-right quadrant by apply_title_overlay() in the next
step. Don't fight it.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from pipeline.kie import KieClient

FLUX_MODEL_ID = "flux-kontext-max"  # high-quality variant, ~$0.03/image

_REPO_ROOT = Path(__file__).resolve().parents[1]
_FONT_DIR = _REPO_ROOT / "assets" / "fonts"
_RTL_LANGUAGES = {"ar", "he", "fa", "ur"}

_CANVAS = 1080
_MARGIN_PCT = 0.08
_MAX_TITLE_BOX_W = int(_CANVAS * 0.42)
_FONT_SIZE_MIN = 36
_FONT_SIZE_MAX = 72


def _font_path_for_language(language: str) -> Path:
    if language in _RTL_LANGUAGES:
        return _FONT_DIR / "Amiri-Regular.ttf"
    return _FONT_DIR / "Inter-Bold.ttf"


def generate_cover_image(
    *,
    client: KieClient,
    cover_prompt: str,
    out_dir: Path,
) -> Path:
    """Call Kie.ai Flux Kontext Max for the raw cover; download to
    `<out_dir>/cover_raw.png`. Returns the path."""
    full_prompt = (
        f"{cover_prompt}, professional album cover art, "
        f"art direction by Hipgnosis, cinematic lighting, "
        f"shallow depth of field, high detail, no text, no watermark, "
        f"square composition, leave space at top-right for title text"
    )
    task_id = client.submit_flux_image_job(
        prompt=full_prompt,
        model=FLUX_MODEL_ID,
        aspect_ratio="1:1",
    )
    url = client.wait_for_flux_image(task_id, poll_interval_s=5, timeout_s=300)
    out_path = out_dir / "cover_raw.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    client.download(url, out_path)
    return out_path


def _load_font(font_path: Path, size: int) -> ImageFont.FreeTypeFont:
    """Open a font at `size`. Handles variable fonts by setting Bold
    weight (wght=700) when supported — assets/fonts/Inter-Bold.ttf
    is actually the Inter variable font containing all weights, so
    without this it would render as Regular."""
    font = ImageFont.truetype(str(font_path), size=size)
    try:
        font.set_variation_by_axes([700])
    except (OSError, AttributeError):
        pass
    return font


def _fit_font(font_path: Path, title: str, max_width: int) -> ImageFont.FreeTypeFont:
    for size in range(_FONT_SIZE_MAX, _FONT_SIZE_MIN - 1, -2):
        font = _load_font(font_path, size)
        bbox = font.getbbox(title)
        text_w = bbox[2] - bbox[0]
        if text_w <= max_width:
            return font
    return _load_font(font_path, _FONT_SIZE_MIN)


def apply_title_overlay(
    *,
    raw_path: Path,
    title: str,
    language: str,
    out_path: Path,
) -> None:
    """Open `raw_path`, paint `title` in the top-right corner with a soft
    drop shadow, write to `out_path`."""
    img = Image.open(raw_path).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    font_path = _font_path_for_language(language)
    font = _fit_font(font_path, title, _MAX_TITLE_BOX_W)

    bbox = font.getbbox(title)
    text_w = bbox[2] - bbox[0]

    margin = int(_CANVAS * _MARGIN_PCT)
    x = img.size[0] - margin - text_w
    y = margin

    shadow_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow_layer)
    shadow_draw.text((x + 2, y + 2), title, font=font, fill=(0, 0, 0, 128))
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=2))

    draw.text((x, y), title, font=font, fill=(255, 255, 255, 255))

    composed = Image.alpha_composite(img, shadow_layer)
    composed = Image.alpha_composite(composed, overlay)
    composed.convert("RGB").save(out_path, format="PNG")
