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
