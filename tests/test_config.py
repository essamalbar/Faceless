"""Config loader tests."""
from __future__ import annotations

import textwrap
from pathlib import Path

from pipeline.config import Config, load_config


def test_load_full_config(tmp_path: Path):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(textwrap.dedent("""
        voice:
          provider: elevenlabs
          name: ar-EG-SalmaNeural
          rate: "+0%"
          pitch: "+0Hz"
          elevenlabs_voice_id: 21m00Tcm4TlvDq8ikWAM
          elevenlabs_model: eleven_multilingual_v2
          fallback_to_edge_tts: true
        script:
          word_count_target: 320
          word_count_tolerance: 60
          enable_critique_pass: true
          repetition_threshold: 0.85
          min_beats: 8
          max_beats: 15
          words_per_beat: 30
        flux:
          steps: 4
          guidance: 3.5
          width: 1280
          height: 720
        assemble:
          output_width: 1920
          output_height: 1080
          shot_crossfade_ms: 350
          music_duck_db: -18
          music_silence_db: -8
          fade_in_s: 1
          fade_out_s: 1
        captions:
          burn_in: false
          font: Cairo-Bold
          font_size: 60
        kie:
          model: veo3
          num_clips: 8
          clip_duration_s: 8
          aspect_ratio: "9:16"
          cost_per_second_usd: 0.40
          max_spend_usd: 50.00
          poll_interval_s: 5
          poll_timeout_s: 300
          flux_model: flux-1.1-pro
          flux_cost_per_image_usd: 0.05
    """))
    cfg = load_config(cfg_path)
    assert cfg.voice.provider == "elevenlabs"
    assert cfg.voice.elevenlabs_voice_id == "21m00Tcm4TlvDq8ikWAM"
    assert cfg.voice.fallback_to_edge_tts is True
    assert cfg.script.min_beats == 8
    assert cfg.script.max_beats == 15
    assert cfg.kie.model == "veo3"
    assert cfg.kie.flux_model == "flux-1.1-pro"
    assert cfg.kie.flux_cost_per_image_usd == 0.05
    assert cfg.kie.max_spend_usd == 50.00


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


def test_song_config_has_cinematic_fields():
    root = Path(__file__).parent.parent
    cfg = load_config(root / "config.yaml")
    assert cfg.song is not None
    assert cfg.song.cinematic_credits_per_song == 3
    assert cfg.song.cinematic_pool_size == 7
    assert cfg.song.bars_per_cut == 4


def test_song_config_cinematic_defaults_when_absent():
    # Old config blocks without the new keys must still load.
    from pipeline.config import SongConfig
    c = SongConfig(
        suno_model="V5_5", suno_cost_usd=0.05,
        cover_flux_model="flux-kontext-max", cover_cost_usd=0.03,
        credits_per_song=1,
    )
    assert c.cinematic_credits_per_song == 3
    assert c.cinematic_pool_size == 7
    assert c.bars_per_cut == 4


def test_song_config_ar_pipeline_defaults(tmp_path):
    from pipeline.config import load_config
    import textwrap
    cfg_path = tmp_path / "c.yaml"
    cfg_path.write_text(textwrap.dedent("""
      voice: {provider: edge_tts, name: x, rate: "+0%", pitch: "+0Hz"}
      script: {word_count_target: 100, word_count_tolerance: 20, enable_critique_pass: false, repetition_threshold: 0.8, min_beats: 4, max_beats: 8, words_per_beat: 20}
      flux: {steps: 4, guidance: 3.5, width: 1280, height: 720}
      assemble: {output_width: 1920, output_height: 1080, shot_crossfade_ms: 350, music_duck_db: -18, music_silence_db: -8, fade_in_s: 1, fade_out_s: 1}
      captions: {burn_in: false, font: X, font_size: 60}
      kie: {model: veo3_fast, num_clips: 5, clip_duration_s: 8, aspect_ratio: "9:16", cost_per_second_usd: 0.1, max_spend_usd: 13, poll_interval_s: 5, poll_timeout_s: 300, flux_model: x, flux_cost_per_image_usd: 0.05, native_audio: true}
      song: {suno_model: V5_5, suno_cost_usd: 0.05, cover_flux_model: x, cover_cost_usd: 0.03, credits_per_song: 1}
    """))
    c = load_config(cfg_path)
    # New A&R fields default without being present in the config block:
    assert c.song.quality_tier_default == "standard"
    assert c.song.best_of == 6
    assert c.song.quality_bar == 70
    assert c.song.regen_max_rounds == 1
    assert c.song.regen_extra_takes == 4
    assert c.song.max_takes == 10
    assert c.song.premium_credit_surcharge == 4
    assert c.song.ar_judge_enabled is False
    assert c.song.master_engine == "matchering"
