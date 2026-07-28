# Song Producer Pass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the free-model-invents-everything Suno `style` blob with a dedicated "music producer" pass — a genre recipe library + a strongest-model LLM call with a deterministic recipe fallback — plus per-run writer-tier visibility, so every song ships a professional-grade Suno steer.

**Architecture:** A new focused module `pipeline/song_style.py` owns "brief → Suno style string + negative tags". It layers a genre-independent *quality spine* under a curated *genre recipe*. `generate_song_script` calls it after composing lyrics; output flows through the unchanged `song.json` schema (plus additive fields) to the already-wired worker submit. A no-op `maybe_master` seam + config flag reserve room for the future ffmpeg polish (Approach B) without building it.

**Tech Stack:** Python 3.11, dataclasses, pytest with `unittest.mock` (external LLM always mocked — never hit real APIs), existing `FallbackLLM` router in `pipeline/llm.py`.

**Spec:** `docs/superpowers/specs/2026-07-27-song-producer-pass-design.md`

**Repo invariants (apply to every task):** every new file starts with `from __future__ import annotations`; imports are absolute from `pipeline.` / package root; `pathlib.Path` never `os.path`; external services are mocked in tests.

---

## File structure

- **new** `pipeline/song_style.py` — `Recipe`, `GENRE_RECIPES`, quality-spine constants, `infer_genre`, `_recipe_style`, `build_negatives`, `_trim_to_last_comma`, `StyleResult`, `compose_style`. One responsibility: brief → style.
- **modify** `pipeline/llm.py` — `FallbackLLM.last_tier` tracking + `resolve_tier(llm)` helper + `GeminiClient.tier`.
- **modify** `pipeline/llm_anthropic.py`, `pipeline/llm_groq.py` — add `tier` class attribute.
- **modify** `pipeline/song_lyrics.py` — `SongScript` gains `negative_tags`/`style_source`/`writer_tier`; `generate_song_script` gains `vocal_gender` param and calls `compose_style`.
- **modify** `pipeline/api.py` — persist new fields into `song.json`; pass `vocal_gender` into `generate_song_script` on create.
- **modify** `pipeline/song_assemble.py` — add `maybe_master(mp3_path, cfg)` no-op seam.
- **modify** `pipeline/config.py` — `SongConfig.master_pass: bool = False`.
- **modify** `config.yaml` — `song.master_pass: false`.
- **modify** `run.py` — call `maybe_master` after the chosen take is copied.
- **new tests** `tests/test_song_style.py`, `tests/test_llm_tier.py`; **modify** `tests/test_song_lyrics.py`.

---

## Task 1: Recipe library + deterministic style builder (no LLM)

**Files:**
- Create: `pipeline/song_style.py`
- Test: `tests/test_song_style.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_song_style.py`:

```python
from __future__ import annotations

from pipeline.song_style import (
    GENRE_RECIPES,
    SHARED_NEGATIVES,
    SPINE_PRODUCTION,
    build_negatives,
    infer_genre,
    _recipe_style,
    _trim_to_last_comma,
)


def test_infer_genre_by_style_hint():
    assert infer_genre("a love song", style_hint="khaleeji pop") == "khaleeji"


def test_infer_genre_keyword_scan_arabic():
    assert infer_genre("a hard trap banger with 808s", language="ar") == "arabic_trap"


def test_infer_genre_dialect_tiebreak():
    # No genre keyword in the theme → dialect bias decides.
    assert infer_genre("song about home", language="ar", dialect="khaleeji") == "khaleeji"


def test_infer_genre_language_gate_excludes_arabic_recipes():
    # "love" is an arabic_ballad alias, but for an English song the Arabic-only
    # recipes are not candidates, so it must fall back to global pop.
    assert infer_genre("a love song", language="en") == "pop"


def test_infer_genre_arabic_language_fallback():
    assert infer_genre("لا يوجد نوع واضح", language="ar") == "arabic_pop"


def test_recipe_style_contains_spine_and_gender_and_length():
    style, neg = _recipe_style(GENRE_RECIPES["arabic_ballad"], "m")
    assert "male vocal" in style
    assert "mixed and mastered" in style
    assert "BPM" in style
    assert len(style) <= 450


def test_recipe_style_female_gender():
    style, _ = _recipe_style(GENRE_RECIPES["arabic_ballad"], "f")
    assert "female vocal" in style


def test_build_negatives_trap_removes_autotune():
    neg = build_negatives(GENRE_RECIPES["arabic_trap"])
    assert "autotune artifacts" not in neg
    assert "robotic vocal" in neg


def test_build_negatives_ballad_keeps_autotune():
    neg = build_negatives(GENRE_RECIPES["arabic_ballad"])
    assert "autotune artifacts" in neg


def test_trim_to_last_comma_lands_on_boundary():
    long = ", ".join(["descriptor number %d" % i for i in range(100)])
    out = _trim_to_last_comma(long, limit=60)
    assert len(out) <= 60
    assert not out.endswith(",")
    # trimmed at a comma boundary → the last kept token is whole
    assert out.split(", ")[-1] in long.split(", ")


def test_recipe_style_keeps_vocal_spine_and_hint():
    # The vocal-realism spine and a user style_hint are the two things most
    # load-bearing for "not AI" — they must survive the 450-char trim.
    style, _ = _recipe_style(GENRE_RECIPES["arabic_pop"], "f",
                             style_hint="nostalgic 90s Lebanese warmth")
    assert "natural breath and vibrato" in style          # SPINE_VOCAL survived
    assert "nostalgic 90s Lebanese warmth" in style        # user hint survived
    assert len(style) <= 450


def test_recipe_style_all_genres_fit_with_full_spine():
    # Every recipe must fit genre + vocal + both spine blocks within budget
    # (no genre may silently lose its vocal-realism spine).
    for key, recipe in GENRE_RECIPES.items():
        style, _ = _recipe_style(recipe, "m")
        assert "natural breath and vibrato" in style, key
        assert "mixed and mastered" in style, key
        assert len(style) <= 450, key


def test_infer_genre_word_boundary_no_false_positives():
    # short LATIN aliases must not match inside unrelated words
    assert infer_genre("a song about abundance and hope",
                       language="en") != "edm_electropop"   # not "dance" in "abundance"
    assert infer_genre("my husband and me", language="en") != "rock"  # not "band"


def test_infer_genre_matches_inflected_arabic_aliases():
    # Arabic inflects by attaching suffixes/prefixes directly, so alias
    # matching must still catch inflected forms (خليجية ⊃ خليجي, الطرب ⊃ طرب).
    assert infer_genre("أغنية خليجية أصيلة", language="ar") == "khaleeji"
    assert infer_genre("أحب الطرب الأصيل", language="ar") == "tarab_classic"


def test_recipe_remove_negatives_are_valid_tokens():
    shared = {p.strip() for p in SHARED_NEGATIVES.split(",")}
    for recipe in GENRE_RECIPES.values():
        assert set(recipe.remove_negatives) <= shared, recipe.key
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_song_style.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pipeline.song_style'`.

