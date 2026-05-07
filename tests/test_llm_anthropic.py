"""Anthropic Messages API client tests. Real HTTP is replaced via monkeypatch."""
from __future__ import annotations

import pytest

from pipeline import llm_anthropic as anth_mod
from pipeline.llm_anthropic import AnthropicClient, AnthropicError


def _client() -> AnthropicClient:
    return AnthropicClient(api_key="k", model="claude-sonnet-4-6")


def test_init_requires_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(AnthropicError):
        AnthropicClient()


def test_complete_returns_concatenated_text_blocks(monkeypatch):
    captured: dict = {}

    def fake_post(self, path, body):
        captured["path"] = path
        captured["body"] = body
        return {
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "model": "claude-sonnet-4-6",
            "content": [
                {"type": "text", "text": '{"title": "x"}'},
            ],
            "stop_reason": "end_turn",
        }

    monkeypatch.setattr(AnthropicClient, "_post", fake_post)
    out = _client().complete("write an Arabic story", system="you are a writer")
    assert out == '{"title": "x"}'
    assert captured["path"] == "/v1/messages"
    assert captured["body"]["model"] == "claude-sonnet-4-6"
    assert captured["body"]["system"] == "you are a writer"
    assert captured["body"]["messages"] == [
        {"role": "user", "content": "write an Arabic story"}
    ]
    # Defaults: max_tokens set high enough for shorts critique JSON
    # (the critique echoes the whole draft + improvements; 2048 truncates),
    # temperature in narrative range
    assert captured["body"]["max_tokens"] == 4096
    assert 0 < captured["body"]["temperature"] <= 1.0


def test_complete_concatenates_multi_block_response(monkeypatch):
    """Anthropic may split long output into multiple text blocks; we join them."""
    monkeypatch.setattr(
        AnthropicClient, "_post",
        lambda self, p, b: {"content": [
            {"type": "text", "text": "part one "},
            {"type": "text", "text": "part two"},
        ]},
    )
    assert _client().complete("x") == "part one part two"


def test_complete_skips_non_text_blocks(monkeypatch):
    """Tool-use or other block types should be ignored, not error."""
    monkeypatch.setattr(
        AnthropicClient, "_post",
        lambda self, p, b: {"content": [
            {"type": "tool_use", "id": "abc", "name": "x"},
            {"type": "text", "text": "hello"},
        ]},
    )
    assert _client().complete("x") == "hello"


def test_complete_raises_when_no_text_blocks(monkeypatch):
    monkeypatch.setattr(
        AnthropicClient, "_post",
        lambda self, p, b: {"content": []},
    )
    monkeypatch.setattr(anth_mod, "_SLEEP", lambda _s: None)
    with pytest.raises(AnthropicError, match="no text content"):
        _client().complete("x")


def test_complete_retries_then_succeeds(monkeypatch):
    attempts = {"n": 0}

    def flaky_post(self, path, body):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RuntimeError("transient")
        return {"content": [{"type": "text", "text": "ok"}]}

    monkeypatch.setattr(AnthropicClient, "_post", flaky_post)
    monkeypatch.setattr(anth_mod, "_SLEEP", lambda _s: None)
    assert _client().complete("x") == "ok"
    assert attempts["n"] == 3


def test_complete_raises_after_max_retries(monkeypatch):
    monkeypatch.setattr(
        AnthropicClient, "_post",
        lambda self, p, b: (_ for _ in ()).throw(RuntimeError("perm")),
    )
    monkeypatch.setattr(anth_mod, "_SLEEP", lambda _s: None)
    with pytest.raises(AnthropicError, match="failed after"):
        _client().complete("x")


def test_embed_not_supported():
    with pytest.raises(NotImplementedError):
        _client().embed("any text")


def test_post_includes_anthropic_headers(monkeypatch):
    """Anthropic requires x-api-key (NOT Bearer) and an anthropic-version header."""
    captured: dict = {}

    class FakeResp:
        status_code = 200
        text = ""
        def json(self):
            return {"content": [{"type": "text", "text": "ok"}]}

    def fake_requests_post(url, json, headers, timeout):
        captured["url"] = url
        captured["headers"] = headers
        return FakeResp()

    monkeypatch.setattr(anth_mod.requests, "post", fake_requests_post)
    _client().complete("x")
    assert captured["headers"]["x-api-key"] == "k"
    assert "anthropic-version" in captured["headers"]
    # NOT Bearer
    assert "Authorization" not in captured["headers"]
