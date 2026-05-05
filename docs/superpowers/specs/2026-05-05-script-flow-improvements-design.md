# Script-Flow Improvements — Design

**Date:** 2026-05-05
**Status:** approved (brainstorming)
**Author:** brainstorming session w/ Claude

## Problem

Four user-reported pain points with the current script-to-video pipeline:

1. **AI mode produces "static" stories** — the existing AI Write tab is hard-locked
   to the Sunstoriz fruit-melodrama style (anthropomorphic fruit cast, Syrian dialect,
   tragic ending) regardless of the user's premise. See
   `pipeline/script.py:260` (`SHORTS_WRITER_SYSTEM`) and `:275`
   (`SHORTS_WRITER_PROMPT_TEMPLATE`).
2. **Pasted prose collapses to one beat** — `pipeline/script_parser.py` is regex-only.
   Without `**Scene N – ...**` headings and `**SPEAKER:**\n"dialogue"` blocks,
   `_extract_scenes` returns a single synthetic scene and `_RE_DIALOGUE` finds
   nothing → the run gets one silent beat for the entire story.
3. **No edit gate after Flux** — once the user approves the script, `run.py` runs
   character_sheet (Flux) → Veo clips → captions → assemble in one continuous
   subprocess. There is no checkpoint after the character sheet that lets the user
   preview it and revise beats before paying for Veo.
4. **Per-clip playback missing** — the API exposes `/runs/{id}/clips/{i}/thumbnail`
   (still JPG) but no per-clip mp4 endpoint, and the Flutter beat tile shows only a
   thumbnail with no tap-to-play. Single-clip reroll exists in `/runs/{id}/reroll`
   but is not surfaced per-beat in the UI.

## Goals

- AI generation honours the user's premise + style controls instead of forcing a
  fixed template.
- Pasted prose, even with no markdown structure, splits into multiple beats.
- The user gets a second approval gate after the Flux character sheet renders, with
  full beat-edit access before Veo spend begins.
- The user can play any individual generated Veo clip in the app, and reroll a
  single clip with one tap.
- All existing behaviour (AI Write tab, Paste Script regex parser, the current
  approve flow, bulk reroll) keeps working unchanged.

## Non-goals

- Replacing or removing the existing AI Write Sunstoriz preset — it remains as a
  one-tap option.
- Adding new external services or providers (still Anthropic + Groq for LLM, Kie
  Flux + Veo for visuals).
- Inline mini-players in each beat row (rejected during brainstorming due to
  multi-controller memory / codec contention).
- Changing the LLM router precedence (`pipeline/llm_anthropic.py` /
  `pipeline/llm_groq.py`) — Anthropic-first stays.
- Refactoring the long-form (non-shorts) script path. All work below targets
  `--shorts` / freeform.

---

## Section 1 — Freeform AI script mode

### UX

`NewRunScreen` (`lib/screens/new_run_screen.dart`) gains a third tab next to AI
Write and Paste Script:

- **Tab 1:** "AI Write" — unchanged, still calls `POST /runs` with the existing
  Sunstoriz prompt.
- **Tab 2:** "Paste Script" — unchanged behaviour, plus the new hybrid parser
  (Section 2).
- **Tab 3:** "AI Freeform" — new. The user fills in a premise plus style controls.

Controls on the AI Freeform tab:

| Field | Control | Default (display / wire) |
|---|---|---|
| Premise (Arabic) | multiline TextField | empty (required, ≥4 chars), RTL |
| Theme | dropdown | folkloric (reuses existing `_themes`) |
| Dialect | dropdown | MSA / `msa` |
| Art style | dropdown | cinematic photo-real / `cinematic_photo_real` |
| Character template | dropdown | let the AI choose / `ai_choose` |
| Ending type | dropdown | let the AI choose / `ai_choose` |
| Number of beats | slider 4–15 | 8 |
| Per-beat seconds | slider 4–10 | 8 (becomes default `clip_duration_s`) |

Allowed wire values per dropdown:

- `dialect`: `msa`, `syrian`, `egyptian`, `khaliji`, `maghrebi`, `iraqi`.
- `art_style`: `pixar_3d`, `anime_2d`, `cinematic_photo_real`, `claymation`,
  `hand_drawn`, `ghibli`.
- `character_template`: `human`, `fruit_sunstoriz`, `animal`, `surreal`,
  `ai_choose`.
- `ending_type`: `open`, `closed_tragic`, `closed_happy`, `twist`, `ai_choose`.

### Backend

New module: `pipeline/script_freeform.py`

