"""Tests for pipeline/agent.py — `AgentRunner`, the bounded Claude tool-use
loop (spec §4).

`test_gate_integrity_no_credit_moves_no_spawn` is THE acceptance gate for
this task: it proves a full agent cycle never touches a spend path
(`credits.check_or_deduct` / `api._spawn`) — the agent's entire toolbox is
read-and-queue only, and this test is the end-to-end proof of that boundary.

External services are mocked throughout: `ScriptedAnthropic` replays a
canned script instead of calling the real Anthropic SDK, and an autouse
fixture replaces the agent's internal LLM builders (used by the
draft_lyrics/critique_draft tools) with a fake — so no real network call
happens even if ANTHROPIC_API_KEY/GEMINI_API_KEY/GROQ_API_KEY are set in the
ambient shell running these tests.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from pipeline import agent
from pipeline.config import AgentConfig


# ---------------------------------------------------------------------------
# ScriptedAnthropic — a stub Anthropic client. Response blocks are
# attribute-bearing objects (SimpleNamespace), matching the real SDK's
# response shape (block.type / block.name / block.input / block.id) — NOT
# plain dicts. The loop reads attributes only (getattr), never dict-indexes
# or string-matches a block, so it drives identically against the real SDK.
# ---------------------------------------------------------------------------

class _Msg:
    """Minimal shape the loop reads: .content (blocks), .stop_reason,
    .usage.output_tokens."""

    def __init__(self, content, stop_reason, output_tokens=0):
        self.content = content
        self.stop_reason = stop_reason
        self.usage = SimpleNamespace(output_tokens=output_tokens)


class ScriptedAnthropic:
    """Stub Anthropic client: replays a canned sequence of responses."""

    def __init__(self, script):
        self.script = list(script)
        self.calls: list[dict] = []

    @property
    def messages(self):
        return self

    def create(self, **kw):
        self.calls.append(kw)
        if not self.script:
            raise AssertionError("ScriptedAnthropic script exhausted")
        return self.script.pop(0)


def _tool_use(name, inp, tid="t"):
    return SimpleNamespace(type="tool_use", id=tid, name=name, input=inp)


def _text(text):
    return SimpleNamespace(type="text", text=text)


def _thinking(text):
    return SimpleNamespace(type="thinking", thinking=text)


def _turn(blocks, output_tokens=0):
    """One assistant turn that used at least one tool -> stop_reason tool_use."""
    return _Msg(list(blocks), "tool_use", output_tokens=output_tokens)


def _end_turn(text="done", output_tokens=0):
    return _Msg([_text(text)], "end_turn", output_tokens=output_tokens)


# ---------------------------------------------------------------------------
# Fakes / fixtures / helpers
# ---------------------------------------------------------------------------

class _FakeLLM:
    """Never a real network call — the draft_lyrics/critique_draft tools
    tolerate a wrong-shaped response gracefully (dispatch_tool catches any
    handler exception), so a single canned response is enough here; none
    of these tests assert on draft_lyrics/critique_draft's own output."""

    def __init__(self):
        self.calls: list[tuple] = []

    def complete(self, prompt, system=None):
        self.calls.append((prompt, system))
        return json.dumps({"overall": 0.9, "notes": "ok"})


@pytest.fixture(autouse=True)
def _fake_llms(monkeypatch):
    """External services are mocked in tests (CLAUDE.md invariant): replace
    the agent's internal LLM builders so draft_lyrics/critique_draft never
    reach a real provider, regardless of ambient API keys."""
    monkeypatch.setattr(agent, "_build_llm_router", lambda: _FakeLLM())
    monkeypatch.setattr(agent, "_build_worker_llm", lambda agent_cfg: _FakeLLM())