- [ ] **Step 3: Create `pipeline/song_style.py` (data + deterministic builder)**

```python
"""Brief → Suno `style` string + negative tags (the "producer pass").

Layers a genre-independent QUALITY SPINE (production + vocal-realism
vocabulary + anti-AI negatives) under a curated per-genre RECIPE. The
deterministic builder here is also the safety net for compose_style
(Task 2): if the producer LLM call fails or looks weak, we ship a
recipe-built steer that is already far above a free-model blob.

See docs/superpowers/specs/2026-07-27-song-producer-pass-design.md.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# --- Quality spine (injected into every genre) ------------------------------
# Kept compact so the full spine + genre + a user style_hint all fit inside
# MAX_STYLE_CHARS for every recipe (the longest recipe lands ~438/450). The
# _looks_weak gate (Task 3) keys off "mixed and mastered" / "radio-ready" /
# "studio production", which must remain present here.
SPINE_PRODUCTION = (
    "professionally mixed and mastered, radio-ready studio production, "
    "warm analog low-end, wide clean stereo"
)
SPINE_VOCAL = (
    "expressive human lead vocal, natural breath and vibrato, real singer"
)
SHARED_NEGATIVES = (
    "robotic vocal, autotune artifacts, pitchy, off-key, muffled, muddy mix, "
    "low quality, MIDI-sounding instruments, karaoke backing track, "
    "amateur demo, digital harshness, boxy"
)

MAX_STYLE_CHARS = 450
_GENDER = {"m": "male vocal", "f": "female vocal"}


@dataclass(frozen=True)
class Recipe:
    key: str
    aliases: tuple[str, ...]
    genre: str
    tempo: str
    instrumentation: str
    vocal: str                              # contains "{gender}" placeholder
    era: str
    remove_negatives: tuple[str, ...] = ()  # shared negatives to drop
    extra_negatives: tuple[str, ...] = ()   # genre-specific negatives to add


# Arabic-only recipes are candidates only when language starts with "ar",
# so an English theme can't match e.g. arabic_ballad via the word "love".
_ARABIC_ONLY = frozenset({
    "arabic_pop", "arabic_ballad", "khaleeji", "tarab_classic",
    "arabic_trap", "folk_shaabi",
})

GENRE_RECIPES: dict[str, Recipe] = {
    "arabic_pop": Recipe(
        key="arabic_pop",
        aliases=("arabic pop", "عربي", "mena pop", "mainstream arabic"),
        genre="modern Arabic pop, mainstream MENA",
        tempo="mid-tempo, 96-112 BPM",
        instrumentation="layered synths, electric bass, live drums and darbuka, "
                        "oud accents, bright piano",
        vocal="{gender}, polished, catchy, confident",
        era="contemporary 2020s Arabic radio pop, glossy commercial mix",
    ),
    "arabic_ballad": Recipe(
        key="arabic_ballad",
        aliases=("ballad", "sad", "حزين", "love", "romantic", "emotional", "slow"),
        genre="Arabic pop ballad, contemporary MENA",
        tempo="slow, 66-76 BPM",
        instrumentation="oud, nay, cinematic strings, soft grand piano, subtle "
                        "hand percussion, deep sustained bass",
        vocal="{gender}, warm, emotive, restrained power, subtle vibrato",
        era="modern 2020s MENA pop, lush organic mix",
    ),
    "khaleeji": Recipe(
        key="khaleeji",
        aliases=("khaleeji", "gulf", "خليجي", "saudi", "kuwaiti", "emirati"),
        genre="Khaleeji Gulf pop",
        tempo="mid, 96-108 BPM",
        instrumentation="oud, qanun, khaleeji tabla and iqa'at percussion, warm "
                        "synth pads, electric bass",
        vocal="{gender}, agile, ornamented tarab melisma, confident",
        era="polished contemporary Gulf radio production",
    ),
    "tarab_classic": Recipe(
        key="tarab_classic",
        aliases=("tarab", "طرب", "classical arabic", "orchestra", "muwashah", "oldies"),
        genre="classical Arabic tarab, orchestral",
        tempo="rubato to slow, 60-80 BPM",
        instrumentation="takht ensemble: oud, qanun, nay, riq, kamanja strings, "
                        "full Arabic orchestra",
        vocal="{gender}, virtuosic, deep tarab expression, long melismatic phrasing",
        era="golden-age Arabic orchestral, warm vintage analog",
    ),
    "arabic_trap": Recipe(
        key="arabic_trap",
        aliases=("trap", "mahragan", "مهرجان", "808", "street", "drill"),
        genre="Arabic trap and mahraganat",
        tempo="128-150 BPM half-time feel",
        instrumentation="808 sub-bass, crisp trap hi-hats, oud and mizmar sample "
                        "hook, hard-clipped kick",
        vocal="{gender}, rhythmic, attitude, melodic autotune as a stylistic effect",
        era="modern street production, punchy loud but clean",
        remove_negatives=("autotune artifacts",),
        extra_negatives=("thin low-end",),
    ),
    "folk_shaabi": Recipe(
        key="folk_shaabi",
        aliases=("shaabi", "شعبي", "baladi", "folk arabic", "wedding"),
        genre="Egyptian shaabi and baladi folk",
        tempo="lively, 100-120 BPM",
        instrumentation="mizmar, accordion, tabla and dohola percussion, oud, hand claps",
        vocal="{gender}, raw, energetic, call-and-response feel",
        era="festive street shaabi, live-room energy",
    ),
    "hiphop_rap": Recipe(
        key="hiphop_rap",
        aliases=("rap", "hip hop", "hip-hop", "راب", "boom bap", "bars"),
        genre="hip-hop / rap",
        tempo="boom-bap, 85-95 BPM",
        instrumentation="punchy drums, deep bass, sampled keys and horns, vinyl texture",
        vocal="{gender}, rhythmic flow, clear diction, confident delivery",
        era="modern hip-hop, tight punchy mix",
    ),
    "rnb_soul": Recipe(
        key="rnb_soul",
        aliases=("rnb", "r&b", "soul", "neo soul"),
        genre="contemporary R&B / soul",
        tempo="smooth, 70-90 BPM",
        instrumentation="electric piano, warm sub-bass, brushed drums, lush pads, "
                        "subtle guitar",
        vocal="{gender}, silky, soulful runs, breathy intimacy",
        era="modern R&B, warm analog low-end, spacious mix",
    ),
    "pop": Recipe(
        key="pop",
        aliases=("pop", "english pop", "western pop", "dance pop"),
        genre="modern global pop",
        tempo="upbeat, 100-120 BPM",
        instrumentation="bright synths, punchy programmed drums, electric bass, "
                        "layered vocal harmonies",
        vocal="{gender}, polished, catchy, energetic",
        era="contemporary 2020s international pop, glossy commercial master",
    ),
    "rock": Recipe(
        key="rock",
        aliases=("rock", "alternative", "band", "guitar", "indie"),
        genre="alternative rock",
        tempo="driving, 110-140 BPM",
        instrumentation="distorted electric guitars, live drums, bass guitar, "
                        "occasional piano",
        vocal="{gender}, powerful, emotive, slight grit",
        era="modern rock, loud analog mix, real amps",
    ),
    "edm_electropop": Recipe(
        key="edm_electropop",
        aliases=("edm", "electro", "dance", "house", "electronic", "club", "synth"),
        genre="EDM / electropop",
        tempo="four-on-the-floor, 120-128 BPM",
        instrumentation="big synth leads, sidechained pads, punchy kick, sub-bass, risers",
        vocal="{gender}, bright, hooky, processed tastefully",
        era="modern festival EDM, wide polished club master",
    ),
    "cinematic_ost": Recipe(
        key="cinematic_ost",
        aliases=("cinematic", "epic", "soundtrack", "ost", "score", "trailer"),
        genre="cinematic orchestral score",
        tempo="building, 70-100 BPM",
        instrumentation="full orchestra, epic strings, brass, choir, taiko and "
                        "cinematic percussion, piano",
        vocal="{gender}, emotive, soaring, dramatic",
        era="modern film-score production, wide dynamic cinematic mix",
    ),
    "generic": Recipe(
        key="generic",
        aliases=(),
        genre="contemporary song, well-produced",
        tempo="mid-tempo, 90-110 BPM",
        instrumentation="balanced modern band: drums, bass, keys, guitar, "
                        "tasteful synths",
        vocal="{gender}, expressive, clear",
        era="modern professional studio production",
    ),
}


def _fill_vocal(recipe: Recipe, vocal_gender: str | None) -> str:
    return recipe.vocal.replace("{gender}", _GENDER.get(vocal_gender or "", "lead vocal"))


def _trim_to_last_comma(text: str, limit: int = MAX_STYLE_CHARS) -> str:
    """Trim to <= limit chars without cutting mid-descriptor (drop the last
    partial token at the final comma boundary)."""
    if len(text) <= limit:
        return text
    cut = text[:limit]
    i = cut.rfind(",")
    return (cut[:i] if i > 0 else cut).strip().rstrip(",")


def build_negatives(recipe: Recipe) -> str:
    parts = [p.strip() for p in SHARED_NEGATIVES.split(",")]
    parts = [p for p in parts if p not in recipe.remove_negatives]
    parts += list(recipe.extra_negatives)
    return ", ".join(parts)


def _alias_hit(alias: str, hay: str) -> bool:
    """Whether an alias occurs in the haystack.

    Latin-script aliases need BOTH word boundaries so short words don't fire
    inside longer ones ("dance" in "abundance", "band" in "husband", "808" in
    "808s"). Arabic inflects by attaching prefixes/suffixes directly
    (خليجي → خليجية, طرب → الطرب), so word boundaries would miss real matches;
    Arabic-script aliases are distinctive enough that a plain substring match
    is safe and catches inflected forms."""
    if re.search(r"[؀-ۿ]", alias):
        return alias in hay
    return re.search(rf"\b{re.escape(alias)}\b", hay) is not None


def infer_genre(theme: str, style_hint: str | None = None,
                language: str = "ar", dialect: str | None = None) -> str:
    """Deterministic genre pick. No LLM. Language-gated so English themes
    never match Arabic-only recipes. An explicit style_hint that names a
    genre wins outright (spec rule 1) before the theme keyword scan; the
    dialect nudge is a tie-breaker for the theme scan only."""
    is_ar = (language or "").startswith("ar")
    candidates = {
        k: v for k, v in GENRE_RECIPES.items()
        if is_ar or k not in _ARABIC_ONLY
    }

    def _pick(hay: str, use_dialect: bool) -> str | None:
        scores = {
            k: sum(1 for a in r.aliases if _alias_hit(a, hay))
            for k, r in candidates.items()
        }
        if use_dialect and dialect == "khaleeji" and "khaleeji" in scores:
            scores["khaleeji"] += 1
        best = max(scores, key=lambda k: scores[k])
        return best if scores[best] > 0 else None

    # Rule 1: an explicit style_hint that names a genre wins outright.
    if style_hint:
        hit = _pick(style_hint.lower(), use_dialect=False)
        if hit:
            return hit
    # Rule 2: keyword-scan theme (+ style_hint as a weaker combined signal),
    # with the dialect nudge as tie-breaker.
    hit = _pick(f"{theme or ''} {style_hint or ''}".lower(), use_dialect=True)
    if hit:
        return hit
    if is_ar:
        return "arabic_pop"
    return "pop" if language else "generic"


def _recipe_style(recipe: Recipe, vocal_gender: str | None,
                  style_hint: str | None = None) -> tuple[str, str]:
    """Deterministic fallback: build style + negatives straight from the recipe.

    Pieces are ordered by DESCENDING importance because _trim_to_last_comma
    drops from the tail: genre, the user's style_hint, the vocal, and both
    quality-spine blocks sit ahead of tempo/instrumentation/era so the
    anti-AI cues and the user's intent always survive the 450-char budget.
    era is the first thing sacrificed when a long style_hint is supplied."""
    pieces = [recipe.genre]
    if style_hint:
        pieces.append(style_hint.strip())
    pieces += [
        _fill_vocal(recipe, vocal_gender),
        SPINE_PRODUCTION, SPINE_VOCAL,
        recipe.tempo, recipe.instrumentation, recipe.era,
    ]
    style = _trim_to_last_comma(", ".join(pieces))
    return style, build_negatives(recipe)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_song_style.py -v`
