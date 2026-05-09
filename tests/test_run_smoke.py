"""End-to-end smoke test: runs the orchestrator with all externals mocked."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from pipeline.types import Script, Shot, ThemeSeed, WordTiming


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


def test_run_full_pipeline_with_all_externals_mocked(
    monkeypatch, tmp_path: Path, fixtures_dir: Path, music_bundle: Path,
):
    """All external services replaced; full pipeline runs and writes final.mp4."""
    sample_mp3 = (fixtures_dir / "narration_sample.mp3").read_bytes()
    pixel_png = (fixtures_dir / "pixel.png").read_bytes()

    # 1) Gemini fake — multi-call sequencer.
    # Manual seed is used (--theme + --seed), so no auto_seed gemini call.
    # Calls in order: script first pass, critique pass, then one prompt-translation
    # call per shot chunk. Default critique is enabled in shipped config.yaml.
    script_payload = json.dumps({
        "title": "بئر",
        "theme": "folkloric",
        "global_setting": "abandoned village, night",
        "music_mood": "dread",
        "hook": "افتتاح. سلام.",
        "story": "افتتاح. سلام.\n\nشيء غريب. ثم آخر. والنهاية.",
        "word_count": 12,
    }, ensure_ascii=False)

    gemini_responses = iter([
        script_payload,                # script first pass
        script_payload,                # critique pass (returns same)
        "lone figure on a dune",       # shot prompt 1
        "lone figure on a dune",       # spare (in case word timings yield 2 chunks)
        "lone figure on a dune",       # spare
    ])

    class Fake:
        def __init__(self):
            self.complete_calls: list = []
        def complete(self, prompt, system=None):
            self.complete_calls.append(prompt)
            try:
                return next(gemini_responses)
            except StopIteration:
                return "lone figure on a dune"
        def embed(self, text):
            return [0.0, 0.0, 1.0]  # always unique vs empty history

    fake = Fake()
    monkeypatch.setattr("run._build_gemini", lambda: fake)

    # 2) Edge TTS fake.
    def fake_synthesize(text, voice, rate, pitch, mp3_path):
        mp3_path.write_bytes(sample_mp3)
        return [
            {"word": "افتتاح.", "offset_ms": 0, "duration_ms": 800},
            {"word": "سلام.", "offset_ms": 900, "duration_ms": 600},
            {"word": "شيء", "offset_ms": 1600, "duration_ms": 400},
            {"word": "غريب.", "offset_ms": 2100, "duration_ms": 600},
            {"word": "والنهاية.", "offset_ms": 2800, "duration_ms": 700},
        ]
    monkeypatch.setattr("pipeline.voice._synthesize", fake_synthesize)

    # 3) Flux fake.
    def fake_render(prompt, negative_prompt, seed, steps, guidance, width, height, out_path):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(pixel_png)
    monkeypatch.setattr("pipeline.images._render_image", fake_render)

    # 4) FFmpeg fake — write a tiny mp4 stub.
    def fake_ffmpeg(args):
        out = Path(args[-1])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"\x00\x00\x00\x18ftypmp42")  # MP4 magic prefix
    monkeypatch.setattr("pipeline.assemble._run_ffmpeg", fake_ffmpeg)

    # 5) Run orchestrator
    from run import main_with_args
    out_root = tmp_path / "out"
    config_path = Path(__file__).parent.parent / "config.yaml"
    code = main_with_args([
        "--theme", "folkloric",
        "--seed", "بئر قديم",
        "--out-root", str(out_root),
        "--music-bundle", str(music_bundle),
        "--config", str(config_path),
    ])
    assert code == 0
    # Default --user-id is "admin", so runs land under out_root/admin/<ts>/.
    user_root = out_root / "admin"
    assert user_root.is_dir()
    runs = [p for p in user_root.iterdir() if p.is_dir()]
    assert len(runs) == 1
    run_dir = runs[0]
    assert (run_dir / "script.json").exists()
    assert (run_dir / "narration.mp3").exists()
    assert (run_dir / "word_timings.json").exists()
    assert (run_dir / "shots.json").exists()
    assert (run_dir / "images").is_dir()
    assert (run_dir / "captions.ar.srt").exists()
    assert (run_dir / "music_track.mp3").exists()
    assert (run_dir / "final.mp4").exists()