def _cfg(**overrides) -> SimpleNamespace:
    """An object with `.agent.<field>` like the real pipeline.config.Config
    — a small stand-in so tests don't need to construct the full Config
    (voice/script/flux/assemble/captions/kie sub-configs)."""
    defaults = dict(
        enabled=True, model="claude-opus-5", worker_model="claude-sonnet-5",
        max_iterations=12, token_budget=60000, proposals_per_cycle=2,
        daily_global_run_cap=50, critique_threshold=0.6,
    )
    defaults.update(overrides)
    return SimpleNamespace(agent=AgentConfig(**defaults))


def _artist() -> dict:
    return {
        "id": "art_x", "name": "Salma", "handle": "salma", "bio": "khaleeji pop artist",
        "default_language": "ar", "default_style": "khaleeji",
        "default_dialect": "khaleeji", "default_vocal_gender": "f",
        "persona_id": None,
    }


def _read_run_state(root: Path, run_id: str) -> dict:
    return json.loads((root / run_id / "api_state.json").read_text(encoding="utf-8"))


def _queue_input(**overrides) -> dict:
    base = dict(
        title="وعد الليل", concept="ليلة صيف في الصحراء", lyrics="[Chorus]\nكورال مكرر",
        style="khaleeji", dialect="khaleeji", language="ar",
        rationale="on brand + trending", self_score=0.82,
    )
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Happy path: trends -> draft -> critique -> queue -> finish
# ---------------------------------------------------------------------------

def test_loop_runs_tools_then_finishes(tmp_path):
    script = [
        _turn([_tool_use("get_trends", {})]),
        _turn([_tool_use("draft_lyrics", {
            "concept": "c", "style": "s", "dialect": "khaleeji", "language": "ar"})]),
        _turn([_tool_use("critique_draft", {"lyrics": "L"})]),
        _turn([_tool_use("queue_proposal", _queue_input())]),
        _turn([_tool_use("finish", {"summary": "queued one strong proposal"})]),
    ]
    client = ScriptedAnthropic(script)
    r = agent.AgentRunner().run_cycle(
        tmp_path, _artist(), anthropic_client=client, config=_cfg())

    assert r["stopped"] == "finished"
    assert r["iterations"] == 5
    assert len(r["queued"]) == 1

    state = _read_run_state(tmp_path, r["queued"][0])
    assert state["status"] == "awaiting_approval"

    # the system prompt was actually built and passed through
    assert "Salma" in client.calls[0]["system"]
    assert client.calls[0]["tools"] is agent.TOOLS

    # the reasoning trace was written to the path queue_proposal recorded
    trace_path = tmp_path / r["queued"][0] / state["agent_trace_path"]
    assert trace_path.exists()
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    tool_calls = [s["name"] for s in trace["steps"] if s.get("type") == "tool_call"]
    assert tool_calls == [
        "get_trends", "draft_lyrics", "critique_draft", "queue_proposal", "finish"]


# ---------------------------------------------------------------------------
# Bounds
# ---------------------------------------------------------------------------

def test_loop_respects_max_iterations(tmp_path):
    # a client that NEVER calls finish
    always_trends = [_turn([_tool_use("get_trends", {})]) for _ in range(50)]
    r = agent.AgentRunner().run_cycle(
        tmp_path, _artist(), anthropic_client=ScriptedAnthropic(always_trends),
        config=_cfg(max_iterations=5))

    assert r["stopped"] == "max_iterations"
    assert r["iterations"] <= 5
    assert r["queued"] == []


def test_loop_respects_token_budget(tmp_path):
    # a single turn that blows the token budget must stop the cycle
    script = [_turn([_tool_use("get_trends", {})], output_tokens=999999)]
    r = agent.AgentRunner().run_cycle(
        tmp_path, _artist(), anthropic_client=ScriptedAnthropic(script),
        config=_cfg(token_budget=100))

    assert r["stopped"] == "budget"
    assert r["queued"] == []


# ---------------------------------------------------------------------------
# The loop OWNS critique_threshold + proposals_per_cycle (hard gates, not
# just prompt wording)
# ---------------------------------------------------------------------------

