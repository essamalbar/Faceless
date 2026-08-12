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
    "أنت كاتب محتوى قصصي قصير باللغة العربية الفصحى. "
    "اقترح فرضية قصة قصيرة مشوّقة (جملة واحدة) ضمن الفئة التالية: {theme}. "
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
