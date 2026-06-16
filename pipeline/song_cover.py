"""Song-cover generation: Kie.ai Flux Kontext Max + Pillow title overlay.

Quality gate: this uses Kie.ai's `flux-kontext-max` model (their
highest-quality Flux variant) because the cover is the only visual the
viewer sees for the entire song. See spec section "Cover generation."

The 'leave space at top-right' hint is intentional — the title is
painted in the top-right quadrant by apply_title_overlay() in the next
step. Don't fight it.

If Kie's Flux service returns errors (Max + Pro both have outages
~weekly), generate_cover_image falls back to a stylized solid-color
placeholder so the song run still completes. Better a usable MP4 with
a basic cover than a failed run that consumed the Suno spend.
"""
from __future__ import annotations

import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from pipeline.kie import KieClient, KieError, TransientKieError

# Fallback chain — tried in order. First succeeding model is used.
FLUX_MODELS_TRIED = [
    "flux-kontext-max",  # high quality, ~$0.03 — preferred
    "flux-kontext-pro",  # standard, ~$0.018 — fallback
]
# Kept for backwards compat with code that imports the constant.
FLUX_MODEL_ID = FLUX_MODELS_TRIED[0]

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


def _make_placeholder_cover(out_path: Path, *, seed_hint: str = "") -> Path:
    """Last-resort cover: a stylized solid-color gradient with subtle
    noise. Same 1080x1080 dimensions as the Flux output so apply_title_
    overlay sees the same layout. Color is derived from seed_hint so
    repeated calls for the same run produce the same cover.

    The point is: a song MUST always produce a usable MP4 even when
    Kie's Flux service is down. The user already paid for Suno; we
    don't waste that spend on an unavailable upstream.
    """
    rng = random.Random(seed_hint or "song")
    # Two complementary cool tones — moonlit / cinematic palette.
    h = rng.randint(0, 360)
    def hsv_to_rgb(h_, s_, v_):
        import colorsys
        r, g, b = colorsys.hsv_to_rgb(h_ / 360.0, s_, v_)
        return (int(r * 255), int(g * 255), int(b * 255))
    top_color = hsv_to_rgb(h, 0.55, 0.22)
    bot_color = hsv_to_rgb((h + 30) % 360, 0.40, 0.08)

    canvas = Image.new("RGB", (_CANVAS, _CANVAS), color=top_color)
    px = canvas.load()
    for y in range(_CANVAS):
        t = y / (_CANVAS - 1)
        r = int(top_color[0] * (1 - t) + bot_color[0] * t)
        g = int(top_color[1] * (1 - t) + bot_color[1] * t)
        b = int(top_color[2] * (1 - t) + bot_color[2] * t)
        for x in range(_CANVAS):
            px[x, y] = (r, g, b)
    # Subtle grain
    grain = Image.effect_noise((_CANVAS, _CANVAS), 12).convert("L")
    canvas = Image.composite(canvas, canvas.point(lambda v: max(0, v - 6)), grain)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, format="PNG")
    return out_path


def generate_cover_image(
    *,
    client: KieClient,
    cover_prompt: str,
    out_dir: Path,
) -> Path:
    """Try Kie.ai Flux models in fallback order, then placeholder.

    Returns the path to cover_raw.png. Never raises — even total Flux
    outages produce a usable placeholder so the song run can complete.
    """
    full_prompt = (
        f"{cover_prompt}, professional album cover art, "
        f"art direction by Hipgnosis, cinematic lighting, "
        f"shallow depth of field, high detail, no text, no watermark, "
        f"square composition, leave space at top-right for title text"
    )
    out_path = out_dir / "cover_raw.png"

    last_err: Exception | None = None
    for model in FLUX_MODELS_TRIED:
        try:
            task_id = client.submit_flux_image_job(
                prompt=full_prompt,
                model=model,
                aspect_ratio="1:1",
            )
            url = client.wait_for_flux_image(
                task_id, poll_interval_s=5, timeout_s=180,
            )
            out_path.parent.mkdir(parents=True, exist_ok=True)
            client.download(url, out_path)
            return out_path
        except (KieError, TransientKieError) as e:
            print(f"[song_cover] {model} failed: {e}; trying next fallback")
            last_err = e
            continue

    # All Flux models failed — placeholder so the song still ships.
    print(
        f"[song_cover] all Flux fallbacks failed (last: {last_err}); "
        f"generating placeholder cover"
    )
    return _make_placeholder_cover(out_path, seed_hint=cover_prompt[:50])


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
    rgb = composed.convert("RGB")
    rgb.save(out_path, format="PNG")
    # Also write a small JPEG thumbnail so the song-list endpoint
    # can serve tiny previews instead of full 1080x1080 PNGs.
    # 256px JPEG @ q=80 is ~15-25 KB vs 1.2 MB for the source PNG.
    thumb = rgb.copy()
    thumb.thumbnail((256, 256), Image.LANCZOS)
    thumb.save(out_path.parent / "cover_thumb.jpg",
               format="JPEG", quality=80, optimize=True)


def generate_scene_images(
    *,
    client: KieClient,
    art_direction: str,
    scene_prompts: list[str],
    out_dir: Path,
    cover_fallback: Path,
) -> list[Path]:
    """Render the cinematic scene pool to out_dir/scenes/scene_NN.png.

    Style-lock v1: the shared `art_direction` is prepended to every
    scene prompt so the pool reads as one music video. Each image is
    independent; if Flux fails for a scene (after the model fallback in
    submit), that slot reuses a copy of `cover_fallback` so the render
    never loses a frame. Returns the ordered list of scene paths.
    """
    import shutil

    scenes_dir = out_dir / "scenes"
    scenes_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    for i, prompt in enumerate(scene_prompts, start=1):
        dest = scenes_dir / f"scene_{i:02d}.png"
        if dest.exists():           # resumable: skip already-rendered scenes
            paths.append(dest)
            continue
        full_prompt = (
            f"{art_direction}. {prompt}, cinematic lighting, shallow depth "
            f"of field, high detail, no text, no watermark, square composition"
        )
        rendered = False
        for model in FLUX_MODELS_TRIED:
            try:
                task_id = client.submit_flux_image_job(
                    prompt=full_prompt, model=model, aspect_ratio="1:1",
                )
                url = client.wait_for_flux_image(task_id, poll_interval_s=5, timeout_s=180)
                client.download(url, dest)
                rendered = True
                break
            except TransientKieError as e:
                # Transient: try next model in fallback chain.
                print(f"[song_cover] scene {i} {model} transient: {e}; next fallback")
                continue
            except KieError as e:
                # Permanent error: no point trying further models.
                print(f"[song_cover] scene {i} {model} permanent error: {e}; reusing cover")
                break
        if not rendered:
            print(f"[song_cover] scene {i} all Flux models failed; reusing cover")
            shutil.copyfile(cover_fallback, dest)
        paths.append(dest)

    return paths
