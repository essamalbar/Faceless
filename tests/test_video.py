"""Video clip generator tests. Kie.ai is replaced via monkeypatch."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline import video as video_mod
from pipeline.kie import KieClient
from pipeline.types import Beat, Script
from pipeline.video import (
    BudgetExceededError,
    REROLL_SEED_BUMP,
    build_veo_prompt,
    clip_seed,
    estimate_spend_usd,
    generate_clips,
)


def _script(num_beats: int = 4) -> Script:
    return Script(
        title="بئر",
        theme="folkloric",
        global_setting="abandoned village, night, desert",
        music_mood="dread",
        beats=tuple(
            Beat(arabic=f"ج{i+1}", english_motion=f"motion{i+1}, push-in")
            for i in range(num_beats)
        ),
        story_combined=" ".join(f"ج{i+1}" for i in range(num_beats)),
    )


def _client() -> KieClient:
    return KieClient(api_key="k", base_url="https://api.kie.ai")


def _patch_generate_clip(monkeypatch, fixtures_dir: Path):
    """Replace pipeline.video.generate_clip with a stub that writes a tiny mp4."""
    sample = (fixtures_dir / "narration_sample.mp3").read_bytes()  # any small file
    calls: list[dict] = []

    def fake(client, prompt, model, duration_s, aspect_ratio, seed, out_path,
             negative_prompt, poll_interval_s, timeout_s):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"\x00\x00\x00\x18ftypmp42")  # mp4 magic prefix
        calls.append({
            "prompt": prompt, "model": model, "seed": seed,
            "duration_s": duration_s, "aspect_ratio": aspect_ratio,
            "out_path": str(out_path),
        })

    monkeypatch.setattr(video_mod, "generate_clip", fake)
    return calls


def test_estimate_spend_math():
    assert estimate_spend_usd(4, 7, 0.10) == pytest.approx(2.80)
    assert estimate_spend_usd(0, 7, 0.10) == 0
    assert estimate_spend_usd(4, 8, 0.50) == 16.0


def test_clip_seed_deterministic_per_title():
    s1 = clip_seed("title-A", 0)
    s2 = clip_seed("title-A", 0)
    s3 = clip_seed("title-A", 1)
    s4 = clip_seed("title-B", 0)
    assert s1 == s2
    assert s1 != s3
    assert s1 != s4


def test_build_veo_prompt_combines_setting_and_motion():
    b = Beat(arabic="x", english_motion="lone hooded figure, moonlight")
    p = build_veo_prompt(b, global_setting="abandoned village at night")
    assert "abandoned village at night" in p
    assert "lone hooded figure" in p
    # Style suffix appended
    assert "vertical cinematic horror" in p


def test_generate_all_clips(monkeypatch, tmp_path: Path, fixtures_dir: Path):
    calls = _patch_generate_clip(monkeypatch, fixtures_dir)
    clips_dir = tmp_path / "clips"
    spend = tmp_path / "kie_spend.json"
    generate_clips(
        client=_client(), script=_script(4),
        clips_dir=clips_dir, spend_log_path=spend,
        model="veo-3.1-fast", clip_duration_s=7, aspect_ratio="9:16",
        cost_per_second_usd=0.10, max_spend_usd=5.0,
        poll_interval_s=1, poll_timeout_s=10,
    )
    for i in range(1, 5):
        assert (clips_dir / f"{i:02d}.mp4").exists()
    assert len(calls) == 4
    # Spend log records 4 entries × 7s × $0.10 = $2.80 total
    spend_data = json.loads(spend.read_text())
    assert len(spend_data["entries"]) == 4
    total = sum(e["cost_usd"] for e in spend_data["entries"])
    assert total == pytest.approx(2.80)


def test_skips_existing_clips(monkeypatch, tmp_path: Path, fixtures_dir: Path):
    calls = _patch_generate_clip(monkeypatch, fixtures_dir)
    clips_dir = tmp_path / "clips"
    clips_dir.mkdir()
    (clips_dir / "01.mp4").write_bytes(b"existing")
    (clips_dir / "02.mp4").write_bytes(b"existing")
    generate_clips(
        client=_client(), script=_script(4),
        clips_dir=clips_dir, spend_log_path=tmp_path / "spend.json",
        model="m", clip_duration_s=7, aspect_ratio="9:16",
        cost_per_second_usd=0.10, max_spend_usd=5.0,
        poll_interval_s=1, poll_timeout_s=10,
    )
    # Only 03 and 04 should be (re)generated
    assert len(calls) == 2


def test_reroll_regenerates_with_bumped_seed(monkeypatch, tmp_path: Path, fixtures_dir: Path):
    calls = _patch_generate_clip(monkeypatch, fixtures_dir)
    clips_dir = tmp_path / "clips"
    clips_dir.mkdir()
    for i in range(1, 5):
        (clips_dir / f"{i:02d}.mp4").write_bytes(b"existing")

    generate_clips(
        client=_client(), script=_script(4),
        clips_dir=clips_dir, spend_log_path=tmp_path / "spend.json",
        model="m", clip_duration_s=7, aspect_ratio="9:16",
        cost_per_second_usd=0.10, max_spend_usd=5.0,
        poll_interval_s=1, poll_timeout_s=10,
        reroll_indices=[2],
    )
    assert len(calls) == 1
    # Rerolled seed should be the original seed + REROLL_SEED_BUMP
    expected = clip_seed(_script().title, 1) + REROLL_SEED_BUMP  # 0-based index 1 = clip 2
    assert calls[0]["seed"] == expected


def test_budget_guard_refuses_when_over_cap(monkeypatch, tmp_path: Path, fixtures_dir: Path):
    _patch_generate_clip(monkeypatch, fixtures_dir)
    clips_dir = tmp_path / "clips"
    # 4 clips × 7s × $0.50 = $14 > $5 cap → must raise BEFORE any API call
    with pytest.raises(BudgetExceededError, match=r"projected spend \$14"):
        generate_clips(
            client=_client(), script=_script(4),
            clips_dir=clips_dir, spend_log_path=tmp_path / "spend.json",
            model="m", clip_duration_s=7, aspect_ratio="9:16",
            cost_per_second_usd=0.50, max_spend_usd=5.0,
            poll_interval_s=1, poll_timeout_s=10,
        )


def test_budget_guard_uses_only_pending_clips(monkeypatch, tmp_path: Path, fixtures_dir: Path):
    """Budget projects spend for clips that actually need (re)generation, not all clips."""
    _patch_generate_clip(monkeypatch, fixtures_dir)
    clips_dir = tmp_path / "clips"
    clips_dir.mkdir()
    # 3 of 4 clips already done — only 1 will be generated → $0.70 < cap
    for i in (1, 2, 3):
        (clips_dir / f"{i:02d}.mp4").write_bytes(b"existing")
    generate_clips(
        client=_client(), script=_script(4),
        clips_dir=clips_dir, spend_log_path=tmp_path / "spend.json",
        model="m", clip_duration_s=7, aspect_ratio="9:16",
        cost_per_second_usd=0.10, max_spend_usd=1.0,  # 1 clip = $0.70 ok
        poll_interval_s=1, poll_timeout_s=10,
    )


def test_raises_on_empty_beats(tmp_path: Path):
    s = Script(
        title="x", theme="folkloric", global_setting="x",
        music_mood="dread", beats=(),
    )
    with pytest.raises(ValueError, match="no beats"):
        generate_clips(
            client=_client(), script=s,
            clips_dir=tmp_path / "clips", spend_log_path=tmp_path / "s.json",
            model="m", clip_duration_s=7, aspect_ratio="9:16",
            cost_per_second_usd=0.10, max_spend_usd=5.0,
            poll_interval_s=1, poll_timeout_s=10,
        )
