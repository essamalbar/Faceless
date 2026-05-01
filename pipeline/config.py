"""Config loader. Maps config.yaml into typed dataclasses."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class VoiceConfig:
    name: str
    rate: str
    pitch: str


@dataclass(frozen=True)
class ScriptConfig:
    word_count_target: int
    word_count_tolerance: int
    enable_critique_pass: bool
    repetition_threshold: float


@dataclass(frozen=True)
class FluxConfig:
    steps: int
    guidance: float
    width: int
    height: int


@dataclass(frozen=True)
class AssembleConfig:
    output_width: int
    output_height: int
    shot_crossfade_ms: int
    music_duck_db: int
    music_silence_db: int
    fade_in_s: int
    fade_out_s: int


@dataclass(frozen=True)
class CaptionsConfig:
    burn_in: bool
    font: str
    font_size: int


@dataclass(frozen=True)
class KieConfig:
    """Kie.ai video-generation config (used by --shorts mode)."""
    model: str                  # e.g. "veo-3.1-fast"
    num_clips: int              # how many clips per Shorts video (default 4)
    clip_duration_s: int        # seconds per clip (default 7 → ~28s total)
    aspect_ratio: str           # e.g. "9:16"
    cost_per_second_usd: float  # used for budget guard estimation
    max_spend_usd: float        # hard cap per video; orchestrator refuses runs exceeding
    poll_interval_s: int        # seconds between job-status polls
    poll_timeout_s: int         # give up on a single clip after this many seconds


@dataclass(frozen=True)
class Config:
    voice: VoiceConfig
    script: ScriptConfig
    flux: FluxConfig
    assemble: AssembleConfig
    captions: CaptionsConfig
    kie: KieConfig


def load_config(path: Path) -> Config:
    if not path.exists():
        raise FileNotFoundError(f"config not found: {path}")
    with path.open() as f:
        raw = yaml.safe_load(f)
    return Config(
        voice=VoiceConfig(**raw["voice"]),
        script=ScriptConfig(**raw["script"]),
        flux=FluxConfig(**raw["flux"]),
        assemble=AssembleConfig(**raw["assemble"]),
        captions=CaptionsConfig(**raw["captions"]),
        kie=KieConfig(**raw["kie"]),
    )
