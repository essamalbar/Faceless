# Quality Pack — Design Spec

**Date:** 2026-07-16
**Status:** Approved (user: "go on quality pack")
**Context:** Three small, independent quality upgrades that improve every song
made from now on. No new external dependencies.

## 1. Cover faithfulness slider (Kie `audioWeight`)

Kie's upload-cover endpoint accepts `audioWeight` (0–1, 2dp): how closely the
cover follows the source audio. We never sent it — Suno picked its own level.

- `pipeline/song.py::submit_cover_job` gains `audio_weight: float | None`
  (and `style_weight: float | None` for completeness) → body `audioWeight` /
  `styleWeight` (rounded 2dp) only when not None.
- `POST /songs/upload-cover` Form field `audio_weight: float | None`
  (validated 0–1 → 422 outside); stored in run state; `run.py`'s cover submit
  branch passes it through.
- Flutter (upload mode): a "Faithfulness" slider, 0.0–1.0, **default 0.8**
  (the user's covers exist to match the original), helper text: low = more
  creative, high = closer to the original. Bilingual keys.

## 2. Better cover transcription (Whisper model bump)

`song_import._transcribe` hardcodes Whisper `base` — mishears Arabic lyrics,
and wrong words go straight into the cover the user must hand-fix.

- Env `WHISPER_COVER_MODEL` (default **`small`** — worker has 4Gi today;
  `medium` needs ~5GB fp32). `_transcribe` tries the configured model, and on
  ANY failure (incl. OOM) retries once with `base` before the existing
  degrade-to-"" path. Never worse than today.
- Deployment: bump the pipeline Job to **8Gi** and set
  `WHISPER_COVER_MODEL=medium` in prod (best quality; cost is per-second of
  job runtime, marginal).

## 3. LLM balance alarm (silent-Groq-degradation banner)

When Anthropic credits run out, `FallbackLLM` silently switches to Groq and
Arabic lyric quality drops — the user discovered this the painful way once.

- `FallbackLLM` gains an optional `on_fallback(exc)` callback; the API's
  `_build_song_llm` passes one that writes `llm_fallback.json` under the out
  root: `{last_fallback_at, error}` (atomic write, best-effort).
- `GET /system/llm-status` (auth): `{degraded: bool, last_fallback_at,
  error}` — degraded = marker within the last 24h.
- Flutter home: on load (best-effort, silent on failure) check the status;
  when degraded show a dismissible amber banner: "Lyric quality reduced — the
  primary writing model is unavailable (check Anthropic credits)." Bilingual.

## Testing (externals mocked)

- `test_song.py`: cover job body carries `audioWeight` 2dp when set, absent
  when None; 0/1 boundaries.
- `test_api.py`: upload-cover accepts/validates `audio_weight` (422 at 1.5),
  persists to state; `/system/llm-status` degraded true/false by marker age.
- `test_run_song_mode.py`: cover post-approve passes the stored weight into
  `submit_cover_job` (extend the existing cover test).
- `test_llm.py` (or new): `FallbackLLM` fires `on_fallback` exactly on
  primary failure; never on success; callback errors are swallowed.
- Flutter: analyzer clean, ARB parity.

## Non-goals

`weirdnessConstraint` exposure; per-song Whisper model UI; live Anthropic
balance probing (costs money — the marker reacts to real failures instead).
