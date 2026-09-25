# Autonomous Artist Agent — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a per-artist autonomous A&R agent — a bounded Claude tool-use loop that reasons about what an artist should release next, drafts + self-critiques a song, and queues `awaiting_approval` proposals that stop at the existing human spend gate.

**Architecture:** A new `pipeline/agent.py` (the `AgentRunner` + 6 read-and-queue tools) runs a bounded Anthropic tool-use loop, invoked by a new `run.py --agent` worker mode, dispatched per opted-in artist by a new `POST /admin/run-agent` sweep (the morning-drafts pattern). Proposals are ordinary `awaiting_approval` runs (`source="agent"`), so the existing approve→render→publish flow is untouched. A per-artist JSON memory store learns from approve/reject/edit. A Flutter "A&R" feed surfaces proposals with the agent's reasoning.

**Tech Stack:** Python 3.11 / FastAPI (`pipeline/`), the official `anthropic` SDK (tool use), pytest with external services mocked via `monkeypatch`; Flutter/Dart for the feed. Backend tests via `uv run pytest`; Flutter via `flutter test`.

**Spec:** `docs/superpowers/specs/2026-09-25-autonomous-artist-agent-design.md`

## Global Constraints

- **Approve-before-spend is absolute.** The agent's 6 tools are read-and-queue only — there is NO tool that deducts a credit, starts a paid render, or publishes. The only spend path is the existing `approve_song` → `credits.check_or_deduct`, fired by a human tap. No agent code path may reach a charge or a public post.
- **Behavior-preserving.** The existing `create_song`/`approve_song`/worker-render/YouTube-publish flow, the credit ledger, the two-phase gate, and all i18n keys are unchanged. Proposals reuse the `awaiting_approval` run shape morning-drafts already produces.
- **Off by default, three gates:** the agent runs only when `FACELESS_AGENT_ENABLED=1` AND `config.agent.enabled` is true AND the artist's `agent_enabled` is true. Any one false → no-op.
- **Requires an Anthropic key.** The tool-use loop calls the Anthropic SDK directly (tool use is not on the Groq/Gemini fallback). No `ANTHROPIC_API_KEY` → the agent no-ops for that cycle and logs it; it never errors the sweep. (`draft_lyrics` still uses the existing `FallbackLLM` router.)
- **The agent never picks the spend tier.** `queue_proposal` carries creative fields only; `video_mode`/`quality_tier` follow artist/config defaults exactly as a manual song.
- **External services mocked in tests.** Never hit the real Anthropic/Kie/YouTube APIs in tests — stub via `monkeypatch` (the repo invariant).
- **All Python files start with `from __future__ import annotations`; use `pathlib.Path`; absolute imports from `pipeline.`.**
- **Verification:** `uv run pytest -q` green (keep the existing 1127 passing); Flutter `flutter test` green (existing 55); `dart analyze` via the Flutter-bundled dart (`/Users/gileshannah/Documents/flutter/bin/dart`), never bare `dart`, never `flutter analyze` (it hangs).

**Config block (`config.yaml > agent`, copy verbatim):**
```yaml
agent:
  enabled: false
  model: claude-opus-5
  worker_model: claude-sonnet-5
  max_iterations: 12
  token_budget: 60000
  proposals_per_cycle: 2
  daily_global_run_cap: 50
  critique_threshold: 0.6
```

**Reused real interfaces (from the codebase):** `_write_song_draft` (api.py:1137), `_has_morning_draft_today` (api.py:1202), `run_morning_drafts` (api.py:1220), `trends.build_briefs`, `approve_song` (api.py:4571), `credits.check_or_deduct`, `_spawn`/`select_backend` (api.py:722 / spawn_backends.py), `_read_state`/`_write_state` (api.py:150-161), `new_artist` (artists.py:44), `PatchArtistRequest` (api.py:558), `_build_llm` (api.py:963), `AnthropicClient` (llm_anthropic.py).

---

### Task 1: Artist `agent_enabled` field + config `agent` block

