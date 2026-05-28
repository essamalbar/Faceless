# AI Song Mode — Design Spec

**Date:** 2026-05-28
**Status:** Approved (sections 1–6 walked through with user)
**Reference artifact:** `ai song.mp4` at the repo root — a 360×360 / 4:44 Suno-style square music video with an Arabic AI song over a single static AI cover image.

## Goal

Add a second creation mode to the Faceless platform: AI-generated songs delivered as square music-video MP4s. A user types a theme (and optionally lyrics + a style hint), reviews the draft, approves the spend, and gets back a Suno-quality song with a Flux-generated cover and subtle Ken-Burns motion.

The horror pipeline stays untouched. Song mode is a sibling, not a refactor.

### Quality bar (load-bearing)

**A first-time listener must not realize the song is AI-generated.** This bar drives several non-obvious technical choices below; they aren't optional polish.

The reference artifact (`ai song.mp4`) was audited and used as a calibration target:

- Audio: AAC 130 kbps, 44.1 kHz stereo, **already mastered to -13.9 LUFS / -2.3 dBTP** (streaming standard). Our pipeline must **not** re-encode or "normalize" Suno's output — that only degrades it.
- Cover: high-detail album-art quality (consistent with Flux **dev** at high step count, not Flux schnell).
- Song length: ~4:44 — Suno's natural full-length, not truncated.

Every section of this design is consistent with that bar. Sections where someone might be tempted to "simplify and lose quality" are flagged with **Quality gate** notes.

## Non-goals

- Multi-scene music videos (cutting between AI clips synced to beats) — deferred; YAGNI until people are using static-cover mode and asking for more.
- Per-genre vocal/instrument pickers — Suno handles those via freeform style text.
- Duration targeting — Suno picks length from style + lyrics.
- Lip sync — no lip sync anywhere in this product, song mode included.
- Editing existing songs — generation-only, no DAW features.

## Architecture

Song mode reuses the existing run lifecycle (subprocess-per-run, `state.json`, `out/<run-id>/` artifacts, approve-before-spend gate) and adds four new modules.

### New modules

