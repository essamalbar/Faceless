# Morning Drafts — Design Spec

**Date:** 2026-07-17
**Status:** Approved (user: "go on morning drafts")
**Context:** The Channel Autopilot's second gear. The trend engine (✅) waits
for the user to open the app; Morning Drafts makes the system work overnight:
every morning each opted-in artist gets a full, FREE song draft written from
the freshest trend brief — the user wakes up to ready-to-approve songs. The
approve-gate (and therefore billing) is untouched: drafts cost $0 until
approved, exactly like manual drafts.

## Flow

```
Cloud Scheduler (daily 02:00 UTC ≈ 06:00 Gulf)
  → POST /admin/run-morning-drafts   (service token)
      for each user root with artists.json:
        for each artist with morning_drafts=true:
          skip if a morning draft for this artist already exists today
          brief = per-user trend briefs (cache-fresh or generated),
                  picked round-robin by artist index, language = artist's
                  default_language
          create a draft run: same writer pass as POST /songs
            (theme=brief.theme, style=artist default or brief style,
             persona/vocal/language from the artist, artist_id stamped,
             source="morning_draft", trend_rationale=brief.rationale)
          → status awaiting_approval ($0 spent)
App (Song tab): "🌅 Morning drafts" section listing awaiting-approval
morning drafts with their "why now" line → tap → the normal approve screen.
```

## Decisions

| # | Question | Decision |
|---|---|---|
| 1 | Trigger | Cloud Scheduler → HTTP endpoint with the service bearer token (`role=service` path already exists in auth). Enable cloudscheduler API at deploy |
| 2 | Opt-in | Per-artist toggle `morning_drafts` (default OFF) beside the auto-publish toggle |
| 3 | Volume | 1 draft/artist/day, idempotent (re-runs skip artists already drafted today) — a stuck scheduler retry can't spam |
| 4 | Cost | $0 by construction — writer pass only; approval charges as always |
| 5 | Brief choice | The user's cached trend briefs (regenerate if stale), brief index = artist index mod len(briefs) so multiple artists get different ideas; brief language follows the artist |
| 6 | Style | Artist `default_style` wins when set (voice consistency); else the brief's style_hint |

## Backend

### `pipeline/api.py`

- `_create_song_draft(user_root, *, theme, style_hint, language, artist) -> str`
  — factored from `create_song`'s writer pass (run dir, state, LLM script,
  song.json, awaiting_approval) so the endpoint and `POST /songs` share one
  implementation. Extra state for drafts: `source`, `trend_rationale`.
- `POST /admin/run-morning-drafts` — **service role only** (403 otherwise).
  Iterates user dirs under the out root; per opted-in artist: idempotency
  check (`source=="morning_draft"` + same `artist_id` + `created_at` today)
  → brief → draft. Per-artist failures are collected, never abort the sweep.
  Returns `{created: N, skipped: N, failed: N, details: [...]}`.
- `SongRunSummary` gains `source: str | None` + `trend_rationale: str | None`.
- Artist model/patch gains `morning_drafts: bool = False`
  (artists.new_artist too).

### Scheduler (deployment step)

```
gcloud services enable cloudscheduler.googleapis.com
gcloud scheduler jobs create http morning-drafts \
  --schedule="0 2 * * *" --time-zone=UTC \
  --uri=https://api.faceless-lab.com/admin/run-morning-drafts \
  --http-method=POST \
  --headers="Authorization=Bearer $FACELESS_API_TOKEN" \
  --location=us-central1
```

## Flutter

- Artist edit: "Morning drafts" SwitchListTile (`morning_drafts` via patch),
  subtitle explains: a free draft each morning from the day's trends.
- Song tab: **"🌅 Morning drafts"** section (above Trending now) listing songs
  with `source=="morning_draft" && status=="awaiting_approval"` — card shows
  title/theme + the rationale line + artist name; tap → SongApproveScreen.
  Section hidden when empty.
- Bilingual `draft*` keys in BOTH ARB files.

## Error handling

- No briefs available (LLM down, no cache) → that user is skipped, counted
  in `failed`, sweep continues.
- LLM failure mid-draft → run marked failed like any writer-pass failure;
  visible in the app; next morning retries fresh (idempotency checks for a
  draft created *today*, and failed drafts don't block: only
  awaiting/complete ones count).
- Endpoint called twice (scheduler retry) → second call all-skips.

## Testing (externals mocked)

- api: 403 for user role; creates drafts only for opted-in artists (mock LLM
  + briefs); artist defaults (persona/language/style) land in song.json;
  `source`/`trend_rationale` in state + summary; idempotent same-day re-run;
  per-artist failure doesn't abort others.
- Flutter: analyzer zero errors, ARB parity.

## Non-goals (v1)

Push notifications; auto-approve (never — the approve gate is the product's
safety); more than one draft per artist per day; per-artist scheduling.
