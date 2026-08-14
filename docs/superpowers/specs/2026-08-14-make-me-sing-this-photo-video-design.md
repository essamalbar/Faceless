# "Make Me Sing This" — Photo → Singing Music Video (Phase C)

- **Date:** 2026-08-14
- **Status:** Approved (design, from this session's brainstorm) — spec for implementation
- **Surface:** Python pipeline (`pipeline/`) + Flutter app (`lib/`)
- **Origin:** InsMelo-style "turn your photo into a singing music video". Brainstorm decisions locked this session: entry = finished song; model = Kling AI Avatar (Kie); length = fixed 30s hook (~$2.40); look = the new dark-neon.

---

## 1. Summary

On a **finished song**, add a **"Make me sing this"** action: the user uploads/takes a **photo**, approves a fixed ~$2.40 cost, and we render a **30-second lip-synced music video** of that person performing the song's hook — via **Kie's Kling AI Avatar** (audio-driven, sings, natural lip-sync). Reuses the song audio we already produce plus our existing Kie createTask + file-publish plumbing.

## 2. Goals / non-goals

**Goals:** photo → 30s singing video on a completed song; deterministic fixed cost with approve-before-spend + refund-on-failure; built in the new dark-neon look; reuse existing plumbing.

**Non-goals:** voice cloning / "sing in YOUR voice" (that's the deferred RVC phase); user-selectable length (fixed 30s hook in v1); full-song video; editing the video; a standalone photo→video tab (it lives on song detail).

## 3. Feasibility & reuse (confirmed)

- **Kie Kling AI Avatar** = audio-driven talking/**singing** avatar, lip-sync, ≤5 min, ~$0.08/s. Endpoint `POST https://api.kie.ai/api/v1/jobs/createTask` — **the same endpoint + poll our `pipeline/kie.py` already implements for Kling** (`kie.py:45-65`, `submit_unified_*`/poll). Input: `input.image_url` (JPEG/PNG/WebP ≤10MB) + `input.audio_url` (MP3/WAV/AAC/MP4/OGG ≤10MB) as **public URLs**; output `taskId` → poll "Get Task Details" → `resultJson.resultUrls[0]` = mp4.
- **Publish helpers exist:** `pipeline/video.py:_upload_image_get_url` (photo → public URL) and `_upload_file_get_url` (audio → public URL).
- **ffmpeg everywhere** (prod image + local) for the 30s hook extraction.
- **KNOWN-UNKNOWN:** the exact avatar **model-id string** (e.g. `kling/ai-avatar-std` vs a versioned id) and whether Standard/Pro. Confirm from docs.kie.ai/kling-ai-avatar or the Kie dashboard at build time; store in `config.yaml` as `kie.avatar_model`. Everything else is settled.

## 4. Design

### 4.1 UX (dark-neon)
1. **Song detail** (finished song): a new **"✨ Make me sing this"** action alongside play/download/share.
2. **Perform sheet:** take-photo / upload-photo (front-facing face guidance), a **likeness attestation** ("This is me / I have the right to use this face"), and a clear **cost card** ("30-second hook video · ~$2.40 · charged on approve") → **Approve & render**.
3. **Progress** (poll) → **Result:** the `perform.mp4` on a cinematic dark stage (reuse `video_player_screen`), with **Save / Share / Redo**.

### 4.2 Backend
- **New endpoint:** `POST /songs/{run_id}/perform` (multipart `file` = photo; `ownership_attested` bool). Guards: run exists, status `complete`, `final.mp3` present, terms accepted, ownership attested, balance ≥ `perform_credits`.
- **Flow (subprocess/job, resumable like other renders):**
  1. Validate + save photo to `run_dir/perform_photo{ext}` (image content-type, size cap ~10MB — reuse the avatar upload validation pattern from `POST /artists/{id}/avatar`).
  2. **Extract 30s hook** from `final.mp3` → `run_dir/hook.mp3`: pick the highest-RMS-energy 30s window (reuse `librosa`, already a dep via `song_beats.py`); fallback to a fixed offset (start at 25% of duration) if analysis fails. ffmpeg trims/encodes the segment.
  3. Publish photo (`_upload_image_get_url`) + `hook.mp3` (`_upload_file_get_url`) to public URLs.
  4. **`submit_avatar_job(image_url, audio_url)`** → `createTask` with `model = cfg.kie.avatar_model`, `input={image_url, audio_url}`; poll the unified status endpoint (mirror the existing Kling poll in `kie.py`).
  5. Download `resultUrls[0]` → `run_dir/perform.mp4`; write state `perform_status="complete"`, `perform_video="perform.mp4"`.
- **Credits:** charge `perform_credits_per_video` (config, default **3**, matching cinematic) on approve; **refund on failure** (reuse `credits.py` / `/admin/credit-back` path). Add `avatar` to `api.py:_COST_BY_MODEL` so the dollar figure (~$2.40 = 30s × $0.08) shows on the gate.
- **Serve:** `GET /songs/{run_id}/perform-video` streams `perform.mp4`; include `perform_video` in the song status payload.

### 4.3 New pipeline code
- `pipeline/perform.py` (new): `extract_hook(mp3_path, seconds=30) -> Path`, `submit_avatar_job(image_url, audio_url, model) -> task_id`, `poll_avatar(task_id) -> video_url` (thin wrappers over the existing `kie.py` createTask/poll; keep the HTTP in `kie.py`, orchestration in `perform.py`).
- `config.yaml`: `kie.avatar_model: <confirm from docs>`, `perform_credits_per_video: 3`, `perform_hook_seconds: 30`.

### 4.4 Flutter
- Add **`image_picker`** to `pubspec.yaml` (gallery + camera). Reuse the `_pickAvatar` pattern from `artist_edit_screen.dart`.
- `song_detail_screen.dart`: add the "Make me sing this" action + a `PerformSheet` (photo pick, attestation, cost card, approve). On approve → `client.performSong(runId, bytes, filename, ownershipAttested)`; poll status; show `perform.mp4` via `video_player_screen`.
- `lib/api/client.dart`: `performSong(...)` (multipart POST) + `performVideoUrl(runId)`; extend the song model with `performStatus`/`performVideo`.

## 5. Files touched
| File | Change |
|---|---|
| `pipeline/perform.py` | **New** — hook extraction + avatar submit/poll orchestration. |
| `pipeline/kie.py` | Add `submit_avatar_job` HTTP (createTask with avatar model + image/audio urls) if not covered by existing helper. |
| `pipeline/api.py` | `POST /songs/{id}/perform`, `GET /songs/{id}/perform-video`, `_COST_BY_MODEL['avatar']`, status payload field. |
| `pipeline/credits.py` | (reuse) charge/refund `perform_credits_per_video`. |
| `config.yaml` | `kie.avatar_model`, `perform_credits_per_video`, `perform_hook_seconds`. |
| `pubspec.yaml` | add `image_picker`. |
| `lib/screens/song_detail_screen.dart` | "Make me sing this" action + PerformSheet + result. |
| `lib/api/client.dart` + `models.dart` | `performSong`, `performVideoUrl`, status fields. |
| tests | see §7. |

## 6. Cost / gate / safety
- Fixed **30s hook**, ~**$2.40** Kie spend, charged as `perform_credits_per_video` (default 3) — shown on the approve gate; **charged only on approve**; **refunded on render failure**. Likeness attestation required (rights). Photo stored per-run, not shared beyond the Kie call.

## 7. Testing (external services mocked — never hit real Kie)
- **Backend (pytest):** `extract_hook` returns a ~30s clip from a synthetic mp3 (mock ffmpeg/librosa or use a tiny real clip); `POST /songs/{id}/perform` with a stub Kie client (monkeypatch `submit_avatar_job`/poll) charges credits, writes `perform.mp4` state, and **refunds on a simulated Kie failure**; rejects when run not complete / no attestation / insufficient balance.
- **Flutter:** widget test the PerformSheet (attestation gates approve; cost shown); `client.performSong` posts multipart with the photo (MockClient).
- **Clean env** for pytest (no `.env`); `dart analyze` not `flutter analyze`.

## 8. Rollout
- Built in the new dark-neon look (Phase A). Implement **after Phase B merges** (avoids `song_detail_screen.dart` / `pubspec` collisions). Branch off the redesign line.
- **No deploy** until the operator confirms `kie.avatar_model` against the live Kie account and runs one real end-to-end test; then user QA → deploy.
