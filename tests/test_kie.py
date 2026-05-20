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
    assert captured["path"] == "/api/v1/flux/kontext/generate"
    assert captured["body"]["model"] == "flux-1.1-pro"
    assert captured["body"]["prompt"].startswith("character sheet")
    assert captured["body"]["aspectRatio"] == "9:16"
    assert captured["body"]["outputFormat"] == "png"


def test_poll_flux_returns_image_url(monkeypatch):
    """When successFlag=1, fullResultUrls[0] is the PNG URL."""
    monkeypatch.setattr(
        KieClient, "poll_job",
        lambda self, jid: {"data": {"successFlag": 1,
                                     "response": {"fullResultUrls": ["https://cdn/x.png"]}}},
    )
    monkeypatch.setattr(kie_mod, "_SLEEP", lambda _s: None)
    assert _client().wait_for_video("flux_task_x") == "https://cdn/x.png"


def test_submit_reference_video_job_sends_image_urls(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        KieClient, "_post_json",
        lambda self, p, b: captured.update(path=p, body=b) or
        {"code": 200, "data": {"taskId": "ref_task_x"}},
    )
    c = _client()
    task_id = c.submit_video_job(
        prompt="lemon mother gives coins to strawberry son",
        model="veo3", aspect_ratio="9:16", seed=0,
        image_urls=["https://cdn/character_sheet.png",
                    "https://cdn/last_frame_clip_2.png"],
        generation_type="REFERENCE_2_VIDEO",
    )
    assert task_id == "ref_task_x"
    assert captured["body"]["generationType"] == "REFERENCE_2_VIDEO"
    assert captured["body"]["imageUrls"] == [
        "https://cdn/character_sheet.png",
        "https://cdn/last_frame_clip_2.png",
    ]


# ---------------------------------------------------------------------------
# Kling (unified /api/v1/jobs/* endpoints) — different body shape, different
# polling endpoint, different result location than the legacy Veo path.
# These tests pin both v2-1 (singular image_url) and v2-6 (image_urls array)
# variants since the input field name differs.
# ---------------------------------------------------------------------------

def test_is_unified_model_classifies_correctly():
    from pipeline.kie import is_unified_model
    assert is_unified_model("kling/v2-1-standard")
    assert is_unified_model("kling/v2-1-pro")
    assert is_unified_model("kling-2.6/image-to-video")
    assert is_unified_model("kling-3.0/video")
    # Veo + Flux stay on legacy path
    assert not is_unified_model("veo3_fast")
    assert not is_unified_model("veo3")
    assert not is_unified_model("flux-kontext-pro")


def test_submit_unified_v2_1_uses_singular_image_url(monkeypatch):
    """Kling 2.1 family expects input.image_url (string), not array."""
    captured: dict = {}
    monkeypatch.setattr(
        KieClient, "_post_json",
        lambda self, p, b: captured.update(path=p, body=b) or
        {"code": 200, "data": {"taskId": "kling_2_1_task"}},
    )
    c = _client()
    task_id = c.submit_unified_image_to_video(
        prompt="a thief walks into an old house at night",
        image_url="https://cdn/character_sheet.png",
        model="kling/v2-1-standard",
        duration_s=5,
        negative_prompt="blur, distort",
        cfg_scale=0.7,
    )
    assert task_id == "kling_2_1_task"
    assert captured["path"] == "/api/v1/jobs/createTask"
    assert captured["body"]["model"] == "kling/v2-1-standard"
    inp = captured["body"]["input"]
    # Singular image_url, not array
    assert inp["image_url"] == "https://cdn/character_sheet.png"
    assert "image_urls" not in inp
    # Duration MUST be a string ('5' or '10') — Kling rejects integers
    assert inp["duration"] == "5"
    assert inp["negative_prompt"] == "blur, distort"
    assert inp["cfg_scale"] == 0.7


def test_submit_unified_snaps_beat_duration_aggressively_up():
    """The script writer outputs 5-10s beats but Kling only accepts '5' or
    '10'. Snap rule favors '10' for anything ≥6s to avoid truncating
    dialogue. Regression for 2026-05-19-095639 where beat 2 was 7s and
    Kling delivered 5s — losing 2s of intended visual content."""
    from pipeline.kie import KieClient
    captured: dict = {}
    import pipeline.kie as _kie
    orig = KieClient._post_json
    def fake_post(self, p, b):
        captured["body"] = b
        return {"code": 200, "data": {"taskId": "snap_task"}}
    _kie.KieClient._post_json = fake_post
    try:
        c = KieClient(api_key="k")
        for duration_s, expected in [
            (4, "5"),   # short atmospheric beat
            (5, "5"),   # exactly 5
            (6, "10"),  # was '5' before fix — snap UP to preserve content
            (7, "10"),  # was '5' before fix — main bug repro
            (8, "10"),
            (9, "10"),
            (10, "10"),
        ]:
            c.submit_unified_image_to_video(
                prompt="x", image_url="u",
                model="kling/v2-1-pro", duration_s=duration_s,
            )
            assert captured["body"]["input"]["duration"] == expected, \
                f"duration_s={duration_s} should snap to {expected}, " \
                f"got {captured['body']['input']['duration']}"
    finally:
        _kie.KieClient._post_json = orig


