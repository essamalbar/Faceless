# Artist Core — Design Spec

**Date:** 2026-07-15
**Status:** Approved (walked through with user)
**Context:** Sub-project 2 of the Virtual Artist Label direction (agreed order:
i18n ✅ → **Artist Core** → Distribution). Pivots the product unit from *song*
to *artist*: a persistent identity (name, voice, visuals, defaults) that
accumulates a discography. User chose the **full artist experience** for v1,
including the public artist page.

## Goal

Users create and run **virtual artists**. Each artist has a name, a pinned
singing voice (Suno Persona), a visual identity, and default style settings.
New songs are made *as* an artist and land in that artist's discography — in
the app and on a public shareable artist page.

## Decisions (resolved during brainstorming)

| # | Question | Decision |
|---|---|---|
| 1 | v1 scope | Full experience: entity + create flows + artist-first New Song + discography + public artist page |
| 2 | Voice creation | No paid audition wizard. Two doors: "Make this singer an artist" from any completed song (primary), or create the identity from scratch and attach the voice from a later song |
| 3 | Public page privacy | Reuses the existing share-token mechanism — an artist's public page lists only songs that have been shared. No new privacy model |
| 4 | Persona relationship | Persona stays the voice primitive; Artist wraps it. Deleting an artist keeps the persona and detaches (not deletes) songs |

## Data model

`artists.json` per user (same storage pattern as `personas.json`, under the
user's run-root):

```json
{
  "id": "art_<8 hex>",
  "name": "ليل",
  "handle": "layl",            // unique per user, slug for the public URL
  "bio": "…",                   // optional
  "persona_id": null,           // Kie personaId — the pinned voice; nullable
  "avatar_run_id": null,        // run whose cover.png is the avatar, or…
  "avatar_upload": null,        // …an uploaded file name under the user root
  "default_style": "arabic pop, 95 BPM…",
  "default_language": "ar",
  "default_vocal_gender": "m",
  "created_at": "2026-07-15T12:00:00+00:00"
}
```

Songs gain `artist_id` in `api_state.json` (set at create; patchable later).
`SongRunSummary` exposes `artist_id` + `artist_name` so lists filter
client-side without N+1 calls.

## Backend API (`pipeline/api.py`)

| Method | Path | Behavior |
|---|---|---|
| GET | `/artists` | list the user's artists (+ song_count computed from run states) |
| POST | `/artists` | create from scratch `{name, handle?, bio?, default_style?, default_language?, default_vocal_gender?}`; handle auto-slugged from name when omitted; duplicate handle → 409 with `suggested_handle` |
| PATCH | `/artists/{id}` | update identity fields, attach `persona_id`, set avatar (`avatar_run_id` or uploaded file) |
| DELETE | `/artists/{id}` | remove artist; songs keep playing but their `artist_id` is cleared; persona untouched |
| POST | `/artists/from-song` | one-step door: `{run_id, take, name, handle?}` → saves the take's voice as a persona (existing persona flow) AND creates the artist with `avatar_run_id=run_id`, `default_style` from the song's style_prompt |
| POST | `/artists/{id}/avatar` | multipart image upload (reuses the upload-cover file pattern; 422 non-image, 413 >10MB) |
| GET | `/artists/{id}/avatar` | serve the avatar (uploaded file, else the avatar run's cover.png, else 404 → client shows generated gradient) |
| GET | `/a/{handle}` | PUBLIC (no auth) server-rendered artist page: header + playable list of the artist's **shared** songs (share_token set), reusing the `/p/{token}` page building blocks |

`POST /songs` and `POST /songs/upload-cover` accept optional `artist_id`:
resolve the artist → default `persona_id`, `vocal_gender`, `language`,
`style_hint` (explicit request fields win) → stamp `artist_id` into state.
Unknown `artist_id` → 404 before any work.

## Flutter

- **Artists row** on the home Song tab: horizontally scrolled avatar circles +
  "＋ New artist"; tap → Artist screen.
- **Artist screen** (`lib/screens/artist_screen.dart`): header (avatar, name,
  bio, song count, share button copying `/a/{handle}`), discography (existing
  song cards filtered by `artist_id`), "New song as {name}" CTA (opens New
  Song with the artist preselected), edit/delete menu.
- **Create/edit artist sheet** (`lib/screens/artist_edit_screen.dart`): name,
  handle (auto-suggested, validation surface for 409), bio, default style
  (reuses the style presets), language, vocal gender, avatar (pick image or
  keep generated).
- **New Song**: Artist picker chips above the mode selector (None + artists);
  picking one prefills style/language/voice and locks `artist_id`.
- **Song detail**: "⭐ Make this singer an artist" (replaces/extends the
  existing save-voice flow) + "Add to artist" for assignment.
- **Avatar widget**: uploaded/run cover if available, else `coverGradient`
  placeholder with the artist's initial.
- All strings added to BOTH ARB files (parity test enforces).

## Public artist page

Server-rendered HTML (same approach as the existing share page): pastel light
brand, artist header, list of shared songs with inline audio/video playback
via the existing public token URLs, "Made with Faceless Lab" footer link.
Songs without a share token never appear. Empty state: artist card + "no
public songs yet".

## Error handling

- Duplicate handle → 409 `{detail, suggested_handle}` (client shows inline).
- Handles: lowercase `[a-z0-9-]{2,32}`, slugged from the name (Arabic names →
  transliteration-free fallback `artist-<id>` when the slug comes out empty).
- Deleting an artist: songs detached (state patched), persona kept.
- `/a/{unknown}` → 404 page in brand style.
- Artist without voice: New Song simply omits persona_id (Suno picks).

## Testing

- **pytest (mock externals per repo invariant):** artists CRUD + persistence;
  handle slugging/uniqueness/409 + suggestion; from-song creates persona+artist
  (persona call mocked); create-song with artist_id resolves defaults +
  stamps state (explicit fields win); delete detaches songs; avatar upload
  422/413/200; `/a/{handle}` renders shared songs only, 404 unknown.
- **Flutter:** analyzer zero errors; ARB parity holds; existing suite green.

## Non-goals (v1)

- No distribution/royalties (sub-project 3).
- No multi-user collaboration on an artist, no artist-level analytics.
- No voice cloning beyond Suno Personas (hard limit, per
  [[project_song_fidelity_cover]]).
