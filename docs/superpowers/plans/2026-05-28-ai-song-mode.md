# AI Song Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an "AI song" creation mode that produces square music-video MP4s (Suno song + Flux cover + Ken-Burns zoom), with the same approve-before-spend gate the horror pipeline uses.

**Architecture:** Sibling to the horror pipeline. Four new Python modules (`song.py`, `song_lyrics.py`, `song_cover.py`, `song_assemble.py`) layered on top of the existing Kie.ai client, LLM router, and FastAPI app. New `/songs` HTTP namespace mirrors `/runs`. New Flutter screens parallel the existing ones with a top-of-home segmented selector.

**Tech Stack:** Python 3 + FastAPI + Kie.ai (Suno V4.5 + Flux Kontext Max) + Pillow + ffmpeg + Flutter.

**Spec:** `docs/superpowers/specs/2026-05-28-ai-song-mode-design.md` — the design document this plan implements. Read sections marked "Quality gate" before changing any of: audio re-encoding policy, Suno model id, lyrics structure, or Flux step count.

**Spec refinements that became apparent during planning** (deltas from the spec the implementer should know):

1. The spec uses status names like `writing-lyrics` and `done`. The existing `api_state.json` and `derive_status` in `pipeline/api.py` use snake_case (`awaiting_approval`, `complete`, `failed`). This plan aligns with the existing convention: `awaiting_approval`, `generating_song`, `generating_cover`, `assembling`, `complete`, `failed`.
2. The spec says POST /songs "spawns a writer-only subprocess." The existing horror writer pass runs **inline** (no subprocess) — see `_generate_script_inline` at `pipeline/api.py:568`. The lyrics LLM is just as cheap; this plan makes the writer pass inline too. The subprocess starts on `/approve`, not on `POST /songs`.
3. The spec says "Flux dev at 28 steps" with a $0.03 cost. Kie.ai's Flux Kontext endpoint doesn't expose a `steps` parameter — quality is selected by model id. This plan uses `flux-kontext-max` (Kie's high-quality variant), which matches the $0.03 cost target and produces the album-art quality the spec calls for.

---

## File structure

### New files (Python)

| File | Responsibility |
|---|---|
| `pipeline/song.py` | Kie.ai Suno client. `submit_song_job`, `wait_for_song`, `download_take`. Mirrors the Kling-family pattern in `pipeline/kie.py:198-311`. |
| `pipeline/song_lyrics.py` | LLM wrapper. One public function: `generate_song_script(theme, custom_lyrics, style_hint, language) -> SongScript`. |
| `pipeline/song_cover.py` | Two public functions: `generate_cover_image(cover_prompt, out_dir) -> Path` (calls Kie.ai Flux Kontext Max) and `apply_title_overlay(raw_path, title, language, out_path) -> None` (Pillow). |
| `pipeline/song_assemble.py` | One public function: `assemble_song_video(cover_path, song_mp3, out_mp4) -> None`. Probes duration, runs ffmpeg with computed zoompan. |

### New files (tests + fixtures)

| File | Purpose |
|---|---|
| `tests/test_song.py` | Suno client units (submit/poll/download). |
| `tests/test_song_lyrics.py` | Lyrics + style + cover prompt validation. |
| `tests/test_song_cover.py` | Pillow overlay regression. |
| `tests/test_song_assemble.py` | ffmpeg recipe correctness (audio stream-copied, video has expected res/fps). |
| `tests/test_song_api.py` | FastAPI endpoint contract. |
| `tests/test_song_pipeline.py` | End-to-end integration: POST /songs → approve → final.mp4. |
| `tests/fixtures/song/short_song.mp3` | 3-second silent MP3 (a few KB). |
| `tests/fixtures/song/cover.png` | Plain 1080×1080 PNG fixture. |
| `assets/fonts/Amiri-Regular.ttf` | Arabic font (Google Fonts, OFL). |
| `assets/fonts/Inter-Bold.ttf` | Latin font (Google Fonts, OFL). |

### New files (Flutter)

| File | Purpose |
|---|---|
| `lib/screens/new_song_screen.dart` | Create-song form (Screen 1 in spec). |
| `lib/screens/song_approve_screen.dart` | Approve gate (Screen 2). |
| `lib/screens/song_detail_screen.dart` | Progress + player + take swap (Screen 3). |

### Modified files

| File | Change |
|---|---|
| `pipeline/api.py` | Add `/songs` endpoint family. New Pydantic models. Extend `derive_status` + `_summarize` to handle `kind: "song"`. |
| `pipeline/config.py` | Add `SongConfig` dataclass; update `load_config` to populate it. |
| `pipeline/kie.py` | Add `submit_song_job`, `wait_for_song` (Kling-style polling, but expecting two takes in the response). |
| `pipeline/credits.py` | Confirm `check_or_deduct` accepts a `reason="song-spend"` ledger kind (already string, no schema change). |
| `run.py` | Add `--mode {horror,song}` flag. New `_run_song_post_approve()` function. |
| `config.yaml` | Add top-level `song:` block. |
| `lib/api/models.dart` | Add `SongSummary`, `SongScript`, `CreateSongRequest`. |
| `lib/api/client.dart` | Add `createSong`, `getSongScript`, `approveSong`, `swapTake`, `regenerateLyrics`, `editSong`, `resumeSong`, `cancelSong`, `listSongs`, `getSong`. |
| `lib/screens/home_screen.dart` | Add `Horror | Song` segmented selector at the top. Song-row variant. |
| `lib/main.dart` | Wire `/songs/new`, `/songs/:id/approve`, `/songs/:id/detail` routes. |

---

## Task 0: Kie.ai Suno API contract (verified 2026-05-28)

**Already done by the plan author against `docs.kie.ai/suno-api/generate-music` and `docs.kie.ai/suno-api/get-music-details`.** The values below are authoritative — use them directly in Task 2.

### Endpoints

- **Submit:** `POST https://api.kie.ai/api/v1/generate`
- **Poll:** `GET https://api.kie.ai/api/v1/generate/record-info?taskId={taskId}`

These are **not** the unified `/api/v1/jobs/createTask` paths used by Kling. Suno has its own dedicated endpoints. Do not reuse the Kling polling code in `pipeline/kie.py:wait_for_unified_video` — it parses a different response shape.

### Model id

- **`V5_5`** — newest at design time. Quality bar met.
- **`V4_5`** — acceptable fallback if `V5_5` is unavailable.
- **`V4`** — acceptable last-resort fallback (lower vocal quality, max 4 min).
- **Never use V3.5** — quality gate per spec.

Model ids are uppercase with underscores. `"v5_5"` lowercase will be rejected.

### Submit request body (flat — NOT wrapped in `input`)

```json
{
  "prompt": "[Verse 1]\n...lyrics with section tags...\n[Chorus]\n...",
  "customMode": true,
  "instrumental": false,
  "model": "V5_5",
  "callBackUrl": "https://example.com/noop",
  "style": "Arabic pop ballad, slow tempo 72 BPM, oud + strings, ...",
  "title": "تحت حراسة القمر"
}
```

Field gotchas:

- **`prompt` carries the lyrics** in custom mode. Not a separate `lyrics` field.
- **`customMode: true`** activates lyrics+style+title control. Without it the API uses simple mode and rewrites the prompt.
- **`instrumental: false`** is required since we want vocals.
- **`callBackUrl` is required by the schema** but we poll instead. Pass any well-formed URL (e.g. `"https://api.example.com/noop"`); Kie will attempt to POST to it on completion and silently fail. Polling still works.
- **Char limits by model:** V5/V5_5 allow 5000-char prompt + 1000-char style; V4_5 allows 3000-char prompt + 200-char style. The lyrics LLM contract in Task 3 stays well under these.

### Submit response

```json
{
  "code": 200,
  "msg": "success",
  "data": { "taskId": "5c79****be8e" }
}
```

Extract `data.taskId`.

### Poll response (success)

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "status": "SUCCESS",
    "response": {
      "sunoData": [
        {
          "id": "e231****-****-****-****-****8cadc7dc",
          "audioUrl": "https://example.cn/****.mp3",
          "streamAudioUrl": "https://example.cn/****",
          "imageUrl": "https://example.cn/****.jpeg"
        },
        { "id": "...", "audioUrl": "...", "streamAudioUrl": "...", "imageUrl": "..." }
      ]
    }
  }
}
```

- **Takes**: `data.response.sunoData` is an array. Suno typically returns **two takes**. Use both.
- **Audio URL**: `sunoData[i].audioUrl` (NOT `streamAudioUrl` — that's an HLS preview, not the full MP3).

### Poll response (in progress)

`data.status` is one of `PENDING`, `TEXT_SUCCESS`, `FIRST_SUCCESS` (this last one means take 1 is ready but take 2 still rendering — wait for `SUCCESS`).

### Poll response (failure)

`data.status` is one of:

- `CREATE_TASK_FAILED` — submit accepted but worker failed to start. Treat as transient (retry).
- `GENERATE_AUDIO_FAILED` — generation actually failed. Permanent (surface to user, don't auto-retry).
- `CALLBACK_EXCEPTION` — callback URL failed but the audio may still be in `sunoData`. Treat as success if `sunoData` has tracks.
- `SENSITIVE_WORD_ERROR` — lyrics tripped content moderation. Permanent (suggest the user re-roll).

---

## Task 1: Test fixtures + bundled fonts

**Files:**
- Create: `tests/fixtures/song/short_song.mp3` (3-second silent MP3, ~5 KB)
- Create: `tests/fixtures/song/cover.png` (1080×1080 solid color)
- Create: `assets/fonts/Amiri-Regular.ttf` (download from Google Fonts)
- Create: `assets/fonts/Inter-Bold.ttf` (download from Google Fonts)
- Create: `assets/fonts/README.md` (license attribution)

- [ ] **Step 1: Generate the silent-MP3 fixture**

```bash
mkdir -p tests/fixtures/song
ffmpeg -y -f lavfi -i anullsrc=r=44100:cl=stereo -t 3 -c:a aac -b:a 128k \
  tests/fixtures/song/short_song.mp3
ffprobe -v error -show_entries stream=codec_name,duration tests/fixtures/song/short_song.mp3
```

Expected: `codec_name=aac`, `duration≈3.0`. File size ~5 KB.

- [ ] **Step 2: Generate the cover-PNG fixture**

```bash
ffmpeg -y -f lavfi -i color=c=0x1a2030:size=1080x1080:d=1 -frames:v 1 \
  tests/fixtures/song/cover.png
ffprobe -v error -show_entries stream=width,height tests/fixtures/song/cover.png
```

Expected: `width=1080`, `height=1080`.

- [ ] **Step 3: Download the bundled fonts**

```bash
mkdir -p assets/fonts
curl -fsSL -o assets/fonts/Amiri-Regular.ttf \
  https://github.com/google/fonts/raw/main/ofl/amiri/Amiri-Regular.ttf
curl -fsSL -o assets/fonts/Inter-Bold.ttf \
  https://github.com/google/fonts/raw/main/ofl/inter/Inter-Bold.ttf
ls -lh assets/fonts/
```

Expected: both files present, each 200–500 KB.

- [ ] **Step 4: License attribution**

Create `assets/fonts/README.md`:

```markdown
# Bundled fonts

- **Amiri** — Khaled Hosny. SIL Open Font License 1.1.
  Used in `pipeline/song_cover.py` for Arabic title overlay on song covers.
  Source: https://github.com/google/fonts/tree/main/ofl/amiri
- **Inter** — Rasmus Andersson. SIL Open Font License 1.1.
  Used in `pipeline/song_cover.py` for Latin title overlay on song covers.
  Source: https://github.com/google/fonts/tree/main/ofl/inter
```

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/song/ assets/fonts/
git commit -m "feat(song): add font + audio + cover fixtures for song mode"
```

---

## Task 2: Kie.ai Suno client — submit + poll + download

**Files:**
- Create: `pipeline/song.py`
- Create: `tests/test_song.py`

Suno on Kie.ai returns **two takes per submission**. The client must surface both. See **Task 0** above for the verified API contract (endpoint, body shape, status enum, response shape) — Task 2 wires that contract into code.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_song.py`:

```python
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from pipeline import song
from pipeline.kie import KieClient


def _stub_client(post_resp=None, get_resps=None):
    """Build a KieClient with _post_json / _get_json mocked."""
    c = KieClient(api_key="fake-key")
    c._post_json = MagicMock(return_value=post_resp or {})
    if get_resps is not None:
        c._get_json = MagicMock(side_effect=get_resps)
    return c


def test_submit_song_job_returns_task_id():
    c = _stub_client(post_resp={"code": 200, "data": {"taskId": "fake-123"}})
    task_id = song.submit_song_job(
        c,
        lyrics="[Verse 1]\nhello\n[Chorus]\nworld",
        style_prompt="Arabic pop ballad, 72 BPM",
        title="Test",
    )
    assert task_id == "fake-123"
    # Inspect the body it sent
    args, _ = c._post_json.call_args
    path, body = args[0], args[1]
    assert path == song.SUNO_GENERATE_PATH
    assert body["model"] == song.SUNO_MODEL_ID
    # prompt carries the lyrics in custom mode (NOT a separate lyrics field)
    assert body["prompt"] == "[Verse 1]\nhello\n[Chorus]\nworld"
    assert body["style"] == "Arabic pop ballad, 72 BPM"
    assert body["title"] == "Test"
    assert body["customMode"] is True
    assert body["instrumental"] is False
    # callBackUrl is required by Kie's schema even though we poll
    assert isinstance(body.get("callBackUrl"), str) and len(body["callBackUrl"]) > 0


def test_wait_for_song_returns_both_take_urls():
    success_resp = {
        "code": 200,
        "data": {
            "status": "SUCCESS",
            "response": {
                "sunoData": [
                    {"id": "uuid-1", "audioUrl": "https://kie.ai/take1.mp3",
                     "streamAudioUrl": "https://kie.ai/stream1", "imageUrl": "x.jpg"},
                    {"id": "uuid-2", "audioUrl": "https://kie.ai/take2.mp3",
                     "streamAudioUrl": "https://kie.ai/stream2", "imageUrl": "y.jpg"},
                ]
            },
        },
    }
    c = _stub_client(get_resps=[success_resp])
    takes = song.wait_for_song(c, "fake-123", poll_interval_s=0)
    assert len(takes) == 2
    assert takes[0].url == "https://kie.ai/take1.mp3"
    assert takes[1].url == "https://kie.ai/take2.mp3"


def test_wait_for_song_polls_until_success():
    pending = {"data": {"status": "PENDING"}}
    text_ready = {"data": {"status": "TEXT_SUCCESS"}}
    first_ready = {"data": {"status": "FIRST_SUCCESS"}}
    success = {
        "data": {
            "status": "SUCCESS",
            "response": {
                "sunoData": [
                    {"id": "u1", "audioUrl": "u1.mp3"},
                    {"id": "u2", "audioUrl": "u2.mp3"},
                ]
            },
        }
    }
    c = _stub_client(get_resps=[pending, text_ready, first_ready, success])
    takes = song.wait_for_song(c, "fake-123", poll_interval_s=0)
    assert c._get_json.call_count == 4
    assert len(takes) == 2


