# YouTube Song Import — Design Spec

**Date:** 2026-06-19
**Status:** Approved (walked through with user)
**Builds on:** `docs/superpowers/specs/2026-05-28-ai-song-mode-design.md` (song mode)
and the existing approve → Suno → cover → assemble pipeline.

## Goal

Add a new front door to song creation: paste a **YouTube link**, the system
listens to the reference and writes an **original, improved** song *inspired by*
its theme, mood, genre and structure — which the user reviews/edits and then
generates through the normal song pipeline.

The reference is used for inspiration only; the output is **100% original
lyrics**. Everything after `awaiting_approval` reuses the existing pipeline
unchanged.

## Decisions (resolved during brainstorming)

| # | Question | Decision |
|---|---|---|
| 1 | What is taken from the song? | **Theme + structure as inspiration → original words.** Never reproduce/paraphrase the source lyrics. |
| 2 | How is the reference analyzed? | **Download audio + analyze** (yt-dlp → librosa tempo → Whisper transcript, transcript internal-only). User accepts the YouTube-ToS operator risk. |
| 3 | How is "your touch" applied? | **Both** — an optional instruction box at import AND the existing review/edit gate. |
| — | Where does the slow analysis run? | **Approach A:** reuse the Cloud Run Job worker as an `analyzing` pre-stage (the inline API writer pass would time out). |

## Non-goals / guardrails

- **Not** a cover/remix that reproduces or rewrites copyrighted lyrics. The
  generator writes original lyrics; the verbatim transcript is transient and
  never stored, displayed, or fed wholesale into generation.
- **Not** a melody/vocal clone of the reference — Suno generates a fresh song
  from the original lyrics + a style descriptor.
- No new billing model — import produces the same `song.json` the manual flow
  produces, then the normal credit cost applies at approve (1 static / 3
  cinematic, per [[project_b3_billing_live]]).

## Legal posture

The user operates the platform and accepts that downloading from YouTube
violates YouTube's ToS (an operator risk). The product mitigates **derivative-
work** risk by generating original lyrics only (decision 1) and enforcing the
originality guardrail below. This spec does not make the feature "legal"; it
minimizes the most acute infringement vector (reproducing lyrics/melody).

## Architecture

A new entry point; the post-approval pipeline is untouched.

### New module — `pipeline/song_import.py`

| Function | Responsibility |
|---|---|
| `download_audio(url, out_dir) -> Path` | yt-dlp pulls best audio to `reference.m4a` (uses the ffmpeg already in the image). Raises `ImportFetchError` with a clear message on failure. |
| `analyze_reference(audio, *, llm, language) -> dict` | librosa → tempo/key; Whisper → transcript (**transient, internal**); LLM distills to derived descriptors `{bpm, genre, mood, instrumentation, language, one_line_theme, section_structure}`. The verbatim transcript is **never** returned or persisted — only descriptors. |
| `build_inspired_script(*, llm, analysis, instruction, language) -> SongScript` | Produces an **original** `{title, lyrics, style_prompt, cover_prompt, art_direction, scene_prompts}` from the descriptors + user instruction. Reuses `SongScript` + `validate_section_tags`. Originality guardrail below. |

Reuses `pipeline/song_lyrics.py` (`SongScript`, `validate_section_tags`),
`pipeline/song_beats.py` (`_librosa_beat_track` / tempo), and `pipeline/align.py`
(Whisper) — no duplication.

**New dependency:** `yt-dlp` (pip). Requires ffmpeg (already present).

### New API — `POST /songs/import`

Request `CreateSongImportRequest`:
```
youtube_url:  str            # validated: must be a YouTube watch/share URL
instruction:  str | None     # optional "your touch" direction
language:     str = "ar"
video_mode:   "static" | "cinematic" = "static"
vocal_gender: str | None = "m"
suno_model:   str | None
```
Behavior: validate the URL (422 on malformed/non-YouTube), run the up-front
credit check (same amount as `create_song` for the chosen `video_mode`; **no
spend**), create the run dir, write state `kind="song", status="analyzing"` with
`youtube_url` + `instruction` + the options, then **spawn the worker** for the
analyze step. Returns `{run_id, status: "analyzing"}`.

### Worker — `run.py` song mode, new pre-stage

At the top of the song worker, before any generation: if the run is in import
mode (`status == "analyzing"` / has `youtube_url` and no `song.json` yet):

```
download_audio → analyze_reference → build_inspired_script
  → write song.json  → write_state(status="awaiting_approval")  → exit 0
```

