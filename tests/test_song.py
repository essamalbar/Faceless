from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from pipeline import song
from pipeline.kie import KieClient


def _stub_client(post_resp=None, get_resps=None):
    """Build a KieClient with _post_json / _get_json mocked."""
    c = KieClient(api_key="fake-key")
    c._post_json = MagicMock(return_value=post_resp or {})
    if get_resps is not None:
        c._get_json = MagicMock(side_effect=get_resps)
    return c


def test_submit_song_job_returns_task_id():
    c = _stub_client(post_resp={"code": 200, "data": {"taskId": "fake-123"}})
    task_id = song.submit_song_job(
        c,
        lyrics="[Verse 1]\nhello\n[Chorus]\nworld",
        style_prompt="Arabic pop ballad, 72 BPM",
        title="Test",
    )
    assert task_id == "fake-123"
    args, _ = c._post_json.call_args
    path, body = args[0], args[1]
    assert path == song.SUNO_GENERATE_PATH
    assert body["model"] == song.SUNO_MODEL_ID
    assert body["prompt"] == "[Verse 1]\nhello\n[Chorus]\nworld"
    assert body["style"] == "Arabic pop ballad, 72 BPM"
    assert body["title"] == "Test"
    assert body["customMode"] is True
    assert body["instrumental"] is False
    assert isinstance(body.get("callBackUrl"), str) and len(body["callBackUrl"]) > 0


def test_wait_for_song_returns_both_take_urls():
    success_resp = {
        "code": 200,
        "data": {
            "status": "SUCCESS",
            "response": {
                "sunoData": [
                    {"id": "uuid-1", "audioUrl": "https://kie.ai/take1.mp3",
                     "streamAudioUrl": "https://kie.ai/stream1", "imageUrl": "x.jpg"},
                    {"id": "uuid-2", "audioUrl": "https://kie.ai/take2.mp3",
                     "streamAudioUrl": "https://kie.ai/stream2", "imageUrl": "y.jpg"},
                ]
            },
        },
    }
    c = _stub_client(get_resps=[success_resp])
    takes = song.wait_for_song(c, "fake-123", poll_interval_s=0)
    assert len(takes) == 2
    assert takes[0].url == "https://kie.ai/take1.mp3"
    assert takes[1].url == "https://kie.ai/take2.mp3"


def test_wait_for_song_polls_until_success():
    pending = {"data": {"status": "PENDING"}}
    text_ready = {"data": {"status": "TEXT_SUCCESS"}}
    first_ready = {"data": {"status": "FIRST_SUCCESS"}}
    success = {
        "data": {
            "status": "SUCCESS",
            "response": {
                "sunoData": [
                    {"id": "u1", "audioUrl": "u1.mp3"},
                    {"id": "u2", "audioUrl": "u2.mp3"},
                ]
            },
        }
    }
    c = _stub_client(get_resps=[pending, text_ready, first_ready, success])
    takes = song.wait_for_song(c, "fake-123", poll_interval_s=0)
    assert c._get_json.call_count == 4
    assert len(takes) == 2


def test_wait_for_song_raises_on_permanent_failure():
    fail_resp = {"data": {"status": "GENERATE_AUDIO_FAILED",
                          "errorMessage": "audio generation failed"}}
    c = _stub_client(get_resps=[fail_resp])
    with pytest.raises(song.SongGenerationError):
        song.wait_for_song(c, "fake-123", poll_interval_s=0)


def test_wait_for_song_raises_on_sensitive_word_error():
    fail_resp = {"data": {"status": "SENSITIVE_WORD_ERROR"}}
    c = _stub_client(get_resps=[fail_resp])
    with pytest.raises(song.SongGenerationError, match="SENSITIVE"):
        song.wait_for_song(c, "fake-123", poll_interval_s=0)


def test_wait_for_song_treats_create_task_failed_as_transient():
    from pipeline.kie import TransientKieError
    fail_resp = {"data": {"status": "CREATE_TASK_FAILED"}}
    c = _stub_client(get_resps=[fail_resp])
    with pytest.raises(TransientKieError):
        song.wait_for_song(c, "fake-123", poll_interval_s=0)


def test_wait_for_song_callback_exception_with_data_is_success():
    resp = {
        "data": {
            "status": "CALLBACK_EXCEPTION",
            "response": {
                "sunoData": [
                    {"id": "u1", "audioUrl": "u1.mp3"},
                    {"id": "u2", "audioUrl": "u2.mp3"},
                ]
            },
        }
    }
    c = _stub_client(get_resps=[resp])
    takes = song.wait_for_song(c, "fake-123", poll_interval_s=0)
    assert len(takes) == 2


def test_wait_for_song_timeout():
    pending = {"data": {"status": "PENDING"}}
    c = _stub_client(get_resps=[pending] * 20)
    with pytest.raises(song.SongGenerationTimeout):
        song.wait_for_song(c, "fake-123", poll_interval_s=0, timeout_s=0.01)


def test_download_take_writes_file(tmp_path: Path):
    c = _stub_client()
    fake_bytes = b"ID3" + b"\x00" * 100
    def fake_download(url, out_path):
        out_path.write_bytes(fake_bytes)
    c._download = fake_download
    out = tmp_path / "take_1.mp3"
    song.download_take(c, "https://kie.ai/take.mp3", out)
    assert out.exists()
    assert out.read_bytes() == fake_bytes
