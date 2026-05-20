"""Kie.ai HTTP client for Veo 3 video generation.

Verified against Kie.ai's Veo 3 API docs (Nov 2025):
  - POST /api/v1/veo/generate     submits a job, returns {data: {taskId}}
  - GET  /api/v1/veo/record-info?taskId=...  polls; returns successFlag
        (0=generating, 1=success, 2=failed, 3=gen-failed) and
        data.response.fullResultUrls[] when complete.

Auth: Bearer token (`Authorization: Bearer <KIE_API_KEY>`).
Pattern: async — submit → poll until successFlag==1 → download mp4.

Veo body fields supported (others rejected as 400):
  - prompt (required)
  - model: 'veo3' | 'veo3_fast' | 'veo3_lite'
  - aspectRatio: '9:16' | '16:9' | 'Auto'
  - generationType: 'TEXT_2_VIDEO' (default) | 'FIRST_AND_LAST_FRAMES_2_VIDEO' | 'REFERENCE_2_VIDEO'
  - resolution: '720p' | '1080p' | '4k'
  - imageUrls, callBackUrl, enableTranslation, watermark
NOT supported: seed, negative_prompt, duration_seconds.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import requests

BASE_URL = os.environ.get("KIE_BASE_URL", "https://api.kie.ai")
SUBMIT_PATH = os.environ.get("KIE_SUBMIT_PATH", "/api/v1/veo/generate")
FLUX_SUBMIT_PATH = os.environ.get("KIE_FLUX_SUBMIT_PATH", "/api/v1/flux/kontext/generate")
# Flux job status uses a SEPARATE poll endpoint than Veo (different namespace).
FLUX_JOB_PATH_TPL = os.environ.get(
    "KIE_FLUX_JOB_PATH_TPL", "/api/v1/flux/kontext/record-info?taskId={job_id}"
)
JOB_PATH_TPL = os.environ.get("KIE_JOB_PATH_TPL", "/api/v1/veo/record-info?taskId={job_id}")

# Unified jobs endpoint — used by Kling, Runway, Hailuo, Seedance, and every
# model added after Kie's API consolidation. Different request shape from
# the legacy Veo endpoint above (nested `input` object instead of flat body)
# and different polling endpoint with `state: success|fail` instead of
# successFlag integers. Keep both paths until the Veo legacy endpoint gets
# retired upstream.
JOBS_CREATETASK_PATH = os.environ.get(
    "KIE_JOBS_CREATETASK_PATH", "/api/v1/jobs/createTask",
)
JOBS_RECORDINFO_PATH_TPL = os.environ.get(
    "KIE_JOBS_RECORDINFO_PATH_TPL", "/api/v1/jobs/recordInfo?taskId={task_id}",
)

# successFlag values Kie.ai returns; override via env if upstream changes.
SUCCESS_FLAG = int(os.environ.get("KIE_SUCCESS_FLAG", "1"))
FAILED_FLAGS = {2, 3}

# Model id prefixes that route through the unified /jobs endpoint. Anything
# matching is sent to submit_unified_image_to_video. Anything else uses the
# legacy Veo path. Keep this list ordered most-specific first.
_KLING_MODEL_PREFIXES = ("kling/", "kling-")
_UNIFIED_MODEL_PREFIXES = _KLING_MODEL_PREFIXES


def is_unified_model(model: str) -> bool:
    """True for models routed through /api/v1/jobs/createTask (Kling et al)."""
    return any(model.startswith(p) for p in _UNIFIED_MODEL_PREFIXES)

# Internal — replaceable in tests
_SLEEP = time.sleep


class KieError(RuntimeError):
    """Any Kie.ai-side failure (HTTP error, timeout, job failure)."""


class TransientKieError(KieError):
    """Recoverable Kie failure — capacity / rate-limit / 'try again later'.
    Callers should retry with exponential backoff."""


class KieClient:
    """Thin sync HTTP client. Tests monkeypatch _post_json / _get_json / _download."""

    def __init__(self, api_key: str | None = None, base_url: str = BASE_URL):
        key = api_key or os.environ.get("KIE_API_KEY")
        if not key:
            raise KieError("KIE_API_KEY not set")
        self._key = key
        self._base = base_url.rstrip("/")

    # --- public ---

    def submit_video_job(
        self,
        prompt: str,
        model: str,
        aspect_ratio: str,
        seed: int | None = None,           # ignored
        negative_prompt: str | None = None,  # ignored
        duration_s: int | None = None,       # ignored
        generation_type: str = "TEXT_2_VIDEO",
        resolution: str = "720p",
        image_urls: list[str] | None = None,  # NEW
    ) -> str:
        """Submit a Veo job; return the taskId.

        For REFERENCE_2_VIDEO / FIRST_AND_LAST_FRAMES_2_VIDEO modes, pass
        `image_urls` (a list of public-accessible image URLs).
        """
        body: dict = {
            "model": model,
            "prompt": prompt,
            "aspectRatio": aspect_ratio,
            "generationType": generation_type,
            "resolution": resolution,
            # Defensive: keep Arabic dialogue inside the prompt verbatim.
            # If translation were on, Kie.ai might rewrite the quoted line
            # to English and Veo would speak English instead of Arabic.
            "enableTranslation": False,
        }
        if image_urls:
            body["imageUrls"] = image_urls
        resp = self._post_json(SUBMIT_PATH, body)
        # Veo wrapper: {code, msg, data: {taskId}}
        data = resp.get("data") or {}
        task_id = data.get("taskId") or resp.get("taskId") or data.get("task_id")
        if not task_id:
            raise KieError(f"submit response missing taskId: {resp}")
        return str(task_id)

    def submit_flux_image_job(
        self,
        prompt: str,
        model: str = "flux-kontext-pro",
        aspect_ratio: str = "9:16",
        image_urls: list[str] | None = None,
        output_format: str = "png",
    ) -> str:
        """Submit a Flux Kontext text-to-image (or image-to-image) job; return taskId.

        Body fields documented at https://docs.kie.ai/flux-kontext-api .
        Use wait_for_flux_image() to poll, NOT wait_for_video() — Flux Kontext has
        its own record-info endpoint distinct from Veo's.
        """
        body: dict = {
            "model": model,
            "prompt": prompt,
            "aspectRatio": aspect_ratio,
            "outputFormat": output_format,
            "enableTranslation": True,
            "promptUpsampling": False,
            "safetyTolerance": 2,
        }
        if image_urls:
            body["inputImage"] = image_urls[0]  # Flux Kontext takes one input image
        resp = self._post_json(FLUX_SUBMIT_PATH, body)
        data = resp.get("data") or {}
        task_id = data.get("taskId") or resp.get("taskId")
        if not task_id:
            raise KieError(f"flux submit response missing taskId: {resp}")
        return str(task_id)

    def wait_for_flux_image(
        self, job_id: str, poll_interval_s: int = 5, timeout_s: int = 300,
    ) -> str:
        """Poll the Flux Kontext record-info endpoint until success; return image URL.

        Same response shape as Veo (data.successFlag + data.response.fullResultUrls),
        but the poll path differs.
        """
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            resp = self._get_json(FLUX_JOB_PATH_TPL.format(job_id=job_id))
            data = resp.get("data") or {}
            flag = data.get("successFlag")
            if flag is None:
                flag = resp.get("successFlag")
            try:
                flag_int = int(flag) if flag is not None else None
            except (TypeError, ValueError):
                flag_int = None
            if flag_int == SUCCESS_FLAG:
                response = data.get("response") or {}
                # Flux Kontext returns a single resultImageUrl; older shapes used arrays.
                single = response.get("resultImageUrl")
                urls = (
                    response.get("fullResultUrls")
                    or response.get("resultUrls")
                    or ([single] if single else [])
                )
                if not urls:
                    raise KieError(f"flux task {job_id} succeeded but no result URL: {resp}")
                return str(urls[0])
            if flag_int in FAILED_FLAGS:
                raise KieError(f"flux task {job_id} successFlag={flag_int}: {resp}")
            _SLEEP(poll_interval_s)
        raise KieError(f"flux task {job_id} did not complete within {timeout_s}s")

    def submit_unified_image_to_video(
        self,
        *,
        prompt: str,
        image_url: str,
        model: str,
        duration_s: int = 5,
        negative_prompt: str | None = None,
        cfg_scale: float | None = None,
        sound: bool = False,
    ) -> str:
        """Submit an image-to-video job via the unified /jobs/createTask endpoint.

        Used for Kling (and any future model hosted under this endpoint).
        Field shape inside `input` differs by model family:
          - kling/v2-1-*       → input.image_url (singular string), optional
                                 negative_prompt + cfg_scale
          - kling-2.6/*        → input.image_urls (array, max 1 item), optional
                                 sound boolean (audio adds 2x to cost)
        Duration is passed as a string ('5' or '10') — Kling rejects integers.
        """
        if not is_unified_model(model):
            raise KieError(
                f"submit_unified_image_to_video called with non-unified model "
                f"{model!r} — use submit_video_job for Veo"
            )
        # Kling only accepts duration_s ∈ {5, 10}. Beat durations from the
        # script writer are 5-10s; we snap aggressively UPWARD because
        # cutting a 7s beat to 5s truncates 2s of intended visual
        # content. Anything ≥6 → 10; only short atmospheric beats (≤5s)
        # stay at 5. Was 1-7 → 5; 8+ → 10 (lost content on 6s and 7s
        # beats — verified on 2026-05-19-095639 where beat 2 was 7s and
        # rendered at 5s).
        snapped = 5 if int(duration_s) <= 5 else 10
        input_block: dict = {
            "prompt": prompt,
            "duration": str(snapped),
        }
        if model.startswith("kling-2.6/") or model.startswith("kling-2.5") \
                or model.startswith("kling-3"):
            # Newer families use array + optional sound. Sound on costs 2x;
            # default off because narration is handled by ElevenLabs.
            input_block["image_urls"] = [image_url]
            input_block["sound"] = sound
        else:
            # 2.1 family — singular image_url field, plus cfg_scale + negative_prompt
            input_block["image_url"] = image_url
            if negative_prompt:
                input_block["negative_prompt"] = negative_prompt
            if cfg_scale is not None:
                input_block["cfg_scale"] = cfg_scale
        body = {"model": model, "input": input_block}
        resp = self._post_json(JOBS_CREATETASK_PATH, body)
        data = resp.get("data") or {}
        task_id = data.get("taskId") or resp.get("taskId")
        if not task_id:
            raise KieError(f"unified submit response missing taskId: {resp}")
        return str(task_id)

    def wait_for_unified_video(
        self, task_id: str, poll_interval_s: int = 5, timeout_s: int = 600,
    ) -> str:
        """Poll /jobs/recordInfo until state=='success'; return first resultUrl.

        Used for Kling and other models that route through the unified
        /jobs/createTask endpoint. Response shape:
          {data: {state: 'success'|'fail', resultJson: '<json-string>',
                  failCode, failMsg}}
        resultJson is a STRING that needs JSON-parsing — Kie did not normalize
        this for us.
        """
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            resp = self._get_json(JOBS_RECORDINFO_PATH_TPL.format(task_id=task_id))
            data = resp.get("data") or {}
            state = (data.get("state") or "").lower()
            if state == "success":
                raw = data.get("resultJson")
                if isinstance(raw, str):
                    try:
                        parsed = json.loads(raw)
                    except json.JSONDecodeError as e:
                        raise KieError(
                            f"task {task_id} success but resultJson not "
                            f"valid JSON: {e}; raw={raw[:200]!r}"
                        )
                else:
                    parsed = raw or {}
                urls = parsed.get("resultUrls") or []
                if not urls:
                    raise KieError(
                        f"task {task_id} succeeded but no resultUrls: {resp}"
                    )
                return str(urls[0])
            if state == "fail":
                fail_msg = (data.get("failMsg") or "").lower()
                transient_markers = (
                    "temporarily unavailable",
                    "try again later",
                    "high traffic",
                    "rate limit",
                    "rate-limit",
                    "too many requests",
                    "service unavailable",
                )
                err_class = TransientKieError if any(
                    m in fail_msg for m in transient_markers
                ) else KieError
                raise err_class(
                    f"task {task_id} failed: failCode={data.get('failCode')} "
                    f"failMsg={data.get('failMsg')!r}"
                )
            _SLEEP(poll_interval_s)
        raise KieError(f"task {task_id} did not complete within {timeout_s}s")

    def poll_job(self, job_id: str) -> dict:
        """Single GET on the record-info endpoint. Returns parsed JSON."""
        return self._get_json(JOB_PATH_TPL.format(job_id=job_id))

    def wait_for_video(
        self, job_id: str, poll_interval_s: int = 5, timeout_s: int = 300,
    ) -> str:
        """Poll until successFlag==1; return the output video URL."""
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            resp = self.poll_job(job_id)
            data = resp.get("data") or {}
            flag = data.get("successFlag")
            if flag is None:
                # Some payloads put it at top level
                flag = resp.get("successFlag")
            try:
                flag_int = int(flag) if flag is not None else None
            except (TypeError, ValueError):
                flag_int = None

            if flag_int == SUCCESS_FLAG:
                response = data.get("response") or {}
                urls = response.get("fullResultUrls") or response.get("resultUrls") or []
                if not urls:
                    raise KieError(f"task {job_id} succeeded but no fullResultUrls: {resp}")
                return str(urls[0])
            if flag_int in FAILED_FLAGS:
                err_msg = (
                    (data.get("errorMessage") or "").lower()
                    + " " + (resp.get("errorMessage") or "").lower()
                )
                transient_markers = (
                    "temporarily unavailable",
                    "try again later",
                    "high traffic",
                    "rate limit",
                    "rate-limit",
                    "too many requests",
                    "service unavailable",
                )
                err_class = TransientKieError if any(
                    m in err_msg for m in transient_markers
                ) else KieError
                raise err_class(f"task {job_id} successFlag={flag_int}: {resp}")
            _SLEEP(poll_interval_s)
        raise KieError(f"task {job_id} did not complete within {timeout_s}s")

    def download(self, url: str, out_path: Path) -> None:
        """Stream-download the produced MP4 to disk."""
        out_path.parent.mkdir(parents=True, exist_ok=True)
        self._download(url, out_path)

    # --- low-level (replaceable in tests) ---

    def _post_json(self, path: str, body: dict) -> dict:
        url = f"{self._base}{path}"
        resp = requests.post(url, json=body, headers=self._headers(), timeout=30)
        if resp.status_code >= 400:
            raise KieError(f"POST {path} → {resp.status_code}: {resp.text[:500]}")
        return resp.json()

    def _get_json(self, path: str) -> dict:
        url = f"{self._base}{path}"
        resp = requests.get(url, headers=self._headers(), timeout=30)
        if resp.status_code >= 400:
            raise KieError(f"GET {path} → {resp.status_code}: {resp.text[:500]}")
        return resp.json()

    def _download(self, url: str, out_path: Path) -> None:
        """Stream a video URL to disk. Retries transient connection resets.

        If KIE_DOWNLOAD_PROXY is set, route the GET through that Cloudflare
        Worker (workaround for ISPs that block the upstream CDN host at the
        SNI level). The proxy URL receives ?url=<encoded>&k=<secret>; the
        worker fetches the upstream from inside Cloudflare and re-streams
        the bytes — see cloudflare-worker/README.md.
        """
        from urllib.parse import quote
        proxy_base = os.environ.get("KIE_DOWNLOAD_PROXY", "").rstrip("/")
        if proxy_base:
            secret = os.environ.get("KIE_DOWNLOAD_PROXY_SECRET", "")
            request_url = f"{proxy_base}/?url={quote(url, safe='')}"
            if secret:
                request_url += f"&k={quote(secret, safe='')}"
        else:
            request_url = url

        attempts = 4
        backoffs = (2, 8, 30, 60)
        last_exc: Exception | None = None
        for attempt in range(attempts):
            try:
                with requests.get(request_url, stream=True, timeout=180) as r:
                    if r.status_code >= 400:
                        raise KieError(f"download {url} → {r.status_code}: {r.text[:200]}")
                    with out_path.open("wb") as f:
                        for chunk in r.iter_content(chunk_size=1 << 16):
                            if chunk:
                                f.write(chunk)
                return  # success
            except (requests.exceptions.ConnectionError,
                    requests.exceptions.ChunkedEncodingError,
                    requests.exceptions.Timeout) as e:
                last_exc = e
                # Make sure a partial file doesn't get accepted as 'done' by skip-logic
                try:
                    out_path.unlink(missing_ok=True)
                except Exception:
                    pass
                if attempt < attempts - 1:
                    print(f"[kie] download retry {attempt+1}/{attempts} for {url}: "
                          f"{type(e).__name__}: {e}")
                    _SLEEP(backoffs[attempt])
        raise KieError(
            f"download failed after {attempts} attempts (URL: {url}): {last_exc}"
        )

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._key}",
            "Content-Type": "application/json",
        }


def submit_and_wait_with_retry(
    client: "KieClient",
    *,
    submit_kwargs: dict,
    poll_interval_s: int,
    timeout_s: int,
    max_attempts: int = 4,
    seed_bump: int = 100_000,
) -> str:
    """Submit + poll a Veo job; auto-retry on transient failures.

    Each retry submits a FRESH job (new taskId) with the seed bumped by
    `seed_bump` to avoid hitting the same content-flag if any. Backoff is
    exponential: 30s, 60s, 120s between retries.

    Permanent errors (content-flag, auth, missing API key) bubble through
    on the first attempt — no retry.
    """
    backoffs_s = (30, 60, 120, 240)
    last_err: TransientKieError | None = None
    submit_kwargs = dict(submit_kwargs)  # don't mutate caller's dict
    seed = submit_kwargs.get("seed")

    for attempt in range(max_attempts):
        if attempt > 0 and seed is not None:
            submit_kwargs["seed"] = seed + attempt * seed_bump
        try:
            job_id = client.submit_video_job(**submit_kwargs)
            return client.wait_for_video(
                job_id, poll_interval_s=poll_interval_s, timeout_s=timeout_s,
            )
        except TransientKieError as e:
            last_err = e
            if attempt + 1 >= max_attempts:
                break
            wait = backoffs_s[min(attempt, len(backoffs_s) - 1)]
            print(
                f"[kie] transient failure on attempt {attempt+1}/{max_attempts}: "
                f"{e}; retrying in {wait}s with seed bumped"
            )
            _SLEEP(wait)
            continue

    assert last_err is not None
    raise last_err


def generate_clip(
    client: KieClient,
    prompt: str,
    model: str,
    duration_s: int,
    aspect_ratio: str,
    seed: int,
    out_path: Path,
    negative_prompt: str | None = None,
    poll_interval_s: int = 5,
    timeout_s: int = 300,
) -> None:
    """End-to-end: submit → poll (with auto-retry on transient failures)
    → download. Raises KieError on permanent failure."""
    url = submit_and_wait_with_retry(
        client,
        submit_kwargs={
            "prompt": prompt,
            "model": model,
            "aspect_ratio": aspect_ratio,
            "seed": seed,
            "negative_prompt": negative_prompt,
            "duration_s": duration_s,
        },
        poll_interval_s=poll_interval_s,
        timeout_s=timeout_s,
    )
    client.download(url, out_path)
    # Move moov atom to the front so HTML5 players can stream progressively
    # instead of waiting for the full file. Silent no-op on failure.
    from pipeline.mp4_faststart import rewrite_with_faststart
    rewrite_with_faststart(out_path)


def generate_unified_clip(
    client: KieClient,
    *,
    prompt: str,
    image_url: str,
    model: str,
    duration_s: int,
    out_path: Path,
    negative_prompt: str | None = None,
    cfg_scale: float | None = None,
    sound: bool = False,
    poll_interval_s: int = 5,
    timeout_s: int = 600,
) -> None:
    """End-to-end Kling-family image-to-video: submit → poll → download.

    `image_url` is REQUIRED — Kling has no text-only mode in our pipeline.
    The character_sheet upload from pipeline/video.py is the canonical
    source so identity is locked the same way across every clip.

    timeout_s defaults higher than Veo (600 vs 300) because Kling queues
    can take longer on the cheaper tiers — observed 4-6 min for Standard.
    """
    if not is_unified_model(model):
        raise KieError(
            f"generate_unified_clip called with non-unified model {model!r}"
        )
    submit_kwargs = {
        "prompt": prompt,
        "image_url": image_url,
        "model": model,
        "duration_s": duration_s,
    }
    if negative_prompt:
        submit_kwargs["negative_prompt"] = negative_prompt
    if cfg_scale is not None:
        submit_kwargs["cfg_scale"] = cfg_scale
    if sound:
        submit_kwargs["sound"] = sound

    # Per-call retry on TransientKieError. Mirror Veo's retry policy
    # (4 attempts, exponential backoff 30/60/120/240s).
    backoffs_s = (30, 60, 120, 240)
    last_err: TransientKieError | None = None
    for attempt in range(4):
        try:
            task_id = client.submit_unified_image_to_video(**submit_kwargs)
            url = client.wait_for_unified_video(
                task_id, poll_interval_s=poll_interval_s, timeout_s=timeout_s,
            )
            break
        except TransientKieError as e:
            last_err = e
            if attempt + 1 >= 4:
                raise
            wait = backoffs_s[min(attempt, len(backoffs_s) - 1)]
            print(
                f"[kie] transient unified-submit failure {attempt+1}/4: "
                f"{e}; retrying in {wait}s"
            )
            _SLEEP(wait)
    else:
        assert last_err is not None
        raise last_err

    client.download(url, out_path)
    from pipeline.mp4_faststart import rewrite_with_faststart
    rewrite_with_faststart(out_path)