The existing post-approve branch (Suno → cover → assemble) is unchanged and runs
on the *second* worker invocation (from `approve_song`), exactly as today.

### Run lifecycle

```
POST /songs/import → analyzing        (worker: yt-dlp → librosa → Whisper → LLM)
                   → awaiting_approval (review/edit = "your touch", $0)
                   → approve           (deduct 1 or 3 credits)
                   → generating_song → generating_cover → assembling → complete
```

### Artifacts per run

```
reference.m4a    ← downloaded audio (input to analysis)
analysis.json    ← derived descriptors only (bpm, genre, mood, theme, structure)
song.json        ← generated ORIGINAL script (normal shape)
... then the usual takes/, cover.png, lyrics.json, final.mp4
```

### Flutter

The new-song screen gains an **"Import from YouTube"** mode: a URL field + the
optional "your touch" instruction box + the existing static/cinematic toggle +
language. Submits to `/songs/import`, then opens the run — which shows
"Analyzing…" until `awaiting_approval`, then the existing review screen.

## Originality guardrail

The legal-safety core, enforced in code (not just prompt wording):

1. **Prompt contract.** `build_inspired_script` instructs the LLM to write
   **new, original** lyrics driven only by the derived descriptors + the user
   instruction, and to **not copy, translate, or closely paraphrase** the
   reference's words or distinctive lines.
2. **Transient transcript.** The verbatim Whisper transcript is distilled to a
   one-line theme + section outline, then discarded. Only those short
   descriptors reach the generation prompt — the raw lyrics never do.
   `analysis.json` stores descriptors only. (Matches the existing
   "never display Whisper transcription" rule, see [[feedback_cost_disclosure]].)
3. **Overlap check.** After generation, compute the fraction of the new
   lyrics' 4-grams that also appear in the transcript; if it exceeds **0.15**
   (default, configurable), regenerate once with a stronger "make it more
   original" instruction. If the regeneration still exceeds the threshold,
   ship it but log a warning (don't hard-fail the run). A misbehaving model
   still cannot silently ship a near-copy.

## Error handling

Analysis runs **before approval**, so every failure here costs nothing.

- **Malformed / non-YouTube URL** → 422 at the API, before any work.
- **Download failure** (private, region-locked, age-restricted, network, or
  **Cloud Run datacenter-IP block** — see Risks) → run `failed`, `failure_stage
  = "analyzing"`, with an actionable vendor-neutral hint via the existing
  error-hint map: *"Couldn't fetch that link — it may be private, region-locked,
  or blocked. Try another link or create the song manually."*
- **Audio downloaded but transcription fails** → **degrade, don't die**:
  proceed style-only (librosa tempo + LLM genre/mood) and lean on the user
  instruction + a generic theme. Still produces a draft to review.
- **librosa tempo failure** → fixed-BPM fallback (same pattern as `song_beats`).

## Risks

- **yt-dlp from Cloud Run is likely blocked/throttled** — YouTube aggressively
  blocks datacenter IPs. The feature may fail in production even when it works
  locally. Mitigation: graceful failure message (above) + a later option to
  route downloads through a residential proxy (reuse the `KIE_DOWNLOAD_PROXY`
  pattern). **Not a launch blocker, but expect day-one failures from prod.**
- **YouTube ToS** — downloading violates it; accepted as operator risk.

## Testing

External services mocked (repo invariant: never hit real APIs/yt-dlp/Whisper in
tests).

- **`song_import` units:**
  - `build_inspired_script` (mock LLM) → valid `SongScript` with section tags;
    assert the originality instruction is present in the prompt.
  - **Overlap guard:** mock LLM returns near-copy lyrics (high overlap with a
    fake transcript) → guard triggers a regeneration; a distinct output passes
    unchanged.
  - `download_audio` failure (mock yt-dlp raising) → raises `ImportFetchError`
    with the clear message.
  - `analyze_reference` with transcription failure (mock Whisper raising) →
    returns style-only analysis (no verbatim lyrics, `one_line_theme` may be
    None), does not raise.
- **API (`tests/test_api.py`):** `POST /songs/import` → 201 `analyzing`;
  malformed/non-YouTube URL → 422; insufficient credits → 402; persists
  `youtube_url` + `instruction` to state.
- **Worker (`tests/test_run_song_mode.py`):** import-mode run (mock
  download/transcribe/LLM) → analyze branch writes `song.json` + sets
  `awaiting_approval` and exits 0; the existing approve→generate path still
  passes.
- **`pyproject.toml`:** add `yt-dlp`; confirm it installs in the slim Linux
  image.
