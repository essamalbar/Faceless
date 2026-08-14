from __future__ import annotations

import pytest

from pipeline.kie import KieClient, KieError
from pipeline.perform import _best_hook_offset, render_avatar


# --- hook selection (pure) --------------------------------------------------

def test_best_hook_offset_picks_energy_peak():
    # low(0-10s) / high(10-20s) / low(20-30s); a 10s hook must land on the peak.
    rms = [0.0] * 10 + [1.0] * 10 + [0.0] * 10
    assert _best_hook_offset(rms, hop_s=1.0, hook_s=10.0, total_s=30.0) == 10.0


def test_best_hook_offset_clamps_window_into_track():
    # flat energy near the end → offset must keep the window inside [0, total].
    rms = [1.0] * 30
    off = _best_hook_offset(rms, hop_s=1.0, hook_s=10.0, total_s=30.0)
    assert 0.0 <= off <= 20.0


def test_best_hook_offset_short_track_returns_zero():
    # track shorter than the hook → start at 0.
    assert _best_hook_offset([1.0, 2.0], hop_s=1.0, hook_s=30.0, total_s=2.0) == 0.0


# --- kie avatar submit ------------------------------------------------------

def test_submit_avatar_job_posts_image_and_audio(monkeypatch):
    client = KieClient(api_key="stub")
    captured: dict = {}

    def fake_post(path, body):
        captured["path"] = path
        captured["body"] = body
        return {"data": {"taskId": "task-123"}}

    monkeypatch.setattr(client, "_post_json", fake_post)
    tid = client.submit_avatar_job(
        image_url="http://img", audio_url="http://aud", model="kling/ai-avatar")
    assert tid == "task-123"
    assert captured["body"]["model"] == "kling/ai-avatar"
    assert captured["body"]["input"]["image_url"] == "http://img"
    assert captured["body"]["input"]["audio_url"] == "http://aud"


def test_submit_avatar_job_missing_taskid_raises(monkeypatch):
    client = KieClient(api_key="stub")
    monkeypatch.setattr(client, "_post_json", lambda p, b: {"data": {}})
    with pytest.raises(KieError):
        client.submit_avatar_job(image_url="i", audio_url="a", model="m")


# --- orchestration ----------------------------------------------------------

def test_render_avatar_submits_waits_downloads(monkeypatch, tmp_path):
    client = KieClient(api_key="stub")
    seen: dict = {}
    monkeypatch.setattr(client, "submit_avatar_job", lambda **k: "t1")
    monkeypatch.setattr(
        client, "wait_for_unified_video", lambda tid, **k: "http://video.mp4")

    def fake_dl(url, out):
        seen["url"] = url
        out.write_text("mp4")

    monkeypatch.setattr(client, "download", fake_dl)
    out = tmp_path / "perform.mp4"
    render_avatar(client=client, image_url="i", audio_url="a", model="m", out_path=out)
    assert seen["url"] == "http://video.mp4"
    assert out.exists()
