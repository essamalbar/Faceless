"""Tests for pipeline/agent.py — the 6 read-and-queue agent tools.

The tool boundary IS the security boundary (spec §4.1, §10): exactly 6
tools, none of which can spend money or publish. Every external service
(LLM, trends) is faked — no real API calls in tests.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline import agent
from pipeline.config import AgentConfig


class _FakeLLM:
    """Canned-response fake satisfying `complete(prompt, system=None) -> str`.

    Defaults to a valid `generate_song_script` JSON payload so draft_lyrics
    tests work out of the box; pass an explicit `response` for other tools.
    """

    _DEFAULT_LYRICS_JSON = json.dumps({
        "title": "وعد الليل",
        "lyrics": "[Verse 1]\nسَطْرٌ أَوَّل\nسَطْرٌ ثانٍ\n\n[Chorus]\nكورال مكرر\n",
        "style_prompt": "khaleeji pop, warm strings",
        "cover_prompt": "a desert night, warm lantern light",
        "art_direction": "warm desert night",
        "scene_prompts": [],
    }, ensure_ascii=False)

    def __init__(self, response: str | None = None):
        self.response = response
        self.calls: list[tuple[str, str | None]] = []

    def complete(self, prompt, system=None):
        self.calls.append((prompt, system))
        return self.response if self.response is not None else self._DEFAULT_LYRICS_JSON


def _cfg() -> AgentConfig:
    return AgentConfig()


def _artist() -> dict:
    return {
        "id": "art_x", "name": "Salma", "handle": "salma",
        "default_language": "ar", "default_style": "khaleeji",
        "default_dialect": "khaleeji", "default_vocal_gender": "f",
        "persona_id": None,
    }


def _ctx(tmp_path: Path, *, llm=None, worker_llm=None, artist=None) -> agent.ToolContext:
    return agent.ToolContext(
        user_root=tmp_path,
        artist=artist if artist is not None else _artist(),
        llm=llm if llm is not None else _FakeLLM(),
        worker_llm=worker_llm if worker_llm is not None else _FakeLLM(),
        config=_cfg(),
    )


def _read_run_state(tmp_path: Path, run_id: str) -> dict:
    return json.loads((tmp_path / run_id / "api_state.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# The tool boundary
# ---------------------------------------------------------------------------

def test_tool_list_is_exactly_the_six_readqueue_tools():
    names = {t["name"] for t in agent.TOOLS}
    assert names == {"get_trends", "get_artist_context", "draft_lyrics",
                      "critique_draft", "queue_proposal", "finish"}
    forbidden = {"approve", "spend", "render", "publish", "post",
                 "deduct", "delete", "charge"}
    assert not (names & forbidden)
    for t in agent.TOOLS:
        assert set(t.keys()) >= {"name", "description", "input_schema"}
        schema = t["input_schema"]
        assert schema["type"] == "object"
        assert schema["additionalProperties"] is False
        assert "required" in schema
        assert "properties" in schema
        # every required field must be a declared property
        for req in schema["required"]:
            assert req in schema["properties"]


def test_tool_schemas_have_required_inputs():
    by_name = {t["name"]: t for t in agent.TOOLS}
    assert by_name["get_trends"]["input_schema"]["required"] == []
    assert by_name["get_artist_context"]["input_schema"]["required"] == []
    assert set(by_name["draft_lyrics"]["input_schema"]["required"]) == {
        "concept", "style", "dialect", "language"}
    assert set(by_name["critique_draft"]["input_schema"]["required"]) == {"lyrics"}
    assert set(by_name["queue_proposal"]["input_schema"]["required"]) == {
        "title", "concept", "lyrics", "style", "dialect", "language",
        "rationale", "self_score"}
    assert set(by_name["finish"]["input_schema"]["required"]) == {"summary"}


def test_unknown_tool_returns_error_not_raise(tmp_path):
    out = agent.dispatch_tool("spend_money", {}, _ctx(tmp_path))
    assert "error" in out


# ---------------------------------------------------------------------------
# finish
# ---------------------------------------------------------------------------

def test_finish_returns_done(tmp_path):
    out = agent.dispatch_tool("finish", {"summary": "queued 1 proposal"}, _ctx(tmp_path))
    assert out == {"done": True}


# ---------------------------------------------------------------------------
# get_artist_context
# ---------------------------------------------------------------------------

def test_get_artist_context_returns_identity_discography_memory(tmp_path):
    from pipeline import agent_memory

    artist = _artist()
    agent_memory.record_decision(
        tmp_path, artist["id"], run_id="r1", decision="approved", self_score=0.9)

    # a pre-existing song run for this artist, for the discography summary
    run_dir = tmp_path / "2026-01-01-000000"
    run_dir.mkdir(parents=True)
    (run_dir / "api_state.json").write_text(json.dumps({
        "kind": "song", "artist_id": artist["id"], "title": "أغنية قديمة",
        "status": "complete",
    }), encoding="utf-8")

    ctx = _ctx(tmp_path, artist=artist)
    out = agent.dispatch_tool("get_artist_context", {}, ctx)

    assert out["identity"]["id"] == artist["id"]
    assert out["identity"]["default_dialect"] == "khaleeji"
    assert out["discography"]["count"] == 1
    assert "أغنية قديمة" in out["discography"]["recent_titles"]
    assert out["memory"]["decisions"][0]["decision"] == "approved"


def test_get_artist_context_tolerates_missing_fields(tmp_path):
    """Pre-existing artist rows may lack newer fields (e.g. agent_enabled)."""
    bare_artist = {"id": "art_bare", "name": "Bare"}
    ctx = _ctx(tmp_path, artist=bare_artist)
    out = agent.dispatch_tool("get_artist_context", {}, ctx)
    assert out["identity"]["id"] == "art_bare"
    assert out["identity"]["agent_enabled"] is False
    assert out["discography"]["count"] == 0


# ---------------------------------------------------------------------------
# draft_lyrics
# ---------------------------------------------------------------------------

def test_draft_lyrics_returns_lyrics_and_title(tmp_path):
    ctx = _ctx(tmp_path)
    out = agent.dispatch_tool("draft_lyrics", {
        "concept": "ليلة صيف في الصحراء", "style": "khaleeji pop",
        "dialect": "khaleeji", "language": "ar",
    }, ctx)
    assert "[Chorus]" in out["lyrics"]
    assert out["title"]
    # goes through ctx.llm (the writer + its producer-style sub-call),
    # never worker_llm
    assert len(ctx.llm.calls) >= 1
    assert len(ctx.worker_llm.calls) == 0


# ---------------------------------------------------------------------------
# critique_draft
# ---------------------------------------------------------------------------

def test_critique_draft_parses_json_response(tmp_path):
    critique_json = json.dumps({
        "scores": {"hook": 0.8, "singability": 0.7, "on_brand": 0.9,
                    "originality": 0.6, "tashkeel": 0.95},
        "overall": 0.82,
        "notes": "Strong hook, on-brand.",
    })
    ctx = _ctx(tmp_path, worker_llm=_FakeLLM(response=critique_json))
    out = agent.dispatch_tool("critique_draft", {"lyrics": "[Chorus]\nكورال"}, ctx)
    assert out["overall"] == 0.82
    assert out["scores"]["hook"] == 0.8
    assert "Strong hook" in out["notes"]
    # goes through worker_llm, not the main llm
    assert len(ctx.worker_llm.calls) == 1
    assert len(ctx.llm.calls) == 0


def test_critique_draft_strips_markdown_fences(tmp_path):
    fenced = "```json\n" + json.dumps({"overall": 0.5, "notes": "ok"}) + "\n```"
    ctx = _ctx(tmp_path, worker_llm=_FakeLLM(response=fenced))
    out = agent.dispatch_tool("critique_draft", {"lyrics": "x"}, ctx)
    assert out["overall"] == 0.5


def test_critique_draft_unparseable_returns_safe_default(tmp_path):
    ctx = _ctx(tmp_path, worker_llm=_FakeLLM(response="not json at all"))
    out = agent.dispatch_tool("critique_draft", {"lyrics": "x"}, ctx)
    assert out == {"overall": 0.0, "notes": "unparseable"}


# ---------------------------------------------------------------------------
# get_trends
# ---------------------------------------------------------------------------

def test_get_trends_returns_fresh_cached_briefs_without_llm_call(tmp_path, monkeypatch):
    from datetime import datetime, timezone
    from pipeline import trends as trends_mod

    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    briefs = [{"id": "tb_1", "theme": "old brief", "title_idea": "t",
               "style_hint": "", "language": "ar", "rationale": ""}]
    trends_mod.save_cache(
        tmp_path, datetime.now(timezone.utc).isoformat(timespec="seconds"), briefs)

    ctx = _ctx(tmp_path)
    out = agent.dispatch_tool("get_trends", {}, ctx)
    assert out["briefs"] == briefs
    assert out["stale"] is False
    assert len(ctx.llm.calls) == 0  # cache hit — no LLM call


def test_get_trends_builds_fresh_briefs_when_no_cache(tmp_path, monkeypatch):
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    fresh_briefs = [
        {"theme": f"theme {i}", "title_idea": "t", "style_hint": "",
         "language": "ar", "rationale": "trending"} for i in range(4)
    ]
    llm = _FakeLLM(response=json.dumps(fresh_briefs, ensure_ascii=False))
    ctx = _ctx(tmp_path, llm=llm)
    out = agent.dispatch_tool("get_trends", {}, ctx)
    assert out["stale"] is False
    assert len(out["briefs"]) == 4
    assert len(llm.calls) >= 1
    # cache file now exists for next cycle
    assert (tmp_path / "trend_briefs.json").exists()


# ---------------------------------------------------------------------------
# queue_proposal — the load-bearing shape test
# ---------------------------------------------------------------------------

def test_queue_proposal_writes_awaiting_approval_agent_run(tmp_path):
    ctx = _ctx(tmp_path)
    out = agent.dispatch_tool("queue_proposal", {
        "title": "وعد الليل", "concept": "c", "lyrics": "L", "style": "khaleeji",
        "dialect": "khaleeji", "language": "ar",
        "rationale": "trending + on brand", "self_score": 0.82}, ctx)
    run_id = out["run_id"]
    assert run_id in ctx.queued

    state = _read_run_state(tmp_path, run_id)
    assert state["status"] == "awaiting_approval"
    assert state["source"] == "agent"
    assert state["kind"] == "song"
    assert state["artist_id"] == ctx.artist["id"]
    assert state["title"] == "وعد الليل"
    assert state["agent_self_score"] == 0.82
    assert "agent_rationale" in state
    assert state["agent_rationale"] == "trending + on brand"
    assert "agent_trace_path" in state
    assert "created_at" in state
    # the agent never chooses the paid tier
    assert "quality_tier" not in state

    song_json = json.loads((tmp_path / run_id / "song.json").read_text(encoding="utf-8"))
    assert song_json["title"] == "وعد الليل"
    assert song_json["lyrics"] == "L"
    assert song_json["language"] == "ar"

    assert (tmp_path / run_id / "lyrics.txt").read_text(encoding="utf-8") == "L"


def test_queue_proposal_multiple_calls_each_append_to_queued(tmp_path):
    ctx = _ctx(tmp_path)
    out1 = agent.dispatch_tool("queue_proposal", {
        "title": "أ", "concept": "c1", "lyrics": "L1", "style": "khaleeji",
        "dialect": "khaleeji", "language": "ar", "rationale": "r1",
        "self_score": 0.7}, ctx)
    out2 = agent.dispatch_tool("queue_proposal", {
        "title": "ب", "concept": "c2", "lyrics": "L2", "style": "khaleeji",
        "dialect": "khaleeji", "language": "ar", "rationale": "r2",
        "self_score": 0.75}, ctx)
    assert out1["run_id"] != out2["run_id"]
    assert ctx.queued == [out1["run_id"], out2["run_id"]]


def test_queue_proposal_reuses_draft_lyrics_style_and_cover(tmp_path):
    """queue_proposal must not throw away the producer-pass output
    draft_lyrics already paid for (style_prompt/cover_prompt/etc) — the
    proposal should carry it, not blanks, when the lyrics match a draft
    from this cycle."""
    ctx = _ctx(tmp_path)
    drafted = agent.dispatch_tool("draft_lyrics", {
        "concept": "ليلة صيف", "style": "khaleeji pop",
        "dialect": "khaleeji", "language": "ar"}, ctx)

    out = agent.dispatch_tool("queue_proposal", {
        "title": drafted["title"], "concept": "ليلة صيف",
        "lyrics": drafted["lyrics"], "style": "khaleeji pop",
        "dialect": "khaleeji", "language": "ar",
        "rationale": "on brand", "self_score": 0.8}, ctx)

    song_json = json.loads(
        (tmp_path / out["run_id"] / "song.json").read_text(encoding="utf-8"))
    # cover_prompt passes through from the LLM's parsed output untouched
    assert song_json["cover_prompt"] == "a desert night, warm lantern light"
    # style_prompt is producer-pass output (may differ from the raw LLM
    # field — generate_song_script overrides it) but must be non-blank,
    # proving queue_proposal recovered the draft instead of writing ""
    assert song_json["style_prompt"] != ""
    assert song_json["art_direction"] == "warm desert night"


def test_queue_proposal_never_calls_llm(tmp_path):
    """queue_proposal takes the agent's already-drafted lyrics verbatim —
    it must not re-generate them via an LLM call."""
    ctx = _ctx(tmp_path)
    agent.dispatch_tool("queue_proposal", {
        "title": "t", "concept": "c", "lyrics": "L", "style": "khaleeji",
        "dialect": "khaleeji", "language": "ar", "rationale": "r",
        "self_score": 0.5}, ctx)
    assert len(ctx.llm.calls) == 0
    assert len(ctx.worker_llm.calls) == 0
