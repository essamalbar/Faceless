"""Photo → singing music video ("Make me sing this").

Extracts the ~30s hook (highest-energy window) from a finished song's audio,
then drives Kie's Kling AI Avatar (audio-driven lip-sync) with a user photo +
that hook to render a short video of the person performing the song.

External services (Kie, ffmpeg, librosa) are wrapped so tests can monkeypatch
them; the pure hook-selection math (`_best_hook_offset`) is unit-tested
directly. See docs/superpowers/specs/2026-08-14-make-me-sing-this-photo-video-design.md
"""
from __future__ import annotations

import subprocess
from pathlib import Path


def _best_hook_offset(
    rms: list[float], hop_s: float, hook_s: float, total_s: float
) -> float:
    """Pure: given per-frame RMS energy, the frame hop (seconds), the desired
    hook length (seconds) and the track length (seconds), return the START
    offset (seconds) of the highest-energy hook-length window — clamped so the
    window fits inside [0, total_s]. A track shorter than the hook starts at 0.
    """
    win = max(1, round(hook_s / hop_s))
    if len(rms) <= win:
        return 0.0
    # prefix sums → O(n) sliding-window energy
    prefix = [0.0]
    for v in rms:
        prefix.append(prefix[-1] + v)
    best_i, best_sum = 0, -1.0
    for i in range(len(rms) - win + 1):
        s = prefix[i + win] - prefix[i]
        if s > best_sum:
            best_sum, best_i = s, i
    offset = best_i * hop_s
    return max(0.0, min(offset, max(0.0, total_s - hook_s)))


def extract_hook(mp3_path: Path, out_path: Path, hook_s: float = 30.0) -> Path:
    """Write the highest-energy `hook_s`-second window of `mp3_path` to
    `out_path` (mp3). Uses librosa RMS to locate the hook and ffmpeg to trim.
    A track shorter than the hook is copied from the start."""
    import librosa  # lazy: heavy import (numba/scipy)

    y, sr = librosa.load(str(mp3_path), mono=True)
    total_s = len(y) / sr if sr else 0.0
    if total_s <= hook_s:
        offset = 0.0
    else:
        hop = 512
        rms = librosa.feature.rms(y=y, hop_length=hop)[0]
        offset = _best_hook_offset(
            [float(v) for v in rms], hop_s=hop / sr, hook_s=hook_s, total_s=total_s
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-ss", f"{offset:.3f}",
            "-t", f"{hook_s:.3f}",
            "-i", str(mp3_path),
            "-c:a", "libmp3lame", "-b:a", "192k",
            str(out_path),
        ],
        check=True,
        capture_output=True,
    )
    return out_path


def render_avatar(
    *,
    client,
    image_url: str,
    audio_url: str,
    model: str,
    prompt: str,
    out_path: Path,
    poll_interval_s: int = 5,
    # Generous default: a timeout here fails the worker and triggers an
    # auto-refund, but the Kie job may still complete and bill — so waiting too
    # short means real Kie spend with no credit charged. _run_perform passes an
    # explicit 1800s; keep this default comfortably above a queued avatar render.
    timeout_s: int = 1800,
) -> Path:
    """Submit the avatar job (photo + hook audio), wait for the render, and
    download the mp4 to `out_path`. `client` is a KieClient (or a stub)."""
    task_id = client.submit_avatar_job(
        image_url=image_url, audio_url=audio_url, model=model, prompt=prompt)
    video_url = client.wait_for_unified_video(
        task_id, poll_interval_s=poll_interval_s, timeout_s=timeout_s)
    client.download(video_url, out_path)
    return out_path
