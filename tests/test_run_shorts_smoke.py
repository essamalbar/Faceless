"""End-to-end smoke test for the Shorts pipeline (--shorts mode).

All four external services are mocked:
  - Gemini  → returns a canned beats[] JSON
  - Edge TTS → writes a fixture mp3 + canned timings
  - Kie.ai  → submit/poll succeed; download writes mp4 magic bytes
  - FFmpeg  → captures args; writes stub mp4 to the output path

Verifies all 7 Shorts stages produce expected artifacts.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def music_bundle(tmp_path: Path) -> Path:
    bundle = tmp_path / "music_bundle"
    bundle.mkdir()
    (bundle / "dread-01.mp3").write_bytes(b"music")
    (bundle / "tracks.json").write_text(json.dumps([
        {"filename": "dread-01.mp3", "duration_s": 100, "mood": "dread",
         "license": "CC0", "source_url": "x", "attribution": None},
    ]))
    return bundle


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"


def test_run_shorts_full_pipeline(monkeypatch, tmp_path: Path, fixtures_dir: Path, music_bundle: Path):
    sample_mp3 = (fixtures_dir / "narration_sample.mp3").read_bytes()

    # ---- 1) Gemini fake — single call returns beats payload ----
    beats_payload = json.dumps({
        "title": "صدى البئر",
        "theme": "folkloric",
        "global_setting": "abandoned village, night, desert",
        "music_mood": "dread",
        "beats": [
            {"arabic": "كنتُ وحيداً عند البئر.",
             "english_motion": "lone hooded figure beside ancient well, slow push-in, moonlight"},
            {"arabic": "سمعتُ بكاءً في الأعماق.",
             "english_motion": "close-up of dark well shaft, mist rising, faint glow"},
            {"arabic": "ظهرتْ يدٌ عظمية.",
             "english_motion": "skeletal hand emerging from well rim, low angle, candlelight"},
            {"arabic": "ثم اختفى كل شيء.",
             "english_motion": "wide shot of empty village, fog rolling in, static camera"},
        ],
    }, ensure_ascii=False)

    class FakeGemini:
        def __init__(self):
            self.complete_calls: list = []
        def complete(self, prompt, system=None):
            self.complete_calls.append(prompt)
            return beats_payload
        def embed(self, text):
            return [0.0, 1.0]
    fake_g = FakeGemini()
    monkeypatch.setattr("run._build_gemini", lambda: fake_g)

    # ---- 2) Edge TTS fake ----
    def fake_synthesize(text, voice, rate, pitch, mp3_path):
        mp3_path.write_bytes(sample_mp3)
        return [
            {"word": "كنتُ", "offset_ms": 0, "duration_ms": 400},
            {"word": "وحيداً.", "offset_ms": 400, "duration_ms": 400},
        ]
    monkeypatch.setattr("pipeline.voice._synthesize", fake_synthesize)

    # ---- 3) Kie.ai fake — Kie client never actually constructed; we mock _build_kie ----
    class FakeKie:
        pass
    monkeypatch.setattr("run._build_kie", lambda: FakeKie())

    # And replace the high-level helper that video.py calls so no real HTTP hits the wire.
    def fake_generate_clip(client, prompt, model, duration_s, aspect_ratio, seed, out_path,
                          negative_prompt, poll_interval_s, timeout_s):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"\x00\x00\x00\x18ftypmp42")  # mp4 magic prefix
    monkeypatch.setattr("pipeline.video.generate_clip", fake_generate_clip)

    # ---- 4) FFmpeg fake — captures args; writes stub mp4 to last arg ----
    ffmpeg_calls: list[list[str]] = []
    def fake_ffmpeg(args):
        ffmpeg_calls.append(args)
        out = Path(args[-1])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"\x00\x00\x00\x18ftypmp42")
    monkeypatch.setattr("pipeline.assemble._run_ffmpeg", fake_ffmpeg)

    # ---- 5) Run orchestrator ----
    from run import main_with_args
    out_root = tmp_path / "out"
    config_path = Path(__file__).parent.parent / "config.yaml"

    code = main_with_args([
        "--shorts",
        "--theme", "folkloric",
        "--seed", "بئر قديم",
        "--out-root", str(out_root),
        "--music-bundle", str(music_bundle),
        "--config", str(config_path),
    ])
    assert code == 0

    # ---- 6) Verify artifacts ----
    runs = [p for p in out_root.iterdir() if p.is_dir()]
    assert len(runs) == 1
    run_dir = runs[0]

    # All 7 Shorts artifacts present
    assert (run_dir / "seed.json").exists()
    assert (run_dir / "script.json").exists()
    assert (run_dir / "narration.mp3").exists()
    assert (run_dir / "word_timings.json").exists()
    assert (run_dir / "clips").is_dir()
    # 4 clips → 4 mp4 files
    clip_files = sorted((run_dir / "clips").glob("*.mp4"))
    assert len(clip_files) == 4
    assert (run_dir / "kie_spend.json").exists()
    assert (run_dir / "music_track.mp3").exists()
    assert (run_dir / "captions.ar.srt").exists()
    assert (run_dir / "captions.ar.ass").exists()
    assert (run_dir / "final.mp4").exists()

    # Spec gate: TikTok captions are karaoke-style (\k tags) AND vertical (PlayResX 1080)
    ass = (run_dir / "captions.ar.ass").read_text(encoding="utf-8")
    assert "PlayResX: 1080" in ass
    assert "\\k" in ass

    # Script has beats[] populated, story_combined non-empty
    script = json.loads((run_dir / "script.json").read_text(encoding="utf-8"))
    assert len(script["beats"]) == 4
    assert script["story_combined"]

    # Spend log records 4 clips
    spend = json.loads((run_dir / "kie_spend.json").read_text(encoding="utf-8"))
    assert len(spend["entries"]) == 4

    # Single Gemini call (script writer only) — saves quota
    assert len(fake_g.complete_calls) == 1


def test_run_shorts_skip_video_uses_placeholder_clips(
    monkeypatch, tmp_path: Path, fixtures_dir: Path, music_bundle: Path,
):
    """--skip-video produces black mp4s via real ffmpeg (cheap path, no Kie.ai)."""
    sample_mp3 = (fixtures_dir / "narration_sample.mp3").read_bytes()

    beats_payload = json.dumps({
        "title": "x",
        "theme": "folkloric",
        "global_setting": "abandoned village",
        "music_mood": "dread",
        "beats": [
            {"arabic": "ج1", "english_motion": "m1"},
            {"arabic": "ج2", "english_motion": "m2"},
        ],
    }, ensure_ascii=False)

    class FakeGemini:
        def complete(self, prompt, system=None):
            return beats_payload
        def embed(self, text):
            return [0.0, 1.0]

    monkeypatch.setattr("run._build_gemini", lambda: FakeGemini())

    def fake_synthesize(text, voice, rate, pitch, mp3_path):
        mp3_path.write_bytes(sample_mp3)
        return [{"word": "ج", "offset_ms": 0, "duration_ms": 400}]
    monkeypatch.setattr("pipeline.voice._synthesize", fake_synthesize)
    # Kie should NEVER be constructed in --skip-video; if it is, fail loud.
    def boom():
        raise AssertionError("KieClient must not be constructed in --skip-video")
    monkeypatch.setattr("run._build_kie", boom)
    # Mock the assembler ffmpeg call only (placeholder clip generation uses real ffmpeg).
    monkeypatch.setattr("pipeline.assemble._run_ffmpeg",
                        lambda args: Path(args[-1]).write_bytes(b"\x00\x00\x00\x18ftypmp42"))

    from run import main_with_args
    out_root = tmp_path / "out"
    config_path = Path(__file__).parent.parent / "config.yaml"

    code = main_with_args([
        "--shorts", "--skip-video",
        "--theme", "folkloric", "--seed", "بئر",
        "--out-root", str(out_root),
        "--music-bundle", str(music_bundle),
        "--config", str(config_path),
    ])
    assert code == 0
    runs = [p for p in out_root.iterdir() if p.is_dir()]
    run_dir = runs[0]
    assert (run_dir / "clips" / "01.mp4").exists()
    assert (run_dir / "clips" / "02.mp4").exists()
    assert (run_dir / "final.mp4").exists()
