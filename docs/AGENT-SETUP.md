# Autonomous Artist Agent — Operator Setup

The Autonomous Artist Agent is a per-artist AI A&R that, on a schedule, reasons
about what an artist should release next, drafts + self-critiques a song, and
**queues `awaiting_approval` proposals that stop at the human spend gate**. It
never spends a credit or publishes — a human taps **Approve** to trigger the
paid render, exactly as with a manually-created song.

Design: `docs/superpowers/specs/2026-09-25-autonomous-artist-agent-design.md`.

## The three gates (it is OFF by default)

The agent worker runs for an artist only when **all** of these are true. If any
is false the worker **no-ops and logs it** (never errors, never spends):

1. **`FACELESS_AGENT_ENABLED=1`** in the API/worker environment (hard kill switch).
2. **`config.yaml > agent.enabled: true`** (default `false`).
3. The artist's **`agent_enabled`** flag is on (per-artist opt-in, toggled in the
   app's artist-edit screen — "Autonomous A&R").

Plus a hard requirement: **`ANTHROPIC_API_KEY` must be set** in the worker
environment. The agent's reasoning loop uses the Anthropic SDK directly (tool
use is not available on the Groq/Gemini fallback), so **without the key every
dispatched worker silently no-ops.**

> ⚠️ Prod check before flipping it on: the deployed service has shown
> `writer_degraded=true` at times (Anthropic key possibly absent). **Confirm
> `ANTHROPIC_API_KEY` is wired into both the `faceless-api` service and the
> `faceless-pipeline` Cloud Run Job** before setting `agent.enabled: true`, or
> nothing will happen.

## config.yaml `agent` block

```yaml
agent:
  enabled: false            # global on/off (also gated by FACELESS_AGENT_ENABLED)
  model: claude-opus-5      # the agent's reasoning brain
  worker_model: claude-sonnet-5   # cheaper draft + critique sub-calls
  max_iterations: 12        # hard loop cap per artist per cycle
  token_budget: 60000       # per-cycle token ceiling (agent's own LLM cost)
  proposals_per_cycle: 2    # max proposals queued per artist per cycle
  daily_global_run_cap: 50  # hard ceiling on dispatches/day
  critique_threshold: 0.6   # queue only proposals scoring >= this
```

The only money the agent itself spends is its own **bounded LLM tokens**
(capped by `max_iterations` + `token_budget` per artist, and `daily_global_run_cap`
globally). Zero credits/renders move without a human Approve.

## Scheduler (Cloud Scheduler → the sweep)

The sweep endpoint is `POST /admin/run-agent` (service-token auth). It sweeps
opted-in artists and dispatches one background worker (`run.py --agent`) per
artist, skipping any that already ran today and stopping at the daily cap.
Provision it like the existing `morning-drafts` job (daily at 02:00 UTC shown):

```bash
gcloud scheduler jobs create http faceless-agent \
  --schedule="0 2 * * *" \
  --uri="https://<your-api-host>/admin/run-agent" \
  --http-method=POST \
  --headers="Authorization=Bearer $FACELESS_API_TOKEN" \
  --location=<region>
```

> Cadence note: the idempotency/daily-cap accounting keys on the proposal
> artifacts a cycle writes, not on the dispatch itself. At **daily** cadence
> this is fine. Before moving to a **sub-daily** schedule, revisit
> `_has_agent_run_today` / `_agent_runs_today_count` — a cycle that queues zero
> proposals leaves no marker and could be re-dispatched (re-billing bounded
> agent tokens).

## First-time smoke test (before enabling for real users)

External services are mocked in the test suite, so run one **real** cycle
manually once the key is wired:

```bash
# On the worker host, with FACELESS_AGENT_ENABLED=1, agent.enabled=true,
# ANTHROPIC_API_KEY set, and an artist with agent_enabled=true:
uv run python run.py --agent --user <user_id> --artist <artist_id>
```

Confirm it produced an `awaiting_approval` run with `source="agent"` (visible in
the app's A&R feed with the agent's rationale + self-critique score), and that
**no credits were deducted**. Then approve one from the app to verify the normal
render/publish flow still works end to end.

## Kill switch

To stop everything immediately: unset/`0` **`FACELESS_AGENT_ENABLED`** on the
service (fastest), or pause the Cloud Scheduler job, or set
`config.agent.enabled: false`. Per-artist: turn off that artist's
**Autonomous A&R** toggle.

## What the human still controls

- **Every spend.** The agent queues; you Approve (the existing cost-disclosure +
  spend gate is unchanged).
- **Every publish.** Nothing is published by the agent.
- **Learning.** Approve / Reject (from the A&R feed) teach the per-artist memory
  what to propose next. (Note: discarding from *inside* the approve screen uses
  the cancel path and does not record a reject signal — use the feed's **Reject**
  button to teach the agent.)
