# Song Upload-&-Cover — Design Spec

**Date:** 2026-06-24
**Status:** Approved (walked through with user)
**Builds on:** `2026-06-19-youtube-song-import-design.md` (import pre-stage, analyze
functions) and the existing approve → Suno → cover → assemble pipeline.

## Goal

Add a creation mode where the user **uploads an audio file** and the system
produces a **faithful cover** — the original song's **melody, words, and feel**,
freshly performed by an AI voice. This is the path that actually sounds like the
source, unlike the YouTube metadata fallback (which only reads title/description
because YouTube blocks our server's downloads).

## Why this works where YouTube import doesn't

- **Audio comes from the user, not a download** → sidesteps the Cloud Run
  datacenter-IP block entirely (the block that forces the import path into
  title-only metadata).
- **Kie.ai exposes `POST /api/v1/generate/upload-cover`** — *"creates a cover
  version while retaining its core melody."* Our existing `submit_song_job`
  (text→song) cannot keep a melody; the cover endpoint can. This is the
  load-bearing discovery.

## Honest capability matrix (disclosed to user, per [[feedback_cost_disclosure]])

| Want | Delivered? | Mechanism |
|---|---|---|
| Same beat / melody | ✅ | Suno cover engine retains the uploaded file's core melody |
| Same words | ✅ | Whisper transcribes → user edits at the $0 review gate → passed as cover lyrics |
| Same genre / tempo / mood | ✅ | librosa tempo + LLM style descriptor → `style` |
| Same exact voice | ⚠️ No | Suno sings in its own voice (same gender via `vocalGender`); no engine clones the original singer |

**Legal posture:** a cover retaining melody **and** words is a derivative work —
the most copyright-exposed mode, and the deliberate reverse of the import
feature's original-only stance. Accepted as **operator risk** (same posture as
the import spec). The product does not claim this is licensed.

**Cost:** unchanged — 1 credit static / 3 cinematic per generation
([[project_b3_billing_live]]); the cover endpoint bills like a normal Suno job.

## Architecture

The post-approval pipeline (takes → cover image → assemble, static or cinematic)
is **untouched**. Only the *song submit* call and a new *analyze* branch change.

### `pipeline/song.py` — new `submit_cover_job`

```
submit_cover_job(client, *, upload_url, lyrics, style_prompt, title,
                 model, callback_url, vocal_gender, negative_tags) -> task_id
```
POSTs to `SUNO_COVER_PATH` (`/api/v1/generate/upload-cover`, env-overridable) with:
`{uploadUrl, prompt: lyrics, customMode: True, instrumental: False, model,
callBackUrl, style, title, vocalGender?}`. Returns `taskId`. Polling
(`wait_for_song`) and `download_take` are reused unchanged — cover jobs use the
same task/record-info system.

### `pipeline/song_import.py` — cover-prep helpers (reuse, don't duplicate)

- `_detect_bpm`, `_transcribe`, `_llm_descriptors` already exist — reused.
- New `section_transcript(llm, transcript, language) -> str`: one LLM call that
  inserts Suno section tags (`[Verse 1]`, `[Chorus]`, …) into the transcript
  **without changing the words**, so `validate_section_tags` passes. Returns
  tagged lyrics.
- New `build_cover_script(*, llm, analysis, transcript, instruction, language)
  -> SongScript`: sections the transcript → calls `generate_song_script(
  custom_lyrics=tagged_lyrics, style_hint=<genre,bpm,instr,mood>, theme=...)`
  so the LLM produces title/style/cover/scene prompts while the **words pass
  through verbatim** (`generate_song_script` already honors `custom_lyrics`).
  If transcription was empty, fall back to `build_inspired_script` (no words to
  keep) and log it.

### `pipeline/video.py` — generalize the uploader

Add `_upload_file_get_url(local_path, *, content_type) -> str` (refactor the
uguu.se body out of `_upload_image_get_url`, which becomes a thin caller with
`image/png`). Used to hand the reference audio to Kie as a public `uploadUrl`.

### `pipeline/api.py` — `POST /songs/upload-cover`

