# Artist Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Users create virtual artists (name + pinned voice + visuals + defaults) and make songs *as* an artist, with in-app discographies and a public artist page.

**Architecture:** New `pipeline/artists.py` storage module (artists.json per user, same pattern as personas.json) + REST endpoints in `pipeline/api.py` + `artist_id` threading through song creation + a server-rendered public page reusing the share mechanism. Flutter: artists row on home, artist screen, create/edit sheet, New Song artist picker — all strings in both ARB files.

**Tech Stack:** FastAPI, pytest (externals mocked), Flutter + gen-l10n.

**Spec:** `docs/superpowers/specs/2026-07-15-artist-core-design.md`

---

### Task B1: `pipeline/artists.py` — storage + slugging (TDD)

**Files:** Create `pipeline/artists.py`, `tests/test_artists.py`.

- [ ] Failing tests: `slugify_handle('ليل')=='artist-<id>' fallback`, `slugify_handle('Cool Artist!')=='cool-artist'`, load/save round-trip in tmp dir, `unique_handle` suggests `-2` suffix on collision, `new_artist` fills id/created_at.
- [ ] Implement: `ARTIST_HANDLE_RE = ^[a-z0-9-]{2,32}$`; `slugify_handle(name, artist_id)`; `load_artists(root: Path) -> list[dict]`; `save_artists(root, list)` (atomic temp+rename); `new_artist(*, name, handle, ...) -> dict`; `find_by_handle/id`.
- [ ] `uv run pytest tests/test_artists.py -v` → PASS; commit `feat(artists): storage module`.

### Task B2: API endpoints + song integration (TDD)

**Files:** Modify `pipeline/api.py`; Test: append to `tests/test_api.py`.

- [ ] Failing tests (client_factory pattern): GET/POST/PATCH/DELETE `/artists`; POST duplicate handle → 409 with `suggested_handle`; `POST /artists/from-song` (mock the persona-save internals) creates persona+artist with avatar_run_id + default_style from song.json; `POST /songs` with `artist_id` resolves persona/style/language defaults (explicit request fields win) and stamps `artist_id` in state, unknown artist → 404; DELETE artist clears `artist_id` from that user's song states; avatar upload 201/422/413 (reuse `_UPLOAD_AUDIO_MAX_BYTES` pattern with image types, cap 10MB); song summaries expose `artist_id`+`artist_name`.
- [ ] Implement endpoints beside the persona block (~line 3575), models `ArtistSummary`/`CreateArtistRequest`/`PatchArtistRequest`; wire `artist_id` into `create_song` + `upload_cover_song` + `SongRunSummary`.
- [ ] `uv run pytest tests/test_api.py -k artist -v` → PASS; full `tests/test_api.py` green; commit `feat(artists): API + song integration`.

### Task B3: public artist page `GET /a/{handle}`

**Files:** Modify `pipeline/api.py`; Test: append to `tests/test_api.py`.

- [ ] Failing tests: `/a/{handle}` 200 HTML contains artist name + ONLY shared songs (one with share_token, one without → only one appears); unknown handle → 404; page includes `/p/{token}` links.
- [ ] Implement: scan the artist's user run-root for song states with `artist_id==artist` AND `share_token`; render brand-styled HTML (reuse the `/p/{token}` page CSS approach — light pastel, white cards).
- [ ] Tests PASS; commit `feat(artists): public artist page`.

### Task F1: Flutter client + models

**Files:** Modify `lib/api/client.dart`, `lib/api/models.dart`.

- [ ] `Artist` model (`fromJson`), `SongSummary.artistId/artistName`; client: `listArtists`, `createArtist`, `patchArtist`, `deleteArtist`, `createArtistFromSong`, `uploadArtistAvatar` (multipart, mirrors uploadCoverSong), `artistAvatarUrl(id)`; `createSong`/`uploadCoverSong` gain `artistId`.
- [ ] `flutter analyze` clean on both files; commit.

### Task F2: Flutter UI (+ ARB strings)

**Files:** Create `lib/screens/artist_screen.dart`, `lib/screens/artist_edit_screen.dart`; Modify `lib/screens/home_screen.dart` (artists row), `lib/screens/new_song_screen.dart` (artist picker), `lib/screens/song_detail_screen.dart` (make-artist / add-to-artist), both ARB files.

- [ ] Artists row: avatar circles (uploaded → run cover → `coverGradient` initial), "＋" tile → edit screen (create mode).
- [ ] Artist screen: header + share (`/a/{handle}` copy), discography via existing song-card widgets filtered client-side, "New song as {name}" CTA → NewSongScreen(preselectedArtist), edit/delete menu (delete confirm).
- [ ] Edit screen: name (required), handle (auto-slug preview; 409 surfacing), bio, default style presets, language, vocal gender, avatar picker (file_picker image).
- [ ] New Song: artist chips (None + artists) above mode selector; selection prefills style/language/vocal and passes artistId on submit.
- [ ] Song detail: "Make this singer an artist" (name dialog → createArtistFromSong) and "Add to artist" (picker → patch song's artist).
- [ ] EVERY new string in BOTH `app_en.arb` + `app_ar.arb` (`artist*` keys); `flutter gen-l10n`; parity test green.
- [ ] `flutter analyze` zero errors; `flutter test` green; commit.

### Task V: verify + merge + deploy

- [ ] `uv run pytest` (bar known env failures) + `flutter test` + `flutter analyze` zero errors.
- [ ] Visual proof: headless screenshot of the public artist page (server-rendered, works logged-out) + landing sanity, both locales.
- [ ] Merge `feat/artist-core` → main, push (essamalbar), clean deploy (`flutter clean` first), verify live bundle md5 changed + `/artists` in openapi.json.

## Self-review
Spec coverage: data model→B1, API→B2, public page→B3, Flutter→F1/F2, bilingual→F2, error handling→B2/B3 tests, testing→every task. Types consistent: `artist_id` snake_case in API/state, `artistId` camelCase in Dart. No placeholders. ✔