Expected: PASS (15 tests).

- [ ] **Step 5: Commit**

```bash
git add pipeline/song_style.py tests/test_song_style.py
git commit -m "$(cat <<'EOF'
feat(song): genre recipe library + deterministic style builder

Quality-spine + per-genre recipes, language-gated genre inference, and
the recipe-built style/negatives that will serve as the producer-pass
fallback. Deterministic, no LLM. Spec: 2026-07-27-song-producer-pass.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Writer-tier tracking in the LLM router

**Files:**
- Modify: `pipeline/llm.py` (`FallbackLLM`, `GeminiClient`, add `resolve_tier`)
- Modify: `pipeline/llm_anthropic.py` (add `tier`)
- Modify: `pipeline/llm_groq.py` (add `tier`)
- Test: `tests/test_llm_tier.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_llm_tier.py`:

```python
from __future__ import annotations

from unittest.mock import MagicMock

from pipeline.llm import FallbackLLM, resolve_tier


class _Stub:
    def __init__(self, tier, raises=False):
        self.tier = tier
        self._raises = raises

    def complete(self, prompt, system=None):
        if self._raises:
            raise RuntimeError("primary down")
        return f"[{self.tier}] {prompt}"


def test_fallback_records_primary_tier_on_success():
    llm = FallbackLLM(_Stub("anthropic"), _Stub("groq"))
    out = llm.complete("hi")
    assert out.startswith("[anthropic]")
    assert llm.last_tier == "anthropic"


