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
class Script:
    title: str
    theme: str
    global_setting: str
    music_mood: str
    hook: str
    story: str
    word_count: int

    def __post_init__(self):
        if self.music_mood not in VALID_MOODS:
            raise ValueError(f"invalid music_mood: {self.music_mood}")
        if self.theme not in VALID_THEMES:
            raise ValueError(f"invalid theme: {self.theme}")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Script":
        return cls(**d)


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
    def music_track_mp3(self) -> Path: return self.root / "music_track.mp3"
    @property
    def captions_srt(self) -> Path: return self.root / "captions.ar.srt"
    @property
    def captions_ass(self) -> Path: return self.root / "captions.ar.ass"
    @property
    def final_mp4(self) -> Path: return self.root / "final.mp4"
    @property
    def run_log(self) -> Path: return self.root / "run.log"
