from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse

import pytest

import pipeline.youtube as yt


class _Resp:
    def __init__(self, status_code, payload=None, headers=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.headers = headers or {}
        self.text = text or json.dumps(self._payload)

    def json(self):
        return self._payload


def test_auth_url_contains_scopes_state_offline():
    url = yt.auth_url("cid", "https://x/cb", "signed-state")
    q = parse_qs(urlparse(url).query)
    assert q["client_id"] == ["cid"]
    assert q["state"] == ["signed-state"]
    assert q["access_type"] == ["offline"]
    assert "youtube.upload" in q["scope"][0]


def test_refresh_access_token_ok_and_error(monkeypatch):
    monkeypatch.setattr(yt.requests, "post",
                        lambda *a, **k: _Resp(200, {"access_token": "at-1"}))
    assert yt.refresh_access_token("c", "s", "rt") == "at-1"

    monkeypatch.setattr(yt.requests, "post",
                        lambda *a, **k: _Resp(400, {"error": "invalid_grant"}))
    with pytest.raises(yt.YouTubeError):
        yt.refresh_access_token("c", "s", "rt")


def test_upload_video_two_step(monkeypatch, tmp_path):
    video = tmp_path / "final.mp4"
    video.write_bytes(b"\x00mp4")
    seen = {}

    def fake_post(url, headers=None, data=None, timeout=None):
        seen["init_body"] = json.loads(data)
        return _Resp(200, headers={"Location": "https://upload.loc/1"})

    def fake_put(url, headers=None, data=None, timeout=None):
        seen["put_url"] = url
        return _Resp(200, {"id": "vid-123"})

    monkeypatch.setattr(yt.requests, "post", fake_post)
    monkeypatch.setattr(yt.requests, "put", fake_put)
    vid = yt.upload_video(
        "at", video, title="حلم في الليل — ليل",
        description="desc", tags=["Arabic pop"], privacy="private")
    assert vid == "vid-123"
    assert seen["put_url"] == "https://upload.loc/1"
    snip = seen["init_body"]["snippet"]
    assert snip["title"].startswith("حلم")
    assert snip["categoryId"] == "10"
    assert seen["init_body"]["status"]["privacyStatus"] == "private"


def test_upload_video_surfaces_api_error(monkeypatch, tmp_path):
    video = tmp_path / "final.mp4"
    video.write_bytes(b"\x00")
    monkeypatch.setattr(yt.requests, "post",
                        lambda *a, **k: _Resp(403, {"error": "quotaExceeded"}))
    with pytest.raises(yt.YouTubeError, match="403"):
        yt.upload_video("at", video, title="t", description="d",
                        tags=[], privacy="private")


def test_build_metadata_with_artist():
    meta = yt.build_metadata(
        {"title": "حلم في الليل",
         "lyrics": "[Verse 1]\nسطر أول\nسطر ثانٍ\n[Chorus]\nلازمة",
         "style_prompt": "Arabic pop, 92 BPM, oud, warm male vocal",
         "language": "ar"},
        {"name": "ليل", "handle": "layl"},
        "https://api.faceless-lab.com",
    )
    assert meta["title"] == "حلم في الليل — ليل"
    assert "سطر أول" in meta["description"]
    assert "/a/layl" in meta["description"]
    assert "#اغاني" in meta["description"]
    assert "Arabic pop" in meta["tags"]
    assert "[Verse 1]" not in meta["description"]


def test_build_metadata_without_artist():
    meta = yt.build_metadata({"title": "Song", "lyrics": "", "language": "en"},
                             None, "https://x")
    assert meta["title"] == "Song"
    assert "/a/" not in meta["description"]


def test_token_storage_roundtrip(tmp_path):
    assert yt.load_token(tmp_path) is None
    yt.save_token(tmp_path, {"refresh_token": "rt", "channel_title": "ليل TV"})
    tok = yt.load_token(tmp_path)
    assert tok["channel_title"] == "ليل TV"
    assert yt.delete_token(tmp_path) is True
    assert yt.load_token(tmp_path) is None


def test_load_token_rejects_corrupt_or_empty(tmp_path):
    yt.token_path(tmp_path).parent.mkdir(parents=True, exist_ok=True)
    yt.token_path(tmp_path).write_text("{not json")
    assert yt.load_token(tmp_path) is None
    yt.token_path(tmp_path).write_text(json.dumps({"channel_title": "x"}))
    assert yt.load_token(tmp_path) is None  # no refresh_token → invalid
