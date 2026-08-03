# Song A&R Quality Pipeline — best-of-N + AI listen + master

**Date:** 2026-08-03
**Status:** Design approved; ready for implementation plan
**Axis:** Sonic quality ("least AI"). Premium tier.
**Builds on:** the producer pass (`pipeline/song_style.py`, spec 2026-07-27) which fixed the *steer into* Suno. This spec fixes *selection + polish on the way out*.

## Problem

Songs still sound "AI, not a real release." The producer pass improved the Suno
style prompt, but the pipeline still rolls the dice **once**: `run.py` takes a
single Suno job (2 takes) and keeps the *longer* one — it never judges which take
sounds better, never generates more, and never polishes the result. Suno's own
per-take quality varies a lot (especially Arabic vocals), so the single biggest
remaining quality lever is: **generate several takes, have something actually
listen and keep the most human-sounding one, regenerate if they're all weak, then
master it.**

### Honest leverage ordering (drives the design)

1. **Best-of-N + the listening judge** — most of the "not-AI" win.
2. **Regenerate-if-weak** — catches unlucky batches.
3. **Mastering** — smallest lever (Suno already outputs ~-14 LUFS); adds polish,
   not a new vocal engine.

### Hard ceiling (stated honestly)

The audio engine is still Suno. This system maximizes *which* Suno output ships
and *how polished* it is; it does not replace Suno's vocal synthesis.

## Goals

1. Generate **best-of-N** Suno takes per premium song and auto-keep the best.
2. A **hybrid A&R judge** — free signal-based defect pruning, then a Gemini
   **audio** judge that scores human-ness / AI-artifacts / Arabic diction /
   production / style-fit and picks the winner.
3. **Regenerate** when the best take is below a quality bar, within hard cost caps.
4. A **mastering** pass on the winner (Matchering, ffmpeg fallback).
5. A **`quality_tier` pricing axis** (standard | premium) with upfront cost
   disclosure at the approve gate.
6. Ship the judge **shadow-mode behind a flag** until validated on labeled takes.

## Non-goals

- Replacing Suno / multi-engine generation (Udio, ElevenLabs Music) — future.
- Letting the user hear + manually pick the ranked finalists — optional phase 2.
- A paid mastering API — evaluated and declined (marginal gain over Matchering
  for a Suno track; adds cost + external failure surface).

## Architecture

The pipeline slots into the **post-approval worker** (`run.py` song stage),
between Suno generation and final assembly. The user still approves **once**
(lyrics + style, pre-spend); everything below runs after approval with no extra
UX steps.

### New module `pipeline/song_ar.py` — "given takes, return the best + why"

Three units, independently testable (audio LLM mocked):

- `screen_takes(take_paths) -> list[ScreenedTake]` — signal-based defect prune.
- `judge_takes(audio_llm, takes, *, style_prompt, language, dialect) -> list[JudgedTake]`
  — Gemini audio judge scores survivors.
- `pick_best(judged) -> Verdict` — winner + composite + `clears_bar`.

### New module `pipeline/mastering.py`

- `master_track(in_path, out_path, *, genre_key, cfg) -> bool` — fills the
  `maybe_master` seam reserved in the producer-pass spec.

### New capability: Gemini audio input

- `judge_audio(audio_path, system, user) -> str` — google-genai `generate_content`
  with an audio Part, `GEMINI_AUDIO_MODEL` (default `gemini-2.5-flash`). Separate
  from the text `_build_song_llm` (which is text-only). Robust JSON reader reused
  (fence-strip → brace-extract → `strict=False` → `isinstance dict` guard).

### Data flow (post-approval worker)

```
approve → worker
  takes = []
  for round in 1..(1 + regen_max_rounds):
      submit K Suno jobs IN PARALLEL → collect task_ids → wait each → download
      takes += new
      screened = screen_takes(takes)                     # prune junk (free)
      judged   = judge_takes(gemini_audio, screened, …)  # AI A&R listens
      best     = pick_best(judged)
      if best.clears_bar or max_takes reached or round == last: break
  best.take → song.mp3
  maybe_master(song.mp3, cfg) → mastering.master_track    # premium only
  write_state(chosen_take, take_scores, ar_reason, takes_generated,
              quality_bar_cleared, judge_source, mastered)
```

### Invariants

- **Never blocks a render.** Every stage degrades: Gemini judge fails → signal
  composite; mastering fails → ship unmastered winner; all takes junk → ship
  least-bad. A quality pipeline must never turn a payable render into a hard fail.
- Replaces the single `run.py:1118` "pick the longer take" with `screen → judge
  → pick`; upgrades `maybe_master` from no-op to real.
- `song_ar.py` / `mastering.py` are pure units; external services mocked in tests.

## The judge

### Stage 1 — `screen_takes` (free defect prune, no LLM)

Cheap no-reference metrics via the existing audio stack (ffprobe + librosa or
ffmpeg `astats`/`silencedetect`), per take:

