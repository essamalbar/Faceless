# Arabic Horror Faceless System — MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI on macOS Apple Silicon (M3 Pro 48GB) that produces one finished Arabic horror video per invocation, end-to-end through 8 disk-checkpointed pipeline stages.

**Architecture:** Single Python package `pipeline/` with one module per pipeline stage plus shared infrastructure (`llm.py`, `runlog.py`, `config.py`, `types.py`). Top-level `run.py` is a thin orchestrator. Each stage reads from / writes to a per-run directory `out/<timestamp>/` so reruns resume from the last successful artifact. All external services (Gemini, Edge TTS, Flux/mflux, FFmpeg) are accessed through narrow interfaces so tests can replace them with fakes.

**Tech Stack:** Python 3.11+, `uv` for env/deps, `pytest` for tests, `google-genai` (Gemini), `edge-tts`, `mflux` (Flux.1 dev on Apple Silicon), `ffmpeg-python`, `pyyaml`, `Pillow`, `pydub`.

**Reference spec:** `docs/superpowers/specs/2026-05-01-arabic-horror-faceless-system-design.md` — read it before starting any task.

---

## File Structure

```
faceless/                              # repo root (existing Flutter project)
├── pipeline/                          # NEW — Python package (does NOT collide with Flutter's lib/)
│   ├── __init__.py
│   ├── types.py                       # shared dataclasses
│   ├── config.py                      # config.yaml loader
│   ├── runlog.py                      # per-run structured logger
│   ├── llm.py                         # Gemini wrapper (chat + embeddings)
│   ├── seed.py                        # Stage 1
│   ├── script.py                      # Stage 2
│   ├── voice.py                       # Stage 3
│   ├── shots.py                       # Stage 4
│   ├── images.py                      # Stage 5
│   ├── music.py                       # Stage 6
│   ├── captions.py                    # Stage 7
│   └── assemble.py                    # Stage 8
├── tests/                             # NEW
│   ├── __init__.py
│   ├── conftest.py                    # shared fakes (Gemini / EdgeTTS / mflux / FFmpeg) + fixtures
│   ├── fixtures/
│   │   ├── word_timings_sample.json
│   │   ├── narration_sample.mp3       # 5-second silent mp3 fixture
│   │   └── pixel.png                  # 1×1 placeholder image
│   ├── test_types.py
│   ├── test_config.py
│   ├── test_runlog.py
│   ├── test_llm.py
│   ├── test_seed.py
│   ├── test_script.py
│   ├── test_voice.py
│   ├── test_shots.py
│   ├── test_images.py
│   ├── test_music.py
│   ├── test_captions.py
│   ├── test_assemble.py
│   └── test_run_smoke.py              # end-to-end with all externals mocked
├── assets/                            # NEW
│   ├── music/                         # populated by scripts/setup_music.sh
│   │   └── tracks.json                # bundle metadata
│   └── fonts/
│       └── Cairo-Bold.ttf
├── scripts/                           # NEW
│   └── setup_music.sh
├── out/                               # NEW — gitignored runtime artifacts
├── pyproject.toml                     # NEW
├── config.yaml                        # NEW
├── run.py                             # NEW — CLI orchestrator
├── .gitignore                         # MODIFY — add Python ignores + out/
├── CLAUDE.md                          # MODIFY — add Python pipeline section
└── (existing Flutter app — lib/, android/, ios/, web/, macos/, linux/, windows/, pubspec.yaml — UNTOUCHED)
```

---

## Conventions for every task

- **Always TDD:** failing test first, then implementation, then verify pass, then commit.
- **Pytest is the only test runner.** Run from repo root: `uv run pytest <path> -v`.
- **No real API/network calls in tests.** Use fakes from `tests/conftest.py`.
- **Commit after each task** (every task ends with a `git commit` step). Use conventional-commit prefixes: `feat:`, `test:`, `chore:`, `refactor:`.
- **Type-hint everything.** Use `from __future__ import annotations` at the top of every Python file.
- **Use `pathlib.Path` for all paths.** Never use `os.path`.
- **Imports are absolute from the package root:** `from pipeline.script import ...`, never relative.

---

## Task 0: Initialize git repository

The working directory is not currently a git repo. Initialize it before any commits.

**Files:**
- Create: `.gitignore`

- [ ] **Step 1: Initialize git**

```bash
cd /Users/gileshannah/Desktop/faceless
git init -b main
```

- [ ] **Step 2: Create `.gitignore`**

Create `.gitignore` with this exact content:

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
.venv/
.uv/
*.egg-info/
.pytest_cache/
.mypy_cache/
.ruff_cache/

# Runtime artifacts
out/
*.log

# Generated content history
story_history.jsonl
theme_log.json

# Local secrets
.env
*.local

# Existing Flutter ignores (mirrors typical Flutter .gitignore — keep additive)
.dart_tool/
.flutter-plugins
.flutter-plugins-dependencies
.packages
build/

# macOS
.DS_Store

# IDE
.idea/
.vscode/
*.iml

