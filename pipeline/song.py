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
# Cover mode: takes an uploaded reference audio and returns a new performance
# that RETAINS the source's core melody. Same task/record-info system as
# generate, so wait_for_song + download_take are reused unchanged.
SUNO_COVER_PATH = os.environ.get(
    "KIE_SUNO_COVER_PATH", "/api/v1/generate/upload-cover"
)
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
    audio_id: str = ""  # the sunoData[i].id — needed to create a Persona


def submit_song_job(
    client: KieClient,
    *,
    lyrics: str,
    style_prompt: str,
    title: str,
    model: str = SUNO_MODEL_ID,
    callback_url: str = DEFAULT_CALLBACK_URL,
    vocal_gender: str | None = None,
    persona_id: str | None = None,
    negative_tags: str | None = None,
) -> str:
    """Submit a Suno custom-mode job; return taskId.

    Optional voice-control parameters (Kie.ai Suno API):
      vocal_gender:  'm' or 'f' — increases probability of chosen gender,
                     doesn't guarantee. Custom-mode only.
      persona_id:    ID of a Persona created via /api/v1/persona/generate.
                     Locks the singer's voice across generations. Custom-mode
                     + V5/V5.5 only. This is the closest thing to voice
                     cloning Suno offers.
      negative_tags: comma-separated tags to exclude (e.g. "female vocal").
    """
    body = {
        "prompt": lyrics,
        "customMode": True,
        "instrumental": False,
        "model": model,
        "callBackUrl": callback_url,
        "style": style_prompt,
        "title": title,
    }
    if vocal_gender in ("m", "f"):
        body["vocalGender"] = vocal_gender
    if persona_id:
        body["personaId"] = persona_id
    if negative_tags:
        body["negativeTags"] = negative_tags
    resp = client._post_json(SUNO_GENERATE_PATH, body)
    data = resp.get("data") or {}
    task_id = data.get("taskId") or resp.get("taskId")
    if not task_id:
        raise KieError(f"suno submit response missing taskId: {resp}")
    return str(task_id)


def submit_cover_job(
    client: KieClient,
    *,
    upload_url: str,
    lyrics: str,
    style_prompt: str,
    title: str,
    model: str = SUNO_MODEL_ID,
    callback_url: str = DEFAULT_CALLBACK_URL,
    vocal_gender: str | None = None,
    negative_tags: str | None = None,
    audio_weight: float | None = None,
    style_weight: float | None = None,
) -> str:
    """Submit a Suno upload-cover job; return taskId.

    Unlike submit_song_job (text→song), this hands Suno an uploaded reference
    track (`upload_url`, ≤8 min, publicly fetchable) and Suno produces a NEW
    performance that RETAINS the source's core melody — the closest thing to a
    faithful cover the engine offers. The voice is still Suno's own (no singer
    cloning); vocal_gender only biases the gender.

    customMode + instrumental=False + lyrics-in-prompt are load-bearing for the
    same reason as submit_song_job: without customMode Suno rewrites the prompt
    and quality drops, and we want it to sing the provided (reviewed) words."""
    body = {
        "uploadUrl": upload_url,
        "prompt": lyrics,
        "customMode": True,
        "instrumental": False,
        "model": model,
        "callBackUrl": callback_url,
        "style": style_prompt,
        "title": title,
    }
    if vocal_gender in ("m", "f"):
        body["vocalGender"] = vocal_gender
    if negative_tags:
        body["negativeTags"] = negative_tags
    # Faithfulness knobs (0-1, 2dp). audioWeight = how closely the cover
    # follows the SOURCE AUDIO's melody/feel — the "match the original"
    # dial the user asked for. Omitted → Suno's own default.
    if audio_weight is not None:
        body["audioWeight"] = round(float(audio_weight), 2)
    if style_weight is not None:
        body["styleWeight"] = round(float(style_weight), 2)
    resp = client._post_json(SUNO_COVER_PATH, body)
    data = resp.get("data") or {}
    task_id = data.get("taskId") or resp.get("taskId")
    if not task_id:
        raise KieError(f"suno cover submit response missing taskId: {resp}")
    return str(task_id)


