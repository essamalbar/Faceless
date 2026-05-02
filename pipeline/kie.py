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

# successFlag values Kie.ai returns; override via env if upstream changes.
SUCCESS_FLAG = int(os.environ.get("KIE_SUCCESS_FLAG", "1"))
FAILED_FLAGS = {2, 3}

# Internal — replaceable in tests
_SLEEP = time.sleep


class KieError(RuntimeError):
    """Any Kie.ai-side failure (HTTP error, timeout, job failure)."""


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
                urls = response.get("fullResultUrls") or response.get("resultUrls") or []
                if not urls:
                    raise KieError(f"flux task {job_id} succeeded but no fullResultUrls: {resp}")
                return str(urls[0])
            if flag_int in FAILED_FLAGS:
                raise KieError(f"flux task {job_id} successFlag={flag_int}: {resp}")
            _SLEEP(poll_interval_s)
        raise KieError(f"flux task {job_id} did not complete within {timeout_s}s")

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
                raise KieError(f"task {job_id} successFlag={flag_int}: {resp}")
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
    """End-to-end: submit → poll → download. Raises KieError on failure.

    duration_s, seed, negative_prompt are accepted for API stability but
    ignored — Veo does not expose those parameters. Pre-bake any "no
    text/watermark" guidance into `prompt` itself.
    """
    job_id = client.submit_video_job(
        prompt=prompt,
        model=model,
        aspect_ratio=aspect_ratio,
        seed=seed,
        negative_prompt=negative_prompt,
        duration_s=duration_s,
    )
    url = client.wait_for_video(job_id, poll_interval_s=poll_interval_s, timeout_s=timeout_s)
    client.download(url, out_path)