# Claude Code session state
.claude/
```

- [ ] **Step 3: First commit (capture existing Flutter scaffold + spec)**

```bash
git add -A
git commit -m "chore: initial commit — flutter scaffold + brainstorm spec"
```

Expected: commit succeeds with files `pubspec.yaml`, `lib/main.dart`, `docs/superpowers/specs/...`, `CLAUDE.md`, `.gitignore`, etc.

---

## Task 1: Project scaffolding (pyproject + dirs + first failing test)

Set up the Python toolchain with `uv`, create the package skeleton, and confirm `pytest` runs.

**Files:**
- Create: `pyproject.toml`
- Create: `pipeline/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/test_smoke.py`

- [ ] **Step 1: Verify `uv` is installed**

```bash
uv --version
```

Expected: prints a version string. If missing: `brew install uv` first.

- [ ] **Step 2: Create `pyproject.toml`**

```toml
[project]
name = "faceless-pipeline"
version = "0.1.0"
description = "Arabic horror faceless YouTube CLI"
requires-python = ">=3.11"
dependencies = [
    "google-genai>=0.3.0",
    "edge-tts>=6.1.0",
    "mflux>=0.4.0",
    "ffmpeg-python>=0.2.0",
    "pyyaml>=6.0",
    "Pillow>=10.0",
    "pydub>=0.25",
    "click>=8.1",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-mock>=3.12",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra --strict-markers"
pythonpath = ["."]

[tool.uv]
package = false
```

- [ ] **Step 3: Create empty package marker files**

```bash
mkdir -p pipeline tests tests/fixtures assets/music assets/fonts scripts out
echo "" > pipeline/__init__.py
echo "" > tests/__init__.py
```

- [ ] **Step 4: Create `tests/conftest.py` (placeholder — fakes added in later tasks)**

```python
"""Shared pytest fixtures and fakes for pipeline tests."""
from __future__ import annotations

import pytest
from pathlib import Path


@pytest.fixture
def tmp_run_dir(tmp_path: Path) -> Path:
    """A temporary per-run output directory."""
    run_dir = tmp_path / "run-test"
    run_dir.mkdir()
    return run_dir


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"
```

- [ ] **Step 5: Write smoke test (the failing test)**

Create `tests/test_smoke.py`:

```python
"""Confirms test infrastructure is wired up."""
from __future__ import annotations


def test_pytest_runs():
    assert 1 + 1 == 2


def test_package_importable():
    import pipeline  # noqa: F401
```

- [ ] **Step 6: Install deps and run tests**

```bash
uv sync
uv run pytest tests/test_smoke.py -v
```

Expected: 2 passed.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml uv.lock pipeline/ tests/ assets/ scripts/
git commit -m "chore: scaffold Python pipeline project (uv + pytest)"
```

---

## Task 2: Shared types (pipeline/types.py)

Define the dataclasses that flow between stages. Every artifact written to disk corresponds to one of these.

**Files:**
- Create: `pipeline/types.py`
- Create: `tests/test_types.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_types.py`:

```python
"""Round-trip serialization tests for shared dataclasses."""
from __future__ import annotations

import json

from pipeline.types import Script, Shot, ThemeSeed, WordTiming


def test_themeseed_roundtrip():
    s = ThemeSeed(theme="folkloric", premise="بئر قديم في قرية مهجورة")
    assert s.to_dict() == {"theme": "folkloric", "premise": "بئر قديم في قرية مهجورة"}
    assert ThemeSeed.from_dict(s.to_dict()) == s


def test_script_roundtrip():
    s = Script(
        title="صوت الجار",
        theme="domestic",
        global_setting="apartment, urban Saudi Arabia, winter night",
        music_mood="dread",
        hook="الفقرة الافتتاحية",
        story="النص الكامل",
        word_count=2187,
    )
    data = s.to_dict()
    assert json.dumps(data, ensure_ascii=False)  # serializable
    assert Script.from_dict(data) == s


def test_shot_roundtrip():
    s = Shot(
        index=1,
        start_ms=0,
        end_ms=18420,
        arabic_text="كنت أسير...",
        english_prompt="lone figure walking...",
        negative_prompt="text, watermark",
        seed=1729384721,
    )
    assert Shot.from_dict(s.to_dict()) == s


def test_wordtiming_roundtrip():
    w = WordTiming(word="كنت", offset_ms=0, duration_ms=480)
    assert WordTiming.from_dict(w.to_dict()) == w


def test_script_invalid_mood_rejected():
    import pytest
    with pytest.raises(ValueError):
        Script(
            title="t", theme="domestic", global_setting="x",
            music_mood="not-a-mood", hook="h", story="s", word_count=100,
        )
```

- [ ] **Step 2: Run, verify failure**

```bash
uv run pytest tests/test_types.py -v
```

Expected: ImportError — `pipeline.types` does not exist.

- [ ] **Step 3: Implement `pipeline/types.py`**

```python
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
```

- [ ] **Step 4: Run tests, verify pass**

```bash
uv run pytest tests/test_types.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline/types.py tests/test_types.py
git commit -m "feat(types): shared dataclasses for pipeline artifacts"
```

---

## Task 3: Config loader (pipeline/config.py + config.yaml)

Load `config.yaml` into a typed `Config` object with sensible defaults.

**Files:**
- Create: `pipeline/config.py`
- Create: `config.yaml`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_config.py`:

```python
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
    """))
    cfg = load_config(cfg_path)
    assert cfg.voice.name == "ar-SA-HamedNeural"
    assert cfg.script.word_count_target == 2200
    assert cfg.flux.steps == 25
    assert cfg.assemble.shot_crossfade_ms == 800
    assert cfg.captions.burn_in is False


def test_missing_file_raises(tmp_path: Path):
    import pytest
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "nope.yaml")


def test_default_config_yaml_loads():
    """The shipped config.yaml at repo root must load."""
    root = Path(__file__).parent.parent
    cfg = load_config(root / "config.yaml")
    assert isinstance(cfg, Config)
    assert cfg.voice.name == "ar-SA-HamedNeural"
```

- [ ] **Step 2: Run, verify failure**

```bash
uv run pytest tests/test_config.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `pipeline/config.py`**

```python
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
class Config:
    voice: VoiceConfig
    script: ScriptConfig
    flux: FluxConfig
    assemble: AssembleConfig
    captions: CaptionsConfig


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
    )
```

- [ ] **Step 4: Create the shipped `config.yaml` at repo root**

```yaml
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
```

- [ ] **Step 5: Run tests, verify pass**

```bash
uv run pytest tests/test_config.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add pipeline/config.py config.yaml tests/test_config.py
git commit -m "feat(config): typed config.yaml loader with shipped defaults"
```

---

## Task 4: Run logger (pipeline/runlog.py)

Per-run structured logger that writes to both stdout and `out/<run>/run.log`. Records stage start/end/duration. Used by every subsequent stage.

**Files:**
- Create: `pipeline/runlog.py`
- Create: `tests/test_runlog.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_runlog.py`:

```python
"""Run logger tests."""
from __future__ import annotations

from pathlib import Path

from pipeline.runlog import RunLog


def test_writes_to_log_file(tmp_run_dir: Path):
    log = RunLog(tmp_run_dir)
    log.info("starting")
    log.close()
    text = (tmp_run_dir / "run.log").read_text()
    assert "starting" in text


def test_stage_context_records_duration(tmp_run_dir: Path):
    log = RunLog(tmp_run_dir)
    with log.stage("script"):
        pass
    log.close()
    text = (tmp_run_dir / "run.log").read_text()
    assert "stage start: script" in text
    assert "stage end: script" in text
    assert "duration_ms=" in text


def test_stage_records_failure_with_exception(tmp_run_dir: Path):
    import pytest
    log = RunLog(tmp_run_dir)
    with pytest.raises(RuntimeError):
        with log.stage("voice"):
            raise RuntimeError("boom")
    log.close()
    text = (tmp_run_dir / "run.log").read_text()
    assert "stage failed: voice" in text
    assert "RuntimeError: boom" in text
```

- [ ] **Step 2: Run, verify failure**

```bash
uv run pytest tests/test_runlog.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `pipeline/runlog.py`**

```python
"""Per-run structured logger writing to stdout + out/<run>/run.log."""
from __future__ import annotations

import sys
import time
import traceback
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import IO


class RunLog:
    def __init__(self, run_dir: Path):
        self.run_dir = run_dir
        run_dir.mkdir(parents=True, exist_ok=True)
        self._fh: IO[str] = (run_dir / "run.log").open("a", encoding="utf-8")

    def _write(self, level: str, msg: str) -> None:
        ts = datetime.now().isoformat(timespec="seconds")
        line = f"{ts} {level} {msg}"
        print(line, file=sys.stdout, flush=True)
        self._fh.write(line + "\n")
        self._fh.flush()

    def info(self, msg: str) -> None:
        self._write("INFO", msg)

    def warn(self, msg: str) -> None:
        self._write("WARN", msg)

    def error(self, msg: str) -> None:
        self._write("ERROR", msg)

    @contextmanager
    def stage(self, name: str):
        self._write("INFO", f"stage start: {name}")
        t0 = time.monotonic()
        try:
            yield
        except Exception as exc:
            duration_ms = int((time.monotonic() - t0) * 1000)
            self._write("ERROR", f"stage failed: {name} duration_ms={duration_ms}")
            self._write("ERROR", f"{type(exc).__name__}: {exc}")
            for line in traceback.format_exc().splitlines():
                self._write("ERROR", line)
            raise
        duration_ms = int((time.monotonic() - t0) * 1000)
        self._write("INFO", f"stage end: {name} duration_ms={duration_ms}")

    def close(self) -> None:
        try:
            self._fh.close()
        except Exception:
            pass
```

- [ ] **Step 4: Run tests, verify pass**

```bash
uv run pytest tests/test_runlog.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline/runlog.py tests/test_runlog.py
git commit -m "feat(runlog): per-run logger with stage timing context"
```

---

## Task 5: Gemini LLM wrapper (pipeline/llm.py)

Two methods: `complete(prompt, system=None) -> str` and `embed(text) -> list[float]`. Retries with exponential backoff on transient errors. The class is constructed with a model name and API key; tests use a fake.

**Files:**
- Create: `pipeline/llm.py`
- Create: `tests/test_llm.py`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Add `FakeGemini` to `tests/conftest.py`**

Append to `tests/conftest.py`:

```python
from typing import Callable


class FakeGemini:
    """Test fake. Configure with prompt-pattern → response mappings."""

    def __init__(self):
        self._responses: list[Callable[[str], str | None]] = []
        self._embeddings: dict[str, list[float]] = {}
        self.complete_calls: list[tuple[str, str | None]] = []
        self.embed_calls: list[str] = []

    def when(self, predicate: Callable[[str], bool], reply: str):
        """Register: if prompt matches predicate, return reply."""
        def matcher(prompt: str) -> str | None:
            return reply if predicate(prompt) else None
        self._responses.append(matcher)

    def set_embedding(self, text: str, vec: list[float]):
        self._embeddings[text] = vec

    # production interface
    def complete(self, prompt: str, system: str | None = None) -> str:
        self.complete_calls.append((prompt, system))
        for matcher in self._responses:
            r = matcher(prompt)
            if r is not None:
                return r
        raise AssertionError(f"FakeGemini got unexpected prompt: {prompt[:200]}")

    def embed(self, text: str) -> list[float]:
        self.embed_calls.append(text)
        if text in self._embeddings:
            return self._embeddings[text]
        # default deterministic embedding from text length
        return [float(len(text) % 100) / 100.0] * 8


@pytest.fixture
def fake_gemini():
    return FakeGemini()
```

- [ ] **Step 2: Write failing test**

Create `tests/test_llm.py`:

```python
"""Gemini wrapper interface tests. Production calls are mocked."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from pipeline.llm import GeminiClient, GeminiError


def test_complete_returns_string(monkeypatch):
    fake_response = MagicMock()
    fake_response.text = "hello"
    fake_models = MagicMock()
    fake_models.generate_content.return_value = fake_response
    fake_client = MagicMock()
    fake_client.models = fake_models

    monkeypatch.setattr("pipeline.llm._make_client", lambda *_a, **_k: fake_client)

    g = GeminiClient(api_key="k", model="gemini-2.5-flash")
    assert g.complete("hi") == "hello"


def test_complete_retries_then_succeeds(monkeypatch):
    call_count = {"n": 0}

    def flaky(*a, **kw):
        call_count["n"] += 1
        if call_count["n"] < 3:
            raise RuntimeError("transient")
        r = MagicMock()
        r.text = "ok"
        return r

    fake_models = MagicMock()
    fake_models.generate_content.side_effect = flaky
    fake_client = MagicMock(); fake_client.models = fake_models
    monkeypatch.setattr("pipeline.llm._make_client", lambda *_a, **_k: fake_client)
    monkeypatch.setattr("pipeline.llm._SLEEP", lambda _: None)  # skip backoff

    g = GeminiClient(api_key="k", model="gemini-2.5-flash")
    assert g.complete("hi") == "ok"
    assert call_count["n"] == 3


def test_complete_raises_after_max_retries(monkeypatch):
    fake_models = MagicMock()
    fake_models.generate_content.side_effect = RuntimeError("permanent")
    fake_client = MagicMock(); fake_client.models = fake_models
    monkeypatch.setattr("pipeline.llm._make_client", lambda *_a, **_k: fake_client)
    monkeypatch.setattr("pipeline.llm._SLEEP", lambda _: None)

    g = GeminiClient(api_key="k", model="gemini-2.5-flash")
    with pytest.raises(GeminiError):
        g.complete("hi")


def test_embed_returns_vector(monkeypatch):
    fake_embed = MagicMock()
    fake_embed.embeddings = [MagicMock(values=[0.1, 0.2, 0.3])]
    fake_models = MagicMock()
    fake_models.embed_content.return_value = fake_embed
    fake_client = MagicMock(); fake_client.models = fake_models
    monkeypatch.setattr("pipeline.llm._make_client", lambda *_a, **_k: fake_client)

    g = GeminiClient(api_key="k", model="gemini-2.5-flash")
    vec = g.embed("text")
    assert vec == [0.1, 0.2, 0.3]
```

- [ ] **Step 3: Run, verify failure**

```bash
uv run pytest tests/test_llm.py -v
```

Expected: ImportError.

- [ ] **Step 4: Implement `pipeline/llm.py`**

```python
"""Gemini API wrapper. Two operations: complete + embed. Retry with backoff."""
from __future__ import annotations

import os
import time

_SLEEP = time.sleep
_MAX_RETRIES = 3
_BACKOFF_S = (1, 5, 30)


class GeminiError(RuntimeError):
    pass


def _make_client(api_key: str):
    """Constructed at runtime so tests can monkeypatch."""
    from google import genai
    return genai.Client(api_key=api_key)


class GeminiClient:
    """Thin wrapper around google-genai with retries.

    Two methods:
      complete(prompt, system=None) -> str
      embed(text) -> list[float]
    """

    def __init__(self, api_key: str | None = None, model: str = "gemini-2.5-flash"):
        key = api_key or os.environ.get("GEMINI_API_KEY")
        if not key:
            raise GeminiError("GEMINI_API_KEY not set")
        self._client = _make_client(key)
        self._model = model

    def complete(self, prompt: str, system: str | None = None) -> str:
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                kwargs = {"model": self._model, "contents": prompt}
                if system:
                    kwargs["config"] = {"system_instruction": system}
                resp = self._client.models.generate_content(**kwargs)
                return resp.text
            except Exception as e:
                last_exc = e
                if attempt < _MAX_RETRIES - 1:
                    _SLEEP(_BACKOFF_S[attempt])
        raise GeminiError(f"complete failed after {_MAX_RETRIES} attempts: {last_exc}")

    def embed(self, text: str) -> list[float]:
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                resp = self._client.models.embed_content(
                    model="text-embedding-004",
                    contents=text,
                )
                return list(resp.embeddings[0].values)
            except Exception as e:
                last_exc = e
                if attempt < _MAX_RETRIES - 1:
                    _SLEEP(_BACKOFF_S[attempt])
        raise GeminiError(f"embed failed after {_MAX_RETRIES} attempts: {last_exc}")
```

- [ ] **Step 5: Run tests, verify pass**

```bash
uv run pytest tests/test_llm.py -v
```

Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add pipeline/llm.py tests/test_llm.py tests/conftest.py
git commit -m "feat(llm): Gemini wrapper with retry + FakeGemini test fake"
```

---

## Task 6: Topic seeder (pipeline/seed.py)

Manual mode (user supplies theme + premise) and auto mode (random theme → Gemini generates premise). Theme rotation guard: reject any theme used in the last 3 auto runs. Persists to `out/theme_log.json` (project-level history, NOT per-run).

**Files:**
- Create: `pipeline/seed.py`
- Create: `tests/test_seed.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_seed.py`:

```python
"""Topic seeder tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline.seed import (
    AUTO_PREMISE_PROMPT,
    THEME_BANK,
    auto_seed,
    manual_seed,
    record_theme_use,
)
from pipeline.types import ThemeSeed


def test_manual_seed_validates_theme():
    s = manual_seed("folkloric", "بئر قديم")
    assert s == ThemeSeed(theme="folkloric", premise="بئر قديم")


def test_manual_seed_rejects_unknown_theme():
    with pytest.raises(ValueError):
        manual_seed("not-a-theme", "x")


def test_auto_seed_uses_gemini_for_premise(fake_gemini, tmp_path: Path):
    fake_gemini.when(
        lambda p: AUTO_PREMISE_PROMPT.split("{")[0] in p,
        "بئر قديم في قرية مهجورة"
    )
    log_path = tmp_path / "theme_log.json"
    seed = auto_seed(fake_gemini, log_path, rng_seed=0)
    assert seed.theme in THEME_BANK
    assert seed.premise == "بئر قديم في قرية مهجورة"


def test_auto_seed_skips_recent_themes(fake_gemini, tmp_path: Path):
    log_path = tmp_path / "theme_log.json"
    # Pre-populate the log with 3 most-recent themes
    recent = list(THEME_BANK)[:3]
    log_path.write_text(json.dumps([
        {"theme": t, "ts": "2026-04-30T10:00:00"} for t in recent
    ], ensure_ascii=False))
    fake_gemini.when(lambda p: True, "بئر")
    seed = auto_seed(fake_gemini, log_path, rng_seed=42)
    assert seed.theme not in recent


def test_record_theme_use_appends(tmp_path: Path):
    log_path = tmp_path / "theme_log.json"
    record_theme_use(log_path, "folkloric")
    record_theme_use(log_path, "domestic")
    data = json.loads(log_path.read_text())
    assert [d["theme"] for d in data] == ["folkloric", "domestic"]
```

- [ ] **Step 2: Run, verify failure**

```bash
uv run pytest tests/test_seed.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `pipeline/seed.py`**

```python
"""Stage 1: topic seeding.

Manual mode: user supplies (theme, premise).
Auto mode:   pick a theme respecting recency guard, ask Gemini for an Arabic premise.
"""
from __future__ import annotations

import json
import random
from datetime import datetime
from pathlib import Path

from pipeline.types import VALID_THEMES, ThemeSeed

THEME_BANK: tuple[str, ...] = tuple(sorted(VALID_THEMES))
RECENCY_BLOCK = 3  # auto mode rejects themes used in last N runs

AUTO_PREMISE_PROMPT = (
    "أنت كاتب قصص رعب باللغة العربية الفصحى. "
    "اقترح فرضية قصة رعب قصيرة (جملة واحدة) ضمن الفئة التالية: {theme}. "
    "الفرضية يجب أن تكون مغرية ومفتوحة ومناسبة لقصة من 10 إلى 15 دقيقة بضمير المتكلم. "
    "أرجع فقط الفرضية بدون مقدمات."
)


def manual_seed(theme: str, premise: str) -> ThemeSeed:
    if theme not in VALID_THEMES:
        raise ValueError(f"unknown theme: {theme}; valid: {sorted(VALID_THEMES)}")
    if not premise.strip():
        raise ValueError("premise must not be empty")
    return ThemeSeed(theme=theme, premise=premise.strip())


def _load_log(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def record_theme_use(path: Path, theme: str) -> None:
    log = _load_log(path)
    log.append({"theme": theme, "ts": datetime.now().isoformat(timespec="seconds")})
    path.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")


def _pick_theme_avoiding_recent(log: list[dict], rng: random.Random) -> str:
    recent = {entry["theme"] for entry in log[-RECENCY_BLOCK:]}
    candidates = [t for t in THEME_BANK if t not in recent]
    if not candidates:  # all themes blocked (only happens if RECENCY_BLOCK >= len(THEME_BANK))
        candidates = list(THEME_BANK)
    return rng.choice(candidates)


def auto_seed(gemini, log_path: Path, rng_seed: int | None = None) -> ThemeSeed:
    rng = random.Random(rng_seed)
    log = _load_log(log_path)
    theme = _pick_theme_avoiding_recent(log, rng)
    prompt = AUTO_PREMISE_PROMPT.format(theme=theme)
    premise = gemini.complete(prompt).strip()
    if not premise:
        raise RuntimeError("Gemini returned empty premise")
    return ThemeSeed(theme=theme, premise=premise)
```

- [ ] **Step 4: Run tests, verify pass**

```bash
uv run pytest tests/test_seed.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline/seed.py tests/test_seed.py
git commit -m "feat(seed): topic seeder with theme rotation guard"
```

---

## Task 7: Script writer — first pass (pipeline/script.py — generation only)

The script writer is split across three tasks. This task implements the first-pass generation only. Critique pass and repetition guard come in tasks 8 and 9.

**Files:**
- Create: `pipeline/script.py`
- Create: `tests/test_script.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_script.py`:

```python
"""Script writer tests — first pass only."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline.script import build_writer_prompt, generate_script_first_pass
from pipeline.types import Script, ThemeSeed


def test_writer_prompt_includes_seed_and_constraints():
    seed = ThemeSeed(theme="folkloric", premise="بئر قديم")
    p = build_writer_prompt(seed, target_words=2200, tolerance=200)
    assert "بئر قديم" in p
    assert "folkloric" in p
    assert "2200" in p or "2,200" in p
    assert "ضمير المتكلم" in p
    assert "MSA" in p or "الفصحى" in p


def test_first_pass_parses_valid_json(fake_gemini):
    seed = ThemeSeed(theme="folkloric", premise="بئر قديم")
    fake_gemini.when(lambda p: "بئر قديم" in p, json.dumps({
        "title": "بئر",
        "theme": "folkloric",
        "global_setting": "مدينة فجر, شتاء",
        "music_mood": "dread",
        "hook": "افتتاح",
        "story": "نص" * 1100,
        "word_count": 2200,
    }, ensure_ascii=False))
    s = generate_script_first_pass(fake_gemini, seed, target_words=2200, tolerance=200)
    assert isinstance(s, Script)
    assert s.title == "بئر"


def test_first_pass_overrides_theme_to_match_seed(fake_gemini):
    """If Gemini returns a different theme tag, we trust the seed."""
    seed = ThemeSeed(theme="folkloric", premise="بئر")
    fake_gemini.when(lambda p: True, json.dumps({
        "title": "x", "theme": "domestic",  # WRONG theme returned
        "global_setting": "x", "music_mood": "drone",
        "hook": "x", "story": "x" * 100, "word_count": 100,
    }, ensure_ascii=False))
    s = generate_script_first_pass(fake_gemini, seed, target_words=100, tolerance=10)
    assert s.theme == "folkloric"  # corrected to match seed


def test_first_pass_strips_markdown_code_fence(fake_gemini):
    """Gemini sometimes wraps JSON in ```json ... ``` fences."""
    seed = ThemeSeed(theme="folkloric", premise="x")
    payload = json.dumps({
        "title": "x", "theme": "folkloric", "global_setting": "x",
        "music_mood": "drone", "hook": "x", "story": "y" * 100, "word_count": 100,
    }, ensure_ascii=False)
    fake_gemini.when(lambda p: True, f"```json\n{payload}\n```")
    s = generate_script_first_pass(fake_gemini, seed, target_words=100, tolerance=10)
    assert s.title == "x"


def test_first_pass_raises_on_invalid_json(fake_gemini):
    seed = ThemeSeed(theme="folkloric", premise="x")
    fake_gemini.when(lambda p: True, "this is not json")
    with pytest.raises(ValueError):
        generate_script_first_pass(fake_gemini, seed, target_words=100, tolerance=10)
```

- [ ] **Step 2: Run, verify failure**

```bash
uv run pytest tests/test_script.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement first pass in `pipeline/script.py`**

```python
"""Stage 2: script generation.

Pipeline: build prompt → Gemini call → parse JSON → optional critique pass → repetition check.

This file holds:
  - first-pass generation (this task)
  - critique pass (Task 8)
  - repetition guard (Task 9)
"""
from __future__ import annotations

import json
import re

from pipeline.types import Script, ThemeSeed

WRITER_SYSTEM = (
    "أنت كاتب قصص رعب محترف بالعربية الفصحى (MSA) بأسلوب أدبي تأملي. "
    "أسلوبك يشبه قنوات mr nightmare لكن باللغة العربية: الإيقاع البطيء، الجو القاتم، "
    "النهايات المفتوحة، ضمير المتكلم. ممنوع: الحوار الزائد، الكليشيهات، "
    "النهايات التي تشرح كل شيء، 'فجأة سمعت صوتاً'، 'كان كل شيء حلماً'."
)

WRITER_PROMPT_TEMPLATE = """\
اكتب قصة رعب باللغة العربية الفصحى وفق هذه القواعد:

الفرضية: {premise}
الفئة: {theme}

البنية المطلوبة (التزم بها):
1) خطاف افتتاحي قوي (أول 30 ثانية، 3-4 جمل) — لحظة عادية فيها ما يثير الريبة.
2) إعداد (1-2 دقيقة) — مكان وزمان وشخصية، أرضية واقعية مألوفة.
3) اضطراب أول (2-3 دقائق) — شيء صغير غير صحيح، الراوي يتجاهله.
4) تصاعد (3-4 دقائق) — اضطرابات متعددة، الإنكار ينهار.
5) مواجهة (2-3 دقائق) — الراوي يواجه ما يحدث.
6) ذروة (1-2 دقيقة) — رعب أقصى، إيقاع سريع، جمل قصيرة.
7) نهاية مفتوحة (آخر 30 ثانية) — لا تشرح أبداً ما الذي حدث.