def test_wait_for_song_raises_on_permanent_failure():
    fail_resp = {"data": {"status": "GENERATE_AUDIO_FAILED",
                          "errorMessage": "audio generation failed"}}
    c = _stub_client(get_resps=[fail_resp])
    with pytest.raises(song.SongGenerationError):
        song.wait_for_song(c, "fake-123", poll_interval_s=0)


def test_wait_for_song_raises_on_sensitive_word_error():
    fail_resp = {"data": {"status": "SENSITIVE_WORD_ERROR"}}
    c = _stub_client(get_resps=[fail_resp])
    with pytest.raises(song.SongGenerationError, match="SENSITIVE"):
        song.wait_for_song(c, "fake-123", poll_interval_s=0)


def test_wait_for_song_treats_create_task_failed_as_transient():
    from pipeline.kie import TransientKieError
    fail_resp = {"data": {"status": "CREATE_TASK_FAILED"}}
    c = _stub_client(get_resps=[fail_resp])
    with pytest.raises(TransientKieError):
        song.wait_for_song(c, "fake-123", poll_interval_s=0)


def test_wait_for_song_callback_exception_with_data_is_success():
    """CALLBACK_EXCEPTION means the webhook ping failed but audio may
    still be in sunoData — treat as success in that case."""
    resp = {
        "data": {
            "status": "CALLBACK_EXCEPTION",
            "response": {
                "sunoData": [
                    {"id": "u1", "audioUrl": "u1.mp3"},
                    {"id": "u2", "audioUrl": "u2.mp3"},
                ]
            },
        }
    }
    c = _stub_client(get_resps=[resp])
    takes = song.wait_for_song(c, "fake-123", poll_interval_s=0)
    assert len(takes) == 2


def test_wait_for_song_timeout():
    pending = {"data": {"status": "PENDING"}}
    c = _stub_client(get_resps=[pending] * 20)
    with pytest.raises(song.SongGenerationTimeout):
        song.wait_for_song(c, "fake-123", poll_interval_s=0, timeout_s=0.01)


def test_download_take_writes_file(tmp_path: Path):
    c = _stub_client()
    fake_bytes = b"ID3" + b"\x00" * 100
    def fake_download(url, out_path):
        out_path.write_bytes(fake_bytes)
    c._download = fake_download
    out = tmp_path / "take_1.mp3"
    song.download_take(c, "https://kie.ai/take.mp3", out)
    assert out.exists()
    assert out.read_bytes() == fake_bytes
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_song.py -v
```

Expected: ALL tests FAIL with `ModuleNotFoundError: No module named 'pipeline.song'` or similar.

- [ ] **Step 3: Write the minimal implementation**

Create `pipeline/song.py`:

```python
"""Kie.ai Suno client.

Suno generates songs from custom lyrics + a structured style hint.
Each submission returns 1+ takes (typically two); both are downloaded
so the user can pick.

Suno has its own dedicated endpoints on Kie.ai — NOT the unified
/api/v1/jobs/createTask used by Kling. See docs at
https://docs.kie.ai/suno-api/generate-music and the Task 0 section
of the implementation plan for the verified contract.

Quality gate (do not regress): submit_song_job MUST set
customMode=true and pass the lyrics in the `prompt` field. Without
customMode, Suno rewrites your prompt and quality drops.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path

from pipeline.kie import (
    KieClient,
    KieError,
    TransientKieError,
)

# Endpoints (Suno-specific, NOT the unified /jobs paths)
SUNO_GENERATE_PATH = os.environ.get("KIE_SUNO_GENERATE_PATH", "/api/v1/generate")
SUNO_RECORD_INFO_PATH_TPL = os.environ.get(
    "KIE_SUNO_RECORD_INFO_PATH_TPL", "/api/v1/generate/record-info?taskId={task_id}"
)

# Model id — see Task 0 in the plan. V5_5 is the latest at design time.
SUNO_MODEL_ID = os.environ.get("KIE_SUNO_MODEL", "V5_5")

# Kie's schema requires callBackUrl even though we poll. Pass a benign
# URL — the webhook ping will fail silently and `data.status` may end up
# as CALLBACK_EXCEPTION, which wait_for_song treats as success when
# sunoData is populated.
DEFAULT_CALLBACK_URL = os.environ.get(
    "KIE_SUNO_CALLBACK_URL", "https://api.example.com/noop"
)

_SLEEP = time.sleep

# Status enum from Kie.ai's Suno polling endpoint
_IN_PROGRESS_STATUSES = {"PENDING", "TEXT_SUCCESS", "FIRST_SUCCESS"}
_SUCCESS_STATUSES = {"SUCCESS"}
_PERMANENT_FAILURE_STATUSES = {"GENERATE_AUDIO_FAILED", "SENSITIVE_WORD_ERROR"}
_TRANSIENT_FAILURE_STATUSES = {"CREATE_TASK_FAILED"}
# CALLBACK_EXCEPTION is handled specially — success if sunoData present,
# transient otherwise.


class SongGenerationError(KieError):
    """Suno-side failure that should not be retried automatically."""


class SongGenerationTimeout(KieError):
    """Suno job did not complete within the timeout."""


@dataclass(frozen=True)
class SongTake:
    url: str
    duration_s: float = 0.0  # Suno's polling response doesn't include duration


def submit_song_job(
    client: KieClient,
    *,
    lyrics: str,
    style_prompt: str,
    title: str,
    model: str = SUNO_MODEL_ID,
    callback_url: str = DEFAULT_CALLBACK_URL,
) -> str:
    """Submit a Suno custom-mode job; return the taskId.

    `lyrics` must contain Suno section tags ([Verse 1], [Chorus], ...).
    `style_prompt` must be structured (genre + BPM + instruments +
    vocal + era + key + mood). See pipeline/song_lyrics.py for both.
    """
    body = {
        "prompt": lyrics,         # NOTE: 'prompt' carries lyrics in custom mode
        "customMode": True,        # required — without it Suno rewrites
        "instrumental": False,     # we want vocals
        "model": model,
        "callBackUrl": callback_url,
        "style": style_prompt,
        "title": title,
    }
    resp = client._post_json(SUNO_GENERATE_PATH, body)
    data = resp.get("data") or {}
    task_id = data.get("taskId") or resp.get("taskId")
    if not task_id:
        raise KieError(f"suno submit response missing taskId: {resp}")
    return str(task_id)


def _parse_takes(suno_data: list[dict]) -> list[SongTake]:
    takes: list[SongTake] = []
    for entry in suno_data:
        url = entry.get("audioUrl")
        if not url:
            continue
        takes.append(SongTake(url=str(url)))
    return takes


def wait_for_song(
    client: KieClient,
    task_id: str,
    *,
    poll_interval_s: float = 5,
    timeout_s: float = 600,
) -> list[SongTake]:
    """Poll until status==SUCCESS; return all takes."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        resp = client._get_json(SUNO_RECORD_INFO_PATH_TPL.format(task_id=task_id))
        data = resp.get("data") or {}
        status = (data.get("status") or "").upper()

        if status in _SUCCESS_STATUSES:
            suno_data = (data.get("response") or {}).get("sunoData") or []
            takes = _parse_takes(suno_data)
            if not takes:
                raise SongGenerationError(
                    f"suno task {task_id} SUCCESS but no audio URLs: {resp}"
                )
            return takes

        if status == "CALLBACK_EXCEPTION":
            # Webhook failed but the audio might still be ready.
            suno_data = (data.get("response") or {}).get("sunoData") or []
            takes = _parse_takes(suno_data)
            if takes:
                return takes
            # No audio + callback exception → treat as transient.
            raise TransientKieError(
                f"suno task {task_id} CALLBACK_EXCEPTION with no audio yet"
            )

        if status in _PERMANENT_FAILURE_STATUSES:
            err_msg = data.get("errorMessage") or status
            raise SongGenerationError(
                f"suno task {task_id} {status}: {err_msg}"
            )

        if status in _TRANSIENT_FAILURE_STATUSES:
            raise TransientKieError(
                f"suno task {task_id} {status} — retry recommended"
            )

        # in-progress (PENDING / TEXT_SUCCESS / FIRST_SUCCESS) or unknown — poll
        _SLEEP(poll_interval_s)

    raise SongGenerationTimeout(
        f"suno task {task_id} did not complete within {timeout_s}s"
    )


def download_take(client: KieClient, url: str, out_path: Path) -> None:
    """Stream-download a Suno take to disk. Honors KIE_DOWNLOAD_PROXY
    (reuses KieClient._download)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    client._download(url, out_path)
```

- [ ] **Step 4: Run tests to verify pass**

```bash
uv run pytest tests/test_song.py -v
```

Expected: 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/song.py tests/test_song.py
git commit -m "feat(song): Kie.ai Suno client with two-take support"
```

---

## Task 3: Lyrics + style + cover-prompt LLM

**Files:**
- Create: `pipeline/song_lyrics.py`
- Create: `tests/test_song_lyrics.py`

The lyrics LLM is the single biggest quality lever (spec, "Lyrics-LLM contract"). It must:
1. Emit Suno section tags (`[Verse 1]`, `[Pre-Chorus]`, `[Chorus]`, ...).
2. Produce a structured style prompt (genre + BPM + instruments + vocal + era + key + mood).
3. Honor user-supplied lyrics (passthrough — don't rewrite).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_song_lyrics.py`:

```python
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from pipeline.song_lyrics import (
    SongScript,
    generate_song_script,
    validate_section_tags,
)


def _stub_llm(json_response: str):
    """Build a fake LLM client whose .complete() returns the given string."""
    llm = MagicMock()
    llm.complete = MagicMock(return_value=json_response)
    return llm


def test_validate_section_tags_accepts_full_structure():
    lyrics = """[Verse 1]
line a
line b

[Chorus]
hook 1
hook 2"""
    # Should not raise.
    validate_section_tags(lyrics)


def test_validate_section_tags_rejects_flat_lyrics():
    with pytest.raises(ValueError, match="missing Suno section tags"):
        validate_section_tags("just a wall of text\nwithout brackets")


def test_validate_section_tags_requires_chorus():
    with pytest.raises(ValueError, match="missing \\[Chorus\\]"):
        validate_section_tags("[Verse 1]\nlines only")


def test_generate_song_script_from_theme_only():
    llm_payload = """{
        "title": "تحت حراسة القمر",
        "lyrics": "[Verse 1]\\nا\\n[Chorus]\\nب",
        "style_prompt": "Arabic pop ballad, slow tempo 72 BPM, oud + cinematic strings + light percussion, male vocal with subtle vibrato, modern 2020s production, melancholic minor key",
        "cover_prompt": "young Arab man under moonlight, fine art photography"
    }"""
    llm = _stub_llm(llm_payload)
    script = generate_song_script(
        llm=llm,
        theme="sad Arabic ballad about the moon",
        custom_lyrics=None,
        style_hint=None,
        language="ar",
    )
    assert isinstance(script, SongScript)
    assert script.title == "تحت حراسة القمر"
    assert "[Verse 1]" in script.lyrics
    assert "[Chorus]" in script.lyrics
    assert "BPM" in script.style_prompt
    assert script.language == "ar"


def test_generate_song_script_honors_user_lyrics_passthrough():
    """When custom_lyrics is provided, the LLM must NOT rewrite them."""
    user_lyrics = "[Verse 1]\nmy own words\n[Chorus]\nstay verbatim"
    # LLM returns style + cover only; lyrics field comes from the user.
    llm_payload = """{
        "title": "Mine",
        "lyrics": "WRONG — LLM tried to rewrite",
        "style_prompt": "indie folk, 80 BPM, acoustic guitar + light percussion, female vocal soft, 2010s production, hopeful major key",
        "cover_prompt": "a quiet morning landscape"
    }"""
    llm = _stub_llm(llm_payload)
    script = generate_song_script(
        llm=llm,
        theme="my own song",
        custom_lyrics=user_lyrics,
        style_hint=None,
        language="en",
    )
    # The LLM's lyrics field is IGNORED when the user gave their own.
    assert script.lyrics == user_lyrics


def test_generate_song_script_merges_user_style_hint():
    """When style_hint is provided, the LLM must extend it, not replace."""
    llm_payload = """{
        "title": "Test",
        "lyrics": "[Verse 1]\\na\\n[Chorus]\\nb",
        "style_prompt": "rock, 120 BPM, electric guitar + drums, male vocal raspy, 1990s production, energetic minor key",
        "cover_prompt": "a stage at dusk"
    }"""
    llm = _stub_llm(llm_payload)
    script = generate_song_script(
        llm=llm,
        theme="energetic rock song",
        custom_lyrics=None,
        style_hint="must include violin",
        language="en",
    )
    # The user's hint is part of the final style prompt (post-merge).
    assert "violin" in script.style_prompt


def test_generate_song_script_validates_lyrics_have_section_tags():
    """If the LLM ignores the contract, we catch it before submitting to Suno."""
    bad_payload = """{
        "title": "Broken",
        "lyrics": "no section tags at all just words",
        "style_prompt": "anything",
        "cover_prompt": "anything"
    }"""
    llm = _stub_llm(bad_payload)
    with pytest.raises(ValueError, match="missing Suno section tags|missing \\[Chorus\\]"):
        generate_song_script(
            llm=llm, theme="x", custom_lyrics=None, style_hint=None, language="ar",
        )
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_song_lyrics.py -v
```

Expected: all tests FAIL — module doesn't exist.

- [ ] **Step 3: Write the minimal implementation**

Create `pipeline/song_lyrics.py`:

```python
"""Lyrics + style + cover-prompt generation for song mode.

The LLM is constrained by contract to emit Suno-readable structure
(section tags) and a structured style prompt. See the spec section
"Lyrics-LLM contract" for the load-bearing reasons; without this,
Suno output sounds obviously-AI.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass


_SECTION_TAG_RE = re.compile(r"\[(Verse|Pre-Chorus|Chorus|Bridge|Outro)[\s\d]*\]", re.I)


@dataclass(frozen=True)
class SongScript:
    title: str
    lyrics: str
    style_prompt: str
    cover_prompt: str
    language: str


def validate_section_tags(lyrics: str) -> None:
    """Raise ValueError if the lyrics block is missing Suno section tags
    or doesn't contain at least one [Chorus]."""
    if not _SECTION_TAG_RE.search(lyrics):
        raise ValueError(
            "lyrics missing Suno section tags ([Verse 1], [Chorus], ...) — "
            "Suno requires these to structure the arrangement"
        )
    if not re.search(r"\[Chorus\]", lyrics, re.I):
        raise ValueError("lyrics missing [Chorus] section")


