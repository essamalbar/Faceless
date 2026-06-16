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


class _SceneFakeClient:
    """Fake KieClient for scene-pool tests. Fails any scene whose prompt
    contains one of `fail_markers`, on EVERY model attempt, so the model
    fallback is exhausted and the cover fallback kicks in."""
    def __init__(self, fail_markers=()):
        self._fail_markers = list(fail_markers)
        self.submits = 0
        self._last_prompt = ""
    def submit_flux_image_job(self, *, prompt, model, aspect_ratio):
        self.submits += 1
        self._last_prompt = prompt
        return "task"
    def wait_for_flux_image(self, task_id, **kw):
        if any(m in self._last_prompt for m in self._fail_markers):
            from pipeline.kie import KieError
            raise KieError("boom")
        return "http://x/img.png"
    def download(self, url, out_path):
        from PIL import Image
        Image.new("RGB", (16, 16), "blue").save(out_path)


def _make_scene_cover(tmp_path):
    from PIL import Image
    p = tmp_path / "cover.png"
    Image.new("RGB", (16, 16), "red").save(p)
    return p


def test_generate_scene_images_writes_pool(tmp_path):
    import pipeline.song_cover as song_cover
    paths = song_cover.generate_scene_images(
        client=_SceneFakeClient(), art_direction="moonlit teal",
        scene_prompts=["alpha", "beta", "gamma"], out_dir=tmp_path,
        cover_fallback=_make_scene_cover(tmp_path),
    )
    assert [p.name for p in paths] == ["scene_01.png", "scene_02.png", "scene_03.png"]
    assert all(p.exists() for p in paths)


def test_failed_scene_falls_back_to_cover(tmp_path):
    import pipeline.song_cover as song_cover
    from PIL import Image
    cover = _make_scene_cover(tmp_path)
    # scene 2 ("beta") fails on EVERY model -> must fall back to a cover copy
    client = _SceneFakeClient(fail_markers=["beta"])
    paths = song_cover.generate_scene_images(
        client=client, art_direction="x", scene_prompts=["alpha", "beta", "gamma"],
        out_dir=tmp_path, cover_fallback=cover,
    )
    assert len(paths) == 3
    assert Image.open(paths[1]).getpixel((0, 0)) == Image.open(cover).getpixel((0, 0))
    # both Flux models were attempted for the failing scene before fallback:
    # alpha=1 submit, beta=2 (both models), gamma=1 -> 4 total
    assert client.submits == 4