def test_fallback_records_fallback_tier_on_primary_failure():
    llm = FallbackLLM(_Stub("anthropic", raises=True), _Stub("groq"))
    out = llm.complete("hi")
    assert out.startswith("[groq]")
    assert llm.last_tier == "groq"


def test_fallback_records_leaf_tier_through_nested_chain():
    inner = FallbackLLM(_Stub("gemini", raises=True), _Stub("groq"))
    outer = FallbackLLM(_Stub("anthropic", raises=True), inner)
    outer.complete("hi")
    assert outer.last_tier == "groq"


def test_resolve_tier_reads_bare_client():
    assert resolve_tier(_Stub("gemini")) == "gemini"


def test_resolve_tier_unknown_when_absent():
    class Bare:
        def complete(self, p, system=None):
            return p
    assert resolve_tier(Bare()) == "unknown"


def test_resolve_tier_ignores_non_str_truthy_attribute():
    # The isinstance(str) guard exists precisely so a MagicMock's auto-created
    # (truthy, non-str) attribute resolves to "unknown" instead of leaking a
    # MagicMock onto the JSON write path.
    assert resolve_tier(MagicMock()) == "unknown"


def test_fallback_records_leaf_tier_when_nested_on_primary():
    # Symmetric with the fallback-side nesting: a FallbackLLM nested as the
    # PRIMARY that succeeds must still report its leaf tier, not "unknown".
    inner = FallbackLLM(_Stub("gemini", raises=True), _Stub("groq"))
    outer = FallbackLLM(inner, _Stub("anthropic"))
    outer.complete("hi")
    assert outer.last_tier == "groq"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_llm_tier.py -v`
Expected: FAIL — `ImportError: cannot import name 'resolve_tier'` and `FallbackLLM` has no `last_tier`.

- [ ] **Step 3: Add tier tracking to `pipeline/llm.py`**

In `FallbackLLM.__init__`, add after `self._on_fallback = on_fallback`:

```python
        # Tier of the provider that actually served the most recent complete().
        # Read via resolve_tier(). A fresh FallbackLLM is built per generation
        # request (see api._build_llm), so this instance attribute is not shared.
        self.last_tier = None
```

Replace `FallbackLLM.complete` with:

```python
    def complete(self, prompt: str, system: str | None = None) -> str:
        try:
            out = self._primary.complete(prompt, system=system)
            # Unwrap a nested FallbackLLM (symmetric with the fallback path)
            # so a chain nested on the primary side still reports the leaf.
            self.last_tier = (getattr(self._primary, "last_tier", None)
                              or getattr(self._primary, "tier", "unknown"))
            return out
        except Exception as e:
            print(f"[llm] primary provider failed ({e}); "
                  f"falling back to secondary provider")
            if self._on_fallback is not None:
                try:
                    self._on_fallback(e)
                except Exception:
                    pass
            out = self._fallback.complete(prompt, system=system)
            # Unwrap a nested FallbackLLM so we report the LEAF tier that served.
            self.last_tier = (getattr(self._fallback, "last_tier", None)
                              or getattr(self._fallback, "tier", "unknown"))
            return out
```

Add a `tier` class attribute to `GeminiClient` (right under `class GeminiClient:` docstring, before `__init__`):

```python
    tier = "gemini"
```

Add the module-level helper at the end of `pipeline/llm.py`:

```python
def resolve_tier(llm) -> str:
    """Which provider actually served the last complete(): a FallbackLLM's
    last_tier, else a bare client's tier, else 'unknown'.

    Only str values count — a test double (e.g. MagicMock) auto-creates any
    attribute, so guarding on isinstance(str) keeps those out of run state and
    off the JSON write path (a MagicMock would raise in json.dumps)."""
    for attr in ("last_tier", "tier"):
        val = getattr(llm, attr, None)
        if isinstance(val, str) and val:
            return val
    return "unknown"
```

- [ ] **Step 4: Add `tier` to the other two clients**

In `pipeline/llm_anthropic.py`, add `tier = "anthropic"` as a class attribute on `AnthropicClient` (first line of the class body).
In `pipeline/llm_groq.py`, add `tier = "groq"` as a class attribute on `GroqClient` (first line of the class body).

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_llm_tier.py -v`
Expected: PASS (7 tests).

- [ ] **Step 6: Run the existing LLM/router tests to confirm no regression**

Run: `uv run pytest tests/ -k "llm or fallback" -v`
Expected: PASS (existing tests still green — changes are additive).

- [ ] **Step 7: Commit**

```bash
git add pipeline/llm.py pipeline/llm_anthropic.py pipeline/llm_groq.py tests/test_llm_tier.py
git commit -m "$(cat <<'EOF'
feat(llm): track resolved writer tier through the fallback chain

Additive last_tier on FallbackLLM + tier on each client + resolve_tier().
Lets the song brief record whether Anthropic/Gemini/Groq actually served,
surfacing a silent free-tier fallback. Spec: 2026-07-27-song-producer-pass.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: The producer pass — `compose_style`

**Files:**
- Modify: `pipeline/song_style.py` (add `StyleResult`, `compose_style`, helpers)
- Test: `tests/test_song_style.py` (add cases)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_song_style.py`:

