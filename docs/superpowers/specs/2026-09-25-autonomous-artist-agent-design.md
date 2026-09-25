# Autonomous Artist Agent — Design Spec

**Date:** 2026-09-25
**Status:** Draft for review
**Approach:** A real Claude tool-calling agent (bounded loop), approve-before-spend, brain-first v1.

## 1. Purpose

Turn Faceless Lab from a tool you *operate* into a **Virtual Artist Label that runs itself**. A per-artist autonomous **A&R agent** works on a schedule: it reasons about what the artist should release next (trends + the artist's identity + what it has learned about your taste), drafts a concept and full Arabic lyrics, critiques its own work, and **queues reasoned proposals that stop at your existing approval gate**. You wake to a feed of "here's what I'd release next, and why" — one tap turns a proposal into a real song.

**The unit is the artist** (consistent with the Virtual Artist Label direction). The agent is the artist's A&R manager + creative partner.

## 2. Non-negotiable invariants

- **Approve-before-spend is absolute.** The agent's entire toolbox is **read-and-queue only**. It has *no tool* that can deduct a credit, start a paid render, or publish anything. The only money path — `approve_song` → `credits.check_or_deduct` → paid worker — fires solely when a human taps **Approve**. There is no code path from the agent to a charge or a public post.
- **Behavior-preserving.** The existing song/run flow (`create_song` → `approve_song` → worker render → YouTube publish), the spend/credit ledger, the two-phase gate, and all i18n keys are untouched. The agent produces the same `awaiting_approval` runs the morning-drafts feature already produces (`source="agent"` instead of `"morning_draft"`).
- **Bounded & fail-safe.** Every agent cycle is capped (iterations + token budget + wall-clock). A per-artist failure is isolated and never spends, never crashes the sweep. A global kill switch and per-artist opt-in gate the whole feature off by default.
- **Only existing infra in v1.** No new paid integrations (no higgsfield/TikTok/avatar). The agent orchestrates what production already does. The new media capabilities are a designed **v2** (§11).
- **Design-system consistent.** The Flutter surface uses the shipped Obsidian & Champagne system; bilingual AR/EN + RTL.

## 3. Where it runs (rides the morning-drafts pattern)

- **Trigger:** a Cloud Scheduler job (provisioned by gcloud CLI, like `morning-drafts`) → **`POST /admin/run-agent`** (service-token auth via `_require_admin`), on a cadence (default daily; configurable).
- **Sweep:** `/admin/run-agent` iterates every user dir under `_out_root()` (mirrors `run_morning_drafts` at `pipeline/api.py:1236`), loads each user's artists, and keeps those with the new **`agent_enabled`** toggle truthy. For each opted-in artist it **dispatches a background agent worker** (does NOT run the loop inline — an agent loop is minutes of LLM turns and must not block the HTTP request or share failure across artists).
- **Dispatch mechanism:** reuse the existing spawn backend (`_spawn` / `select_backend`, `pipeline/api.py:722`, `pipeline/spawn_backends.py`). The worker is `run.py` with a new **`--agent`** mode (`run.py --agent --user <id> --artist <id>`), analogous to `--mode song --resume <dir>`. On Cloud Run it uses `CloudRunJobsBackend` (already the path for paid renders); locally `LocalSubprocessBackend`.
- **Idempotency & quota:** one agent cycle per artist per period (a `_has_agent_run_today(artist)` guard mirroring `_has_morning_draft_today`, `api.py:1202`). Each cycle may queue up to `proposals_per_cycle` proposals (config, default 2). A **global daily cap** on total agent worker runs bounds cost.

## 4. The agent brain (bounded Claude tool-use loop)

New module **`pipeline/agent.py`** — the `AgentRunner`. A **bounded manual tool-use loop** on the Anthropic SDK (`client.messages.create` with `tools=`), chosen over the beta Tool Runner for determinism, testability, and no beta dependency (fits the "external services mocked in tests" invariant).

- **Model:** `claude-opus-5` for the agent's reasoning (adaptive thinking, `output_config.effort="high"`). Cheaper sub-calls (lyric drafting, critique) run on `claude-sonnet-5`. Both configurable in `config.yaml > agent`.
- **Requires an Anthropic key.** The tool-use loop calls the Anthropic SDK directly (tool-use is not available on the existing Groq/Gemini fallback path). So the agent runs only when `ANTHROPIC_API_KEY` is set — if it's absent the agent no-ops for that cycle and logs it (never errors the sweep). The `draft_lyrics` tool still goes through the existing `FallbackLLM` router, so lyric drafting keeps its fallback behavior.
- **Loop control:** hard `max_iterations` (default 12) + a `task_budget` token ceiling (Anthropic `task_budget` beta, streamed) + the worker's wall-clock timeout. The loop MUST terminate by calling `finish()` or hitting a cap; on cap/error it fails safe (queues whatever valid proposals it produced, logs the rest, spends nothing further).
- **System prompt:** casts the model as the artist's A&R — the artist's identity/voice/dialect, the label's originality rules (reuse the trends originality guardrail: trends are mood-context only, never covers), full-tashkeel + singability requirements (reuse the Arabic Quality Pack contract), and the approve-before-spend framing ("you propose; a human approves the spend"). Cached prefix for cost.
- **Reasoning trace:** the agent's thinking summary + tool-call sequence is captured and stored on each queued proposal (observability + the "magic made legible" UX).

### 4.1 Tools (the complete toolbox — all $0, read-and-queue only)

| Tool | Input | Effect | Backed by |
|---|---|---|---|
| `get_trends` | `{}` | Returns current trend briefs for the artist's language | `trends.build_briefs` / cached `trend_briefs.json` |
| `get_artist_context` | `{}` | Returns the artist's identity (name, voice/persona, default style/dialect/language), a discography summary, and the **agent memory** (distilled taste + recent decisions) | `artists.py` + §5 memory store |
| `draft_lyrics` | `{concept, style, dialect, language}` | Runs the existing **$0 writer pass**, returns lyrics for the agent to inspect | `generate_song_script` (the same call `_write_song_draft` uses, `api.py:1137`) |
| `critique_draft` | `{lyrics}` | LLM-judge (sonnet) scores the draft: hook strength, singability, on-brand fit, originality, tashkeel completeness → `{scores, verdict, notes}` | new sub-call in `agent.py` |
| `queue_proposal` | `{title, concept, lyrics, style, dialect, language, rationale, self_score}` | Writes an `awaiting_approval` song run with `source="agent"` + the reasoning/score in state (the human-approvable proposal) | `_write_song_draft`-shaped writer, reused |
| `finish` | `{summary}` | Ends this artist's cycle | loop terminator |

There is deliberately **no** `approve`, `spend`, `render`, `publish`, `post`, or `delete` tool. The tool list is the security boundary.

## 5. Memory & learning

New per-artist **agent memory** file: `<user_root>/agent/<artist_id>.json`, written atomically (the `artists.py`/`trends.py` temp+rename pattern; no DB migration — the DB stays financial-only per `pipeline/db.py`).

```json
{
  "artist_id": "art_ab12cd34",
  "preferences_summary": "Approves upbeat khaleeji with concrete imagery; rejects abstract sad ballads; likes a strong repeated hook.",
  "decisions": [
    {"run_id": "2026-09-25T02-00-00Z", "decision": "approved|rejected|edited", "reason": "...", "self_score": 0.82, "at": "..."}
  ],
  "updated_at": "..."
}
```

- **`get_artist_context`** reads `preferences_summary` + recent `decisions` and past discography, so the agent's proposals evolve toward your taste.
- **Learning signal (v1) = your approve/reject/edit decisions** — immediate and strong. Recorded by hooks:
  - `approve_song` (`api.py:4571`): on approving an `source="agent"` run, append an `approved` decision.
  - **new `POST /songs/{id}/reject`**: marks the run `rejected` (a terminal state distinct from cancel/delete) and appends a `rejected` decision with the optional reason. (Today there is no reject endpoint — morning drafts just linger; the agent needs an explicit reject to learn.)
  - edit-then-approve records `edited`.
- **Preference distillation:** after each cycle (or every N decisions), a cheap sonnet call rewrites `preferences_summary` from the decision history. Bounded, cheap, cached.
- YouTube analytics fold into this signal in **v2** once the compliance audit clears (the analytics learning loop is currently gated).

## 6. Proposal = an `awaiting_approval` run (reuses everything)

A proposal is exactly the artifact morning-drafts already produces — a run dir with `api_state.json`, `song.json`, `lyrics.txt`, `status="awaiting_approval"` — with:
- `source="agent"` (new value alongside `"morning_draft"`),
- `agent_rationale` (why this, why now),
- `agent_self_score` (the critique score),
- `agent_trace_path` (the stored reasoning trace),
- inherited artist identity (`artist_id`, persona, dialect, style — same inheritance as `_write_song_draft`).

Because it's a normal `awaiting_approval` run, the **existing** `GET /songs/{id}/script` (cost disclosure), `approve_song` (spend), edit, render, and publish flow all work **unchanged**. The agent simply fills the queue the human already knows how to act on.

**The agent does not choose the spend level.** `queue_proposal` carries only creative fields (concept, lyrics, style, dialect); the render's `video_mode` / `quality_tier` (what actually sets the dollar cost) follow the artist's / config defaults exactly as a manual song does. Keeping cost-tier out of the agent's hands is deliberate — it proposes the art, never the price.

## 7. API surface (additions only)

| Method | Path | Purpose | Auth |
|---|---|---|---|
| POST | `/admin/run-agent` | Scheduler entry: sweep opted-in artists, dispatch an agent worker each | service (`_require_admin`) |
| POST | `/songs/{id}/reject` | Mark an agent proposal rejected + record the learning signal (optional `reason`) | user (owner) |
| GET | `/agent/proposals` | List the user's agent proposals (the A&R feed) with rationale + score | user |
| GET | `/songs/{id}/agent-trace` | The stored reasoning trace for a proposal (observability) | user (owner) |
| PATCH | `/artists/{id}` | (existing) gains `agent_enabled` in the patchable field list | user (owner) |

All existing endpoints unchanged.

## 8. Config & flags

`config.yaml > agent`:
```yaml
agent:
  enabled: false            # global default OFF (also gated by env)
  model: claude-opus-5      # the agent brain
  worker_model: claude-sonnet-5   # draft + critique sub-calls
  max_iterations: 12
  token_budget: 60000       # per-artist per-cycle task budget
  proposals_per_cycle: 2
  daily_global_run_cap: 50  # hard ceiling on agent worker runs/day
  critique_threshold: 0.6   # queue only proposals scoring >= this
```
- **`FACELESS_AGENT_ENABLED`** env = the hard kill switch (must be `1` AND `config.agent.enabled` true AND the artist's `agent_enabled` true for the agent to run). Any one false → the agent never runs. Mirrors the `FACELESS_PERFORM_ENABLED` dormant-feature pattern.
- Per-artist **`agent_enabled: bool = False`** on the Artist model (`artists.py`), patchable.

## 9. Flutter surface (Obsidian & Champagne)

- **New "A&R" tab / home section:** a feed of agent proposals. Each **proposal card** shows the artist, the agent's **rationale** (why this, why now), its **self-critique score**, the concept title, and the lyrics preview — with **Approve** (→ existing cost-disclosure + spend gate), **Reject** (+ optional reason → learning), **Edit** (→ existing edit screen).
- **Reasoning trace view:** tap to see the agent's full trace (what it considered) — the transparency that makes the autonomy trustworthy and sets up v2's looser autonomy.
- **Per-artist agent toggle** in the artist edit screen (like `morning_drafts`/`auto_publish_youtube`), plus the "proposals per cycle" quota.
- Bilingual AR/EN + RTL; new l10n keys in both `.arb` files.

## 10. Safety, cost & observability (load-bearing)

- **Tool boundary:** the 6 read/queue tools are the security perimeter — enumerated, tested, no spend/publish among them.
- **Bounded cost:** the agent's *only* spend is its own bounded LLM tokens (opus reasoning + sonnet sub-calls), capped by `max_iterations` + `token_budget` per artist and `daily_global_run_cap` globally. Zero Kie/render/credit spend without a human tap.
- **Kill switch & opt-in:** `FACELESS_AGENT_ENABLED` + `config.agent.enabled` + per-artist `agent_enabled`; pause the Cloud Scheduler job to stop everything.
- **Fail-safe isolation:** each artist's worker is independent; any error is caught, logged to the agent log, and never spends or aborts the sweep (mirrors `run_morning_drafts` per-artist try/except at `api.py:1297`).
- **Observability:** every cycle stores its reasoning trace + tool calls; the A&R feed + trace view expose them; the agent log is tailable like run logs.
- **Rate/idempotency:** reuse the existing caps + `_has_agent_run_today` guard.

## 11. Phasing

- **v1 (this build):** the brain-first free agent — the loop + 6 tools + memory/learning-from-decisions + the A&R feed + reject endpoint + safety/tests. Existing infra only; zero new paid integrations.
- **v2 (designed, not built):** graduate the agent to real **actions within a budget** — auto-approve tiny spends under a per-artist cap and auto-publish to YouTube (the "graduated trust" model); add **TikTok** publishing, **avatar performance videos** (higgsfield/similar), and an **ML virality predictor** as a `critique_draft` signal (the "ambitious" option). Same agent, new tools + budget guards. Honest constraint carried forward: TikTok/Meta don't monetize fully-AI vocals, so v2's value is reach/catalog growth; revenue still flows through the app's own subscriptions.

## 12. Testing

Following the **"external services mocked"** invariant:
- **Stub the Anthropic client** (`monkeypatch`) with canned tool-call scripts. Assert the loop: executes tools in order; respects `max_iterations` and the token budget (fails safe on exceed); `queue_proposal` writes an `awaiting_approval` run with `source="agent"` + rationale + score; **never** calls `approve_song`/`check_or_deduct`/a paid spawn/publish; catches a tool error and continues/fails safe.
- **Memory:** approve/reject/edit hooks append the right decision; `get_artist_context` returns the distilled preferences; the distillation call is bounded.
- **Sweep:** `/admin/run-agent` dispatches one worker per opted-in artist, skips opted-out and already-run-today, respects the global cap, isolates per-artist failure.
- **Gate integrity (the critical test):** an end-to-end assertion that a full agent cycle produces only `awaiting_approval` runs and moves **zero** credits until a simulated human `approve_song`.
- Keep the existing suites green (1127 backend + 55 Flutter).

## 13. Key files

- New: `pipeline/agent.py` (AgentRunner + tools + loop), `pipeline/agent_memory.py` (the per-artist store), Flutter `lib/screens/agent_feed_screen.dart` + `lib/widgets/agent/*`.
- Modified: `run.py` (`--agent` mode), `pipeline/api.py` (`/admin/run-agent`, `/songs/{id}/reject`, `/agent/proposals`, `/songs/{id}/agent-trace`, approve hook, `agent_enabled` patch), `pipeline/artists.py` (`agent_enabled` field), `config.yaml` (`agent` block), l10n `.arb` files, the artist edit screen.
- Scheduler: a new Cloud Scheduler job (provisioned via gcloud, documented like morning-drafts).
