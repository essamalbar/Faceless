"""Image generator tests. Flux is fully mocked."""
from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.images import generate_images
from pipeline.types import Shot


def _shots(n: int) -> list[Shot]:
    return [
        Shot(index=i + 1, start_ms=i * 1000, end_ms=(i + 1) * 1000,
             arabic_text="x", english_prompt=f"prompt {i+1}",
             negative_prompt="neg", seed=1000 + i)
        for i in range(n)
    ]


def _fake_flux(monkeypatch, fixtures_dir: Path):
    """Replace mflux call with a function that copies the pixel fixture."""
    sample = (fixtures_dir / "pixel.png").read_bytes()
    calls: list[dict] = []

    def fake_render(prompt, negative_prompt, seed, steps, guidance, width, height, out_path: Path):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(sample)
        calls.append({"prompt": prompt, "seed": seed, "out": str(out_path)})

    monkeypatch.setattr("pipeline.images._render_image", fake_render)
    return calls


def test_generates_all_images(monkeypatch, tmp_run_dir: Path, fixtures_dir: Path):
    calls = _fake_flux(monkeypatch, fixtures_dir)
    images_dir = tmp_run_dir / "images"
    generate_images(
        shots=_shots(3),
        images_dir=images_dir,
        steps=25, guidance=3.5, width=1280, height=720,
    )
    assert (images_dir / "01.png").exists()
    assert (images_dir / "02.png").exists()
    assert (images_dir / "03.png").exists()
    assert len(calls) == 3


def test_skips_existing_images(monkeypatch, tmp_run_dir: Path, fixtures_dir: Path):
    calls = _fake_flux(monkeypatch, fixtures_dir)
    images_dir = tmp_run_dir / "images"
    images_dir.mkdir()
    (images_dir / "01.png").write_bytes(b"existing")
    generate_images(
        shots=_shots(3), images_dir=images_dir,
        steps=25, guidance=3.5, width=1280, height=720,
    )
    # Only 02 and 03 should be re-rendered
    assert len(calls) == 2
    seeds = [c["seed"] for c in calls]
    assert 1000 not in seeds  # shot 1 was skipped


def test_reroll_regenerates_with_bumped_seed(monkeypatch, tmp_run_dir: Path, fixtures_dir: Path):
    calls = _fake_flux(monkeypatch, fixtures_dir)
    images_dir = tmp_run_dir / "images"
    images_dir.mkdir()
    (images_dir / "01.png").write_bytes(b"existing")
    (images_dir / "02.png").write_bytes(b"existing")
    (images_dir / "03.png").write_bytes(b"existing")
    generate_images(
        shots=_shots(3), images_dir=images_dir,
        steps=25, guidance=3.5, width=1280, height=720,
        reroll_indices=[2],
    )
    assert len(calls) == 1
    assert calls[0]["seed"] == 1001 + 10_000  # bumped from original seed (1001 for index 2)