```python
import json

from pipeline.song_style import StyleResult, compose_style


class _StubLLM:
    def __init__(self, response=None, raises=False):
        self._response = response
        self._raises = raises

    def complete(self, prompt, system=None):
        if self._raises:
            raise RuntimeError("llm down")
        return self._response


_GOOD_PRODUCER_JSON = json.dumps({
    "style_prompt": ("Arabic pop ballad, cinematic strings and soft piano, "
                     "warm male vocal, professionally mixed and mastered"),
    "negative_tags": "robotic vocal, off-key",
})


def _compose(llm, theme="أغنية حزينة عن الفراق", genre_hint=None):
    # "حزينة" contains the arabic_ballad alias "حزين" (Arabic substring match)
    # → infer_genre returns "arabic_ballad", which the fallback tests assert.
    return compose_style(
        llm, theme=theme, title="عنوان", lyrics="[Verse 1]\nكلمات\n[Chorus]\nلازمة",
        language="ar", dialect=None, style_hint=genre_hint, vocal_gender="m",
    )


def test_compose_style_uses_producer_when_valid():
    res = _compose(_StubLLM(_GOOD_PRODUCER_JSON))
    assert isinstance(res, StyleResult)
    assert res.source.startswith("producer:")
    assert "mixed and mastered" in res.style_prompt
    assert res.negative_tags == "robotic vocal, off-key"


def test_compose_style_falls_back_on_exception():
    res = _compose(_StubLLM(raises=True))
    assert res.source == "fallback:recipe"
    assert "mixed and mastered" in res.style_prompt  # recipe spine present
    assert res.genre_key == "arabic_ballad"


def test_compose_style_falls_back_on_weak_output():
    weak = json.dumps({"style_prompt": "pop song", "negative_tags": ""})
    res = _compose(_StubLLM(weak))
    assert res.source == "fallback:recipe"


def test_compose_style_rejects_leaked_section_tags():
    leaked = json.dumps({
        "style_prompt": ("Arabic pop ballad, cinematic strings, professionally "
                         "mixed and mastered [Chorus]"),
        "negative_tags": "",
    })
    res = _compose(_StubLLM(leaked))
    assert res.source == "fallback:recipe"


def test_compose_style_trims_overlong_producer_output():
    huge = json.dumps({
        "style_prompt": ("professionally mixed and mastered, Arabic pop ballad, "
                         "cinematic strings, ") + ", ".join(["extra tag"] * 200),
        "negative_tags": "",
    })
    res = _compose(_StubLLM(huge))
    assert len(res.style_prompt) <= 450


def test_compose_style_falls_back_on_non_json_text():
    # LLM returned prose, not JSON → JSONDecodeError → fallback, no crash.
    res = _compose(_StubLLM("here is your style: pop, upbeat, fun"))
    assert res.source == "fallback:recipe"


def test_compose_style_falls_back_on_non_object_json():
    # Valid JSON but a list, not an object → ValueError guard → fallback.
    res = _compose(_StubLLM(json.dumps(["pop", "upbeat"])))
    assert res.source == "fallback:recipe"


def test_compose_style_falls_back_on_missing_keys():
    # Object without style_prompt → empty style → weak → fallback.
    res = _compose(_StubLLM(json.dumps({"foo": "bar"})))
    assert res.source == "fallback:recipe"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_song_style.py -k compose -v`
Expected: FAIL — `cannot import name 'StyleResult'` / `compose_style`.

- [ ] **Step 3: Add `compose_style` to `pipeline/song_style.py`**

Add these imports at the top (after `from dataclasses import ...`):

```python
import json
import re

from pipeline.llm import resolve_tier
```

Append to the module:

```python
@dataclass(frozen=True)
class StyleResult:
    style_prompt: str
    negative_tags: str
    genre_key: str
    source: str   # "producer:<tier>" | "fallback:recipe"


_PRODUCER_SYSTEM = """You are a hit-record music producer writing the STYLE
field for Suno V5.5 — NOT a lyricist. Given a genre recipe and the finished
lyrics, output the single best comma-separated style descriptor.

OUTPUT: a JSON object, no markdown, no commentary:
  {"style_prompt": "...", "negative_tags": "..."}

RULES for style_prompt:
  - Comma-separated descriptors only. No sentences, no lyrics, no [section] tags.
  - START with the mandatory production + vocal-realism language ("professionally
    mixed and mastered, radio-ready studio production, ... expressive human lead
    vocal ...") so it can never be lost; THEN add genre, instrumentation,
    tempo and era from the recipe.
  - MUST reflect the recipe's instrumentation and era; adapt tempo/mood to the
    actual lyrics.
  - Keep it SHORT — under 45 words — so it fits without truncation.
negative_tags: comma-separated things to exclude for this genre."""


def _producer_user_msg(recipe: Recipe, title: str, lyrics: str, language: str,
                       dialect: str | None, style_hint: str | None,
                       vocal_gender: str | None) -> str:
    return (
        f"Genre recipe (scaffold — refine, don't just copy):\n"
        f"  genre: {recipe.genre}\n"
        f"  tempo: {recipe.tempo}\n"
        f"  instrumentation: {recipe.instrumentation}\n"
        f"  vocal: {_fill_vocal(recipe, vocal_gender)}\n"
        f"  era: {recipe.era}\n"
        f"  production spine (keep): {SPINE_PRODUCTION}\n"
        f"  vocal spine (keep): {SPINE_VOCAL}\n"
        f"  negative tags (baseline): {build_negatives(recipe)}\n"
        f"Song title: {title}\n"
        f"Language: {language}" + (f" ({dialect})" if dialect else "") + "\n"
        + (f"User style hint (honor it): {style_hint}\n" if style_hint else "")
        + f"Lyrics:\n{lyrics}"
    )


def _parse_json_object(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?|\n?```$", "", raw, flags=re.MULTILINE).strip()
    if not raw.startswith("{"):
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end > start:
            raw = raw[start:end + 1]
    data = json.loads(raw, strict=False)
    if not isinstance(data, dict):
        raise ValueError("producer output was not a JSON object")
    return data


def _key_tokens(recipe: Recipe) -> list[str]:
    raw = f"{recipe.genre} {recipe.instrumentation}".lower()
    return [w for w in re.split(r"[,\s]+", raw) if len(w) > 3]


def _looks_weak(style: str, recipe: Recipe) -> bool:
    if not style or len(style) < 20:
        return True
    if "[" in style or "]" in style or "\n" in style:
        return True
    low = style.lower()
    if not any(t in low for t in
               ("mixed and mastered", "radio-ready", "studio production")):
        return True
    if sum(1 for t in _key_tokens(recipe) if t in low) < 2:
        return True
    return False


