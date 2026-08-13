# Song Create Screen Redesign — Genre Grid + Simple/Advanced Split

- **Date:** 2026-08-13
- **Status:** Approved (design) — ready for implementation plan
- **Surface:** Flutter app (`lib/screens/new_song_screen.dart`) + Python pipeline (`pipeline/`)
- **Origin:** Competitive analysis vs. *AI Song Generator – Jukebox* (`co.twowise.jukebox`) and *AI Song Generator, Cover Music* (`mp3.videomp3convert.ringtonemaker.recorder`). Both foreground a **visual genre grid**; our create screen hides genre behind 6 style-preset chips + keyword inference.

---

## 1. Summary

Redesign the song create screen so genre becomes a **visible, tappable grid** of soft-gradient tiles, and the screen splits into a clean **Simple** default view with an **Advanced** disclosure for power-user options. Wire the picked genre to the pipeline via a new **explicit optional `genre` parameter** so the user's choice is honored exactly (deterministic), while preserving today's zero-effort "let AI decide" path via an **Auto** tile.

This is a UX + light-touch backend change. It does **not** add new generation *modes* (Photo→Song, Voice→Song), does not change the billing/credits model, and does not touch the video pipeline.

## 2. Goals

- Genre is chosen by **tapping a tile**, not inferred silently or buried in free text.
- The default view is uncluttered: describe → pick genre → generate. Advanced controls are one tap away, not gone.
- The picked genre is **honored exactly** by the engine (no keyword-matching fragility).
- Fully backward compatible: **Auto** tile = today's `infer_genre()` behavior.
- Arabic-first: the grid offers all 12 grid-eligible genres for Arabic (6 Arabic-only + 6 universal) and the 6 universal genres for other languages.
- On-brand: soft pastel gradient tiles that fit the existing light/glass theme (`lib/theme.dart`, `lib/ui/brand.dart`).

## 3. Non-goals (explicitly out of scope)

