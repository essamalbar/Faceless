# Song Producer Pass — style-prompt quality upgrade

**Date:** 2026-07-27
**Status:** Design approved; ready for implementation plan
**Scope:** Approach A ("Producer Pass") built in the shape of C (B is hooked, not built)

## Problem

Generated songs still sound "AI / bad" across the board — voice, melody,
lyrics, and mix. The audio engine itself (Suno V5.5 via Kie.ai) sets a hard
ceiling we cannot re-engineer, and it is weaker at Arabic vocals than English.
Within that ceiling, most of the obvious **free** levers are already in the
codebase:

- Negative tags are already sent (`run.py:1061`): `robotic vocal, autotune
  artifacts, off-key, muffled, low quality`.
- Take selection already picks the *longer* take to dodge Suno's ~20%
  truncation (`run.py:1118`) — defect avoidance, not quality ranking.
- Singability, mature register, and full tashkeel are already contracted in
  `song_lyrics.py`.
- Mastering is deliberately off (`song_assemble.py:5`, `-c:a copy`, "Suno is
  already at −14 LUFS").

The transformational levers — best-of-N takes (~$0.15) and a real reference
melody (cover mode) — were **ruled out** by the user (free-only, ~1 credit, no
reference track). So the design targets the single highest-leverage *free*
lever left: the **style prompt** sent to Suno, which is what most controls
whether output sounds professionally produced or generically AI.

Today the entire style prompt (genre and all) is invented from scratch by
whatever model the router lands on (`Anthropic → Gemini → Groq`), inside one
large JSON blob shared with lyrics generation. On a Gemini/Groq fallback, the
Suno steer is written by a weak model with no expert guardrails — an invisible
quality drain.

### Expectations (stated honestly)

Within the free-only budget, gains are **meaningful but incremental**, not a
total transformation. The design also makes a currently-invisible failure mode
visible: if production is silently running on the free-tier writer, that alone
explains a large share of the quality gap, and the fix is a config change
(set `ANTHROPIC_API_KEY`).

## Goals

1. Produce a professional-grade Suno `style` string for **every** song,
   regardless of genre or which writer model is available.
2. Attach genre-aware negative tags.
3. Make the resolved writer tier and the style source **visible** per run.
4. Keep everything **free** (no extra Suno spend; one small extra LLM call in
   the pre-approval stage) and **low-regression** (no downstream schema change).
5. Leave a contained seam so the optional post-production polish (Approach B)
   can be dropped in later behind a flag.

## Non-goals

- No best-of-N take generation (extra Suno spend — excluded by the user).
- No cover / reference-melody path (no reference track — excluded).
- No paid mastering service.
- No implementation of the ffmpeg master pass now (only its seam + config flag).

## Architecture

New focused module **`pipeline/song_style.py`** — one job: turn a song brief
into a professional Suno `style` string + matching negative tags. Callers use
two functions (`infer_genre`, `compose_style`); nothing imports its internals.

### Key idea — "quality spine + genre layer"

- **Quality spine** — genre-independent production + vocal-realism vocabulary
  plus an anti-AI negative set, injected into every song. This is the part most
  responsible for "sounds produced" vs "sounds AI".
- **Genre layer** — a curated recipe (instrumentation, tempo, vocal character,
  era) for ~12 genre families + a `generic` fallback, layered on the spine.

### Data flow (initial generation)

```
theme + style_hint + language/dialect
        │
        ▼
generate_song_script()  ── composes lyrics + title  (unchanged)
        │
        ▼
song_style.compose_style()  ← NEW producer pass (inside generate_song_script)
   • infer genre family (deterministic keyword match — no LLM)
   • load recipe = quality spine + genre layer
   • dedicated "music producer" LLM call on the strongest available model,
     grounded in the recipe; returns a polished style_prompt + negative_tags
   • deterministic fallback: if the call fails or looks weak, build the
     style_prompt straight from the recipe (so even Groq ships a good steer)
        │
        ▼
song.json  { style_prompt, negative_tags, style_source, writer_tier }
        │
        ▼
run.py submit_song_job(style=…, negative_tags=…)   (already wired)
```

`song.json` keeps the same keys plus additive fields, so the review screen,
edit-style, regenerate, and the worker submit path all keep working. The
producer pass runs on initial generate + regenerate only — never after a
manual style edit.

Because `song_import.py` (YouTube-import and upload-cover builders) also go
through `generate_song_script`, putting the producer pass **inside** that
function upgrades every path — create, regenerate, morning-drafts,
YouTube-import, upload-cover — with no per-path work and no coverage gap.

## Component detail

### `Recipe` shape

```python
@dataclass(frozen=True)
class Recipe:
    key: str                  # "arabic_ballad"
    aliases: tuple[str, ...]  # keywords that map a theme/style_hint here
    genre: str                # "Arabic pop ballad, contemporary MENA"
    tempo: str                # "slow, 66-76 BPM"
    instrumentation: str      # concrete, named instruments
    vocal: str                # timbre + delivery ({gender} filled in)
    era: str                  # production era / reference sound
    extra_negatives: str = "" # genre-specific things to exclude/remove
```

### Quality spine (injected into every genre)

- **Production:** `professionally mixed and mastered, radio-ready, high-fidelity
  studio production, warm analog low-end, airy detailed highs, wide natural
  stereo, balanced dynamics not over-compressed`
- **Vocal realism:** `expressive human lead vocal, natural breath and vibrato,
  emotional phrasing, intimate and present, real singer`
- **Shared negatives:** `robotic vocal, autotune artifacts, pitchy, off-key,
  muffled, muddy mix, low quality, MIDI-sounding instruments, karaoke backing
  track, amateur demo, digital harshness, boxy`

### Genre families (~12 + fallback)

`arabic_pop`, `arabic_ballad`, `khaleeji`, `tarab_classic`, `arabic_trap`
(mahraganat), `folk_shaabi`, `hiphop_rap`, `rnb_soul`, `pop`, `rock`,
`edm_electropop`, `cinematic_ost`, and `generic` (fallback).

Example recipes (illustrative — full field values live in code):

| key | genre | tempo | instrumentation | vocal | era |
|---|---|---|---|---|---|
| `arabic_ballad` | Arabic pop ballad, contemporary MENA | slow, 66–76 BPM | oud, nay, cinematic strings, soft grand piano, subtle hand percussion, deep sustained bass | {gender}, warm, emotive, restrained power, subtle vibrato | modern 2020s MENA pop, lush organic mix |
| `khaleeji` | Khaleeji Gulf pop | mid, 96–108 BPM | oud, qanun, khaleeji tabla + iqa'at percussion, warm synth pads, electric bass | {gender}, agile, ornamented (tarab melisma), confident | polished contemporary Gulf radio production |
| `arabic_trap` | Arabic trap / mahraganat | 128–150 BPM (half-time feel) | 808 sub-bass, crisp trap hats, oud/mizmar sample hook, hard-clipped kick | {gender}, rhythmic, autotune-as-style (musical), attitude | modern street production, punchy but clean |

The library is **genre-aware, not one-size-fits-all**: `arabic_trap`'s
`extra_negatives` *removes* `autotune artifacts` from the shared negatives,
because there autotune is a desired stylistic element.

### `infer_genre(theme, style_hint, language, dialect) -> key`

Deterministic, no LLM required:

1. If `style_hint` names a genre → match its aliases directly.
2. Else keyword-scan `theme + style_hint` against every recipe's `aliases`;
   highest hit count wins.
3. Dialect bias (e.g. `khaleeji` dialect nudges toward `khaleeji` on ties).
4. Fallback: `arabic_pop` for Arabic, `pop` for other languages, else `generic`.

This deterministic result is also the safety net for the producer call.

### `compose_style(...) -> StyleResult`

```python
@dataclass(frozen=True)
class StyleResult:
    style_prompt: str   # polished Suno `style` string (<= 450 chars)
    negative_tags: str  # genre-aware, from the recipe
    genre_key: str      # for logging / analytics
    source: str         # "producer:anthropic" | "producer:gemini" | "fallback:recipe"

def compose_style(llm, *, theme, title, lyrics, language, dialect,
                  style_hint, vocal_gender) -> StyleResult
```

Steps:

1. `genre_key = infer_genre(...)`; load `recipe`.
2. Dedicated **"music producer" system prompt** — persona is a hit-record
   producer writing a Suno `style` field, not a lyricist. It receives the
   recipe as scaffolding + the **finished lyrics** (to match tempo/mood/energy
   to the real words) and returns one JSON object
   `{"style_prompt": "...", "negative_tags": "..."}` with hard rules:
   comma-separated; must carry the quality-spine descriptors; must reflect the
   recipe's instrumentation + era; fill the vocal gender; ≤ 450 chars; no
   lyrics, no section tags, no prose.
3. Parse with the same robust JSON reader `song_lyrics.py` uses (strip fences →
   extract outermost `{...}` → `json.loads(strict=False)` → one retry).

### Validation gate ("looks weak" check)

Before trusting producer output:

- non-empty and ≤ 450 chars (trim at the last comma boundary if over);
- **token coverage** — contains a minimum share of the recipe's key tokens and
  at least one quality-spine descriptor (a model that ignored the recipe fails);
- no leaked lyrics / `[Section]` tags / Arabic sentence fragments.

Pass → use it (`source="producer:<tier>"`). Fail or exception → fallback.

### Deterministic fallback (safety net)

```python
def _recipe_style(recipe, vocal_gender, style_hint) -> (style_prompt, negative_tags)
```

Pure string assembly:
`genre, tempo, instrumentation, vocal(gender), era, <production spine>,
<vocal-realism spine>` (+ `style_hint` appended if given), trimmed to 450;
negatives = shared set − recipe removals + `recipe.extra_negatives`. Zero LLM
dependency — even a total Groq meltdown ships an expert-grade steer. This is
also what the unit tests assert against.

### Writer-tier visibility

`compose_style` records the producing path in `source`. The resolved provider
tier for both the lyrics call and the producer call is captured by reading the
degradation marker `FallbackLLM` **already sets** (the one driving the in-app
quality banner). Both are written into run state as `writer_tier`
(`anthropic`/`gemini`/`groq`) and `style_source`, so a silent fallback to the
weak writer shows up on `/runs/{id}`, in the log line, and on the review screen
— instead of being an invisible quality drain.

## Integration

- `SongScript` gains `negative_tags: str = ""`.
- Inside `generate_song_script`, after lyrics compose + tashkeel, call
  `compose_style(...)`. Its result becomes the authoritative `style_prompt` +
  `negative_tags`. The lyrics-JSON `style_prompt` drops to an optional seed
  (`parsed.get("style_prompt")`, passed in as a hint) — the producer pass owns
  the final steer.
- `song.json` write (`api.py:2827`) adds `negative_tags`, `style_source`,
  `writer_tier`.
- No worker change needed for negatives — `run.py:1061` already reads
  `script.get("negative_tags")` first; the producer's per-genre tags flow to
  Suno automatically, and the existing hardcoded string stays as the last-ditch
  default for old runs.

## Edge cases

- **custom_lyrics / cover / import:** producer still runs (style derived from
  theme + the actual words) — all covered via the single hook.
- **Manual style edit:** producer does not re-run on the PATCH edit endpoint;
  a user edit is final. Only create/regenerate compose.
- **Regenerate:** old `style_prompt` is passed as `style_hint` seed; treated as
  a hint, not a lock — no feedback loop.
- **Latency/cost:** one extra LLM call in the pre-approval `writing_lyrics`
  stage → no Suno spend, pre-payment; free and safe.
- **Length:** trimmed at the last comma boundary ≤ 450 chars (never mid-word),
  under the 500-char style-edit cap (round-trips through the edit screen) and
  well under Suno's 1000-char style limit.
- **Backward compat:** old `song.json` with no `negative_tags` → `run.py`
  default still applies.

## The B-hook (keeps the "C shape" alive without building B)

- Add `song.master_pass: false` to `config.yaml`, documented.
- Define the seam in `run.py` right after the chosen take is copied to
  `song.mp3` (`run.py:1131`): a `maybe_master(song_mp3, cfg)` that returns
  immediately unless the flag is on. A comment documents the intended free
  chain (HPF rumble cut, de-ess, gentle compression, −1 dBTP true-peak limiter,
  **no** loudnorm — respects the deliberate −14 LUFS gate). Not implemented now;
  the seam makes B a contained drop-in later.

## Testing

External LLM mocked per the repo invariant — never hit real APIs.

- `infer_genre`: style_hint match, keyword scan, dialect tie-break, language
  fallbacks.
- `_recipe_style` (deterministic): contains genre + both spine blocks + correct
  gender; ≤ 450; negatives correct per genre — including `arabic_trap`
  *removing* the autotune negative.
- `compose_style` with mocked LLM: (a) good JSON → used, `source="producer:*"`;
  (b) raises → fallback, `source="fallback:recipe"`; (c) weak output (ignores
  recipe / too long / leaks lyrics/tags) → validation fails → fallback.
- Length trim lands on a comma boundary.
- `generate_song_script` integration: `SongScript.negative_tags` populated;
  `style_source`/`writer_tier` recorded.
- Light API assertion: `song.json` carries `negative_tags`.

## Files touched

- **new** `pipeline/song_style.py` — recipes, spine, `infer_genre`,
  `compose_style`, `_recipe_style`, `StyleResult`, `Recipe`.
- `pipeline/song_lyrics.py` — `SongScript.negative_tags`; call `compose_style`
  in `generate_song_script`; style_prompt from lyrics JSON becomes optional seed.
- `pipeline/api.py` — persist `negative_tags`, `style_source`, `writer_tier`
  in `song.json` / run state.
- `run.py` — `maybe_master` seam after the take copy (no-op unless flag on).
- `config.yaml` — `song.master_pass: false` (documented).
- **new** `tests/test_song_style.py` — the tests above.

## Follow-ups (explicitly out of this spec)

- Approach B (ffmpeg tonal-master pass) — build behind `song.master_pass`.
- Best-of-N take selection (~$0.15) — the biggest remaining quality jump if the
  cost budget is ever reconsidered.
- Surface `writer_tier`/`style_source` in the Flutter review screen if the
  existing quality banner does not already cover it.