def compose_style(llm, *, theme: str, title: str, lyrics: str, language: str,
                  dialect: str | None, style_hint: str | None,
                  vocal_gender: str | None) -> StyleResult:
    """Producer pass: strongest-model style prompt, recipe fallback on
    failure or weak output. Never raises — always returns a usable steer."""
    genre_key = infer_genre(theme, style_hint, language, dialect)
    recipe = GENRE_RECIPES[genre_key]
    fb_style, fb_neg = _recipe_style(recipe, vocal_gender, style_hint)
    try:
        raw = llm.complete(
            _producer_user_msg(recipe, title, lyrics, language, dialect,
                               style_hint, vocal_gender),
            system=_PRODUCER_SYSTEM,
        )
        parsed = _parse_json_object(raw)
        # Trim BEFORE the weak-check on purpose: this guarantees the SHIPPED
        # style always carries the spine tokens. If trimming a too-long
        # response drops them, _looks_weak fails and we ship the spine-bearing
        # recipe fallback instead. _PRODUCER_SYSTEM front-loads the spine so
        # this rarely fires.
        style = _trim_to_last_comma(str(parsed.get("style_prompt", "")).strip())
        neg = str(parsed.get("negative_tags", "")).strip() or fb_neg
        if _looks_weak(style, recipe):
            print(f"[song-style] producer output looked weak for {genre_key}; "
                  f"using recipe fallback")
            return StyleResult(fb_style, fb_neg, genre_key, "fallback:recipe")
        return StyleResult(style, neg, genre_key, f"producer:{resolve_tier(llm)}")
    except Exception as e:
        print(f"[song-style] producer pass failed ({e}); using recipe fallback")
        return StyleResult(fb_style, fb_neg, genre_key, "fallback:recipe")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_song_style.py -v`
Expected: PASS (23 tests — 15 Task 1 + 8 Task 3).

- [ ] **Step 5: Commit**

```bash
git add pipeline/song_style.py tests/test_song_style.py
git commit -m "$(cat <<'EOF'
feat(song): compose_style producer pass with recipe fallback

Dedicated music-producer LLM call, validation gate (spine + recipe-token
coverage, no leaked lyrics/tags, length trim), and a recipe fallback that
never raises. Records producer:<tier> vs fallback:recipe as the source.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Wire the producer pass into `generate_song_script`

**Files:**
- Modify: `pipeline/song_lyrics.py` (`SongScript`, `generate_song_script`)
- Test: `tests/test_song_lyrics.py` (add integration case + adjust helper)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_song_lyrics.py`:

```python
def _routing_llm(lyrics_json: str, producer_json: str):
    """Fake LLM: returns producer JSON when it sees the producer system prompt,
    otherwise the lyrics JSON (also covers the optional diacritize call)."""
    llm = MagicMock()

    def _complete(prompt, system=None):
        if system and "music producer" in system.lower():
            return producer_json
        return lyrics_json

    llm.complete = MagicMock(side_effect=_complete)
    llm.last_tier = "anthropic"
    return llm


def test_generate_song_script_populates_producer_fields():
    lyrics_json = """{
        "title": "قمر",
        "lyrics": "[Verse 1]\\nكَلِمَات\\n[Chorus]\\nلَازِمَة",
        "style_prompt": "weak blob to be ignored",
        "cover_prompt": "moonlit portrait"
    }"""
    producer_json = """{
        "style_prompt": "Arabic pop ballad, cinematic strings and soft piano, warm male vocal, professionally mixed and mastered",
        "negative_tags": "robotic vocal, off-key"
    }"""
    llm = _routing_llm(lyrics_json, producer_json)
    script = generate_song_script(
        llm=llm, theme="أغنية حب حزينة", custom_lyrics=None,
        style_hint=None, language="ar", vocal_gender="m",
    )
    assert "mixed and mastered" in script.style_prompt
    assert script.negative_tags == "robotic vocal, off-key"
    assert script.style_source.startswith("producer:")
    assert script.writer_tier == "anthropic"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_song_lyrics.py::test_generate_song_script_populates_producer_fields -v`
Expected: FAIL — `SongScript` has no `negative_tags` / `generate_song_script` has no `vocal_gender` kwarg.

- [ ] **Step 3: Extend `SongScript`**

In `pipeline/song_lyrics.py`, add three fields to the `SongScript` dataclass (after `scene_prompts`):

```python
    negative_tags: str = ""
    # Provenance: which writer tier served the lyrics, and whether the style
    # came from the producer LLM ("producer:<tier>") or the recipe fallback.
    style_source: str = ""
    writer_tier: str = ""
```

- [ ] **Step 4: Call the producer pass inside `generate_song_script`**

Add to the imports at the top of `pipeline/song_lyrics.py`:

```python
from pipeline.llm import resolve_tier
from pipeline.song_style import compose_style
```

Change the signature to accept `vocal_gender` (add as the last keyword-only param):

```python
def generate_song_script(
    *,
    llm,
    theme: str,
    custom_lyrics: str | None,
    style_hint: str | None,
    language: str,
    dialect: str | None = None,
    vocal_gender: str | None = "m",
) -> SongScript:
```

Capture `writer_tier` right after `validate_section_tags(lyrics)` — BEFORE the
tashkeel/diacritize block — so it reflects the tier that wrote the LYRICS, not a
tier a later diacritize rescue or the producer pass may fall back to:

```python
    lyrics = custom_lyrics if custom_lyrics else parsed["lyrics"]
    validate_section_tags(lyrics)

    # Capture which writer tier produced the LYRICS here — before the rescue
    # diacritize pass AND the producer pass, both of which make their own
    # llm.complete() calls that would overwrite last_tier and misattribute
    # provenance (e.g. a transient diacritize-only fallback to Groq would
    # otherwise make writer_tier read "groq" for lyrics Anthropic wrote).
    writer_tier = resolve_tier(llm)
```

Then replace the final `return SongScript(...)` block with (note: no
`writer_tier = ...` here — it was captured above):

```python
    # Producer pass: authoritative Suno style + negative tags. The lyrics-JSON
    # style_prompt (parsed["style_prompt"]) is intentionally ignored — a weak
    # writer's blob is exactly what this replaces.
    style = compose_style(
        llm, theme=theme, title=parsed["title"], lyrics=lyrics,
        language=language, dialect=dialect, style_hint=style_hint,
        vocal_gender=vocal_gender,
    )

    return SongScript(
        title=parsed["title"],
        lyrics=lyrics,
        style_prompt=style.style_prompt,
        cover_prompt=parsed["cover_prompt"],
        language=language,
        art_direction=str(parsed.get("art_direction", "")),
        scene_prompts=list(parsed.get("scene_prompts", []) or []),
        negative_tags=style.negative_tags,
        style_source=style.source,
        writer_tier=writer_tier,
    )
