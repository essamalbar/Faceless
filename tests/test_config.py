"""Config loader tests."""
from __future__ import annotations

import textwrap
from pathlib import Path

from pipeline.config import Config, load_config


def test_load_full_config(tmp_path: Path):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(textwrap.dedent("""
        voice:
          name: ar-SA-HamedNeural
          rate: -20%
          pitch: -5%
        script:
          word_count_target: 2200
          word_count_tolerance: 200
          enable_critique_pass: true
          repetition_threshold: 0.85
        flux:
          steps: 25
          guidance: 3.5
          width: 1280
          height: 720
        assemble:
          output_width: 1920
          output_height: 1080
          shot_crossfade_ms: 800
          music_duck_db: -18
          music_silence_db: -8
          fade_in_s: 3
          fade_out_s: 3
        captions:
          burn_in: false
          font: Cairo-Bold
          font_size: 60
        kie:
          model: veo-3.1-fast
          num_clips: 4
          clip_duration_s: 7
          aspect_ratio: "9:16"
          cost_per_second_usd: 0.10
          max_spend_usd: 3.50
          poll_interval_s: 5
          poll_timeout_s: 300
    """))
    cfg = load_config(cfg_path)
    assert cfg.voice.name == "ar-SA-HamedNeural"
    assert cfg.script.word_count_target == 2200
    assert cfg.flux.steps == 25
    assert cfg.assemble.shot_crossfade_ms == 800
    assert cfg.captions.burn_in is False
    assert cfg.kie.model == "veo-3.1-fast"
    assert cfg.kie.num_clips == 4
    assert cfg.kie.max_spend_usd == 3.50


def test_missing_file_raises(tmp_path: Path):
    import pytest
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "nope.yaml")


def test_default_config_yaml_loads():
    """The shipped config.yaml at repo root must load."""
    root = Path(__file__).parent.parent
    cfg = load_config(root / "config.yaml")
    assert isinstance(cfg, Config)
    # Voice depends on current style; just confirm a valid Edge TTS voice loads.
    assert cfg.voice.name.startswith("ar-")