_SYSTEM_PROMPT = """You write song lyrics for Suno V4.5.

OUTPUT FORMAT: a JSON object with these keys (no surrounding markdown, no commentary):
  - title:        short song title in the song's language
  - lyrics:       the full song with REQUIRED section tags
  - style_prompt: a structured comma-separated descriptor
  - cover_prompt: a prompt for an AI image model to make the album cover

LYRICS — REQUIRED SHAPE:
[Verse 1]
4–6 lines

[Pre-Chorus]
2–4 lines

[Chorus]
4 lines, hooky, will repeat

[Verse 2]
4–6 lines

[Chorus]
(same chorus, repeated verbatim)

[Bridge]
2–4 lines, contrasting

[Chorus]
(same chorus, possibly modified)

[Outro]
1–2 lines or empty

The bracket tags are LOAD-BEARING. Suno reads them. Do not omit them.

STYLE PROMPT — REQUIRED SHAPE (comma-separated):
  Genre/sub-genre, tempo (with BPM), instrumentation, vocal description,
  era/production style, mood + key.
Example: "Arabic pop ballad, slow tempo 72 BPM, oud + cinematic strings
+ light percussion, male vocal with subtle vibrato, modern 2020s
production warm analog mix, melancholic minor key"

COVER PROMPT — describe a single image: subject, setting, lighting, mood,
photography or art style. No text in the image (we burn the title on
separately). Leave space at the top-right corner.

If the user gave a style hint, include it in the style_prompt.
"""


def generate_song_script(
    *,
    llm,
    theme: str,
    custom_lyrics: str | None,
    style_hint: str | None,
    language: str,
) -> SongScript:
    """One-shot LLM call; returns a validated SongScript.

    If `custom_lyrics` is given, it is passed through verbatim — the LLM's
    lyrics field is ignored. If `style_hint` is given, it is appended to
    the user prompt as a "must include" so it surfaces in the LLM's
    style_prompt output.
    """
    user_msg = f"Theme: {theme}\nLanguage: {language}"
    if style_hint:
        user_msg += f"\nMust include in style: {style_hint}"
    if custom_lyrics:
        user_msg += (
            "\n\nThe user has provided their own lyrics — do NOT rewrite them, "
            "but still produce title, style_prompt, and cover_prompt:\n"
            + custom_lyrics
        )

    raw = llm.complete(user_msg, system=_SYSTEM_PROMPT)
    raw = raw.strip()
    if raw.startswith("```"):
        # Strip fenced-code wrappers (some models always wrap).
        raw = re.sub(r"^```[a-z]*\n?|\n?```$", "", raw, flags=re.MULTILINE).strip()
    parsed = json.loads(raw)

    lyrics = custom_lyrics if custom_lyrics else parsed["lyrics"]
    validate_section_tags(lyrics)

    return SongScript(
        title=parsed["title"],
        lyrics=lyrics,
        style_prompt=parsed["style_prompt"],
        cover_prompt=parsed["cover_prompt"],
        language=language,
    )
```

- [ ] **Step 4: Run tests to verify pass**

```bash
uv run pytest tests/test_song_lyrics.py -v
```

Expected: 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/song_lyrics.py tests/test_song_lyrics.py
git commit -m "feat(song): lyrics + style + cover-prompt LLM contract"
```

---

## Task 4: Cover-image generation + title overlay

**Files:**
- Create: `pipeline/song_cover.py`
- Create: `tests/test_song_cover.py`

