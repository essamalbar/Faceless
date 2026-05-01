"""Stage 5: image generation via Flux (mflux on Apple Silicon).

Default model: Flux.1-schnell (open license, no HuggingFace auth required, ~4 inference steps).
To switch to Flux.1-dev (higher quality, requires HF token + license acceptance):
  1. Visit https://huggingface.co/black-forest-labs/FLUX.1-dev and click "Agree".
  2. Generate an HF token at https://huggingface.co/settings/tokens.
  3. Run `huggingface-cli login` or set HF_TOKEN in .env.
  4. Change FLUX_MODEL_ALIAS below to "dev".
  5. Bump steps from ~4 to 25 in config.yaml for dev (schnell is optimized for 4 steps).
"""
from __future__ import annotations

from pathlib import Path

from pipeline.types import Shot

REROLL_SEED_BUMP = 10_000
FLUX_MODEL_ALIAS = "schnell"  # see header comment to switch to "dev"


def _render_image(
    prompt: str,
    negative_prompt: str,
    seed: int,
    steps: int,
    guidance: float,
    width: int,
    height: int,
    out_path: Path,
) -> None:
    """Run mflux. Replaceable in tests via monkeypatch.

    Tested against mflux 0.17.x. Keep the import path narrow so the rest of
    the codebase doesn't depend on mflux's deep module layout.
    """
    from mflux.models.flux.variants.txt2img.flux import Flux1

    flux = Flux1.from_name(FLUX_MODEL_ALIAS, quantize=8)
    image = flux.generate_image(
        seed=seed,
        prompt=prompt,
        num_inference_steps=steps,
        guidance=guidance,
        height=height,
        width=width,
        negative_prompt=negative_prompt or None,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path=out_path, export_json_metadata=False, overwrite=True)


def _shot_filename(images_dir: Path, index: int) -> Path:
    return images_dir / f"{index:02d}.png"


def generate_images(
    shots: list[Shot],
    images_dir: Path,
    steps: int,
    guidance: float,
    width: int,
    height: int,
    reroll_indices: list[int] | None = None,
) -> None:
    """Render each shot to images_dir/NN.png. Resumable.

    reroll_indices: 1-based shot indices to force regenerate; their seeds get bumped by REROLL_SEED_BUMP.
    """
    images_dir.mkdir(parents=True, exist_ok=True)
    reroll_set = set(reroll_indices or [])
    for shot in shots:
        out_path = _shot_filename(images_dir, shot.index)
        if out_path.exists() and shot.index not in reroll_set:
            continue
        seed = shot.seed + (REROLL_SEED_BUMP if shot.index in reroll_set else 0)
        _render_image(
            prompt=shot.english_prompt,
            negative_prompt=shot.negative_prompt,
            seed=seed,
            steps=steps,
            guidance=guidance,
            width=width,
            height=height,
            out_path=out_path,
        )
