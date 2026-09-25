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


# ---------------------------------------------------------------------------
# AgentRunner — the bounded Claude tool-use loop (spec §4).
#
# A MANUAL loop over the Anthropic SDK's `messages.create(tools=...)`
# protocol — deliberately NOT the beta Tool Runner — chosen for determinism,
# testability, and no beta dependency (spec §4, "external services mocked in
# tests" invariant). `anthropic_client` is always dependency-injected: a
# `ScriptedAnthropic` stub in tests, `anthropic.Anthropic()` in production
# (Task 5's `run.py --agent` worker). Every bound (max_iterations, token
# budget, critique_threshold, proposals_per_cycle) is enforced by THIS loop,
# never left to the model's own judgement or to prompt wording alone.
# ---------------------------------------------------------------------------

_DEFAULT_MAX_TOKENS = 8192


class _NoLLMAvailable:
    """A `.complete()`-shaped sentinel used when no LLM provider key is
    configured. Raises only when actually CALLED, never at construction
    time — so building a ToolContext never explodes in an environment with
    no ANTHROPIC/GEMINI/GROQ key (e.g. a test env). The resulting error is
    caught by `dispatch_tool`'s own per-tool try/except and surfaces as a
    normal tool_result, never a loop crash."""

    def complete(self, prompt: str, system: str | None = None) -> str:
        raise RuntimeError(
            "no LLM provider configured (ANTHROPIC_API_KEY / GEMINI_API_KEY "
            "/ GROQ_API_KEY) -- draft_lyrics/critique_draft unavailable "
            "this cycle")


def _build_llm_router() -> Any:
    """Anthropic -> Gemini -> Groq, best-available-first — mirrors
    `pipeline.api._build_llm()`. Reimplemented here (not imported from
    pipeline.api) to avoid pulling that heavy module into pipeline.agent
    (see the module docstring's circular-import note). Every provider
    import is function-local, and this never raises at construction time —
    only a real `.complete()` call can fail, and dispatch_tool always
    catches that."""
    providers: list[Any] = []
    if os.environ.get("ANTHROPIC_API_KEY"):
        from pipeline.llm_anthropic import AnthropicClient
        providers.append(AnthropicClient())
    if os.environ.get("GEMINI_API_KEY"):
        from pipeline.llm import GeminiClient
        providers.append(GeminiClient())
    if os.environ.get("GROQ_API_KEY"):
        from pipeline.llm_groq import GroqClient
        providers.append(GroqClient())
    if not providers:
        return _NoLLMAvailable()
    from pipeline.llm import FallbackLLM
    chain = providers[-1]
    for provider in reversed(providers[:-1]):
        chain = FallbackLLM(provider, chain)
    return chain


def _build_worker_llm(agent_cfg: Any) -> Any:
    """The cheaper sub-call model (spec §4: `worker_model`, default
    claude-sonnet-5) that backs draft_lyrics/critique_draft. Pins the
    configured worker model when Anthropic is available; otherwise falls
    back to the same best-available router as the main brain."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        from pipeline.llm_anthropic import AnthropicClient
        worker_model = getattr(agent_cfg, "worker_model", None) or "claude-sonnet-4-6"
        try:
            return AnthropicClient(model=worker_model)
        except Exception:
            pass  # fall through to the general router below
    return _build_llm_router()


def _system_prompt(artist: dict, agent_cfg: Any) -> str:
    """Casts the model as the artist's A&R manager + creative partner
    (spec §4): artist identity, the label's originality rule (trends are
    mood-context only — never covers/soundalikes), the full-tashkeel +
    singability contract, and the approve-before-spend framing. The tool
    list IS the actual security boundary — this just tells the model the
    truth about it, so it doesn't waste turns trying tools that don't
    exist."""
    name = artist.get("name") or "this artist"
    bio = artist.get("bio") or "(no bio on file)"
    persona_id = artist.get("persona_id")
    persona_note = f" (persona id: {persona_id})" if persona_id else ""
    style = artist.get("default_style") or "commercial pop"
    dialect = artist.get("default_dialect") or ""
    language = artist.get("default_language") or "ar"
    quota = getattr(agent_cfg, "proposals_per_cycle", 2)
    threshold = getattr(agent_cfg, "critique_threshold", 0.6)
    dialect_line = (
        f"- Default dialect: {dialect} — write fully diacritized {dialect} "
        f"Arabic unless the concept genuinely calls for another."
        if dialect else ""
    )

    return f"""You are the A&R manager and creative partner for the AI recording artist "{name}".

