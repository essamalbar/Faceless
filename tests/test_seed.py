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