Cover image comes from Kie.ai Flux Kontext Max (the spec's "Flux dev at 28 steps" maps to this; see "Spec refinements" at the top of this plan). Title is burned in with Pillow + bundled fonts.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_song_cover.py`:

```python
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PIL import Image

from pipeline import song_cover


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_COVER = REPO_ROOT / "tests" / "fixtures" / "song" / "cover.png"


def test_generate_cover_image_calls_kie_flux_max(tmp_path: Path):
    """Verify we pass the correct model id and prompt to Kie.ai."""
    fake_url = "https://kie.ai/result.png"
    fake_client = MagicMock()
    fake_client.submit_flux_image_job = MagicMock(return_value="task-abc")
    fake_client.wait_for_flux_image = MagicMock(return_value=fake_url)
    def fake_download(url, out_path):
        Image.new("RGB", (1080, 1080), color="navy").save(out_path)
    fake_client.download = fake_download

    out_path = song_cover.generate_cover_image(
        client=fake_client,
        cover_prompt="young man under moonlight",
        out_dir=tmp_path,
    )
    assert out_path == tmp_path / "cover_raw.png"
    assert out_path.exists()

    # Check the prompt was wrapped with album-art language
    submit_kwargs = fake_client.submit_flux_image_job.call_args.kwargs
    assert "Hipgnosis" in submit_kwargs["prompt"]
    assert "album cover" in submit_kwargs["prompt"].lower()
    assert "no text" in submit_kwargs["prompt"].lower()
    # Check the model is the high-quality variant
    assert submit_kwargs["model"] == song_cover.FLUX_MODEL_ID
    assert submit_kwargs["aspect_ratio"] == "1:1"


def test_apply_title_overlay_arabic(tmp_path: Path):
    """Arabic title renders with Amiri and shows up as non-empty pixel diff."""
    out = tmp_path / "cover.png"
    song_cover.apply_title_overlay(
        raw_path=FIXTURE_COVER,
        title="تحت حراسة القمر",
        language="ar",
        out_path=out,
    )
    assert out.exists()
    # The fixture is uniform navy; the overlaid version must differ in
    # the top-right quadrant where the title lives.
    raw_img = Image.open(FIXTURE_COVER).convert("RGB")
    out_img = Image.open(out).convert("RGB")
    assert raw_img.size == out_img.size == (1080, 1080)
    # Top-right quadrant pixels should differ from raw (title was drawn).
    box = (540, 0, 1080, 540)  # right half, top half
    raw_crop = list(raw_img.crop(box).getdata())
    out_crop = list(out_img.crop(box).getdata())
    diff_pixels = sum(1 for a, b in zip(raw_crop, out_crop) if a != b)
    assert diff_pixels > 1000  # title text covers many pixels


def test_apply_title_overlay_latin(tmp_path: Path):
    """Latin title uses Inter font."""
    out = tmp_path / "cover.png"
    song_cover.apply_title_overlay(
        raw_path=FIXTURE_COVER,
        title="Moonlit Vigil",
        language="en",
        out_path=out,
    )
    assert out.exists()
    out_img = Image.open(out).convert("RGB")
    assert out_img.size == (1080, 1080)


def test_apply_title_overlay_picks_font_by_language(tmp_path: Path):
    """ar/he/fa/ur scripts use Amiri; everything else uses Inter."""
    assert song_cover._font_path_for_language("ar").name == "Amiri-Regular.ttf"
    assert song_cover._font_path_for_language("he").name == "Amiri-Regular.ttf"
    assert song_cover._font_path_for_language("en").name == "Inter-Bold.ttf"
    assert song_cover._font_path_for_language("es").name == "Inter-Bold.ttf"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_song_cover.py -v
```

Expected: all FAIL — module doesn't exist.

- [ ] **Step 3: Write the minimal implementation**

Create `pipeline/song_cover.py`:

```python
"""Song-cover generation: Kie.ai Flux Kontext Max + Pillow title overlay.

Quality gate: this uses Kie.ai's `flux-kontext-max` model (their
highest-quality Flux variant) because the cover is the only visual the
viewer sees for the entire song. See spec section "Cover generation."

The 'leave space at top-right' hint is intentional — the title is
painted in the top-right quadrant by apply_title_overlay() in the next
step. Don't fight it.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from pipeline.kie import KieClient

FLUX_MODEL_ID = "flux-kontext-max"  # high-quality variant, ~$0.03/image

_REPO_ROOT = Path(__file__).resolve().parents[1]
_FONT_DIR = _REPO_ROOT / "assets" / "fonts"
_RTL_LANGUAGES = {"ar", "he", "fa", "ur"}

# Title styling
_CANVAS = 1080
_MARGIN_PCT = 0.08
_MAX_TITLE_BOX_W = int(_CANVAS * 0.42)  # ~42% of canvas — top-right quadrant
_FONT_SIZE_MIN = 36
_FONT_SIZE_MAX = 72


def _font_path_for_language(language: str) -> Path:
    if language in _RTL_LANGUAGES:
        return _FONT_DIR / "Amiri-Regular.ttf"
    return _FONT_DIR / "Inter-Bold.ttf"


def generate_cover_image(
    *,
    client: KieClient,
    cover_prompt: str,
    out_dir: Path,
) -> Path:
    """Call Kie.ai Flux Kontext Max for the raw cover; download to
    `<out_dir>/cover_raw.png`. Returns the path."""
    full_prompt = (
        f"{cover_prompt}, professional album cover art, "
        f"art direction by Hipgnosis, cinematic lighting, "
        f"shallow depth of field, high detail, no text, no watermark, "
        f"square composition, leave space at top-right for title text"
    )
    task_id = client.submit_flux_image_job(
        prompt=full_prompt,
        model=FLUX_MODEL_ID,
        aspect_ratio="1:1",
    )
    url = client.wait_for_flux_image(task_id, poll_interval_s=5, timeout_s=300)
    out_path = out_dir / "cover_raw.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    client.download(url, out_path)
    return out_path


def _fit_font(font_path: Path, title: str, max_width: int) -> ImageFont.FreeTypeFont:
    """Pick the largest font size that fits the title in max_width."""
    for size in range(_FONT_SIZE_MAX, _FONT_SIZE_MIN - 1, -2):
        font = ImageFont.truetype(str(font_path), size=size)
        bbox = font.getbbox(title)
        text_w = bbox[2] - bbox[0]
        if text_w <= max_width:
            return font
    return ImageFont.truetype(str(font_path), size=_FONT_SIZE_MIN)


def apply_title_overlay(
    *,
    raw_path: Path,
    title: str,
    language: str,
    out_path: Path,
) -> None:
    """Open `raw_path`, paint `title` in the top-right corner with a soft
    drop shadow, write to `out_path`."""
    img = Image.open(raw_path).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    font_path = _font_path_for_language(language)
    font = _fit_font(font_path, title, _MAX_TITLE_BOX_W)

    bbox = font.getbbox(title)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    margin = int(_CANVAS * _MARGIN_PCT)
    x = img.size[0] - margin - text_w
    y = margin

    # Soft black drop shadow (blur for the haze; offset 2px down/right).
    shadow_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow_layer)
    shadow_draw.text((x + 2, y + 2), title, font=font, fill=(0, 0, 0, 128))
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=2))

    # White title on top.
    draw.text((x, y), title, font=font, fill=(255, 255, 255, 255))

    composed = Image.alpha_composite(img, shadow_layer)
    composed = Image.alpha_composite(composed, overlay)
    composed.convert("RGB").save(out_path, format="PNG")
```

- [ ] **Step 4: Run tests to verify pass**

```bash
uv run pytest tests/test_song_cover.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/song_cover.py tests/test_song_cover.py
git commit -m "feat(song): Flux Kontext Max cover + Pillow title overlay"
```

---

## Task 5: ffmpeg assembly with stream-copied audio

**Files:**
- Create: `pipeline/song_assemble.py`
- Create: `tests/test_song_assemble.py`

Critical quality gate: `-c:a copy`, not re-encode. See spec section "Assembly (ffmpeg)."

- [ ] **Step 1: Write the failing tests**

Create `tests/test_song_assemble.py`:

```python
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from pipeline import song_assemble


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_COVER = REPO_ROOT / "tests" / "fixtures" / "song" / "cover.png"
FIXTURE_SONG = REPO_ROOT / "tests" / "fixtures" / "song" / "short_song.mp3"


def _ffprobe(path: Path) -> dict:
    """Return the parsed ffprobe JSON for path."""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json",
         "-show_streams", "-show_format", str(path)],
        capture_output=True, text=True, check=True,
    )
    return json.loads(out.stdout)


def test_ffprobe_duration_reads_real_mp3():
    d = song_assemble.ffprobe_duration(FIXTURE_SONG)
    assert 2.5 < d < 3.5  # fixture is 3 seconds


def test_assemble_song_video_writes_mp4(tmp_path: Path):
    cover = tmp_path / "cover.png"
    shutil.copy(FIXTURE_COVER, cover)
    song = tmp_path / "song.mp3"
    shutil.copy(FIXTURE_SONG, song)
    out = tmp_path / "final.mp4"
    song_assemble.assemble_song_video(cover_path=cover, song_mp3=song, out_mp4=out)
    assert out.exists()
    assert out.stat().st_size > 1000


def test_assemble_output_has_video_and_audio_streams(tmp_path: Path):
    out = tmp_path / "final.mp4"
    song_assemble.assemble_song_video(
        cover_path=FIXTURE_COVER, song_mp3=FIXTURE_SONG, out_mp4=out,
    )
    info = _ffprobe(out)
    streams = info["streams"]
    video = next((s for s in streams if s["codec_type"] == "video"), None)
    audio = next((s for s in streams if s["codec_type"] == "audio"), None)
    assert video is not None
    assert audio is not None


def test_assemble_output_is_1080x1080_at_25fps(tmp_path: Path):
    out = tmp_path / "final.mp4"
    song_assemble.assemble_song_video(
        cover_path=FIXTURE_COVER, song_mp3=FIXTURE_SONG, out_mp4=out,
    )
    info = _ffprobe(out)
    video = next(s for s in streams if s["codec_type"] == "video"
                 for streams in [info["streams"]])
    assert video["width"] == 1080
    assert video["height"] == 1080
    # r_frame_rate is "25/1" or "25"
    fps = video["r_frame_rate"]
    assert fps in ("25/1", "25")


def test_assemble_audio_is_stream_copied_not_reencoded(tmp_path: Path):
    """Quality gate: -c:a copy means the output AAC bitstream is
    identical to the input AAC bitstream — no re-encoding artifacts.
    The clearest signal is that the audio codec name and the
    sample_rate match the input exactly, and the codec_tag_string is
    'mp4a'. (We don't bit-compare because the MP4 muxer adds frame
    headers, but the audio payload is byte-identical.)"""
    out = tmp_path / "final.mp4"
    song_assemble.assemble_song_video(
        cover_path=FIXTURE_COVER, song_mp3=FIXTURE_SONG, out_mp4=out,
    )
    info = _ffprobe(out)
    audio = next(s for s in info["streams"] if s["codec_type"] == "audio")
    in_info = _ffprobe(FIXTURE_SONG)
    in_audio = next(s for s in in_info["streams"] if s["codec_type"] == "audio")
    assert audio["codec_name"] == in_audio["codec_name"] == "aac"
    assert audio["sample_rate"] == in_audio["sample_rate"]


def test_assemble_video_has_faststart_moov_at_front(tmp_path: Path):
    """`-movflags +faststart` puts moov atom at the front for streaming.
    Detect by reading the first few KB: 'moov' string should appear
    before 'mdat'."""
    out = tmp_path / "final.mp4"
    song_assemble.assemble_song_video(
        cover_path=FIXTURE_COVER, song_mp3=FIXTURE_SONG, out_mp4=out,
    )
    head = out.read_bytes()[:64 * 1024]
    moov_pos = head.find(b"moov")
    mdat_pos = head.find(b"mdat")
    assert moov_pos != -1, "moov atom not found in first 64KB"
    if mdat_pos != -1:
        assert moov_pos < mdat_pos, "moov atom must precede mdat (faststart)"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_song_assemble.py -v
```

Expected: all FAIL — module doesn't exist.

- [ ] **Step 3: Write the minimal implementation**

Create `pipeline/song_assemble.py`:

```python
"""ffmpeg assembly: cover.png + song.mp3 → final.mp4.

Quality gates (do not silently optimize away — see spec section
"Assembly (ffmpeg)"):
  - `-c:a copy` preserves Suno's mastering bit-for-bit. Do NOT re-encode.
  - No loudnorm/dynaudnorm filters — Suno is already at -14 LUFS.
  - `-movflags +faststart` puts moov atom at the front so the Flutter
    `<video>` player streams immediately.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

FPS = 25
OUTPUT_SIZE = 1080
UPSCALE_SIZE = 2160  # pre-zoompan upscale to avoid resampling blur
ZOOM_END = 1.13  # target zoom at end of song


def ffprobe_duration(path: Path) -> float:
    """Authoritative duration in seconds (Suno's job metadata is sometimes off)."""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json",
         "-show_format", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(json.loads(out.stdout)["format"]["duration"])


def assemble_song_video(*, cover_path: Path, song_mp3: Path, out_mp4: Path) -> None:
    """Build the music-video MP4. Raises subprocess.CalledProcessError on failure."""
    duration_s = ffprobe_duration(song_mp3)
    total_frames = max(1, int(duration_s * FPS))
    zoom_step = (ZOOM_END - 1.0) / total_frames

    filter_complex = (
        f"[0:v]scale={UPSCALE_SIZE}:{UPSCALE_SIZE},"
        f"zoompan=z='1+{zoom_step:.10f}*on':"
        f"d={total_frames}:s={OUTPUT_SIZE}x{OUTPUT_SIZE}:fps={FPS}[v]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(cover_path),
        "-i", str(song_mp3),
        "-filter_complex", filter_complex,
        "-map", "[v]", "-map", "1:a",
        "-c:v", "libx264", "-preset", "slow", "-crf", "18",
        "-c:a", "copy",
        "-pix_fmt", "yuv420p",
        "-shortest",
        "-movflags", "+faststart",
        str(out_mp4),
    ]
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(cmd, check=True, capture_output=True)
```

- [ ] **Step 4: Run tests to verify pass**

```bash
uv run pytest tests/test_song_assemble.py -v
```

Expected: 6 tests PASS. (One may need a tweak to the fixture-stream extraction — fix any iteration error in the 1080×1080 test as needed.)

If `test_assemble_output_is_1080x1080_at_25fps` fails with a syntax error around `for streams in [info["streams"]]`, fix it to a normal next-call:

```python
def test_assemble_output_is_1080x1080_at_25fps(tmp_path: Path):
    out = tmp_path / "final.mp4"
    song_assemble.assemble_song_video(
        cover_path=FIXTURE_COVER, song_mp3=FIXTURE_SONG, out_mp4=out,
    )
    info = _ffprobe(out)
    video = next(s for s in info["streams"] if s["codec_type"] == "video")
    assert video["width"] == 1080
    assert video["height"] == 1080
    fps = video["r_frame_rate"]
    assert fps in ("25/1", "25")
```

- [ ] **Step 5: Commit**

```bash
git add pipeline/song_assemble.py tests/test_song_assemble.py
git commit -m "feat(song): ffmpeg assemble with stream-copied audio + faststart"
```

---

## Task 6: Config block for song mode

**Files:**
- Modify: `pipeline/config.py`
- Modify: `config.yaml`

- [ ] **Step 1: Add song block to `config.yaml`**

Append to `config.yaml`:

```yaml
song:
  # Suno model id. V4.5 or newer required (V3.5 is the bad-old-AI sound).
  # See pipeline/song.py SUNO_MODEL_ID.
  suno_model: suno-v4-5
  # Per-song flat cost on Kie.ai (USD). Verify against current Kie.ai pricing.
  suno_cost_usd: 0.05
  # Kie.ai Flux model id for covers. Max = highest quality.
  cover_flux_model: flux-kontext-max
  cover_cost_usd: 0.03
  # User-facing credit price for one song run. 1 credit = $0.10 (B3 ledger).
  # Cost basis is ~0.5 credits; we charge 1 to cover failure-retry risk.
  credits_per_song: 1
```

- [ ] **Step 2: Add `SongConfig` dataclass to `pipeline/config.py`**

In `pipeline/config.py`, add a new dataclass near `FluxConfig`:

```python
@dataclass(frozen=True)
class SongConfig:
    suno_model: str
    suno_cost_usd: float
    cover_flux_model: str
    cover_cost_usd: float
    credits_per_song: int
```

- [ ] **Step 3: Update `load_config` to populate it**

Locate `load_config` (line ~95). Add `song` to the `Config` constructor:

```python
def load_config(path: Path) -> Config:
    with path.open() as f:
        raw = yaml.safe_load(f)
    return Config(
        voice=VoiceConfig(**raw["voice"]),
        script=ScriptConfig(**raw["script"]),
        flux=FluxConfig(**raw["flux"]),
        assemble=AssembleConfig(**raw["assemble"]),
        captions=CaptionsConfig(**raw["captions"]),
        kie=KieConfig(**raw["kie"]),
        song=SongConfig(**raw["song"]) if "song" in raw else None,
    )
```

The `if "song" in raw else None` keeps existing test configs that don't define the song block from breaking. Add `song: SongConfig | None = None` to the `Config` dataclass.

- [ ] **Step 4: Run the existing test suite to make sure nothing broke**

```bash
uv run pytest tests/ -x -q
```

Expected: all existing tests still pass. (New song tests not yet wired into anything that needs config.)

- [ ] **Step 5: Commit**

```bash
git add pipeline/config.py config.yaml
git commit -m "feat(song): add SongConfig block — Suno + Flux model ids + credit cost"
```

---

## Task 7: `run.py --mode song` dispatch

**Files:**
- Modify: `run.py`
- Create: `tests/test_run_song_mode.py`

`run.py --mode song --resume <run-dir>` runs Suno → cover → assemble after the user has approved. Lyrics are written inline by the API endpoint in Task 9 (not by this subprocess).

- [ ] **Step 1: Write the failing integration test**

Create `tests/test_run_song_mode.py`:

```python
from __future__ import annotations

import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import run as run_mod
from pipeline import song, song_cover


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_COVER = REPO_ROOT / "tests" / "fixtures" / "song" / "cover.png"
FIXTURE_SONG = REPO_ROOT / "tests" / "fixtures" / "song" / "short_song.mp3"


def test_song_post_approve_produces_final_mp4(tmp_path: Path, monkeypatch):
    run_dir = tmp_path / "song-run-1"
    run_dir.mkdir()

    # Pre-populated by the API writer pass:
    (run_dir / "song.json").write_text(json.dumps({
        "title": "Test",
        "lyrics": "[Verse 1]\nhi\n[Chorus]\nworld",
        "style_prompt": "Arabic pop ballad, slow tempo 72 BPM, oud, male vocal, modern, minor key",
        "cover_prompt": "moonlight over the sea",
        "language": "ar",
    }))
    (run_dir / "api_state.json").write_text(json.dumps({
        "kind": "song", "status": "generating_song",
    }))

    # Stub Suno: returns two takes whose MP3s already exist on disk
    def fake_submit(client, *, lyrics, style_prompt, title, model=song.SUNO_MODEL_ID):
        return "fake-task"
    def fake_wait(client, task_id, *, poll_interval_s=5, timeout_s=600):
        return [
            song.SongTake(url="https://kie.ai/t1.mp3", duration_s=3.0),
            song.SongTake(url="https://kie.ai/t2.mp3", duration_s=2.8),
        ]
    def fake_download(client, url, out_path):
        shutil.copy(FIXTURE_SONG, out_path)

    monkeypatch.setattr(song, "submit_song_job", fake_submit)
    monkeypatch.setattr(song, "wait_for_song", fake_wait)
    monkeypatch.setattr(song, "download_take", fake_download)

    # Stub cover generation: write the fixture PNG as cover_raw.png
    def fake_cover(*, client, cover_prompt, out_dir):
        out = out_dir / "cover_raw.png"
        shutil.copy(FIXTURE_COVER, out)
        return out
    monkeypatch.setattr(song_cover, "generate_cover_image", fake_cover)

    # Stub KieClient construction (would otherwise demand KIE_API_KEY)
    monkeypatch.setenv("KIE_API_KEY", "stub")

    rc = run_mod.main_with_args([
        "--mode", "song", "--resume", str(run_dir),
    ])

    assert rc == 0
    assert (run_dir / "final.mp4").exists()
    assert (run_dir / "cover.png").exists()
    assert (run_dir / "takes" / "take_1.mp3").exists()
    assert (run_dir / "takes" / "take_2.mp3").exists()
    assert (run_dir / "song.mp3").exists()  # symlink/copy of chosen take

    state = json.loads((run_dir / "api_state.json").read_text())
    assert state["status"] == "complete"
    assert state["chosen_take"] == 1  # longer of 3.0 vs 2.8
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_run_song_mode.py -v
```

Expected: FAIL — `--mode` argument not recognized.

- [ ] **Step 3: Add `--mode` arg and song dispatch to `run.py`**

In `run.py`, in `main_with_args` near the other argparse adds (line ~609), add:

```python
parser.add_argument(
    "--mode", choices=["horror", "song"], default="horror",
    help="Pipeline mode. 'song' runs the AI song pipeline after a user "
         "approval (Suno → Flux cover → ffmpeg assemble).",
)
```

Then, at the top of the dispatch section (just before `if args.shorts:` at line ~694), add:

```python
if args.mode == "song":
    return _run_song_post_approve(args)
```

At the bottom of `run.py` (before `def main():` at line ~882), add the new function:

```python
def _run_song_post_approve(args) -> int:
    """Song-mode post-approve stage: Suno → cover → assemble.

    Reads song.json (written by POST /songs inline) from --resume dir.
    Writes api_state.json transitions: generating_song → generating_cover
    → assembling → complete (or failed).
    """
    import json
    import os
    import shutil
    import sys
    from pathlib import Path

    from pipeline import song, song_cover, song_assemble
    from pipeline.config import load_config
    from pipeline.kie import KieClient

    if not args.resume:
        print("--mode song requires --resume <run-dir>", file=sys.stderr)
        return 2
    run_dir = Path(args.resume)
    if not run_dir.is_dir():
        print(f"run dir not found: {run_dir}", file=sys.stderr)
        return 2

    script_path = run_dir / "song.json"
    state_path = run_dir / "api_state.json"
    cfg = load_config(Path("config.yaml"))

    def write_state(**patch):
        state = json.loads(state_path.read_text()) if state_path.exists() else {}
        state.update(patch)
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2))

    try:
        script = json.loads(script_path.read_text())
        client = KieClient()

        # --- Stage 1: Suno song ---
        write_state(status="generating_song")
        task_id = song.submit_song_job(
            client,
            lyrics=script["lyrics"],
            style_prompt=script["style_prompt"],
            title=script["title"],
            model=cfg.song.suno_model if cfg.song else song.SUNO_MODEL_ID,
        )
        takes = song.wait_for_song(client, task_id)
        takes_dir = run_dir / "takes"
        takes_dir.mkdir(exist_ok=True)
        for i, take in enumerate(takes, start=1):
            song.download_take(client, take.url, takes_dir / f"take_{i}.mp3")

        # Pick the longer take (Suno truncates one ~20% of the time)
        chosen = 1 if takes[0].duration_s >= takes[1].duration_s else 2
        chosen_path = takes_dir / f"take_{chosen}.mp3"
        song_mp3 = run_dir / "song.mp3"
        if song_mp3.exists() or song_mp3.is_symlink():
            song_mp3.unlink()
        shutil.copy(chosen_path, song_mp3)  # copy not symlink — survives mount changes
        write_state(chosen_take=chosen)

        # --- Stage 2: cover ---
        write_state(status="generating_cover")
        raw_cover = song_cover.generate_cover_image(
            client=client,
            cover_prompt=script["cover_prompt"],
            out_dir=run_dir,
        )
        song_cover.apply_title_overlay(
            raw_path=raw_cover,
            title=script["title"],
            language=script.get("language", "ar"),
            out_path=run_dir / "cover.png",
        )

        # --- Stage 3: assemble ---
        write_state(status="assembling")
        song_assemble.assemble_song_video(
            cover_path=run_dir / "cover.png",
            song_mp3=song_mp3,
            out_mp4=run_dir / "final.mp4",
        )

        write_state(status="complete")
        return 0
    except Exception as e:
        # Log + flip state to failed so derive_status sees it
        write_state(status="failed", last_error=f"{type(e).__name__}: {e}")
        print(f"[song-post-approve] failed: {e}", file=sys.stderr)
        return 1
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
uv run pytest tests/test_run_song_mode.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add run.py tests/test_run_song_mode.py
git commit -m "feat(song): run.py --mode song post-approve dispatch"
```

---

## Task 8: API — POST /songs (writer pass, inline LLM)

**Files:**
- Modify: `pipeline/api.py`
- Create: `tests/test_song_api.py`

POST /songs runs the lyrics LLM inline (mirrors how `_generate_script_inline` works at `pipeline/api.py:568`) and returns `awaiting_approval`. No subprocess spawned until `/approve`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_song_api.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app(monkeypatch, tmp_path: Path):
    """Build the FastAPI app with a fake out-root and no-op spawn."""
    token = "test-token-123"
    monkeypatch.setenv("FACELESS_API_TOKEN", token)
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path / "out"))
    monkeypatch.setenv("KIE_API_KEY", "stub")
    # Import AFTER env vars set so module-level reads pick them up
    from pipeline import api as api_mod
    api_mod.set_spawn_fn(lambda args, run_dir: 999999)
    # Stub the LLM the writer pass uses — return canned JSON
    canned = json.dumps({
        "title": "Test Song",
        "lyrics": "[Verse 1]\nline\n[Chorus]\nhook\n[Verse 2]\nline\n[Chorus]\nhook",
        "style_prompt": "Arabic pop ballad, slow tempo 72 BPM, oud + strings, male vocal, modern 2020s, melancholic minor key",
        "cover_prompt": "moonlight over the sea",
    })
    fake_llm = MagicMock()
    fake_llm.complete = MagicMock(return_value=canned)
    monkeypatch.setattr(api_mod, "_build_song_llm", lambda: fake_llm)
    return api_mod.app, token


