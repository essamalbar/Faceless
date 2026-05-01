"""Kie.ai HTTP client for video generation (Veo 3.1 family).

Kie.ai's full API spec is paywalled / behind login, so this module
isolates the HTTP details so they're easy to adjust once you have
access to the dashboard. Replace `BASE_URL` and the three endpoint
constants below with whatever the dashboard shows; everything else
in the pipeline calls this module through `generate_clip`.

Auth: Bearer token (`Authorization: Bearer <KIE_API_KEY>`).
Pattern: async — POST to submit returns a job_id, GET polled until
status indicates done, then download the resulting MP4.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import requests

# --- API surface (adjust to match your Kie.ai dashboard once you have access) ---
BASE_URL = os.environ.get("KIE_BASE_URL", "https://api.kie.ai")
SUBMIT_PATH = os.environ.get("KIE_SUBMIT_PATH", "/v1/video/generate")
JOB_PATH_TPL = os.environ.get("KIE_JOB_PATH_TPL", "/v1/jobs/{job_id}")

# Status string Kie.ai returns when the job is finished. Override via env if different.
COMPLETED_STATUS = os.environ.get("KIE_COMPLETED_STATUS", "completed")
FAILED_STATUSES = {"failed", "error", "cancelled"}

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
        duration_s: int,
        aspect_ratio: str,
        seed: int,
        negative_prompt: str | None = None,
    ) -> str:
        """Submit a video-generation job; return the job_id."""
        body = {
            "model": model,
            "prompt": prompt,
            "duration_seconds": duration_s,
            "aspect_ratio": aspect_ratio,
            "seed": seed,
        }
        if negative_prompt:
            body["negative_prompt"] = negative_prompt
        resp = self._post_json(SUBMIT_PATH, body)
        # Kie.ai responses have varied wrapping in the wild; accept several common shapes.
        job_id = (
            resp.get("job_id")
            or resp.get("id")
            or (resp.get("data") or {}).get("job_id")
            or (resp.get("data") or {}).get("id")
        )
        if not job_id:
            raise KieError(f"submit response missing job_id: {resp}")
        return str(job_id)

    def poll_job(self, job_id: str) -> dict:
        """Single GET on the job status endpoint. Returns parsed JSON."""
        return self._get_json(JOB_PATH_TPL.format(job_id=job_id))

    def wait_for_video(
        self, job_id: str, poll_interval_s: int = 5, timeout_s: int = 300,
    ) -> str:
        """Poll until the job succeeds. Returns the output video URL."""
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            data = self.poll_job(job_id)
            status = str(
                data.get("status")
                or (data.get("data") or {}).get("status")
                or ""
            ).lower()
            if status == COMPLETED_STATUS:
                url = (
                    data.get("output_url")
                    or data.get("video_url")
                    or (data.get("output") or {}).get("url")
                    or (data.get("data") or {}).get("output_url")
                    or (data.get("data") or {}).get("video_url")
                )
                if not url:
                    raise KieError(f"job {job_id} completed but no video URL: {data}")
                return str(url)
            if status in FAILED_STATUSES:
                raise KieError(f"job {job_id} status={status}: {data}")
            _SLEEP(poll_interval_s)
        raise KieError(f"job {job_id} did not complete within {timeout_s}s")

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
        with requests.get(url, stream=True, timeout=120) as r:
            if r.status_code >= 400:
                raise KieError(f"download {url} → {r.status_code}")
            with out_path.open("wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 16):
                    if chunk:
                        f.write(chunk)

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
    """End-to-end: submit → poll → download. Raises KieError on failure."""
    job_id = client.submit_video_job(
        prompt=prompt,
        model=model,
        duration_s=duration_s,
        aspect_ratio=aspect_ratio,
        seed=seed,
        negative_prompt=negative_prompt,
    )
    url = client.wait_for_video(job_id, poll_interval_s=poll_interval_s, timeout_s=timeout_s)
    client.download(url, out_path)