ARTIST IDENTITY
- Name: {name}
- Bio / persona: {bio}{persona_note}
- Default style: {style}
- Default language: {language}
{dialect_line}

YOUR JOB THIS CYCLE
Reason about what this artist should release next: ground yourself in
current trends and this artist's identity, memory, and discography, draft a
concept and full lyrics, critique your own draft honestly, and queue up to
{quota} strong proposals for a human to review.

ORIGINALITY RULE (non-negotiable)
Trends are mood/cultural-calendar context ONLY. Never write a cover,
soundalike, or lyrical paraphrase of a specific existing song or artist.
Every proposal must be an original composition with original lyrics.

QUALITY BAR
- Lyrics must be fully diacritized (tashkeel) and genuinely singable —
  natural meter and phrasing, not just grammatically correct prose.
- Only queue a proposal you would honestly score at {threshold} or higher.
  A weaker draft should be revised or dropped, not queued anyway.
- Queue at most {quota} proposals this cycle, then call finish.

YOU PROPOSE — YOU CANNOT SPEND
Your entire toolbox is read-and-queue only. You have NO tool that can
deduct a credit, start a paid render, or publish anything — there is no
code path from you to a charge or a public post. A human reviews every
proposal you queue and taps Approve before any money moves, so be genuinely
specific and ambitious; the human, not you, carries the spend risk.