- **Truncation** — duration < ~60% of the batch median.
- **Clipping** — share of full-scale samples > ~1%.
- **Silence/dropout** — mostly-silent or long internal gaps.
- **Peak/DC sanity.**

`ScreenedTake(path, duration_s, clip_ratio, silence_ratio, passed, reject_reason)`.
Failed takes skip the judge (saves cost). **If every take fails, keep them all**
and fall through on a composite signal score — never drop the whole batch.

### Stage 2 — `judge_takes` (Gemini audio A&R)

Each surviving MP3 → Gemini audio with a rubric. **We compute the composite from
the sub-scores** (control over "what quality means"), not the model's holistic
number.

Sub-scores 0–100 (for `artifacts`/`pronunciation`, higher = better):

| Criterion | Weight | Catches |
|---|---|---|
| `vocal_realism` | 35% | robotic/synthetic vs real human voice, breath, emotion |
| `artifacts` | 25% | autotune-warble, metallic/underwater tone, smearing, glitches |
| `pronunciation` | 20% | slurred/garbled words; **Arabic diction** (Suno's weak spot) |
| `production` | 10% | mix clarity, arrangement coherence, not muddy/thin |
| `style_fit` | 10% | matches the intended `style_prompt` genre/mood/tempo |

`composite = Σ weight × subscore`. **Deal-breakers** (model returns a
`deal_breakers` list — garbled words, wrong language, dead silence) **hard-cap the
composite at 40**, so a pretty-but-gibberish take can't win.

JSON contract:
```json
{"vocal_realism":0-100,"artifacts":0-100,"pronunciation":0-100,
 "production":0-100,"style_fit":0-100,"reason":"one line","deal_breakers":[]}
```

### Fallback (never blocks)

Gemini call/parse fails → each take gets a **signal-only composite** from
`screen_takes` and `source="signal-fallback"`. `pick_best` returns the top
composite either way; `clears_bar = composite >= quality_bar` drives regenerate.

### Validation gate (required before trusting auto-pick)

An LLM judging *music* — especially Arabic vocals — is unproven. Before the judge
drives real renders, run it on a small **labeled set** (known-good vs known-bad
takes) and confirm it separates them. Until then it ships **shadow-mode behind a
flag**: judge + log the scores, but selection stays signal-based. Flip the flag
after validation.

## Best-of-N, regenerate & pricing

### Best-of-N (round 1)

- **6 takes = 3 Suno jobs** (N maps to ⌈N/2⌉ jobs).
- **Parallel submit:** fire all `submit_song_job` calls up front, collect task
  IDs, then wait on each. Suno runs them concurrently → wall-clock ≈ one job
  (~2–3 min), not 3×.

### Regenerate loop

- If `best.composite < quality_bar` (default **70**): another round, **+4 takes
  (2 jobs)**, re-judge the whole pool, keep the best.
- **Hard caps:** `regen_max_rounds: 1` and `max_takes: 10` — whichever hits first
  stops the loop. With `best_of: 6` + `regen_extra_takes: 4`, `max_takes` is the
  binding cap: worst case = 5 jobs / 10 takes (one regen round). `regen_max_rounds`
  exists so raising `max_takes` later can allow more rounds without a code change.
- Regen re-submits the same params (Suno randomizes takes). Optional prompt nudge
  ("cleaner vocal, no artifacts") is a later refinement, not MVP.
- **No silent caps:** stopping below-bar logs it explicitly — e.g.
  `shipped best of 10 @ 63 < bar 70 (max_takes reached)`.

### Cost & latency envelope (disclosed)

| | Typical (bar cleared R1) | Worst case (caps hit) |
|---|---|---|
| Suno | 3 jobs ≈ $0.15 | 5 jobs ≈ $0.25 |
| Gemini audio judge | ~$0.02 | ~$0.05 |
| Mastering | free (Matchering) | free |
| Latency | ~3–4 min | ~7 min |

### Pricing

- New **`quality_tier`** axis (`standard` | `premium`), orthogonal to
  `video_mode`: `credits = base(video_mode) + premium_surcharge`.
- `premium_credit_surcharge: 4` → static+premium = **5 credits**,
  cinematic+premium = **7**. Covers worst-case raw (~$0.30) with margin at
  1 credit ≈ $0.10.
- **Approve gate shows max spend** before greenlight (extends existing dollar
  disclosure): "Premium: best-of-N + AI A&R + master — up to 10 takes, ~$0.30,
  5 credits." Charged flat on approval; early clear is margin (no partial refund).

### Shadow-mode interaction

While the judge is behind its validation flag: selection = signal-based
(screen → least-defective), Gemini scores logged only, regenerate bar uses the
signal composite. Flip the flag after validation → Gemini drives selection *and*
the regenerate bar. Best-of-N + regenerate ship value (more takes, defect-pruned
pick) even before the AI ear is trusted.

## Mastering engine

For a Suno track (already ~-14 LUFS) mastering is the smallest lever; optimize
quality-per-effort.

- **Matchering (chosen)** — free, open-source, reference-based: match the take's
  spectral balance + loudness to a professionally-mastered **reference track**
  per genre (`assets/reference_masters/<genre_key>.wav`). Deterministic, offline.
- **ffmpeg chain (fallback)** — HPF rumble cut, de-ess, gentle comp, −1 dBTP
  limiter, **no loudnorm**. Used when Matchering errors or no reference exists for
  the genre.
- **Paid API — declined** (marginal gain over Matchering for Suno tracks; cost +
  external failure surface).

`master_track(in, out, *, genre_key, cfg)` dispatches on `master_engine:
matchering | ffmpeg`; returns `False` on any failure (ship unmastered winner);
**never raises**. Gated on premium tier via `maybe_master`. (`api` is a reserved
value — not implemented in MVP; selecting it falls back to `ffmpeg` with a logged
warning.)

**Required asset (licensing):** Matchering needs owned or royalty-free reference
masters — one pro-mastered track per genre family. Ship a small CC0 set,
swappable by the user. Missing reference → ffmpeg fallback.

## State surfacing & UX

- Per-run state (`song.json`/`api_state.json`): `takes_generated`, `take_scores`
  (each take's composite + sub-scores + source), `chosen_take`, `ar_reason`,
  `quality_bar_cleared`, `judge_source` (`gemini`|`signal-fallback`), `mastered`.
- Approve gate: max-spend + "Premium: best-of-N + AI A&R + master".
- Run detail surfaces winner score + reason + take count (premium value made
  visible: "listened to 8 takes, kept the best at 82/100 — natural vocal, clean
  diction").
- **Optional phase 2:** let the user hear the ranked finalists and override. MVP
  auto-picks.

## Config (song section)

```yaml
quality_tier_default: standard      # premium enables the pipeline
best_of: 6                          # round-1 takes (→ 3 jobs)
quality_bar: 70                     # composite to accept
regen_max_rounds: 1                 # max_takes is the binding cap at these values
regen_extra_takes: 4
max_takes: 10                       # hard budget backstop
premium_credit_surcharge: 4
ar_judge_enabled: false             # shadow-mode flag; flip after validation
master_engine: matchering           # matchering | ffmpeg (api reserved, not built)
```

Env: `GEMINI_AUDIO_MODEL` (default `gemini-2.5-flash`).

## Files touched

- **new** `pipeline/song_ar.py` — `ScreenedTake`, `JudgedTake`, `Verdict`,
  `screen_takes`, `judge_takes`, `pick_best`, composite/deal-breaker logic.
- **new** `pipeline/mastering.py` — `master_track` (matchering/ffmpeg dispatch).
- **new** audio-judge client (`judge_audio`) — in `pipeline/llm.py` or a small
  `pipeline/llm_gemini_audio.py`.
- `run.py` — song stage becomes the best-of-N + regenerate loop; parallel submit;
  calls `screen/judge/pick` and `maybe_master`; writes the new state.
- `pipeline/song_assemble.py` — `maybe_master` delegates to `mastering.master_track`
  (premium-gated) instead of no-op.
- `pipeline/config.py` + `config.yaml` — the config block above.
- `pipeline/api.py` — `quality_tier` on the request + credit calc + approve-gate
  max-spend string + persist tier.
- **new assets** `assets/reference_masters/*.wav` — CC0 per-genre references.
- **new tests** `tests/test_song_ar.py`, `tests/test_mastering.py`; extend
  `tests/test_run_song_mode.py`, `tests/test_song_api.py`.

## Testing

External services mocked (Suno, Gemini audio, ffmpeg/Matchering).

- `song_ar.py`: `screen_takes` rejects truncated/clipped/silent, keeps valid,
  all-fail→keep-all; `judge_takes` computes the weighted composite, deal-breaker
  caps at 40, bad-JSON→signal-fallback; `pick_best` picks top composite +
  `clears_bar`.
- Regenerate loop (run.py stage): mocked submit/wait/judge → stops when bar
  cleared, respects `regen_max_rounds`/`max_takes`, logs when capped, shadow-mode
  uses signal selection while logging Gemini scores.
- `mastering.py`: mocked Matchering/ffmpeg → `True` on success, `False`/fallback
  on failure, missing reference → ffmpeg path, never raises.
- Pricing: `standard`/`premium` × `static`/`cinematic` → correct credit totals;
  approve-gate max-spend string.
- Validation gate: a manual/offline step in the plan (labeled-take separation),
  NOT a unit test; the shadow-mode flag default (`ar_judge_enabled: false`) is
  asserted so prod can't auto-pick before the flag is deliberately flipped.

## Follow-ups (out of scope)

- Let the user hear + override the ranked finalists (phase 2).
- Optional prompt nudges on regenerate rounds.
- Multi-engine generation (Suno + Udio/ElevenLabs) and cross-engine judging.
- Paid mastering API if Matchering proves insufficient in practice.
