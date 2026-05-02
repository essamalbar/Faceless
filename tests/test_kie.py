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


def test_submit_sends_veo_body_shape(monkeypatch):
    captured: dict = {}

    def fake_post(self, path, body):
        captured["path"] = path
        captured["body"] = body
        return {"code": 200, "msg": "success", "data": {"taskId": "veo_task_abc123"}}

    monkeypatch.setattr(KieClient, "_post_json", fake_post)
    c = _client()
    task_id = c.submit_video_job(
        prompt="P", model="veo3_fast",
        aspect_ratio="9:16", seed=42, duration_s=8,
    )
    assert task_id == "veo_task_abc123"
    assert captured["path"] == "/api/v1/veo/generate"
    # Veo body uses aspectRatio (camelCase) and generationType
    assert captured["body"]["model"] == "veo3_fast"
    assert captured["body"]["aspectRatio"] == "9:16"
    assert captured["body"]["generationType"] == "TEXT_2_VIDEO"
    # Unsupported fields must NOT be in the body (Veo would 400)
    assert "duration_seconds" not in captured["body"]
    assert "seed" not in captured["body"]
    assert "negative_prompt" not in captured["body"]


def test_submit_raises_when_no_task_id(monkeypatch):
    monkeypatch.setattr(KieClient, "_post_json",
                        lambda self, path, body: {"code": 200, "data": {}})
    with pytest.raises(KieError, match="missing taskId"):
        _client().submit_video_job(
            prompt="P", model="veo3_fast", aspect_ratio="9:16",
        )


def test_wait_polls_until_success_flag_1(monkeypatch):
    responses = iter([
        {"data": {"successFlag": 0}},
        {"data": {"successFlag": 0}},
        {"data": {"successFlag": 1, "response": {"fullResultUrls": ["https://cdn.example/clip.mp4"]}}},
    ])
    monkeypatch.setattr(KieClient, "poll_job", lambda self, jid: next(responses))
    monkeypatch.setattr(kie_mod, "_SLEEP", lambda _s: None)
    url = _client().wait_for_video("veo_task_1", poll_interval_s=1, timeout_s=10)
    assert url == "https://cdn.example/clip.mp4"


def test_wait_falls_back_to_resultUrls(monkeypatch):
    monkeypatch.setattr(
        KieClient, "poll_job",
        lambda self, jid: {"data": {"successFlag": 1, "response": {"resultUrls": ["https://u/x.mp4"]}}},
    )
    monkeypatch.setattr(kie_mod, "_SLEEP", lambda _s: None)
    assert _client().wait_for_video("t-1") == "https://u/x.mp4"


def test_wait_raises_on_failed_flag(monkeypatch):
    monkeypatch.setattr(KieClient, "poll_job",
                        lambda self, jid: {"data": {"successFlag": 2, "msg": "censored"}})
    monkeypatch.setattr(kie_mod, "_SLEEP", lambda _s: None)
    with pytest.raises(KieError, match="successFlag=2"):
        _client().wait_for_video("t-1")


def test_wait_raises_on_gen_failed_flag(monkeypatch):
    monkeypatch.setattr(KieClient, "poll_job",
                        lambda self, jid: {"data": {"successFlag": 3}})
    monkeypatch.setattr(kie_mod, "_SLEEP", lambda _s: None)
    with pytest.raises(KieError, match="successFlag=3"):
        _client().wait_for_video("t-1")


def test_wait_raises_on_timeout(monkeypatch):
    monkeypatch.setattr(KieClient, "poll_job",
                        lambda self, jid: {"data": {"successFlag": 0}})
    monkeypatch.setattr(kie_mod, "_SLEEP", lambda _s: None)
    with pytest.raises(KieError, match="did not complete"):
        _client().wait_for_video("t-1", poll_interval_s=0, timeout_s=0)


def test_generate_clip_end_to_end(monkeypatch, tmp_path: Path):
    """submit → poll-completed → download — verified through the orchestrator helper."""
    monkeypatch.setattr(KieClient, "_post_json",
                        lambda self, p, b: {"code": 200, "data": {"taskId": "veo_task_e2e"}})
    monkeypatch.setattr(
        KieClient, "poll_job",
        lambda self, jid: {"data": {"successFlag": 1, "response": {"fullResultUrls": ["https://cdn/clip.mp4"]}}},
    )
    monkeypatch.setattr(kie_mod, "_SLEEP", lambda _s: None)

    download_calls: list = []

    def fake_download(self, url, out_path):
        download_calls.append((url, out_path))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"\x00\x00\x00\x18ftypmp42")

    monkeypatch.setattr(KieClient, "_download", fake_download)

    out = tmp_path / "clips" / "01.mp4"
    generate_clip(
        client=_client(),
        prompt="lone hooded figure walking",
        model="veo3_fast",
        duration_s=8, aspect_ratio="9:16", seed=42,
        out_path=out,
        poll_interval_s=1, timeout_s=10,
    )
    assert out.exists()
    assert out.stat().st_size > 0
    assert download_calls[0][0] == "https://cdn/clip.mp4"
    assert download_calls[0][1] == out


def test_submit_flux_image_job_sends_correct_body(monkeypatch):
    captured: dict = {}

    def fake_post(self, path, body):
        captured["path"] = path
        captured["body"] = body
        return {"code": 200, "data": {"taskId": "flux_task_x"}}

    monkeypatch.setattr(KieClient, "_post_json", fake_post)
    c = _client()
    task_id = c.submit_flux_image_job(
        prompt="character sheet of fruit characters",
        model="flux-1.1-pro",
        aspect_ratio="9:16",
    )
    assert task_id == "flux_task_x"
    assert captured["path"] == "/api/v1/flux/generate"
    assert captured["body"]["model"] == "flux-1.1-pro"
    assert captured["body"]["prompt"].startswith("character sheet")
    assert captured["body"]["aspectRatio"] == "9:16"


def test_poll_flux_returns_image_url(monkeypatch):
    """When successFlag=1, fullResultUrls[0] is the PNG URL."""
    monkeypatch.setattr(
        KieClient, "poll_job",
        lambda self, jid: {"data": {"successFlag": 1,
                                     "response": {"fullResultUrls": ["https://cdn/x.png"]}}},
    )
    monkeypatch.setattr(kie_mod, "_SLEEP", lambda _s: None)
    assert _client().wait_for_video("flux_task_x") == "https://cdn/x.png"
