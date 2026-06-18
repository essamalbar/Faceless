"""Range-aware video streaming — keeps every response under Cloud Run's
~32 MiB buffered-response cap (which 500'd full-file GETs of large mp4s)."""
from __future__ import annotations

from pipeline.api import _serve_video, _VIDEO_RANGE_CAP


class _Req:
    def __init__(self, rng: str | None = None):
        self.headers = {"range": rng} if rng else {}


def test_open_ended_range_is_capped_under_limit(tmp_path):
    f = tmp_path / "v.mp4"
    f.write_bytes(b"\0" * (_VIDEO_RANGE_CAP + 4096))  # bigger than one response
    total = f.stat().st_size
    r = _serve_video(f, _Req("bytes=0-"))  # what a <video> element sends
    assert r.status_code == 206
    # served slice is capped, NOT the whole (over-limit) file
    assert int(r.headers["Content-Length"]) == _VIDEO_RANGE_CAP
    assert r.headers["Content-Range"] == f"bytes 0-{_VIDEO_RANGE_CAP - 1}/{total}"
    assert r.headers["Accept-Ranges"] == "bytes"


def test_mid_file_range_serves_requested_slice(tmp_path):
    f = tmp_path / "v.mp4"
    f.write_bytes(b"\0" * 10000)
    r = _serve_video(f, _Req("bytes=1000-1999"))
    assert r.status_code == 206
    assert int(r.headers["Content-Length"]) == 1000
    assert r.headers["Content-Range"] == "bytes 1000-1999/10000"


def test_no_range_streams_full_file_chunked(tmp_path):
    # No Range -> 200 chunked stream (no Content-Length), so Cloud Run does
    # not apply the buffered 32 MiB cap.
    f = tmp_path / "v.mp4"
    f.write_bytes(b"\0" * 5000)
    r = _serve_video(f, _Req())
    assert r.status_code == 200
    assert all(k.lower() != "content-length" for k in r.headers)


def test_unsatisfiable_range_returns_416(tmp_path):
    f = tmp_path / "v.mp4"
    f.write_bytes(b"\0" * 100)
    r = _serve_video(f, _Req("bytes=500-600"))
    assert r.status_code == 416