def _parse_takes(suno_data: list[dict]) -> list[SongTake]:
    """Extract SongTake list from a sunoData array.

    Each entry MUST have an audioUrl. duration is optional — Kie.ai's
    documented schema doesn't list it, but undocumented fields are
    sometimes present. If missing, duration_s stays 0.0 and callers
    that need duration (e.g. take-picking in run.py) must measure it
    from the downloaded MP3 via ffprobe.
    """
    takes: list[SongTake] = []
    for entry in suno_data:
        url = entry.get("audioUrl")
        if not url:
            continue
        duration = entry.get("duration") or entry.get("durationSec") or 0
        try:
            duration_s = float(duration)
        except (TypeError, ValueError):
            duration_s = 0.0
        audio_id = str(entry.get("id") or "")
        takes.append(SongTake(
            url=str(url), duration_s=duration_s, audio_id=audio_id,
        ))
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

        # Known in-progress statuses keep polling. Anything else (an
        # undocumented status Kie.ai may add later) is treated as
        # transient with a warning rather than silently looping until
        # timeout — a new failure mode should surface fast.
        if status and status not in _IN_PROGRESS_STATUSES:
            raise TransientKieError(
                f"suno task {task_id} unrecognised status {status!r} "
                f"— treating as transient; check Kie.ai docs for new enums"
            )

        _SLEEP(poll_interval_s)

    raise SongGenerationTimeout(
        f"suno task {task_id} did not complete within {timeout_s}s"
    )


def download_take(client: KieClient, url: str, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    client._download(url, out_path)


# Persona endpoint — used to lock a singer's voice across future songs.
# Pass a previous generation's taskId + audioId; Kie returns a personaId
# that subsequent submit_song_job calls can pass via persona_id to
# preserve voice character.
SUNO_PERSONA_GENERATE_PATH = os.environ.get(
    "KIE_SUNO_PERSONA_GENERATE_PATH", "/api/v1/generate/generate-persona"
)


class PersonaSourceNotFound(KieError):
    """The source song's Suno taskId is no longer queryable on Kie's
    side (typically because it expired or was never recorded). The
    user needs to generate a fresh song to create a persona from."""


def submit_persona_job(
    client: KieClient,
    *,
    source_task_id: str,
    source_audio_id: str,
    name: str,
    description: str,
) -> str:
    """Create a Persona from an existing Suno generation.

    Returns the personaId, which can be passed to submit_song_job's
    persona_id parameter to reuse the same singer's voice in future
    songs. Custom-mode + V5/V5.5 only.

    Per Kie.ai docs:
      - source_task_id is the taskId returned from /api/v1/generate
        (or /api/v1/generate/extend)
      - source_audio_id is the sunoData[i].id of the specific track
        within that generation (since each submission has 2 takes)
    """
    body = {
        "taskId": source_task_id,
        "audioId": source_audio_id,
        "name": name,
        "description": description,
    }
    resp = client._post_json(SUNO_PERSONA_GENERATE_PATH, body)
    # Kie semantically-fails the request even when HTTP returns 200,
    # via the code/msg fields in the body. The most common is
    # code=422 / msg="Music does not exist" — happens when Kie's
    # retention window has expired or the taskId was never persisted.
    code = resp.get("code")
    if code is not None and code != 200:
        msg = resp.get("msg") or "unknown error from Kie persona endpoint"
        if "Music does not exist" in msg or code == 422:
            raise PersonaSourceNotFound(
                f"Kie can no longer find the source Suno generation "
                f"(taskId={source_task_id}). This usually means the "
                f"song is too old or was generated before voice-saving "
                f"was wired up. Try generating a fresh song first."
            )
        raise KieError(f"persona endpoint returned code={code}: {msg}")
    data = resp.get("data") or {}
    persona_id = data.get("personaId") or resp.get("personaId")
    if not persona_id:
        raise KieError(f"persona response missing personaId: {resp}")
    return str(persona_id)