- New creation modes (Photo→Song, Voice→Song, character/celebrity voice covers).
- Changes to the cover-a-song (upload-cover) flow beyond adopting the Advanced disclosure.
- `Artist.default_genre` (artists don't store a genre today) — noted as a **future follow-up**.
- Dark mode, home/gallery redesign, free-credits funnel — separate items from the competitive analysis.
- Any change to `GENRE_RECIPES` contents or the producer/A&R pipeline.

---

## 4. Current state (ground truth)

- **`lib/screens/new_song_screen.dart`** — a single long vertical form. Order: artist picker → mode `SegmentedButton` (`theme` | `upload`) → explainer → theme fields / upload fields → style-hint textfield → language dropdown → dialect dropdown (ar only) → vocal-gender dropdown → Suno-model dropdown → video-type segmented → quality-tier segmented → persona dropdown → ownership checkbox → Generate. Six `_kStylePresets` chips fill the style field in theme mode.
- **`pipeline/song_style.py`** — `GENRE_RECIPES` holds 13 recipes; `infer_genre(theme, style_hint, language, dialect)` picks one by keyword scan, language-gated by `_ARABIC_ONLY`. `compose_style(llm, *, theme, title, lyrics, language, dialect, style_hint, vocal_gender)` calls `infer_genre` internally (line ~375) — **no way to force a genre today**.
- **`pipeline/song_lyrics.py:310`** — `compose_style(...)` is called inside `generate_song_script(...)`.
- **`pipeline/api.py`** — `CreateSongRequest` (line 398) has no `genre` field; `POST /songs` / `create_song` (line 3520) forwards request fields to the writer pass; artist defaults fill empty fields (persona/style_hint/dialect).
- **`lib/api/client.dart:653`** — `createSong({...})` has no `genre` argument.

## 5. Design

### 5.1 Layout (approved via visual mockup)

**Simple view (default), theme mode — top to bottom:**
1. Artist picker row (existing; unchanged; hidden when no artists).
2. Mode toggle — `Write a theme` | `Cover a song` (existing SegmentedButton).
3. **Describe your song** (theme field).
4. **＋ Write my own lyrics** — a disclosure that reveals the custom-lyrics field (collapsed by default to keep Simple clean; auto-expanded if prefilled).
5. **Language** selector (Arabic / English / +3) — placed above the grid because it **filters** the grid.
6. **Genre grid** — the hero (see 5.2).
7. **Vocal** (Male / Female / Auto).
8. **Video** (Static / Cinematic · 3 cr).
9. **⚙️ Advanced options** — collapsed disclosure (see 5.3).
10. Ownership attestation (existing).
11. Generate + "review before spend" notice (existing).

**Cover-a-song mode:** genre grid is **hidden** (a cover follows its source). File picker + faithfulness + "your touch" stay; Advanced disclosure applies. Otherwise unchanged.

### 5.2 Genre grid behavior

- 3-column grid of **soft-gradient tiles** (direction A from the mockup): per-genre pastel gradient, emoji, name. Selected tile shows a green ring + check (reuse `FacelessTheme.accent`).
- First tile is **✨ Auto**, **selected by default**. Auto = no explicit genre → pipeline runs `infer_genre()` (today's behavior).
- Tapping a genre tile selects it (single-select) and deselects Auto. Tapping Auto clears any genre pick.
- **Language filter:** when language starts with `ar`, show all 12 grid-eligible genres (the 6 `_ARABIC_ONLY` + 6 universal); otherwise show only the 6 universal genres (non-`_ARABIC_ONLY`, non-`generic`). Grid rebuilds on language change. (`generic` is never a tile in either case.)
- **Language-switch invalidation:** if the currently selected genre is not valid for the new language (e.g. `khaleeji` after switching to English), reset selection to **Auto**.
- RTL: grid respects `Directionality`; emoji are direction-neutral. Labels come from l10n.

### 5.3 Advanced options (collapsed by default)

An `ExpansionTile`-style disclosure holding today's lower-frequency controls:
- Dialect (Arabic only).
- **Style hint** free-text ("fine-tune") — the field that `_kStylePresets` used to fill; now optional refinement that composes *with* the picked genre.
- Quality tier (Standard / Premium).
- Suno model (default V5.5 / V5 / V4.5 / V4).
- Voice / persona picker (shown only when personas exist).

### 5.4 Genre catalog — single source of truth

New file **`lib/ui/song_genres.dart`**: a `const` list of genre descriptors, each `(key, labelEn, labelAr, emoji, gradient, arabicOnly)`.
- **`key` must exactly equal a `GENRE_RECIPES` key**: `arabic_pop, arabic_ballad, khaleeji, tarab_classic, arabic_trap, folk_shaabi` (arabicOnly=true) and `hiphop_rap, rnb_soul, pop, rock, edm_electropop, cinematic_ost` (arabicOnly=false).
- `generic` is **never** a tile — it stays the `infer_genre` fallback only.
- Gradients defined with existing theme color family; labels wired through l10n (`app_en.arb` / `app_ar.arb`).
- Keeps `new_song_screen.dart` from bloating and gives one place to add genres later.

### 5.5 Backend wiring — explicit `genre` param (end-to-end)

Thread an optional `genre` string from UI to the style composer. Null/absent ⇒ Auto ⇒ unchanged inference.

1. **`lib/api/client.dart`** — `createSong({..., String? genre})`; include `"genre": genre` in the POST body only when non-null.
2. **`pipeline/api.py`** — `CreateSongRequest` gains `genre: str | None = None`. `create_song` forwards `req.genre` into the writer pass. (Artist genre-default is **not** applied — future follow-up. If `req.genre` is present but not a valid `GENRE_RECIPES` key, treat as `None` / Auto rather than erroring.)
3. **`pipeline/song_lyrics.py`** — `generate_song_script(...)` gains a `genre_key: str | None = None` parameter, forwarded to `compose_style(..., forced_genre_key=genre_key)`.
4. **`pipeline/song_style.py`** — `compose_style(...)` gains `forced_genre_key: str | None = None`. Resolution becomes:
   ```
   genre_key = forced_genre_key if (forced_genre_key in GENRE_RECIPES) else infer_genre(theme, style_hint, language, dialect)
   ```
   Everything downstream (recipe lookup, producer pass, fallback) is unchanged. Language-gating note: a forced Arabic-only key is honored even if language≠ar (the UI already prevents this combination; the backend does not second-guess an explicit pick).

**Rejected alternative — "stamp genre name into style_hint":** relies on `infer_genre`'s keyword match and silently breaks if the user edits the style field. Rejected for fragility; the explicit param is ~1 optional argument per layer and deterministic.

### 5.6 Migration

- The 6 `_kStylePresets` chips are **removed**; the grid replaces them. The style string they produced is superseded by genre recipes; users can still hand-write a style in the Advanced "style hint" field.
- **`initialPresetLabel`** entry points (empty-state "try this" chips, Trend Engine briefs) are remapped: instead of a preset label, callers pass an `initialGenreKey` (+ existing `initialTheme`/`initialStyleHint`). Audit call sites of `NewSongScreen(initialPresetLabel: ...)` and migrate each. If any caller can't be cleanly mapped, it falls back to Auto (safe).
- Auto paths that already skip the picker (Trend Engine `morning drafts`, premium best-of-N) pass no `genre` ⇒ Auto ⇒ unchanged.

## 6. Files touched

| File | Change |
|---|---|
| `lib/ui/song_genres.dart` | **New.** Genre catalog (keys, labels, emoji, gradients, arabicOnly). |
| `lib/screens/new_song_screen.dart` | Restructure into Simple/Advanced; add genre grid + `_genreKey` state; language-filter + invalidation; remove `_kStylePresets`; move dialect/style-hint/quality/model/persona into Advanced; lyrics disclosure. |
| `lib/api/client.dart` | `createSong` gains `genre`. |
| `lib/l10n/app_en.arb`, `app_ar.arb` | Genre labels + "Advanced options" / "Write my own lyrics" / "Pick a genre" strings. Regenerate `app_localizations_*`. |
| `pipeline/api.py` | `CreateSongRequest.genre`; forward in `create_song`; validate-or-ignore. |
| `pipeline/song_lyrics.py` | `generate_song_script` gains `genre_key`, forwarded to `compose_style`. |
| `pipeline/song_style.py` | `compose_style` gains `forced_genre_key`; resolution line updated. |
| Callers of `NewSongScreen(initialPresetLabel:)` | Remap to `initialGenreKey`. |

## 7. Testing

**Backend (pytest; external services mocked per repo invariants — never hit real APIs):**
- `compose_style(..., forced_genre_key="rock", theme="حب")` selects the `rock` recipe regardless of Arabic theme keywords (assert `StyleResult.genre_key == "rock"`).
- `forced_genre_key=None` and `forced_genre_key="not_a_key"` both fall through to `infer_genre` (unchanged behavior).
- `POST /songs` with `genre` round-trips into the writer pass; omitting `genre` behaves exactly as today.

**Flutter (widget tests):**
- Auto tile is selected on first build.
- Language = English hides `_ARABIC_ONLY` tiles; language = Arabic shows all 13.
- Tapping a genre tile updates `_genreKey` and visually selects it; tapping Auto clears it.
- Switching language while an Arabic-only genre is selected resets selection to Auto.
- Cover mode hides the grid.

## 8. Rollout & follow-ups

- Ship behind normal review; no feature flag needed (Auto default = current behavior, so risk is contained to the create screen).
- **Follow-ups (out of scope):** `Artist.default_genre` so releasing "as" an artist can pre-select a genre; surfacing genre on the approve/detail screens; the other competitive gaps (free-first-song funnel, Photo→Song, Voice→Song record button, instrumental toggle, credit packs).