```

- [ ] **Step 5: Run the FULL suite (the producer pass adds an llm.complete call)**

Run: `uv run pytest tests/test_song_lyrics.py tests/test_arabic_quality.py -v` (and then the whole suite before Task 7).
Expected: PASS. The existing `test_generate_song_script_from_theme_only` still passes — its single-return stub feeds the producer call the lyrics JSON, which fails the validation gate and falls back to the `arabic_ballad` recipe whose style still contains `"BPM"`.

The unconditional producer-pass call means `generate_song_script` now makes ONE extra `llm.complete` call. Tests that assert exact call counts or the raw lyrics-JSON `style_prompt` need updating (intended behavior change — preserve each test's real invariant, do not weaken it):
- `tests/test_song_lyrics.py::test_song_script_tolerates_messy_groq_output`: `"90 BPM"` assertion → `s.style_source == "fallback:recipe"` + `"mixed and mastered" in s.style_prompt` (keep the `title`/`[Chorus]` parsing-tolerance checks).
- `tests/test_arabic_quality.py::test_rescue_diacritization_fires_only_on_low_density`: `len(calls) == 2` → `== 3` (compose + diacritize + producer).
- `tests/test_arabic_quality.py::test_custom_lyrics_never_auto_diacritized` and `test_high_density_compose_skips_rescue`: replace the brittle `len(calls) == 1` with the real invariant `DIACRITIZE_SYSTEM not in calls` (import `DIACRITIZE_SYSTEM`; note `_SYSTEM_PROMPT` itself mentions تشكيل, so a substring check is wrong).
- `tests/test_arabic_quality.py::test_generate_retries_once_on_malformed_json`: make the flaky stub return a valid producer object for calls beyond the 2 lyrics attempts; `len(calls) == 2` → `== 3`.
Also add `tests/test_song_lyrics.py::test_writer_tier_reflects_lyrics_call_not_diacritize_fallback` — a stub whose `last_tier` mutates per call (anthropic for lyrics, groq for the rescue/producer) asserting `writer_tier == "anthropic"` (locks the capture-before-diacritize fix).

- [ ] **Step 6: Commit**

```bash
git add pipeline/song_lyrics.py tests/test_song_lyrics.py
git commit -m "$(cat <<'EOF'
feat(song): generate_song_script runs the producer pass

SongScript carries negative_tags/style_source/writer_tier; the producer
pass owns the Suno style (weak lyrics-JSON style_prompt dropped). All
callers (create/regenerate/drafts/import/cover) inherit it via this hook.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Persist the new fields + pass vocal_gender on create

**Files:**
- Modify: `pipeline/api.py` (create-song `generate_song_script` call ~2815; `song.json` write ~2827)
- Test: `tests/test_song_api.py` (add case — uses the existing `app` fixture + `_find_run_dir` helper)

