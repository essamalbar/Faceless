"""Autonomous Artist Agent — the 6 read-and-queue tools.

These tool schemas + `dispatch_tool` ARE the security boundary (spec §4.1,
§10): the agent's entire toolbox can only read state and queue a proposal.
There is deliberately no `approve`/`spend`/`render`/`publish`/`post`/
`deduct`/`delete`/`charge` tool — the only money path
(`approve_song` → `credits.check_or_deduct` → paid worker) fires solely on
a human tap, in `pipeline/api.py`, never from here.

The bounded Claude tool-use loop that calls these tools (`AgentRunner`) is
built in a later task, in this same module.

Spec: docs/superpowers/specs/2026-09-25-autonomous-artist-agent-design.md
  §4.1 (tool table), §6 (proposal = an awaiting_approval run).
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline import agent_memory
from pipeline.song_lyrics import generate_song_script

# ---------------------------------------------------------------------------
# Tool schemas — Anthropic tool-use format. `additionalProperties: false` +
# an explicit `required` list on every schema (strict-tool-calling friendly).
# ---------------------------------------------------------------------------

TOOLS: list[dict] = [
    {
        "name": "get_trends",
        "description": (
            "Get current trend briefs (mood/cultural-calendar context ideas "
            "for a song — never covers or soundalikes) for the artist's "
            "target language. Returns a fresh cached set when available, "
            "else generates and caches new ones. $0 — never spends money "
            "or queues/publishes anything."
        ),
        "input_schema": {
            "type": "object",
            "additionalProperties": False,
            "required": [],
            "properties": {},
        },
    },
    {
        "name": "get_artist_context",
        "description": (
            "Get the artist's identity (name, voice/persona, default "
            "style/dialect/language), a discography summary (count + "
            "recent titles), and this artist's agent memory (distilled "
            "taste + recent approve/reject/edit decisions). Read-only; $0."
        ),
        "input_schema": {
            "type": "object",
            "additionalProperties": False,
            "required": [],
            "properties": {},
        },
    },
    {
        "name": "draft_lyrics",
        "description": (
            "Run the existing $0 writer pass to draft full lyrics + a "
            "title for a song concept, for you to inspect and critique. "
            "Does not queue or persist anything."
        ),
        "input_schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["concept", "style", "dialect", "language"],
            "properties": {
                "concept": {
                    "type": "string",
                    "description": "The song's theme/concept.",
                },
                "style": {
                    "type": "string",
                    "description": "Style/genre hint, e.g. 'khaleeji pop'.",
                },
                "dialect": {
                    "type": "string",
                    "description": (
                        "Arabic dialect (msa/egyptian/khaleeji/levantine/"
                        "iraqi), or '' if not applicable."
                    ),
                },
                "language": {
                    "type": "string",
                    "description": "Target language code, e.g. 'ar' or 'en'.",
                },
            },
        },
    },
    {
        "name": "critique_draft",
        "description": (
            "Score a lyrics draft on hook strength, singability, on-brand "
            "fit, originality, and tashkeel (diacritics) completeness. "
            "Read-only; $0."
        ),
        "input_schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["lyrics"],
            "properties": {
                "lyrics": {
                    "type": "string",
                    "description": "The full lyrics text to critique.",
                },
            },
        },
    },
    {
        "name": "queue_proposal",
        "description": (
            "Queue a finished song concept as an awaiting_approval run for "
            "a human to review and approve. This is the ONLY way this "
            "agent can surface a proposal — it never spends money and "
            "never publishes anything; a human must tap Approve before "
            "any spend happens."
        ),
        "input_schema": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "title", "concept", "lyrics", "style", "dialect",
                "language", "rationale", "self_score",
            ],
            "properties": {
                "title": {"type": "string", "description": "Song title."},
                "concept": {
                    "type": "string",
                    "description": "The song's theme/concept.",
                },
                "lyrics": {
                    "type": "string",
                    "description": "The final lyrics text (from draft_lyrics).",
                },
                "style": {
                    "type": "string",
                    "description": "Style/genre hint.",
                },
                "dialect": {
                    "type": "string",
                    "description": "Arabic dialect, or '' if not applicable.",
                },
                "language": {
                    "type": "string",
                    "description": "Target language code.",
                },
                "rationale": {
                    "type": "string",
                    "description": "Why this concept, why now (trend/brand fit).",
                },
                "self_score": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                    "description": "This agent's own critique score, 0-1.",
                },
            },
        },
    },
    {
        "name": "finish",
        "description": (
            "End this artist's cycle. Call this once done proposing (or "
            "deciding not to propose anything) this cycle."
        ),
        "input_schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["summary"],
            "properties": {
                "summary": {
                    "type": "string",
                    "description": (
                        "One or two sentences summarizing what was done "
                        "this cycle."
                    ),
                },
            },
        },
    },
]


# ---------------------------------------------------------------------------
# ToolContext
# ---------------------------------------------------------------------------

@dataclass
class ToolContext:
    """Everything one tool call needs. Not frozen — `queued` accumulates
    across a cycle's tool calls."""
    user_root: Path
    artist: dict
    llm: Any
    worker_llm: Any
    config: Any
    queued: list[str] = field(default_factory=list)
    # Cache of this cycle's draft_lyrics results, keyed by lyrics text, so
    # queue_proposal can recover the FULL SongScript (style_prompt,
    # cover_prompt, art_direction, scene_prompts, ...) that draft_lyrics
    # already paid for — without re-calling the LLM (queue_proposal must
    # never regenerate lyrics/style).
    drafts: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Minimal run-dir helpers, self-contained (deliberately NOT importing
# pipeline.api — that module is heavy and importing it here risks a
# circular import). These mirror pipeline/api.py's `_read_state` /
# `_write_state` / `_make_run_id` byte-for-byte so a queued proposal is a
# normal `api_state.json` the rest of the system already knows how to read.
# ---------------------------------------------------------------------------

def _state_path(run_dir: Path) -> Path:
    return run_dir / "api_state.json"


def _read_state(run_dir: Path) -> dict:
    p = _state_path(run_dir)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _write_state(run_dir: Path, **kwargs: Any) -> None:
    """Read-modify-write of api_state.json, atomic rename (temp+replace) so
    a concurrent reader never sees a half-written file."""
    state = _read_state(run_dir)
    state.update(kwargs)
    state["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    path = _state_path(run_dir)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _make_run_id(root: Path) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M%S")
    base = root / ts
    suffix = 0
    while base.exists():
        suffix += 1
        base = root / f"{ts}-{suffix}"
    return base.name


# ---------------------------------------------------------------------------
# get_trends
# ---------------------------------------------------------------------------

_TRENDS_TTL_H = float(os.environ.get("TRENDS_TTL_H", "12"))


def _get_trends(_tool_input: dict, ctx: ToolContext) -> dict:
    """Mirrors GET /trends/briefs + the morning-drafts sweep (api.py:1096,
    1220): cached briefs when fresh, else one LLM call to build new ones."""
    from pipeline import trends as trends_mod

    language = ctx.artist.get("default_language", "ar")
    cached = trends_mod.load_cache(ctx.user_root)
    if cached:
        try:
            age_h = (
                datetime.now(timezone.utc)
                - datetime.fromisoformat(cached["generated_at"])
            ).total_seconds() / 3600
            if age_h <= _TRENDS_TTL_H:
                return {"briefs": cached["briefs"], "stale": False}
        except (KeyError, TypeError, ValueError):
            pass  # unreadable timestamp → fall through and regenerate

    api_key = os.environ.get("YOUTUBE_API_KEY", "")
    trending = trends_mod.fetch_trending_music(api_key) if api_key else []
    today = datetime.now(timezone.utc).date().isoformat()
    try:
        briefs = trends_mod.build_briefs(
            ctx.llm, trending, language=language, today=today)
    except Exception as e:
        if cached:
            return {"briefs": cached["briefs"], "stale": True, "error": str(e)}
        return {"briefs": [], "stale": True, "error": str(e)}
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    trends_mod.save_cache(ctx.user_root, generated_at, briefs)
    return {"briefs": briefs, "stale": False}


# ---------------------------------------------------------------------------
# get_artist_context
# ---------------------------------------------------------------------------

def _discography_summary(user_root: Path, artist_id: str, limit: int = 5) -> dict:
    """Cheap discography summary from run dirs on disk — count + the most
    recent titles. No DB query (the DB stays financial-only)."""
    if not artist_id or not user_root.exists():
        return {"count": 0, "recent_titles": []}
    rows: list[tuple[str, str]] = []
    for d in user_root.iterdir():
        if not d.is_dir():
            continue
        st = _read_state(d)
        if st.get("kind") == "song" and st.get("artist_id") == artist_id:
            rows.append((d.name, str(st.get("title") or "")))
    rows.sort(key=lambda r: r[0], reverse=True)  # run ids are timestamps
    return {
        "count": len(rows),
        "recent_titles": [title for _run_id, title in rows[:limit] if title],
    }


def _get_artist_context(_tool_input: dict, ctx: ToolContext) -> dict:
    artist = ctx.artist
    artist_id = artist.get("id", "")
    identity = {
        "id": artist_id,
        "name": artist.get("name", ""),
        "handle": artist.get("handle", ""),
        "bio": artist.get("bio", ""),
        "persona_id": artist.get("persona_id"),
        "default_style": artist.get("default_style", ""),
        "default_language": artist.get("default_language", "ar"),
        "default_dialect": artist.get("default_dialect", ""),
        "default_vocal_gender": artist.get("default_vocal_gender", "m"),
        # Pre-existing artist rows may lack this (added alongside the
        # agent feature) — always .get() with a default, never index.
        "agent_enabled": artist.get("agent_enabled", False),
    }
    discography = _discography_summary(ctx.user_root, artist_id)
    memory = agent_memory.load_memory(ctx.user_root, artist_id)
    return {"identity": identity, "discography": discography, "memory": memory}


# ---------------------------------------------------------------------------
# draft_lyrics
# ---------------------------------------------------------------------------

def _draft_lyrics(tool_input: dict, ctx: ToolContext) -> dict:
    """The same $0 writer pass `_write_song_draft` uses (api.py:1137),
    called with `ctx.llm` (the loop's FallbackLLM router in production;
    a fake in tests)."""
    concept = str(tool_input.get("concept") or "")
    style = str(tool_input.get("style") or "") or None
    dialect = str(tool_input.get("dialect") or "") or None
    language = str(tool_input.get("language") or "") or ctx.artist.get(
        "default_language", "ar")

    script = generate_song_script(
        llm=ctx.llm,
        theme=concept,
        custom_lyrics=None,
        style_hint=style,
        language=language,
        dialect=dialect,
        vocal_gender=ctx.artist.get("default_vocal_gender") or "m",
    )
    # Stash the full SongScript so queue_proposal can recover
    # style_prompt/cover_prompt/etc. without a second LLM call. Keyed on
    # stripped lyrics — the lyrics round-trip through the agent model
    # (tool_result -> model -> queue_proposal input) and a model may trim
    # trailing whitespace/newlines along the way.
    ctx.drafts[script.lyrics.strip()] = script
    return {"lyrics": script.lyrics, "title": script.title}


# ---------------------------------------------------------------------------
# critique_draft
# ---------------------------------------------------------------------------

_CRITIQUE_SYSTEM = """You are a music A&R judge for an AI song label.
Score the given song lyrics on five axes, each 0.0-1.0:
  - hook: how strong/memorable the chorus hook is
  - singability: how naturally singable the phrasing/meter is
  - on_brand: how well it fits a commercial, radio-ready pop/folk song
  - originality: distinct from generic AI-song clichés
  - tashkeel: completeness of Arabic diacritics (1.0 if not Arabic)

Reply with ONLY a JSON object, no markdown, no commentary:
{"scores": {"hook": <0-1>, "singability": <0-1>, "on_brand": <0-1>, \
"originality": <0-1>, "tashkeel": <0-1>}, "overall": <0-1>, \
"notes": "one or two sentences"}"""


def _parse_critique(raw: str) -> dict:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?|\n?```$", "", text,
                      flags=re.MULTILINE).strip()
    if not text.startswith("{"):
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            text = text[start:end + 1]
    try:
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("critique response is not a JSON object")
    except (json.JSONDecodeError, ValueError):
        return {"overall": 0.0, "notes": "unparseable"}

    scores = data.get("scores")
    if not isinstance(scores, dict):
        scores = {}
    try:
        overall = float(data.get("overall", 0.0))
    except (TypeError, ValueError):
        overall = 0.0
    notes = str(data.get("notes", ""))
    return {"scores": scores, "overall": overall, "notes": notes}


def _critique_draft(tool_input: dict, ctx: ToolContext) -> dict:
    lyrics = str(tool_input.get("lyrics") or "")
    raw = ctx.worker_llm.complete(lyrics, system=_CRITIQUE_SYSTEM)
    return _parse_critique(raw)


# ---------------------------------------------------------------------------
# queue_proposal — writes an awaiting_approval run indistinguishable from a
# morning-draft proposal (spec §6), except source="agent" + the new
# agent_rationale / agent_self_score / agent_trace_path fields.
# ---------------------------------------------------------------------------

def _queue_proposal(tool_input: dict, ctx: ToolContext) -> dict:
    artist = ctx.artist
    title = str(tool_input.get("title") or "").strip() or "Untitled"
    concept = str(tool_input.get("concept") or "")
    lyrics = str(tool_input.get("lyrics") or "")
    style = str(tool_input.get("style") or "") or artist.get("default_style", "")
    language = str(tool_input.get("language") or "") or artist.get(
        "default_language", "ar")
    rationale = str(tool_input.get("rationale") or "")
    try:
        self_score = float(tool_input.get("self_score", 0.0))
    except (TypeError, ValueError):
        self_score = 0.0

    ctx.user_root.mkdir(parents=True, exist_ok=True)
    run_id = _make_run_id(ctx.user_root)
    run_dir = ctx.user_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    # Task 4 fills the actual trace contents. Stored relative to run_dir
    # (like every other run artifact — song.json, lyrics.txt) rather than
    # an absolute path, so a relocated FACELESS_OUT_ROOT doesn't strand it.
    trace_path = "agent_trace.json"

    # Recover the full SongScript draft_lyrics already produced (same
    # lyrics text) so the proposal carries the real producer-pass
    # style/cover/scene prompts instead of blanks — without a second LLM
    # call. Falls back to blanks if the agent queues lyrics it never
    # drafted through this cycle's draft_lyrics tool.
    draft = ctx.drafts.get(lyrics.strip())

    # Write the run dir + an initial transient state FIRST — mirrors
    # `_write_song_draft` (api.py:1162-1202): song.json/lyrics.txt land
    # before the state ever says "awaiting_approval", so a process death
    # mid-write never leaves an awaiting_approval run with no song.json
    # (which would 500 on Approve — api.py:4605 does
    # `json.loads((run_dir/"song.json").read_text())` unconditionally for
    # that status). NOT setting a paid tier here (video_mode/quality_tier):
    # those follow the artist's/config defaults exactly like a manual song.
    # The agent proposes the art, never the price.
    _write_state(
        run_dir,
        kind="song",
        status="writing_lyrics",
        user_id=ctx.user_root.name,
        theme=concept,
        video_mode="static",
        artist_id=artist.get("id"),
        source="agent",
        created_at=created_at,
    )
    try:
        (run_dir / "song.json").write_text(json.dumps({
            "title": title,
            "lyrics": lyrics,
            "style_prompt": draft.style_prompt if draft else style,
            "cover_prompt": draft.cover_prompt if draft else "",
            "language": language,
            "vocal_gender": artist.get("default_vocal_gender") or "m",
            "persona_id": artist.get("persona_id"),
            "suno_model": None,
            "video_mode": "static",
            "art_direction": draft.art_direction if draft else "",
            "scene_prompts": draft.scene_prompts if draft else [],
            "negative_tags": draft.negative_tags if draft else "",
            "style_source": draft.style_source if draft else "agent",
            "writer_tier": draft.writer_tier if draft else "",
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        (run_dir / "lyrics.txt").write_text(lyrics, encoding="utf-8")
    except Exception as e:
        # Mirrors `_write_song_draft`'s failure handling (api.py:1179-1182):
        # never leave the run stuck at a transient status — mark it failed
        # so `_has_agent_run_today`-style idempotency guards (status !=
        # "failed" counts as "already ran today") don't block a same-day
        # retry for this artist.
        _write_state(run_dir, status="failed",
                     last_error=f"queue_proposal write failed: {e}")
        raise
    # Only now flip to awaiting_approval — song.json/lyrics.txt are
    # guaranteed to exist by the time a human can see this run to approve it.
    _write_state(
        run_dir,
        status="awaiting_approval",
        title=title,
        agent_rationale=rationale,
        agent_self_score=self_score,
        agent_trace_path=trace_path,
    )

    ctx.queued.append(run_id)
    return {"run_id": run_id}


# ---------------------------------------------------------------------------
# finish
# ---------------------------------------------------------------------------

def _finish(_tool_input: dict, _ctx: ToolContext) -> dict:
    return {"done": True}


# ---------------------------------------------------------------------------
# Dispatch — the security perimeter. Exactly these 6 names; anything else
# (a hallucinated or malicious tool name) returns an error, never raises,
# so the bounded loop always survives a bad tool call.
# ---------------------------------------------------------------------------

_HANDLERS = {
    "get_trends": _get_trends,
    "get_artist_context": _get_artist_context,
    "draft_lyrics": _draft_lyrics,
    "critique_draft": _critique_draft,
    "queue_proposal": _queue_proposal,
    "finish": _finish,
}


def dispatch_tool(name: str, tool_input: dict, ctx: ToolContext) -> dict:
    handler = _HANDLERS.get(name)
    if handler is None:
        return {"error": f"unknown tool: {name}"}
    try:
        return handler(tool_input, ctx)
    except Exception as e:  # a tool must never crash the loop
        return {"error": f"{name} failed: {e}"}
