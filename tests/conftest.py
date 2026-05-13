"""Shared pytest fixtures and fakes for pipeline tests."""
from __future__ import annotations

import pytest
from pathlib import Path


@pytest.fixture
def tmp_run_dir(tmp_path: Path) -> Path:
    """A temporary per-run output directory."""
    run_dir = tmp_path / "run-test"
    run_dir.mkdir()
    return run_dir


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"


from typing import Callable


class FakeGemini:
    """Test fake. Configure with prompt-pattern → response mappings."""

    def __init__(self):
        self._responses: list[Callable[[str], str | None]] = []
        self._embeddings: dict[str, list[float]] = {}
        self.complete_calls: list[tuple[str, str | None]] = []
        self.embed_calls: list[str] = []

    def when(self, predicate: Callable[[str], bool], reply: str):
        """Register: if prompt matches predicate, return reply."""
        def matcher(prompt: str) -> str | None:
            return reply if predicate(prompt) else None
        self._responses.append(matcher)

    def set_embedding(self, text: str, vec: list[float]):
        self._embeddings[text] = vec

    # production interface
    def complete(self, prompt: str, system: str | None = None) -> str:
        self.complete_calls.append((prompt, system))
        for matcher in self._responses:
            r = matcher(prompt)
            if r is not None:
                return r
        raise AssertionError(f"FakeGemini got unexpected prompt: {prompt[:200]}")

    def embed(self, text: str) -> list[float]:
        self.embed_calls.append(text)
        if text in self._embeddings:
            return self._embeddings[text]
        # default deterministic embedding from text length
        return [float(len(text) % 100) / 100.0] * 8


@pytest.fixture
def fake_gemini():
    return FakeGemini()


@pytest.fixture
def client_factory():
    """Returns a callable that builds a TestClient with a forced user_id.

    The fixture overrides the require_user FastAPI dependency, so endpoints
    behave as if the request came from the given user. Each client carries
    its own user_id via a request header (X-Test-User-Id), so multiple
    clients in the same test are independent. Cleared after the test.
    """
    from fastapi import Header
    from fastapi.testclient import TestClient

    from pipeline.api import app
    from pipeline.auth import User, require_user

    # Per-client identity is encoded in a header so multiple TestClients
    # in the same test (e.g. alice + bob) don't clobber each other's
    # overrides.
    _users: dict[str, User] = {}

    async def _resolve_user(x_test_user_id: str | None = Header(default=None)):
        if x_test_user_id and x_test_user_id in _users:
            return _users[x_test_user_id]
        # Fall back to a default admin if the header isn't set — preserves
        # the simplest single-client case.
        return User(id="admin", email=None, role="user")

    app.dependency_overrides[require_user] = _resolve_user

    def _make(user_id: str = "admin", role: str = "user", email: str | None = None):
        _users[user_id] = User(id=user_id, email=email, role=role)
        client = TestClient(app)
        client.headers.update({"X-Test-User-Id": user_id})
        return client

    yield _make
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _auto_mock_inline_script_gen(monkeypatch):
    """Inline script generation calls Anthropic (or Groq/Gemini) and writes
    `seed.json` + `script.json` directly inside the /runs/{*} request, replacing
    the older "spawn a Cloud Run Job, let it write the files, return" flow.

    Tests don't want to actually call the LLM, so this autouse fixture wraps
    `pipeline.api._generate_script_inline` with a stub that writes the same
    files the real implementation would. Individual tests can still override
    by monkeypatching `pipeline.api._generate_script_inline` again — pytest
    applies overrides in registration order, so a test's `monkeypatch.setattr`
    wins over this fixture.

    Why autouse: every test that hits /runs or /runs/freeform now depends on
    this; making it explicit per-test would mean editing 8+ tests for what
    is fundamentally a test infrastructure migration.
    """
    import json as _json

    def fake_inline(*, run_dir, theme, premise, controls):
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "seed.json").write_text(
            _json.dumps(
                {"theme": theme, "premise": premise},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        # Build a Script-shaped doc so derive_status finds beats and other
        # API code that reads script.json doesn't crash.
        num_beats = int(controls.get("num_beats", 8))
        per_beat = int(controls.get("per_beat_seconds", 8))
        (run_dir / "script.json").write_text(
            _json.dumps(
                {
                    "title": f"test-{run_dir.name}",
                    "theme": theme,
                    "global_setting": "test setting",
                    "music_mood": "dread",
                    "target_duration_s": num_beats * per_beat,
                    "beats": [
                        {
                            "arabic": f"بيت {i+1}",
                            "english_motion": f"motion {i+1}",
                            "clip_duration_s": float(per_beat),
                            "speaker": "narrator",
                            "character_name": "",
                        }
                        for i in range(num_beats)
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    monkeypatch.setattr("pipeline.api._generate_script_inline", fake_inline)