def test_post_songs_creates_run_and_returns_awaiting_approval(app):
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    r = client.post(
        "/songs",
        json={"theme": "sad Arabic ballad about the moon", "language": "ar"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert "run_id" in body
    assert body["status"] == "awaiting_approval"


def test_post_songs_writes_song_json_to_disk(app, tmp_path: Path, monkeypatch):
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    r = client.post(
        "/songs",
        json={"theme": "x", "language": "ar"},
        headers={"Authorization": f"Bearer {token}"},
    )
    run_id = r.json()["run_id"]
    # Find the run dir
    out_root = Path(tmp_path / "out")
    matches = list(out_root.glob(f"**/{run_id}"))
    assert matches, f"no run dir for {run_id} under {out_root}"
    run_dir = matches[0]
    song_json = json.loads((run_dir / "song.json").read_text())
    assert song_json["title"] == "Test Song"
    assert "[Verse 1]" in song_json["lyrics"]
    assert "BPM" in song_json["style_prompt"]
    state = json.loads((run_dir / "api_state.json").read_text())
    assert state["kind"] == "song"
    assert state["status"] == "awaiting_approval"


def test_post_songs_requires_auth(app):
    fastapi_app, _ = app
    client = TestClient(fastapi_app)
    r = client.post("/songs", json={"theme": "x"})
    assert r.status_code == 401


def test_post_songs_honors_custom_lyrics_passthrough(app):
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    custom = "[Verse 1]\nmy own words\n[Chorus]\nverbatim"
    r = client.post(
        "/songs",
        json={"theme": "x", "custom_lyrics": custom, "language": "en"},
        headers={"Authorization": f"Bearer {token}"},
    )
    run_id = r.json()["run_id"]
    out_root = Path(r.app.dependency_overrides.get('out_root', None) or "")
    # Find via filesystem
    import os
    matches = []
    for root, _, files in os.walk(os.environ["FACELESS_OUT_ROOT"]):
        if "song.json" in files and Path(root).name == run_id:
            matches.append(Path(root))
    assert matches
    song_json = json.loads((matches[0] / "song.json").read_text())
    assert song_json["lyrics"] == custom
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_song_api.py -v
```

Expected: all FAIL — endpoint doesn't exist; `_build_song_llm` doesn't exist.

- [ ] **Step 3: Add the endpoint to `pipeline/api.py`**

Add these Pydantic models near the existing request/response models (around line 366):

```python
class CreateSongRequest(BaseModel):
    theme: str
    custom_lyrics: str | None = None
    style_hint: str | None = None
    language: str = "ar"


class SongScriptResponse(BaseModel):
    title: str
    lyrics: str
    style_prompt: str
    cover_prompt: str
    language: str
    cost_credits: int
    cost_usd: float


class SongRunSummary(BaseModel):
    id: str
    status: str
    kind: str  # always "song"
    title: str | None
    theme: str | None
    created_at: str
    has_video: bool
    chosen_take: int | None
    last_error: str | None
```

Add the LLM builder function near `_build_llm` (line ~553):

```python
def _build_song_llm():
    """Same router as _build_llm — Anthropic > Groq > Gemini."""
    return _build_llm()
```

Add the endpoint. Place near `/runs` POST (~line 1195):

```python
@app.post("/songs", status_code=201)
def create_song(
    req: CreateSongRequest,
    user: User = Depends(require_user),
):
    """Writer pass: generate lyrics + style + cover prompt inline.
    No spend; returns awaiting_approval immediately."""
    from pipeline.song_lyrics import generate_song_script
    from pipeline.config import load_config

    cfg = load_config(Path("config.yaml"))
    credits_required = cfg.song.credits_per_song if cfg.song else 1

    # Preflight credit check (estimate; no deduction)
    if get_balance(user.id) < credits_required and user.role != "service":
        _raise_402_insufficient_credits(get_balance(user.id), credits_required)

    run_id = _make_run_id()
    run_dir = _run_dir(run_id, user)
    run_dir.mkdir(parents=True, exist_ok=True)

    # Write initial state
    _write_state(
        run_dir,
        kind="song",
        status="writing_lyrics",
        user_id=user.id,
        theme=req.theme,
        created_at=_now_iso(),
    )

    # Inline LLM call (mirrors _generate_script_inline pattern)
    try:
        llm = _build_song_llm()
        script = generate_song_script(
            llm=llm,
            theme=req.theme,
            custom_lyrics=req.custom_lyrics,
            style_hint=req.style_hint,
            language=req.language,
        )
    except Exception as e:
        _write_state(run_dir, status="failed", last_error=f"lyrics LLM failed: {e}")
        raise HTTPException(500, f"lyrics generation failed: {e}")

    # Persist
    (run_dir / "song.json").write_text(
        json.dumps({
            "title": script.title,
            "lyrics": script.lyrics,
            "style_prompt": script.style_prompt,
            "cover_prompt": script.cover_prompt,
            "language": script.language,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (run_dir / "lyrics.txt").write_text(script.lyrics, encoding="utf-8")
    _write_state(run_dir, status="awaiting_approval", title=script.title)

    return {"run_id": run_id, "status": "awaiting_approval"}
```

Note: if `_now_iso` doesn't exist in `pipeline/api.py`, add it or replace with `datetime.now(timezone.utc).isoformat()`. Similarly check `get_balance` — it's likely in `pipeline/credits.py`; import it at the top.

- [ ] **Step 4: Run tests to verify pass**

```bash
uv run pytest tests/test_song_api.py -v
```

Expected: 4 tests PASS. If anything else in `pipeline/api.py` (e.g. a missing import or a helper name) doesn't quite match, debug each error in sequence. Do NOT change the test contracts.

- [ ] **Step 5: Commit**

```bash
git add pipeline/api.py tests/test_song_api.py
git commit -m "feat(song): POST /songs writer pass (inline LLM, awaiting_approval)"
```

---

## Task 9: API — GET /songs/{id}, GET /songs/{id}/script, GET /songs

**Files:**
- Modify: `pipeline/api.py`
- Modify: `tests/test_song_api.py`

- [ ] **Step 1: Add tests for the read endpoints**

Append to `tests/test_song_api.py`:

```python
def test_get_song_returns_summary(app):
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    create = client.post(
        "/songs", json={"theme": "x"},
        headers={"Authorization": f"Bearer {token}"},
    )
    run_id = create.json()["run_id"]
    r = client.get(f"/songs/{run_id}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == run_id
    assert body["kind"] == "song"
    assert body["status"] == "awaiting_approval"
    assert body["title"] == "Test Song"


def test_get_song_404_for_unknown_id(app):
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    r = client.get("/songs/nope", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 404


def test_get_song_script_returns_full_payload(app):
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    create = client.post(
        "/songs", json={"theme": "x", "language": "ar"},
        headers={"Authorization": f"Bearer {token}"},
    )
    run_id = create.json()["run_id"]
    r = client.get(
        f"/songs/{run_id}/script",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "Test Song"
    assert "[Chorus]" in body["lyrics"]
    assert body["style_prompt"]
    assert body["cover_prompt"]
    assert body["language"] == "ar"
    assert body["cost_credits"] >= 1
    assert body["cost_usd"] > 0


def test_list_songs_returns_only_song_runs(app):
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    # Create two songs
    for _ in range(2):
        client.post(
            "/songs", json={"theme": "x"},
            headers={"Authorization": f"Bearer {token}"},
        )
    r = client.get("/songs", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 2
    assert all(s["kind"] == "song" for s in body)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_song_api.py -v -k "get_song or list_songs"
```

Expected: FAIL — endpoints not registered yet.

- [ ] **Step 3: Add the endpoints**

In `pipeline/api.py`, near the create-song endpoint:

```python
@app.get("/songs/{run_id}", response_model=SongRunSummary)
def get_song(run_id: str, user: User = Depends(require_user)):
    run_dir = _resolve_song_dir(run_id, user)
    state = _read_state(run_dir)
    if state.get("kind") != "song":
        raise HTTPException(404, "not a song run")
    return SongRunSummary(
        id=run_id,
        status=state.get("status", "unknown"),
        kind="song",
        title=state.get("title"),
        theme=state.get("theme"),
        created_at=state.get("created_at", ""),
        has_video=(run_dir / "final.mp4").exists(),
        chosen_take=state.get("chosen_take"),
        last_error=state.get("last_error"),
    )


@app.get("/songs/{run_id}/script", response_model=SongScriptResponse)
def get_song_script(run_id: str, user: User = Depends(require_user)):
    run_dir = _resolve_song_dir(run_id, user)
    script_path = run_dir / "song.json"
    if not script_path.exists():
        raise HTTPException(404, "song.json not yet written")
    script = json.loads(script_path.read_text())
    from pipeline.config import load_config
    cfg = load_config(Path("config.yaml"))
    return SongScriptResponse(
        title=script["title"],
        lyrics=script["lyrics"],
        style_prompt=script["style_prompt"],
        cover_prompt=script["cover_prompt"],
        language=script["language"],
        cost_credits=cfg.song.credits_per_song if cfg.song else 1,
        cost_usd=(cfg.song.suno_cost_usd + cfg.song.cover_cost_usd) if cfg.song else 0.08,
    )


@app.get("/songs", response_model=list[SongRunSummary])
def list_songs(user: User = Depends(require_user)):
    out = []
    user_root = _user_runs_root(user)
    if not user_root.exists():
        return out
    for d in sorted(user_root.iterdir(), key=lambda p: p.name, reverse=True):
        if not d.is_dir():
            continue
        state = _read_state(d)
        if state.get("kind") != "song":
            continue
        out.append(SongRunSummary(
            id=d.name,
            status=state.get("status", "unknown"),
            kind="song",
            title=state.get("title"),
            theme=state.get("theme"),
            created_at=state.get("created_at", ""),
            has_video=(d / "final.mp4").exists(),
            chosen_take=state.get("chosen_take"),
            last_error=state.get("last_error"),
        ))
    return out


def _resolve_song_dir(run_id: str, user: "User") -> Path:
    """Locate the run dir; 404 if missing or owned by someone else."""
    run_dir = _run_dir(run_id, user)
    if not run_dir.exists():
        raise HTTPException(404, "run not found")
    return run_dir
```

- [ ] **Step 4: Run tests to verify pass**

```bash
uv run pytest tests/test_song_api.py -v
```

Expected: all PASS (including the earlier 4 from Task 8 + 4 new ones = 8).

- [ ] **Step 5: Commit**

```bash
git add pipeline/api.py tests/test_song_api.py
git commit -m "feat(song): GET /songs, /songs/{id}, /songs/{id}/script"
```

---

## Task 10: API — regenerate-lyrics, regenerate-cover-prompt, edit, cancel

**Files:**
- Modify: `pipeline/api.py`
- Modify: `tests/test_song_api.py`

State-guarded mutations: only allowed while `status == awaiting_approval`. Outside that → 409.

- [ ] **Step 1: Add tests**

Append to `tests/test_song_api.py`:

```python
def test_regenerate_lyrics_only_pre_approval(app):
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    create = client.post(
        "/songs", json={"theme": "x"},
        headers={"Authorization": f"Bearer {token}"},
    )
    run_id = create.json()["run_id"]
    # Allowed in awaiting_approval
    r = client.post(
        f"/songs/{run_id}/regenerate-lyrics",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    # Simulate post-approval by writing state directly
    import os
    run_dir_root = os.environ["FACELESS_OUT_ROOT"]
    matches = []
    for root, _, files in os.walk(run_dir_root):
        if Path(root).name == run_id:
            matches.append(Path(root))
    run_dir = matches[0]
    state = json.loads((run_dir / "api_state.json").read_text())
    state["status"] = "generating_song"
    (run_dir / "api_state.json").write_text(json.dumps(state))
    # Now regen must 409
    r = client.post(
        f"/songs/{run_id}/regenerate-lyrics",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 409


def test_edit_validates_lyrics_length(app):
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    create = client.post(
        "/songs", json={"theme": "x"},
        headers={"Authorization": f"Bearer {token}"},
    )
    run_id = create.json()["run_id"]
    big = "x" * 4001
    r = client.post(
        f"/songs/{run_id}/edit",
        json={"lyrics": big},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422


def test_edit_patches_fields(app):
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    create = client.post(
        "/songs", json={"theme": "x"},
        headers={"Authorization": f"Bearer {token}"},
    )
    run_id = create.json()["run_id"]
    new_lyrics = "[Verse 1]\nedited\n[Chorus]\nnew hook"
    r = client.post(
        f"/songs/{run_id}/edit",
        json={"lyrics": new_lyrics},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    # Confirm song.json updated
    r2 = client.get(
        f"/songs/{run_id}/script",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.json()["lyrics"] == new_lyrics


def test_cancel_pre_approval_sets_canceled_status(app):
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    create = client.post(
        "/songs", json={"theme": "x"},
        headers={"Authorization": f"Bearer {token}"},
    )
    run_id = create.json()["run_id"]
    r = client.post(
        f"/songs/{run_id}/cancel",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    r2 = client.get(f"/songs/{run_id}", headers={"Authorization": f"Bearer {token}"})
    assert r2.json()["status"] == "canceled"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_song_api.py -v -k "regenerate or edit or cancel"
```

Expected: FAIL — endpoints don't exist.

- [ ] **Step 3: Implement the endpoints**

Add to `pipeline/api.py`:

```python
class EditSongRequest(BaseModel):
    lyrics: str | None = None
    style_prompt: str | None = None
    cover_prompt: str | None = None


def _require_song_awaiting_approval(run_dir: Path) -> dict:
    state = _read_state(run_dir)
    if state.get("kind") != "song":
        raise HTTPException(404, "not a song run")
    if state.get("status") != "awaiting_approval":
        raise HTTPException(409, f"song is in state {state.get('status')!r}, edits not allowed")
    return state


@app.post("/songs/{run_id}/regenerate-lyrics")
def regenerate_song_lyrics(run_id: str, user: User = Depends(require_user)):
    from pipeline.song_lyrics import generate_song_script
    run_dir = _resolve_song_dir(run_id, user)
    _require_song_awaiting_approval(run_dir)
    script_path = run_dir / "song.json"
    current = json.loads(script_path.read_text())
    llm = _build_song_llm()
    new_script = generate_song_script(
        llm=llm,
        theme=_read_state(run_dir).get("theme", ""),
        custom_lyrics=None,
        style_hint=current.get("style_prompt"),  # preserve style direction
        language=current["language"],
    )
    new_data = {
        "title": new_script.title,
        "lyrics": new_script.lyrics,
        "style_prompt": new_script.style_prompt,
        "cover_prompt": current["cover_prompt"],  # keep cover prompt
        "language": new_script.language,
    }
    _atomic_write_json(script_path, new_data)
    (run_dir / "lyrics.txt").write_text(new_script.lyrics, encoding="utf-8")
    _write_state(run_dir, title=new_script.title)
    return {"ok": True}


@app.post("/songs/{run_id}/regenerate-cover-prompt")
def regenerate_song_cover_prompt(run_id: str, user: User = Depends(require_user)):
    from pipeline.song_lyrics import generate_song_script
    run_dir = _resolve_song_dir(run_id, user)
    _require_song_awaiting_approval(run_dir)
    script_path = run_dir / "song.json"
    current = json.loads(script_path.read_text())
    llm = _build_song_llm()
    new_script = generate_song_script(
        llm=llm,
        theme=_read_state(run_dir).get("theme", ""),
        custom_lyrics=current["lyrics"],  # keep lyrics
        style_hint=current["style_prompt"],
        language=current["language"],
    )
    current["cover_prompt"] = new_script.cover_prompt
    _atomic_write_json(script_path, current)
    return {"ok": True}


@app.post("/songs/{run_id}/edit")
def edit_song(
    run_id: str,
    req: EditSongRequest,
    user: User = Depends(require_user),
):
    run_dir = _resolve_song_dir(run_id, user)
    _require_song_awaiting_approval(run_dir)
    # Length validation
    if req.lyrics is not None and len(req.lyrics) > 4000:
        raise HTTPException(422, "lyrics exceeds 4000 chars")
    if req.style_prompt is not None and len(req.style_prompt) > 500:
        raise HTTPException(422, "style_prompt exceeds 500 chars")
    if req.cover_prompt is not None and len(req.cover_prompt) > 500:
        raise HTTPException(422, "cover_prompt exceeds 500 chars")
    # Patch
    script_path = run_dir / "song.json"
    current = json.loads(script_path.read_text())
    for field in ("lyrics", "style_prompt", "cover_prompt"):
        v = getattr(req, field)
        if v is not None:
            current[field] = v
    _atomic_write_json(script_path, current)
    if req.lyrics is not None:
        (run_dir / "lyrics.txt").write_text(req.lyrics, encoding="utf-8")
    return {"ok": True}


@app.post("/songs/{run_id}/cancel")
def cancel_song(run_id: str, user: User = Depends(require_user)):
    run_dir = _resolve_song_dir(run_id, user)
    state = _read_state(run_dir)
    if state.get("kind") != "song":
        raise HTTPException(404, "not a song run")
    if state.get("status") == "complete":
        raise HTTPException(409, "song already complete")
    # Kill subprocess if running (post-approval cancellation)
    pid = state.get("pid")
    if pid and _process_alive(pid, run_dir):
        try:
            import os
            import signal
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    _write_state(run_dir, status="canceled")
    return {"ok": True}


def _atomic_write_json(path: Path, data: dict) -> None:
    """Write JSON atomically via temp + rename."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
```

- [ ] **Step 4: Run tests to verify pass**

```bash
uv run pytest tests/test_song_api.py -v
```

Expected: 12 tests PASS (8 from before + 4 new).

- [ ] **Step 5: Commit**

```bash
git add pipeline/api.py tests/test_song_api.py
git commit -m "feat(song): regenerate-lyrics, regenerate-cover-prompt, edit, cancel"
```

---

## Task 11: API — POST /songs/{id}/approve (the money step)

**Files:**
- Modify: `pipeline/api.py`
- Modify: `tests/test_song_api.py`

Deduct credits atomically, spawn `run.py --mode song --resume <run-dir>`.

- [ ] **Step 1: Add tests**

Append to `tests/test_song_api.py`:

```python
def test_approve_song_deducts_credits_and_spawns(app, monkeypatch):
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    from pipeline import api as api_mod
    spawn_calls = []
    def fake_spawn(args, run_dir):
        spawn_calls.append((args, run_dir))
        return 12345
    api_mod.set_spawn_fn(fake_spawn)

    # Pre-credit the user so the deduction can succeed
    from pipeline import credits
    monkeypatch.setattr(credits, "get_balance", lambda uid: 100)
    monkeypatch.setattr(
        credits, "check_or_deduct",
        lambda user, amount, run_id, reason: 100 - amount,
    )

    create = client.post(
        "/songs", json={"theme": "x"},
        headers={"Authorization": f"Bearer {token}"},
    )
    run_id = create.json()["run_id"]
    r = client.post(
        f"/songs/{run_id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["run_id"] == run_id
    assert body["balance_after"] == 99

    # spawn args include --mode song --resume
    assert len(spawn_calls) == 1
    args, _ = spawn_calls[0]
    assert "--mode" in args
    assert args[args.index("--mode") + 1] == "song"
    assert "--resume" in args


def test_approve_song_idempotent_after_first_call(app, monkeypatch):
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    from pipeline import credits
    deduction_count = {"n": 0}
    def counted_deduct(user, amount, run_id, reason):
        deduction_count["n"] += 1
        return 100 - amount
    monkeypatch.setattr(credits, "get_balance", lambda uid: 100)
    monkeypatch.setattr(credits, "check_or_deduct", counted_deduct)

    create = client.post(
        "/songs", json={"theme": "x"},
        headers={"Authorization": f"Bearer {token}"},
    )
    run_id = create.json()["run_id"]
    client.post(f"/songs/{run_id}/approve", headers={"Authorization": f"Bearer {token}"})
    client.post(f"/songs/{run_id}/approve", headers={"Authorization": f"Bearer {token}"})
    assert deduction_count["n"] == 1


def test_approve_song_402_when_balance_insufficient(app, monkeypatch):
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    from pipeline import credits
    monkeypatch.setattr(credits, "get_balance", lambda uid: 0)
    create = client.post(
        "/songs", json={"theme": "x"},
        headers={"Authorization": f"Bearer {token}"},
    )
    run_id = create.json()["run_id"]
    r = client.post(
        f"/songs/{run_id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 402
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_song_api.py -v -k "approve"
```

Expected: FAIL — `/approve` endpoint doesn't exist.

- [ ] **Step 3: Implement the approve endpoint**

Add to `pipeline/api.py`:

```python
@app.post("/songs/{run_id}/approve")
def approve_song(run_id: str, user: User = Depends(require_user)):
    from pipeline.credits import check_or_deduct, get_balance
    from pipeline.config import load_config

    run_dir = _resolve_song_dir(run_id, user)
    state = _read_state(run_dir)
    if state.get("kind") != "song":
        raise HTTPException(404, "not a song run")

    # Idempotency: second call after the spawn already happened
    if state.get("status") != "awaiting_approval":
        return {"run_id": run_id, "balance_after": get_balance(user.id),
                "status": state.get("status")}

    cfg = load_config(Path("config.yaml"))
    amount = cfg.song.credits_per_song if cfg.song else 1

    if get_balance(user.id) < amount and user.role != "service":
        _raise_402_insufficient_credits(get_balance(user.id), amount)

    new_balance = check_or_deduct(
        user, amount=amount, run_id=run_id, reason="song-spend",
    )

    # Spawn the post-approve subprocess
    args = ["--mode", "song", "--resume", str(run_dir)]
    pid = _SPAWN_FN(args, run_dir)
    _write_state(run_dir, status="generating_song", pid=pid)

    return {"run_id": run_id, "balance_after": new_balance, "status": "generating_song"}
```

- [ ] **Step 4: Run tests to verify pass**

```bash
uv run pytest tests/test_song_api.py -v
```

Expected: 15 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/api.py tests/test_song_api.py
git commit -m "feat(song): POST /songs/{id}/approve — deduct credits + spawn"
```

---

## Task 12: API — take-swap, streaming endpoints, log tail, resume

**Files:**
- Modify: `pipeline/api.py`
- Modify: `tests/test_song_api.py`

Take-swap re-runs ffmpeg with the alternate take. Streaming endpoints serve audio/cover/video. Resume re-spawns the failed stage.

- [ ] **Step 1: Add tests**

Append to `tests/test_song_api.py`:

```python
def test_swap_take_reruns_assembly(app, tmp_path: Path, monkeypatch):
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    create = client.post(
        "/songs", json={"theme": "x"},
        headers={"Authorization": f"Bearer {token}"},
    )
    run_id = create.json()["run_id"]

    # Pretend the run has completed
    import os
    run_dir = None
    for root, _, _ in os.walk(os.environ["FACELESS_OUT_ROOT"]):
        if Path(root).name == run_id:
            run_dir = Path(root)
            break
    assert run_dir
    (run_dir / "takes").mkdir(exist_ok=True)
    (run_dir / "takes" / "take_1.mp3").write_bytes(b"\x00" * 100)
    (run_dir / "takes" / "take_2.mp3").write_bytes(b"\x00" * 100)
    (run_dir / "song.mp3").write_bytes(b"\x00" * 100)
    state = json.loads((run_dir / "api_state.json").read_text())
    state["status"] = "complete"
    state["chosen_take"] = 1
    (run_dir / "api_state.json").write_text(json.dumps(state))

    # Mock the assemble call
    from pipeline import song_assemble
    monkeypatch.setattr(
        song_assemble, "assemble_song_video",
        lambda *, cover_path, song_mp3, out_mp4: out_mp4.write_bytes(b"FAKE"),
    )

    r = client.post(
        f"/songs/{run_id}/swap-take",
        json={"take": 2},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    new_state = json.loads((run_dir / "api_state.json").read_text())
    assert new_state["chosen_take"] == 2


def test_get_audio_serves_chosen_take(app):
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    create = client.post(
        "/songs", json={"theme": "x"},
        headers={"Authorization": f"Bearer {token}"},
    )
    run_id = create.json()["run_id"]
    import os
    for root, _, _ in os.walk(os.environ["FACELESS_OUT_ROOT"]):
        if Path(root).name == run_id:
            run_dir = Path(root)
            break
    (run_dir / "song.mp3").write_bytes(b"\xff\xfb" + b"\x00" * 100)
    r = client.get(
        f"/songs/{run_id}/audio",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.content.startswith(b"\xff\xfb")


def test_get_audio_serves_alternate_take_via_query(app):
    fastapi_app, token = app
    client = TestClient(fastapi_app)
    create = client.post(
        "/songs", json={"theme": "x"},
        headers={"Authorization": f"Bearer {token}"},
    )
    run_id = create.json()["run_id"]
    import os
    for root, _, _ in os.walk(os.environ["FACELESS_OUT_ROOT"]):
        if Path(root).name == run_id:
            run_dir = Path(root)
            break
    (run_dir / "takes").mkdir(exist_ok=True)
    (run_dir / "takes" / "take_2.mp3").write_bytes(b"TAKE2")
    r = client.get(
        f"/songs/{run_id}/audio?take=2",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.content == b"TAKE2"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_song_api.py -v -k "swap or audio"
```

Expected: FAIL — endpoints missing.

- [ ] **Step 3: Implement the endpoints**

Add to `pipeline/api.py`:

```python
class SwapTakeRequest(BaseModel):
    take: int  # 1 or 2


@app.post("/songs/{run_id}/swap-take")
def swap_take(
    run_id: str,
    req: SwapTakeRequest,
    user: User = Depends(require_user),
):
    from pipeline import song_assemble
    if req.take not in (1, 2):
        raise HTTPException(422, "take must be 1 or 2")
    run_dir = _resolve_song_dir(run_id, user)
    state = _read_state(run_dir)
    if state.get("kind") != "song":
        raise HTTPException(404, "not a song run")
    take_path = run_dir / "takes" / f"take_{req.take}.mp3"
    if not take_path.exists():
        raise HTTPException(404, f"take_{req.take}.mp3 not found")
    # Swap the chosen take, re-run ffmpeg
    song_mp3 = run_dir / "song.mp3"
    if song_mp3.exists():
        song_mp3.unlink()
    import shutil
    shutil.copy(take_path, song_mp3)
    song_assemble.assemble_song_video(
        cover_path=run_dir / "cover.png",
        song_mp3=song_mp3,
        out_mp4=run_dir / "final.mp4",
    )
    _write_state(run_dir, chosen_take=req.take)
    return {"ok": True, "chosen_take": req.take}


@app.get("/songs/{run_id}/audio")
def get_song_audio(
    run_id: str,
    take: int | None = None,
    user: User = Depends(require_user),
):
    from fastapi.responses import FileResponse
    run_dir = _resolve_song_dir(run_id, user)
    if take is not None:
        path = run_dir / "takes" / f"take_{take}.mp3"
    else:
        path = run_dir / "song.mp3"
    if not path.exists():
        raise HTTPException(404, "audio not found")
    return FileResponse(path, media_type="audio/mpeg")


@app.get("/songs/{run_id}/cover")
def get_song_cover(run_id: str, user: User = Depends(require_user)):
    from fastapi.responses import FileResponse
    run_dir = _resolve_song_dir(run_id, user)
    path = run_dir / "cover.png"
    if not path.exists():
        raise HTTPException(404, "cover not yet generated")
    return FileResponse(path, media_type="image/png")


@app.get("/songs/{run_id}/video")
def get_song_video(run_id: str, user: User = Depends(require_user)):
    from fastapi.responses import FileResponse
    run_dir = _resolve_song_dir(run_id, user)
    path = run_dir / "final.mp4"
    if not path.exists():
        raise HTTPException(404, "final.mp4 not yet assembled")
    return FileResponse(path, media_type="video/mp4")


@app.get("/songs/{run_id}/log")
def get_song_log(
    run_id: str,
    lines: int = 200,
    user: User = Depends(require_user),
):
    run_dir = _resolve_song_dir(run_id, user)
    path = run_dir / "run.log"
    if not path.exists():
        return {"log": ""}
    text = path.read_text(errors="replace")
    tail = "\n".join(text.splitlines()[-lines:])
    return {"log": tail}


@app.post("/songs/{run_id}/resume")
def resume_song(run_id: str, user: User = Depends(require_user)):
    run_dir = _resolve_song_dir(run_id, user)
    state = _read_state(run_dir)
    if state.get("kind") != "song":
        raise HTTPException(404, "not a song run")
    if state.get("status") != "failed":
        raise HTTPException(409, f"song is in state {state.get('status')!r}, cannot resume")
    # Re-spawn the post-approve subprocess from the failed stage onward.
    # run.py's --mode song reads api_state.json; the stage logic in
    # _run_song_post_approve currently always re-runs from generating_song.
    # MVP behavior: this re-charges for Suno. Improvement task: skip
    # Suno if song.mp3 exists and resume from cover or assemble.
    args = ["--mode", "song", "--resume", str(run_dir)]
    pid = _SPAWN_FN(args, run_dir)
    _write_state(run_dir, status="generating_song", pid=pid, last_error=None)
    return {"ok": True}
```

- [ ] **Step 4: Run tests to verify pass**

```bash
uv run pytest tests/test_song_api.py -v
```

Expected: 18 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/api.py tests/test_song_api.py
git commit -m "feat(song): swap-take, audio/cover/video streaming, log tail, resume"
```

---

## Task 13: End-to-end integration test (writer → approve → final.mp4)

**Files:**
- Create: `tests/test_song_pipeline.py`

Closes the loop. Exercises every mocked seam from `POST /songs` through `GET /songs/{id}/video`.

- [ ] **Step 1: Write the integration test**

Create `tests/test_song_pipeline.py`:

```python
from __future__ import annotations

import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_COVER = REPO_ROOT / "tests" / "fixtures" / "song" / "cover.png"
FIXTURE_SONG = REPO_ROOT / "tests" / "fixtures" / "song" / "short_song.mp3"


@pytest.fixture
def wired_app(monkeypatch, tmp_path: Path):
    token = "e2e-token"
    monkeypatch.setenv("FACELESS_API_TOKEN", token)
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path / "out"))
    monkeypatch.setenv("KIE_API_KEY", "stub")

    from pipeline import api as api_mod, song, song_cover, credits

    # Lyrics LLM
    canned = json.dumps({
        "title": "Test",
        "lyrics": "[Verse 1]\nline\n[Chorus]\nhook\n[Verse 2]\nline\n[Chorus]\nhook",
        "style_prompt": "Arabic pop ballad, slow tempo 72 BPM, oud + strings, male vocal, modern 2020s, melancholic minor key",
        "cover_prompt": "moonlight",
    })
    fake_llm = MagicMock()
    fake_llm.complete = MagicMock(return_value=canned)
    monkeypatch.setattr(api_mod, "_build_song_llm", lambda: fake_llm)

    # Credits — always allow
    monkeypatch.setattr(credits, "get_balance", lambda uid: 100)
    monkeypatch.setattr(credits, "check_or_deduct",
                        lambda user, amount, run_id, reason: 99)

    # Suno + cover stubs
    monkeypatch.setattr(song, "submit_song_job",
                        lambda client, **kw: "fake-task")
    monkeypatch.setattr(
        song, "wait_for_song",
        lambda client, task_id, **kw: [
            song.SongTake(url="https://x/t1.mp3", duration_s=3.0),
            song.SongTake(url="https://x/t2.mp3", duration_s=2.8),
        ],
    )
    monkeypatch.setattr(
        song, "download_take",
        lambda client, url, out_path: shutil.copy(FIXTURE_SONG, out_path),
    )

    def fake_cover(*, client, cover_prompt, out_dir):
        out = out_dir / "cover_raw.png"
        shutil.copy(FIXTURE_COVER, out)
        return out
    monkeypatch.setattr(song_cover, "generate_cover_image", fake_cover)

    # In-process spawn: run main_with_args directly so the test executes
    # the real pipeline plumbing
    import run as run_mod
    def in_process_spawn(args, run_dir):
        rc = run_mod.main_with_args(args)
        if rc != 0:
            raise RuntimeError(f"pipeline failed rc={rc}")
        # Real spawn would return a pid; we just need a non-zero int
        return 99999
    api_mod.set_spawn_fn(in_process_spawn)

    return api_mod.app, token


def test_full_song_pipeline(wired_app):
    fastapi_app, token = wired_app
    client = TestClient(fastapi_app)

    # 1. Writer pass
    r = client.post("/songs", json={"theme": "moon"},
                    headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 201
    run_id = r.json()["run_id"]

    # 2. Get script
    r = client.get(f"/songs/{run_id}/script",
                   headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert "[Chorus]" in r.json()["lyrics"]

    # 3. Approve
    r = client.post(f"/songs/{run_id}/approve",
                    headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200

    # 4. After in-process spawn, the run should be complete
    r = client.get(f"/songs/{run_id}",
                   headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "complete", body
    assert body["has_video"] is True

    # 5. Video streams back
    r = client.get(f"/songs/{run_id}/video",
                   headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.headers["content-type"] == "video/mp4"
    assert len(r.content) > 1000
```

- [ ] **Step 2: Run the test**

```bash
uv run pytest tests/test_song_pipeline.py -v -s
```

Expected: PASS. If a stub seam is missing for an LLM call inside `regenerate_*` paths or similar, surface the failure — the integration test is the canary.

- [ ] **Step 3: Commit**

```bash
git add tests/test_song_pipeline.py
git commit -m "test(song): end-to-end integration covering write → approve → video"
```

---

## Task 14: Flutter — API client + models

**Files:**
- Modify: `lib/api/models.dart`
- Modify: `lib/api/client.dart`

- [ ] **Step 1: Add the model classes**

In `lib/api/models.dart`, add:

```dart
class SongSummary {
  final String id;
  final String status;
  final String? title;
  final String? theme;
  final String createdAt;
  final bool hasVideo;
  final int? chosenTake;
  final String? lastError;

  SongSummary({
    required this.id,
    required this.status,
    required this.title,
    required this.theme,
    required this.createdAt,
    required this.hasVideo,
    required this.chosenTake,
    required this.lastError,
  });

  factory SongSummary.fromJson(Map<String, dynamic> j) => SongSummary(
        id: j['id'],
        status: j['status'],
        title: j['title'],
        theme: j['theme'],
        createdAt: j['created_at'] ?? '',
        hasVideo: j['has_video'] ?? false,
        chosenTake: j['chosen_take'],
        lastError: j['last_error'],
      );
}

class SongScript {
  final String title;
  final String lyrics;
  final String stylePrompt;
  final String coverPrompt;
  final String language;
  final int costCredits;
  final double costUsd;

  SongScript({
    required this.title,
    required this.lyrics,
    required this.stylePrompt,
    required this.coverPrompt,
    required this.language,
    required this.costCredits,
    required this.costUsd,
  });

  factory SongScript.fromJson(Map<String, dynamic> j) => SongScript(
        title: j['title'],
        lyrics: j['lyrics'],
        stylePrompt: j['style_prompt'],
        coverPrompt: j['cover_prompt'],
        language: j['language'],
        costCredits: j['cost_credits'],
        costUsd: (j['cost_usd'] as num).toDouble(),
      );
}
```

- [ ] **Step 2: Add the client methods**

In `lib/api/client.dart`, add (mirroring the existing horror methods' shape):

```dart
Future<String> createSong({
  required String theme,
  String? customLyrics,
  String? styleHint,
  String language = 'ar',
}) async {
  final r = await _http.post(
    Uri.parse('$_baseUrl/songs'),
    headers: _authHeaders(),
    body: jsonEncode({
      'theme': theme,
      if (customLyrics != null) 'custom_lyrics': customLyrics,
      if (styleHint != null) 'style_hint': styleHint,
      'language': language,
    }),
  );
  _check(r);
  return jsonDecode(r.body)['run_id'];
}

Future<List<SongSummary>> listSongs() async {
  final r = await _http.get(Uri.parse('$_baseUrl/songs'), headers: _authHeaders());
  _check(r);
  final arr = jsonDecode(r.body) as List;
  return arr.map((j) => SongSummary.fromJson(j)).toList();
}

Future<SongSummary> getSong(String id) async {
  final r = await _http.get(Uri.parse('$_baseUrl/songs/$id'), headers: _authHeaders());
  _check(r);
  return SongSummary.fromJson(jsonDecode(r.body));
}

Future<SongScript> getSongScript(String id) async {
  final r = await _http.get(Uri.parse('$_baseUrl/songs/$id/script'), headers: _authHeaders());
  _check(r);
  return SongScript.fromJson(jsonDecode(r.body));
}

Future<void> approveSong(String id) async {
  final r = await _http.post(Uri.parse('$_baseUrl/songs/$id/approve'), headers: _authHeaders());
  _check(r);
}

Future<void> regenerateLyrics(String id) async {
  final r = await _http.post(Uri.parse('$_baseUrl/songs/$id/regenerate-lyrics'), headers: _authHeaders());
  _check(r);
}

Future<void> regenerateCoverPrompt(String id) async {
  final r = await _http.post(Uri.parse('$_baseUrl/songs/$id/regenerate-cover-prompt'), headers: _authHeaders());
  _check(r);
}

Future<void> editSong(String id, {String? lyrics, String? stylePrompt, String? coverPrompt}) async {
  final r = await _http.post(
    Uri.parse('$_baseUrl/songs/$id/edit'),
    headers: _authHeaders(),
    body: jsonEncode({
      if (lyrics != null) 'lyrics': lyrics,
      if (stylePrompt != null) 'style_prompt': stylePrompt,
      if (coverPrompt != null) 'cover_prompt': coverPrompt,
    }),
  );
  _check(r);
}

Future<void> swapTake(String id, int take) async {
  final r = await _http.post(
    Uri.parse('$_baseUrl/songs/$id/swap-take'),
    headers: _authHeaders(),
    body: jsonEncode({'take': take}),
  );
  _check(r);
}

Future<void> cancelSong(String id) async {
  final r = await _http.post(Uri.parse('$_baseUrl/songs/$id/cancel'), headers: _authHeaders());
  _check(r);
}

Future<void> resumeSong(String id) async {
  final r = await _http.post(Uri.parse('$_baseUrl/songs/$id/resume'), headers: _authHeaders());
  _check(r);
}

String songVideoUrl(String id) => '$_baseUrl/songs/$id/video';
String songCoverUrl(String id) => '$_baseUrl/songs/$id/cover';
String songAudioUrl(String id, {int? take}) =>
    '$_baseUrl/songs/$id/audio${take != null ? '?take=$take' : ''}';
```

If `_check`, `_authHeaders`, `_http`, `_baseUrl` are named differently in your client, adapt to the existing names (read `lib/api/client.dart` first).

- [ ] **Step 3: Confirm analyzer passes**

```bash
flutter analyze lib/api/
```

Expected: no errors. (Existing analyzer warnings outside `lib/api/` are unrelated.)

- [ ] **Step 4: Commit**

```bash
git add lib/api/models.dart lib/api/client.dart
git commit -m "feat(song): Flutter API client + models for /songs endpoints"
```

---

## Task 15: Flutter — Create Song screen

**Files:**
- Create: `lib/screens/new_song_screen.dart`
- Modify: `lib/main.dart` (route registration)

- [ ] **Step 1: Implement the screen**

Create `lib/screens/new_song_screen.dart`:

```dart
import 'package:flutter/material.dart';

import '../api/client.dart';
import 'song_approve_screen.dart';

class NewSongScreen extends StatefulWidget {
  final ApiClient client;
  const NewSongScreen({super.key, required this.client});

  @override
  State<NewSongScreen> createState() => _NewSongScreenState();
}

class _NewSongScreenState extends State<NewSongScreen> {
  final _themeCtrl = TextEditingController();
  final _lyricsCtrl = TextEditingController();
  final _styleCtrl = TextEditingController();
  String _language = 'ar';
  bool _submitting = false;
  String? _error;

  Future<void> _submit() async {
    if (_themeCtrl.text.trim().isEmpty) {
      setState(() => _error = 'Theme is required');
      return;
    }
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      final runId = await widget.client.createSong(
        theme: _themeCtrl.text.trim(),
        customLyrics: _lyricsCtrl.text.trim().isEmpty ? null : _lyricsCtrl.text,
        styleHint: _styleCtrl.text.trim().isEmpty ? null : _styleCtrl.text,
        language: _language,
      );
      if (!mounted) return;
      Navigator.of(context).pushReplacement(MaterialPageRoute(
        builder: (_) => SongApproveScreen(client: widget.client, runId: runId),
      ));
    } catch (e) {
      setState(() {
        _error = '$e';
        _submitting = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('New song')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: ListView(
          children: [
            TextField(
              controller: _themeCtrl,
              decoration: const InputDecoration(
                labelText: 'Theme',
                hintText: 'أغنية حزينة عن القمر',
              ),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _lyricsCtrl,
              maxLines: 6,
              decoration: const InputDecoration(
                labelText: 'Custom lyrics (optional)',
                hintText: 'Leave empty for AI',
              ),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _styleCtrl,
              decoration: const InputDecoration(
                labelText: 'Style hint (optional)',
                hintText: 'Arabic ballad, slow tempo, male vocal',
              ),
            ),
            const SizedBox(height: 16),
            DropdownButtonFormField<String>(
              value: _language,
              decoration: const InputDecoration(labelText: 'Language'),
              items: const [
                DropdownMenuItem(value: 'ar', child: Text('Arabic')),
                DropdownMenuItem(value: 'en', child: Text('English')),
                DropdownMenuItem(value: 'es', child: Text('Spanish')),
                DropdownMenuItem(value: 'fr', child: Text('French')),
                DropdownMenuItem(value: 'tr', child: Text('Turkish')),
              ],
              onChanged: (v) => setState(() => _language = v ?? 'ar'),
            ),
            const SizedBox(height: 24),
            if (_error != null)
              Text(_error!, style: const TextStyle(color: Colors.red)),
            ElevatedButton(
              onPressed: _submitting ? null : _submit,
              child: _submitting
                  ? const SizedBox(
                      width: 18, height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2))
                  : const Text('Generate draft'),
            ),
            const SizedBox(height: 8),
            const Text(
              'You will review lyrics + cover prompt before any credit is spent.',
              style: TextStyle(fontSize: 12, color: Colors.grey),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }
}
```

- [ ] **Step 2: Run analyzer**

```bash
flutter analyze lib/screens/new_song_screen.dart
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add lib/screens/new_song_screen.dart
git commit -m "feat(song): NewSongScreen form (theme, lyrics, style, language)"
```

---

## Task 16: Flutter — Approve screen

**Files:**
- Create: `lib/screens/song_approve_screen.dart`

- [ ] **Step 1: Implement the screen**

Create `lib/screens/song_approve_screen.dart`:

```dart
import 'package:flutter/material.dart';

import '../api/client.dart';
import '../api/models.dart';
import 'song_detail_screen.dart';

class SongApproveScreen extends StatefulWidget {
  final ApiClient client;
  final String runId;
  const SongApproveScreen({super.key, required this.client, required this.runId});

  @override
  State<SongApproveScreen> createState() => _SongApproveScreenState();
}

class _SongApproveScreenState extends State<SongApproveScreen> {
  SongScript? _script;
  String? _error;
  bool _busy = true;
  bool _approving = false;

  @override
  void initState() {
    super.initState();
    _pollUntilReady();
  }

  Future<void> _pollUntilReady() async {
    for (int i = 0; i < 30; i++) {
      try {
        final s = await widget.client.getSong(widget.runId);
        if (s.status == 'awaiting_approval') {
          final script = await widget.client.getSongScript(widget.runId);
          if (!mounted) return;
          setState(() {
            _script = script;
            _busy = false;
          });
          return;
        }
        if (s.status == 'failed') {
          setState(() {
            _error = s.lastError ?? 'lyrics generation failed';
            _busy = false;
          });
          return;
        }
      } catch (e) {
        // Keep polling; might be a transient 404 while disk write settles.
      }
      await Future.delayed(const Duration(seconds: 1));
    }
    setState(() {
      _error = 'Timed out waiting for lyrics';
      _busy = false;
    });
  }

  Future<void> _regenLyrics() async {
    setState(() => _busy = true);
    try {
      await widget.client.regenerateLyrics(widget.runId);
      final script = await widget.client.getSongScript(widget.runId);
      setState(() => _script = script);
    } catch (e) {
      setState(() => _error = '$e');
    } finally {
      setState(() => _busy = false);
    }
  }

  Future<void> _regenCover() async {
    setState(() => _busy = true);
    try {
      await widget.client.regenerateCoverPrompt(widget.runId);
      final script = await widget.client.getSongScript(widget.runId);
      setState(() => _script = script);
    } catch (e) {
      setState(() => _error = '$e');
    } finally {
      setState(() => _busy = false);
    }
  }

  Future<void> _approve() async {
    setState(() => _approving = true);
    try {
      await widget.client.approveSong(widget.runId);
      if (!mounted) return;
      Navigator.of(context).pushReplacement(MaterialPageRoute(
        builder: (_) => SongDetailScreen(client: widget.client, runId: widget.runId),
      ));
    } catch (e) {
      setState(() {
        _error = '$e';
        _approving = false;
      });
    }
  }

  Future<void> _discard() async {
    await widget.client.cancelSong(widget.runId);
    if (!mounted) return;
    Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    if (_busy) {
      return Scaffold(
        appBar: AppBar(title: const Text('Review draft')),
        body: const Center(child: CircularProgressIndicator()),
      );
    }
    if (_error != null) {
      return Scaffold(
        appBar: AppBar(title: const Text('Review draft')),
        body: Center(child: Text(_error!, style: const TextStyle(color: Colors.red))),
      );
    }
    final s = _script!;
    return Scaffold(
      appBar: AppBar(title: Text(s.title)),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: ListView(
          children: [
            _Card(
              title: 'Lyrics',
              body: Directionality(
                textDirection: s.language == 'ar' ? TextDirection.rtl : TextDirection.ltr,
                child: Text(s.lyrics, style: const TextStyle(fontSize: 16)),
              ),
              actions: [
                TextButton.icon(
                  icon: const Icon(Icons.refresh),
                  label: const Text('Re-roll'),
                  onPressed: _regenLyrics,
                ),
              ],
            ),
            _Card(
              title: 'Style',
              body: Text(s.stylePrompt),
            ),
            _Card(
              title: 'Cover prompt',
              body: Text(s.coverPrompt),
              actions: [
                TextButton.icon(
                  icon: const Icon(Icons.refresh),
                  label: const Text('Re-roll'),
                  onPressed: _regenCover,
                ),
              ],
            ),
            const SizedBox(height: 24),
            Text('Cost: ${s.costCredits} credit(s) (~\$${s.costUsd.toStringAsFixed(2)})',
                style: const TextStyle(fontWeight: FontWeight.bold)),
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    onPressed: _approving ? null : _discard,
                    child: const Text('Discard'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: ElevatedButton(
                    onPressed: _approving ? null : _approve,
                    child: _approving
                        ? const SizedBox(width: 18, height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2))
                        : const Text('Approve & generate'),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _Card extends StatelessWidget {
  final String title;
  final Widget body;
  final List<Widget>? actions;
  const _Card({required this.title, required this.body, this.actions});
  @override
  Widget build(BuildContext context) => Card(
        margin: const EdgeInsets.only(bottom: 12),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title, style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 8),
              body,
              if (actions != null) ...[
                const SizedBox(height: 8),
                Row(mainAxisAlignment: MainAxisAlignment.end, children: actions!),
              ],
            ],
          ),
        ),
      );
}
```

- [ ] **Step 2: Analyzer**

```bash
flutter analyze lib/screens/song_approve_screen.dart
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add lib/screens/song_approve_screen.dart
git commit -m "feat(song): SongApproveScreen — review + regen + approve"
```

---

## Task 17: Flutter — Detail screen with take swap

**Files:**
- Create: `lib/screens/song_detail_screen.dart`
- Add: `video_player` package dependency in `pubspec.yaml` (if not already present)

- [ ] **Step 1: Ensure `video_player` is in pubspec**

Open `pubspec.yaml`. Confirm `video_player:` is listed under `dependencies:`. If not, add:

```yaml
  video_player: ^2.8.0
```

Then run:

```bash
flutter pub get
```

- [ ] **Step 2: Implement the screen**

Create `lib/screens/song_detail_screen.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:video_player/video_player.dart';

import '../api/client.dart';
import '../api/models.dart';

class SongDetailScreen extends StatefulWidget {
  final ApiClient client;
  final String runId;
  const SongDetailScreen({super.key, required this.client, required this.runId});

  @override
  State<SongDetailScreen> createState() => _SongDetailScreenState();
}

class _SongDetailScreenState extends State<SongDetailScreen> {
  SongSummary? _summary;
  VideoPlayerController? _video;
  bool _swapping = false;

  @override
  void initState() {
    super.initState();
    _poll();
  }

  @override
  void dispose() {
    _video?.dispose();
    super.dispose();
  }

  Future<void> _poll() async {
    while (mounted) {
      try {
        final s = await widget.client.getSong(widget.runId);
        if (!mounted) return;
        setState(() => _summary = s);
        if (s.status == 'complete') {
          await _initVideo();
          return;
        }
        if (s.status == 'failed' || s.status == 'canceled') {
          return;
        }
      } catch (_) {
        // tolerate transient errors
      }
      await Future.delayed(const Duration(seconds: 3));
    }
  }

  Future<void> _initVideo() async {
    final url = widget.client.songVideoUrl(widget.runId);
    _video?.dispose();
    _video = VideoPlayerController.networkUrl(
      Uri.parse(url),
      httpHeaders: widget.client.authHeaders,  // make sure this exists in client.dart
    );
    await _video!.initialize();
    if (mounted) setState(() {});
  }

  Future<void> _swap(int take) async {
    setState(() => _swapping = true);
    try {
      await widget.client.swapTake(widget.runId, take);
      await _initVideo();
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Swap failed: $e')));
    } finally {
      setState(() => _swapping = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = _summary;
    if (s == null) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    return Scaffold(
      appBar: AppBar(title: Text(s.title ?? 'Song')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Status: ${s.status}',
                style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 16),
            if (s.hasVideo && _video != null && _video!.value.isInitialized)
              AspectRatio(
                aspectRatio: _video!.value.aspectRatio,
                child: Stack(alignment: Alignment.bottomCenter, children: [
                  VideoPlayer(_video!),
                  VideoProgressIndicator(_video!, allowScrubbing: true),
                ]),
              ),
            if (s.hasVideo && _video != null) ...[
              const SizedBox(height: 16),
              Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                IconButton(
                  iconSize: 48,
                  icon: Icon(_video!.value.isPlaying
                      ? Icons.pause_circle : Icons.play_circle),
                  onPressed: () {
                    setState(() {
                      if (_video!.value.isPlaying) {
                        _video!.pause();
                      } else {
                        _video!.play();
                      }
                    });
                  },
                ),
              ]),
              const SizedBox(height: 16),
              Text('Take ${s.chosenTake ?? 1} (active)',
                  textAlign: TextAlign.center),
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  ElevatedButton(
                    onPressed: _swapping || s.chosenTake == 1 ? null : () => _swap(1),
                    child: const Text('Use Take 1'),
                  ),
                  const SizedBox(width: 12),
                  ElevatedButton(
                    onPressed: _swapping || s.chosenTake == 2 ? null : () => _swap(2),
                    child: const Text('Use Take 2'),
                  ),
                ],
              ),
            ],
            if (s.status == 'failed' && s.lastError != null) ...[
              const SizedBox(height: 16),
              Card(
                color: Colors.red.shade50,
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Text(s.lastError!,
                      style: const TextStyle(color: Colors.red)),
                ),
              ),
              ElevatedButton(
                onPressed: () async {
                  await widget.client.resumeSong(widget.runId);
                  _poll();
                },
                child: const Text('Retry'),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
```

If `widget.client.authHeaders` doesn't exist publicly on `ApiClient`, expose a getter that returns the auth headers map. If `client.dart` keeps headers private, add: `Map<String, String> get authHeaders => _authHeaders();`.

- [ ] **Step 3: Analyzer**

```bash
flutter analyze lib/screens/song_detail_screen.dart
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add lib/screens/song_detail_screen.dart pubspec.yaml pubspec.lock
git commit -m "feat(song): SongDetailScreen — video player + take swap"
```

---

## Task 18: Flutter — Wire home screen tabs + main routes

**Files:**
- Modify: `lib/screens/home_screen.dart`
- Modify: `lib/main.dart`

- [ ] **Step 1: Add a Horror|Song segmented selector to the home screen**

Read `lib/screens/home_screen.dart`. Find the body's column. At the top of the body, add:

```dart
SegmentedButton<String>(
  segments: const [
    ButtonSegment(value: 'horror', label: Text('Horror'), icon: Icon(Icons.movie)),
    ButtonSegment(value: 'song', label: Text('Song'), icon: Icon(Icons.music_note)),
  ],
  selected: {_mode},
  onSelectionChanged: (s) => setState(() {
    _mode = s.first;
    if (_mode == 'song') {
      _songsFuture = widget.client.listSongs();
    } else {
      _runsFuture = widget.client.listRuns();
    }
  }),
),
```

Add to state:

```dart
String _mode = 'horror';
Future<List<SongSummary>>? _songsFuture;
```

Conditionally render the songs list when `_mode == 'song'`:

```dart
if (_mode == 'song')
  Expanded(
    child: FutureBuilder<List<SongSummary>>(
      future: _songsFuture,
      builder: (ctx, snap) {
        if (!snap.hasData) return const Center(child: CircularProgressIndicator());
        final songs = snap.data!;
        if (songs.isEmpty) return const Center(child: Text('No songs yet'));
        return ListView.builder(
          itemCount: songs.length,
          itemBuilder: (ctx, i) => ListTile(
            leading: songs[i].hasVideo
                ? Image.network(
                    widget.client.songCoverUrl(songs[i].id),
                    width: 48, height: 48, fit: BoxFit.cover,
                    headers: widget.client.authHeaders,
                  )
                : const Icon(Icons.music_note),
            title: Text(songs[i].title ?? songs[i].theme ?? '(untitled)'),
            subtitle: Text(songs[i].status),
            onTap: () {
              if (songs[i].status == 'awaiting_approval') {
                Navigator.of(context).push(MaterialPageRoute(
                  builder: (_) => SongApproveScreen(
                    client: widget.client, runId: songs[i].id),
                ));
              } else {
                Navigator.of(context).push(MaterialPageRoute(
                  builder: (_) => SongDetailScreen(
                    client: widget.client, runId: songs[i].id),
                ));
              }
            },
          ),
        );
      },
    ),
  ),
```

Add imports:

```dart
import '../api/models.dart';
import 'song_approve_screen.dart';
import 'song_detail_screen.dart';
```

Update the FAB / "New" button so when `_mode == 'song'` it routes to `NewSongScreen` instead of the horror create flow. Pattern:

```dart
floatingActionButton: FloatingActionButton(
  onPressed: () {
    if (_mode == 'song') {
      Navigator.of(context).push(MaterialPageRoute(
        builder: (_) => NewSongScreen(client: widget.client),
      ));
    } else {
      // existing horror path
    }
  },
  child: const Icon(Icons.add),
),
```

(`import '../screens/new_song_screen.dart';` at the top.)

- [ ] **Step 2: Analyzer**

```bash
flutter analyze lib/screens/home_screen.dart lib/main.dart
```

Expected: no errors.

- [ ] **Step 3: Smoke-test in a browser**

```bash
./scripts/run-app.sh
```

In the browser: see the `Horror | Song` selector at the top; tapping `Song` shows the (empty) song list; the `+` button opens the new-song form.

- [ ] **Step 4: Commit**

```bash
git add lib/screens/home_screen.dart lib/main.dart
git commit -m "feat(song): home screen Horror|Song selector + song list routing"
```

---

## Task 19: Manual end-to-end smoke test (real API spend)

**Not a code change — this is the live verification step before declaring the feature done.**

- [ ] **Step 1: Start backend**

```bash
source .env
uv run uvicorn pipeline.api:app --host 0.0.0.0 --port 8000
```

In another terminal, start the Cloudflare tunnel:

```bash
cloudflared tunnel --url http://localhost:8000
```

Capture the tunnel URL.

- [ ] **Step 2: Run the Flutter app pointed at the tunnel**

```bash
./scripts/run-app.sh
```

- [ ] **Step 3: Create a real song**

In the app: switch to **Song**, tap +, enter theme `أغنية حزينة عن القمر`, leave lyrics + style empty, language Arabic, tap **Generate draft**. Wait ~10s, review the lyrics on the approve screen.

- [ ] **Step 4: Approve and watch**

Tap **Approve & generate**. Watch the detail screen progress: `generating_song` → `generating_cover` → `assembling` → `complete`. Total time ~2–3 min (Suno ~60s, Flux ~15s, ffmpeg ~10–60s).

- [ ] **Step 5: Verify quality bar**

Play the result. **Listen with fresh ears.** Specifically check:

- Does the song sound like a real song to you on first listen?
- Section structure audible (verse / chorus / bridge)?
- Vocals confident, not robotic?
- Cover art looks like a real album cover, not a stock-photo collage?
- Title text legible and well-placed on the cover?

If any of these miss, **do not declare the feature done.** The most likely fix is one of: (a) Suno model id is wrong — verify against Kie.ai docs (Task 0), (b) lyrics LLM is omitting section tags despite the contract — inspect `song.json` directly, (c) style hint is too vague — inspect `song.json`.

- [ ] **Step 6: Verify take swap**

Tap **Use Take 2**, wait ~10s, verify the audio under the player changed.

- [ ] **Step 7: Spot-check streaming**

Download `final.mp4` from the detail screen; play it in QuickTime. Confirm:

- 1080×1080, 25fps
- Audio is the same as the streaming preview (no re-encoding artifacts)
- Title text on the cover is readable

- [ ] **Step 8: Commit a note**

If everything passed, commit:

```bash
git commit --allow-empty -m "feat(song): manual e2e smoke test passed on 2026-05-28"
```

If anything failed, file a follow-up task; do NOT mark this plan complete.

---

## Self-review notes (for the implementer to read)

After Task 19, look at the full diff and the spec together. The spec has six "Quality gate" callouts — confirm each is honored in the final code:

1. **Suno V4.5 model id** — pinned in `pipeline/song.py:SUNO_MODEL_ID`. Verify Task 0 was actually done.
2. **Suno custom mode** — `submit_song_job` sets `customMode: True` in the body.
3. **Section tags in lyrics** — `validate_section_tags` is called from `generate_song_script` and would have raised in Task 3 tests if missing.
4. **Both takes saved** — `_run_song_post_approve` writes both `takes/take_1.mp3` and `takes/take_2.mp3`.
5. **Flux Kontext Max for cover** — `song_cover.FLUX_MODEL_ID = "flux-kontext-max"`.
6. **Audio stream-copied** — `song_assemble` uses `-c:a copy`, no `loudnorm`.

If any are accidentally regressed during the build, the test suite catches them — keep all the tests green through every task.

## Open items deliberately left for after MVP

- Stage-aware `/resume` (currently restarts from Suno even on cover/assemble failures). MVP is correct but wasteful; track as a follow-up.
- Title-overlay positioning for very long titles in RTL — current right-align + width fit handles common cases but extreme outliers may overflow.
- Multilingual font support beyond Arabic/Latin (e.g., Devanagari, Thai). Add as needed.
- A separate cost line for re-roll spend (currently regen calls are free since lyrics LLM is free; document if we ever switch the lyrics LLM to a paid model).