def test_below_threshold_proposal_is_not_queued(tmp_path):
    script = [
        _turn([_tool_use("queue_proposal", _queue_input(self_score=0.3))]),
        _turn([_tool_use("finish", {"summary": "nothing good enough this cycle"})]),
    ]
    r = agent.AgentRunner().run_cycle(
        tmp_path, _artist(), anthropic_client=ScriptedAnthropic(script),
        config=_cfg(critique_threshold=0.6))

    assert r["queued"] == []
    assert r["stopped"] == "finished"
    # a rejected proposal never even creates a run dir
    assert list(tmp_path.iterdir()) == []


def test_proposals_per_cycle_cap(tmp_path):
    script = [
        _turn([_tool_use("queue_proposal", _queue_input(title="a"))]),
        _turn([_tool_use("queue_proposal", _queue_input(title="b"))]),
        _turn([_tool_use("queue_proposal", _queue_input(title="c"))]),
        _turn([_tool_use("finish", {"summary": "done"})]),
    ]
    r = agent.AgentRunner().run_cycle(
        tmp_path, _artist(), anthropic_client=ScriptedAnthropic(script),
        config=_cfg(proposals_per_cycle=2))

    assert len(r["queued"]) == 2
    assert r["stopped"] == "finished"


# ---------------------------------------------------------------------------
# THE gate-integrity test — the acceptance gate for this task.
# ---------------------------------------------------------------------------

def test_gate_integrity_no_credit_moves_no_spawn(tmp_path, monkeypatch):
    """A full agent cycle must NEVER touch a spend path. Queued proposals
    are `awaiting_approval` only — the same state morning-drafts already
    produces, requiring a human tap to spend anything."""
    import pipeline.credits as credits
    monkeypatch.setattr(
        credits, "check_or_deduct",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("agent must NOT deduct credits")))

    import pipeline.api as api
    monkeypatch.setattr(
        api, "_spawn",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("agent must NOT spawn a paid render")))

    script = [
        _turn([_tool_use("get_trends", {})]),
        _turn([_tool_use("get_artist_context", {})]),
        _turn([_tool_use("draft_lyrics", {
            "concept": "c", "style": "s", "dialect": "khaleeji", "language": "ar"})]),
        _turn([_tool_use("critique_draft", {"lyrics": "L"})]),
        _turn([_tool_use("queue_proposal", _queue_input())]),
        _turn([_tool_use("finish", {"summary": "ok"})]),
    ]
    r = agent.AgentRunner().run_cycle(
        tmp_path, _artist(), anthropic_client=ScriptedAnthropic(script), config=_cfg())

    # no AssertionError raised above = no spend path was ever touched
    assert r["stopped"] == "finished"
    assert r["queued"], "expected at least one queued proposal"
    for run_id in r["queued"]:
        assert _read_run_state(tmp_path, run_id)["status"] == "awaiting_approval"


# ---------------------------------------------------------------------------
# Fail-safe on an unexpected exception
# ---------------------------------------------------------------------------

def test_loop_fails_safe_on_tool_exception(tmp_path, monkeypatch):
    """A tool call that raises (bypassing dispatch_tool's own per-tool
    try/except, simulating a genuinely unexpected bug) must not propagate
    out of run_cycle: the cycle stops, keeps whatever was already validly
    queued (nothing, here), and spends nothing further."""
    calls = {"n": 0}
    real_dispatch = agent.dispatch_tool

    def flaky(name, tool_input, ctx):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("boom - simulated unexpected tool crash")
        return real_dispatch(name, tool_input, ctx)

    monkeypatch.setattr(agent, "dispatch_tool", flaky)

    script = [
        _turn([_tool_use("get_trends", {})]),
        _turn([_tool_use("queue_proposal", _queue_input())]),
        _turn([_tool_use("finish", {"summary": "ok"})]),
    ]
    r = agent.AgentRunner().run_cycle(
        tmp_path, _artist(), anthropic_client=ScriptedAnthropic(script), config=_cfg())

    assert r["stopped"] == "error"
    assert r["queued"] == []