Multipart (`UploadFile` + `Form`): `file`, `instruction?`, `language="ar"`,
`video_mode="static"`, `vocal_gender="m"`, `suno_model?`. Behavior mirrors
`/songs/import`: validate the upload is audio (`content_type` startswith
`audio/` OR known ext → else 422); run the up-front credit check
(`_song_credit_amount`, **no spend**); create the run dir; save bytes to
`run_dir/reference.<ext>`; `write_state(kind="song", mode="cover",
status="analyzing", reference_filename=..., import_instruction, language,
video_mode, vocal_gender, suno_model)`; spawn the worker. Returns
`{run_id, status: "analyzing"}`.

### `run.py` — analyze branch + submit branch

**Analyze pre-stage** (inside the existing `status=="analyzing" and not
song.json` guard): branch on `mode`:
- `mode == "cover"`: `ref = run_dir/reference_filename`; `bpm=_detect_bpm(ref)`;
  `transcript=_transcribe(ref, language)` (degrade to "" on failure);
  `analysis = _llm_descriptors(...)` style-only; `script =
  build_cover_script(...)`. Write `analysis.json` (descriptors only — never the
  transcript, per [[feedback_cost_disclosure]]) + `song.json` (carrying
  `mode="cover"`, `reference_filename`) + `lyrics.txt`; `awaiting_approval`.
- else: existing YouTube import branch, unchanged.

**Submit branch** (Stage 1): if `current_state.get("mode")=="cover"` (or
`script.get("mode")=="cover"`):
`upload_url = video._upload_file_get_url(run_dir/reference_filename,
content_type="audio/mpeg")` → `task_id = song.submit_cover_job(client,
upload_url=upload_url, lyrics=script["lyrics"], style_prompt=..., title=...,
model=..., vocal_gender=...)`. Otherwise the existing `submit_song_job` path.
Everything after (takes, chosen-take, cover image, assemble/cinematic) is shared.

### Flutter

`new_song_screen.dart` gains an **"Upload a song"** mode (third segment beside
Manual / YouTube): an audio file picker + the "your touch" note + language +
static/cinematic toggle + vocal gender. `client.dart` gains
`uploadCoverSong({filePath/bytes, instruction, language, videoMode,
vocalGender})` (multipart POST). The approve screen already handles `analyzing`
and lyric editing — the user fixes any transcription slips there before paying.

## Run lifecycle

```
POST /songs/upload-cover → analyzing        (worker: librosa + Whisper + LLM)
                         → awaiting_approval (review/EDIT lyrics = "your touch", $0)
                         → approve           (deduct 1 or 3 credits)
                         → generating_song   (submit_cover_job → upload-cover)
                         → generating_cover → assembling → complete
```

## Error handling

- Non-audio / missing file → **422** at the API, before any work.
- Upload too large (Cloud Run ~32 MiB request cap) → 413 with a clear hint
  ("compress or trim to ≤8 min"); typical 3-min MP3 is well under.
- Transcription fails → **degrade**: style-only cover via `build_inspired_script`
  (melody still kept by the cover engine; words become original). Never hard-fail.
- librosa tempo fails → fixed-BPM fallback (existing `song_beats` pattern).
- `upload-cover` submit / public-URL fetch fails → run `failed`,
  `failure_stage="generating_song"`; credits already deducted at approve →
  existing `/resume` retries (audio still on disk).

## Testing (externals mocked — repo invariant)

- **`song.py`:** `submit_cover_job` posts to the cover path with
  `customMode=True, instrumental=False, uploadUrl, style, title, vocalGender`;
  returns `taskId`; missing `taskId` → `KieError`.
- **`song_import.py`:** `section_transcript` (mock LLM) inserts tags →
  `validate_section_tags` passes, words preserved; `build_cover_script` keeps
  words (custom_lyrics passthrough) and returns a valid `SongScript`; empty
  transcript → falls back to inspired (logged).
- **`video.py`:** `_upload_file_get_url` (mock `requests.post`) returns the URL;
  ≥400 → raises; `_upload_image_get_url` still passes its existing tests.
- **`api.py`:** `POST /songs/upload-cover` → 201 `analyzing`; non-audio → 422;
  insufficient credits → 402; persists `mode="cover"` + `reference_filename`.
- **`run.py`:** cover analyze branch (mock detect/transcribe/LLM) → writes
  `song.json` with `mode="cover"` + `awaiting_approval`; cover post-approve
  (mock submit_cover_job + uploader) calls `submit_cover_job` **not**
  `submit_song_job`; existing import + manual paths still pass.
- Append to existing test files — never overwrite (lost-tests regression).
```