Use get_trends and get_artist_context first to ground your proposal in real
context, then draft_lyrics and critique_draft before you queue_proposal.
Call finish when you are done for this cycle (including if you decide
nothing this cycle is worth proposing)."""


def _write_trace_for_queued(user_root: Path, run_ids: list[str], trace: dict) -> None:
    """Persist the cycle's reasoning trace to each queued proposal's
    `agent_trace_path` (spec §4, §6) — a path `_queue_proposal` stores
    RELATIVE to the run dir, resolved here against `run_dir`. Best-effort:
    a trace-write failure must never turn an already-queued,
    already-awaiting_approval proposal into a broken one."""
    for run_id in run_ids:
        run_dir = user_root / run_id
        try:
            state = _read_state(run_dir)
            rel = state.get("agent_trace_path") or "agent_trace.json"
            path = run_dir / rel
            path.write_text(
                json.dumps(trace, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
        except Exception as e:
            print(f"[agent] failed to write trace for run {run_id}: {e}")


class AgentRunner:
    """Runs one bounded tool-use cycle for one artist. Stateless across
    calls — `run_cycle` builds and owns everything for a single cycle (one
    ToolContext, one reasoning trace); nothing is shared or cached on
    `self`, so a fresh `AgentRunner()` per cycle (or one reused across many)
    behaves identically."""

    def run_cycle(
        self,
        user_root: Path,
        artist: dict,
        *,
        anthropic_client: Any,
        config: Any,
    ) -> dict:
        agent_cfg = config.agent
        ctx = ToolContext(
            user_root=user_root,
            artist=artist,
            llm=_build_llm_router(),
            worker_llm=_build_worker_llm(agent_cfg),
            config=agent_cfg,
        )
        system = _system_prompt(artist, agent_cfg)
        artist_name = artist.get("name") or "this artist"
        messages: list[dict] = [{
            "role": "user",
            "content": (
                f'Begin this cycle for "{artist_name}". Start with '
                "get_trends and get_artist_context."
            ),
        }]

        trace: dict[str, Any] = {
            "artist_id": artist.get("id"),
            "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "steps": [],
        }
        iterations = 0
        output_tokens_used = 0
        stopped = "max_iterations"  # the default outcome if the bound is hit

        try:
            while iterations < agent_cfg.max_iterations:
                iterations += 1
                response = anthropic_client.messages.create(
                    model=agent_cfg.model,
                    max_tokens=_DEFAULT_MAX_TOKENS,
                    system=system,
                    tools=TOOLS,
                    messages=messages,
                    thinking={"type": "adaptive", "display": "summarized"},
                    output_config={"effort": "high"},
                    # Prompt caching (spec §4): system + TOOLS are byte-stable
                    # across every iteration of this loop (no timestamps or
                    # per-iteration data anywhere in them). Top-level
                    # auto-caching places the cache breakpoint at the end of
                    # the request, so each call caches the full prefix sent
                    # so far (system + TOOLS + conversation history) and the
                    # NEXT iteration reads that whole prefix back at ~10%
                    # cost — the growing history is cached too, which is the
                    # right outcome for an agentic loop like this one.
                    cache_control={"type": "ephemeral"},
                )

                usage = getattr(response, "usage", None)
                if usage is not None:
                    output_tokens_used += getattr(usage, "output_tokens", 0) or 0

                content = list(response.content or [])
                messages.append({"role": "assistant", "content": content})

                for block in content:
                    btype = getattr(block, "type", None)
                    if btype in ("thinking", "redacted_thinking"):
                        trace["steps"].append({
                            "type": "thinking",
                            "text": (getattr(block, "thinking", None)
                                     or getattr(block, "data", None) or ""),
                        })
                    elif btype == "text":
                        trace["steps"].append({
                            "type": "text",
                            "text": getattr(block, "text", "") or "",
                        })

                if output_tokens_used > agent_cfg.token_budget:
                    stopped = "budget"
                    break

                if getattr(response, "stop_reason", None) != "tool_use":
                    # The model ended its turn without invoking a tool (e.g.
                    # a plain text reply) — nothing more for this cycle to do.
                    stopped = "finished"
                    break

                tool_results: list[dict] = []
                finished = False
                for block in content:
                    if getattr(block, "type", None) != "tool_use":
                        continue
                    name = getattr(block, "name", "")
                    tool_input = getattr(block, "input", None) or {}
                    tool_id = getattr(block, "id", "")

                    trace["steps"].append({
                        "type": "tool_call", "name": name, "input": tool_input,
                    })

                    result = self._handle_tool_call(name, tool_input, ctx, agent_cfg)
                    if name == "finish":
                        finished = True

                    trace["steps"].append({
                        "type": "tool_result", "name": name, "result": result,
                    })
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": json.dumps(result, ensure_ascii=False, default=str),
                    })

                messages.append({"role": "user", "content": tool_results})

                if finished:
                    stopped = "finished"
                    break
        except Exception as e:  # fail safe: never let a cycle crash the sweep
            stopped = "error"
            trace["steps"].append({"type": "error", "text": str(e)})
            print(f"[agent] cycle for artist={artist.get('id')} failed safe: {e}")

        trace["stopped"] = stopped
        trace["iterations"] = iterations
        _write_trace_for_queued(user_root, ctx.queued, trace)

        return {
            "queued": list(ctx.queued),
            "iterations": iterations,
            "stopped": stopped,
        }

    @staticmethod
    def _handle_tool_call(
        name: str, tool_input: dict, ctx: ToolContext, agent_cfg: Any,
    ) -> dict:
        """The loop's own hard-gate policies (spec §4): `critique_threshold`
        and `proposals_per_cycle` are enforced HERE, before a queue_proposal
        call ever reaches `dispatch_tool` — a rejected proposal never
        creates a run dir at all, and the gate can't be talked around by
        prompt wording alone."""
        if name == "queue_proposal":
            quota = getattr(agent_cfg, "proposals_per_cycle", 2)
            if len(ctx.queued) >= quota:
                return {
                    "error": (
                        f"quota reached ({len(ctx.queued)}/{quota} proposals "
                        "already queued this cycle) -- do not queue another; "
                        "call finish now."
                    ),
                }
            threshold = getattr(agent_cfg, "critique_threshold", 0.6)
            try:
                self_score = float(tool_input.get("self_score", 0.0))
            except (TypeError, ValueError):
                self_score = 0.0
            if self_score < threshold:
                return {
                    "error": (
                        f"self_score {self_score} is below the quality bar "
                        f"({threshold}) -- not queued. Improve the draft "
                        "and try again, or finish without proposing it."
                    ),
                }
        return dispatch_tool(name, tool_input, ctx)
