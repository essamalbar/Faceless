"""Config loader. Maps config.yaml into typed dataclasses."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class VoiceConfig:
    provider: str = "edge_tts"          # "edge_tts" | "elevenlabs"
    name: str = "ar-EG-SalmaNeural"     # Edge TTS voice name (legacy field)
    rate: str = "+0%"
    pitch: str = "+0Hz"
    # ElevenLabs-specific
    elevenlabs_voice_id: str = ""
    elevenlabs_model: str = "eleven_multilingual_v2"
    fallback_to_edge_tts: bool = True
    # Per-character voice IDs. Keys are speaker labels emitted by the writer
    # (e.g. "mother", "son", "father", "doctor", "narrator"); values are
    # ElevenLabs voice IDs. Unknown speakers fall back to elevenlabs_voice_id.
    character_voices: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ScriptConfig:
    word_count_target: int
    word_count_tolerance: int
    enable_critique_pass: bool
    repetition_threshold: float
    # Tier-3 variable-length beats
    min_beats: int = 8
    max_beats: int = 15
    words_per_beat: int = 30


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
    model: str                  # e.g. "veo3"
    num_clips: int              # legacy / fallback default; writer picks per-story
    clip_duration_s: int        # seconds per clip
    aspect_ratio: str           # e.g. "9:16"
    cost_per_second_usd: float  # used for budget guard estimation
    max_spend_usd: float        # hard cap per video; orchestrator refuses runs exceeding
    poll_interval_s: int        # seconds between job-status polls
    poll_timeout_s: int         # give up on a single clip after this many seconds
    # Tier-3 Flux character sheet
    flux_model: str = "flux-1.1-pro"
    flux_cost_per_image_usd: float = 0.05
    # Tier-4 native dialogue: when true, the Veo prompt embeds each beat's
    # Arabic line so the character speaks it on-camera (lip-synced). The
    # ElevenLabs voice stage is skipped — Veo generates the audio. We lose
    # voice-ID control but gain real lip sync at no extra cost.
    native_audio: bool = True


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
