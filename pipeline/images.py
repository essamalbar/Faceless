"""Stage 5: image generation via Flux.1 dev (mflux on Apple Silicon)."""
from __future__ import annotations

from pathlib import Path

from pipeline.types import Shot

REROLL_SEED_BUMP = 10_000


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
    """Run mflux. Replaceable in tests via monkeypatch."""
    # mflux ≥ 0.4 API. Adjust if upstream API changes.
    from mflux import Config, Flux1, ModelConfig

    flux = Flux1(
        model_config=ModelConfig.from_alias("dev"),
        quantize=8,  # int8 quant; fits comfortably in 48GB unified memory and is faster
    )
    image = flux.generate_image(
        seed=seed,
        prompt=prompt,
        config=Config(
            num_inference_steps=steps,
            guidance=guidance,
            height=height,
            width=width,
        ),
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path=out_path, export_json_metadata=False)


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
