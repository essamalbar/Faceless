from __future__ import annotations

import json

import pytest

import pipeline.trends as tr


class _Resp:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload or {}
    def json(self):
        return self._payload


def _chart(*titles, region_ok=True):
    return _Resp(200, {"items": [
        {"snippet": {"title": t, "channelTitle": "ch"}} for t in titles]})


def test_fetch_trending_merges_regions_and_skips_failures(monkeypatch):
    calls = []
    def fake_get(url, params=None, timeout=None):
        calls.append(params["regionCode"])
        if params["regionCode"] == "EG":
            return _Resp(403, {"error": "quota"})
        return _chart(f"song-{params['regionCode']}")
    monkeypatch.setattr(tr.requests, "get", fake_get)
    out = tr.fetch_trending_music("key")
    assert calls == ["SA", "EG", "AE"]
    assert {t["region"] for t in out} == {"SA", "AE"}  # EG skipped


def test_fetch_trending_all_fail_returns_empty(monkeypatch):
    monkeypatch.setattr(tr.requests, "get",
                        lambda *a, **k: _Resp(500, {}))
    assert tr.fetch_trending_music("key") == []


class _LLM:
    def __init__(self, outputs):
        self._outputs = list(outputs)
        self.calls = 0
    def complete(self, prompt, system=None):
        self.calls += 1
        return self._outputs.pop(0)


def _valid_briefs_json(n=6):
    return json.dumps([{
        "title_idea": f"فكرة {i}",
        "theme": f"أغنية عن الموضوع {i}",
        "style_hint": "Arabic pop, 95 BPM, oud, warm male vocal",
        "language": "ar",
        "rationale": "موسم الصيف",
    } for i in range(n)], ensure_ascii=False)


def test_build_briefs_parses_fenced_json():
    llm = _LLM(["```json\n" + _valid_briefs_json() + "\n```"])
    briefs = tr.build_briefs(llm, [], language="ar", today="2026-07-16")
    assert len(briefs) == 6
    assert briefs[0]["id"].startswith("tb_")
    assert briefs[0]["theme"].startswith("أغنية")


def test_build_briefs_retries_once_then_succeeds():
    llm = _LLM(["totally not json", _valid_briefs_json(4)])
    briefs = tr.build_briefs(llm, [], language="ar", today="2026-07-16")
    assert llm.calls == 2 and len(briefs) == 4


def test_build_briefs_raises_after_two_bad():
    llm = _LLM(["nope", "still nope"])
    with pytest.raises(tr.TrendsError):
        tr.build_briefs(llm, [], language="ar", today="2026-07-16")


def test_build_briefs_includes_chart_context():
    seen = {}
    class _CaptureLLM:
        def complete(self, prompt, system=None):
            seen["prompt"] = prompt
            return _valid_briefs_json()
    tr.build_briefs(_CaptureLLM(),
                    [{"title": "Trending Song X", "channel": "c", "region": "SA"}],
                    language="ar", today="2026-07-16")
    assert "Trending Song X" in seen["prompt"]
    assert "2026-07-16" in seen["prompt"]


def test_cache_roundtrip_and_corrupt(tmp_path):
    assert tr.load_cache(tmp_path) is None
    tr.save_cache(tmp_path, "2026-07-16T00:00:00+00:00",
                  [{"id": "tb_1", "theme": "x"}])
    got = tr.load_cache(tmp_path)
    assert got["briefs"][0]["id"] == "tb_1"
    tr.cache_path(tmp_path).write_text("{broken")
    assert tr.load_cache(tmp_path) is None
