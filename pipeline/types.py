"""Shared dataclasses for pipeline artifacts."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

MusicMood = Literal["drone", "dread", "cosmic", "discovery"]
ThemeTag = Literal[
    "domestic", "wilderness", "urban", "workplace",
    "travel", "folkloric", "tech", "memory",
]
VALID_MOODS = {"drone", "dread", "cosmic", "discovery"}
VALID_THEMES = {
    "domestic", "wilderness", "urban", "workplace",
    "travel", "folkloric", "tech", "memory",
}


@dataclass(frozen=True)
class ThemeSeed:
    theme: str
    premise: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ThemeSeed":
        return cls(**d)


@dataclass(frozen=True)
class Beat:
    """One narration beat ↔ one Veo clip in the Shorts pipeline."""
    arabic: str
    english_motion: str
    clip_duration_s: float = 8.0  # how long the matching Veo clip should run

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Beat":
        return cls(**d)


@dataclass(frozen=True)
class Script:
    """Script artifact for both pipeline modes.

    Long-form (slideshow): uses `story` + `hook` + `word_count`.
    Shorts: uses `beats` + `story_combined` (concatenated arabic for TTS).
    Both share title/theme/global_setting/music_mood metadata.
    """
    title: str
    theme: str
    global_setting: str
    music_mood: str
    # Long-form fields (optional in shorts mode)
    hook: str = ""
    story: str = ""
    word_count: int = 0
    # Shorts-mode fields (optional in long-form mode)
    beats: tuple[Beat, ...] = ()
    story_combined: str = ""
    target_duration_s: float = 0.0  # writer's chosen length (Tier-3 variable)

    def __post_init__(self):
        if self.music_mood not in VALID_MOODS:
            raise ValueError(f"invalid music_mood: {self.music_mood}")
        if self.theme not in VALID_THEMES:
            raise ValueError(f"invalid theme: {self.theme}")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Script":
        d = dict(d)
        beats_raw = d.pop("beats", None) or ()
        beats = tuple(Beat.from_dict(b) if isinstance(b, dict) else b for b in beats_raw)
        return cls(**d, beats=beats) if "beats" not in d else cls(**d)


@dataclass(frozen=True)
class WordTiming:
    word: str
    offset_ms: int
    duration_ms: int

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "WordTiming":
        return cls(**d)


@dataclass(frozen=True)
class Shot:
    index: int
    start_ms: int
    end_ms: int
    arabic_text: str
    english_prompt: str
    negative_prompt: str
    seed: int

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Shot":
        return cls(**d)


@dataclass(frozen=True)
class RunPaths:
    """All artifact paths for a single run."""
    root: Path

    @property
    def script_json(self) -> Path: return self.root / "script.json"
    @property
    def narration_mp3(self) -> Path: return self.root / "narration.mp3"
    @property
    def word_timings_json(self) -> Path: return self.root / "word_timings.json"
    @property
    def shots_json(self) -> Path: return self.root / "shots.json"
    @property
    def images_dir(self) -> Path: return self.root / "images"
    @property
    def clips_dir(self) -> Path: return self.root / "clips"
    @property
    def character_sheet_png(self) -> Path: return self.root / "character_sheet.png"
    @property
    def first_keyframe_png(self) -> Path: return self.root / "first_keyframe.png"
    @property
    def last_frames_dir(self) -> Path: return self.root / "last_frames"
    @property
    def kie_spend_json(self) -> Path: return self.root / "kie_spend.json"
    @property
    def music_track_mp3(self) -> Path: return self.root / "music_track.mp3"
    @property
    def captions_srt(self) -> Path: return self.root / "captions.ar.srt"
    @property
    def captions_ass(self) -> Path: return self.root / "captions.ar.ass"
    @property
    def final_mp4(self) -> Path: return self.root / "final.mp4"
    @property
    def run_log(self) -> Path: return self.root / "run.log"