- Public function:
  ```
  generate_freeform_script(
      llm,
      seed: ThemeSeed,
      controls: FreeformControls,
  ) -> Script
  ```
- `FreeformControls` is a frozen dataclass with `dialect`, `art_style`,
  `character_template`, `ending_type`, `num_beats`, `per_beat_seconds`.
- Uses a new system prompt + template that interpolate the controls. **Critically
  there are NO hard-coded fruit characters, no hard-coded Syrian dialect, no
  hard-coded tragic ending.** The system prompt is a generic "Arabic-language
  short-form video writer" instruction; the template fills in the user's selected
  values.
- Returns the same `Script` shape as `generate_shorts_script` so all downstream
  Flux/Veo/assemble code is unchanged.
- Reuses `pipeline.llm.get_llm_client` (Anthropic-first, Groq fallback) — no
  router changes.

`run.py` gains `--freeform` (mutually exclusive with `--shorts` for
template-selection purposes; both produce the same `script.json` shape on disk).

### API

New endpoint: `POST /runs/freeform`

Request body:
```
{
  "theme": "folkloric",
  "premise": "...",
  "dialect": "msa",
  "art_style": "cinematic_photo_real",
  "character_template": "ai_choose",
  "ending_type": "ai_choose",
  "num_beats": 8,
  "per_beat_seconds": 8
}
```

Response: `RunSummary` (same as `POST /runs`).

Behaviour: spawns `run.py --freeform --pause-after-script --theme ... --seed ...
--run-dir ...` plus the freeform controls passed through as flags. Lands in
`awaiting_approval` exactly like `POST /runs`.

The existing `POST /runs` endpoint is untouched — Sunstoriz-style requests still
go through it.

### Why a new endpoint instead of a `mode` field on `POST /runs`

The freeform request shape adds 6 fields that only apply in freeform mode. A
union schema (each field optional, only required in one branch) is harder to read
and harder to validate. Two endpoints stay self-documenting and let
`CreateRunRequest` keep its current minimal Pydantic model.

### Test coverage

- `tests/test_script_freeform.py` — prompt-build determinism, control-value
  interpolation, JSON parse path mirroring `tests/test_script.py`.
- `tests/test_api.py` — `/runs/freeform` happy path + invalid-control rejection.
  Existing `_SPAWN_FN` stub used to avoid actually running the pipeline.

---

## Section 2 — Hybrid script parser

### Behaviour

`POST /runs/parse-script` (defined at `pipeline/api.py:628`) gains a hybrid path:

1. Run the existing `parse_episode_markdown` (regex). If it produces ≥2 dialogue
   beats, return that result and tag the response `parse_method: "regex"`.
2. Otherwise, fall through to a new LLM-based splitter. Tag the response
   `parse_method: "llm_split"`.

Silent-only beats from regex (zero dialogue blocks but a long synthetic-scene
trail) count as a regex *miss*, not a hit, so freeform prose triggers the LLM
splitter.

### LLM splitter

New module: `pipeline/script_splitter.py`

- Public function:
  ```
  split_prose_into_beats(
      llm,
      raw_text: str,
      target_beats: int = 8,
      per_beat_seconds: int = 8,
  ) -> list[ParsedBeat]
  ```
- Prompt instructs the LLM to:
  - Segment the prose into `target_beats` beats (±1 acceptable).
  - For each beat: produce `arabic` (verbatim from input — only segment, never
    rewrite), `english_motion` (a short visual prompt for Veo), `speaker` (one
    of the existing valid-speaker enum), `clip_duration_s` (between
    `per_beat_seconds * 0.6` and `per_beat_seconds * 1.4`).
- **Verbatim guard (server-side):** after the LLM responds, normalize input and
  output by stripping whitespace and concatenating every `arabic` field. If the
  joined output diverges from the joined input by more than a small whitespace-
  only / punctuation-only tolerance, retry once. If the retry also fails, fall
  back to a naive sentence-split: split on `.` `!` `?` `…` and `\n\n`, then
  pad/clip to `target_beats` segments. The naive fallback is dumb but it ALWAYS
  produces multiple beats — paste-script will never silently return one beat
  again.

### API

`POST /runs/parse-script` request body extended:
```
{
  "raw_text": "...",
  "target_beats": 8        // optional, default 8, server-clamped to 4..15
}
```

Response shape extended:
```
{
  "title": "...",
  "beats": [...],
  "parse_method": "regex" | "llm_split" | "naive_fallback"
}
```

`PasteScriptBeat` schema unchanged.

### Frontend

`new_run_screen.dart` — Paste Script tab:

