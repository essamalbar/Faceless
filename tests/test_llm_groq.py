"""Groq LLM client tests. Real HTTP is replaced via monkeypatch."""
from __future__ import annotations

import pytest

from pipeline import llm_groq as groq_mod
from pipeline.llm_groq import GroqClient, GroqError


def test_init_requires_api_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(GroqError):
        GroqClient()


def test_complete_sends_chat_payload(monkeypatch):
    captured: dict = {}

    def fake_post(self, path, body):
        captured["path"] = path
        captured["body"] = body
        return {"choices": [{"message": {"content": "مرحبا"}}]}

    monkeypatch.setattr(GroqClient, "_post", fake_post)
    # Deterministic against a stray env override — assert the real default.
    monkeypatch.delenv("GROQ_MODEL", raising=False)
    c = GroqClient(api_key="k")
    out = c.complete("hi", system="be brief")
    assert out == "مرحبا"
    assert captured["path"] == "/chat/completions"
    assert captured["body"]["model"] == "openai/gpt-oss-120b"
    assert captured["body"]["messages"][0] == {"role": "system", "content": "be brief"}
    assert captured["body"]["messages"][1] == {"role": "user", "content": "hi"}


def test_complete_works_without_system(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(GroqClient, "_post",
                        lambda self, path, body: captured.update(body=body) or
                        {"choices": [{"message": {"content": "ok"}}]})
    GroqClient(api_key="k").complete("hi")
    assert captured["body"]["messages"] == [{"role": "user", "content": "hi"}]


def test_complete_retries_then_succeeds(monkeypatch):
    calls = {"n": 0}
    def flaky(self, path, body):
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("transient")
        return {"choices": [{"message": {"content": "ok"}}]}
    monkeypatch.setattr(GroqClient, "_post", flaky)
    monkeypatch.setattr(groq_mod, "_SLEEP", lambda _s: None)
    assert GroqClient(api_key="k").complete("hi") == "ok"
    assert calls["n"] == 3


def test_complete_raises_after_max_retries(monkeypatch):
    monkeypatch.setattr(GroqClient, "_post",
                        lambda self, path, body: (_ for _ in ()).throw(RuntimeError("permanent")))
    monkeypatch.setattr(groq_mod, "_SLEEP", lambda _s: None)
    with pytest.raises(GroqError, match="complete failed"):
        GroqClient(api_key="k").complete("hi")


def test_embed_raises_not_implemented():
    with pytest.raises(NotImplementedError):
        GroqClient(api_key="k").embed("text")


def test_json_mode_enabled_when_prompt_mentions_json(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(GroqClient, "_post",
                        lambda self, path, body: captured.update(body=body) or
                        {"choices": [{"message": {"content": "{}"}}]})
    GroqClient(api_key="k").complete("hi", system="Output a JSON object with keys")
    assert captured["body"]["response_format"] == {"type": "json_object"}


def test_json_mode_off_for_prose(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(GroqClient, "_post",
                        lambda self, path, body: captured.update(body=body) or
                        {"choices": [{"message": {"content": "a story"}}]})
    GroqClient(api_key="k").complete("hi", system="Write a short story")
    assert "response_format" not in captured["body"]
