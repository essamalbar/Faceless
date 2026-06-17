from __future__ import annotations

import pytest

from pipeline.llm import FallbackLLM


class _OK:
    def __init__(self, out):
        self.out = out
        self.calls = 0

    def complete(self, prompt, system=None):
        self.calls += 1
        return self.out


class _Boom:
    def __init__(self):
        self.calls = 0

    def complete(self, prompt, system=None):
        self.calls += 1
        raise RuntimeError("provider down")


def test_uses_primary_when_it_succeeds():
    p, f = _OK("primary"), _OK("fallback")
    assert FallbackLLM(p, f).complete("hi", system="s") == "primary"
    assert p.calls == 1 and f.calls == 0


def test_falls_back_when_primary_raises():
    p, f = _Boom(), _OK("fallback")
    assert FallbackLLM(p, f).complete("hi") == "fallback"
    assert p.calls == 1 and f.calls == 1


def test_propagates_if_both_fail():
    with pytest.raises(RuntimeError):
        FallbackLLM(_Boom(), _Boom()).complete("hi")


def test_router_wraps_in_fallback_when_both_keys_present(monkeypatch):
    # AnthropicClient/GroqClient constructors only store the key (no network),
    # so this exercises the real router wiring without any API calls.
    import pipeline.api as api
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("GROQ_API_KEY", "y")
    assert isinstance(api._build_llm(), FallbackLLM)


def test_router_anthropic_only_no_wrapper(monkeypatch):
    import pipeline.api as api
    from pipeline.llm_anthropic import AnthropicClient
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert isinstance(api._build_llm(), AnthropicClient)


def test_router_groq_only_when_no_anthropic(monkeypatch):
    import pipeline.api as api
    from pipeline.llm_groq import GroqClient
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "y")
    assert isinstance(api._build_llm(), GroqClient)