- Add a slider above "Parse to Beats": "Target beats: 8" (range 4–15).
- After parsing, surface `parse_method` as a small badge below the title:
  - `regex` — green, "8 beats parsed from your markdown"
  - `llm_split` — orange, "8 beats split by AI — review before saving"
  - `naive_fallback` — yellow, "Couldn't split with AI — review carefully"
- Existing per-beat editor handles tweaks; no new screen.

### Test coverage

- `tests/test_script_splitter.py` — verbatim-guard pass / fail / retry /
  naive-fallback paths.
- `tests/test_api.py` — `/runs/parse-script` regex hit, LLM fallback (with stub
  LLM), naive fallback (with broken stub).

---

## Section 3 — Post-Flux pause + edit gate

### State machine

New `RunStatus`: `awaiting_veo_approval`.

```
creating
   ↓
awaiting_approval         (script.json present; user clicks Approve #1)
   ↓
running_paid              (Flux character sheet rendering, ~30s, $0.05)
   ↓
awaiting_veo_approval     ← NEW: character_sheet.png present, no clips,
   ↓                              subprocess EXITED. User clicks Approve #2.
running_paid              (Veo clips rendering)
   ↓
complete
```

### Backend

- `run.py` gains `--pause-after-character-sheet`. Same exit-after-stage machinery
  as `--pause-after-script`, but the exit point is right after
  `character_sheet.png` is written.
- `pipeline/api.py` `approve_run` (line 809) updated: spawn args become
  `--shorts --resume <dir> --pause-after-character-sheet [--max-spend ...]`. So
  the Approve #1 click no longer runs Veo.
- New endpoint: `POST /runs/{id}/approve-veo`
  - Allowed only when current status is `awaiting_veo_approval`.
  - Spawns `run.py --shorts --resume <dir> [--max-spend ...]` with NO pause
    flags → Veo + captions + assemble run end-to-end.
  - Returns `ApprovalAck`.
- `derive_status` (line 306) gets a new branch ordered above the existing
  `not sheet_exists and not has_clips` check:
  - If `script.json` exists AND `character_sheet.png` exists AND no clips AND
    process is not alive → `awaiting_veo_approval`.
- `PUT /runs/{id}/script` (edit-script, line 879) — currently restricted to
  `awaiting_approval`. Loosened: allowed when status is `awaiting_approval` OR
  `awaiting_veo_approval`. The dialogue is still locked once any clip exists.
- `PUT /runs/{id}/character-sheet/reroll` — new endpoint; deletes
  `character_sheet.png` and respawns `run.py --shorts --resume <dir>
  --pause-after-character-sheet`. Costs another $0.05 of Flux. Allowed only when
  status is `awaiting_veo_approval` (you only reroll when you can see the
  current sheet is wrong).

### Frontend

`lib/api/models.dart`:
- New `RunStatus.awaitingVeoApproval` enum value with JSON key
  `awaiting_veo_approval`.
- `isAwaitingVeoApproval` getter mirroring the existing `isAwaitingApproval`.

`lib/screens/run_detail_screen.dart`:
- `_StatusBanner` gains a case for `awaitingVeoApproval`: "Character sheet ready
  — review before Veo spend (\$X.XX)".
- New panel above `_ScriptPanel` when status is `awaitingVeoApproval`:
  - Shows the character-sheet image (already served by `/runs/{id}/thumbnail`,
    which falls back to `character_sheet.png` per `pipeline/api.py:1208`).
  - "Reroll character sheet (\$0.05)" outlined button → calls the new
    character-sheet reroll endpoint.
- `_ApprovalBar` reused; tapping Approve calls `/approve-veo` instead of
  `/approve` when status is `awaitingVeoApproval`. Edit + Discard buttons keep
  working — Edit opens `EditScriptScreen` exactly as today (server now allows
  edits in this state too).

`lib/api/client.dart`:
- New methods: `approveVeoRun(runId)`, `rerollCharacterSheet(runId)`.

### Why subprocess exit + respawn instead of an in-process pause

Pipeline state today is filesystem-driven: `script.json` exists, `character_sheet.png`
exists, `clips/NN.mp4` exists. A long-lived paused subprocess would be the only
piece of in-memory state in the system, and it would have to survive the API
server restarting (`./scripts/run-app.sh` restarts the server on `.env` changes).
Exit + respawn keeps every checkpoint resumable from a cold start, which is how
`--pause-after-script` already works.

### Test coverage

- `tests/test_api.py`:
  - `derive_status` returns `awaiting_veo_approval` when the right artifacts
    exist.
  - `/runs/{id}/approve-veo` rejects from any other status.
  - `/runs/{id}/character-sheet/reroll` deletes the sheet and spawns the
    correct args (verified via `_SPAWN_FN` stub).
  - `PUT /runs/{id}/script` accepts edits in both pause states.
