"""Stage X (Tier-3): Generate a single Flux character sheet for a video.

The caller is responsible for composing the lineup_prompt — this module
no longer has a hardcoded fruit-cast fallback. See run.py:_stage_character_sheet
for the standard composition (script.global_setting + unique character_names
+ pipeline.cast_guidance.flux_lineup_override).

Idempotent: skips Flux call if `out_path` already exists.
"""
from __future__ import annotations

import time
from pathlib import Path

from pipeline.kie import KieClient
from pipeline.types import is_complete_artifact

_SLEEP = time.sleep


def generate_character_sheet(
    client: KieClient,
    out_path: Path,
    *,
    lineup_prompt: str,
    model: str = "flux-kontext-pro",
    aspect_ratio: str = "1:1",
    poll_interval_s: int = 5,
    poll_timeout_s: int = 300,
) -> None:
    """Submit a Flux job for the character sheet, poll, download. Idempotent.

    `lineup_prompt`: required, non-empty. The caller builds it from the
    script's actual content (global_setting + character_names +
    cast_guidance). Empty / None raises ValueError — there is no
    hardcoded fallback after Phase A.

    `aspect_ratio` defaults to '1:1' (square — what Veo expects). Set to
    '9:16' when the downstream video model is Kling: Kling 2.1 inherits
    the input image's aspect ratio, so a square reference produces
    square video. A 9:16 reference produces 9:16 video matching our
    Shorts target."""
    if is_complete_artifact(out_path):
        return
    if not (lineup_prompt or "").strip():
        raise ValueError(
            "lineup_prompt is required and must be non-empty — "
            "the legacy CHARACTER_SHEET_PROMPT fallback was removed in PA-2"
        )
    job_id = client.submit_flux_image_job(
        prompt=lineup_prompt,
        model=model,
        aspect_ratio=aspect_ratio,
    )
    url = client.wait_for_flux_image(
        job_id, poll_interval_s=poll_interval_s, timeout_s=poll_timeout_s,
    )
    client.download(url, out_path)
