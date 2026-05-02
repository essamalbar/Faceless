"""Stage 5 (Shorts mode): clip generation via Kie.ai.

Replaces the still-image stage from the long-form pipeline. Reads the
script's beats, builds a Veo prompt per beat (style suffix + global
setting + beat motion), submits each as a Kie.ai job, downloads the
resulting MP4 to clips/NN.mp4. Resumable per-clip; supports rerolls
with bumped seeds. Refuses to start any run that exceeds max_spend_usd.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

import requests

from pipeline.kie import KieClient, generate_clip
from pipeline.types import Beat, Script

# Style suffix appended to every Veo prompt for visual consistency across clips.
# Veo on Kie.ai does NOT accept a separate negative_prompt — guidance about what
# NOT to show must be baked directly into the prompt text.
#
# This suffix targets @sunstoriz-style: 3D Pixar-quality animation with
# anthropomorphic fruit characters as humans (lemon mother, strawberry son,
# apple doctor, etc.). Photorealistic textures + dramatic emotional lighting.
VIDEO_STYLE_SUFFIX = (
    "3D Pixar-style animation, photorealistic CGI textures, "
    "anthropomorphic fruit characters wearing human clothing "
    "(hijab, traditional thobe, doctor coat, casual t-shirt), "
    "expressive emotional faces with sad detailed eyes, "
    "dramatic cinematic lighting, vertical 9:16 aspect ratio, "
    "high detail, professional rendering, "
    "no text overlay, no watermark, no logo, no captions burned into video"
)
VIDEO_NEGATIVE_PROMPT = ""  # unused (Veo ignores it); kept for API stability
REROLL_SEED_BUMP = 100_000


def clip_seed(title: str, index: int) -> int:
    """Deterministic seed per (title, clip_index). Stable across runs."""
    h = hashlib.sha256(f"shorts::{title}::{index}".encode("utf-8")).hexdigest()
    return int(h[:8], 16)


def build_veo_prompt(beat: Beat, global_setting: str) -> str:
    """Compose the final Veo prompt for one beat."""
    return f"{global_setting}, {beat.english_motion}, {VIDEO_STYLE_SUFFIX}"


class BudgetExceededError(RuntimeError):
    """Raised before any API call when projected spend exceeds the cap."""


def estimate_spend_usd(num_clips: int, clip_duration_s: int, cost_per_sec: float) -> float:
    return num_clips * clip_duration_s * cost_per_sec


def _clip_filename(clips_dir: Path, index: int) -> Path:
    return clips_dir / f"{index:02d}.mp4"


def _record_spend(spend_path: Path, entries: list[dict]) -> None:
    spend_path.parent.mkdir(parents=True, exist_ok=True)
    spend_path.write_text(
        json.dumps({"entries": entries, "ts": datetime.now().isoformat(timespec="seconds")},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def generate_clips(
    client: KieClient,
    script: Script,
    clips_dir: Path,
    spend_log_path: Path,
    *,
    model: str,
    clip_duration_s: int,
    aspect_ratio: str,
    cost_per_second_usd: float,
    max_spend_usd: float,
    poll_interval_s: int,
    poll_timeout_s: int,
    reroll_indices: list[int] | None = None,
) -> None:
    """Render each beat to clips_dir/NN.mp4. Resumable + reroll-aware.

    Budget guard: refuses to start the run if projected spend exceeds max_spend_usd.
    A reroll only re-spends for the rerolled clips, so the guard uses the count
    of clips that would actually be (re)generated this run, not all of them.
    """
    if not script.beats:
        raise ValueError("script has no beats — Shorts mode requires beats[]")

    clips_dir.mkdir(parents=True, exist_ok=True)
    reroll_set = set(reroll_indices or [])

    # Determine which clips actually need to (re)generate this run.
    pending: list[int] = []
    for i, _beat in enumerate(script.beats):
        idx = i + 1
        out_path = _clip_filename(clips_dir, idx)
        already_done = out_path.exists() and idx not in reroll_set
        if not already_done:
            pending.append(idx)

    projected = estimate_spend_usd(len(pending), clip_duration_s, cost_per_second_usd)
    if projected > max_spend_usd:
        raise BudgetExceededError(
            f"projected spend ${projected:.2f} exceeds cap ${max_spend_usd:.2f} "
            f"({len(pending)} clips × {clip_duration_s}s × ${cost_per_second_usd}/s). "
            f"Override with --max-spend or change config.kie.max_spend_usd."
        )

    spend_entries: list[dict] = []
    for i, beat in enumerate(script.beats):
        idx = i + 1
        out_path = _clip_filename(clips_dir, idx)
        if idx not in pending:
            continue  # already on disk, skip

        seed = clip_seed(script.title, i)
        if idx in reroll_set:
            seed += REROLL_SEED_BUMP

        prompt = build_veo_prompt(beat, script.global_setting)
        generate_clip(
            client=client,
            prompt=prompt,
            model=model,
            duration_s=clip_duration_s,
            aspect_ratio=aspect_ratio,
            seed=seed,
            out_path=out_path,
            negative_prompt=VIDEO_NEGATIVE_PROMPT,
            poll_interval_s=poll_interval_s,
            timeout_s=poll_timeout_s,
        )
        spend_entries.append({
            "clip": idx,
            "seed": seed,
            "duration_s": clip_duration_s,
            "cost_usd": clip_duration_s * cost_per_second_usd,
            "model": model,
        })

    if spend_entries:
        _record_spend(spend_log_path, spend_entries)


def _extract_last_frame(clip_path: Path, out_path: Path) -> None:
    """Indirection over pipeline.frames.extract_last_frame for monkeypatching."""
    from pipeline.frames import extract_last_frame
    extract_last_frame(clip_path, out_path)


def _upload_image_get_url(local_path: Path) -> str:
    """Upload a local image to 0x0.st (free, anonymous, no API key) and return
    the public URL so Kie.ai can fetch it.

    0x0.st is a public pastebin; files stay for ~7 days. We only need them for
    a few minutes (the duration of one Veo job), so this fits.
    Tests monkeypatch this function.
    """
    with local_path.open("rb") as f:
        resp = requests.post(
            "https://0x0.st",
            files={"file": (local_path.name, f, "image/png")},
            headers={"User-Agent": "faceless-pipeline/1.0"},
            timeout=60,
        )
    if resp.status_code >= 400:
        raise RuntimeError(
            f"upload to 0x0.st failed: {resp.status_code}: {resp.text[:200]}"
        )
    return resp.text.strip()


def generate_clips_chained(
    client: KieClient,
    script: Script,
    clips_dir: Path,
    last_frames_dir: Path,
    spend_log_path: Path,
    *,
    character_sheet_path: Path,
    model: str,
    aspect_ratio: str,
    cost_per_second_usd: float,
    max_spend_usd: float,
    poll_interval_s: int,
    poll_timeout_s: int,
    reroll_indices: list[int] | None = None,
) -> None:
    """Tier-3 video stage: REFERENCE_2_VIDEO with character sheet + chained last frames.

    For clip 1: image_urls = [character_sheet]
    For clip N (N>1): image_urls = [character_sheet, last_frame_of_clip_(N-1)]

    Per-beat clip duration from `beat.clip_duration_s`.
    """
    if not script.beats:
        raise ValueError("script has no beats — Tier-3 mode requires beats[]")
    clips_dir.mkdir(parents=True, exist_ok=True)
    last_frames_dir.mkdir(parents=True, exist_ok=True)

    reroll_set = set(reroll_indices or [])

    pending_durations: list[float] = []
    for i, beat in enumerate(script.beats):
        idx = i + 1
        out_path = _clip_filename(clips_dir, idx)
        if not (out_path.exists() and idx not in reroll_set):
            pending_durations.append(beat.clip_duration_s)

    projected = sum(pending_durations) * cost_per_second_usd
    if projected > max_spend_usd:
        raise BudgetExceededError(
            f"projected spend ${projected:.2f} exceeds cap ${max_spend_usd:.2f} "
            f"({len(pending_durations)} clips × ${cost_per_second_usd}/s). "
            f"Override with --max-spend or change config.kie.max_spend_usd."
        )

    sheet_url = _upload_image_get_url(character_sheet_path)
    spend_entries: list[dict] = []
    prev_last_frame_url: str | None = None

    for i, beat in enumerate(script.beats):
        idx = i + 1
        out_path = _clip_filename(clips_dir, idx)
        last_frame_path = last_frames_dir / f"{idx:02d}.png"
        if out_path.exists() and idx not in reroll_set:
            # Already done; still need to ensure last-frame is on disk for next iteration.
            if not last_frame_path.exists():
                _extract_last_frame(out_path, last_frame_path)
            prev_last_frame_url = _upload_image_get_url(last_frame_path)
            continue

        prompt = build_veo_prompt(beat, script.global_setting)
        image_urls = [sheet_url]
        if prev_last_frame_url:
            image_urls.append(prev_last_frame_url)

        job_id = client.submit_video_job(
            prompt=prompt,
            model=model,
            aspect_ratio=aspect_ratio,
            generation_type="REFERENCE_2_VIDEO",
            image_urls=image_urls,
            duration_s=beat.clip_duration_s,
        )
        url = client.wait_for_video(
            job_id, poll_interval_s=poll_interval_s, timeout_s=poll_timeout_s,
        )
        client.download(url, out_path)
        _extract_last_frame(out_path, last_frame_path)
        prev_last_frame_url = _upload_image_get_url(last_frame_path)

        spend_entries.append({
            "clip": idx, "seed": clip_seed(script.title, i),
            "duration_s": beat.clip_duration_s,
            "cost_usd": beat.clip_duration_s * cost_per_second_usd,
            "model": model,
        })

    if spend_entries:
        _record_spend(spend_log_path, spend_entries)
