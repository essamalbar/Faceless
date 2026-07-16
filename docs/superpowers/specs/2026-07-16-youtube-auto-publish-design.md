# YouTube Auto-Publish — Design Spec

**Date:** 2026-07-16
**Status:** Approved (walked through with user)
**Context:** Station 4 of the "best system" roadmap — the first piece of the
Channel Autopilot, building on the Virtual Artist Label (i18n ✅, Artist Core
✅, Distribution ✅). Scope decisions: **YouTube only** in v1 (TikTok's API
audit is a separate 2–4-week battle — its own later phase), trigger =
**manual button + per-artist auto-publish toggle**.

## Goal

One tap (or zero, with the artist toggle) puts a finished song's video on the
user's YouTube channel with metadata auto-built from the song + artist — the
file never touches the user's device.

## The pre-audit privacy reality (disclosed, by design)

Google forces uploads from **unaudited API projects to private**. v1 therefore
uploads with `privacyStatus` from env `YOUTUBE_PRIVACY_STATUS` (default
`private`); the user flips videos public in YouTube Studio until their free
compliance audit passes, then the env flips to `public` — no code change.
The UI says this plainly on the publish dialog (per the disclosure rule).

## Architecture

### `pipeline/youtube.py` (new — plain `requests`, no new deps, fully mockable)

| Function | Responsibility |
|---|---|
| `auth_url(client_id, redirect_uri, state) -> str` | Google OAuth consent URL — scopes `youtube.upload youtube.readonly`, `access_type=offline`, `prompt=consent` |
| `exchange_code(client_id, client_secret, code, redirect_uri) -> dict` | code → `{refresh_token, access_token, ...}` via `oauth2.googleapis.com/token` |
| `refresh_access_token(client_id, client_secret, refresh_token) -> str` | refresh → short-lived access token |
| `channel_title(access_token) -> str` | `GET /youtube/v3/channels?part=snippet&mine=true` → the channel's display name |
| `upload_video(access_token, video_path, *, title, description, tags, privacy) -> str` | resumable upload: POST `uploadType=resumable` → `Location` → PUT bytes in one shot; returns the videoId. Raises `YouTubeError(msg)` with the API error surfaced |
| `build_metadata(song_json, state, artist, base_url) -> dict` | title `"{song} — {artist}"` (song only if no artist), description = 2-line lyrics teaser (section tags stripped, reuse `release.strip_section_tags`) + public artist page link + `#AI #music` + language tag, tags from style_prompt segments (≤500 chars total, YouTube cap) |

Token storage: `youtube_token.json` under the user's run-root (same pattern
as artists/personas): `{refresh_token, channel_title, connected_at}`.

### API (`pipeline/api.py`)

| Method | Path | Behavior |
|---|---|---|
| GET | `/auth/youtube/start` | auth'd. 503 if `YT_OAUTH_CLIENT_ID/SECRET` unset. Returns `{url}` — the Google consent URL with `state` = HMAC-signed user id (`FACELESS_API_TOKEN` as key, `ts` bound, 15-min expiry) |
| GET | `/auth/youtube/callback` | PUBLIC (Google redirects here). Verifies the signed state → exchanges the code → fetches channel title → writes `youtube_token.json` → redirects to `/app/` (or renders a tiny "connected — return to the app" page) |
| GET | `/auth/youtube/status` | auth'd. `{connected, channel_title}` |
| DELETE | `/auth/youtube` | auth'd. Deletes the token file (disconnect) |
| POST | `/songs/{run_id}/publish-youtube` | auth'd. Guards: song complete + `final.mp4` exists (409), YouTube connected (409), not already published (409, `{video_url}` included). Refresh token → upload → `_write_state(youtube_video_id=…, youtube_url=…)` → returns `{video_id, video_url}`. Upload errors → 502 with the API message |

`SongRunSummary` gains `youtube_url: str | None` (from state).

### Worker hook (`run.py`) — the auto-publish toggle

Artist gains `auto_publish_youtube: bool = False` (PatchArtistRequest +
ArtistSummary + Flutter toggle). At the END of a successful song post-approve
run (right after `status="complete"`): if the run has an `artist_id` whose
artist has the toggle ON and `youtube_token.json` exists → call the same
upload path → stamp `youtube_video_id/url`. Failures are logged +
`youtube_publish_error` written to state — they never fail the completed run.

### Flutter

- **Settings**: "YouTube" row — Connect (opens `{url}` via url_launcher) /
  "Connected: {channel}" + Disconnect. Status refreshed on screen open.
- **Song detail** (complete): "Publish to YouTube" button → dialog: metadata
  preview (title it will use), the pre-audit privacy note, [Publish] with
  progress; on success the button becomes "▶ On YouTube" opening the video URL.
- **Song cards / discography**: small ▶ badge when `youtube_url != null`.
- **Artist edit**: "Auto-publish new songs to YouTube" switch
  (`auto_publish_youtube` via patchArtist).
- All strings in BOTH ARB files (`yt*` keys).

### Config / deployment

- New env: `YT_OAUTH_CLIENT_ID`, `YT_OAUTH_CLIENT_SECRET` (Secret Manager,
  mapped onto the service + job like GROQ/YOUTUBE_API_KEY were), optional
  `YOUTUBE_PRIVACY_STATUS` (default `private`), `YT_OAUTH_REDIRECT` (defaults
  to `{PUBLIC_BASE_URL}/auth/youtube/callback`).
- One-time user setup (documented in the PR/summary): OAuth consent screen +
  Web client in their existing GCP project, redirect URI set to the prod
  callback; later the free YouTube API compliance audit to unlock public.

## Error handling

- Connect endpoints 503 when the OAuth client env is missing (feature dark
  until configured — nothing else breaks).
- Callback with bad/expired state → 403 page.
- Publish without connection → 409 `{detail: "youtube not connected"}` →
  the dialog deep-links to Settings.
- Re-publish guard → 409 with the existing URL (idempotent UX).
- Auto-publish failure → state `youtube_publish_error`, run stays complete.
- Token revoked by user on Google's side → refresh fails → 502 with
  "reconnect YouTube" hint; status endpoint reports disconnected on next
  check (refresh failure deletes the stale token file).

## Testing (externals mocked — repo invariant)

- `tests/test_youtube.py`: auth_url shape; exchange/refresh (mocked requests);
  resumable upload two-step (mocked POST→Location, PUT→videoId), error
  surfacing; build_metadata (with/without artist, tag cap, teaser strip).
- `tests/test_api.py`: start 503 unconfigured / 200 signed URL; callback
  verifies state + writes token (mocked exchange/channel); status/disconnect;
  publish happy path (mocked uploader) stamps state + summary `youtube_url`;
  409s (not complete / not connected / already published).
- `tests/test_run_song_mode.py`: completed run with toggle-ON artist +
  token file → uploader called once, state stamped (mocked); toggle OFF or
  no token → not called; uploader raising → run still completes with
  `youtube_publish_error`.
- Flutter: analyzer zero errors; ARB parity green.

## Non-goals (v1)

- TikTok (separate phase; draft-mode design when its developer app exists).
- Scheduling/queueing publishes; playlists; Shorts-specific metadata.
- Analytics ingestion (that's station 5 — the learning loop).