**Files:** Modify `pipeline/artists.py` (`new_artist`), `pipeline/api.py` (`PatchArtistRequest` + patch field list), `config.yaml`. Test: `tests/test_agent_config.py` (create).

**Interfaces — Produces:** `Artist["agent_enabled"]: bool` (default False); `PatchArtistRequest.agent_enabled: bool | None`; `config["agent"]` dict with the keys above.

- [ ] **Step 1: Write the failing test**
```python
# tests/test_agent_config.py
from __future__ import annotations
from pipeline.artists import new_artist

def test_new_artist_has_agent_enabled_default_false():
    a = new_artist(name="Salma")
    assert a["agent_enabled"] is False

def test_config_has_agent_block(tmp_path, monkeypatch):
    from pipeline.config import load_config  # use the repo's config loader
    cfg = load_config()  # reads config.yaml
    ag = cfg["agent"]
    assert ag["enabled"] is False
    assert ag["model"] == "claude-opus-5"
    assert ag["worker_model"] == "claude-sonnet-5"
    assert ag["max_iterations"] == 12
    assert ag["proposals_per_cycle"] == 2
    assert ag["daily_global_run_cap"] == 50
```
(Adjust `load_config` import to the repo's actual config accessor — grep `config.yaml`/`load_config` first.)

- [ ] **Step 2: Run it — expect FAIL** (`uv run pytest tests/test_agent_config.py -q`).
- [ ] **Step 3: Implement:** add `"agent_enabled": False` to `new_artist`'s returned dict; add `agent_enabled: bool | None = None` to `PatchArtistRequest` and include `"agent_enabled"` in the PATCH patchable-field list (`api.py:5649-5652`); add the `agent` block to `config.yaml` (verbatim from Global Constraints).
- [ ] **Step 4: Run — expect PASS**; `uv run pytest tests/test_artists.py tests/test_agent_config.py -q` green.
- [ ] **Step 5: Commit** `feat(agent): artist agent_enabled toggle + config agent block`

---

### Task 2: Agent memory store (`pipeline/agent_memory.py`)

**Files:** Create `pipeline/agent_memory.py`. Test: `tests/test_agent_memory.py`.

**Interfaces — Produces:**
- `memory_path(user_root: Path, artist_id: str) -> Path` → `<user_root>/agent/<artist_id>.json`
- `load_memory(user_root, artist_id) -> dict` → `{artist_id, preferences_summary: str, decisions: list, updated_at}` (empty defaults if absent)
- `record_decision(user_root, artist_id, *, run_id: str, decision: str, reason: str="", self_score: float|None=None) -> None` (atomic append; `decision` ∈ {"approved","rejected","edited"})
- `distill_preferences(user_root, artist_id, llm) -> str` (rewrites `preferences_summary` from recent decisions via one cheap LLM call; bounded; returns the summary)

- [ ] **Step 1: Write the failing test**
```python
# tests/test_agent_memory.py
from __future__ import annotations
from pathlib import Path
from pipeline import agent_memory as am

def test_load_empty(tmp_path: Path):
    m = am.load_memory(tmp_path, "art_x")
    assert m["decisions"] == [] and m["preferences_summary"] == ""

def test_record_decision_appends_atomically(tmp_path: Path):
    am.record_decision(tmp_path, "art_x", run_id="r1", decision="approved", self_score=0.8)
    am.record_decision(tmp_path, "art_x", run_id="r2", decision="rejected", reason="too sad")
    m = am.load_memory(tmp_path, "art_x")
    assert [d["decision"] for d in m["decisions"]] == ["approved", "rejected"]
    assert m["decisions"][1]["reason"] == "too sad"

def test_distill_uses_llm_and_stores_summary(tmp_path: Path):
    am.record_decision(tmp_path, "art_x", run_id="r1", decision="rejected", reason="abstract")
    class FakeLLM:
        def complete(self, *a, **k): return "Prefers concrete imagery."
    out = am.distill_preferences(tmp_path, "art_x", FakeLLM())
    assert "concrete" in out.lower()
    assert am.load_memory(tmp_path, "art_x")["preferences_summary"] == out
```
(Match `FakeLLM` to the repo's LLM interface — grep `class AnthropicClient`/`def complete`/`def generate` in `pipeline/llm*.py` and mirror the real method name.)

- [ ] **Step 2: Run — expect FAIL.**
- [ ] **Step 3: Implement `pipeline/agent_memory.py`** using the atomic temp+rename pattern from `pipeline/artists.py` (`artists.py:92-100`). `record_decision` = load→append→atomic write. `distill_preferences` = one LLM call over the recent decisions with a tight prompt, store the result. Cap decisions history length.
- [ ] **Step 4: Run — expect PASS**; `uv run pytest tests/test_agent_memory.py -q`.
- [ ] **Step 5: Commit** `feat(agent): per-artist memory store (decisions + distilled preferences)`

---

### Task 3: The 6 agent tools (`pipeline/agent.py` — tool handlers)

**Files:** Create `pipeline/agent.py` (tool schemas + handlers + a `ToolContext`). Test: `tests/test_agent_tools.py`.

**Interfaces — Produces:**
- `TOOLS: list[dict]` — the Anthropic tool schemas for `get_trends`, `get_artist_context`, `draft_lyrics`, `critique_draft`, `queue_proposal`, `finish` (each `{name, description, input_schema}` with `input_schema.additionalProperties=false` + `required`).
- `class ToolContext` — carries `user_root: Path`, `artist: dict`, `llm`, `worker_llm`, `config`, and a `queued: list[str]` (run_ids queued this cycle).
- `def dispatch_tool(name: str, tool_input: dict, ctx: ToolContext) -> dict` — executes one tool, returns a JSON-serializable result. `queue_proposal` writes an `awaiting_approval` run and appends to `ctx.queued`.

**Consumes:** Task 1 config, Task 2 memory, `trends.build_briefs`, the `_write_song_draft`-style writer.

- [ ] **Step 1: Write the failing tests (the tool boundary is load-bearing)**
```python
# tests/test_agent_tools.py
from __future__ import annotations
from pathlib import Path
from pipeline import agent

def _ctx(tmp_path, monkeypatch):
    artist = {"id": "art_x", "name": "Salma", "default_language": "ar",
              "default_style": "khaleeji", "default_dialect": "khaleeji"}
    # stub the writer + trends + llm so no external calls happen
    return agent.ToolContext(user_root=tmp_path, artist=artist,
                             llm=_FakeLLM(), worker_llm=_FakeLLM(), config=_cfg())

def test_tool_list_has_no_spend_or_publish_tool():
    names = {t["name"] for t in agent.TOOLS}
    assert names == {"get_trends","get_artist_context","draft_lyrics",
                     "critique_draft","queue_proposal","finish"}
    forbidden = {"approve","spend","render","publish","post","deduct","delete","charge"}
    assert not (names & forbidden)

def test_queue_proposal_writes_awaiting_approval_run(tmp_path, monkeypatch):
    ctx = _ctx(tmp_path, monkeypatch)
    out = agent.dispatch_tool("queue_proposal", {
        "title": "وعد الليل", "concept": "...", "lyrics": "...",
        "style": "khaleeji", "dialect": "khaleeji", "language": "ar",
        "rationale": "trending + on brand", "self_score": 0.82}, ctx)
    run_id = out["run_id"]; assert run_id in ctx.queued
    # read the written run state
    state = _read_run_state(tmp_path, run_id)
    assert state["status"] == "awaiting_approval"
    assert state["source"] == "agent"
    assert state["agent_self_score"] == 0.82
    assert "agent_rationale" in state
    # the run carries NO tier/spend field the agent chose:
    assert "quality_tier" not in {"chosen_by_agent"}  # tier follows defaults, not queue_proposal input
```
(Provide `_FakeLLM`, `_cfg`, `_read_run_state` helpers in the test; mirror the real writer's state file location.)

- [ ] **Step 2: Run — expect FAIL.**
- [ ] **Step 3: Implement the tools:**
  - `get_trends` → `trends.build_briefs(...)` or the cached briefs for `artist.default_language`.
  - `get_artist_context` → artist identity + a discography summary (count/recent titles) + `agent_memory.load_memory` (preferences + recent decisions).
  - `draft_lyrics` → call the same `generate_song_script` path `_write_song_draft` uses (goes through `FallbackLLM`), return lyrics text.
  - `critique_draft` → one `worker_llm` (sonnet) call returning `{scores:{hook,singability,on_brand,originality,tashkeel}, overall: float, notes}`.
  - `queue_proposal` → write an `awaiting_approval` run reusing the `_write_song_draft` shape but with the agent's concept/lyrics + `source="agent"`, `agent_rationale`, `agent_self_score`, `agent_trace_path` (filled in Task 4); inherit artist identity; do NOT set a paid tier. Return `{run_id}`.
  - `finish` → `{"done": true}`.
  - `TOOLS` schemas with `strict`-friendly `input_schema` (additionalProperties:false, required lists).
- [ ] **Step 4: Run — expect PASS**; `uv run pytest tests/test_agent_tools.py -q`.
- [ ] **Step 5: Commit** `feat(agent): 6 read-and-queue tools (trends/context/draft/critique/queue/finish)`

---

### Task 4: The bounded tool-use loop (`AgentRunner`)

**Files:** Modify `pipeline/agent.py` (add `AgentRunner`). Test: `tests/test_agent_loop.py`.

**Interfaces — Produces:** `class AgentRunner` with `run_cycle(user_root: Path, artist: dict, *, anthropic_client, config) -> dict` returning `{queued: list[str], iterations: int, stopped: str}` where `stopped` ∈ {"finished","max_iterations","budget","error"}. It writes the reasoning trace to `agent_trace_path` on each queued proposal.

**Consumes:** Task 3 tools/dispatch; the Anthropic SDK's `messages.create(model, tools, messages, ...)` tool-use protocol.

- [ ] **Step 1: Write the failing tests (loop control + the GATE-INTEGRITY proof)**
```python
# tests/test_agent_loop.py
from __future__ import annotations
from pipeline import agent

class ScriptedAnthropic:
    """Stub Anthropic client: replays a canned sequence of tool-use / end_turn responses."""
    def __init__(self, script): self.script = list(script); self.calls = []
    class _Msg:  # minimal shape the loop reads: .content (blocks), .stop_reason
        def __init__(self, content, stop): self.content=content; self.stop_reason=stop
    @property
    def messages(self): return self
    def create(self, **kw):
        self.calls.append(kw); return self.script.pop(0)

def _tool_use(name, inp, tid="t"): 
    return {"type":"tool_use","id":tid,"name":name,"input":inp}
def _end(text="done"): return {"type":"text","text":text}

def test_loop_runs_tools_then_finishes(tmp_path, monkeypatch):
    # trends -> draft -> critique -> queue -> finish
    script = [
        agent_msg([_tool_use("get_trends",{})], "tool_use"),
        agent_msg([_tool_use("draft_lyrics",{"concept":"c","style":"s","dialect":"d","language":"ar"})],"tool_use"),
        agent_msg([_tool_use("critique_draft",{"lyrics":"L"})],"tool_use"),
        agent_msg([_tool_use("queue_proposal",{...})],"tool_use"),
        agent_msg([_tool_use("finish",{"summary":"ok"})],"tool_use"),
    ]
    r = agent.AgentRunner().run_cycle(tmp_path, _artist(), anthropic_client=ScriptedAnthropic(script), config=_cfg())
    assert r["stopped"] == "finished"
    assert len(r["queued"]) == 1

def test_loop_respects_max_iterations(tmp_path):
    # a client that NEVER calls finish — loop must stop at max_iterations, fail safe
    always_trends = [agent_msg([_tool_use("get_trends",{})],"tool_use")] * 50
    r = agent.AgentRunner().run_cycle(tmp_path, _artist(),
        anthropic_client=ScriptedAnthropic(always_trends), config=_cfg(max_iterations=5))
    assert r["stopped"] == "max_iterations"
    assert r["iterations"] <= 5

def test_gate_integrity_no_credit_moves_and_no_spend_call(tmp_path, monkeypatch):
    """THE critical test: a full cycle queues awaiting_approval runs and NEVER calls a spend path."""
    import pipeline.credits as credits
    monkeypatch.setattr(credits, "check_or_deduct",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("agent must not deduct")))
    # also assert no paid spawn:
    import pipeline.api as api
    monkeypatch.setattr(api, "_spawn",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("agent must not spawn a render")))
    script = [... a normal trends->draft->critique->queue->finish ...]
    r = agent.AgentRunner().run_cycle(tmp_path, _artist(), anthropic_client=ScriptedAnthropic(script), config=_cfg())
    # queued proposals are awaiting_approval only; no exception raised = no spend path touched
    for run_id in r["queued"]:
        assert _read_run_state(tmp_path, run_id)["status"] == "awaiting_approval"
```
(Add `agent_msg`/`_artist`/`_cfg`/`_read_run_state` helpers; align the block/stop-reason shape to whatever the loop actually reads from the Anthropic response — keep the stub minimal and matched.)

- [ ] **Step 2: Run — expect FAIL.**
- [ ] **Step 3: Implement `AgentRunner.run_cycle`:** a manual loop — build the system prompt (A&R role + artist identity + originality/tashkeel rules + approve-before-spend framing), then repeatedly `messages.create(model=config["model"], tools=agent.TOOLS, messages=..., thinking={"type":"adaptive"}, output_config={"effort":"high"})`; while `stop_reason=="tool_use"`, execute each `tool_use` block via `dispatch_tool`, append the `tool_result`, loop. Terminate on `finish`, `max_iterations`, token budget exceed, or a caught error (fail safe — keep valid queued proposals, log the rest, spend nothing). Persist the trace (thinking summaries + tool-call log) to each proposal's `agent_trace_path`. Parse tool inputs with `json.loads` (never string-match).
- [ ] **Step 4: Run — expect PASS**; `uv run pytest tests/test_agent_loop.py -q`. The gate-integrity test is the acceptance gate.
- [ ] **Step 5: Commit** `feat(agent): bounded tool-use loop (AgentRunner) + gate-integrity tests`

---

### Task 5: `run.py --agent` worker mode

**Files:** Modify `run.py` (arg parsing + an `_run_agent_cycle` branch). Test: `tests/test_agent_worker.py`.

**Interfaces — Produces:** `run.py --agent --user <id> --artist <id>` loads the artist, builds the Anthropic client + config, checks the three gates (`FACELESS_AGENT_ENABLED`, `config.agent.enabled`, artist `agent_enabled`) + Anthropic-key presence, and calls `AgentRunner().run_cycle(...)`. No-ops (logged) if any gate is off or the key is missing.

- [ ] **Step 1: Write the failing test**
```python
# tests/test_agent_worker.py — call the worker entry with a stubbed AgentRunner
def test_agent_worker_noops_when_flag_off(tmp_path, monkeypatch):
    monkeypatch.delenv("FACELESS_AGENT_ENABLED", raising=False)
    called = {"ran": False}
    monkeypatch.setattr("pipeline.agent.AgentRunner.run_cycle", lambda *a, **k: called.__setitem__("ran", True))
    import run
    run.main_with_args(["--agent","--user","u1","--artist","art_x"])
    assert called["ran"] is False  # gated off → never ran the loop

def test_agent_worker_runs_when_all_gates_on(tmp_path, monkeypatch):
    monkeypatch.setenv("FACELESS_AGENT_ENABLED","1")
    monkeypatch.setenv("ANTHROPIC_API_KEY","sk-test")
    # config.agent.enabled true + artist agent_enabled true via fixtures/monkeypatch
    called = {"ran": False}
    monkeypatch.setattr("pipeline.agent.AgentRunner.run_cycle", lambda *a, **k: (called.__setitem__("ran", True) or {"queued":[],"stopped":"finished","iterations":1}))
    import run
    run.main_with_args(["--agent","--user","u1","--artist","art_x"])
    assert called["ran"] is True
```
- [ ] **Step 2: Run — expect FAIL.**
- [ ] **Step 3: Implement** the `--agent` branch in `run.py` (mirror how `--mode song --resume` is parsed at `run.py:627+`). Resolve user_root + artist, evaluate the three gates + key, construct `anthropic.Anthropic()` and config, call `run_cycle`, log the result. Any exception is caught + logged (fail safe).
- [ ] **Step 4: Run — expect PASS**; full suite still green.
- [ ] **Step 5: Commit** `feat(agent): run.py --agent worker mode (gated, fail-safe)`

---

### Task 6: `POST /songs/{id}/reject` + approve-hook memory recording

**Files:** Modify `pipeline/api.py` (`approve_song` hook + new `reject_song`). Test: `tests/test_agent_decisions.py`.

**Interfaces — Produces:** `POST /songs/{id}/reject` (owner auth) → sets the run `status="rejected"` (new terminal state) and calls `agent_memory.record_decision(..., decision="rejected", reason=...)` when `source=="agent"`. `approve_song` gains: if `source=="agent"`, `record_decision(..., decision="approved", self_score=...)` (before/after the existing deduct — must NOT change the spend behavior).

- [ ] **Step 1: Write the failing test**
```python
# tests/test_agent_decisions.py (use the existing client_factory fixture)
def test_reject_marks_rejected_and_records_decision(client_factory, tmp_path, monkeypatch):
    c = client_factory(user_id="u1", role="user")
    run_id = _make_agent_awaiting_approval_run(...)   # source="agent", awaiting_approval
    r = c.post(f"/songs/{run_id}/reject", json={"reason":"too sad"})
    assert r.status_code == 200
    assert _read_state(run_id)["status"] == "rejected"
    mem = agent_memory.load_memory(user_root, artist_id)
    assert mem["decisions"][-1]["decision"] == "rejected"
    assert mem["decisions"][-1]["reason"] == "too sad"

def test_approve_records_approved_without_changing_spend(client_factory, monkeypatch):
    # monkeypatch credits.check_or_deduct to a spy; assert it's still called exactly as before
    ...
```
- [ ] **Step 2: Run — expect FAIL.**
- [ ] **Step 3: Implement** `reject_song` (guard: owner + run exists + `awaiting_approval` → `rejected`; idempotent otherwise) and the `approve_song` hook (record `approved` only for `source=="agent"`; leave the deduct/spawn path byte-for-byte). Add `"rejected"` to any status enums/localized status maps as needed (backend only; Flutter status handled in T10).
- [ ] **Step 4: Run — expect PASS**; `uv run pytest tests/test_agent_decisions.py tests/test_api.py -q` green (approve flow unchanged).
- [ ] **Step 5: Commit** `feat(agent): reject endpoint + approve/reject/edit memory recording`

---

### Task 7: `POST /admin/run-agent` sweep + dispatch

**Files:** Modify `pipeline/api.py` (new `run_agent` endpoint + `_has_agent_run_today`). Test: `tests/test_agent_sweep.py`.

**Interfaces — Produces:** `POST /admin/run-agent` (service auth via `_require_admin`) → sweeps user dirs, keeps `agent_enabled` artists, skips those already run today or over the `daily_global_run_cap`, and dispatches an agent worker per artist via `_spawn` (args `["--agent","--user",uid,"--artist",aid]`). Returns `{dispatched, skipped, capped, details}`. Per-artist errors isolated.

- [ ] **Step 1: Write the failing test**
```python
# tests/test_agent_sweep.py
def test_sweep_dispatches_only_opted_in_artists(client_factory, monkeypatch):
    spawns = []
    monkeypatch.setattr("pipeline.api._spawn", lambda args, **k: spawns.append(args))
    # user with 2 artists: one agent_enabled=True, one False
    c = client_factory(role="service")
    r = c.post("/admin/run-agent"); assert r.status_code == 200
    assert len(spawns) == 1 and "--agent" in spawns[0]

def test_sweep_respects_daily_global_cap_and_idempotency(client_factory, monkeypatch):
    ... assert capped/skipped behavior, and that a second call same-day skips ...

def test_sweep_requires_service_auth(client_factory):
    assert client_factory(role="user").post("/admin/run-agent").status_code == 403
```
- [ ] **Step 2: Run — expect FAIL.**
- [ ] **Step 3: Implement** `run_agent` mirroring `run_morning_drafts` (`api.py:1220`): iterate `_out_root()` user dirs, load artists, filter `agent_enabled`, guard `_has_agent_run_today`, enforce `daily_global_run_cap`, dispatch via `_spawn`, catch per-artist errors. `_has_agent_run_today` mirrors `_has_morning_draft_today` (a non-failed `source="agent"` run today).
- [ ] **Step 4: Run — expect PASS**; full suite green.
- [ ] **Step 5: Commit** `feat(agent): /admin/run-agent scheduler sweep + dispatch (gated, capped, idempotent)`

---

### Task 8: `GET /agent/proposals` + `GET /songs/{id}/agent-trace`

**Files:** Modify `pipeline/api.py` (two read endpoints + response models). Test: `tests/test_agent_feed.py`.

**Interfaces — Produces:** `GET /agent/proposals` (owner) → list of the user's `source="agent"` runs still `awaiting_approval`, each `{run_id, artist_id, title, rationale, self_score, created_at, cost_credits, cost_usd}` (cost via the existing `_song_credit_amount` so the feed shows the same figure the approve gate will). `GET /songs/{id}/agent-trace` (owner) → the stored reasoning trace.

- [ ] **Step 1: Write the failing test** (list returns only agent awaiting_approval runs with rationale+score+cost; trace returns the stored trace; both owner-scoped).
- [ ] **Step 2: Run — expect FAIL.**
- [ ] **Step 3: Implement** the two endpoints (reuse the run-listing helpers + `_song_credit_amount` for cost; read `agent_trace_path`).
- [ ] **Step 4: Run — expect PASS**; full suite green.
- [ ] **Step 5: Commit** `feat(agent): A&R feed + reasoning-trace read endpoints`

---

### Task 9: Flutter — API client + models + artist toggle

**Files:** Modify `lib/api/client.dart` (new methods), `lib/api/models.dart` (`AgentProposal` model + `Artist.agentEnabled`), `lib/screens/artist_edit_screen.dart` (the toggle), l10n `.arb` files. Test: extend a Flutter test if one covers the client/models.

**Interfaces — Produces:** `client.listAgentProposals()`, `client.rejectSong(id, reason)`, `client.agentTrace(id)`; `AgentProposal{runId,artistId,title,rationale,selfScore,costUsd,costCredits}`; `Artist.agentEnabled` (parse + in the patch); an "Autonomous A&R" toggle in artist edit.

- [ ] **Step 1:** Add the model + client methods (mirror existing `listSongs`/`approve` shapes). Add `agentEnabled` to `Artist` parse + the PATCH body. Add the toggle to `artist_edit_screen` (like `morningDrafts`/`autoPublishYoutube`). Add l10n keys (both `.arb`).
- [ ] **Step 2 (verify):** `flutter test` green; `/Users/gileshannah/Documents/flutter/bin/dart analyze lib/api/ lib/screens/artist_edit_screen.dart` clean.
- [ ] **Step 3: Commit** `feat(agent): Flutter API client + models + artist A&R toggle`

---

### Task 10: Flutter — the A&R feed screen

**Files:** Create `lib/screens/agent_feed_screen.dart`, `lib/widgets/agent/proposal_card.dart`, `lib/widgets/agent/reasoning_trace_sheet.dart`; wire an entry point (home tab/section). l10n `.arb`.

**Interfaces — Consumes:** Task 9 client/models; the Obsidian & Champagne primitives (`EditorialHeading`, `Eyebrow`, `GlassCard`, `GradientButton`, `StatusPill`, `Hairline`).

- [ ] **Step 1:** Build the feed: a list of `ProposalCard`s each showing artist, the agent's **rationale** (`Eyebrow` "Why now" + text), the **self-score** (a small champagne meter/pill), the concept title (`EditorialHeading`), a lyrics preview, and **Approve** (→ existing cost/approve flow) / **Reject** (+ optional reason sheet → `rejectSong`) / **Edit** (→ existing edit screen). Tap → `reasoning_trace_sheet` (the agent's full trace). Empty state ("Your A&R is composing…"). Obsidian+champagne; bilingual AR/EN + RTL; new l10n keys both `.arb`. Animated widgets use `pump()` not `pumpAndSettle()`.
- [ ] **Step 2 (verify):** `flutter test` green; `dart analyze` (Flutter dart) clean on the new files.
- [ ] **Step 3:** Visual check via `./scripts/run-app.sh` (AR + EN) — feed renders, approve/reject/edit wired, trace opens.
- [ ] **Step 4: Commit** `feat(agent): A&R feed screen (proposal cards + reasoning trace)`

---

### Task 11: End-to-end verification + scheduler doc + branch finish

- [ ] **Step 1:** `uv run pytest -q` → all green (1127 existing + the new agent tests). Re-run the **gate-integrity** test explicitly and confirm zero-credit-movement.
- [ ] **Step 2:** `flutter test` green; `dart analyze lib/ test/` (Flutter dart) clean.
- [ ] **Step 3:** Add operator doc `docs/AGENT-SETUP.md`: the Cloud Scheduler job (`gcloud scheduler jobs create http faceless-agent --schedule="0 2 * * *" --uri=<API>/admin/run-agent --http-method=POST --headers="Authorization=Bearer $FACELESS_API_TOKEN"`), the env gate (`FACELESS_AGENT_ENABLED=1` on the service), and the three-gate + kill-switch model.
- [ ] **Step 4:** `./scripts/run-app.sh` walkthrough AR + EN of the A&R feed.
- [ ] **Step 5:** Invoke **superpowers:finishing-a-development-branch**.

---

## Self-Review

**Spec coverage:** §2 invariants → global constraints + T4 gate-integrity + T7 gating; §3 run-location → T5 (`--agent`) + T7 (sweep); §4 brain/loop → T3 (tools) + T4 (loop); §4.1 tools → T3; §5 memory/learning → T2 + T6; §6 proposal=run → T3 (`queue_proposal`); §7 API → T6 (reject) + T7 (run-agent) + T8 (feed/trace) + T1 (patch field); §8 config/flags → T1 + T5; §9 Flutter → T9 + T10; §10 safety → T4/T5/T7 + gate test; §11 phasing (v2) → out of scope, noted; §12 testing → every task's tests + T11; §13 files → all covered. No gaps.
**Placeholder scan:** the load-bearing tests (tool boundary, loop control, gate-integrity, sweep auth) have concrete code; mechanical CRUD/Flutter tasks give exact signatures + endpoints + the reused real interfaces. The `...` inside a few test bodies marks fixture/data the implementer fills from the real state shape — acceptable, as the assertion under test is concrete. No "add error handling" hand-waving.
**Type consistency:** `ToolContext`, `dispatch_tool`, `AgentRunner.run_cycle`, `agent_memory.record_decision/load_memory/distill_preferences`, `source="agent"`, `agent_rationale`/`agent_self_score`/`agent_trace_path`, `agent_enabled`, `status="rejected"` — consistent across producer/consumer tasks.
