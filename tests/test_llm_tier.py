from __future__ import annotations

import pytest

from pipeline.llm import FallbackLLM, resolve_tier


class _Stub:
    def __init__(self, tier, raises=False):
        self.tier = tier
        self._raises = raises

    def complete(self, prompt, system=None):
        if self._raises:
            raise RuntimeError("primary down")
        return f"[{self.tier}] {prompt}"


def test_fallback_records_primary_tier_on_success():
    llm = FallbackLLM(_Stub("anthropic"), _Stub("groq"))
    out = llm.complete("hi")
    assert out.startswith("[anthropic]")
    assert llm.last_tier == "anthropic"


def test_fallback_records_fallback_tier_on_primary_failure():
    llm = FallbackLLM(_Stub("anthropic", raises=True), _Stub("groq"))
    out = llm.complete("hi")
    assert out.startswith("[groq]")
    assert llm.last_tier == "groq"


def test_fallback_records_leaf_tier_through_nested_chain():
    inner = FallbackLLM(_Stub("gemini", raises=True), _Stub("groq"))
    outer = FallbackLLM(_Stub("anthropic", raises=True), inner)
    outer.complete("hi")
    assert outer.last_tier == "groq"


def test_resolve_tier_reads_bare_client():
    assert resolve_tier(_Stub("gemini")) == "gemini"


def test_resolve_tier_unknown_when_absent():
    class Bare:
        def complete(self, p, system=None):
            return p
    assert resolve_tier(Bare()) == "unknown"
