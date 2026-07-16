# Trend Engine — Design Spec

**Date:** 2026-07-16
**Status:** Approved (walked through with user)
**Context:** Station 6 of the "best system" roadmap. Flips the creative burden
from "what should I make?" to "which of these do I approve?" — timely,
ready-to-approve song briefs from what's trending in MENA plus the cultural
calendar. Feeds the existing pipeline: brief → New Song (prefilled) → review
($0) → approve → render → (artist auto-publish) YouTube.

## Sources (both free, both proven)

1. **YouTube trending music charts** — official Data API
   `videos.list?chart=mostPopular&videoCategoryId=10` for regions **SA, EG,
   AE** (reuses the existing `YOUTUBE_API_KEY`; 1 quota unit per region —
   trivial). Verified live during design.
2. **Cultural calendar** — the LLM reasons from today's date (passed in)
   about seasonal/cultural moments (Eid, national days, Ramadan, summer…).
   No scraping.

## Originality guardrail

Briefs are **original songs riding a moment** — the prompt forbids covers,
copies, soundalikes, or naming/imitating the trending artists/tracks. The
trending titles are context ("what the audience is in the mood for"), not
material. Same posture as the import feature.

## Architecture

### `pipeline/trends.py` (new)

| Function | Responsibility |
|---|---|
| `fetch_trending_music(api_key, regions=("SA","EG","AE"), max_per=8) -> list[dict]` | official chart per region → `[{title, channel, region}]`; per-region failures skipped (partial data beats none); all regions failing → `[]` (LLM works calendar-only) |
| `build_briefs(llm, trending, *, language, today, count=6) -> list[dict]` | ONE LLM call (JSON contract like song_lyrics) → briefs `[{id, title_idea, theme, style_hint, language, rationale}]`; `id = tb_<8hex>`; parses fenced/messy JSON (reuse the strict=False + substring pattern); raises `TrendsError` on unusable output |
| `load_cache(user_root) / save_cache(user_root, briefs)` | `trend_briefs.json` per user: `{generated_at, briefs}` — atomic write, corrupt → None |

LLM system prompt (the contract): input = trending titles by region + today's
date + target language; output = STRICT JSON array of `count` briefs; each
theme is a one-sentence song premise; style_hint follows the Suno style shape
already used by presets; rationale is ONE short "why now" line; NO covers of
the listed tracks, no artist imitations.

### API (`pipeline/api.py`)

`GET /trends/briefs?refresh=0|1` (auth):
- cache fresh (< 12h, env `TRENDS_TTL_H`) and not refresh → cached.
- else: `fetch_trending_music` (missing YOUTUBE_API_KEY → empty trending,
  calendar-only) → `build_briefs` with `_build_song_llm()` → save cache.
- Response `{generated_at, briefs: [...]}`. LLM failure with a stale cache →
  return the stale cache (`stale: true`); no cache at all → 502.

### Flutter

- `TrendBrief` model + `client.trendBriefs({refresh})`.
- Song tab: **"✨ Trending now"** section above Your Songs — horizontal cards
  (~260w): title_idea (display font), rationale line (2 max), Create button
  → `NewSongScreen(initialTheme: theme, initialStyleHint: style_hint,
  initialLanguage: language)` (add the two new optional params; style only
  stamped when the field is empty — same rule as artist defaults). Refresh
  icon on the section title (spinner while regenerating). Section hides on
  fetch failure (never blocks the home screen).
- Bilingual `trend*` keys in BOTH ARB files.

## Error handling

- Region chart failure → skip region; all fail → calendar-only briefs.
- LLM unusable JSON → one retry with a "STRICT JSON" nudge, then TrendsError
  → 502 (or stale cache when available).
- Brief count from LLM ≠ requested → accept 3–10, else error.
- Home section is fire-and-forget: any client error hides the section.

## Testing (externals mocked)

- `tests/test_trends.py`: fetch (mocked requests) merges regions + skips
  failures; build_briefs parses fenced JSON, validates shape, retries once on
  garbage, raises after; cache round-trip + corrupt → None.
- `tests/test_api.py`: fresh cache honored; refresh regenerates; missing YT
  key → still 200 (calendar-only, mocked LLM); LLM failure + stale cache →
  stale payload; no cache + failure → 502.
- Flutter: analyzer zero errors; ARB parity green.

## Non-goals (v1)

- No scheduled generation (on-demand + cache; Cloud Scheduler can come with
  the learning loop); no TikTok/Twitter sources; no per-artist brief
  targeting (briefs are user-level; artist gets picked at Create time).
