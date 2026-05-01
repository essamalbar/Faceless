"""Gemini wrapper interface tests. Production calls are mocked."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from pipeline.llm import GeminiClient, GeminiError


def test_complete_returns_string(monkeypatch):
    fake_response = MagicMock()
    fake_response.text = "hello"
    fake_models = MagicMock()
    fake_models.generate_content.return_value = fake_response
    fake_client = MagicMock()
    fake_client.models = fake_models

    monkeypatch.setattr("pipeline.llm._make_client", lambda *_a, **_k: fake_client)

    g = GeminiClient(api_key="k", model="gemini-2.5-flash")
    assert g.complete("hi") == "hello"


def test_complete_retries_then_succeeds(monkeypatch):
    call_count = {"n": 0}

    def flaky(*a, **kw):
        call_count["n"] += 1
        if call_count["n"] < 3:
            raise RuntimeError("transient")
        r = MagicMock()
        r.text = "ok"
        return r

    fake_models = MagicMock()
    fake_models.generate_content.side_effect = flaky
    fake_client = MagicMock(); fake_client.models = fake_models
    monkeypatch.setattr("pipeline.llm._make_client", lambda *_a, **_k: fake_client)
    monkeypatch.setattr("pipeline.llm._SLEEP", lambda _: None)  # skip backoff

    g = GeminiClient(api_key="k", model="gemini-2.5-flash")
    assert g.complete("hi") == "ok"
    assert call_count["n"] == 3


def test_complete_raises_after_max_retries(monkeypatch):
    fake_models = MagicMock()
    fake_models.generate_content.side_effect = RuntimeError("permanent")
    fake_client = MagicMock(); fake_client.models = fake_models
    monkeypatch.setattr("pipeline.llm._make_client", lambda *_a, **_k: fake_client)
    monkeypatch.setattr("pipeline.llm._SLEEP", lambda _: None)

    g = GeminiClient(api_key="k", model="gemini-2.5-flash")
    with pytest.raises(GeminiError):
        g.complete("hi")


def test_embed_returns_vector(monkeypatch):
    fake_embed = MagicMock()
    fake_embed.embeddings = [MagicMock(values=[0.1, 0.2, 0.3])]
    fake_models = MagicMock()
    fake_models.embed_content.return_value = fake_embed
    fake_client = MagicMock(); fake_client.models = fake_models
    monkeypatch.setattr("pipeline.llm._make_client", lambda *_a, **_k: fake_client)

    g = GeminiClient(api_key="k", model="gemini-2.5-flash")
    vec = g.embed("text")
    assert vec == [0.1, 0.2, 0.3]