Note: the `app` fixture stubs `_build_song_llm` with a bare `MagicMock` whose
`.complete` returns a fixed lyrics JSON. That means the producer pass receives
the lyrics JSON, fails its validation gate, and returns the recipe fallback —
so `style_source == "fallback:recipe"` and `writer_tier == "unknown"` (the
str-guard in `resolve_tier` keeps the MagicMock out of the JSON write). This is
exactly the behavior the test below asserts.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_song_api.py` (reuses the module's `app` fixture and the
existing `_find_run_dir` helper at the top of the file):

```python
def test_post_songs_persists_producer_fields(app):
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    r = client.post(
        "/songs",
        json={"theme": "sad Arabic ballad about the moon", "language": "ar",
              "vocal_gender": "m"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    run_dir = _find_run_dir(r.json()["run_id"])
    song_json = json.loads((run_dir / "song.json").read_text())
    # New producer fields present and JSON-serialisable (no MagicMock leak).
    assert song_json["style_source"] == "fallback:recipe"
    assert song_json["writer_tier"] == "unknown"
    assert "robotic vocal" in song_json["negative_tags"]  # recipe negatives
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_song_api.py::test_post_songs_persists_producer_fields -v`
Expected: FAIL — `KeyError: 'style_source'` (keys not yet written to `song.json`).

- [ ] **Step 3: Pass `vocal_gender` into the create call**

In `pipeline/api.py`, the create-song `generate_song_script(...)` call (~line 2815) — add `vocal_gender=req.vocal_gender`:

```python
        script = generate_song_script(
            llm=llm,
            theme=req.theme,
            custom_lyrics=req.custom_lyrics,
            style_hint=style_hint,
            language=req.language,
            dialect=dialect,
            vocal_gender=req.vocal_gender,
        )
```

- [ ] **Step 4: Persist the new fields in `song.json`**

In the `song.json` write block (~line 2827), add three keys inside the JSON dict (next to `"style_prompt"`):

```python
            "negative_tags": script.negative_tags,
            "style_source": script.style_source,
            "writer_tier": script.writer_tier,
```

`run.py:1061` already reads `script.get("negative_tags")` first, so the
producer's per-genre negatives now flow to Suno with no worker change; the
hardcoded default remains the last-ditch fallback for older runs.

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_song_api.py::test_post_songs_persists_producer_fields -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add pipeline/api.py tests/test_song_api.py
git commit -m "$(cat <<'EOF'
feat(song): persist producer fields + thread vocal_gender on create

song.json now carries negative_tags/style_source/writer_tier; POST /songs
passes vocal_gender into the producer pass so the vocal descriptor matches.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: The Approach-B seam (config flag + no-op maybe_master)

**Files:**
- Modify: `pipeline/config.py` (`SongConfig.master_pass`)
- Modify: `config.yaml` (`song.master_pass: false`)
- Modify: `pipeline/song_assemble.py` (`maybe_master`)
- Modify: `run.py` (call `maybe_master` after the take copy)
- Test: `tests/test_song_assemble.py` (add cases)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_song_assemble.py`:

```python
from types import SimpleNamespace

from pipeline.song_assemble import maybe_master


def test_maybe_master_noop_when_flag_off(tmp_path):
    mp3 = tmp_path / "song.mp3"
    mp3.write_bytes(b"fake")
    cfg = SimpleNamespace(song=SimpleNamespace(master_pass=False))
    assert maybe_master(mp3, cfg) is False


def test_maybe_master_noop_when_flag_on_not_yet_implemented(tmp_path):
    mp3 = tmp_path / "song.mp3"
    mp3.write_bytes(b"fake")
    cfg = SimpleNamespace(song=SimpleNamespace(master_pass=True))
    # Seam exists; Approach B not built yet → still a no-op, never raises.
    assert maybe_master(mp3, cfg) is False


def test_maybe_master_handles_missing_song_config(tmp_path):
    mp3 = tmp_path / "song.mp3"
    mp3.write_bytes(b"fake")
    assert maybe_master(mp3, SimpleNamespace(song=None)) is False


def test_maybe_master_never_shells_out_even_when_flag_on(tmp_path, monkeypatch):
    # Locks the seam contract: Approach B is NOT built, so maybe_master must
    # not invoke ffmpeg/subprocess under any branch — including flag ON.
    import subprocess
    def _boom(*a, **k):
        raise AssertionError("maybe_master must not shell out (seam is a no-op)")
    monkeypatch.setattr(subprocess, "run", _boom)
    monkeypatch.setattr(subprocess, "Popen", _boom)
    mp3 = tmp_path / "song.mp3"
    mp3.write_bytes(b"fake")
    assert maybe_master(mp3, SimpleNamespace(song=SimpleNamespace(master_pass=True))) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_song_assemble.py -k maybe_master -v`
Expected: FAIL — `cannot import name 'maybe_master'`.

- [ ] **Step 3: Add `maybe_master` to `pipeline/song_assemble.py`**

Add `from pathlib import Path` is already imported. Append:

```python
def maybe_master(mp3_path: Path, cfg) -> bool:
    """Approach-B seam (optional free tonal-master pass). Returns True if a
    master pass ran. Currently ALWAYS a no-op — the flag + call site exist so
    Approach B is a contained drop-in later. When built, this applies (in
    ffmpeg): high-pass rumble cut, de-ess, gentle compression, and a -1 dBTP
    true-peak limiter. It must NOT loudnorm — Suno already ships at -14 LUFS.
    See docs/superpowers/specs/2026-07-27-song-producer-pass-design.md."""
    if not (cfg and getattr(cfg, "song", None)
            and getattr(cfg.song, "master_pass", False)):
        return False
    print("[song] master_pass is enabled but the Approach-B chain is not "
          "implemented yet — skipping (no-op).")
    return False
```

- [ ] **Step 4: Add the config field**

In `pipeline/config.py`, add to `SongConfig` (after `bars_per_cut`):

```python
    master_pass: bool = False   # Approach-B tonal master (seam only; not built)
```

In `config.yaml`, under `song:` (after `bars_per_cut: 4`):

```yaml
  master_pass: false            # Approach B (ffmpeg tonal master) — seam only,
                                # not yet implemented. See spec
                                # 2026-07-27-song-producer-pass.
```

- [ ] **Step 5: Call the seam from the worker**

In `run.py`, immediately after `write_state(chosen_take=chosen)` (~line 1131, end of the song-generation stage), add (use the module already imported at the top of the function — `song_assemble` is in scope):

```python
            # Approach-B seam: no-op today (see maybe_master docstring); the
            # return value is intentionally ignored until B is built.
            song_assemble.maybe_master(song_mp3, cfg)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_song_assemble.py -k maybe_master -v`
Expected: PASS (3 tests).

- [ ] **Step 7: Verify config still loads**

Run: `uv run python -c "from pipeline.config import load_config; from pathlib import Path; c = load_config(Path('config.yaml')); print('master_pass =', c.song.master_pass)"`
Expected: prints `master_pass = False` (no TypeError from the new key).

- [ ] **Step 8: Commit**

```bash
git add pipeline/song_assemble.py pipeline/config.py config.yaml run.py tests/test_song_assemble.py
git commit -m "$(cat <<'EOF'
feat(song): reserve Approach-B master-pass seam (no-op) + config flag

maybe_master() + song.master_pass flag + worker call site. Always a no-op
today; keeps the C-shape so the ffmpeg tonal master drops in later without
touching the producer-pass work.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Full-suite verification

**Files:** none (verification only)

- [ ] **Step 1: Run the entire test suite**

Run: `uv run pytest`
Expected: PASS (all green, including pre-existing tests). If any song/API test broke because it stubbed `_build_song_llm`/`generate_song_script` with a single-return mock that now also feeds the producer call, fix it to route (see `_routing_llm` in Task 4) or assert the recipe-fallback behavior — do NOT weaken the producer logic to satisfy a stale stub.

- [ ] **Step 2: Smoke-test the deterministic path end-to-end (no network)**

Run:
```bash
uv run python -c "
from pipeline.song_style import compose_style
class Down:
    def complete(self, p, system=None): raise RuntimeError('offline')
r = compose_style(Down(), theme='أغنية خليجية عن الفراق', title='t',
                  lyrics='[Verse 1]\nx\n[Chorus]\ny', language='ar',
                  dialect='khaleeji', style_hint=None, vocal_gender='m')
print('genre =', r.genre_key); print('source =', r.source)
print('style =', r.style_prompt); print('neg =', r.negative_tags)
"
```
Expected: `genre = khaleeji`, `source = fallback:recipe`, a style string containing `mixed and mastered` and `male vocal`, and negatives containing `robotic vocal`.

- [ ] **Step 3: Final commit (if Step 1 required test fixups)**

```bash
git add -A
git commit -m "$(cat <<'EOF'
test(song): fix stale single-return LLM stubs for the producer pass

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Follow-ups (out of scope — noted, not built)

- **Approach B:** implement the `maybe_master` ffmpeg chain behind `song.master_pass`.
- **Best-of-N takes** (~$0.15): the biggest remaining quality jump if the cost budget is reconsidered.
- **Flutter surfacing:** show `writer_tier`/`style_source` on the review screen if the existing quality banner (`/system/llm-status`) doesn't already cover it.
- **Config check:** if production lacks `ANTHROPIC_API_KEY`, `writer_tier` will read `gemini`/`groq` — the cheapest single win is to fund the Anthropic key.
- **Artist `default_vocal_gender` → producer pass (bug, found in Task 5 review):** the artist's `default_vocal_gender` is not threaded into `compose_style`'s vocal descriptor, so a female-persona artist can get a "male vocal" steer. Two call sites: (a) `create_song`'s artist-inherit block (`api.py` ~2780) must inherit `vocal_gender` from the artist when the request didn't set it — needs `req.model_fields_set` since the field defaults to truthy `"m"`, so a plain `if not req.vocal_gender` won't distinguish "unset" from "explicitly male"; (b) `_write_song_draft` (`api.py` ~925) already computes `artist.get("default_vocal_gender") or "m"` for the `song.json` write but never passes it into `generate_song_script`. Fix both together with an artist-inheritance test in each direction (m and f).
- **`regenerate-lyrics` drops persisted fields (pre-existing):** `api.py`'s regenerate-lyrics rebuilds `song.json` from scratch with only title/lyrics/style_prompt/cover_prompt/language, silently dropping `negative_tags`/`style_source`/`writer_tier` (and `vocal_gender`/`persona_id`/`suno_model`/`video_mode`/`art_direction`/`scene_prompts`). Preserve the existing keys on regen (mutate-in-place like regenerate-cover-prompt does). NOTE: this is now the ONLY generation entry point that drops the producer fields — the create, morning-draft, and YouTube-import/upload-cover `song.json` writes all persist them (fixed during the final holistic review).
- **`regenerate-cover-prompt` double-cost (minor):** that endpoint calls `generate_song_script` only for `cover_prompt` but now also pays for the producer-pass LLM call (output discarded). Cheap (pre-approval LLM cents), but a `run_producer=False` skip param on `generate_song_script` would avoid it.
