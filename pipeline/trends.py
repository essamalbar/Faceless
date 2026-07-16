"""Trend Engine — timely, ready-to-approve song briefs.

Distills what MENA is listening to right now (official YouTube trending music
charts for SA/EG/AE) plus the cultural calendar (the LLM reasons from today's
date) into original song briefs the user can create with one tap.

Originality guardrail: the trending titles are AUDIENCE-MOOD context, never
material — the prompt forbids covers, soundalikes, and artist imitations.
Spec: docs/superpowers/specs/2026-07-16-trend-engine-design.md.
"""
from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

import requests

_CHART_URL = "https://www.googleapis.com/youtube/v3/videos"
_TIMEOUT = 20

DEFAULT_REGIONS = ("SA", "EG", "AE")


class TrendsError(RuntimeError):
    """Brief generation failed (unusable LLM output after retry)."""


def fetch_trending_music(
    api_key: str,
    regions: tuple[str, ...] = DEFAULT_REGIONS,
    max_per: int = 8,
) -> list[dict]:
    """Official trending-music chart per region. A failing region is skipped
    (partial data beats none); every region failing returns [] and the brief
    generator works calendar-only."""
    out: list[dict] = []
    for region in regions:
        try:
            r = requests.get(_CHART_URL, params={
                "part": "snippet",
                "chart": "mostPopular",
                "videoCategoryId": "10",  # Music
                "regionCode": region,
                "maxResults": max_per,
                "key": api_key,
            }, timeout=_TIMEOUT)
            if r.status_code >= 400:
                print(f"[trends] chart {region} failed: {r.status_code}")
                continue
            for item in r.json().get("items", []):
                snip = item.get("snippet", {})
                out.append({
                    "title": str(snip.get("title", ""))[:120],
                    "channel": str(snip.get("channelTitle", ""))[:80],
                    "region": region,
                })
        except requests.RequestException as e:
            print(f"[trends] chart {region} error: {e}")
            continue
    return out


_BRIEFS_SYSTEM = """You are the idea engine of an AI music studio serving
Arabic-first audiences (Gulf, Egypt, Levant) plus some English content.

INPUT: today's date, a target language, and (optionally) the titles currently
trending on YouTube Music charts in Saudi Arabia, Egypt and the UAE — use them
ONLY to read the audience's current mood/genre appetite.

OUTPUT: a STRICT JSON array (no markdown, no commentary) of exactly {count}
song briefs. Each element:
  {{
    "title_idea": "short catchy song title in the target language",
    "theme": "ONE sentence song premise in the target language",
    "style_hint": "Suno-style comma-separated descriptor: genre, tempo with BPM, instrumentation, vocal, production era, mood + key",
    "language": "the target language code",
    "rationale": "ONE short line: why this idea is timely NOW"
  }}

RULES:
- ORIGINAL ideas that ride the moment (season, cultural calendar, the mood the
  charts reveal). NEVER a cover, copy, soundalike, or imitation of any listed
  track or artist — do not name them.
- Vary the ideas: different tempos, moods and sub-genres across the set.
- Consider the cultural calendar around the given date (religious seasons,
  national days, school/summer rhythms, weather).
"""


def _parse_briefs_json(raw: str) -> list[dict]:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?|\n?```$", "", raw, flags=re.MULTILINE).strip()
    if not raw.startswith("["):
        start, end = raw.find("["), raw.rfind("]")
        if start != -1 and end > start:
            raw = raw[start:end + 1]
    data = json.loads(raw, strict=False)
    if not isinstance(data, list):
        raise ValueError("briefs output is not a list")
    return data


def build_briefs(llm, trending: list[dict], *, language: str,
                 today: str, count: int = 6) -> list[dict]:
    """One LLM call → validated briefs. Retries once with a STRICT-JSON nudge;
    raises TrendsError when still unusable."""
    chart_lines = "\n".join(
        f"- [{t['region']}] {t['title']}" for t in trending[:24])
    user_msg = (
        f"Today's date: {today}\n"
        f"Target language: {language}\n"
        + (f"Currently trending (mood context only):\n{chart_lines}"
           if chart_lines else
           "(No chart data available — use the cultural calendar only.)")
    )
    system = _BRIEFS_SYSTEM.replace("{count}", str(count))

    last_err: Exception | None = None
    for attempt, msg in enumerate(
            [user_msg,
             user_msg + "\n\nIMPORTANT: reply with ONLY the raw JSON array."]):
        try:
            data = _parse_briefs_json(llm.complete(msg, system=system))
            briefs = []
            for item in data:
                if not isinstance(item, dict):
                    continue
                theme = str(item.get("theme") or "").strip()
                if not theme:
                    continue
                briefs.append({
                    "id": f"tb_{uuid.uuid4().hex[:8]}",
                    "title_idea": str(item.get("title_idea") or "")[:80],
                    "theme": theme[:300],
                    "style_hint": str(item.get("style_hint") or "")[:400],
                    "language": str(item.get("language") or language),
                    "rationale": str(item.get("rationale") or "")[:160],
                })
            if 3 <= len(briefs) <= 10:
                return briefs
            raise ValueError(f"got {len(briefs)} usable briefs")
        except Exception as e:
            last_err = e
            print(f"[trends] briefs attempt {attempt + 1} unusable: {e}")
    raise TrendsError(f"brief generation failed: {last_err}")


# --- per-user cache ---------------------------------------------------------

def cache_path(user_root: Path) -> Path:
    return user_root / "trend_briefs.json"


def load_cache(user_root: Path) -> dict | None:
    p = cache_path(user_root)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("briefs"):
            return data
        return None
    except (OSError, json.JSONDecodeError):
        return None


def save_cache(user_root: Path, generated_at: str, briefs: list[dict]) -> None:
    user_root.mkdir(parents=True, exist_ok=True)
    p = cache_path(user_root)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps({"generated_at": generated_at, "briefs": briefs},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)
