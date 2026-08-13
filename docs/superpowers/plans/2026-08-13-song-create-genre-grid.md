# Song Create Screen Genre Grid Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the hidden style-preset chips on the song create screen with a visible soft-gradient **genre grid**, restructure the screen into a Simple/Advanced split, and honor the picked genre exactly via a new explicit `genre` parameter threaded to the style engine.

**Architecture:** A new optional `genre` string flows UI → API → writer pass → `compose_style(forced_genre_key=…)`. When present and valid it overrides keyword inference; when absent (the **Auto** tile) behavior is byte-for-byte today's `infer_genre()`. The Flutter side gains a data catalog (`song_genres.dart`), a reusable `GenreGrid` widget, and a restructured `NewSongScreen`.

**Tech Stack:** Python 3 / FastAPI / pytest (backend); Flutter / Dart / flutter_test (frontend). Song engine = Suno via `pipeline/song_style.py` genre recipes.

## Global Constraints

_Every task's requirements implicitly include this section._

- **Branch:** work on `feat/song-create-genre-grid` (already created; the spec is committed there).
- **Python:** every file starts with `from __future__ import annotations`; use `pathlib.Path`, never `os.path`; imports absolute from package root (`from pipeline.x import y`).
- **Tests never hit real APIs.** Replace external calls via `monkeypatch` / stub LLMs. (Repo invariant.)
- **Run pytest in a CLEAN shell — do NOT `source .env`.** Sourcing `.env` flips the failing set. (Memory: `reference_test_suite_verification`.)
- **`flutter analyze` hangs in this environment → use `dart analyze <files>`** for static checks; use `flutter test <file>` for widget/unit tests. (Same memory.)
- **Genre keys MUST exactly equal `GENRE_RECIPES` keys** in `pipeline/song_style.py`: `arabic_pop, arabic_ballad, khaleeji, tarab_classic, arabic_trap, folk_shaabi, hiphop_rap, rnb_soul, pop, rock, edm_electropop, cinematic_ost`. `generic` is **never** a grid tile.
- **Auto (no `genre`) = unchanged behavior.** Fully backward compatible; the approve-before-spend flow is untouched.
- **Flutter theme:** light/glass only. Use `FacelessTheme.*` tokens (`accent`, `surface2`, `border`, `textPrimary`, `textSecondary`, `faint`) and `FacelessTheme.build()`. RTL-aware (AR/EN).
- **Flutter package name is `faceless`** (test imports: `package:faceless/...`).
- **Commit after each task** (message convention: end body with the repo's `Co-Authored-By:` trailer used on the spec commit).

---

## File structure

| File | Responsibility | New/Modify |
|---|---|---|
| `pipeline/song_style.py` | `compose_style` gains `forced_genre_key` resolution. | Modify |
| `pipeline/song_lyrics.py` | `generate_song_script` gains `genre_key`, forwards it. | Modify |
| `pipeline/api.py` | `CreateSongRequest.genre` + forward in `create_song`. | Modify |
| `lib/ui/song_genres.dart` | Genre catalog: keys, emoji, gradients, arabicOnly, labels, language filter + validity helpers. | **Create** |
| `lib/widgets/genre_grid.dart` | Reusable `GenreGrid` widget (Auto tile + gradient tiles, selection). | **Create** |
| `lib/api/client.dart` | `createSong` gains `genre`. | Modify |
| `lib/screens/new_song_screen.dart` | Simple/Advanced restructure; wire `GenreGrid`; `initialPresetLabel`→`initialGenreKey`. | Modify |
| `lib/screens/home_screen.dart` | Migrate empty-state sample entry points to `initialGenreKey`. | Modify |
| `lib/l10n/app_en.arb`, `app_ar.arb` | Genre labels + new UI strings; regenerate `app_localizations_*`. | Modify |
| `tests/test_song_style.py`, `tests/test_song_lyrics.py`, `tests/test_song_api.py` | Backend tests. | Modify |
| `test/song_genres_test.dart`, `test/genre_grid_test.dart`, `test/create_song_genre_test.dart` | Flutter tests. | **Create** |

---

## Task 1: Backend — `compose_style` accepts `forced_genre_key`

**Files:**
- Modify: `pipeline/song_style.py:370-376` (`compose_style` signature + genre resolution)
- Test: `tests/test_song_style.py` (append)

**Interfaces:**
- Produces: `compose_style(llm, *, theme, title, lyrics, language, dialect, style_hint, vocal_gender, forced_genre_key: str | None = None) -> StyleResult`. Resolution: use `forced_genre_key` iff it is a key in `GENRE_RECIPES`, else `infer_genre(theme, style_hint, language, dialect)`. `StyleResult.genre_key` reflects the resolved key.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_song_style.py` (reuses the existing `_StubLLM` and `_compose` helpers already in that file):

```python
def test_compose_style_forced_genre_overrides_inference():
    # "حزينة" → infer_genre would pick arabic_ballad; force rock instead.
    # _StubLLM(raises=True) forces the recipe fallback so genre_key is deterministic.
    res = compose_style(
        _StubLLM(raises=True),
        theme="أغنية حزينة عن الفراق", title="عنوان",
        lyrics="[Verse 1]\nكلمات\n[Chorus]\nلازمة",
        language="ar", dialect=None, style_hint=None, vocal_gender="m",
        forced_genre_key="rock",
    )
    assert res.genre_key == "rock"
    assert "distorted electric guitars" in res.style_prompt  # rock recipe instrumentation


def test_compose_style_invalid_forced_genre_falls_back_to_inference():
    res = compose_style(
        _StubLLM(raises=True),
        theme="أغنية حزينة عن الفراق", title="عنوان",
        lyrics="[Verse 1]\nكلمات\n[Chorus]\nلازمة",
        language="ar", dialect=None, style_hint=None, vocal_gender="m",
        forced_genre_key="not_a_real_genre",
    )
    assert res.genre_key == "arabic_ballad"


def test_compose_style_none_forced_genre_uses_inference():
    res = compose_style(
        _StubLLM(raises=True),
        theme="أغنية حزينة عن الفراق", title="عنوان",
        lyrics="[Verse 1]\nكلمات\n[Chorus]\nلازمة",
        language="ar", dialect=None, style_hint=None, vocal_gender="m",
    )
    assert res.genre_key == "arabic_ballad"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_song_style.py -k forced_genre -v`
Expected: FAIL — `compose_style() got an unexpected keyword argument 'forced_genre_key'`.

- [ ] **Step 3: Implement** — edit `compose_style` in `pipeline/song_style.py`:

```python
def compose_style(llm, *, theme: str, title: str, lyrics: str, language: str,
                  dialect: str | None, style_hint: str | None,
                  vocal_gender: str | None,
                  forced_genre_key: str | None = None) -> StyleResult:
    """Producer pass: strongest-model style prompt, recipe fallback on
    failure or weak output. Never raises — always returns a usable steer.

    If ``forced_genre_key`` names a real recipe it is honored exactly
    (the create screen's genre grid); otherwise genre is inferred as before.
    """
    genre_key = (forced_genre_key
                 if forced_genre_key in GENRE_RECIPES
                 else infer_genre(theme, style_hint, language, dialect))
    recipe = GENRE_RECIPES[genre_key]
    fb_style, fb_neg = _recipe_style(recipe, vocal_gender, style_hint)
    # ... rest unchanged ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_song_style.py -v`
Expected: PASS (all existing + 3 new).

- [ ] **Step 5: Commit**

```bash
git add pipeline/song_style.py tests/test_song_style.py
git commit -m "feat(song): compose_style honors an explicit forced_genre_key"
```

---

## Task 2: Backend — `generate_song_script` forwards `genre_key`

**Files:**
- Modify: `pipeline/song_lyrics.py:225-234` (signature) and `:310-314` (the `compose_style` call)
- Test: `tests/test_song_lyrics.py` (append)

**Interfaces:**
- Consumes: `compose_style(..., forced_genre_key=…)` from Task 1.
- Produces: `generate_song_script(*, llm, theme, custom_lyrics, style_hint, language, dialect=None, vocal_gender="m", genre_key: str | None = None) -> SongScript`. `genre_key` is forwarded verbatim to `compose_style(forced_genre_key=genre_key)`.

- [ ] **Step 1: Write the failing test** — append to `tests/test_song_lyrics.py` (reuses the module's `_stub_llm` helper):

```python
def test_generate_song_script_forwards_genre_key(monkeypatch):
    from pipeline import song_lyrics as sl
    captured = {}
    real = sl.compose_style

    def spy(llm, **kwargs):
        captured["forced_genre_key"] = kwargs.get("forced_genre_key")
        return real(llm, **kwargs)

    monkeypatch.setattr(sl, "compose_style", spy)
    llm = _stub_llm("""{
        "title": "T",
        "lyrics": "[Verse 1]\\na\\n[Chorus]\\nb",
        "style_prompt": "pop, 100 BPM, synths, male vocal, 2020s, major key",
        "cover_prompt": "a bright city skyline"
    }""")
    sl.generate_song_script(
        llm=llm, theme="x", custom_lyrics=None, style_hint=None,
        language="ar", genre_key="rock",
    )
    assert captured["forced_genre_key"] == "rock"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_song_lyrics.py -k forwards_genre_key -v`
Expected: FAIL — `generate_song_script() got an unexpected keyword argument 'genre_key'`.

- [ ] **Step 3: Implement** — two edits in `pipeline/song_lyrics.py`:

Signature (add the trailing param):
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
    genre_key: str | None = None,
) -> SongScript:
```

The `compose_style` call (~line 310) — add the forward:
```python
    style = compose_style(
        llm, theme=theme, title=parsed["title"], lyrics=lyrics,
        language=language, dialect=dialect, style_hint=style_hint,
        vocal_gender=vocal_gender, forced_genre_key=genre_key,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_song_lyrics.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/song_lyrics.py tests/test_song_lyrics.py
git commit -m "feat(song): generate_song_script forwards genre_key to compose_style"
```

---

## Task 3: Backend — API `genre` field + forward in `create_song`

**Files:**
- Modify: `pipeline/api.py:398-426` (`CreateSongRequest`) and `:3593-3601` (the `generate_song_script` call inside `create_song`)
- Test: `tests/test_song_api.py` (append; reuses the `app` fixture + `_find_run_dir`)

**Interfaces:**
- Consumes: `generate_song_script(..., genre_key=…)` from Task 2.
- Produces: HTTP `POST /songs` accepts an optional `"genre"` string; it is forwarded to the writer pass as `genre_key`. Absent/invalid → Auto (inference).

- [ ] **Step 1: Write the failing tests** — append to `tests/test_song_api.py`:

```python
def test_post_songs_forces_genre(app):
    # The canned writer LLM style is "weak" (no spine tokens) → compose_style
    # falls back to the forced recipe. genre=rock → rock recipe instrumentation
    # ("distorted electric guitars") must appear even for an Arabic theme.
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    r = client.post(
        "/songs",
        json={"theme": "أغنية حزينة عن الفراق", "language": "ar",
              "genre": "rock", "ownership_attested": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    run_dir = _find_run_dir(r.json()["run_id"])
    song_json = json.loads((run_dir / "song.json").read_text())
    assert "distorted electric guitars" in song_json["style_prompt"]


def test_post_songs_without_genre_infers_arabic(app):
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    r = client.post(
        "/songs",
        json={"theme": "أغنية حزينة عن الفراق", "language": "ar",
              "ownership_attested": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    run_dir = _find_run_dir(r.json()["run_id"])
    song_json = json.loads((run_dir / "song.json").read_text())
    assert "distorted electric guitars" not in song_json["style_prompt"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_song_api.py -k genre -v`
Expected: `test_post_songs_forces_genre` FAILS (rock tokens absent — genre ignored); `test_post_songs_without_genre_infers_arabic` may pass. The forcing test is the gate.

- [ ] **Step 3: Implement** — two edits in `pipeline/api.py`:

Add to `CreateSongRequest` (after `quality_tier`, before `ownership_attested`):
```python
    # Explicit genre from the create-screen grid. Must be a GENRE_RECIPES key;
    # an unknown value is treated as None (Auto) by compose_style, not an error.
    # None → keyword inference (unchanged behavior).
    genre: str | None = None
```

In `create_song`, the `generate_song_script(...)` call (~line 3593) — add the forward:
```python
        script = generate_song_script(
            llm=llm,
            theme=req.theme,
            custom_lyrics=req.custom_lyrics,
            style_hint=style_hint,
            language=req.language,
            dialect=dialect,
            vocal_gender=req.vocal_gender,
            genre_key=req.genre,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_song_api.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/api.py tests/test_song_api.py
git commit -m "feat(song): POST /songs accepts explicit genre, forwarded to writer pass"
```

---

## Task 4: Flutter — l10n strings + genre catalog

**Files:**
- Modify: `lib/l10n/app_en.arb`, `lib/l10n/app_ar.arb` (add strings), then regenerate.
- Create: `lib/ui/song_genres.dart`
- Test: `test/song_genres_test.dart`

**Interfaces:**
- Produces:
  - `class SongGenre { final String key; final String emoji; final List<Color> gradient; final bool arabicOnly; String label(AppLocalizations l); }`
  - `const List<SongGenre> kSongGenres` (12 entries; keys per Global Constraints; `generic` excluded).
  - `List<SongGenre> genresForLanguage(String language)` — all 12 when `language.startsWith('ar')`, else the 6 non-`arabicOnly`.
  - `bool isGenreValidForLanguage(String? key, String language)` — `true` for `null` (Auto) or any key present in `genresForLanguage(language)`.

- [ ] **Step 1: Add l10n strings** — add these keys to `lib/l10n/app_en.arb` (and Arabic equivalents to `app_ar.arb`). English:

```json
  "genrePickerLabel": "Pick a genre",
  "genrePickerHint": "Auto = let AI decide",
  "genreAuto": "Auto",
  "genreArabicPop": "Arabic Pop",
  "genreArabicBallad": "Ballad",
  "genreKhaleeji": "Khaleeji",
  "genreTarab": "Tarab",
  "genreArabicTrap": "Trap",
  "genreShaabi": "Shaabi",
  "genreHipHop": "Hip-Hop",
  "genreRnb": "R&B",
  "genrePop": "Pop",
  "genreRock": "Rock",
  "genreEdm": "EDM",
  "genreCinematic": "Cinematic",
  "advancedOptions": "Advanced options",
  "addMyLyrics": "Write my own lyrics"
```

Arabic (`app_ar.arb`): `genrePickerLabel` "اختر النوع", `genrePickerHint` "تلقائي = دع الذكاء يقرر", `genreAuto` "تلقائي", `genreArabicPop` "بوب عربي", `genreArabicBallad` "بالاد", `genreKhaleeji` "خليجي", `genreTarab` "طرب", `genreArabicTrap` "تراب", `genreShaabi` "شعبي", `genreHipHop` "هيب هوب", `genreRnb` "آر أند بي", `genrePop` "بوب", `genreRock` "روك", `genreEdm` "إلكترونيك", `genreCinematic` "سينمائي", `advancedOptions` "خيارات متقدمة", `addMyLyrics` "اكتب كلماتي". (Match the `@`-metadata style already used in the arb files if present.)

- [ ] **Step 2: Regenerate localizations**

Run: `flutter gen-l10n`
Expected: `lib/l10n/app_localizations*.dart` updated with the new getters (e.g. `l10n.genreArabicPop`).

- [ ] **Step 3: Write the failing test** — create `test/song_genres_test.dart`:

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:faceless/ui/song_genres.dart';

void main() {
  test('arabic shows 12 genres, other languages show 6', () {
    expect(genresForLanguage('ar').length, 12);
    expect(genresForLanguage('en').length, 6);
    expect(genresForLanguage('fr').length, 6);
  });

  test('generic is never a tile', () {
    expect(kSongGenres.any((g) => g.key == 'generic'), isFalse);
  });

  test('english excludes arabic-only genres', () {
    final en = genresForLanguage('en').map((g) => g.key).toSet();
    expect(en.contains('khaleeji'), isFalse);
    expect(en.contains('tarab_classic'), isFalse);
    expect(en.contains('pop'), isTrue);
    expect(en.contains('rock'), isTrue);
  });

  test('isGenreValidForLanguage', () {
    expect(isGenreValidForLanguage('khaleeji', 'en'), isFalse);
    expect(isGenreValidForLanguage('khaleeji', 'ar'), isTrue);
    expect(isGenreValidForLanguage(null, 'en'), isTrue); // Auto always valid
  });
}
```

- [ ] **Step 4: Run test to verify it fails**

Run: `flutter test test/song_genres_test.dart`
Expected: FAIL — `Target of URI doesn't exist: 'package:faceless/ui/song_genres.dart'`.

- [ ] **Step 5: Implement the catalog** — create `lib/ui/song_genres.dart`:

```dart
import 'package:flutter/material.dart';

import '../l10n/l10n.dart';

/// A selectable genre tile for the create screen.
///
/// [key] MUST equal a GENRE_RECIPES key in pipeline/song_style.py — it is sent
/// to the backend as the forced genre. `generic` is intentionally NOT a tile
/// (it stays the inference fallback). Gradient colours are cosmetic.
class SongGenre {
  final String key;
  final String emoji;
  final List<Color> gradient;
  final bool arabicOnly;
  const SongGenre(this.key, this.emoji, this.gradient,
      {this.arabicOnly = false});

  String label(AppLocalizations l) => switch (key) {
        'arabic_pop' => l.genreArabicPop,
        'arabic_ballad' => l.genreArabicBallad,
        'khaleeji' => l.genreKhaleeji,
        'tarab_classic' => l.genreTarab,
        'arabic_trap' => l.genreArabicTrap,
        'folk_shaabi' => l.genreShaabi,
        'hiphop_rap' => l.genreHipHop,
        'rnb_soul' => l.genreRnb,
        'pop' => l.genrePop,
        'rock' => l.genreRock,
        'edm_electropop' => l.genreEdm,
        'cinematic_ost' => l.genreCinematic,
        _ => key,
      };
}

const kSongGenres = <SongGenre>[
  SongGenre('arabic_pop', '🎤', [Color(0xFFFFE3D3), Color(0xFFFBD0E0)], arabicOnly: true),
  SongGenre('arabic_ballad', '💔', [Color(0xFFE7DEF9), Color(0xFFD6E4FB)], arabicOnly: true),
  SongGenre('khaleeji', '🌙', [Color(0xFFD8F3E7), Color(0xFFCDECEF)], arabicOnly: true),
  SongGenre('tarab_classic', '🎻', [Color(0xFFFBEFCB), Color(0xFFF6E0C4)], arabicOnly: true),
  SongGenre('arabic_trap', '🔥', [Color(0xFFE4D9FA), Color(0xFFD9DEFB)], arabicOnly: true),
  SongGenre('folk_shaabi', '🪗', [Color(0xFFFCE1EC), Color(0xFFF3D9E9)], arabicOnly: true),
  SongGenre('hiphop_rap', '🎧', [Color(0xFFE1F0E6), Color(0xFFDCEFEA)]),
  SongGenre('rnb_soul', '🎹', [Color(0xFFDEE6F2), Color(0xFFE9E1F1)]),
  SongGenre('pop', '🎶', [Color(0xFFFFE9D8), Color(0xFFF7D9E6)]),
  SongGenre('rock', '🎸', [Color(0xFFE6E1F5), Color(0xFFD9DEFB)]),
  SongGenre('edm_electropop', '🎛️', [Color(0xFFD8F0F3), Color(0xFFCDE8EF)]),
  SongGenre('cinematic_ost', '🎬', [Color(0xFFDEE6F2), Color(0xFFE4DDEF)]),
];

List<SongGenre> genresForLanguage(String language) =>
    language.startsWith('ar')
        ? kSongGenres
        : kSongGenres.where((g) => !g.arabicOnly).toList();

bool isGenreValidForLanguage(String? key, String language) =>
    key == null || genresForLanguage(language).any((g) => g.key == key);
```

- [ ] **Step 6: Run test to verify it passes**

Run: `flutter test test/song_genres_test.dart`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add lib/ui/song_genres.dart lib/l10n/ test/song_genres_test.dart
git commit -m "feat(song): genre catalog + l10n strings for the create-screen grid"
```

---

## Task 5: Flutter — `GenreGrid` widget

**Files:**
- Create: `lib/widgets/genre_grid.dart`
- Test: `test/genre_grid_test.dart`

**Interfaces:**
- Consumes: `kSongGenres`, `genresForLanguage`, `SongGenre` from Task 4.
- Produces:
  ```dart
  class GenreGrid extends StatelessWidget {
    final String? selectedKey;          // null = Auto tile selected
    final String language;              // filters tiles
    final ValueChanged<String?> onChanged; // fires null when Auto tapped, else the genre key
    const GenreGrid({super.key, required this.selectedKey,
        required this.language, required this.onChanged});
  }
  ```

- [ ] **Step 1: Write the failing widget test** — create `test/genre_grid_test.dart` (wrapper mirrors `test/locale_switch_test.dart`):

```dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:faceless/l10n/l10n.dart';
import 'package:faceless/theme.dart';
import 'package:faceless/widgets/genre_grid.dart';

Widget _host(Widget child, {Locale locale = const Locale('en')}) => MaterialApp(
      locale: locale,
      theme: FacelessTheme.build(),
      supportedLocales: const [Locale('en'), Locale('ar')],
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      home: Scaffold(body: SingleChildScrollView(child: child)),
    );

void main() {
  testWidgets('renders Auto + universal genres for English', (t) async {
    await t.pumpWidget(_host(GenreGrid(
      selectedKey: null, language: 'en', onChanged: (_) {},
    )));
    await t.pumpAndSettle();
    expect(find.text('Auto'), findsOneWidget);
    expect(find.text('Pop'), findsOneWidget);
    expect(find.text('Khaleeji'), findsNothing); // arabic-only hidden for en
  });

  testWidgets('shows arabic-only genres for Arabic', (t) async {
    await t.pumpWidget(_host(
      GenreGrid(selectedKey: null, language: 'ar', onChanged: (_) {}),
      locale: const Locale('ar'),
    ));
    await t.pumpAndSettle();
    expect(find.text('خليجي'), findsOneWidget);
  });

  testWidgets('tapping a genre fires onChanged with its key', (t) async {
    String? picked = 'sentinel';
    await t.pumpWidget(_host(GenreGrid(
      selectedKey: null, language: 'en', onChanged: (k) => picked = k,
    )));
    await t.pumpAndSettle();
    await t.tap(find.text('Rock'));
    expect(picked, 'rock');
  });

  testWidgets('tapping Auto fires onChanged with null', (t) async {
    String? picked = 'rock';
    await t.pumpWidget(_host(GenreGrid(
      selectedKey: 'rock', language: 'en', onChanged: (k) => picked = k,
    )));
    await t.pumpAndSettle();
    await t.tap(find.text('Auto'));
    expect(picked, isNull);
  });
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `flutter test test/genre_grid_test.dart`
Expected: FAIL — `Target of URI doesn't exist: 'package:faceless/widgets/genre_grid.dart'`.

- [ ] **Step 3: Implement the widget** — create `lib/widgets/genre_grid.dart`:

```dart
import 'package:flutter/material.dart';

import '../l10n/l10n.dart';
import '../theme.dart';
import '../ui/song_genres.dart';

/// Soft-gradient genre picker for the create screen. First tile is Auto
/// (selectedKey == null); the rest come from [genresForLanguage].
class GenreGrid extends StatelessWidget {
  final String? selectedKey;
  final String language;
  final ValueChanged<String?> onChanged;
  const GenreGrid({
    super.key,
    required this.selectedKey,
    required this.language,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final genres = genresForLanguage(language);
    return GridView.count(
      crossAxisCount: 3,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      mainAxisSpacing: 8,
      crossAxisSpacing: 8,
      childAspectRatio: 1.5,
      children: [
        _AutoTile(
          selected: selectedKey == null,
          label: l10n.genreAuto,
          onTap: () => onChanged(null),
        ),
        for (final g in genres)
          _GenreTile(
            genre: g,
            label: g.label(l10n),
            selected: selectedKey == g.key,
            onTap: () => onChanged(g.key),
          ),
      ],
    );
  }
}

class _TileShell extends StatelessWidget {
  final Widget child;
  final Gradient gradient;
  final bool selected;
  final VoidCallback onTap;
  const _TileShell({
    required this.child,
    required this.gradient,
    required this.selected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(14),
      child: Container(
        padding: const EdgeInsets.all(10),
        decoration: BoxDecoration(
          gradient: gradient,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(
            color: selected ? FacelessTheme.accent : Colors.white.withValues(alpha: 0.6),
            width: selected ? 2.5 : 1,
          ),
        ),
        child: child,
      ),
    );
  }
}

class _AutoTile extends StatelessWidget {
  final bool selected;
  final String label;
  final VoidCallback onTap;
  const _AutoTile({required this.selected, required this.label, required this.onTap});

  @override
  Widget build(BuildContext context) => _TileShell(
        selected: selected,
        onTap: onTap,
        gradient: const LinearGradient(colors: [Color(0xFFEAF7F0), Color(0xFFE4F3F4)]),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            const Text('✨', style: TextStyle(fontSize: 16)),
            Text(label,
                style: const TextStyle(
                    fontWeight: FontWeight.w600, fontSize: 12, color: FacelessTheme.accent)),
          ],
        ),
      );
}

class _GenreTile extends StatelessWidget {
  final SongGenre genre;
  final String label;
  final bool selected;
  final VoidCallback onTap;
  const _GenreTile({
    required this.genre,
    required this.label,
    required this.selected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) => _TileShell(
        selected: selected,
        onTap: onTap,
        gradient: LinearGradient(
          colors: genre.gradient,
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(genre.emoji, style: const TextStyle(fontSize: 16)),
            Text(label,
                style: const TextStyle(
                    fontWeight: FontWeight.w600, fontSize: 12, color: Color(0xFF3A2F36))),
          ],
        ),
      );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `flutter test test/genre_grid_test.dart`
Expected: PASS. (If `Colors.white.withValues` is unavailable on the pinned Flutter, use `Colors.white.withOpacity(0.6)`.)

- [ ] **Step 5: Commit**

```bash
git add lib/widgets/genre_grid.dart test/genre_grid_test.dart
git commit -m "feat(song): GenreGrid widget — soft gradient tiles + Auto"
```

---

## Task 6: Flutter — `createSong` gains `genre`

**Files:**
- Modify: `lib/api/client.dart:653-690` (`createSong` params + body)
- Test: `test/create_song_genre_test.dart`

**Interfaces:**
- Produces: `createSong({... , String? genre})`; the POST body includes `"genre": genre` **only when** `genre != null`.

- [ ] **Step 1: Write the failing test** — create `test/create_song_genre_test.dart` (mirrors `test/api_client_401_test.dart`):

```dart
import 'package:faceless/api/client.dart';
import 'package:faceless/api/settings.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

class _FixedSettings extends FacelessSettings {
  @override
  Future<String?> baseUrl() async => 'http://localhost:9999';
  @override
  Future<String?> tokenForLegacyMode() async => 'fake-dev-token';
}

void main() {
  test('createSong includes genre in body when set', () async {
    late String sent;
    final mock = MockClient((req) async {
      sent = req.body;
      return http.Response('{"run_id":"r1"}', 201);
    });
    final client = FacelessApiClient(_FixedSettings(), httpClient: mock);
    final id = await client.createSong(
        theme: 'x', genre: 'rock', ownershipAttested: true);
    expect(id, 'r1');
    expect(sent, contains('"genre":"rock"'));
  });

  test('createSong omits genre when null', () async {
    late String sent;
    final mock = MockClient((req) async {
      sent = req.body;
      return http.Response('{"run_id":"r1"}', 201);
    });
    final client = FacelessApiClient(_FixedSettings(), httpClient: mock);
    await client.createSong(theme: 'x', ownershipAttested: true);
    expect(sent.contains('genre'), isFalse);
  });
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `flutter test test/create_song_genre_test.dart`
Expected: FAIL — `createSong` has no named parameter `genre`.

- [ ] **Step 3: Implement** — in `lib/api/client.dart`, add `String? genre,` to the `createSong` parameter list and one line to the body map (place it beside the other optional fields):

```dart
  Future<String> createSong({
    required String theme,
    String? customLyrics,
    String? styleHint,
    String language = 'ar',
    String? personaId,
    String vocalGender = 'm',
    String? sunoModel,
    String videoMode = 'static',
    String? artistId,
    String? dialect,
    String qualityTier = 'standard',
    String? genre,
    bool ownershipAttested = false,
  }) async {
    final body = <String, dynamic>{
      'theme': theme,
      if (customLyrics != null && customLyrics.isNotEmpty) 'custom_lyrics': customLyrics,
      if (styleHint != null && styleHint.isNotEmpty) 'style_hint': styleHint,
      'language': language,
      if (dialect != null) 'dialect': dialect,
      if (personaId != null && personaId.isNotEmpty) 'persona_id': personaId,
      'vocal_gender': vocalGender,
      if (sunoModel != null) 'suno_model': sunoModel,
      'video_mode': videoMode,
      if (artistId != null) 'artist_id': artistId,
      'quality_tier': qualityTier,
      if (genre != null) 'genre': genre,
      'ownership_attested': ownershipAttested,
    };
    // ... POST unchanged ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `flutter test test/create_song_genre_test.dart`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/api/client.dart test/create_song_genre_test.dart
git commit -m "feat(song): createSong sends optional genre"
```

---

## Task 7: Flutter — restructure `NewSongScreen` (Simple/Advanced + grid) & migrate entry points

**Files:**
- Modify: `lib/screens/new_song_screen.dart` (remove presets, add grid + Advanced disclosure + genre state, `initialPresetLabel`→`initialGenreKey`)
- Modify: `lib/screens/home_screen.dart:233-248, 3200-3245` (empty-state sample entry points)
- Verify: `dart analyze lib/screens/new_song_screen.dart lib/screens/home_screen.dart` (clean) + manual smoke.

**Interfaces:**
- Consumes: `GenreGrid` (Task 5), `isGenreValidForLanguage` (Task 4), `createSong(genre:)` (Task 6).
- Produces: `NewSongScreen({..., String? initialGenreKey})` (replaces `initialPresetLabel`). `_openNewSongWithSample(String theme, String genreKey)` in `home_screen.dart`.

- [ ] **Step 1: Restructure the create screen state**

In `lib/screens/new_song_screen.dart`:
1. **Constructor:** replace `final String? initialPresetLabel;` with `final String? initialGenreKey;`; update the constructor param.
2. **Delete** the `_kStylePresets` constant, the `_presetLabel(...)` function, and the `_selectedPreset` field.
3. **Add state:** `String? _genreKey;` (null = Auto) and `bool _showLyrics = false;`.
4. **initState:** replace the `initialPresetLabel` block with:
   ```dart
   if (widget.initialGenreKey != null &&
       isGenreValidForLanguage(widget.initialGenreKey, _language)) {
     _genreKey = widget.initialGenreKey;
   }
   ```
   Add imports: `import '../ui/song_genres.dart';` and `import '../widgets/genre_grid.dart';`.

- [ ] **Step 2: Rebuild the theme-mode body**

In `build()`, theme-mode branch:
- Keep the **Describe your song** (`_themeCtrl`) field.
- Replace the always-visible custom-lyrics field with a disclosure: an `InkWell`/`TextButton` labelled `l10n.addMyLyrics` that toggles `_showLyrics`; show the `_lyricsCtrl` `TextField` only when `_showLyrics`.
- **Move the Language dropdown above the grid** and, in its `onChanged`, invalidate a now-illegal genre:
  ```dart
  onChanged: (v) => setState(() {
    _language = v ?? 'ar';
    if (!isGenreValidForLanguage(_genreKey, _language)) _genreKey = null;
  }),
  ```
- Insert the grid where the preset chips used to be:
  ```dart
  Text(l10n.genrePickerLabel, style: Theme.of(context).textTheme.labelLarge),
  const SizedBox(height: 8),
  GenreGrid(
    selectedKey: _genreKey,
    language: _language,
    onChanged: (k) => setState(() => _genreKey = k),
  ),
  const SizedBox(height: 16),
  ```
- Keep **Vocal** and **Video** segments visible in the Simple flow.

- [ ] **Step 3: Move power-user controls into an Advanced disclosure**

Wrap the **dialect dropdown, the style-hint TextField (`_styleCtrl`), the quality-tier segmented control, the Suno-model dropdown, and the persona dropdown** in a single `ExpansionTile(title: Text(l10n.advancedOptions), initiallyExpanded: false, children: [...])`. (These widgets already exist in the file — relocate them, don't rewrite their logic. The style-hint field stays bound to `_styleCtrl`; drop the now-removed `_selectedPreset` clearing in its `onChanged`.)

- [ ] **Step 4: Pass genre on submit**

In `_submit()`, the theme-mode `createSong(...)` call: add `genre: _genreKey,`. (Upload/cover mode is unchanged — it does not send a genre and hides the grid.)

- [ ] **Step 5: Static-check the screen**

Run: `dart analyze lib/screens/new_song_screen.dart`
Expected: No errors. (Fix any dangling references to the deleted `_kStylePresets`/`_presetLabel`/`_selectedPreset`/`initialPresetLabel`.)

- [ ] **Step 6: Migrate the home-screen entry points**

In `lib/screens/home_screen.dart`:
- `_openNewSongWithSample(String theme, String presetLabel)` → `_openNewSongWithSample(String theme, String genreKey)`, and change `initialPresetLabel: presetLabel` to `initialGenreKey: genreKey`.
- `_SongsEmptyState`: change the callback type to `void Function(String theme, String genreKey)` and update the two sample tuples (`:3209-3210`) so both Arabic ballad samples pass the genre key `'arabic_ballad'` instead of the old preset labels:
  ```dart
  ('🌙', 'أغنية رومانسية عن القمر والشوق', 'arabic_ballad'),
  ('💔', 'أغنية حزينة عن الفراق', 'arabic_ballad'),
  ```
  (The tuple's third element is now a genre key; rename the local `preset`/`presetLabel` variables to `genreKey` for clarity.)

- [ ] **Step 7: Static-check both screens**

Run: `dart analyze lib/screens/new_song_screen.dart lib/screens/home_screen.dart`
Expected: No errors.

- [ ] **Step 8: Manual smoke test** (the create screen renders authed — headless Chrome shows blank, so run the real app per memory `feedback_ide_run_strips_dart_defines`):

Run: `./scripts/run-app.sh` (chrome). Then: open **New song** → confirm the genre grid renders with **Auto** pre-selected; switch Language EN⇄AR and confirm Arabic-only tiles appear/disappear and a selected Arabic-only genre resets to Auto on switching to English; tap a genre; expand **Advanced options** and confirm dialect/style-hint/quality/model/persona are inside; generate a song and confirm the approve screen still appears.

- [ ] **Step 9: Commit**

```bash
git add lib/screens/new_song_screen.dart lib/screens/home_screen.dart
git commit -m "feat(song): create screen — genre grid + Simple/Advanced split"
```

---

## Task 8: Full verification & finish the branch

**Files:** none (verification only).

- [ ] **Step 1: Backend suite in a CLEAN env** (do NOT source `.env`):

Run: `uv run pytest tests/test_song_style.py tests/test_song_lyrics.py tests/test_song_api.py -v`
Expected: all PASS. Then a full run `uv run pytest -q` to confirm no regressions.

- [ ] **Step 2: Flutter tests + static analysis:**

Run: `flutter test test/song_genres_test.dart test/genre_grid_test.dart test/create_song_genre_test.dart`
Then: `dart analyze lib/ui/song_genres.dart lib/widgets/genre_grid.dart lib/screens/new_song_screen.dart lib/screens/home_screen.dart lib/api/client.dart`
Expected: tests PASS; analyze clean.

- [ ] **Step 3: Confirm no orphans** — grep proves the migration is complete:

Run: `grep -rn "initialPresetLabel\|_kStylePresets\|_selectedPreset\|_presetLabel" lib/`
Expected: **no matches**.

- [ ] **Step 4: Finish the branch** — use the `superpowers:finishing-a-development-branch` skill to decide merge/PR. (Do not merge to `main` without the user's go-ahead.)

---

## Self-review (completed by author)

- **Spec coverage:** §5.1 layout → Task 7; §5.2 grid behavior (Auto default, language filter, invalidation) → Tasks 4,5,7; §5.3 Advanced → Task 7; §5.4 catalog → Task 4; §5.5 backend param → Tasks 1,2,3,6; §5.6 migration (retire presets, remap entry points) → Task 7. All covered.
- **Placeholder scan:** every code step contains real code; test payloads are concrete; no "TBD/handle edge cases".
- **Type consistency:** `forced_genre_key` (Task 1) = the kwarg `generate_song_script` sends (Task 2) = fed by `CreateSongRequest.genre` (Task 3); Dart `genre`/`_genreKey`/`onChanged(String?)` names consistent across Tasks 4–7; `isGenreValidForLanguage` signature identical in Task 4 (def) and Task 7 (use).
