from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PIL import Image

from pipeline import song_cover


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_COVER = REPO_ROOT / "tests" / "fixtures" / "song" / "cover.png"


def test_generate_cover_image_calls_kie_flux_max(tmp_path: Path):
    """Verify we pass the correct model id and prompt to Kie.ai."""
    fake_url = "https://kie.ai/result.png"
    fake_client = MagicMock()
    fake_client.submit_flux_image_job = MagicMock(return_value="task-abc")
    fake_client.wait_for_flux_image = MagicMock(return_value=fake_url)
    def fake_download(url, out_path):
        Image.new("RGB", (1080, 1080), color="navy").save(out_path)
    fake_client.download = fake_download

    out_path = song_cover.generate_cover_image(
        client=fake_client,
        cover_prompt="young man under moonlight",
        out_dir=tmp_path,
    )
    assert out_path == tmp_path / "cover_raw.png"
    assert out_path.exists()

    submit_kwargs = fake_client.submit_flux_image_job.call_args.kwargs
    assert "Hipgnosis" in submit_kwargs["prompt"]
    assert "album cover" in submit_kwargs["prompt"].lower()
    assert "no text" in submit_kwargs["prompt"].lower()
    assert submit_kwargs["model"] == song_cover.FLUX_MODEL_ID
    assert submit_kwargs["aspect_ratio"] == "1:1"


def test_apply_title_overlay_arabic(tmp_path: Path):
    """Arabic title renders with Amiri and shows up as non-empty pixel diff."""
    out = tmp_path / "cover.png"
    song_cover.apply_title_overlay(
        raw_path=FIXTURE_COVER,
        title="تحت حراسة القمر",
        language="ar",
        out_path=out,
    )
    assert out.exists()
    raw_img = Image.open(FIXTURE_COVER).convert("RGB")
    out_img = Image.open(out).convert("RGB")
    assert raw_img.size == out_img.size == (1080, 1080)
    box = (540, 0, 1080, 540)  # top-right quadrant
    raw_crop = list(raw_img.crop(box).getdata())
    out_crop = list(out_img.crop(box).getdata())
    diff_pixels = sum(1 for a, b in zip(raw_crop, out_crop) if a != b)
    assert diff_pixels > 1000  # title text covers many pixels


def test_apply_title_overlay_latin(tmp_path: Path):
    out = tmp_path / "cover.png"
    song_cover.apply_title_overlay(
        raw_path=FIXTURE_COVER,
        title="Moonlit Vigil",
        language="en",
        out_path=out,
    )
    assert out.exists()
    out_img = Image.open(out).convert("RGB")
    assert out_img.size == (1080, 1080)


def test_apply_title_overlay_picks_font_by_language(tmp_path: Path):
    assert song_cover._font_path_for_language("ar").name == "Amiri-Regular.ttf"
    assert song_cover._font_path_for_language("he").name == "Amiri-Regular.ttf"
    assert song_cover._font_path_for_language("en").name == "Inter-Bold.ttf"
    assert song_cover._font_path_for_language("es").name == "Inter-Bold.ttf"