def test_submit_unified_v2_6_uses_array_image_urls(monkeypatch):
    """Kling 2.6 family expects input.image_urls (array, max 1)."""
    captured: dict = {}
    monkeypatch.setattr(
        KieClient, "_post_json",
        lambda self, p, b: captured.update(path=p, body=b) or
        {"code": 200, "data": {"taskId": "kling_2_6_task"}},
    )
    c = _client()
    task_id = c.submit_unified_image_to_video(
        prompt="opening scene",
        image_url="https://cdn/character_sheet.png",
        model="kling-2.6/image-to-video",
        duration_s=10,
    )
    assert task_id == "kling_2_6_task"
    inp = captured["body"]["input"]
    # Array form, with the single character_sheet inside
    assert inp["image_urls"] == ["https://cdn/character_sheet.png"]
    assert "image_url" not in inp
    assert inp["duration"] == "10"
    # 2.6 default sound=False (we use ElevenLabs for narration; sound=True
    # doubles the Kling cost).
    assert inp["sound"] is False


def test_submit_unified_refuses_non_unified_model():
    """Belt-and-suspenders — passing a Veo model id to the Kling path
    raises, instead of silently sending a bad request body."""
    with pytest.raises(KieError, match="non-unified"):
        _client().submit_unified_image_to_video(
            prompt="x", image_url="u", model="veo3_fast",
        )


def test_wait_unified_parses_resultJson_string(monkeypatch):
    """recordInfo returns resultJson as a STRING (not parsed JSON). The
    wait helper must json.loads it before reading resultUrls."""
    monkeypatch.setattr(
        KieClient, "_get_json",
        lambda self, path: {
            "data": {
                "state": "success",
                "resultJson": '{"resultUrls": ["https://cdn/clip.mp4"]}',
            },
        },
    )
    monkeypatch.setattr(kie_mod, "_SLEEP", lambda _s: None)
    url = _client().wait_for_unified_video("kling_task_x", poll_interval_s=0)
    assert url == "https://cdn/clip.mp4"


def test_wait_unified_polls_until_success(monkeypatch):
    """state cycles pending → success."""
    states = iter([
        {"data": {"state": "pending"}},
        {"data": {"state": "pending"}},
        {"data": {"state": "success",
                  "resultJson": '{"resultUrls": ["https://cdn/k.mp4"]}'}},
    ])
    monkeypatch.setattr(KieClient, "_get_json",
                        lambda self, p: next(states))
    monkeypatch.setattr(kie_mod, "_SLEEP", lambda _s: None)
    assert _client().wait_for_unified_video("t-1", poll_interval_s=0) \
        == "https://cdn/k.mp4"


def test_wait_unified_raises_on_fail(monkeypatch):
    monkeypatch.setattr(
        KieClient, "_get_json",
        lambda self, path: {
            "data": {"state": "fail", "failCode": 422, "failMsg": "content policy"},
        },
    )
    monkeypatch.setattr(kie_mod, "_SLEEP", lambda _s: None)
    with pytest.raises(KieError, match="failed"):
        _client().wait_for_unified_video("kling_bad")


def test_wait_unified_classifies_transient_failures(monkeypatch):
    """'try again later' / 'rate limit' messages route to TransientKieError
    so callers can retry with backoff instead of bubbling a permanent error."""
    from pipeline.kie import TransientKieError
    monkeypatch.setattr(
        KieClient, "_get_json",
        lambda self, path: {
            "data": {"state": "fail", "failCode": 503,
                     "failMsg": "Service temporarily unavailable, try again later"},
        },
    )
    monkeypatch.setattr(kie_mod, "_SLEEP", lambda _s: None)
    with pytest.raises(TransientKieError):
        _client().wait_for_unified_video("k-transient")


def test_generate_unified_clip_end_to_end(monkeypatch, tmp_path: Path):
    """Full Kling round-trip via the public helper."""
    from pipeline.kie import generate_unified_clip
    # Submit + poll
    monkeypatch.setattr(
        KieClient, "_post_json",
        lambda self, p, b: {"code": 200, "data": {"taskId": "k_e2e"}},
    )
    monkeypatch.setattr(
        KieClient, "_get_json",
        lambda self, p: {
            "data": {"state": "success",
                     "resultJson": '{"resultUrls": ["https://cdn/k_e2e.mp4"]}'},
        },
    )
    monkeypatch.setattr(kie_mod, "_SLEEP", lambda _s: None)

    download_calls: list = []
    def fake_download(self, url, out_path):
        download_calls.append((url, out_path))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"\x00\x00\x00\x18ftypmp42")
    monkeypatch.setattr(KieClient, "_download", fake_download)

    out = tmp_path / "clips" / "01.mp4"
    generate_unified_clip(
        client=_client(),
        prompt="opening shot",
        image_url="https://cdn/sheet.png",
        model="kling/v2-1-standard",
        duration_s=5,
        out_path=out,
    )
    assert out.exists()
    assert download_calls[0][0] == "https://cdn/k_e2e.mp4"
