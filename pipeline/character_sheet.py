"""Stage X (Tier-3): Generate a single Flux character sheet for a video.

The sheet is a 1024×1024 image showing all the named anthropomorphic fruit
characters (lemon mother, strawberry son child + adult, apple doctor, etc.)
together. It's then passed via `imageUrls` as a reference to every Veo clip
to anchor character appearance across all clips.

Idempotent: skips Flux call if `out_path` already exists.
"""
from __future__ import annotations

import time
from pathlib import Path

from pipeline.kie import KieClient

_SLEEP = time.sleep

CHARACTER_SHEET_PROMPT = (
    "Character lineup sheet for a tragic Arabic family-drama animated short. "
    "Five anthropomorphic fruit characters standing side by side, full body, "
    "facing camera, neutral expressions, plain warm-grey background, "
    "consistent 3D Pixar-style rendering, photorealistic CGI textures: "
    "(1) Lemon mother — yellow lemon-shaped head with sad eyes, wearing a black hijab and dark dress; "
    "(2) Strawberry child — small red strawberry head with green leaves on top, wearing blue t-shirt and jeans; "
    "(3) Strawberry adult son — same red strawberry head but with a beard, wearing a traditional thobe; "
    "(4) Apple doctor — red apple head, white doctor coat, stethoscope; "
    "(5) Mango neighbor — orange mango head, casual button-up shirt. "
    "High detail, consistent shading, design-sheet aesthetic. NO text, NO watermark, NO logo."
)


def generate_character_sheet(
    client: KieClient,
    out_path: Path,
    global_setting: str,
    model: str = "flux-kontext-pro",
    poll_interval_s: int = 5,
    poll_timeout_s: int = 300,
) -> None:
    """Submit a Flux job for the character sheet, poll, download to out_path. Idempotent."""
    if out_path.exists():
        return
    job_id = client.submit_flux_image_job(
        prompt=CHARACTER_SHEET_PROMPT,
        model=model,
        aspect_ratio="1:1",
    )
    url = client.wait_for_flux_image(
        job_id, poll_interval_s=poll_interval_s, timeout_s=poll_timeout_s,
    )
    client.download(url, out_path)
