# Distribution — Release-Package Export (Route B) — Design Spec

**Date:** 2026-07-16
**Status:** Approved (user accepted the recommended route)
**Context:** Sub-project 3 of the Virtual Artist Label (i18n ✅ → Artist Core ✅
→ **Distribution**). Route B = free export MVP: the app assembles everything a
distributor (DistroKid et al.) needs into one download plus a guided
checklist. Designed so Route A (LabelGrid API automation) can replace the
manual upload step later without changing the package builder.

## Goal

One tap on a completed song produces a **store-ready release package**, and
the app walks the user through uploading it to a distributor. Songs can be
marked *released* so discographies show what's live on Spotify/Apple.

## Decisions

| # | Question | Decision |
|---|---|---|
| 1 | Route | B (export package) now; builder API shaped so LabelGrid (A) slots in later |
| 2 | Audio format | The chosen take's MP3 as-is (stores accept MP3; it's the best source we have — no fake "upscaling" to WAV) |
| 3 | Cover art | `cover.png` (1080×1080, title overlay is store-compliant) **upscaled to 3000×3000** Lanczos → JPEG quality 92 (stores want ≥1400px square) |
| 4 | Released state | Manual toggle (`released` bool in run state) — the user confirms after uploading; feeds the future royalties UI |
| 5 | Package scope | Per-song releases (singles). Album/EP grouping deferred |

## Package contents (`{artist-handle}-{song-slug}-release.zip`)

```
audio.mp3          ← chosen take (copy of song.mp3)
cover.jpg          ← 3000×3000 Lanczos upscale of cover.png
metadata.json      ← machine-readable (Route A feeds from this later)
metadata.txt       ← human-readable copy-paste sheet for the DistroKid form
lyrics.txt         ← plain lyrics (section tags stripped)
README.txt         ← 8-step DistroKid upload checklist (English; the in-app
                     dialog shows the localized version)
```

`metadata.json` fields: `title`, `artist_name`, `artist_handle`, `language`,
`explicit: false`, `genre` (derived from style_prompt's first segment, else
"World"), `lyrics_language`, `release_type: "single"`, `style_prompt`,
`generated_with: "Faceless Lab"`.

## Backend (`pipeline/api.py` + `pipeline/release.py`)

- **`pipeline/release.py`** (new, pure/testable):
  - `song_slug(title) -> str` (reuses artists.slugify_handle logic)
  - `upscale_cover(src: Path, dest: Path, size=3000)` — PIL Lanczos → JPEG q92
  - `strip_section_tags(lyrics) -> str`
  - `derive_genre(style_prompt) -> str`
  - `build_release_package(run_dir, artist: dict | None, out_zip: Path)` —
    assembles the zip; raises `ReleaseNotReady(missing=...)` listing what's
    absent (no song.mp3 / no cover.png / not complete)
- **`GET /songs/{run_id}/release-package`** — auth (header or query token,
  it's a browser download); 409 with the missing-items list when not ready;
  else streams the zip (`Content-Disposition` RFC 5987 for Arabic titles —
  same pattern as the video download). Package built into the run dir
  (`release.zip`, rebuilt on each request — cheap, always fresh).
- **`POST /songs/{run_id}/mark-released`** `{released: bool}` → state;
  `SongRunSummary.released: bool = False`.

## Flutter

- **Song detail** (complete songs): a **"Release to stores"** button →
  bilingual dialog: short explainer + the 8-step checklist + [Download
  package] (opens the release-package URL via url_launcher, like the MP4
  download) + [Mark as released] toggle calling mark-released.
- **Discography/song cards**: a small "● Released" badge when
  `summary.released`.
- All strings in BOTH ARB files (`release*` keys).

## Checklist copy (the 8 steps, localized in-app)

1. Download the release package. 2. Unzip it. 3. Create a DistroKid (or any
distributor) account. 4. "Upload" → choose `audio.mp3`. 5. Use `cover.jpg` as
the artwork. 6. Copy title/artist/genre/language from `metadata.txt`.
7. Paste `lyrics.txt` when asked. 8. Submit — stores go live in 1–7 days,
then return here and tap "Mark as released".

## Error handling

- Not complete / missing artifacts → 409 `{detail, missing: [...]}` → dialog
  shows what's missing instead of the download button.
- Song without an artist → package still builds; `artist_name` falls back to
  the song title's owner field (`"Faceless Artist"` default) and the dialog
  nudges: "assign an artist first for consistent branding" (non-blocking).
- Cover upscale failure → package builds WITHOUT cover.jpg + README notes it;
  the endpoint still succeeds (audio is the irreplaceable part).

## Testing

- **`tests/test_release.py`**: slug/genre/strip helpers; upscale produces
  3000×3000 JPEG (tiny PNG fixture); build_release_package zip contains the 6
  entries with correct metadata.json (artist attached and not); ReleaseNotReady
  lists missing artifacts.
- **`tests/test_api.py`**: endpoint 200 zip (magic bytes `PK`), 409 + missing
  list on incomplete run, mark-released toggles state + summary, query-token
  auth works.
- **Flutter**: analyzer clean; ARB parity green.

## Non-goals (v1)

- No LabelGrid/API automation (Route A — later, feeds from metadata.json).
- No royalty ingestion (needs Route A or manual CSV import — later).
- No album/EP bundling; singles only.