| Module | Responsibility |
|---|---|
| `pipeline/song.py` | Kie.ai Suno client. Submits to `/api/v1/jobs/createTask` with **`model="suno-v4-5"`** (latest at design time; bump to whatever's newest at implementation), polls `/api/v1/jobs/recordInfo`, downloads BOTH takes. Uses Suno's **custom mode** — passes lyrics + style hint explicitly rather than letting Suno pick. Mirrors `pipeline/kie.py` shape. |
| `pipeline/song_lyrics.py` | Wraps `pipeline/llm.py` to produce `{title, lyrics, style_prompt, cover_prompt}` from a theme. Honors user-supplied lyrics (passthrough). Lyrics output uses **Suno section tags** (`[Verse 1]`, `[Pre-Chorus]`, `[Chorus]`, `[Bridge]`, `[Outro]`). Style prompt is **specific by contract**: BPM, instrumentation, vocal tone, era, key, mood — not "Arabic ballad." Language-aware (default Arabic). |
| `pipeline/song_cover.py` | Wraps `pipeline/images.py` (**Flux dev at 28 steps**, 1080×1080) and burns the title text on the cover via Pillow + bundled fonts (Amiri for Arabic, Inter for Latin). |
| `pipeline/song_assemble.py` | ffmpeg recipe: cover.png + song.mp3 → MP4 with slow Ken-Burns zoom. **Audio is stream-copied (`-c:a copy`), not re-encoded** — preserves Suno's mastered output bit-for-bit. |

### Run lifecycle

```
new song run (POST /songs)
  ├─ writing-lyrics       (LLM, ~free)
  ├─ awaiting-approval    ← review screen; regen/edit allowed here only
  ├─ approved             (credits deducted in DB transaction)
  ├─ generating-song      (Suno via Kie.ai)
  ├─ generating-cover     (Flux + title overlay)
  ├─ assembling           (ffmpeg)
  └─ done | failed
```

`state.json` gains a `kind: "song"` discriminator so existing helpers (`derive_status`, `_summarize`, `_process_alive`) handle both kinds without branching.

### Artifacts per run

```
out/<run-id>/
  state.json          ← status, kind, failure_stage, pid, chosen_take, ...
  song.json           ← {title, lyrics, style_prompt, cover_prompt, language}
  lyrics.txt          ← convenience copy of lyrics for download
  cover_raw.png       ← Flux output before title overlay
  cover.png           ← final cover with title burned in (1080×1080)
  takes/
    take_1.mp3        ← Suno take 1 (Suno always returns two)
    take_2.mp3        ← Suno take 2
  song.mp3            ← symlink/copy of the chosen take (default: longer one)
  final.mp4           ← 1080×1080 MP4, ffmpeg-assembled
  run.log             ← subprocess stdout/stderr
  _debug/
    suno_response.json  ← full Kie.ai response, triage only
```

**Quality gate — both takes:** Suno's two takes are not equivalent. One is often noticeably better (less abrupt outro, less voice cracking, better mix balance). MVP behavior: auto-pick the longer take (Suno truncates one ~20% of the time) and expose a "swap take" affordance on the detail screen for the user to flip between them without re-rendering anything. Backend re-runs only ffmpeg when the user swaps — free, fast.

### Mode flag wiring

`run.py` gets a `--mode {horror,song}` flag. Default stays `horror` so existing scripts keep working. Song mode also takes `--writer-only` (lyrics pass, then exit) and `--post-approve` (song + cover + assemble), parallel to the horror `--pause-after-script` pattern.

### Lyrics-LLM contract (quality gate)

This is the **single biggest quality lever on the Suno side.** Suno's output quality is overwhelmingly determined by the lyrics + style hint it receives. The LLM in `song_lyrics.py` is constrained by contract — not just "write a song" — to emit Suno-readable structure.

**Lyrics shape (required):**

```
[Verse 1]
<4–6 lines>

[Pre-Chorus]
<2–4 lines>

[Chorus]
<4 lines, hooky, repeats later>

[Verse 2]
<4–6 lines>

[Chorus]
<same chorus repeated>

[Bridge]
<2–4 lines, contrasting>

[Chorus]
<same chorus, possibly modified>

[Outro]
<1–2 lines or empty>
```

The bracketed tags are load-bearing — Suno reads them as section markers and structures the arrangement accordingly. A song submitted as a flat block of lines comes back formless and obviously-AI. This shape is what makes the reference convincing.

**Style hint shape (required):**

Not "Arabic ballad." A real Suno-quality style hint is a structured comma-separated descriptor covering all of:

- **Genre + sub-genre:** "Arabic pop ballad," "Khaleeji nasheed," "Lebanese indie."
- **Tempo:** "slow tempo, 72 BPM" — explicit BPM matters.
- **Instrumentation:** "oud + cinematic strings + light percussion + subtle piano."
- **Vocal:** "male vocal with subtle vibrato" or "female vocal, breathy, intimate."
- **Era / production style:** "modern 2020s production, warm analog mix, light reverb."
- **Mood + key:** "melancholic, minor key" or "hopeful, major key with bittersweet undertone."

The LLM is prompted to emit this from the user's theme even when the user gave no style hint. If the user *did* provide a style hint, it's merged into the prompt rather than replaced — user intent wins on conflicts.

**`song.json` schema (final):**

```json
{
  "title": "تحت حراسة القمر",
  "lyrics": "[Verse 1]\n...\n[Chorus]\n...",
  "style_prompt": "Arabic pop ballad, slow tempo 72 BPM, oud + cinematic strings + light percussion, male vocal with subtle vibrato, modern 2020s production warm analog mix, melancholic minor key",
  "cover_prompt": "young Arab man in profile under a full moon over a calm sea, lanterns and candles, deep navy night sky, soft moonlight, romantic melancholy, fine art photography",
  "language": "ar"
}
```

The Suno API receives `lyrics` and `style_prompt` verbatim (custom mode). Suno picks the melody, mix, and arrangement from those constraints.

## HTTP API

All endpoints require `Authorization: Bearer $FACELESS_API_TOKEN` (existing single-token auth). Errors follow existing convention: 401 unauth, 402 insufficient credits, 404 not found, 409 wrong state, 422 invalid input.

| Method | Path | Purpose |
|---|---|---|
| POST | `/songs` | Start new song run. Body: `{theme, custom_lyrics?, style_hint?, language?}`. Returns `{run_id}`. Writer pass only; pauses for approval. |
| GET | `/songs` | List past song runs (mirrors `/runs`). |
| GET | `/songs/{id}` | Full status. Returns `RunSummary` shape with `kind: "song"`. |
| GET | `/songs/{id}/script` | The approve-screen payload: `{title, lyrics, style_prompt, cover_prompt, language, estimated_duration_s, cost_usd, cost_credits}`. |
| POST | `/songs/{id}/approve` | Green-light the spend. Idempotent on `status≠awaiting-approval`. Deducts credits in a DB transaction. |
| POST | `/songs/{id}/regenerate-lyrics` | Pre-approval only. Re-rolls lyrics via LLM. 409 once approved. |
| POST | `/songs/{id}/regenerate-cover-prompt` | Pre-approval only. Re-rolls cover prompt via LLM. |
| POST | `/songs/{id}/edit` | Pre-approval only. Body any of `{lyrics, style_hint, cover_prompt}`. Lyrics ≤ 4000 chars, hints ≤ 500 chars (422 otherwise). |
| POST | `/songs/{id}/resume` | Retry after a transient failure. Stage-aware: re-runs only the failed stage onward. |
| POST | `/songs/{id}/cancel` | Kill subprocess + (if pre-approval) no charge. Post-approval cancellation does not refund Suno spend (matches existing memory: "money lost = real Kie spend"). |
| GET | `/songs/{id}/audio` | Stream the chosen take's `song.mp3`. |
| GET | `/songs/{id}/audio?take=2` | Stream the *other* take's MP3 for preview without re-assembling. |
| POST | `/songs/{id}/swap-take` | Body: `{take: 1\|2}`. Re-runs ffmpeg with the other take. Free (no API spend). |
| GET | `/songs/{id}/cover` | Stream `cover.png`. |
| GET | `/songs/{id}/video` | Stream `final.mp4`. |
| GET | `/songs/{id}/log?lines=N` | Tail `run.log`. Identical to `/runs/{id}/log`. |

### Why `/songs` instead of merging into `/runs`

The horror `/runs/{id}/script` returns beats + speakers, a different shape from lyrics + style. Forcing a polymorphic response onto a shared endpoint costs the Flutter client more than the duplication costs the server. List endpoints can still merge both kinds for a unified history if desired.

### Credit estimation

`_estimate_credits_for_request` in `pipeline/api.py` gets a `song` branch.

**Cost basis** (raw API spend per song):

- Suno on Kie.ai: ~$0.05/song flat (verify at implementation against current Kie.ai pricing).
- Flux cover (1080×1080, 4 steps): ~$0.003.
- **Total raw cost ≈ $0.053 per song.**

**Credit pricing** (what the user sees) is a product decision, not a design one. Per the existing B3 ledger, `1 credit = 1 sec Veo at $0.10/s ⇒ 1 credit = $0.10`. So raw cost is ~0.5 credits per song. Final user-facing price (with margin for failed-run risk, business markup, and the fact that a song is a "thing" that feels worth more than half a credit) is set in the implementation plan.

The spec's contract is *"single flat estimate per song run, computed by the same function on backend and surfaced in the Flutter form/approve screen, validated again at `/approve` time."* Wherever this spec quotes a credit number, treat it as illustrative until the implementation plan pins it.

## Approve-gate flow

The state machine and money path are spelled out so leakage is impossible by construction.

### States and transitions

```
created → writing-lyrics → awaiting-approval ─┬─ approved → generating-song
       ↘ failed                               ├─ canceled                ↘ generating-cover
                                              └─ (edit/regen loops here)            ↘ assembling
                                                                                    ↘ done | failed
```

`awaiting-approval` is the *only* state where `/edit`, `/regenerate-lyrics`, and `/regenerate-cover-prompt` accept writes. Any other state → 409.

### POST /songs (writer pass, no spend)

1. Auth + preflight credit check (estimated total; no deduction).
2. Create `run_dir`, write `state.json` with `kind: "song"`, `status: "writing-lyrics"`.
3. Spawn `run.py --mode song --writer-only --run-id <id>` via the existing `_spawn` hook (test seam: `set_spawn_fn`).
4. Subprocess: LLM call → write `song.json` → set `status: "awaiting-approval"` → exit 0.
5. API returns `{run_id}` immediately. Flutter polls `/songs/{id}` until `awaiting-approval`, then fetches `/songs/{id}/script`.

### Review loop (no spend)

- `/songs/{id}/script` returns the current draft.
- Regen calls rewrite `song.json` atomically (temp + rename).
- `/edit` validates field lengths and patches `song.json`.
- `/cancel` sets `status: "canceled"`. No credits charged.

### POST /songs/{id}/approve (money step)

1. Verify `status == awaiting-approval` else 409.
2. Re-read `song.json` and recompute the cost estimate (defensive — lyrics edits shouldn't change cost but verify).
3. Verify balance covers estimate else 402.
4. **Inside a DB transaction:** deduct credits, write ledger row `{kind: "song-spend", run_id}`. Atomicity is the invariant — no commit, no spend.
5. Flip `status: "approved"`, spawn `run.py --mode song --post-approve --run-id <id>`.
6. Return `{run_id, balance_after}`.

Second call to `/approve` while not in `awaiting-approval` is idempotent — returns current state, no double-charge.

### Failure recovery

| Failed stage | `/resume` behavior | Re-charges? |
|---|---|---|
| `writing-lyrics` | Re-run LLM. | No (no spend yet). |
| `generating-song` | Re-submit Suno from scratch. | **Yes.** Flutter must show "Suno failed — retry will charge again. Continue?" confirmation. |
| `generating-cover` | Re-run Flux only. song.mp3 stays. | Yes (~$0.003). |
| `assembling` | Re-run ffmpeg only. | No (no API spend). |

Subprocess-died detection reuses `_process_alive` (`pipeline/api.py:49`) — non-terminal status + dead pid → `derive_status` flips to `failed` with `error: "subprocess died"`.

### Edge case: Suno's two variants

Suno often returns two takes per job. Save both as `song.mp3` (the chosen take) and `song_v2.mp3` (sits on disk). MVP returns only the first. A "pick a take" UI is a future option.

## Flutter app

Existing horror screens are unchanged. Song mode adds parallel screens with the same patterns.

### Navigation

Home tab gets a **Horror | Song** segmented selector at the top. The runs list below it filters by kind. Detail pages route on `kind`.

### Screen 1 — Create Song form

- **Theme** (required) — single-line text, Arabic placeholder ("أغنية حزينة عن القمر").
- **Custom lyrics** (optional, multi-line) — helper text: "Leave empty for AI."
- **Style hint** (optional) — example: "Arabic ballad, slow tempo, male vocal."
- **Language** — dropdown, default Arabic. Suno is multilingual; we surface a short list.
- **Cost chip** at the bottom, sourced from the same estimate function the backend uses (the exact credit number is set in the implementation plan — see Credit estimation above).
- Primary button: **Generate draft** → `POST /songs` → navigate to Screen 2.

### Screen 2 — Song approve screen

The money-saving screen.

- **Lyrics card** — full text, RTL-aware. Buttons: Re-roll (`/regenerate-lyrics`), Edit (inline → `/edit`).
- **Style prompt card** — Edit button.
- **Cover prompt card** — Re-roll + Edit.
- **Cost breakdown** — line items for "Song generation" and "Cover image" with a total. Numbers come from the same estimate function as Screen 1.
- Primary actions: **Approve & generate** (`/approve` → Screen 3) and **Discard** (`/cancel` → list).

### Screen 3 — Song detail / progress

- Header: title + cover thumbnail (gray placeholder before cover exists).
- Progress strip: "Generating song… (Suno ~30s)" → "Generating cover…" → "Assembling video…" → done. Polls `GET /songs/{id}`.
- On done: inline `<video>` player (uses `/songs/{id}/video`), download buttons for MP4 + MP3.
- **Take A / Take B toggle** at the bottom of the player — small audio-only A/B preview using `GET /songs/{id}/audio?take=1|2`, "Use this take" button calls `/swap-take`. Re-assembly takes ~5–10s with a small spinner. Default-selected take is the longer of the two; the toggle lets the user override.
- On error: red banner with last-log tail + Retry button (`/resume`). Pre-resume modal for the Suno re-charge case.

### Screen 4 — Runs list (modified)

Existing list grows a `kind` badge per row. Song rows show the square cover thumbnail + a 🎵 icon. Horror rows unchanged. Tap routes by kind.

### Explicitly cut from MVP

- Genre dropdown (freeform style hint is more flexible).
- Vocal-gender toggle (belongs in style hint).
- Duration slider (Suno picks).

## Cover art + subtle motion

### Cover generation

**Quality gate — Flux variant and steps:** The existing horror pipeline runs Flux schnell at 4 steps because cover art is *one of dozens* of frames and the per-image budget is tiny. For song mode the cover is *the only visual the viewer sees for 4+ minutes* — it has to look like a real album cover, not a placeholder. So song mode runs **Flux dev at 28 steps** (override of the existing `flux:` config block, configured per-mode in `config.yaml` under a new `song.flux:` section). Cost goes from ~$0.003 → ~$0.03 per cover, still negligible against the Suno spend, and the difference between schnell and dev at album-art quality is night-and-day.

- Resolution: 1080×1080 (square — Suno's expected cover format and 1:1-native for Instagram/Shorts).
- Prompt builder composes: `{cover_prompt}, professional album cover art, art direction by Hipgnosis, cinematic lighting, shallow depth of field, high detail, no text, no watermark, square composition, leave space at top-right for title text`. The "leave space" hint matters because the title gets burned in next. The "Hipgnosis" reference (the studio behind Pink Floyd / Led Zeppelin covers) pushes Flux toward real-album aesthetics instead of generic stock-photo.
- One Flux call per run. Re-rolling cover quality is via cover-prompt LLM regen, not via Flux retries.

### Title-text overlay (Pillow, not ffmpeg)

- `song_cover.py` opens `cover_raw.png`, paints the title (and optional subtitle) using bundled fonts:
  - **Amiri** (Google Fonts, free) for Arabic — handles RTL ligatures correctly.
  - **Inter** for Latin scripts.
- Fonts ship in `assets/fonts/` (~600 KB total). Bundling avoids runtime download flakiness.
- Layout: title in the top-right quadrant, right-aligned, ~10% canvas-width margin, auto-fit to ~64–72px. White text + soft black drop shadow (1px blur, 50% opacity) for legibility on any cover.
- Title comes from `song.json.title`, generated by the lyrics LLM during the writer pass.
- Output: `cover.png`.

### Assembly (ffmpeg)

`song_assemble.py` first probes the actual duration of `song.mp3` via `ffprobe` (authoritative — Suno's job metadata is sometimes off). It then computes the per-frame zoom step so the zoom hits exactly the target zoom level when the song ends:

```python
duration_s = ffprobe_duration("song.mp3")
fps = 25
zoom_end = 1.13                    # target final zoom
total_frames = int(duration_s * fps)
zoom_step = (zoom_end - 1.0) / total_frames   # e.g. ~0.0000217 for a 4-min song
```

Then it shells out to ffmpeg with the computed values interpolated in:

```
ffmpeg -loop 1 -i cover.png -i song.mp3 \
  -filter_complex "[0:v]scale=2160:2160,zoompan=z='1+{zoom_step}*on':d={total_frames}:s=1080x1080:fps={fps}[v]" \
  -map "[v]" -map 1:a \
  -c:v libx264 -preset slow -crf 18 \
  -c:a copy \
  -pix_fmt yuv420p -shortest \
  -movflags +faststart \
  final.mp4
```

- **Quality gate — audio is stream-copied, not re-encoded.** Suno's output is already AAC at 130 kbps mastered to ~-14 LUFS / -2 dBTP (streaming standard, verified against the reference). Re-encoding to "higher" AAC would be a *quality loss*, not a gain — there's no PCM master to encode from, and AAC-to-AAC transcoding adds artifacts. `-c:a copy` preserves Suno's mastering bit-for-bit.
- **Quality gate — no `loudnorm` or `dynaudnorm` filter.** Tempting because they sound like "make it louder/cleaner," but they re-encode the audio and Suno's loudness is already correct. Skip.
- Upscale-then-zoompan avoids the famous zoompan blur (zoompan resamples; pre-upscaling buys headroom).
- Zoom: 1.0× → ~1.13× over the song's full duration. Per-frame rate computed at assemble time so songs of any length zoom at the same overall arc.
- 25fps, 1080×1080 (3× the reference's 360×360).
- `-movflags +faststart` so the MP4 streams immediately in the Flutter `<video>` player (moov atom at the front).
- `-shortest` so video ends with audio.

### Take-swap re-assemble

When the user taps "swap take" in the detail screen, `song_assemble.py` is re-run with the other take pointed at as `song.mp3`. Cover and ffmpeg-zoompan are deterministic so the new `final.mp4` is identical except for the audio track. Operation is free (no API spend), takes ~5–10s on the existing CRF 18 preset.

### YAGNI cuts on visuals

- No particle overlay (snow/embers/dust) — adds visual noise that fights the cover. Revisit after 5+ shipped songs.
- No vinyl-record or waveform overlay — same reason. The slow zoom is enough.

## Errors, resume, and logging

### Failure taxonomy

| Stage | Common failures | Resume |
|---|---|---|
| `writing-lyrics` | LLM timeout, policy refusal, empty response | Re-run; no spend yet. |
| `generating-song` | Suno >5min timeout, Kie error, MP3 404 (the existing `KIE_DOWNLOAD_PROXY` case) | Re-submit Suno; **re-charges**. |
| `generating-cover` | Flux timeout, NSFW filter, image download fail | Re-run Flux only. |
| `assembling` | ffmpeg disk/font failure | Re-run ffmpeg only. |

Subprocess crashes (non-terminal status + dead pid) reuse `_process_alive` → `derive_status` flip to `failed`.

### Logging hygiene

- `run.log` gets short status lines: `{taskId, status, mp3_url}`.
- Full Suno response → `out/<id>/_debug/suno_response.json`. Triage only; never streamed to the API client.
- Mirrors the existing pattern in `pipeline/kie.py` for Veo.

### Concurrency

`_process_alive` already prevents double-spawning the same run. Multiple parallel song runs by the same user are fine and intended.

## Testing

Three new test files. All hew to the invariant *external services are mocked; never hit real APIs.*

### `tests/test_song.py` — `pipeline/song.py` units

- Submit returns task id (mocked `POST` → `{taskId: "fake-123"}`).
- Poll returns `{mp3_url, duration_s}` on success (mocked `GET` → `{successFlag: 1, mp3Url: "...", durationSec: 180}`).
- Timeout: poll loop respects `max_attempts`, raises `SongGenerationTimeout`.
- Cost mapping helper returns expected credit count for the active Suno model.

### `tests/test_song_pipeline.py` — full song path

- Monkeypatch `pipeline.llm.generate` → canned `{title, lyrics, style_prompt, cover_prompt}`.
- Monkeypatch `pipeline.song.submit_song_job` + `poll_song_job` → returns path to `tests/fixtures/short_song.mp3` (3-second silent MP3 committed to the repo, a few KB).
- Monkeypatch `pipeline.images.generate` → writes a fixture PNG into the run dir.
- Run `run.py --mode song --writer-only`, then `--post-approve`, against a tempdir.
- Assert `final.mp4` exists; assert it has both video + audio streams via `ffprobe`.
- Assert `state.json` transitions through every status in order.

### `tests/test_song_api.py` — FastAPI

- `POST /songs` returns 200 + run_id, spawn intercepted by `set_spawn_fn`.
- `GET /songs/{id}/script` returns 404 before lyrics written, 200 after.
- `POST /songs/{id}/regenerate-lyrics` returns 409 once status has moved past `awaiting-approval`.
- `POST /songs/{id}/approve` deducts credits exactly once even when called twice (idempotency).
- `POST /songs/{id}/approve` returns 402 if balance insufficient.
- `POST /songs/{id}/edit` returns 422 for lyrics > 4000 chars.
- `POST /songs/{id}/cancel` post-approval does NOT refund (asserts ledger unchanged).

No new mocking infrastructure — existing `monkeypatch` + `set_spawn_fn` patterns cover everything.

## Out of scope (future work)

- Multi-scene music videos with Kling/Veo clips synced to beats.
- "Pick a take" UI exposing Suno's second variant (`song_v2.mp3`).
- Genre dropdown / vocal-gender toggle / duration slider.
- Editing existing songs (DAW-style trimming, re-mastering, voice swap).
- Cover-art motion beyond Ken Burns (particles, vinyl, waveform).
- Multi-provider music routing (Suno + Mureka + Udio fallback). Adopt only if Suno disappoints.

## Open implementation-time questions

These don't change the design but need confirming in the plan:

1. **Exact Kie.ai model id for Suno V4.5** — verify against current Kie.ai docs at implementation; the design pins V4.5 or newer (V4 is acceptable fallback; V3.5 is **not** — it's the bad-old-AI sound and would miss the quality bar).
2. **Exact Suno-on-Kie cost per song** — adjust the `_estimate_credits_for_request` value once confirmed.
3. **Whether Kie.ai exposes Suno's custom-mode parameters** (lyrics, style hint, title separately) on `/api/v1/jobs/createTask`. The design assumes yes — that's how Suno's own API works. If Kie wrappers it into one prompt field, the quality bar can still be hit by formatting the combined prompt carefully, but the wrapper shape needs verifying first.
4. Whether Kie.ai's Suno endpoint accepts the `make_instrumental` flag (defer instrumental-only mode unless trivially exposed).
5. Flux dev configuration confirmation — the existing `pipeline/images.py` uses Kie.ai's Flux Kontext endpoint; verify it accepts step count overrides (`steps: 28`) on a per-call basis without breaking the horror pipeline's `steps: 4` default. Likely yes; this is a single-field override.