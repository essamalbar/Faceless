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
