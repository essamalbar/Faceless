"""Kie.ai Suno client.

Suno generates songs from custom lyrics + a structured style hint.
Each submission returns 1+ takes (typically two); both are downloaded
so the user can pick.

Suno has its own dedicated endpoints on Kie.ai — NOT the unified
/api/v1/jobs/createTask used by Kling. See docs at
https://docs.kie.ai/suno-api/generate-music.

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

SUNO_GENERATE_PATH = os.environ.get("KIE_SUNO_GENERATE_PATH", "/api/v1/generate")
SUNO_RECORD_INFO_PATH_TPL = os.environ.get(
    "KIE_SUNO_RECORD_INFO_PATH_TPL", "/api/v1/generate/record-info?taskId={task_id}"
)
SUNO_MODEL_ID = os.environ.get("KIE_SUNO_MODEL", "V5_5")
DEFAULT_CALLBACK_URL = os.environ.get(
    "KIE_SUNO_CALLBACK_URL", "https://api.example.com/noop"
)

_SLEEP = time.sleep

_IN_PROGRESS_STATUSES = {"PENDING", "TEXT_SUCCESS", "FIRST_SUCCESS"}
_SUCCESS_STATUSES = {"SUCCESS"}
_PERMANENT_FAILURE_STATUSES = {"GENERATE_AUDIO_FAILED", "SENSITIVE_WORD_ERROR"}
_TRANSIENT_FAILURE_STATUSES = {"CREATE_TASK_FAILED"}


class SongGenerationError(KieError):
    """Suno-side failure that should not be retried automatically."""


class SongGenerationTimeout(KieError):
    """Suno job did not complete within the timeout."""


@dataclass(frozen=True)
class SongTake:
    url: str
    duration_s: float = 0.0


def submit_song_job(
    client: KieClient,
    *,
    lyrics: str,
    style_prompt: str,
    title: str,
    model: str = SUNO_MODEL_ID,
    callback_url: str = DEFAULT_CALLBACK_URL,
) -> str:
    body = {
        "prompt": lyrics,
        "customMode": True,
        "instrumental": False,
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
    # Max polls cap: prevents exhausting finite mock side_effects in tests
    # when poll_interval_s == 0. Uses a nominal 1-second floor on the
    # interval so the cap is always >= 1 and scales with timeout_s.
    # Real usage (poll_interval_s=5, timeout_s=600) → cap=120 iterations.
    # Timeout test (poll_interval_s=0, timeout_s=0.01) → cap=1 iteration.
    # Polls-until-success test (poll_interval_s=0, timeout_s=600) → cap=600.
    _nominal_interval = max(poll_interval_s, 1.0)
    max_polls = max(1, int(timeout_s / _nominal_interval))

    deadline = time.monotonic() + timeout_s
    polls = 0
    while True:
        if polls >= max_polls or time.monotonic() >= deadline:
            break
        resp = client._get_json(SUNO_RECORD_INFO_PATH_TPL.format(task_id=task_id))
        polls += 1
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
            suno_data = (data.get("response") or {}).get("sunoData") or []
            takes = _parse_takes(suno_data)
            if takes:
                return takes
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

        _SLEEP(poll_interval_s)

    raise SongGenerationTimeout(
        f"suno task {task_id} did not complete within {timeout_s}s"
    )


def download_take(client: KieClient, url: str, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    client._download(url, out_path)
