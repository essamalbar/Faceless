"""Kie.ai HTTP client tests. Real HTTP is replaced via monkeypatch."""
from __future__ import annotations

from pathlib import Path

import pytest

from pipeline import kie as kie_mod
from pipeline.kie import KieClient, KieError, generate_clip


def _client() -> KieClient:
    return KieClient(api_key="k", base_url="https://api.kie.ai")


def test_init_requires_api_key(monkeypatch):
    monkeypatch.delenv("KIE_API_KEY", raising=False)
    with pytest.raises(KieError):
        KieClient()


def test_submit_extracts_job_id_from_top_level(monkeypatch):
    captured: dict = {}

    def fake_post(self, path, body):
        captured["path"] = path
        captured["body"] = body
        return {"job_id": "abc-123"}

    monkeypatch.setattr(KieClient, "_post_json", fake_post)
    c = _client()
    job_id = c.submit_video_job(
        prompt="P", model="veo-3.1-fast", duration_s=7,
        aspect_ratio="9:16", seed=42,
    )
    assert job_id == "abc-123"
    assert captured["body"]["model"] == "veo-3.1-fast"
    assert captured["body"]["duration_seconds"] == 7
    assert captured["body"]["aspect_ratio"] == "9:16"
    assert captured["body"]["seed"] == 42
    assert "negative_prompt" not in captured["body"]


def test_submit_includes_negative_prompt_when_provided(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(KieClient, "_post_json",
                        lambda self, path, body: captured.update(body=body) or {"job_id": "x"})
    _client().submit_video_job(
        prompt="P", model="m", duration_s=5, aspect_ratio="9:16", seed=1,
        negative_prompt="blurry, text",
    )
    assert captured["body"]["negative_prompt"] == "blurry, text"


def test_submit_extracts_job_id_from_nested_data(monkeypatch):
    monkeypatch.setattr(KieClient, "_post_json",
                        lambda self, path, body: {"data": {"id": "nested-789"}})
    assert _client().submit_video_job(
        prompt="P", model="m", duration_s=5, aspect_ratio="9:16", seed=1,
    ) == "nested-789"


def test_submit_raises_when_no_job_id(monkeypatch):
    monkeypatch.setattr(KieClient, "_post_json",
                        lambda self, path, body: {"meaningless": "response"})
    with pytest.raises(KieError, match="missing job_id"):
        _client().submit_video_job(
            prompt="P", model="m", duration_s=5, aspect_ratio="9:16", seed=1,
        )


def test_wait_polls_until_completed(monkeypatch):
    responses = iter([
        {"status": "queued"},
        {"status": "processing"},
        {"status": "completed", "video_url": "https://cdn.example/clip.mp4"},
    ])
    monkeypatch.setattr(KieClient, "poll_job", lambda self, jid: next(responses))
    monkeypatch.setattr(kie_mod, "_SLEEP", lambda _s: None)
    url = _client().wait_for_video("job-1", poll_interval_s=1, timeout_s=10)
    assert url == "https://cdn.example/clip.mp4"


def test_wait_finds_url_in_nested_data(monkeypatch):
    monkeypatch.setattr(KieClient, "poll_job",
                        lambda self, jid: {"data": {"status": "completed", "output_url": "https://u/x.mp4"}})
    monkeypatch.setattr(kie_mod, "_SLEEP", lambda _s: None)
    assert _client().wait_for_video("job-1") == "https://u/x.mp4"


def test_wait_raises_on_failed_status(monkeypatch):
    monkeypatch.setattr(KieClient, "poll_job", lambda self, jid: {"status": "failed", "reason": "censored"})
    monkeypatch.setattr(kie_mod, "_SLEEP", lambda _s: None)
    with pytest.raises(KieError, match="status=failed"):
        _client().wait_for_video("job-1")


def test_wait_raises_on_timeout(monkeypatch):
    monkeypatch.setattr(KieClient, "poll_job", lambda self, jid: {"status": "processing"})
    monkeypatch.setattr(kie_mod, "_SLEEP", lambda _s: None)
    # Use a 0-second timeout so the loop body never executes (deadline reached on first check)
    with pytest.raises(KieError, match="did not complete"):
        _client().wait_for_video("job-1", poll_interval_s=0, timeout_s=0)


def test_generate_clip_end_to_end(monkeypatch, tmp_path: Path):
    """submit → poll-completed → download — verified through the orchestrator helper."""
    monkeypatch.setattr(KieClient, "_post_json", lambda self, p, b: {"job_id": "jid"})
    monkeypatch.setattr(KieClient, "poll_job",
                        lambda self, jid: {"status": "completed", "video_url": "https://cdn/clip.mp4"})
    monkeypatch.setattr(kie_mod, "_SLEEP", lambda _s: None)

    download_calls: list = []

    def fake_download(self, url, out_path):
        download_calls.append((url, out_path))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"\x00\x00\x00\x18ftypmp42")  # mp4 magic

    monkeypatch.setattr(KieClient, "_download", fake_download)

    out = tmp_path / "clips" / "01.mp4"
    generate_clip(
        client=_client(),
        prompt="lone hooded figure walking",
        model="veo-3.1-fast",
        duration_s=7, aspect_ratio="9:16", seed=42,
        out_path=out,
        poll_interval_s=1, timeout_s=10,
    )
    assert out.exists()
    assert out.stat().st_size > 0
    assert download_calls[0][0] == "https://cdn/clip.mp4"
    assert download_calls[0][1] == out