- `tests/test_run_shorts_smoke.py` — extend the existing smoke test to verify
  both pause flags produce the expected exit points.

---

## Section 4 — Per-clip playback + reroll

### Backend

New endpoint: `GET /runs/{run_id}/clips/{clip_index}/video`
- Mirrors `/clips/{i}/thumbnail` at `pipeline/api.py:1229`.
- Streams `clips/NN.mp4` via `FileResponse(media_type="video/mp4")`.
- Uses `require_token_header_or_query` so the Flutter `video_player` plugin
  works on web (query-string token, same as `/runs/{id}/video`).
- Validates `clip_index` is 1..99; returns 404 if the clip mp4 doesn't exist.

No other backend changes — single-clip reroll already works via
`POST /runs/{id}/reroll` with `{"clips": [N]}`.

### Frontend

`lib/screens/video_player_screen.dart`:
- Add optional `clipIndex: int?` constructor param.
- When non-null, the screen loads `/runs/{id}/clips/{i}/video` instead of
  `/runs/{id}/video`, and the title becomes `"Clip NN — <speaker>"`.
- When null, current behaviour (final video) is preserved.

`lib/screens/run_detail_screen.dart` `_BeatTile`:
- Wrap `_ClipThumbBox` in `InkWell` so tapping pushes `VideoPlayerScreen` with
  the clip index. Disabled when `hasClip == false`.
- Add a "Reroll" `IconButton` to the right of the beat row, visible when
  `hasClip == true`. Tapping shows a confirmation dialog
  ("Regenerate clip NN — \$0.85") and on confirm calls
  `widget.client.rerollClips(runId, [index])`.

### Test coverage

- `tests/test_api.py` — new `/clips/{i}/video` route serves the file with the
  right MIME type, 404s for missing clips, accepts both header and query-string
  auth.
- Flutter widget test — `widget_test.dart` extension verifying that tapping a
  beat tile with `hasClip=true` pushes a `VideoPlayerScreen` with `clipIndex` set.

### Why fullscreen tap-to-play instead of inline mini-players

8–15 simultaneous `VideoPlayerController` instances on one screen burn memory
and battery, and on mobile the platform decoder serializes anyway so they fight
for the codec. Fullscreen on tap uses one controller at a time and matches
standard Flutter / mobile UX patterns.

---

## Cross-cutting concerns

### Cost transparency

- `awaiting_veo_approval` shows the *Veo* dollar figure, NOT including the
  already-spent Flux \$0.05. Use the existing `_cost_estimate_usd` minus
  `FLUX_COST_PER_RUN_USD`.
- Single-clip reroll dialog displays \$0.85 (≈ 8s × \$0.10/s plus ~5% buffer).
- Character-sheet reroll dialog displays \$0.05.
- Per the user's standing preference (memory:
  `feedback_cost_disclosure.md`), every paid action restates the dollar figure
  immediately before the user commits.

### Resumability

All four sections preserve the project invariant: artifacts on disk are the
single source of truth. No new in-memory state. A power loss anywhere in the
flow leaves the run in a derivable status, and the existing Resume button still
works.

### Backwards compatibility

- Existing AI Write tab: unchanged.
- Existing Paste Script regex parser: unchanged for runs whose markdown matches
  the current grammar.
- Existing `/approve` endpoint: still works, but now produces an
  `awaiting_veo_approval` state after Flux instead of going straight to clips.
  The Flutter app handles both — old run dirs created before this change will
  go through the new gate naturally because `derive_status` is filesystem-based.
- Existing `/reroll` endpoint: unchanged.
- Existing `/clips/{i}/thumbnail` endpoint: unchanged.

### Security / auth

All new endpoints require the existing `require_token` (or
`require_token_header_or_query` for media). No changes to the auth model.

---

## Open questions

None at design time — all four flows have explicit user decisions:
- **Q1 → B:** separate freeform mode, keep Sunstoriz preset as a tab.
- **Q2 → C:** hybrid parser, regex first, LLM fallback.
- **Q3 → A:** auto-pause after Flux every time, full edit gate.
- **Q4 → C:** tap-to-fullscreen + per-clip reroll button.

## Out-of-scope follow-ups (not in this plan)

- Streaming Veo clip generation status to the UI in real time (today the UI
  polls `/runs/{id}` every 5s; that stays).
- A "save freeform settings as preset" feature for the Freeform tab.
- Internationalising the new dropdown labels (today's UI is English-with-Arabic-
  content; same here).