عدد الكلمات المستهدف: {target_words} كلمة (±{tolerance}).
ضمير المتكلم (أنا) — إجباري.
MSA الفصحى — لا لهجة.
لحظة "غريب لكن مألوف" — إجبارية.
نهاية مفتوحة — إجبارية.

أرجع JSON صالح فقط (بدون أي تعليق أو ``` markdown) بالحقول التالية بالضبط:
{{
  "title": "...",
  "theme": "{theme}",
  "global_setting": "وصف موجز للموقع/الزمن/الجو الذي تجري فيه القصة كلها (إنجليزي مختصر) — يستخدم لاحقاً لتوليد الصور",
  "music_mood": "drone | dread | cosmic | discovery — اختر واحد",
  "hook": "الفقرة الافتتاحية (3-4 جمل)",
  "story": "النص الكامل من البداية للنهاية، فقرات مفصولة بـ \\n\\n",
  "word_count": <عدد كلمات story>
}}
"""


def build_writer_prompt(seed: ThemeSeed, target_words: int, tolerance: int) -> str:
    return WRITER_PROMPT_TEMPLATE.format(
        premise=seed.premise,
        theme=seed.theme,
        target_words=target_words,
        tolerance=tolerance,
    )


def _strip_code_fence(text: str) -> str:
    """Remove ```json ... ``` or ``` ... ``` wrappers if present."""
    s = text.strip()
    fence = re.match(r"^```(?:json)?\s*\n(.*?)\n```\s*$", s, re.DOTALL)
    if fence:
        return fence.group(1).strip()
    return s


def _parse_script_json(text: str, seed: ThemeSeed) -> Script:
    cleaned = _strip_code_fence(text)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"script writer returned invalid JSON: {e}\n--- got ---\n{text[:500]}")
    # We trust the seed.theme over whatever Gemini returned (defensive).
    data["theme"] = seed.theme
    # Recompute word_count from story to avoid LLM miscount.
    story = data.get("story", "")
    data["word_count"] = len([w for w in story.split() if w.strip()])
    try:
        return Script.from_dict(data)
    except (TypeError, ValueError) as e:
        raise ValueError(f"script JSON missing/invalid fields: {e}; got keys={list(data.keys())}")


def generate_script_first_pass(
    gemini, seed: ThemeSeed, target_words: int, tolerance: int
) -> Script:
    prompt = build_writer_prompt(seed, target_words, tolerance)
    raw = gemini.complete(prompt, system=WRITER_SYSTEM)
    return _parse_script_json(raw, seed)
```

- [ ] **Step 4: Run tests, verify pass**

```bash
uv run pytest tests/test_script.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline/script.py tests/test_script.py
git commit -m "feat(script): first-pass Arabic horror script generator"
```

---

## Task 8: Script writer — critique pass

Adds a second Gemini call: read the draft, look for weak hooks / explanatory endings / banned-trope phrases, return a revised script.

**Files:**
- Modify: `pipeline/script.py`
- Modify: `tests/test_script.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_script.py`:

```python
def test_critique_pass_revises_when_flagged(fake_gemini):
    seed = ThemeSeed(theme="folkloric", premise="x")
    draft = Script(
        title="t", theme="folkloric", global_setting="x",
        music_mood="dread", hook="weak", story="y" * 100, word_count=100,
    )
    revised_payload = json.dumps({
        "title": "t-revised", "theme": "folkloric", "global_setting": "x",
        "music_mood": "dread", "hook": "stronger hook", "story": "z" * 100,
        "word_count": 100,
    }, ensure_ascii=False)
    fake_gemini.when(lambda p: "نقد" in p or "critique" in p.lower(), revised_payload)

    from pipeline.script import critique_pass
    out = critique_pass(fake_gemini, seed, draft)
    assert out.title == "t-revised"
    assert out.hook == "stronger hook"


def test_generate_script_full_pipeline_with_critique(fake_gemini):
    """End-to-end: first pass + critique pass."""
    seed = ThemeSeed(theme="folkloric", premise="بئر")
    first = json.dumps({
        "title": "v1", "theme": "folkloric", "global_setting": "x",
        "music_mood": "dread", "hook": "h", "story": "s" * 100, "word_count": 100,
    }, ensure_ascii=False)
    second = json.dumps({
        "title": "v2", "theme": "folkloric", "global_setting": "x",
        "music_mood": "dread", "hook": "h2", "story": "s" * 100, "word_count": 100,
    }, ensure_ascii=False)
    # First call returns first; second (critique) returns second.
    seq = [first, second]
    fake_gemini.when(lambda p: bool(seq), "")  # placeholder; we override below

    # Replace responses list with a sequencer
    fake_gemini._responses.clear()
    def sequencer(prompt: str):
        return seq.pop(0) if seq else None
    fake_gemini._responses.append(sequencer)

    from pipeline.script import generate_script
    out = generate_script(fake_gemini, seed, target_words=100, tolerance=10, enable_critique=True)
    assert out.title == "v2"


def test_generate_script_skips_critique_when_disabled(fake_gemini):
    seed = ThemeSeed(theme="folkloric", premise="بئر")
    fake_gemini.when(lambda p: True, json.dumps({
        "title": "v1", "theme": "folkloric", "global_setting": "x",
        "music_mood": "dread", "hook": "h", "story": "s" * 100, "word_count": 100,
    }, ensure_ascii=False))
    from pipeline.script import generate_script
    out = generate_script(fake_gemini, seed, target_words=100, tolerance=10, enable_critique=False)
    assert out.title == "v1"
    assert len(fake_gemini.complete_calls) == 1  # only first pass
```

- [ ] **Step 2: Run, verify failure**

```bash
uv run pytest tests/test_script.py::test_critique_pass_revises_when_flagged tests/test_script.py::test_generate_script_full_pipeline_with_critique -v
```

Expected: ImportError on `critique_pass` / `generate_script`.

- [ ] **Step 3: Add critique pass to `pipeline/script.py`**

Append to `pipeline/script.py`:

```python
CRITIQUE_PROMPT_TEMPLATE = """\
أنت محرر صارم لقصص الرعب. اقرأ المسودة التالية وقم بتحسينها:

المسودة:
{draft_json}

افحص:
- هل الخطاف الافتتاحي قوي بما يكفي ليوقف المشاهد في أول 30 ثانية؟
- هل النهاية مفتوحة وغير مفسرة؟ (إذا كانت تشرح كل شيء — أصلحها)
- هل توجد كليشيهات ممنوعة مثل: "فجأة سمعت صوتاً"، "كان كل شيء حلماً"، "شعرت بأن أحداً يراقبني" المباشر؟
- هل هناك لحظة "غريب لكن مألوف" واضحة؟
- هل الإيقاع يتصاعد بشكل صحيح؟

أعد كتابة المسودة كاملةً مع التحسينات. حافظ على عدد الكلمات تقريباً.

أرجع JSON صالح فقط بنفس الحقول السابقة (نقد + إصلاح في خطوة واحدة):
{{
  "title": "...",
  "theme": "{theme}",
  "global_setting": "...",
  "music_mood": "drone | dread | cosmic | discovery",
  "hook": "...",
  "story": "...",
  "word_count": <int>
}}
"""


def critique_pass(gemini, seed: ThemeSeed, draft: Script) -> Script:
    prompt = CRITIQUE_PROMPT_TEMPLATE.format(
        draft_json=json.dumps(draft.to_dict(), ensure_ascii=False, indent=2),
        theme=seed.theme,
    )
    raw = gemini.complete(prompt, system=WRITER_SYSTEM)
    return _parse_script_json(raw, seed)


def generate_script(
    gemini,
    seed: ThemeSeed,
    target_words: int,
    tolerance: int,
    enable_critique: bool = True,
) -> Script:
    """First pass + (optional) critique pass. No repetition guard yet — added in next task."""
    draft = generate_script_first_pass(gemini, seed, target_words, tolerance)
    if enable_critique:
        return critique_pass(gemini, seed, draft)
    return draft
```

- [ ] **Step 4: Run tests, verify pass**

```bash
uv run pytest tests/test_script.py -v
```

Expected: 8 passed (5 from Task 7 + 3 new).

- [ ] **Step 5: Commit**

```bash
git add pipeline/script.py tests/test_script.py
git commit -m "feat(script): critique pass + generate_script orchestration"
```

---

## Task 9: Script writer — repetition guard

Embed the new story; compare cosine similarity vs the last 30 stories in `out/story_history.jsonl`. If any similarity > threshold, regenerate (up to 2 retries). Then append the accepted story's embedding to history.

**Files:**
- Modify: `pipeline/script.py`
- Modify: `tests/test_script.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_script.py`:

```python
def test_cosine_similarity():
    from pipeline.script import _cosine
    assert abs(_cosine([1, 0], [1, 0]) - 1.0) < 1e-9
    assert abs(_cosine([1, 0], [0, 1])) < 1e-9
    assert abs(_cosine([1, 0], [-1, 0]) + 1.0) < 1e-9


def test_repetition_guard_appends_when_unique(fake_gemini, tmp_path: Path):
    from pipeline.script import check_and_record_uniqueness

    # No history file → unique by default
    fake_gemini.set_embedding("story text", [1.0, 0.0, 0.0])
    history = tmp_path / "story_history.jsonl"

    is_unique, similarity = check_and_record_uniqueness(
        fake_gemini, "story text", history, threshold=0.85,
    )
    assert is_unique is True
    assert similarity == 0.0
    assert history.exists()
    line = history.read_text().strip()
    assert "[1.0" in line


def test_repetition_guard_rejects_when_too_similar(fake_gemini, tmp_path: Path):
    from pipeline.script import check_and_record_uniqueness
    history = tmp_path / "story_history.jsonl"
    history.write_text(json.dumps({"embedding": [1.0, 0.0, 0.0], "ts": "2026-04-30"}) + "\n")
    fake_gemini.set_embedding("near-dup", [0.99, 0.01, 0.0])  # cos ≈ 1.0

    is_unique, similarity = check_and_record_uniqueness(
        fake_gemini, "near-dup", history, threshold=0.85,
    )
    assert is_unique is False
    assert similarity > 0.85


def test_run_full_regenerates_on_repetition(fake_gemini, tmp_path: Path):
    """End-to-end: first attempt is too similar → regenerate, second succeeds."""
    seed = ThemeSeed(theme="folkloric", premise="x")

    # Two distinct payloads. Embeddings: first matches history, second is distant.
    payload_a = json.dumps({
        "title": "a", "theme": "folkloric", "global_setting": "x",
        "music_mood": "dread", "hook": "h", "story": "story-a" * 20, "word_count": 100,
    }, ensure_ascii=False)
    payload_b = json.dumps({
        "title": "b", "theme": "folkloric", "global_setting": "x",
        "music_mood": "dread", "hook": "h", "story": "story-b" * 20, "word_count": 100,
    }, ensure_ascii=False)

    seq = [payload_a, payload_b]
    fake_gemini._responses.clear()
    fake_gemini._responses.append(lambda p: seq.pop(0) if seq else None)

    fake_gemini.set_embedding("story-a" * 20, [1.0, 0.0])
    fake_gemini.set_embedding("story-b" * 20, [0.0, 1.0])

    history = tmp_path / "story_history.jsonl"
    history.write_text(json.dumps({"embedding": [1.0, 0.0], "ts": "p"}) + "\n")

    from pipeline.script import generate_script_with_uniqueness
    out = generate_script_with_uniqueness(
        fake_gemini, seed,
        target_words=100, tolerance=10,
        enable_critique=False,
        history_path=history,
        repetition_threshold=0.85,
        max_attempts=3,
    )
    assert out.title == "b"
```

- [ ] **Step 2: Run, verify failure**

```bash
uv run pytest tests/test_script.py -v
```

Expected: failures on missing functions.

- [ ] **Step 3: Append to `pipeline/script.py`**

```python
import math
from datetime import datetime
from pathlib import Path


def _cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        raise ValueError(f"vector dim mismatch: {len(a)} vs {len(b)}")
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _read_history(path: Path, limit: int = 30) -> list[list[float]]:
    if not path.exists():
        return []
    embeddings: list[list[float]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            embeddings.append(json.loads(line)["embedding"])
        except (json.JSONDecodeError, KeyError):
            continue
    return embeddings[-limit:]


def check_and_record_uniqueness(
    gemini, story_text: str, history_path: Path, threshold: float
) -> tuple[bool, float]:
    """Embed `story_text`, compare against history, append if unique. Returns (is_unique, max_sim)."""
    new_emb = gemini.embed(story_text)
    history = _read_history(history_path)
    max_sim = max((_cosine(new_emb, prev) for prev in history), default=0.0)
    is_unique = max_sim < threshold
    if is_unique:
        history_path.parent.mkdir(parents=True, exist_ok=True)
        with history_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "embedding": new_emb,
                "ts": datetime.now().isoformat(timespec="seconds"),
            }) + "\n")
    return is_unique, max_sim


def generate_script_with_uniqueness(
    gemini,
    seed: ThemeSeed,
    target_words: int,
    tolerance: int,
    enable_critique: bool,
    history_path: Path,
    repetition_threshold: float,
    max_attempts: int = 3,
) -> Script:
    """Loop: generate → check uniqueness → accept or retry up to max_attempts."""
    last_sim = 0.0
    for attempt in range(max_attempts):
        script = generate_script(gemini, seed, target_words, tolerance, enable_critique)
        is_unique, sim = check_and_record_uniqueness(
            gemini, script.story, history_path, repetition_threshold,
        )
        if is_unique:
            return script
        last_sim = sim
    raise RuntimeError(
        f"could not generate unique script after {max_attempts} attempts "
        f"(last similarity {last_sim:.3f} >= threshold {repetition_threshold})"
    )
```

- [ ] **Step 4: Run tests, verify pass**

```bash
uv run pytest tests/test_script.py -v
```

Expected: 12 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline/script.py tests/test_script.py
git commit -m "feat(script): embedding-based repetition guard with retries"
```

---

## Task 10: Voice generator (pipeline/voice.py)

Wraps `edge-tts`. SSML pause injection, word-timing extraction. The function `generate_narration` is the public API; the internal Edge TTS call is isolated in `_synthesize` so tests can monkeypatch it.

**Files:**
- Create: `pipeline/voice.py`
- Create: `tests/test_voice.py`

- [ ] **Step 1: Add a tiny silent MP3 fixture**

```bash
# Use ffmpeg to generate a 1-second silent mp3 fixture (one-time setup):
ffmpeg -f lavfi -i anullsrc=r=24000:cl=mono -t 1 -q:a 9 -acodec libmp3lame tests/fixtures/narration_sample.mp3 -y
```

Confirm: `ls -la tests/fixtures/narration_sample.mp3` shows the file (~5 KB).

- [ ] **Step 2: Write failing test**

Create `tests/test_voice.py`:

```python
"""Voice generator tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline.voice import generate_narration, inject_ssml_pauses


def test_inject_ssml_period():
    out = inject_ssml_pauses("جملة أولى. جملة ثانية.")
    assert "<break time=\"600ms\"/>" in out


def test_inject_ssml_ellipsis():
    out = inject_ssml_pauses("جملة... ثم")
    assert "<break time=\"1200ms\"/>" in out


def test_inject_ssml_paragraph():
    out = inject_ssml_pauses("فقرة1\n\nفقرة2")
    assert "<break time=\"1500ms\"/>" in out


def test_generate_narration_writes_outputs(monkeypatch, tmp_run_dir: Path, fixtures_dir: Path):
    """`_synthesize` is replaced with a fake that writes a known fixture."""
    sample_mp3 = (fixtures_dir / "narration_sample.mp3").read_bytes()
    fake_timings = [
        {"word": "كنت", "offset_ms": 0, "duration_ms": 480},
        {"word": "أسير", "offset_ms": 510, "duration_ms": 620},
    ]

    def fake_synthesize(text, voice, rate, pitch, mp3_path: Path):
        mp3_path.write_bytes(sample_mp3)
        return fake_timings

    monkeypatch.setattr("pipeline.voice._synthesize", fake_synthesize)

    out_mp3 = tmp_run_dir / "narration.mp3"
    out_timings = tmp_run_dir / "word_timings.json"
    generate_narration(
        text="كنت أسير.",
        voice="ar-SA-HamedNeural", rate="-20%", pitch="-5%",
        mp3_path=out_mp3, timings_path=out_timings,
    )
    assert out_mp3.exists() and out_mp3.stat().st_size > 0
    timings = json.loads(out_timings.read_text())
    assert timings[0]["word"] == "كنت"
    assert len(timings) == 2


def test_generate_narration_skips_if_already_exists(monkeypatch, tmp_run_dir: Path, fixtures_dir: Path):
    """Resumability: if both files exist, synthesize is not called."""
    sample_mp3 = (fixtures_dir / "narration_sample.mp3").read_bytes()
    out_mp3 = tmp_run_dir / "narration.mp3"
    out_timings = tmp_run_dir / "word_timings.json"
    out_mp3.write_bytes(sample_mp3)
    out_timings.write_text(json.dumps([{"word": "x", "offset_ms": 0, "duration_ms": 100}]))

    called = {"count": 0}
    def fake_synthesize(*a, **kw):
        called["count"] += 1
        return []
    monkeypatch.setattr("pipeline.voice._synthesize", fake_synthesize)

    generate_narration(
        text="...",
        voice="x", rate="0%", pitch="0%",
        mp3_path=out_mp3, timings_path=out_timings,
    )
    assert called["count"] == 0


def test_synthesize_retries_then_succeeds(monkeypatch, tmp_path: Path):
    """The internal _synthesize retries transient edge-tts failures."""
    from pipeline import voice as voice_mod

    attempts = {"n": 0}

    def flaky_run(text, voice, rate, pitch, mp3_path):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RuntimeError("transient")
        mp3_path.write_bytes(b"\x00")
        return [{"word": "ok", "offset_ms": 0, "duration_ms": 100}]

    async def fake_run(*a, **kw):
        return flaky_run(*a, **kw)

    monkeypatch.setattr(voice_mod, "_edge_tts_run", fake_run)
    monkeypatch.setattr(voice_mod, "_SLEEP", lambda _s: None)

    out = tmp_path / "n.mp3"
    timings = voice_mod._synthesize("hi", "v", "0%", "0%", out)
    assert attempts["n"] == 3
    assert timings[0]["word"] == "ok"


def test_synthesize_raises_after_max_retries(monkeypatch, tmp_path: Path):
    from pipeline import voice as voice_mod

    async def always_fail(*a, **kw):
        raise RuntimeError("permanent")

    monkeypatch.setattr(voice_mod, "_edge_tts_run", always_fail)
    monkeypatch.setattr(voice_mod, "_SLEEP", lambda _s: None)

    with pytest.raises(RuntimeError, match="edge-tts failed"):
        voice_mod._synthesize("hi", "v", "0%", "0%", tmp_path / "n.mp3")
```

- [ ] **Step 3: Run, verify failure**

```bash
uv run pytest tests/test_voice.py -v
```

Expected: ImportError.

- [ ] **Step 4: Implement `pipeline/voice.py`**

```python
"""Stage 3: Edge TTS narration + word-level timings."""
from __future__ import annotations

import asyncio
import json
import re
import time
from pathlib import Path


def inject_ssml_pauses(text: str) -> str:
    """Convert plain Arabic text to text with SSML <break/> tags.

    - Paragraph break (\n\n)  → 1500ms
    - Ellipsis or em-dash    → 1200ms
    - Period                 → 600ms
    """
    # Order matters: handle long-form punctuation first.
    text = text.replace("\n\n", '<break time="1500ms"/>')
    text = re.sub(r"\.\.\.|…|—", '<break time="1200ms"/>', text)
    text = re.sub(r"\.(?!\d)", '<break time="600ms"/>', text)  # avoid breaking decimals
    return text


async def _edge_tts_run(text: str, voice: str, rate: str, pitch: str, mp3_path: Path) -> list[dict]:
    """Run edge-tts in async context. Returns word-timing dicts."""
    import edge_tts

    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate, pitch=pitch)
    timings: list[dict] = []
    with mp3_path.open("wb") as f:
        async for chunk in communicate.stream():
            t = chunk["type"]
            if t == "audio":
                f.write(chunk["data"])
            elif t == "WordBoundary":
                # offset and duration are in 100-nanosecond units (HNS)
                offset_ms = chunk["offset"] // 10_000
                duration_ms = chunk["duration"] // 10_000
                timings.append({
                    "word": chunk["text"],
                    "offset_ms": int(offset_ms),
                    "duration_ms": int(duration_ms),
                })
    return timings


_SLEEP = time.sleep
_MAX_RETRIES = 3
_BACKOFF_S = (1, 5, 30)


def _synthesize(text: str, voice: str, rate: str, pitch: str, mp3_path: Path) -> list[dict]:
    """Sync wrapper around the async edge-tts call with retry. Replaceable in tests."""
    mp3_path.parent.mkdir(parents=True, exist_ok=True)
    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            return asyncio.run(_edge_tts_run(text, voice, rate, pitch, mp3_path))
        except Exception as e:
            last_exc = e
            if attempt < _MAX_RETRIES - 1:
                _SLEEP(_BACKOFF_S[attempt])
    raise RuntimeError(f"edge-tts failed after {_MAX_RETRIES} attempts: {last_exc}")


def generate_narration(
    text: str,
    voice: str,
    rate: str,
    pitch: str,
    mp3_path: Path,
    timings_path: Path,
) -> None:
    """Resumable: if both outputs already exist, skip."""
    if mp3_path.exists() and timings_path.exists():
        return
    ssml_text = inject_ssml_pauses(text)
    timings = _synthesize(ssml_text, voice, rate, pitch, mp3_path)
    timings_path.write_text(
        json.dumps(timings, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
```

- [ ] **Step 5: Run tests, verify pass**

```bash
uv run pytest tests/test_voice.py -v
```

Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add pipeline/voice.py tests/test_voice.py tests/fixtures/narration_sample.mp3
git commit -m "feat(voice): edge-tts wrapper with SSML pauses + word timings"
```

---

## Task 11: Scene splitter (pipeline/shots.py)

Reads `script.json` + `word_timings.json`. Chunks into 15–20s segments snapped to sentence ends. Calls Gemini per chunk to translate each chunk into an English Flux prompt. Appends the fixed style suffix and emits `shots.json`.

**Files:**
- Create: `pipeline/shots.py`
- Create: `tests/test_shots.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_shots.py`:

```python
"""Scene splitter tests."""
from __future__ import annotations

import json
from pathlib import Path

from pipeline.shots import (
    NEGATIVE_PROMPT,
    STYLE_SUFFIX,
    chunk_by_timing,
    generate_shots,
)
from pipeline.types import Script, WordTiming


def _wt(word: str, offset: int, duration: int = 400) -> WordTiming:
    return WordTiming(word=word, offset_ms=offset, duration_ms=duration)


def test_chunk_targets_15_20_seconds():
    timings = [_wt("w", i * 500) for i in range(80)]  # 80 words × 500ms = 40s
    chunks = chunk_by_timing(timings, target_ms=18000, sentence_ends=set())
    # 40s / 18s ≈ 2-3 chunks
    assert 2 <= len(chunks) <= 3
    for c in chunks:
        assert c["end_ms"] - c["start_ms"] <= 25_000  # honored upper bound roughly


def test_chunk_snaps_to_sentence_end():
    timings = [_wt(str(i), i * 1000) for i in range(20)]
    sentence_ends = {5, 12}  # word indices where sentences end
    chunks = chunk_by_timing(timings, target_ms=8000, sentence_ends=sentence_ends)
    end_indices = [c["last_word_index"] for c in chunks]
    # Boundaries must align with sentence ends (the last chunk ends at the last word)
    for idx in end_indices[:-1]:
        assert idx in sentence_ends


def test_seed_assignment_deterministic_per_title():
    from pipeline.shots import shot_seed
    s1 = shot_seed("a-title", index=0)
    s2 = shot_seed("a-title", index=0)
    s3 = shot_seed("a-title", index=1)
    s4 = shot_seed("other", index=0)
    assert s1 == s2
    assert s1 != s3
    assert s1 != s4


def test_generate_shots_writes_shots_json(fake_gemini, tmp_run_dir: Path):
    script = Script(
        title="بئر قديم", theme="folkloric",
        global_setting="abandoned village, night, desert",
        music_mood="dread",
        hook="الفقرة الأولى. الفقرة الثانية.",
        story="فقرة1.\n\nفقرة2. فقرة3.",
        word_count=6,
    )
    timings = [
        _wt("الفقرة1", 0), _wt(".", 500),
        _wt("الفقرة2", 1000), _wt(".", 1500),
        _wt("الفقرة3", 2000), _wt(".", 2500),
    ]
    fake_gemini.when(
        lambda p: "image prompt" in p.lower() or "atmospheric" in p.lower(),
        "lone figure on a moonlit dune"
    )
    out = tmp_run_dir / "shots.json"
    generate_shots(
        gemini=fake_gemini,
        script=script,
        timings=timings,
        out_path=out,
        target_segment_ms=2000,
    )
    data = json.loads(out.read_text())
    assert len(data) >= 1
    first = data[0]
    assert "lone figure" in first["english_prompt"]
    assert STYLE_SUFFIX.split(",")[0] in first["english_prompt"]  # suffix appended
    assert first["negative_prompt"] == NEGATIVE_PROMPT
    assert first["seed"] != 0


def test_generate_shots_skips_if_exists(fake_gemini, tmp_run_dir: Path):
    out = tmp_run_dir / "shots.json"
    out.write_text("[]")  # already exists
    script = Script(
        title="t", theme="folkloric", global_setting="x",
        music_mood="dread", hook="h", story="s", word_count=1,
    )
    generate_shots(
        gemini=fake_gemini, script=script,
        timings=[_wt("x", 0)],
        out_path=out, target_segment_ms=18000,
    )
    assert fake_gemini.complete_calls == []  # skipped
```

- [ ] **Step 2: Run, verify failure**

```bash
uv run pytest tests/test_shots.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `pipeline/shots.py`**

```python
"""Stage 4: scene splitter — turns script + word timings into shots.json."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from pipeline.types import Script, Shot, WordTiming

STYLE_SUFFIX = (
    "dark atmospheric horror photography, dim moonlight, slight film grain, "
    "35mm aesthetic, low light, cinematic composition, eerie mood, "
    "muted desaturated colors, ultra-realistic, 16:9"
)
NEGATIVE_PROMPT = (
    "text, watermark, logo, blurry, low quality, deformed faces, "
    "clear faces, multiple subjects, busy composition, cartoon, illustration"
)

# Arabic + Latin sentence enders
SENTENCE_END_CHARS = {".", "؟", "!", "…"}

PROMPT_TRANSLATE_TEMPLATE = """\
You are translating an Arabic horror story into atmospheric image prompts.

Story global setting: {global_setting}

Below is one Arabic paragraph (~15-20 seconds of narration). Output ONE
English image prompt for an atmospheric horror image illustrating this moment.
NO text in the image. Photographic, dark, eerie. Describe environment,
lighting, time of day, key visual element. ~25 words. Plain text only,
no quotes, no preamble.

Arabic paragraph:
{arabic_text}

Output:
"""


def shot_seed(title: str, index: int) -> int:
    """Deterministic seed per (title, shot_index). Stable across runs."""
    h = hashlib.sha256(f"{title}::{index}".encode("utf-8")).hexdigest()
    return int(h[:8], 16)  # 32-bit unsigned


def _sentence_end_indices(timings: list[WordTiming]) -> set[int]:
    """Word indices whose token ends with a sentence-end character."""
    ends: set[int] = set()
    for i, wt in enumerate(timings):
        if wt.word and wt.word.strip() and wt.word.strip()[-1] in SENTENCE_END_CHARS:
            ends.add(i)
    if timings:
        ends.add(len(timings) - 1)  # always include the very last word
    return ends


def chunk_by_timing(
    timings: list[WordTiming],
    target_ms: int,
    sentence_ends: set[int],
) -> list[dict]:
    """Walk word timings; close chunk near `target_ms`, snapping to sentence ends.

    Returns list of {start_ms, end_ms, first_word_index, last_word_index}.
    """
    if not timings:
        return []
    chunks: list[dict] = []
    chunk_start_idx = 0
    chunk_start_ms = timings[0].offset_ms
    for i, wt in enumerate(timings):
        elapsed = (wt.offset_ms + wt.duration_ms) - chunk_start_ms
        is_sentence_end = i in sentence_ends
        is_last_word = i == len(timings) - 1
        if (elapsed >= target_ms and is_sentence_end) or is_last_word:
            chunks.append({
                "start_ms": chunk_start_ms,
                "end_ms": wt.offset_ms + wt.duration_ms,
                "first_word_index": chunk_start_idx,
                "last_word_index": i,
            })
            if not is_last_word:
                chunk_start_idx = i + 1
                chunk_start_ms = timings[i + 1].offset_ms
    return chunks


def _arabic_text_for_chunk(timings: list[WordTiming], chunk: dict) -> str:
    words = [t.word for t in timings[chunk["first_word_index"] : chunk["last_word_index"] + 1]]
    return " ".join(w for w in words if w.strip())


def generate_shots(
    gemini,
    script: Script,
    timings: list[WordTiming],
    out_path: Path,
    target_segment_ms: int = 18000,
) -> list[Shot]:
    """Produce shots.json. Resumable (skips if file exists)."""
    if out_path.exists():
        return [Shot.from_dict(d) for d in json.loads(out_path.read_text(encoding="utf-8"))]

    sentence_ends = _sentence_end_indices(timings)
    chunks = chunk_by_timing(timings, target_segment_ms, sentence_ends)

    shots: list[Shot] = []
    for i, chunk in enumerate(chunks):
        arabic = _arabic_text_for_chunk(timings, chunk)
        prompt = PROMPT_TRANSLATE_TEMPLATE.format(
            global_setting=script.global_setting,
            arabic_text=arabic,
        )
        english_core = gemini.complete(prompt).strip()
        # strip surrounding quotes if Gemini ignored instructions
        english_core = english_core.strip('"\'')
        english_full = f"{english_core}, {STYLE_SUFFIX}"
        shots.append(Shot(
            index=i + 1,
            start_ms=chunk["start_ms"],
            end_ms=chunk["end_ms"],
            arabic_text=arabic,
            english_prompt=english_full,
            negative_prompt=NEGATIVE_PROMPT,
            seed=shot_seed(script.title, i),
        ))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps([s.to_dict() for s in shots], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return shots
```

- [ ] **Step 4: Run tests, verify pass**

```bash
uv run pytest tests/test_shots.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline/shots.py tests/test_shots.py
git commit -m "feat(shots): timing-aware scene splitter with Gemini prompt translation"
```

---

## Task 12: Image generator (pipeline/images.py)

Wraps `mflux` (Flux.1 dev on Apple Silicon). Resumable per shot. Supports `reroll` to regenerate specific shots with bumped seeds.

**Files:**
- Create: `pipeline/images.py`
- Create: `tests/test_images.py`

- [ ] **Step 1: Add 1×1 PNG fixture**

```bash
python -c "from PIL import Image; Image.new('RGB',(1,1),'black').save('tests/fixtures/pixel.png')"
```

- [ ] **Step 2: Write failing test**

Create `tests/test_images.py`:

```python
"""Image generator tests. Flux is fully mocked."""
from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.images import generate_images
from pipeline.types import Shot


def _shots(n: int) -> list[Shot]:
    return [
        Shot(index=i + 1, start_ms=i * 1000, end_ms=(i + 1) * 1000,
             arabic_text="x", english_prompt=f"prompt {i+1}",
             negative_prompt="neg", seed=1000 + i)
        for i in range(n)
    ]


def _fake_flux(monkeypatch, fixtures_dir: Path):
    """Replace mflux call with a function that copies the pixel fixture."""
    sample = (fixtures_dir / "pixel.png").read_bytes()
    calls: list[dict] = []

    def fake_render(prompt, negative_prompt, seed, steps, guidance, width, height, out_path: Path):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(sample)
        calls.append({"prompt": prompt, "seed": seed, "out": str(out_path)})

    monkeypatch.setattr("pipeline.images._render_image", fake_render)
    return calls


def test_generates_all_images(monkeypatch, tmp_run_dir: Path, fixtures_dir: Path):
    calls = _fake_flux(monkeypatch, fixtures_dir)
    images_dir = tmp_run_dir / "images"
    generate_images(
        shots=_shots(3),
        images_dir=images_dir,
        steps=25, guidance=3.5, width=1280, height=720,
    )
    assert (images_dir / "01.png").exists()
    assert (images_dir / "02.png").exists()
    assert (images_dir / "03.png").exists()
    assert len(calls) == 3


def test_skips_existing_images(monkeypatch, tmp_run_dir: Path, fixtures_dir: Path):
    calls = _fake_flux(monkeypatch, fixtures_dir)
    images_dir = tmp_run_dir / "images"
    images_dir.mkdir()
    (images_dir / "01.png").write_bytes(b"existing")
    generate_images(
        shots=_shots(3), images_dir=images_dir,
        steps=25, guidance=3.5, width=1280, height=720,
    )
    # Only 02 and 03 should be re-rendered
    assert len(calls) == 2
    seeds = [c["seed"] for c in calls]
    assert 1000 not in seeds  # shot 1 was skipped


def test_reroll_regenerates_with_bumped_seed(monkeypatch, tmp_run_dir: Path, fixtures_dir: Path):
    calls = _fake_flux(monkeypatch, fixtures_dir)
    images_dir = tmp_run_dir / "images"
    images_dir.mkdir()
    (images_dir / "01.png").write_bytes(b"existing")
    (images_dir / "02.png").write_bytes(b"existing")
    (images_dir / "03.png").write_bytes(b"existing")
    generate_images(
        shots=_shots(3), images_dir=images_dir,
        steps=25, guidance=3.5, width=1280, height=720,
        reroll_indices=[2],
    )
    assert len(calls) == 1
    assert calls[0]["seed"] == 1001 + 10_000  # bumped from original seed (1001 for index 2)
```

- [ ] **Step 3: Run, verify failure**

```bash
uv run pytest tests/test_images.py -v
```

Expected: ImportError.

- [ ] **Step 4: Implement `pipeline/images.py`**

```python
"""Stage 5: image generation via Flux.1 dev (mflux on Apple Silicon)."""
from __future__ import annotations

from pathlib import Path

from pipeline.types import Shot

REROLL_SEED_BUMP = 10_000


def _render_image(
    prompt: str,
    negative_prompt: str,
    seed: int,
    steps: int,
    guidance: float,
    width: int,
    height: int,
    out_path: Path,
) -> None:
    """Run mflux. Replaceable in tests via monkeypatch."""
    # mflux ≥ 0.4 API. Adjust if upstream API changes.
    from mflux import Config, Flux1, ModelConfig

    flux = Flux1(
        model_config=ModelConfig.from_alias("dev"),
        quantize=8,  # int8 quant; fits comfortably in 48GB unified memory and is faster
    )
    image = flux.generate_image(
        seed=seed,
        prompt=prompt,
        config=Config(
            num_inference_steps=steps,
            guidance=guidance,
            height=height,
            width=width,
        ),
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path=out_path, export_json_metadata=False)


def _shot_filename(images_dir: Path, index: int) -> Path:
    return images_dir / f"{index:02d}.png"


def generate_images(
    shots: list[Shot],
    images_dir: Path,
    steps: int,
    guidance: float,
    width: int,
    height: int,
    reroll_indices: list[int] | None = None,
) -> None:
    """Render each shot to images_dir/NN.png. Resumable.

    reroll_indices: 1-based shot indices to force regenerate; their seeds get bumped by REROLL_SEED_BUMP.
    """
    images_dir.mkdir(parents=True, exist_ok=True)
    reroll_set = set(reroll_indices or [])
    for shot in shots:
        out_path = _shot_filename(images_dir, shot.index)
        if out_path.exists() and shot.index not in reroll_set:
            continue
        seed = shot.seed + (REROLL_SEED_BUMP if shot.index in reroll_set else 0)
        _render_image(
            prompt=shot.english_prompt,
            negative_prompt=shot.negative_prompt,
            seed=seed,
            steps=steps,
            guidance=guidance,
            width=width,
            height=height,
            out_path=out_path,
        )
```

- [ ] **Step 5: Run tests, verify pass**

```bash
uv run pytest tests/test_images.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add pipeline/images.py tests/test_images.py tests/fixtures/pixel.png
git commit -m "feat(images): mflux Flux.1 dev wrapper, resumable + reroll"
```

---

## Task 13: Music selector (pipeline/music.py)

Reads `assets/music/tracks.json`, filters by mood, picks one randomly, copies it into the run directory as `music_track.mp3`.

**Files:**
- Create: `pipeline/music.py`
- Create: `tests/test_music.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_music.py`:

```python
"""Music selector tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline.music import select_music_track


def _seed_bundle(bundle_dir: Path):
    bundle_dir.mkdir(parents=True, exist_ok=True)
    (bundle_dir / "drone-01.mp3").write_bytes(b"drone-content")
    (bundle_dir / "dread-01.mp3").write_bytes(b"dread-content")
    tracks = [
        {"filename": "drone-01.mp3", "duration_s": 300, "mood": "drone",
         "license": "CC0", "source_url": "https://x", "attribution": None},
        {"filename": "dread-01.mp3", "duration_s": 280, "mood": "dread",
         "license": "CC0", "source_url": "https://y", "attribution": None},
    ]
    (bundle_dir / "tracks.json").write_text(json.dumps(tracks))


def test_picks_track_matching_mood(tmp_path: Path, tmp_run_dir: Path):
    bundle = tmp_path / "music"
    _seed_bundle(bundle)
    out = tmp_run_dir / "music_track.mp3"
    select_music_track(bundle_dir=bundle, mood="dread", out_path=out, rng_seed=0)
    assert out.read_bytes() == b"dread-content"


def test_skips_if_already_present(tmp_path: Path, tmp_run_dir: Path):
    bundle = tmp_path / "music"
    _seed_bundle(bundle)
    out = tmp_run_dir / "music_track.mp3"
    out.write_bytes(b"prefilled")
    select_music_track(bundle_dir=bundle, mood="dread", out_path=out, rng_seed=0)
    assert out.read_bytes() == b"prefilled"


def test_raises_if_no_track_for_mood(tmp_path: Path, tmp_run_dir: Path):
    bundle = tmp_path / "music"
    _seed_bundle(bundle)
    out = tmp_run_dir / "music_track.mp3"
    with pytest.raises(RuntimeError):
        select_music_track(bundle_dir=bundle, mood="cosmic", out_path=out, rng_seed=0)


def test_raises_if_bundle_missing(tmp_path: Path, tmp_run_dir: Path):
    out = tmp_run_dir / "music_track.mp3"
    with pytest.raises(FileNotFoundError):
        select_music_track(
            bundle_dir=tmp_path / "doesnotexist",
            mood="dread", out_path=out, rng_seed=0,
        )
```

- [ ] **Step 2: Run, verify failure**

```bash
uv run pytest tests/test_music.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `pipeline/music.py`**

```python
"""Stage 6: music selection from a hand-curated CC0/CC-BY bundle."""
from __future__ import annotations

import json
import random
import shutil
from pathlib import Path


def select_music_track(
    bundle_dir: Path,
    mood: str,
    out_path: Path,
    rng_seed: int | None = None,
) -> None:
    """Pick a track matching `mood` and copy it to `out_path`. Resumable."""
    if out_path.exists():
        return
    if not bundle_dir.exists():
        raise FileNotFoundError(f"music bundle dir not found: {bundle_dir}")
    tracks_json = bundle_dir / "tracks.json"
    if not tracks_json.exists():
        raise FileNotFoundError(f"tracks.json missing in {bundle_dir}")
    tracks = json.loads(tracks_json.read_text())
    candidates = [t for t in tracks if t["mood"] == mood]
    if not candidates:
        raise RuntimeError(f"no tracks for mood={mood} in bundle (have {sorted({t['mood'] for t in tracks})})")
    rng = random.Random(rng_seed)
    chosen = rng.choice(candidates)
    src = bundle_dir / chosen["filename"]
    if not src.exists():
        raise FileNotFoundError(f"track file missing: {src}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, out_path)
```

- [ ] **Step 4: Run tests, verify pass**

```bash
uv run pytest tests/test_music.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline/music.py tests/test_music.py
git commit -m "feat(music): mood-matched track selection from local bundle"
```

---

## Task 14: Captions generator (pipeline/captions.py)

Generate `.srt` from word timings. Group into 6–10 word lines, max 4 seconds each, never break mid-sentence. Optional `.ass` burn-in file.

**Files:**
- Create: `pipeline/captions.py`
- Create: `tests/test_captions.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_captions.py`:

```python
"""Captions generator tests."""
from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.captions import (
    SENTENCE_END_CHARS,
    chunk_into_caption_lines,
    format_srt,
    generate_captions,
)
from pipeline.types import WordTiming


def _wt(word, off, dur=400):
    return WordTiming(word=word, offset_ms=off, duration_ms=dur)


def test_chunk_respects_max_words():
    timings = [_wt(f"w{i}", i * 200, 200) for i in range(20)]
    lines = chunk_into_caption_lines(timings, max_words=10, max_duration_ms=4000)
    for line in lines:
        assert len(line["words"]) <= 10


def test_chunk_respects_max_duration():
    timings = [_wt(f"w{i}", i * 1000, 1000) for i in range(10)]  # each word 1s
    lines = chunk_into_caption_lines(timings, max_words=10, max_duration_ms=4000)
    for line in lines:
        assert (line["end_ms"] - line["start_ms"]) <= 4500  # small tolerance


def test_chunk_breaks_at_sentence_end():
    timings = [_wt("w1", 0), _wt("w2.", 500), _wt("w3", 1000), _wt("w4", 1500)]
    lines = chunk_into_caption_lines(timings, max_words=10, max_duration_ms=10_000)
    assert len(lines) == 2
    assert lines[0]["words"][-1].word.endswith(".")


def test_format_srt_indexing():
    lines = [
        {"start_ms": 0, "end_ms": 1500, "text": "السطر الأول"},
        {"start_ms": 1500, "end_ms": 3000, "text": "السطر الثاني"},
    ]
    srt = format_srt(lines)
    assert srt.startswith("1\n")
    assert "السطر الأول" in srt
    assert "00:00:00,000 --> 00:00:01,500" in srt
    assert "\n2\n" in srt
    assert "00:00:01,500 --> 00:00:03,000" in srt


def test_generate_captions_writes_srt(tmp_run_dir: Path):
    timings = [_wt("كلمة", 0), _wt("ثانية.", 500), _wt("ثالثة", 1000)]
    srt_path = tmp_run_dir / "captions.ar.srt"
    generate_captions(
        timings=timings, srt_path=srt_path, ass_path=None,
        font="Cairo-Bold", font_size=60,
    )
    assert srt_path.exists()
    text = srt_path.read_text(encoding="utf-8")
    assert "كلمة" in text


def test_generate_captions_writes_ass_when_requested(tmp_run_dir: Path):
    timings = [_wt("كلمة", 0), _wt("ثانية.", 500)]
    srt_path = tmp_run_dir / "captions.ar.srt"
    ass_path = tmp_run_dir / "captions.ar.ass"
    generate_captions(
        timings=timings, srt_path=srt_path, ass_path=ass_path,
        font="Cairo-Bold", font_size=60,
    )
    assert ass_path.exists()
    text = ass_path.read_text(encoding="utf-8")
    assert "[Script Info]" in text
    assert "Cairo-Bold" in text


def test_generate_captions_skips_when_srt_exists(tmp_run_dir: Path):
    timings = [_wt("ك", 0)]
    srt_path = tmp_run_dir / "captions.ar.srt"
    srt_path.write_text("preexisting", encoding="utf-8")
    generate_captions(
        timings=timings, srt_path=srt_path, ass_path=None,
        font="Cairo-Bold", font_size=60,
    )
    assert srt_path.read_text() == "preexisting"
```

- [ ] **Step 2: Run, verify failure**

```bash
uv run pytest tests/test_captions.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `pipeline/captions.py`**

```python
"""Stage 7: caption generation. SRT (default) + optional .ass for FFmpeg burn-in."""
from __future__ import annotations

from pathlib import Path

from pipeline.types import WordTiming

SENTENCE_END_CHARS = {".", "؟", "!", "…"}


def _is_sentence_end(word: str) -> bool:
    return bool(word) and word.strip()[-1:] in SENTENCE_END_CHARS


def chunk_into_caption_lines(
    timings: list[WordTiming],
    max_words: int = 10,
    max_duration_ms: int = 4000,
) -> list[dict]:
    """Group word timings into caption lines.

    Rules:
    - <= max_words words per line
    - <= max_duration_ms duration per line
    - Break at sentence-end words when possible (preferred boundary)
    """
    if not timings:
        return []
    lines: list[dict] = []
    current: list[WordTiming] = []
    current_start = timings[0].offset_ms
    for wt in timings:
        if not current:
            current_start = wt.offset_ms
        current.append(wt)
        elapsed = (wt.offset_ms + wt.duration_ms) - current_start
        too_long = elapsed >= max_duration_ms
        too_many = len(current) >= max_words
        sentence_break = _is_sentence_end(wt.word)

        should_close = (sentence_break and len(current) >= 3) or too_long or too_many
        if should_close:
            lines.append({
                "start_ms": current_start,
                "end_ms": wt.offset_ms + wt.duration_ms,
                "words": list(current),
                "text": " ".join(w.word for w in current).strip(),
            })
            current = []
    if current:
        last = current[-1]
        lines.append({
            "start_ms": current[0].offset_ms,
            "end_ms": last.offset_ms + last.duration_ms,
            "words": list(current),
            "text": " ".join(w.word for w in current).strip(),
        })
    return lines


def _ms_to_srt_time(ms: int) -> str:
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def format_srt(lines: list[dict]) -> str:
    out: list[str] = []
    for i, line in enumerate(lines, start=1):
        out.append(str(i))
        out.append(f"{_ms_to_srt_time(line['start_ms'])} --> {_ms_to_srt_time(line['end_ms'])}")
        out.append(line["text"])
        out.append("")  # blank line separator
    return "\n".join(out)


def _ms_to_ass_time(ms: int) -> str:
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    cs = ms // 10  # centiseconds
    return f"{h:01d}:{m:02d}:{s:02d}.{cs:02d}"


def format_ass(lines: list[dict], font: str, font_size: int) -> str:
    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "PlayResX: 1920\n"
        "PlayResY: 1080\n"
        "WrapStyle: 0\n"
        "ScaledBorderAndShadow: yes\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, "
        "BackColour, Bold, Italic, BorderStyle, Outline, Shadow, Alignment, "
        "MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,{font},{font_size},&H00FFFFFF,&H00000000,"
        f"&H80000000,1,0,3,4,0,2,40,40,180,1\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    events: list[str] = []
    for line in lines:
        events.append(
            f"Dialogue: 0,{_ms_to_ass_time(line['start_ms'])},"
            f"{_ms_to_ass_time(line['end_ms'])},Default,,0,0,0,,{line['text']}"
        )
    return header + "\n".join(events) + "\n"


def generate_captions(
    timings: list[WordTiming],
    srt_path: Path,
    ass_path: Path | None,
    font: str,
    font_size: int,
) -> None:
    """Resumable: skips if srt_path already exists. .ass written if path given."""
    if srt_path.exists():
        return
    lines = chunk_into_caption_lines(timings)
    srt_path.parent.mkdir(parents=True, exist_ok=True)
    srt_path.write_text(format_srt(lines), encoding="utf-8")
    if ass_path is not None:
        ass_path.write_text(format_ass(lines, font=font, font_size=font_size), encoding="utf-8")
```

- [ ] **Step 4: Run tests, verify pass**

```bash
uv run pytest tests/test_captions.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline/captions.py tests/test_captions.py
git commit -m "feat(captions): SRT + optional .ass generation from word timings"
```

---

## Task 15: Video assembler (pipeline/assemble.py)

The most complex module. Builds the FFmpeg filter graph: per-shot Ken Burns motion (alternating direction), `xfade` crossfades, voice + music sidechain ducking, fade-in/out, optional caption burn-in. The actual `ffmpeg.run()` is isolated in `_run_ffmpeg` for testability.

**Files:**
- Create: `pipeline/assemble.py`
- Create: `tests/test_assemble.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_assemble.py`:

```python
"""Assembler tests. FFmpeg run is mocked; we verify the command-line graph."""
from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.assemble import (
    KEN_BURNS_PATTERNS,
    assemble_video,
    build_filter_graph,
    pick_motion_pattern,
)
from pipeline.types import Shot


def _shots(durations_ms: list[int]) -> list[Shot]:
    out: list[Shot] = []
    cursor = 0
    for i, d in enumerate(durations_ms):
        out.append(Shot(
            index=i + 1, start_ms=cursor, end_ms=cursor + d,
            arabic_text="", english_prompt="", negative_prompt="", seed=0,
        ))
        cursor += d
    return out


def test_motion_pattern_cycles():
    assert pick_motion_pattern(0) == KEN_BURNS_PATTERNS[0]
    assert pick_motion_pattern(1) == KEN_BURNS_PATTERNS[1]
    assert pick_motion_pattern(4) == KEN_BURNS_PATTERNS[0]  # cycles


def test_filter_graph_has_one_zoompan_per_shot():
    graph = build_filter_graph(
        shots=_shots([5000, 4000]),
        output_w=1920, output_h=1080,
        crossfade_ms=800,
        burn_caption_ass=None,
    )
    assert graph.count("zoompan=") == 2


def test_filter_graph_includes_xfade_between_shots():
    graph = build_filter_graph(
        shots=_shots([5000, 4000, 3000]),
        output_w=1920, output_h=1080, crossfade_ms=800,
        burn_caption_ass=None,
    )
    # 3 shots → 2 xfade nodes
    assert graph.count("xfade=") == 2


def test_filter_graph_includes_subtitles_when_burn_in_set():
    graph = build_filter_graph(
        shots=_shots([5000]),
        output_w=1920, output_h=1080, crossfade_ms=800,
        burn_caption_ass=Path("/tmp/captions.ass"),
    )
    assert "subtitles=" in graph
    assert "captions.ass" in graph


def test_assemble_invokes_ffmpeg_with_expected_inputs(monkeypatch, tmp_run_dir: Path):
    captured: dict = {}

    def fake_run(args: list[str]):
        captured["args"] = args

    monkeypatch.setattr("pipeline.assemble._run_ffmpeg", fake_run)

    images_dir = tmp_run_dir / "images"
    images_dir.mkdir()
    (images_dir / "01.png").write_bytes(b"x")
    (images_dir / "02.png").write_bytes(b"x")
    narration = tmp_run_dir / "narration.mp3"
    narration.write_bytes(b"x")
    music = tmp_run_dir / "music_track.mp3"
    music.write_bytes(b"x")

    assemble_video(
        shots=_shots([5000, 4000]),
        images_dir=images_dir,
        narration_path=narration,
        music_path=music,
        out_path=tmp_run_dir / "final.mp4",
        burn_caption_ass=None,
        output_width=1920, output_height=1080,
        crossfade_ms=800, music_duck_db=-18, music_silence_db=-8,
        fade_in_s=3, fade_out_s=3,
    )
    args = captured["args"]
    assert "-i" in args
    assert str(narration) in args
    assert str(music) in args
    assert any("01.png" in a for a in args)
    assert any("02.png" in a for a in args)
    assert str(tmp_run_dir / "final.mp4") in args


def test_assemble_skips_when_output_exists(monkeypatch, tmp_run_dir: Path):
    called = {"n": 0}
    monkeypatch.setattr("pipeline.assemble._run_ffmpeg", lambda args: called.update(n=called["n"] + 1))
    out = tmp_run_dir / "final.mp4"
    out.write_bytes(b"existing")
    assemble_video(
        shots=_shots([5000]), images_dir=tmp_run_dir, narration_path=tmp_run_dir / "n.mp3",
        music_path=tmp_run_dir / "m.mp3", out_path=out, burn_caption_ass=None,
        output_width=1920, output_height=1080, crossfade_ms=800,
        music_duck_db=-18, music_silence_db=-8, fade_in_s=3, fade_out_s=3,
    )
    assert called["n"] == 0
```

- [ ] **Step 2: Run, verify failure**

```bash
uv run pytest tests/test_assemble.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `pipeline/assemble.py`**

```python
"""Stage 8: video assembly via FFmpeg."""
from __future__ import annotations

import subprocess
from pathlib import Path

from pipeline.types import Shot

# Ken Burns motion patterns. zoompan filter syntax:
# (z, x, y) — z is zoom factor, x/y are crop offsets within the source.
# Each pattern returns (z, x, y) expressions over normalized progress t (0→1).
KEN_BURNS_PATTERNS: list[tuple[str, str, str]] = [
    # 0: zoom in, hold center
    ("1.0+0.10*on/d", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),
    # 1: zoom out + pan right
    ("1.10-0.10*on/d", "(iw-iw/zoom)*on/d", "ih/2-(ih/zoom/2)"),
    # 2: zoom in + pan left
    ("1.0+0.10*on/d", "(iw-iw/zoom)*(1-on/d)", "ih/2-(ih/zoom/2)"),
    # 3: zoom in + pan down
    ("1.0+0.10*on/d", "iw/2-(iw/zoom/2)", "(ih-ih/zoom)*on/d"),
]


def pick_motion_pattern(shot_index_zero_based: int) -> tuple[str, str, str]:
    return KEN_BURNS_PATTERNS[shot_index_zero_based % len(KEN_BURNS_PATTERNS)]


def build_filter_graph(
    shots: list[Shot],
    output_w: int,
    output_h: int,
    crossfade_ms: int,
    burn_caption_ass: Path | None,
) -> str:
    """Build the FFmpeg -filter_complex graph string.

    Inputs (in order):
      [0:v]…[N-1:v]: still images, one per shot
      [N:a] narration mp3
      [N+1:a] music mp3
    Output:
      [vout] [aout]
    """
    parts: list[str] = []
    # Per-shot zoompan + scale to output resolution.
    for i, shot in enumerate(shots):
        duration_s = max((shot.end_ms - shot.start_ms) / 1000.0, 0.2)
        z, x, y = pick_motion_pattern(i)
        # Zoompan: 30 fps, total frames = duration_s * 30.
        d_frames = int(duration_s * 30)
        parts.append(
            f"[{i}:v]scale={output_w * 2}:{output_h * 2},"
            f"zoompan=z='{z}':x='{x}':y='{y}':d={d_frames}:s={output_w}x{output_h}:fps=30,"
            f"setpts=PTS-STARTPTS,format=yuv420p[v{i}]"
        )
    # Crossfade chain: v0 + v1 → vab; vab + v2 → vabc; ...
    crossfade_s = crossfade_ms / 1000.0
    if len(shots) == 1:
        last_label = "v0"
    else:
        cumulative = (shots[0].end_ms - shots[0].start_ms) / 1000.0
        last_label = "v0"
        for i in range(1, len(shots)):
            new_label = f"vx{i}"
            offset = max(cumulative - crossfade_s, 0.0)
            parts.append(
                f"[{last_label}][v{i}]xfade=transition=fade:"
                f"duration={crossfade_s}:offset={offset:.3f}[{new_label}]"
            )
            cumulative += (shots[i].end_ms - shots[i].start_ms) / 1000.0 - crossfade_s
            last_label = new_label

    # Optional subtitle burn-in.
    if burn_caption_ass is not None:
        # Escape colon and backslash for ffmpeg filter arg.
        ass_path = str(burn_caption_ass).replace("\\", "\\\\").replace(":", r"\:")
        parts.append(f"[{last_label}]subtitles='{ass_path}'[vout]")
    else:
        parts.append(f"[{last_label}]copy[vout]")

    # Audio: narration is [N:a]; music is [N+1:a]. Sidechain ducks music by narration.
    n = len(shots)
    parts.append(
        f"[{n+1}:a]aloop=loop=-1:size=2e+09[mloop];"
        f"[mloop][{n}:a]sidechaincompress=threshold=0.05:ratio=8:attack=20:release=300[ducked];"
        f"[{n}:a][ducked]amix=inputs=2:duration=first:dropout_transition=0[aout]"
    )
    return ";".join(parts)


def _run_ffmpeg(args: list[str]) -> None:
    """Replaceable in tests via monkeypatch."""
    subprocess.run(args, check=True)


def assemble_video(
    shots: list[Shot],
    images_dir: Path,
    narration_path: Path,
    music_path: Path,
    out_path: Path,
    burn_caption_ass: Path | None,
    output_width: int,
    output_height: int,
    crossfade_ms: int,
    music_duck_db: int,
    music_silence_db: int,
    fade_in_s: int,
    fade_out_s: int,
) -> None:
    """Resumable: skips if out_path already exists."""
    if out_path.exists():
        return
    out_path.parent.mkdir(parents=True, exist_ok=True)

    args: list[str] = ["ffmpeg", "-y"]
    # Image inputs — each shot is a still input with a -loop 1 flag and matching duration.
    for shot in shots:
        duration_s = max((shot.end_ms - shot.start_ms) / 1000.0, 0.2)
        args += [
            "-loop", "1",
            "-t", f"{duration_s:.3f}",
            "-i", str(images_dir / f"{shot.index:02d}.png"),
        ]
    args += ["-i", str(narration_path)]
    args += ["-i", str(music_path)]

    graph = build_filter_graph(
        shots=shots, output_w=output_width, output_h=output_height,
        crossfade_ms=crossfade_ms, burn_caption_ass=burn_caption_ass,
    )
    args += [
        "-filter_complex", graph,
        "-map", "[vout]",
        "-map", "[aout]",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        str(out_path),
    ]
    _run_ffmpeg(args)
```

- [ ] **Step 4: Run tests, verify pass**

```bash
uv run pytest tests/test_assemble.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline/assemble.py tests/test_assemble.py
git commit -m "feat(assemble): FFmpeg ken-burns + xfade + audio mix pipeline"
```

---

## Task 16: CLI orchestrator (run.py)

The single entry point. Wires every stage together. Detects resume state from disk. Supports manual seed, auto seed, reroll, voice override, burn-captions, skip-images.

**Files:**
- Create: `run.py`
- Create: `tests/test_run_smoke.py`

- [ ] **Step 1: Write failing smoke test**

Create `tests/test_run_smoke.py`:

```python
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
    runs = [p for p in out_root.iterdir() if p.is_dir()]
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
```

- [ ] **Step 2: Run, verify failure**

```bash
uv run pytest tests/test_run_smoke.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `run.py`**

```python
"""Faceless pipeline CLI orchestrator.

Usage:
  python run.py                                  # auto theme, full pipeline
  python run.py --theme folkloric --seed "بئر"   # manual seed
  python run.py --resume out/2026-05-01-1430     # resume crashed run
  python run.py --reroll-images 23,27 --run-dir out/2026-05-01-1430
  python run.py --skip-images
  python run.py --voice ar-EG-ShakirNeural
  python run.py --burn-captions
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from pipeline.assemble import assemble_video
from pipeline.captions import generate_captions
from pipeline.config import Config, load_config
from pipeline.images import generate_images
from pipeline.llm import GeminiClient
from pipeline.music import select_music_track
from pipeline.runlog import RunLog
from pipeline.script import generate_script_with_uniqueness
from pipeline.seed import auto_seed, manual_seed, record_theme_use
from pipeline.shots import generate_shots
from pipeline.types import RunPaths, Script, Shot, ThemeSeed, WordTiming
from pipeline.voice import generate_narration


REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = REPO_ROOT / "config.yaml"
DEFAULT_OUT_ROOT = REPO_ROOT / "out"
DEFAULT_MUSIC_BUNDLE = REPO_ROOT / "assets" / "music"
DEFAULT_FONTS_DIR = REPO_ROOT / "assets" / "fonts"
PROJECT_THEME_LOG = DEFAULT_OUT_ROOT / "theme_log.json"
PROJECT_STORY_HISTORY = DEFAULT_OUT_ROOT / "story_history.jsonl"


def _build_gemini() -> GeminiClient:
    """Indirection so tests can monkeypatch."""
    return GeminiClient()


def _make_run_dir(out_root: Path) -> Path:
    out_root.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d-%H%M")
    run_dir = out_root / ts
    # Ensure uniqueness if two runs start in the same minute.
    suffix = 0
    while run_dir.exists():
        suffix += 1
        run_dir = out_root / f"{ts}-{suffix}"
    run_dir.mkdir()
    return run_dir


def _resolve_run_dir(args, out_root: Path) -> Path:
    if args.resume:
        return Path(args.resume).resolve()
    if args.run_dir:
        return Path(args.run_dir).resolve()
    return _make_run_dir(out_root)


def _stage_seed(args, gemini, log: RunLog, paths: RunPaths,
                project_theme_log: Path) -> ThemeSeed:
    seed_path = paths.root / "seed.json"
    if seed_path.exists():
        log.info("seed: already exists, skipping")
        return ThemeSeed.from_dict(json.loads(seed_path.read_text(encoding="utf-8")))
    if args.theme and args.seed:
        seed = manual_seed(args.theme, args.seed)
    elif args.theme and not args.seed:
        # Theme given, no premise — let auto_seed pick the premise but constrain to that theme.
        # Implemented inline: ask Gemini using AUTO_PREMISE_PROMPT format.
        from pipeline.seed import AUTO_PREMISE_PROMPT
        premise = gemini.complete(AUTO_PREMISE_PROMPT.format(theme=args.theme)).strip()
        seed = ThemeSeed(theme=args.theme, premise=premise)
    else:
        seed = auto_seed(gemini, project_theme_log)
    seed_path.write_text(json.dumps(seed.to_dict(), ensure_ascii=False, indent=2),
                         encoding="utf-8")
    record_theme_use(project_theme_log, seed.theme)
    return seed


def _stage_script(gemini, cfg: Config, seed: ThemeSeed, paths: RunPaths,
                  story_history: Path) -> Script:
    if paths.script_json.exists():
        return Script.from_dict(json.loads(paths.script_json.read_text(encoding="utf-8")))
    script = generate_script_with_uniqueness(
        gemini=gemini, seed=seed,
        target_words=cfg.script.word_count_target,
        tolerance=cfg.script.word_count_tolerance,
        enable_critique=cfg.script.enable_critique_pass,
        history_path=story_history,
        repetition_threshold=cfg.script.repetition_threshold,
    )
    paths.script_json.write_text(
        json.dumps(script.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return script


def _stage_voice(args, cfg: Config, script: Script, paths: RunPaths) -> list[WordTiming]:
    voice = args.voice or cfg.voice.name
    generate_narration(
        text=script.story,
        voice=voice, rate=cfg.voice.rate, pitch=cfg.voice.pitch,
        mp3_path=paths.narration_mp3, timings_path=paths.word_timings_json,
    )
    return [WordTiming.from_dict(d)
            for d in json.loads(paths.word_timings_json.read_text(encoding="utf-8"))]


def _stage_shots(gemini, script: Script, timings: list[WordTiming], paths: RunPaths) -> list[Shot]:
    return generate_shots(
        gemini=gemini, script=script, timings=timings,
        out_path=paths.shots_json,
    )


def _stage_images(args, cfg: Config, shots: list[Shot], paths: RunPaths) -> None:
    if args.skip_images:
        # Write tiny placeholder PNGs so downstream stages can still run.
        from PIL import Image
        paths.images_dir.mkdir(parents=True, exist_ok=True)
        for shot in shots:
            p = paths.images_dir / f"{shot.index:02d}.png"
            if not p.exists():
                Image.new("RGB", (cfg.flux.width, cfg.flux.height), "black").save(p)
        return
    reroll = []
    if args.reroll_images:
        reroll = [int(x) for x in args.reroll_images.split(",")]
    generate_images(
        shots=shots, images_dir=paths.images_dir,
        steps=cfg.flux.steps, guidance=cfg.flux.guidance,
        width=cfg.flux.width, height=cfg.flux.height,
        reroll_indices=reroll,
    )


def _stage_music(script: Script, music_bundle: Path, paths: RunPaths) -> None:
    select_music_track(
        bundle_dir=music_bundle, mood=script.music_mood,
        out_path=paths.music_track_mp3,
    )


def _stage_captions(args, cfg: Config, timings: list[WordTiming], paths: RunPaths) -> Path | None:
    burn = args.burn_captions or cfg.captions.burn_in
    ass_path = paths.captions_ass if burn else None
    generate_captions(
        timings=timings, srt_path=paths.captions_srt,
        ass_path=ass_path, font=cfg.captions.font, font_size=cfg.captions.font_size,
    )
    return ass_path if burn else None


def _stage_assemble(cfg: Config, shots: list[Shot], paths: RunPaths,
                    burn_caption_ass: Path | None) -> None:
    assemble_video(
        shots=shots,
        images_dir=paths.images_dir,
        narration_path=paths.narration_mp3,
        music_path=paths.music_track_mp3,
        out_path=paths.final_mp4,
        burn_caption_ass=burn_caption_ass,
        output_width=cfg.assemble.output_width,
        output_height=cfg.assemble.output_height,
        crossfade_ms=cfg.assemble.shot_crossfade_ms,
        music_duck_db=cfg.assemble.music_duck_db,
        music_silence_db=cfg.assemble.music_silence_db,
        fade_in_s=cfg.assemble.fade_in_s,
        fade_out_s=cfg.assemble.fade_out_s,
    )


def main_with_args(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Arabic horror faceless pipeline")
    p.add_argument("--theme", help="Theme tag (manual mode)")
    p.add_argument("--seed", help="Arabic premise (manual mode)")
    p.add_argument("--resume", help="Resume an existing run dir")
    p.add_argument("--run-dir", help="Use a specific run dir (advanced)")
    p.add_argument("--reroll-images", help="Comma-separated 1-based indices to regenerate")
    p.add_argument("--skip-images", action="store_true", help="Use placeholder images (dev only)")
    p.add_argument("--voice", help="Override Edge TTS voice (e.g. ar-EG-ShakirNeural)")
    p.add_argument("--burn-captions", action="store_true",
                   help="Burn captions into video (default: SRT only)")
    p.add_argument("--config", default=str(DEFAULT_CONFIG))
    p.add_argument("--out-root", default=str(DEFAULT_OUT_ROOT))
    p.add_argument("--music-bundle", default=str(DEFAULT_MUSIC_BUNDLE))
    args = p.parse_args(argv)

    cfg = load_config(Path(args.config))
    out_root = Path(args.out_root)
    music_bundle = Path(args.music_bundle)
    project_theme_log = out_root / "theme_log.json"
    project_story_history = out_root / "story_history.jsonl"

    run_dir = _resolve_run_dir(args, out_root)
    paths = RunPaths(root=run_dir)
    log = RunLog(run_dir)

    try:
        gemini = _build_gemini()
        log.info(f"run dir: {run_dir}")

        with log.stage("seed"):
            seed = _stage_seed(args, gemini, log, paths, project_theme_log)
        with log.stage("script"):
            script = _stage_script(gemini, cfg, seed, paths, project_story_history)
        with log.stage("voice"):
            timings = _stage_voice(args, cfg, script, paths)
        with log.stage("shots"):
            shots = _stage_shots(gemini, script, timings, paths)
        with log.stage("images"):
            _stage_images(args, cfg, shots, paths)
        with log.stage("music"):
            _stage_music(script, music_bundle, paths)
        with log.stage("captions"):
            burn_ass = _stage_captions(args, cfg, timings, paths)
        with log.stage("assemble"):
            _stage_assemble(cfg, shots, paths, burn_ass)
        log.info(f"DONE: {paths.final_mp4}")
        return 0
    except Exception as exc:
        log.error(f"FAILED: {type(exc).__name__}: {exc}")
        return 1
    finally:
        log.close()


def main() -> int:
    return main_with_args(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run smoke test, verify pass**

```bash
uv run pytest tests/test_run_smoke.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Run the full test suite to confirm nothing regressed**

```bash
uv run pytest -v
```

Expected: ~50+ tests, all passing.

- [ ] **Step 6: Commit**

```bash
git add run.py tests/test_run_smoke.py
git commit -m "feat(run): CLI orchestrator + end-to-end smoke test"
```

---

## Task 17: Music bundle setup script

A bash script that downloads ~20 CC0 / CC-BY atmospheric horror tracks and writes `tracks.json`. The track URLs are placeholder examples — the user (or this script) curates the final list manually because track selection is taste-driven and one-time.

**Files:**
- Create: `scripts/setup_music.sh`

- [ ] **Step 1: Write the script**

Create `scripts/setup_music.sh`:

```bash
#!/usr/bin/env bash
# Download a curated bundle of CC0 / CC-BY atmospheric horror tracks
# into assets/music/. Run once.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUNDLE_DIR="$REPO_ROOT/assets/music"
mkdir -p "$BUNDLE_DIR"

# Track list — replace these URLs with actual CC0/CC-BY tracks you've vetted.
# Format: filename|mood|license|source_url|attribution
# License must be CC0 or CC-BY (verify on source page before using).
# Recommended sources:
#   https://pixabay.com/music/search/horror%20ambient/
#   https://freemusicarchive.org/genre/Soundtrack/
TRACKS=(
  # MOOD: drone (long sustained tones, no melody)
  # "drone-01.mp3|drone|CC0|https://pixabay.com/.../drone-1.mp3|"
  # "drone-02.mp3|drone|CC0|https://pixabay.com/.../drone-2.mp3|"
  # MOOD: dread (low rumble, heartbeat-like)
  # "dread-01.mp3|dread|CC0|https://pixabay.com/.../dread-1.mp3|"
  # MOOD: cosmic (otherworldly, spacious)
  # "cosmic-01.mp3|cosmic|CC0|https://pixabay.com/.../cosmic-1.mp3|"
  # MOOD: discovery (slow tension build)
  # "discovery-01.mp3|discovery|CC0|https://pixabay.com/.../discovery-1.mp3|"
  : # placeholder — uncomment + populate before running
)

if [ ${#TRACKS[@]} -eq 0 ]; then
  echo "ERROR: TRACKS array is empty. Populate scripts/setup_music.sh with vetted CC0/CC-BY URLs first."
  echo "Recommended sources:"
  echo "  https://pixabay.com/music/search/horror%20ambient/"
  echo "  https://freemusicarchive.org/"
  exit 1
fi

JSON_ENTRIES=()
for entry in "${TRACKS[@]}"; do
  IFS='|' read -r filename mood license source_url attribution <<<"$entry"
  echo "Downloading $filename ..."
  curl -fsSL "$source_url" -o "$BUNDLE_DIR/$filename"
  duration_s=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$BUNDLE_DIR/$filename" | cut -d. -f1)
  attr_json="null"
  [ -n "$attribution" ] && attr_json="\"$attribution\""
  JSON_ENTRIES+=("{\"filename\":\"$filename\",\"duration_s\":$duration_s,\"mood\":\"$mood\",\"license\":\"$license\",\"source_url\":\"$source_url\",\"attribution\":$attr_json}")
done

# Write tracks.json
{
  echo "["
  for i in "${!JSON_ENTRIES[@]}"; do
    if [ "$i" -eq $((${#JSON_ENTRIES[@]} - 1)) ]; then
      echo "  ${JSON_ENTRIES[$i]}"
    else
      echo "  ${JSON_ENTRIES[$i]},"
    fi
  done
  echo "]"
} > "$BUNDLE_DIR/tracks.json"

echo "Bundle written to $BUNDLE_DIR with ${#TRACKS[@]} tracks."
```

- [ ] **Step 2: Make executable + sanity-check**

```bash
chmod +x scripts/setup_music.sh
bash -n scripts/setup_music.sh   # syntax check
./scripts/setup_music.sh         # should fail with the "populate" message
```

Expected: bash syntax check passes; running it prints the "populate" error and exits 1.

- [ ] **Step 3: Commit**

```bash
git add scripts/setup_music.sh
git commit -m "chore(scripts): music bundle setup script (URLs pending curation)"
```

---

## Task 18: Update `.gitignore` and `CLAUDE.md`

Final housekeeping.

**Files:**
- Modify: `.gitignore` (already has Python ignores from Task 0, just verify)
- Modify: `CLAUDE.md`

- [ ] **Step 1: Read current `CLAUDE.md`**

```bash
cat CLAUDE.md
```

- [ ] **Step 2: Replace `CLAUDE.md` content**

Overwrite `CLAUDE.md` with:

```markdown
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

This repo holds two unrelated codebases coexisting:

1. **Python pipeline** at the repo root (`pipeline/`, `tests/`, `run.py`, `pyproject.toml`) — the active MVP. Generates Arabic horror videos end-to-end (script → narration → images → assembly). See `docs/superpowers/specs/2026-05-01-arabic-horror-faceless-system-design.md` for design and `docs/superpowers/plans/2026-05-01-arabic-horror-faceless-system.md` for the build plan.
2. **Flutter app scaffold** (`lib/`, `pubspec.yaml`, `android/`, `ios/`, etc.) — untouched in MVP. Will become the dashboard in Phase 2+.

When working on the Python pipeline, **never modify Flutter files**. When working on Flutter, **never modify the Python pipeline**.

## Common commands (Python pipeline)

```bash
uv sync                                 # install Python deps
uv run pytest                           # run all tests
uv run pytest tests/test_seed.py -v     # single test file
uv run pytest -k test_chunk             # tests matching pattern
uv run python run.py --theme folkloric --seed "بئر قديم"   # run pipeline manually
uv run python run.py --skip-images      # dry-run with placeholder PNGs (fast)
```

## Common commands (Flutter app — unchanged from scaffold)

```bash
flutter pub get
flutter analyze
flutter test
flutter run -d chrome
```

Note: `lib/main.dart:31` and `:105` have invalid Dart (missing type names on `.fromSeed(...)` and `.center`) — `flutter analyze` will fail until these are fixed. Not blocking the Python work.

## Key invariants

- **External services are mocked in tests.** Every external API (Gemini, Edge TTS, mflux, FFmpeg) is wrapped behind a small interface; tests replace the function via `monkeypatch`. Never hit real APIs in tests.
- **All artifacts go through `out/<run-timestamp>/`.** Stages are resumable: if an artifact exists, the stage skips itself.
- **All Python files start with `from __future__ import annotations`.** Use `pathlib.Path` for paths; never `os.path`.
- **Imports are absolute from the package root** (`from pipeline.script import …`).
```

- [ ] **Step 3: Verify `.gitignore` already excludes Python and `out/`** (added in Task 0)

```bash
grep -E "^out/|__pycache__" .gitignore
```

Expected: matches present.

- [ ] **Step 4: Final smoke run + full test suite**

```bash
uv run pytest -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(claude): document Python + Flutter coexistence and dev commands"
```

---

## Done criteria

The MVP is complete when:

- [ ] `uv run pytest` passes with all tests green (target: 50+ tests).
- [ ] `uv run python run.py --skip-images --theme folkloric --seed "بئر قديم"` produces an `out/<timestamp>/final.mp4` file, end-to-end, with placeholder images.
- [ ] The user has populated `assets/music/` with at least 4 real CC-licensed tracks (one per mood) via `scripts/setup_music.sh`.
- [ ] The user has set `GEMINI_API_KEY` in their environment.
- [ ] The user has run the pipeline with real Flux (no `--skip-images`) and watched 3 finished videos.
- [ ] The user answers "yes, I would subscribe to this channel" to all 3 — at which point Phase 2 (YouTube uploader) brainstorming may begin.

---

## What this plan does NOT cover

Per spec §2 non-goals and §10 roadmap, the following are out of scope and need their own brainstorm → spec → plan cycles:

- YouTube Data API uploader
- Daily scheduler / GitHub Actions
- Multi-channel support
- Mobile dashboard (Flutter app + backend)
- Trend miner
- TikTok adaptation (vertical reframe + always-on burned captions)

Do not implement any of these as part of MVP.
