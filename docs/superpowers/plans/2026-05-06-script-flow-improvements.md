# Script-Flow Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement four user-facing improvements: freeform AI script mode, hybrid paste-script parser (regex + LLM fallback), post-Flux pause + edit gate, and per-clip playback with single-clip reroll.

**Architecture:** Backend changes are filesystem-driven (new `awaiting_veo_approval` status derived from artifacts on disk; new pipeline pause point exits subprocess cleanly). Frontend gets a third tab on the new-run screen, a second approval bar, and tap-to-play wiring on each beat tile. The existing AI Write / Paste Script / approve flows keep working unchanged.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, pytest (backend); Flutter/Dart, `flutter_test`, `cached_network_image`, `video_player` (frontend); Anthropic + Groq LLMs via existing router.

**Spec:** `docs/superpowers/specs/2026-05-05-script-flow-improvements-design.md`

---

## File Map

**New files:**
- `pipeline/script_freeform.py` — freeform writer prompt + `generate_freeform_script()`
- `pipeline/script_splitter.py` — LLM-based prose-to-beats splitter w/ verbatim guard
- `tests/test_script_freeform.py`
- `tests/test_script_splitter.py`

**Modified files (Python):**
- `run.py` — add `--pause-after-character-sheet`, `--freeform`, freeform flag passthrough
- `pipeline/api.py` — new endpoints (`/runs/freeform`, `/runs/{id}/approve-veo`, `/runs/{id}/character-sheet/reroll`, `/runs/{id}/clips/{i}/video`); new `awaiting_veo_approval` status branch in `derive_status`; loosen `PUT /runs/{id}/script`; extend `/runs/parse-script` for hybrid path; update `/runs/{id}/approve` to add the new pause flag
- `tests/test_api.py` — coverage for all new endpoints / status branches
- `tests/test_run_shorts_smoke.py` — extend for new pause flag (optional, only if smoke pass already covers `--pause-after-script`)

**Modified files (Flutter):**
- `lib/api/models.dart` — `RunStatus.awaitingVeoApproval`, `parseMethod` field on parse response
- `lib/api/client.dart` — new methods (`createFreeformRun`, `approveVeoRun`, `rerollCharacterSheet`, `parseScript` with `targetBeats`, per-clip video URL helper)
- `lib/screens/new_run_screen.dart` — third tab "AI Freeform"; target_beats slider + parse_method badge in Paste Script tab
- `lib/screens/run_detail_screen.dart` — `awaitingVeoApproval` status banner, character-sheet preview panel, `_BeatTile` tap-to-play + per-clip reroll
- `lib/screens/video_player_screen.dart` — optional `clipIndex` param

---

## Phase 1 — Post-Flux pause gate (backend)

### Task 1: Add `--pause-after-character-sheet` flag to run.py

**Files:**
- Modify: `run.py` (argparse around line 547; main flow around line 605)
- Modify: `tests/test_run_shorts_smoke.py`

- [ ] **Step 1: Write the failing test**

In `tests/test_run_shorts_smoke.py`, add:

```python
def test_pause_after_character_sheet_exits_after_flux(tmp_path, monkeypatch):
    """When --pause-after-character-sheet is passed AND --resume points at a run
    with script.json already present, run.py runs the Flux stage exactly once
    and then exits 0 without entering the video stage."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    # Pre-populate script.json so resume skips the script stage
    (run_dir / "script.json").write_text(_MINIMAL_SCRIPT_JSON, encoding="utf-8")
    (run_dir / "seed.json").write_text(
        '{"theme":"folkloric","premise":"x"}', encoding="utf-8")

    video_calls: list = []
    sheet_calls: list = []
    def fake_sheet(client, cfg, paths, script):
        sheet_calls.append(paths.character_sheet_png)
        paths.character_sheet_png.write_bytes(b"fake-png")
    def fake_video(*a, **kw):
        video_calls.append(a)

    monkeypatch.setattr("run._stage_character_sheet", fake_sheet)
    monkeypatch.setattr("run._stage_video_chained", fake_video)

    rc = run.main([
        "--shorts", "--resume", str(run_dir),
        "--pause-after-character-sheet",
    ])
    assert rc == 0
    assert len(sheet_calls) == 1
    assert video_calls == []
```

`_MINIMAL_SCRIPT_JSON` already exists in the smoke test file; if not, define it as a one-beat valid script JSON string.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_run_shorts_smoke.py::test_pause_after_character_sheet_exits_after_flux -v`
Expected: FAIL — argparse rejects `--pause-after-character-sheet`.

- [ ] **Step 3: Implement the flag**

In `run.py`, after the existing `--pause-after-script` declaration (around line 547), add:

```python
p.add_argument("--pause-after-character-sheet", action="store_true",
               help="Exit cleanly after Flux character_sheet.png is written. "
                    "Used by the API server to gate Veo spend on a second "
                    "human approval. Resume with --resume <dir>.")
```

In the main shorts flow (around line 604, immediately after the `with log.stage("character_sheet"): _stage_character_sheet(...)` block), add:

```python
if args.pause_after_character_sheet:
    log.info("PAUSED: character_sheet generated, awaiting Veo approval. "
             f"Resume with: uv run python run.py --shorts --resume {run_dir}")
    return 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_run_shorts_smoke.py::test_pause_after_character_sheet_exits_after_flux -v`
Expected: PASS.

Run the broader test file too: `uv run pytest tests/test_run_shorts_smoke.py -v`
Expected: all pass — no regressions to `--pause-after-script` behaviour.

- [ ] **Step 5: Commit**

```bash
git add run.py tests/test_run_shorts_smoke.py
git commit -m "feat(run): add --pause-after-character-sheet flag for Veo approval gate"
```

---

### Task 2: Add `awaiting_veo_approval` to `derive_status`

**Files:**
- Modify: `pipeline/api.py:118-124` (RunStatus literal), `pipeline/api.py:306-338` (`derive_status`)
- Modify: `tests/test_api.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_api.py`:

```python
def test_derive_status_awaiting_veo_approval(tmp_path, monkeypatch):
    """script.json + character_sheet.png both present, no clips, process dead
    → awaiting_veo_approval."""
    from pipeline.api import derive_status
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path))
    run_dir = tmp_path / "test-run"
    run_dir.mkdir()
    (run_dir / "script.json").write_text('{"beats":[]}', encoding="utf-8")
    (run_dir / "character_sheet.png").write_bytes(b"fake-png")
    # no clips/, no final.mp4, no live PID
    (run_dir / "api_state.json").write_text(
        '{"pid": null}', encoding="utf-8")
    assert derive_status(run_dir) == "awaiting_veo_approval"


def test_derive_status_awaiting_approval_unchanged(tmp_path, monkeypatch):
    """Regression: script.json alone (no character_sheet.png) still returns
    awaiting_approval, not the new awaiting_veo_approval state."""
    from pipeline.api import derive_status
    run_dir = tmp_path / "test-run-2"
    run_dir.mkdir()
    (run_dir / "script.json").write_text('{"beats":[]}', encoding="utf-8")
    (run_dir / "api_state.json").write_text('{"pid": null}', encoding="utf-8")
    assert derive_status(run_dir) == "awaiting_approval"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_api.py::test_derive_status_awaiting_veo_approval tests/test_api.py::test_derive_status_awaiting_approval_unchanged -v`
Expected: first FAILS (`awaiting_veo_approval` not in literal), second passes.

- [ ] **Step 3: Add the status literal**

In `pipeline/api.py:118`, extend `RunStatus`:

```python
RunStatus = Literal[
    "creating",
    "awaiting_approval",
    "awaiting_veo_approval",   # NEW: Flux done, waiting for second approval
    "running_paid",
    "complete",
    "failed",
]
```

- [ ] **Step 4: Add the derive_status branch**

In `pipeline/api.py` `derive_status` (around line 322, immediately after the `script_exists` check passes and BEFORE the `not sheet_exists and not has_clips` branch), insert:

```python
# NEW: Flux finished, no clips yet, subprocess exited → second approval gate.
if sheet_exists and not has_clips and not process_running:
    if last_error and _last_error_from_log(run_dir):
        return "failed"
    return "awaiting_veo_approval"
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_api.py -v`
Expected: PASS for both new tests AND all existing api tests (the new branch is gated on `sheet_exists` so prior states are unaffected).

- [ ] **Step 6: Commit**

```bash
git add pipeline/api.py tests/test_api.py
git commit -m "feat(api): derive awaiting_veo_approval status after Flux"
```

---

### Task 3: Update `/runs/{id}/approve` to insert the new pause flag

**Files:**
- Modify: `pipeline/api.py:809-824` (`approve_run`)
- Modify: `tests/test_api.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_api.py`:

```python
def test_approve_passes_pause_after_character_sheet(tmp_path, monkeypatch, client):
    """After /approve, the spawned subprocess must include
    --pause-after-character-sheet so Veo doesn't auto-start."""
    from pipeline.api import set_spawn_fn
    captured: list[list[str]] = []
    def stub_spawn(args, run_dir):
        captured.append(args)
        return 9999
    set_spawn_fn(stub_spawn)
    # Set up a run in awaiting_approval
    run_id = _create_run_with_script_json(tmp_path)
    resp = client.post(f"/runs/{run_id}/approve",
                        headers={"Authorization": f"Bearer {TOKEN}"})
    assert resp.status_code == 200
    assert any(a == "--pause-after-character-sheet" for a in captured[0])
```

`_create_run_with_script_json` is a helper you write or reuse from existing test fixtures — it should write `script.json` + `seed.json` + `api_state.json` into a fresh `out/<id>/` and return the id. Reuse the pattern already present in `test_api.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_api.py::test_approve_passes_pause_after_character_sheet -v`
Expected: FAIL — flag not in spawned args.

- [ ] **Step 3: Implement**

In `pipeline/api.py:817`, change:

```python
args = ["--shorts", "--resume", str(run_dir)]
```

to:

```python
args = ["--shorts", "--resume", str(run_dir),
        "--pause-after-character-sheet"]
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_api.py -v`
Expected: new test PASSES; existing approve tests still pass.

- [ ] **Step 5: Commit**

```bash
git add pipeline/api.py tests/test_api.py
git commit -m "feat(api): /approve now pauses after Flux for second approval"
```

---

### Task 4: New `POST /runs/{id}/approve-veo` endpoint

**Files:**
- Modify: `pipeline/api.py` (add endpoint near the existing `approve_run` block)
- Modify: `tests/test_api.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_api.py`:

```python
def test_approve_veo_happy_path(tmp_path, monkeypatch, client):
    """From awaiting_veo_approval, /approve-veo spawns run.py --resume with no
    pause flags so Veo runs to completion."""
    from pipeline.api import set_spawn_fn
    captured: list[list[str]] = []
    def stub_spawn(args, run_dir):
        captured.append(args)
        return 9999
    set_spawn_fn(stub_spawn)
    run_id = _create_run_in_awaiting_veo_approval(tmp_path)
    resp = client.post(f"/runs/{run_id}/approve-veo",
                        headers={"Authorization": f"Bearer {TOKEN}"})
    assert resp.status_code == 200
    assert "--pause-after-character-sheet" not in captured[0]
    assert "--pause-after-script" not in captured[0]
    assert "--resume" in captured[0]


def test_approve_veo_rejected_from_wrong_status(tmp_path, monkeypatch, client):
    run_id = _create_run_with_script_json(tmp_path)  # awaiting_approval
    resp = client.post(f"/runs/{run_id}/approve-veo",
                        headers={"Authorization": f"Bearer {TOKEN}"})
    assert resp.status_code == 409
```

`_create_run_in_awaiting_veo_approval` writes `script.json` + `character_sheet.png` + `api_state.json` (no live PID) into a new run dir.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_api.py::test_approve_veo_happy_path tests/test_api.py::test_approve_veo_rejected_from_wrong_status -v`
Expected: FAIL — endpoint missing.

- [ ] **Step 3: Implement the endpoint**

Add to `pipeline/api.py` immediately after `approve_run`:

```python
@app.post(
    "/runs/{run_id}/approve-veo",
    response_model=ApprovalAck,
    dependencies=[Depends(require_token)],
)
def approve_veo_run(run_id: str):
    """Second approval gate — confirms the user is OK with the Flux character
    sheet and wants Veo to start spending. Only valid from awaiting_veo_approval.
    Spawns run.py --resume with NO pause flags so the pipeline runs Veo →
    captions → assemble in one shot."""
    run_dir = _run_dir(run_id)
    s = derive_status(run_dir)
    if s != "awaiting_veo_approval":
        raise HTTPException(
            409,
            f"cannot approve-veo from status={s} "
            f"(expected awaiting_veo_approval)",
        )
    args = ["--shorts", "--resume", str(run_dir)]
    max_spend = _compute_max_spend_for_run(run_dir)
    if max_spend is not None:
        args += ["--max-spend", f"{max_spend:.2f}"]
    pid = _SPAWN_FN(args, run_dir)
    _write_state(run_dir, pid=pid, last_error=None,
                 last_action="approve_veo")
    return ApprovalAck(run_id=run_id, status=derive_status(run_dir),
                      started_paid_stages=True)
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_api.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/api.py tests/test_api.py
git commit -m "feat(api): POST /runs/{id}/approve-veo for second approval gate"
```

---

### Task 5: Loosen `PUT /runs/{id}/script` to accept `awaiting_veo_approval`

**Files:**
- Modify: `pipeline/api.py:879-938` (`edit_script`)
- Modify: `tests/test_api.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_api.py`:

```python
def test_edit_script_allowed_in_awaiting_veo_approval(tmp_path, client):
    run_id = _create_run_in_awaiting_veo_approval(tmp_path)
    payload = {
        "title": "edited",
        "beats": [{
            "arabic": "نص جديد",
            "english_motion": "new visual",
            "speaker": "mother",
            "clip_duration_s": 8.0,
        }],
    }
    resp = client.put(
        f"/runs/{run_id}/script",
        json=payload,
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "edited"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_api.py::test_edit_script_allowed_in_awaiting_veo_approval -v`
Expected: FAIL — current code 409s for any status != awaiting_approval.

- [ ] **Step 3: Implement**

In `pipeline/api.py:889-893`, change:

```python
if s != "awaiting_approval":
    raise HTTPException(
        409,
        f"cannot edit script from status={s} (only awaiting_approval is editable)",
    )
```

to:

```python
if s not in ("awaiting_approval", "awaiting_veo_approval"):
    raise HTTPException(
        409,
        f"cannot edit script from status={s} "
        f"(only awaiting_approval / awaiting_veo_approval are editable)",
    )
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_api.py -v`
Expected: PASS for new test AND all existing edit-script tests (existing tests use awaiting_approval which is still allowed).

- [ ] **Step 5: Commit**

```bash
git add pipeline/api.py tests/test_api.py
git commit -m "feat(api): allow script edits during awaiting_veo_approval"
```

---

### Task 6: New `POST /runs/{id}/character-sheet/reroll` endpoint

**Files:**
- Modify: `pipeline/api.py`
- Modify: `tests/test_api.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_api.py`:

```python
def test_character_sheet_reroll_deletes_and_respawns(tmp_path, client):
    from pipeline.api import set_spawn_fn
    captured = []
    def stub_spawn(args, run_dir):
        captured.append(args)
        return 5555
    set_spawn_fn(stub_spawn)

    run_id = _create_run_in_awaiting_veo_approval(tmp_path)
    sheet = tmp_path / run_id / "character_sheet.png"
    assert sheet.exists()

    resp = client.post(
        f"/runs/{run_id}/character-sheet/reroll",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert resp.status_code == 200
    assert not sheet.exists(), "reroll must delete existing sheet"
    assert "--pause-after-character-sheet" in captured[0]


def test_character_sheet_reroll_rejected_from_wrong_status(tmp_path, client):
    run_id = _create_run_with_script_json(tmp_path)  # awaiting_approval
    resp = client.post(
        f"/runs/{run_id}/character-sheet/reroll",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert resp.status_code == 409
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_api.py -k character_sheet_reroll -v`
Expected: FAIL — endpoint missing.

- [ ] **Step 3: Implement**

Add to `pipeline/api.py` after `approve_veo_run`:

```python
@app.post(
    "/runs/{run_id}/character-sheet/reroll",
    response_model=ApprovalAck,
    dependencies=[Depends(require_token)],
)
def reroll_character_sheet(run_id: str):
    """Throw away the current Flux character sheet and regenerate it. Costs
    another $0.05 of Flux. Only valid from awaiting_veo_approval (you only
    reroll when you can see the current sheet is wrong)."""
    run_dir = _run_dir(run_id)
    s = derive_status(run_dir)
    if s != "awaiting_veo_approval":
        raise HTTPException(
            409,
            f"cannot reroll character sheet from status={s} "
            f"(expected awaiting_veo_approval)",
        )
    state = _read_state(run_dir)
    if _process_alive(state.get("pid")):
        raise HTTPException(409, "a pipeline process is already running")
    (run_dir / "character_sheet.png").unlink(missing_ok=True)
    args = ["--shorts", "--resume", str(run_dir),
            "--pause-after-character-sheet"]
    pid = _SPAWN_FN(args, run_dir)
    _write_state(run_dir, pid=pid, last_error=None,
                 last_action="reroll_character_sheet")
    return ApprovalAck(run_id=run_id, status=derive_status(run_dir),
                      started_paid_stages=True)
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_api.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/api.py tests/test_api.py
git commit -m "feat(api): POST /runs/{id}/character-sheet/reroll"
```

---

## Phase 2 — Per-clip video (backend)

### Task 7: New `GET /runs/{id}/clips/{i}/video` endpoint

**Files:**
- Modify: `pipeline/api.py`
- Modify: `tests/test_api.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_api.py`:

```python
def test_get_clip_video_serves_mp4(tmp_path, client):
    run_id = _create_run_with_script_json(tmp_path)
    clips = tmp_path / run_id / "clips"
    clips.mkdir()
    (clips / "03.mp4").write_bytes(b"fake-mp4-bytes")

    resp = client.get(
        f"/runs/{run_id}/clips/3/video",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "video/mp4"
    assert resp.content == b"fake-mp4-bytes"


def test_get_clip_video_404_when_missing(tmp_path, client):
    run_id = _create_run_with_script_json(tmp_path)
    resp = client.get(
        f"/runs/{run_id}/clips/2/video",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert resp.status_code == 404


def test_get_clip_video_query_token_works(tmp_path, client):
    """Query-string token path used by Flutter web."""
    run_id = _create_run_with_script_json(tmp_path)
    clips = tmp_path / run_id / "clips"
    clips.mkdir()
    (clips / "01.mp4").write_bytes(b"x")
    resp = client.get(f"/runs/{run_id}/clips/1/video?token={TOKEN}")
    assert resp.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_api.py -k get_clip_video -v`
Expected: FAIL — endpoint missing.

- [ ] **Step 3: Implement**

Add to `pipeline/api.py` immediately after the existing `get_clip_thumbnail` (around line 1249):

```python
@app.get(
    "/runs/{run_id}/clips/{clip_index}/video",
    dependencies=[Depends(require_token_header_or_query)],
)
def get_clip_video(run_id: str, clip_index: int):
    """Stream a single Veo clip's mp4. Mirrors /clips/{i}/thumbnail but for
    full-motion playback. Used by the run-detail screen's tap-to-play UX."""
    if clip_index < 1 or clip_index > 99:
        raise HTTPException(400, "clip_index out of range")
    run_dir = _run_dir(run_id)
    clip_path = run_dir / "clips" / f"{clip_index:02d}.mp4"
    if not clip_path.exists():
        raise HTTPException(404, "clip not generated yet")
    return FileResponse(
        path=str(clip_path),
        media_type="video/mp4",
        filename=f"{run_id}-clip-{clip_index:02d}.mp4",
    )
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_api.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/api.py tests/test_api.py
git commit -m "feat(api): GET /runs/{id}/clips/{i}/video for per-clip playback"
```

---

## Phase 3 — Hybrid paste-script parser (backend)

### Task 8: Create `pipeline/script_splitter.py` with verbatim guard

**Files:**
- Create: `pipeline/script_splitter.py`
- Create: `tests/test_script_splitter.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_script_splitter.py`:

```python
from __future__ import annotations

import pytest
from pipeline.script_splitter import split_prose_into_beats, _verbatim_match


class _StubLLM:
    """Mimics the .complete() interface of the LLM router used elsewhere."""
    def __init__(self, response: str):
        self.response = response
        self.calls = 0
    def complete(self, prompt: str, system: str = "") -> str:
        self.calls += 1
        return self.response


def test_splits_prose_into_n_beats_verbatim():
    raw = "أنا قاعدة بالمطبخ. ابني نسي. قلبي مكسور."
    llm_response = '''{"beats":[
        {"arabic":"أنا قاعدة بالمطبخ.","english_motion":"mother in kitchen","speaker":"mother","clip_duration_s":7.0},
        {"arabic":"ابني نسي.","english_motion":"son walks away","speaker":"son","clip_duration_s":7.0},
        {"arabic":"قلبي مكسور.","english_motion":"close-up tears","speaker":"mother","clip_duration_s":7.0}
    ]}'''
    llm = _StubLLM(llm_response)
    beats = split_prose_into_beats(llm, raw, target_beats=3, per_beat_seconds=7)
    assert len(beats) == 3
    assert beats[0].arabic == "أنا قاعدة بالمطبخ."
    assert beats[1].speaker == "son"


def test_verbatim_guard_rejects_rewritten_arabic():
    """If the LLM 'improves' the text, the verbatim check must reject and retry."""
    raw = "أنا قاعدة بالمطبخ."
    bad = '''{"beats":[{"arabic":"أنا قاعدة في المطبخ الحزين","english_motion":"x","speaker":"mother","clip_duration_s":8}]}'''
    good = '''{"beats":[{"arabic":"أنا قاعدة بالمطبخ.","english_motion":"x","speaker":"mother","clip_duration_s":8}]}'''
    class _RetryLLM:
        def __init__(self):
            self.calls = 0
        def complete(self, prompt, system=""):
            self.calls += 1
            return bad if self.calls == 1 else good
    llm = _RetryLLM()
    beats = split_prose_into_beats(llm, raw, target_beats=1, per_beat_seconds=8)
    assert llm.calls == 2  # first rejected, second accepted
    assert beats[0].arabic == "أنا قاعدة بالمطبخ."


def test_naive_fallback_on_persistent_verbatim_failure():
    """If the LLM keeps rewriting, fall back to sentence-split — must still
    produce >1 beats."""
    raw = "جملة أولى. جملة ثانية. جملة ثالثة."
    bad = '''{"beats":[{"arabic":"شيء مختلف","english_motion":"x","speaker":"mother","clip_duration_s":8}]}'''
    llm = _StubLLM(bad)
    beats = split_prose_into_beats(llm, raw, target_beats=3, per_beat_seconds=8)
    assert len(beats) >= 2  # naive splitter produces multiple beats
    # All naive-fallback beats must be substrings of raw
    for b in beats:
        assert b.arabic.strip() in raw or raw.find(b.arabic.strip()) >= 0


def test_verbatim_match_helper_tolerates_whitespace():
    assert _verbatim_match("أ ب ج", "أب ج") is True
    assert _verbatim_match("أ ب ج", "أ ب  ج\n") is True
    assert _verbatim_match("أ ب ج", "أ ب د") is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_script_splitter.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement the module**

Create `pipeline/script_splitter.py`:

```python
"""LLM-based prose-to-beats splitter for the hybrid paste-script parser.

Used by POST /runs/parse-script when the regex parser finds zero dialogue
blocks (i.e. freeform prose, not the structured episode-markdown grammar).

Critical invariant: the LLM segments text but NEVER rewrites it. We verify
this by concatenating every output beat's `arabic` field and comparing
(whitespace-normalised) to the input. Mismatches retry once; persistent
mismatches fall back to a naive sentence-split that always produces
multiple beats."""
from __future__ import annotations

import json
import re

from pipeline.script_parser import ParsedBeat

_SYSTEM = (
    "You are a script-segmentation tool. You split Arabic prose into beats "
    "without rewriting a single character of the user's text. You only "
    "decide WHERE to cut and produce visual descriptions."
)

_PROMPT_TEMPLATE = """\
Split the following Arabic prose into approximately {target_beats} beats
(±1 acceptable). For each beat output:

- arabic: a verbatim contiguous slice of the input. Concatenated together,
  every beat's arabic field MUST equal the original input minus whitespace.
  Do not paraphrase, summarise, fix grammar, or change a single word.
- english_motion: a short English visual prompt for video generation (~25 words).
- speaker: one of mother, son, father, doctor, neighbor, grandmother, wife,
  daughter, friend, enemy, shadow. Pick the most likely speaker for that beat.
- clip_duration_s: a number between {min_s} and {max_s} based on beat length.

Return JSON only, no markdown:

{{"beats": [{{"arabic":"…","english_motion":"…","speaker":"…","clip_duration_s":N}}, ...]}}

Input prose:
{raw}
"""

_VALID_SPEAKERS = {
    "mother", "son", "father", "doctor", "neighbor",
    "grandmother", "wife", "daughter", "friend", "enemy", "shadow",
}


def _normalize(s: str) -> str:
    """Collapse all whitespace to single spaces and strip — used by the
    verbatim guard so trivial whitespace differences don't trigger a retry."""
    return re.sub(r"\s+", " ", s).strip()


def _verbatim_match(input_text: str, joined_output: str) -> bool:
    """True iff the LLM's concatenated arabic equals the input modulo whitespace."""
    return _normalize(input_text) == _normalize(joined_output)


def _strip_code_fence(text: str) -> str:
    """Mirror the helper in pipeline/script.py — handle ```json ... ``` wraps."""
    s = text.strip()
    m = re.match(r"^```(?:json)?\s*\n(.*?)\n```\s*$", s, re.DOTALL)
    return m.group(1).strip() if m else s


def _parse_response(raw_response: str) -> list[ParsedBeat]:
    cleaned = _strip_code_fence(raw_response)
    data = json.loads(cleaned)
    beats_raw = data.get("beats") or []
    beats: list[ParsedBeat] = []
    for b in beats_raw:
        speaker = str(b.get("speaker", "")).strip().lower()
        if speaker not in _VALID_SPEAKERS:
            speaker = "mother"  # safe default
        beats.append(ParsedBeat(
            arabic=str(b.get("arabic", "")).strip(),
            english_motion=str(b.get("english_motion", "")).strip(),
            speaker=speaker,
            clip_duration_s=float(b.get("clip_duration_s", 8.0)),
        ))
    return beats


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[\.!\?؟…])\s+|\n\n+")


def _naive_split(raw: str, target_beats: int, per_beat_seconds: int) -> list[ParsedBeat]:
    """Last-resort sentence splitter. Always produces ≥1 beat; tries to land
    near `target_beats` by grouping sentences into roughly-equal chunks."""
    sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(raw) if s.strip()]
    if not sentences:
        sentences = [raw.strip()]
    if len(sentences) <= target_beats:
        groups = [[s] for s in sentences]
    else:
        # Distribute sentences across target_beats groups
        per_group = max(1, len(sentences) // target_beats)
        groups = [
            sentences[i:i + per_group]
            for i in range(0, len(sentences), per_group)
        ]
        # Merge any trailing tiny group into the previous one
        if len(groups) > target_beats and len(groups[-1]) <= 1:
            groups[-2].extend(groups[-1])
            groups.pop()
    return [
        ParsedBeat(
            arabic=" ".join(g),
            english_motion="(auto-generated visual — please review)",
            speaker="mother",
            clip_duration_s=float(per_beat_seconds),
        )
        for g in groups
    ]


def split_prose_into_beats(
    llm,
    raw_text: str,
    target_beats: int = 8,
    per_beat_seconds: int = 8,
) -> list[ParsedBeat]:
    """Split freeform prose into beats. LLM-first with verbatim guard;
    naive sentence-split fallback if the LLM keeps rewriting."""
    target_beats = max(2, min(15, target_beats))
    min_s = max(4.0, per_beat_seconds * 0.6)
    max_s = min(12.0, per_beat_seconds * 1.4)
    prompt = _PROMPT_TEMPLATE.format(
        target_beats=target_beats,
        min_s=min_s, max_s=max_s,
        raw=raw_text,
    )
    for attempt in range(2):
        try:
            response = llm.complete(prompt, system=_SYSTEM)
            beats = _parse_response(response)
        except (json.JSONDecodeError, ValueError, TypeError):
            continue
        if not beats:
            continue
        joined = " ".join(b.arabic for b in beats)
        if _verbatim_match(raw_text, joined):
            return beats
    # Both attempts failed — fall back
    return _naive_split(raw_text, target_beats, per_beat_seconds)
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_script_splitter.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/script_splitter.py tests/test_script_splitter.py
git commit -m "feat(splitter): LLM prose-to-beats splitter with verbatim guard"
```

---

### Task 9: Wire `/runs/parse-script` to use hybrid path

**Files:**
- Modify: `pipeline/api.py:619-651` (`ParseScriptRequest`, `ParseScriptResponse`, `parse_script`)
- Modify: `tests/test_api.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_api.py`:

```python
def test_parse_script_regex_path(client, monkeypatch):
    """Structured markdown still uses regex (parse_method=regex)."""
    raw = """**العنوان: Episode 1**\n\n**المشهد 1 – Opening**\n\n**الأم:**\n"كلام الأم"\n\n**الابن:**\n"كلام الابن"\n"""
    resp = client.post("/runs/parse-script",
                       json={"raw_text": raw},
                       headers={"Authorization": f"Bearer {TOKEN}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["parse_method"] == "regex"
    assert len(body["beats"]) >= 2


def test_parse_script_llm_fallback(client, monkeypatch):
    """Freeform prose with no dialogue markers → llm_split."""
    from pipeline import api as api_mod
    raw = "أنا قاعدة بالمطبخ. ابني نسي. قلبي مكسور."
    fake_response = '{"beats":[' \
        '{"arabic":"أنا قاعدة بالمطبخ.","english_motion":"x","speaker":"mother","clip_duration_s":7},' \
        '{"arabic":"ابني نسي.","english_motion":"y","speaker":"son","clip_duration_s":7},' \
        '{"arabic":"قلبي مكسور.","english_motion":"z","speaker":"mother","clip_duration_s":7}' \
        ']}'
    class _Stub:
        def complete(self, p, system=""): return fake_response
    monkeypatch.setattr(api_mod, "_get_splitter_llm", lambda: _Stub())
    resp = client.post("/runs/parse-script",
                       json={"raw_text": raw, "target_beats": 3},
                       headers={"Authorization": f"Bearer {TOKEN}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["parse_method"] == "llm_split"
    assert len(body["beats"]) == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_api.py -k parse_script -v`
Expected: FAIL — `parse_method` field missing, `target_beats` not accepted.

- [ ] **Step 3: Update request/response shapes and handler**

In `pipeline/api.py:619-626`, replace:

```python
class ParseScriptRequest(BaseModel):
    raw_text: str = Field(..., min_length=4)


class ParseScriptResponse(BaseModel):
    title: str
    beats: list[PasteScriptBeat]
```

with:

```python
class ParseScriptRequest(BaseModel):
    raw_text: str = Field(..., min_length=4)
    target_beats: int = Field(default=8, ge=4, le=15,
                              description="Target beats for the LLM splitter "
                                          "(ignored on the regex path)")


class ParseScriptResponse(BaseModel):
    title: str
    beats: list[PasteScriptBeat]
    parse_method: Literal["regex", "llm_split", "naive_fallback"]
```

Add a small indirection so tests can stub the LLM (above the endpoint, before `parse_script`):

```python
def _get_splitter_llm():
    """Lazy-import + return the configured LLM client. Indirection point so
    tests can monkeypatch this without touching the actual router."""
    from pipeline.llm import get_llm_client
    return get_llm_client()
```

(If `pipeline.llm.get_llm_client` doesn't exist, use whatever the existing
router exposes — check `pipeline/llm_anthropic.py` and `pipeline/llm.py`.
Match the call shape used elsewhere in `pipeline/script.py`'s
`generate_shorts_script`.)

Replace the `parse_script` handler (line 633) with:

```python
@app.post(
    "/runs/parse-script",
    response_model=ParseScriptResponse,
    dependencies=[Depends(require_token)],
)
def parse_script(req: ParseScriptRequest):
    """Hybrid parser. Step 1: try the regex parser (fast, free, exact for
    structured markdown). If it found ≥2 dialogue beats, return that result.
    Otherwise, step 2: send the prose to the LLM splitter with a verbatim
    guard. If even that fails, fall back to a naive sentence split — the
    user always gets >1 beat."""
    from pipeline.script_parser import parse_episode_markdown
    from pipeline.script_splitter import split_prose_into_beats
    parsed = parse_episode_markdown(req.raw_text)
    dialogue_beats = [b for b in parsed.beats if b.arabic.strip()]
    if len(dialogue_beats) >= 2:
        return ParseScriptResponse(
            title=parsed.title,
            beats=[
                PasteScriptBeat(
                    arabic=b.arabic, english_motion=b.english_motion,
                    speaker=b.speaker, clip_duration_s=b.clip_duration_s,
                )
                for b in parsed.beats
            ],
            parse_method="regex",
        )
    # Regex miss — fall through to LLM splitter
    llm = _get_splitter_llm()
    split_beats = split_prose_into_beats(
        llm, req.raw_text, target_beats=req.target_beats, per_beat_seconds=8,
    )
    # split_prose_into_beats internally falls back to naive on persistent
    # verbatim failure. We can't tell from here which path it took without
    # a second signal, so query the function: any beat with
    # english_motion=="(auto-generated visual — please review)" is the naive marker.
    is_naive = any(
        b.english_motion == "(auto-generated visual — please review)"
        for b in split_beats
    )
    return ParseScriptResponse(
        title=parsed.title or "Untitled",
        beats=[
            PasteScriptBeat(
                arabic=b.arabic, english_motion=b.english_motion,
                speaker=b.speaker, clip_duration_s=b.clip_duration_s,
            )
            for b in split_beats
        ],
        parse_method="naive_fallback" if is_naive else "llm_split",
    )
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_api.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/api.py tests/test_api.py
git commit -m "feat(api): /parse-script hybrid path with regex + LLM fallback"
```

---

## Phase 4 — Freeform AI mode (backend)

### Task 10: Create `pipeline/script_freeform.py`

**Files:**
- Create: `pipeline/script_freeform.py`
- Create: `tests/test_script_freeform.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_script_freeform.py`:

```python
from __future__ import annotations

from pipeline.script_freeform import (
    FreeformControls,
    build_freeform_prompt,
    generate_freeform_script,
)
from pipeline.types import ThemeSeed


def test_controls_interpolated_into_prompt():
    seed = ThemeSeed(theme="urban", premise="A photographer who loses memory.")
    controls = FreeformControls(
        dialect="egyptian", art_style="anime_2d",
        character_template="human", ending_type="twist",
        num_beats=10, per_beat_seconds=8,
    )
    prompt = build_freeform_prompt(seed, controls)
    assert "egyptian" in prompt.lower()
    assert "anime" in prompt.lower()
    assert "twist" in prompt.lower()
    assert "10" in prompt  # num_beats present
    assert "A photographer who loses memory." in prompt


def test_no_hardcoded_sunstoriz_in_default_prompt():
    """Critical: the default prompt MUST NOT mention fruit characters,
    Syrian dialect, or tragic-ending lock — those were the static-story bug."""
    seed = ThemeSeed(theme="folkloric", premise="x")
    controls = FreeformControls()  # all defaults
    prompt = build_freeform_prompt(seed, controls)
    lower = prompt.lower()
    assert "lemon" not in lower
    assert "strawberry" not in lower
    assert "syrian" not in lower
    assert "tragic" not in lower or "ai_choose" in lower  # only as a menu item


class _StubLLM:
    def __init__(self, response): self.response = response
    def complete(self, prompt, system=""): return self.response


def test_generate_freeform_script_happy_path():
    llm = _StubLLM('''{
      "title":"Lost",
      "theme":"urban",
      "global_setting":"foggy city",
      "music_mood":"dread",
      "target_duration_s":24,
      "beats":[
        {"arabic":"بيت أول","english_motion":"x","clip_duration_s":8,"speaker":"mother"},
        {"arabic":"بيت ثاني","english_motion":"y","clip_duration_s":8,"speaker":"son"},
        {"arabic":"بيت ثالث","english_motion":"z","clip_duration_s":8,"speaker":"father"}
      ]
    }''')
    seed = ThemeSeed(theme="urban", premise="x")
    controls = FreeformControls(num_beats=3, per_beat_seconds=8)
    script = generate_freeform_script(llm, seed, controls)
    assert script.title == "Lost"
    assert len(script.beats) == 3
    assert script.beats[1].speaker == "son"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_script_freeform.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement the module**

Create `pipeline/script_freeform.py`:

```python
"""Freeform Arabic short-script generator.

Unlike pipeline.script.generate_shorts_script (which is locked to the
Sunstoriz fruit-melodrama template), this module's prompt is parameterised
by user-supplied controls — dialect, art style, character template, ending
type. The downstream Script schema is identical so Flux/Veo/assemble are
unchanged."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pipeline.script import _parse_shorts_script_json
from pipeline.types import Script, ThemeSeed


Dialect = Literal["msa", "syrian", "egyptian", "khaliji", "maghrebi", "iraqi"]
ArtStyle = Literal[
    "pixar_3d", "anime_2d", "cinematic_photo_real",
    "claymation", "hand_drawn", "ghibli",
]
CharacterTemplate = Literal[
    "human", "fruit_sunstoriz", "animal", "surreal", "ai_choose",
]
EndingType = Literal[
    "open", "closed_tragic", "closed_happy", "twist", "ai_choose",
]


_DIALECT_TO_HUMAN = {
    "msa": "Modern Standard Arabic (الفصحى)",
    "syrian": "Syrian / Levantine dialect (شامي)",
    "egyptian": "Egyptian dialect (مصري)",
    "khaliji": "Khaliji / Gulf dialect (خليجي)",
    "maghrebi": "Maghrebi / North-African dialect (مغربي)",
    "iraqi": "Iraqi dialect (عراقي)",
}

_ART_STYLE_TO_HUMAN = {
    "pixar_3d": "3D Pixar-style animation",
    "anime_2d": "2D anime",
    "cinematic_photo_real": "cinematic photo-real live-action look",
    "claymation": "claymation / stop-motion",
    "hand_drawn": "hand-drawn illustrative animation",
    "ghibli": "Studio Ghibli-style 2D animation",
}

_CHAR_TEMPLATE_TO_HUMAN = {
    "human": "human characters",
    "fruit_sunstoriz": "anthropomorphic fruit characters (Sunstoriz style)",
    "animal": "anthropomorphic animal characters",
    "surreal": "surreal / abstract creatures",
    "ai_choose": "let the writer choose whichever character cast fits the premise",
}

_ENDING_TO_HUMAN = {
    "open": "an open-ended, unresolved ending",
    "closed_tragic": "a closed tragic ending (clear loss / death / final breaking point)",
    "closed_happy": "a closed happy or hopeful ending",
    "twist": "a twist ending the audience does not see coming",
    "ai_choose": "whichever ending type best serves the premise",
}


@dataclass(frozen=True)
class FreeformControls:
    dialect: Dialect = "msa"
    art_style: ArtStyle = "cinematic_photo_real"
    character_template: CharacterTemplate = "ai_choose"
    ending_type: EndingType = "ai_choose"
    num_beats: int = 8
    per_beat_seconds: int = 8


_SYSTEM = (
    "You are an Arabic-language short-form video script writer. You adapt "
    "your style — dialect, character cast, ending type, art direction — to "
    "the user's premise and controls. You do not impose any fixed template."
)


_PROMPT_TEMPLATE = """\
Write a short-form Arabic video script (TikTok / Reels) for the following premise.

Premise: {premise}
Theme tag: {theme}

Controls:
- Dialect: {dialect}
- Visual / art style: {art_style}
- Character cast: {character_template}
- Ending type: {ending_type}
- Number of beats: exactly {num_beats}
- Target duration per beat: ~{per_beat_seconds}s (each clip_duration_s between {min_s} and {max_s})

Requirements:
- All Arabic dialogue MUST be in {dialect}. No mixing with other dialects.
- Each beat speaks in first person — a named character talks, not a narrator.
- Speaker values must be one of: mother, son, father, doctor, neighbor,
  grandmother, wife, daughter, friend, enemy, shadow.
- english_motion describes the visual action for that beat (~25 words),
  reinforcing visual continuity from the previous beat.
- The final beat must match the ending type above.
- music_mood: pick one of drone, dread, cosmic, discovery.

Return JSON only, no markdown:

{{
  "title": "...",
  "theme": "{theme}",
  "global_setting": "short English visual style summary",
  "music_mood": "drone|dread|cosmic|discovery",
  "target_duration_s": <int>,
  "beats": [
    {{"arabic":"...","english_motion":"...","clip_duration_s":<float>,"speaker":"..."}},
    ...exactly {num_beats} beats...
  ]
}}
"""


def build_freeform_prompt(seed: ThemeSeed, controls: FreeformControls) -> str:
    min_s = max(4.0, controls.per_beat_seconds * 0.6)
    max_s = min(12.0, controls.per_beat_seconds * 1.4)
    return _PROMPT_TEMPLATE.format(
        premise=seed.premise,
        theme=seed.theme,
        dialect=_DIALECT_TO_HUMAN[controls.dialect],
        art_style=_ART_STYLE_TO_HUMAN[controls.art_style],
        character_template=_CHAR_TEMPLATE_TO_HUMAN[controls.character_template],
        ending_type=_ENDING_TO_HUMAN[controls.ending_type],
        num_beats=controls.num_beats,
        per_beat_seconds=controls.per_beat_seconds,
        min_s=min_s, max_s=max_s,
    )


def generate_freeform_script(
    llm,
    seed: ThemeSeed,
    controls: FreeformControls,
) -> Script:
    prompt = build_freeform_prompt(seed, controls)
    raw = llm.complete(prompt, system=_SYSTEM)
    return _parse_shorts_script_json(raw, seed)
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_script_freeform.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/script_freeform.py tests/test_script_freeform.py
git commit -m "feat(script): freeform script generator with user-supplied controls"
```

---

### Task 11: Add `--freeform` CLI flag to run.py

**Files:**
- Modify: `run.py` (argparse + shorts script stage selector)
- Modify: `tests/test_run_shorts_smoke.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_run_shorts_smoke.py`:

```python
def test_freeform_flag_routes_to_freeform_writer(tmp_path, monkeypatch):
    """When --freeform is passed, the shorts-script stage calls
    generate_freeform_script, NOT generate_shorts_script."""
    called = {}
    def fake_freeform(llm, seed, controls):
        called["freeform"] = True
        return _MINIMAL_SCRIPT
    def fake_shorts(*a, **kw):
        called["shorts"] = True
        return _MINIMAL_SCRIPT
    monkeypatch.setattr("pipeline.script_freeform.generate_freeform_script",
                        fake_freeform)
    monkeypatch.setattr("pipeline.script.generate_shorts_script", fake_shorts)
    # Stub out paid stages so the run completes
    monkeypatch.setattr("run._stage_character_sheet", lambda *a, **kw: None)
    monkeypatch.setattr("run._stage_video_chained", lambda *a, **kw: None)
    monkeypatch.setattr("run._stage_shorts_captions", lambda *a, **kw: False)
    monkeypatch.setattr("run._stage_assemble", lambda *a, **kw: None)

    rc = run.main([
        "--shorts", "--freeform",
        "--theme", "urban", "--seed", "test",
        "--out-root", str(tmp_path),
        "--pause-after-script",
        "--ff-dialect", "egyptian",
        "--ff-art-style", "anime_2d",
        "--ff-character-template", "human",
        "--ff-ending-type", "twist",
        "--ff-num-beats", "6",
    ])
    assert rc == 0
    assert called.get("freeform") is True
    assert "shorts" not in called
```

`_MINIMAL_SCRIPT` should be a real `Script` instance with one beat — define near the top of the test file alongside `_MINIMAL_SCRIPT_JSON`.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_run_shorts_smoke.py::test_freeform_flag_routes_to_freeform_writer -v`
Expected: FAIL — argparse rejects `--freeform`.

- [ ] **Step 3: Implement**

In `run.py`, near the existing `--shorts` flag (around line 536), add:

```python
p.add_argument("--freeform", action="store_true",
               help="Use the freeform script writer (premise-driven, "
                    "no fixed character/dialect/ending). Requires --shorts.")
p.add_argument("--ff-dialect", default="msa",
               choices=["msa", "syrian", "egyptian", "khaliji",
                        "maghrebi", "iraqi"])
p.add_argument("--ff-art-style", default="cinematic_photo_real",
               choices=["pixar_3d", "anime_2d", "cinematic_photo_real",
                        "claymation", "hand_drawn", "ghibli"])
p.add_argument("--ff-character-template", default="ai_choose",
               choices=["human", "fruit_sunstoriz", "animal",
                        "surreal", "ai_choose"])
p.add_argument("--ff-ending-type", default="ai_choose",
               choices=["open", "closed_tragic", "closed_happy",
                        "twist", "ai_choose"])
p.add_argument("--ff-num-beats", type=int, default=8)
p.add_argument("--ff-per-beat-seconds", type=int, default=8)
```

Locate the `_stage_shorts_script(...)` call (around line 582) and add a branch:

```python
with log.stage("script"):
    if args.freeform:
        from pipeline.script_freeform import (
            FreeformControls, generate_freeform_script,
        )
        from pipeline.types import ThemeSeed
        controls = FreeformControls(
            dialect=args.ff_dialect,
            art_style=args.ff_art_style,
            character_template=args.ff_character_template,
            ending_type=args.ff_ending_type,
            num_beats=args.ff_num_beats,
            per_beat_seconds=args.ff_per_beat_seconds,
        )
        script = generate_freeform_script(
            gemini, ThemeSeed(theme=args.theme, premise=args.seed), controls,
        )
        # Persist to disk same way _stage_shorts_script does
        paths.script_json.write_text(
            json.dumps(script.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    else:
        script = _stage_shorts_script(gemini, seed, cfg, paths,
                                       max_beats_override=args.max_beats)
```

(Match the existing JSON-write pattern by inspecting `_stage_shorts_script`'s
trailing logic in `run.py` — the simplest robust path is to refactor
`_stage_shorts_script` so it accepts a callable for `generate_*` and call it
twice, but for this task an inline branch is fine.)

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_run_shorts_smoke.py -v`
Expected: PASS — new test passes, existing pause-after-script tests still pass.

- [ ] **Step 5: Commit**

```bash
git add run.py tests/test_run_shorts_smoke.py
git commit -m "feat(run): --freeform CLI flag for the freeform script path"
```

---

### Task 12: New `POST /runs/freeform` endpoint

**Files:**
- Modify: `pipeline/api.py`
- Modify: `tests/test_api.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_api.py`:

```python
def test_freeform_endpoint_spawns_subprocess_with_flags(tmp_path, client):
    from pipeline.api import set_spawn_fn
    captured = []
    def stub_spawn(args, run_dir):
        captured.append(args)
        return 4242
    set_spawn_fn(stub_spawn)
    payload = {
        "theme": "urban",
        "premise": "A photographer who loses memory in Cairo.",
        "dialect": "egyptian",
        "art_style": "anime_2d",
        "character_template": "human",
        "ending_type": "twist",
        "num_beats": 8,
        "per_beat_seconds": 8,
    }
    resp = client.post("/runs/freeform", json=payload,
                       headers={"Authorization": f"Bearer {TOKEN}"})
    assert resp.status_code == 201
    assert "--freeform" in captured[0]
    assert "--ff-dialect" in captured[0]
    assert "egyptian" in captured[0]
    assert "--pause-after-script" in captured[0]


def test_freeform_endpoint_validates_dialect(client):
    payload = {"theme": "urban", "premise": "x", "dialect": "klingon",
               "art_style": "anime_2d", "character_template": "human",
               "ending_type": "twist", "num_beats": 8, "per_beat_seconds": 8}
    resp = client.post("/runs/freeform", json=payload,
                       headers={"Authorization": f"Bearer {TOKEN}"})
    assert resp.status_code in (400, 422)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_api.py -k freeform -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

Add to `pipeline/api.py` near the existing `create_run` endpoint:

```python
class CreateFreeformRunRequest(BaseModel):
    theme: str
    premise: str = Field(..., min_length=4)
    dialect: Literal["msa", "syrian", "egyptian", "khaliji",
                     "maghrebi", "iraqi"] = "msa"
    art_style: Literal["pixar_3d", "anime_2d", "cinematic_photo_real",
                       "claymation", "hand_drawn", "ghibli"] = "cinematic_photo_real"
    character_template: Literal["human", "fruit_sunstoriz", "animal",
                                "surreal", "ai_choose"] = "ai_choose"
    ending_type: Literal["open", "closed_tragic", "closed_happy",
                         "twist", "ai_choose"] = "ai_choose"
    num_beats: int = Field(default=8, ge=4, le=15)
    per_beat_seconds: int = Field(default=8, ge=4, le=10)


@app.post(
    "/runs/freeform",
    response_model=RunSummary,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_token)],
)
def create_freeform_run(req: CreateFreeformRunRequest):
    if req.theme not in VALID_THEMES:
        raise HTTPException(400, f"theme must be one of {sorted(VALID_THEMES)}")

    run_id = _make_run_id()
    run_dir = _out_root() / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    args = [
        "--shorts", "--freeform", "--pause-after-script",
        "--theme", req.theme,
        "--seed", req.premise,
        "--run-dir", str(run_dir),
        "--ff-dialect", req.dialect,
        "--ff-art-style", req.art_style,
        "--ff-character-template", req.character_template,
        "--ff-ending-type", req.ending_type,
        "--ff-num-beats", str(req.num_beats),
        "--ff-per-beat-seconds", str(req.per_beat_seconds),
    ]
    pid = _SPAWN_FN(args, run_dir)
    _write_state(
        run_dir,
        pid=pid,
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        last_error=None,
        last_action="create_freeform_run",
    )
    return _summarize(run_dir)
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_api.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/api.py tests/test_api.py
git commit -m "feat(api): POST /runs/freeform endpoint"
```

---

## Phase 5 — Frontend models + API client

### Task 13: Extend `RunStatus` and parse-script response in models.dart

**Files:**
- Modify: `lib/api/models.dart`

- [ ] **Step 1: Locate the existing enum**

Read `lib/api/models.dart` and find the `RunStatus` enum and the existing `getRunStatusFromString` helper / extension getters (`isAwaitingApproval`, `isComplete`, etc.).

- [ ] **Step 2: Add the new enum value + getter**

Add `awaitingVeoApproval` to the `RunStatus` enum, mapped to JSON key `"awaiting_veo_approval"` everywhere existing strings are mapped (`runStatusFromString`, `runStatusToString`, or whatever pattern the file uses). Add a getter:

```dart
extension RunStatusX on RunSummary {
  bool get isAwaitingVeoApproval =>
      status == RunStatus.awaitingVeoApproval;
}
```

(If the file already has an extension class, add the getter inside it.)

- [ ] **Step 3: Add `ParseMethod` enum and update `ParseScriptResponse`**

If `ParseScriptResponse` doesn't exist in `lib/api/models.dart` yet, add it:

```dart
enum ParseMethod { regex, llmSplit, naiveFallback }

ParseMethod parseMethodFromString(String s) => switch (s) {
      'regex' => ParseMethod.regex,
      'llm_split' => ParseMethod.llmSplit,
      'naive_fallback' => ParseMethod.naiveFallback,
      _ => ParseMethod.regex,
    };

class ParseScriptResponse {
  final String title;
  final List<PasteScriptBeat> beats;
  final ParseMethod parseMethod;
  ParseScriptResponse({required this.title, required this.beats,
                      required this.parseMethod});
  factory ParseScriptResponse.fromJson(Map<String, dynamic> j) =>
      ParseScriptResponse(
        title: j['title'] as String? ?? '',
        beats: (j['beats'] as List? ?? [])
            .map((b) => PasteScriptBeat.fromJson(b as Map<String, dynamic>))
            .toList(),
        parseMethod: parseMethodFromString(j['parse_method'] as String? ?? 'regex'),
      );
}
```

- [ ] **Step 4: Verify Flutter still analyzes**

Run: `flutter analyze`
Expected: no new errors. (Pre-existing errors at `lib/main.dart:31` / `:105` are noted in CLAUDE.md as not blocking — leave them unless you fix them as a separate cleanup.)

- [ ] **Step 5: Commit**

```bash
git add lib/api/models.dart
git commit -m "feat(flutter): models — RunStatus.awaitingVeoApproval + ParseScriptResponse"
```

---

### Task 14: Add new methods to `client.dart`

**Files:**
- Modify: `lib/api/client.dart`

- [ ] **Step 1: Add `approveVeoRun`**

Find the existing `approveRun` method. Add a sibling:

```dart
Future<ApprovalAck> approveVeoRun(String runId) async {
  final resp = await _http.post(
    Uri.parse('$_baseUrl/runs/$runId/approve-veo'),
    headers: _headers,
  );
  _throwIfError(resp);
  return ApprovalAck.fromJson(jsonDecode(resp.body));
}
```

- [ ] **Step 2: Add `rerollCharacterSheet`**

```dart
Future<ApprovalAck> rerollCharacterSheet(String runId) async {
  final resp = await _http.post(
    Uri.parse('$_baseUrl/runs/$runId/character-sheet/reroll'),
    headers: _headers,
  );
  _throwIfError(resp);
  return ApprovalAck.fromJson(jsonDecode(resp.body));
}
```

- [ ] **Step 3: Add `createFreeformRun`**

```dart
Future<RunSummary> createFreeformRun({
  required String theme,
  required String premise,
  required String dialect,
  required String artStyle,
  required String characterTemplate,
  required String endingType,
  required int numBeats,
  required int perBeatSeconds,
}) async {
  final resp = await _http.post(
    Uri.parse('$_baseUrl/runs/freeform'),
    headers: {..._headers, 'Content-Type': 'application/json'},
    body: jsonEncode({
      'theme': theme,
      'premise': premise,
      'dialect': dialect,
      'art_style': artStyle,
      'character_template': characterTemplate,
      'ending_type': endingType,
      'num_beats': numBeats,
      'per_beat_seconds': perBeatSeconds,
    }),
  );
  _throwIfError(resp);
  return RunSummary.fromJson(jsonDecode(resp.body));
}
```

- [ ] **Step 4: Update `parseScript` to accept `targetBeats` and return `ParseScriptResponse`**

Replace the existing `parseScript` body with:

```dart
Future<ParseScriptResponse> parseScript(String rawText,
    {int targetBeats = 8}) async {
  final resp = await _http.post(
    Uri.parse('$_baseUrl/runs/parse-script'),
    headers: {..._headers, 'Content-Type': 'application/json'},
    body: jsonEncode({'raw_text': rawText, 'target_beats': targetBeats}),
  );
  _throwIfError(resp);
  return ParseScriptResponse.fromJson(jsonDecode(resp.body));
}
```

(If callers expect the old shape — `Map<String, dynamic>` — also update those call sites in `new_run_screen.dart`. The compiler will tell you.)

- [ ] **Step 5: Add `clipVideoUrl` helper**

Append:

```dart
/// Returns the URL for a single clip's mp4 with the auth token in the
/// query string (so the Flutter video_player plugin works on web, where
/// it cannot attach Authorization headers).
String clipVideoUrl(String runId, int clipIndex) =>
    '$_baseUrl/runs/$runId/clips/$clipIndex/video?token=$_token';
```

(If `_token` is private to a different scope, expose it the same way the existing `videoUrl` / `thumbnailUrl` helpers do — match the pattern already in the file.)

- [ ] **Step 6: Verify Flutter still analyzes**

Run: `flutter analyze`
Expected: no new errors.

- [ ] **Step 7: Commit**

```bash
git add lib/api/client.dart lib/screens/new_run_screen.dart
git commit -m "feat(flutter): API client — approve-veo, sheet reroll, freeform, clip video"
```

(`new_run_screen.dart` is included only if Step 4's signature change forced an update there.)

---

## Phase 6 — Frontend UI

### Task 15: Update `_StatusBanner` for `awaitingVeoApproval`

**Files:**
- Modify: `lib/screens/run_detail_screen.dart` (`_StatusBanner` switch around line 420)

- [ ] **Step 1: Add the case**

In the `_StatusBanner.build` switch statement, add after `awaitingApproval`:

```dart
RunStatus.awaitingVeoApproval => (
    'Character sheet ready — review before Veo spend',
    Icons.image_outlined,
    Colors.orange,
  ),
```

- [ ] **Step 2: Verify analyze**

Run: `flutter analyze`
Expected: no new errors.

- [ ] **Step 3: Commit**

```bash
git add lib/screens/run_detail_screen.dart
git commit -m "feat(flutter): status banner copy for awaitingVeoApproval"
```

---

### Task 16: Add character-sheet preview panel + wire approval bar to approve-veo

**Files:**
- Modify: `lib/screens/run_detail_screen.dart` (`_body()` around line 384, `_ApprovalBar` and `_approve` method)

- [ ] **Step 1: Add a separate `_approveVeo` method**

In `_RunDetailScreenState`, add (mirroring `_approve` at line 71):

```dart
Future<void> _approveVeo() async {
  if (_busy) return;
  setState(() => _busy = true);
  final messenger = ScaffoldMessenger.of(context);
  messenger.showSnackBar(const SnackBar(
    content: Text('Approved — starting Veo generation…'),
    duration: Duration(seconds: 4),
  ));
  try {
    await widget.client.approveVeoRun(widget.runId);
    await _refresh();
  } catch (e) {
    if (mounted) {
      messenger.showSnackBar(SnackBar(content: Text('Approve failed: $e')));
      setState(() => _busy = false);
    }
    return;
  }
  if (mounted) setState(() => _busy = false);
}
```

- [ ] **Step 2: Add a `_rerollCharacterSheet` method**

```dart
Future<void> _rerollCharacterSheet() async {
  if (_busy) return;
  final yes = await showDialog<bool>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: const Text('Reroll character sheet?'),
      content: const Text(
        'This deletes the current character sheet and regenerates it on Flux. '
        'Costs another \$0.05.',
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(ctx, false),
                   child: const Text('Keep')),
        FilledButton(onPressed: () => Navigator.pop(ctx, true),
                     child: const Text('Reroll (\$0.05)')),
      ],
    ),
  );
  if (yes != true || !mounted) return;
  setState(() => _busy = true);
  try {
    await widget.client.rerollCharacterSheet(widget.runId);
    await _refresh();
  } catch (e) {
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Reroll failed: $e')),
      );
    }
  } finally {
    if (mounted) setState(() => _busy = false);
  }
}
```

- [ ] **Step 3: Render the character-sheet preview when in `awaitingVeoApproval`**

In `_body()`'s ListView children list, immediately above the `_script != null` branch (around line 374), add:

```dart
if (run.isAwaitingVeoApproval) ...[
  const SizedBox(height: 16),
  _CharacterSheetPanel(
    runId: run.id,
    client: widget.client,
    onReroll: _busy ? null : _rerollCharacterSheet,
  ),
],
```

- [ ] **Step 4: Update the approval bar conditional**

In `_body()` around line 384, change:

```dart
if (run.isAwaitingApproval) ...[
  const SizedBox(height: 16),
  _ApprovalBar(
    busy: _busy,
    cost: _script?.estimatedCostUsd ?? 0,
    onApprove: _approve,
    onEdit: _editScript,
    onCancel: _cancelAndDelete,
  ),
],
```

to:

```dart
if (run.isAwaitingApproval || run.isAwaitingVeoApproval) ...[
  const SizedBox(height: 16),
  _ApprovalBar(
    busy: _busy,
    // For the Veo gate, show only the Veo cost (Flux already spent)
    cost: run.isAwaitingVeoApproval
        ? (_script?.estimatedCostUsd ?? 0) - 0.05
        : (_script?.estimatedCostUsd ?? 0),
    isVeoGate: run.isAwaitingVeoApproval,
    onApprove: run.isAwaitingVeoApproval ? _approveVeo : _approve,
    onEdit: _editScript,
    onCancel: _cancelAndDelete,
  ),
],
```

- [ ] **Step 5: Update `_ApprovalBar` to know about the Veo gate**

In `_ApprovalBar` (around line 575), add `final bool isVeoGate;` field, update the constructor, and change the headline:

```dart
Text(
  isVeoGate
    ? 'Approve to start Veo generation (~\$${cost.toStringAsFixed(2)})'
    : 'Approve to render character sheet on Flux (~\$0.05) — '
      'Veo cost (~\$${cost.toStringAsFixed(2)}) confirmed at next step',
  style: const TextStyle(fontWeight: FontWeight.w600),
),
```

(If you want the original "Approve to start Veo" copy on the first gate too, keep it simple. The version above is more accurate but optional.)

- [ ] **Step 6: Add `_CharacterSheetPanel` widget**

At the end of `lib/screens/run_detail_screen.dart`, add:

```dart
class _CharacterSheetPanel extends StatelessWidget {
  final String runId;
  final FacelessApiClient client;
  final VoidCallback? onReroll;
  const _CharacterSheetPanel({
    required this.runId,
    required this.client,
    required this.onReroll,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      color: FacelessTheme.surface2,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Character sheet (Flux)',
                style: TextStyle(
                    color: FacelessTheme.textSecondary,
                    fontWeight: FontWeight.w700,
                    fontSize: 12,
                    letterSpacing: 1.2)),
            const SizedBox(height: 8),
            ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: CachedNetworkImage(
                imageUrl: client.thumbnailUrl(runId),
                fit: BoxFit.contain,
                httpHeaders: client.authHeaders,
                errorWidget: (_, __, ___) => const SizedBox(
                  height: 200,
                  child: Center(child: Icon(Icons.broken_image)),
                ),
                placeholder: (_, __) => const SizedBox(
                  height: 200,
                  child: Center(child: CircularProgressIndicator()),
                ),
              ),
            ),
            const SizedBox(height: 8),
            OutlinedButton.icon(
              onPressed: onReroll,
              icon: const Icon(Icons.refresh),
              label: const Text('Reroll character sheet (\$0.05)'),
            ),
          ],
        ),
      ),
    );
  }
}
```

(`client.thumbnailUrl` and `client.authHeaders` may be named slightly differently — check `client.dart` for the existing accessor.)

- [ ] **Step 7: Verify analyze + manual run**

```bash
flutter analyze
```

Then start the app (`./scripts/run-app.sh`) against a real run dir that's been hand-placed in `awaiting_veo_approval` (or trigger the path by running an actual script-approve cycle).

- [ ] **Step 8: Commit**

```bash
git add lib/screens/run_detail_screen.dart
git commit -m "feat(flutter): Veo approval gate UI with character-sheet preview"
```

---

### Task 17: Build the AI Freeform tab

**Files:**
- Modify: `lib/screens/new_run_screen.dart`

- [ ] **Step 1: Increase the TabController length to 3 and add the new tab**

Change `length: 2` to `length: 3` and update the `tabs:` list:

```dart
tabs: [
  Tab(icon: Icon(Icons.auto_awesome), text: 'AI Write'),
  Tab(icon: Icon(Icons.tune), text: 'AI Freeform'),
  Tab(icon: Icon(Icons.edit_note), text: 'Paste Script'),
],
```

And update `TabBarView`:

```dart
children: [
  _AiWriteTab(client: client),
  _AiFreeformTab(client: client),
  _PasteScriptTab(client: client),
],
```

- [ ] **Step 2: Add `_AiFreeformTab` widget**

At the bottom of `lib/screens/new_run_screen.dart`, add a new widget:

```dart
class _AiFreeformTab extends StatefulWidget {
  final FacelessApiClient client;
  const _AiFreeformTab({required this.client});
  @override
  State<_AiFreeformTab> createState() => _AiFreeformTabState();
}

class _AiFreeformTabState extends State<_AiFreeformTab> {
  String _theme = 'folkloric';
  String _dialect = 'msa';
  String _artStyle = 'cinematic_photo_real';
  String _characterTemplate = 'ai_choose';
  String _endingType = 'ai_choose';
  int _numBeats = 8;
  int _perBeatSeconds = 8;
  final _premiseCtrl = TextEditingController();
  bool _submitting = false;
  String? _error;

  static const _dialects = [
    ('msa', 'MSA (الفصحى)'),
    ('syrian', 'Syrian / Levantine'),
    ('egyptian', 'Egyptian'),
    ('khaliji', 'Khaliji / Gulf'),
    ('maghrebi', 'Maghrebi'),
    ('iraqi', 'Iraqi'),
  ];
  static const _artStyles = [
    ('pixar_3d', '3D Pixar'),
    ('anime_2d', '2D Anime'),
    ('cinematic_photo_real', 'Cinematic photo-real'),
    ('claymation', 'Claymation'),
    ('hand_drawn', 'Hand-drawn'),
    ('ghibli', 'Studio Ghibli'),
  ];
  static const _characterTemplates = [
    ('ai_choose', 'Let the AI choose'),
    ('human', 'Human cast'),
    ('fruit_sunstoriz', 'Fruit cast (Sunstoriz)'),
    ('animal', 'Animal cast'),
    ('surreal', 'Surreal creatures'),
  ];
  static const _endingTypes = [
    ('ai_choose', 'Let the AI choose'),
    ('open', 'Open-ended'),
    ('closed_tragic', 'Closed tragic'),
    ('closed_happy', 'Closed happy'),
    ('twist', 'Twist'),
  ];

  Future<void> _submit() async {
    final premise = _premiseCtrl.text.trim();
    if (premise.length < 4) {
      setState(() => _error = 'Premise too short');
      return;
    }
    setState(() { _submitting = true; _error = null; });
    try {
      final run = await widget.client.createFreeformRun(
        theme: _theme,
        premise: premise,
        dialect: _dialect,
        artStyle: _artStyle,
        characterTemplate: _characterTemplate,
        endingType: _endingType,
        numBeats: _numBeats,
        perBeatSeconds: _perBeatSeconds,
      );
      if (!mounted) return;
      Navigator.of(context).pop<RunSummary?>(run);
    } catch (e) {
      setState(() { _error = e.toString(); _submitting = false; });
    }
  }

  Widget _kvDropdown<T>({
    required String label,
    required T value,
    required List<(T, String)> items,
    required ValueChanged<T?> onChanged,
  }) =>
      DropdownButtonFormField<T>(
        initialValue: value,
        decoration: InputDecoration(
            labelText: label, border: const OutlineInputBorder()),
        items: items
            .map((p) => DropdownMenuItem<T>(value: p.$1, child: Text(p.$2)))
            .toList(),
        onChanged: onChanged,
      );

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Card(
            color: FacelessTheme.surface2,
            child: const Padding(
              padding: EdgeInsets.all(16),
              child: Text(
                'Freeform AI: the script writer follows YOUR premise '
                'instead of any fixed character/dialect template.',
              ),
            ),
          ),
          const SizedBox(height: 16),
          TextField(
            controller: _premiseCtrl,
            decoration: const InputDecoration(
              labelText: 'Premise (Arabic)',
              border: OutlineInputBorder(),
              alignLabelWithHint: true,
            ),
            textDirection: TextDirection.rtl,
            maxLines: 4,
          ),
          const SizedBox(height: 12),
          _kvDropdown<String>(
            label: 'Theme',
            value: _theme,
            items: _themes.map((t) => (t, t)).toList(),
            onChanged: (v) => setState(() => _theme = v ?? 'folkloric'),
          ),
          const SizedBox(height: 12),
          _kvDropdown<String>(
            label: 'Dialect',
            value: _dialect,
            items: _dialects,
            onChanged: (v) => setState(() => _dialect = v ?? 'msa'),
          ),
          const SizedBox(height: 12),
          _kvDropdown<String>(
            label: 'Art style',
            value: _artStyle,
            items: _artStyles,
            onChanged: (v) =>
                setState(() => _artStyle = v ?? 'cinematic_photo_real'),
          ),
          const SizedBox(height: 12),
          _kvDropdown<String>(
            label: 'Character template',
            value: _characterTemplate,
            items: _characterTemplates,
            onChanged: (v) =>
                setState(() => _characterTemplate = v ?? 'ai_choose'),
          ),
          const SizedBox(height: 12),
          _kvDropdown<String>(
            label: 'Ending type',
            value: _endingType,
            items: _endingTypes,
            onChanged: (v) =>
                setState(() => _endingType = v ?? 'ai_choose'),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              const Text('Beats:'),
              Expanded(
                child: Slider(
                  min: 4, max: 15, divisions: 11,
                  value: _numBeats.toDouble(),
                  label: '$_numBeats',
                  onChanged: (v) => setState(() => _numBeats = v.round()),
                ),
              ),
              Text('$_numBeats'),
            ],
          ),
          Row(
            children: [
              const Text('Sec / beat:'),
              Expanded(
                child: Slider(
                  min: 4, max: 10, divisions: 6,
                  value: _perBeatSeconds.toDouble(),
                  label: '${_perBeatSeconds}s',
                  onChanged: (v) =>
                      setState(() => _perBeatSeconds = v.round()),
                ),
              ),
              Text('${_perBeatSeconds}s'),
            ],
          ),
          const SizedBox(height: 16),
          if (_error != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Text(_error!,
                  style: TextStyle(
                      color: Theme.of(context).colorScheme.error)),
            ),
          FilledButton.icon(
            onPressed: _submitting ? null : _submit,
            icon: _submitting
                ? const SizedBox(
                    width: 16, height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2))
                : const Icon(Icons.tune),
            label: Text(_submitting ? 'Writing…' : 'Generate Script'),
          ),
        ],
      ),
    );
  }

  @override
  void dispose() {
    _premiseCtrl.dispose();
    super.dispose();
  }
}
```

- [ ] **Step 3: Verify analyze + smoke**

```bash
flutter analyze
./scripts/run-app.sh
```

Tap into the new "AI Freeform" tab, fill in the fields, and submit. Verify a new run lands in `awaiting_approval` with the expected dialect / art style applied.

- [ ] **Step 4: Commit**

```bash
git add lib/screens/new_run_screen.dart
git commit -m "feat(flutter): AI Freeform tab on new-run screen"
```

---

### Task 18: Add target_beats slider + parse_method badge to Paste Script tab

**Files:**
- Modify: `lib/screens/new_run_screen.dart` (`_PasteScriptTab` state + `_MarkdownPasteDialog`)

- [ ] **Step 1: Add `targetBeats` field to `_MarkdownPasteDialog`**

In `_MarkdownPasteDialogState`, add:

```dart
int _targetBeats = 8;
```

Above the existing parse button, add a slider:

```dart
Row(
  children: [
    const Text('Target beats:'),
    Expanded(
      child: Slider(
        min: 4, max: 15, divisions: 11,
        value: _targetBeats.toDouble(),
        label: '$_targetBeats',
        onChanged: (v) => setState(() => _targetBeats = v.round()),
      ),
    ),
    Text('$_targetBeats'),
  ],
),
const SizedBox(height: 8),
```

- [ ] **Step 2: Pass `targetBeats` to `parseScript`**

In `_parse()`, change:

```dart
final result = await widget.client.parseScript(raw);
```

to:

```dart
final result = await widget.client.parseScript(raw, targetBeats: _targetBeats);
```

(`parseScript` now returns `ParseScriptResponse`. Update the `Navigator.pop` call to return the typed object directly, and update `_PasteScriptTabState._openMarkdownPaster` accordingly — instead of reading `parsed['title']` / `parsed['beats']` from a dynamic map, use `result.title` / `result.beats`.)

- [ ] **Step 3: Surface `parse_method` as a badge**

In `_PasteScriptTabState._openMarkdownPaster`, after replacing `_beats`, also remember the method:

```dart
String? _lastParseMethod;
```

Set it from the response:

```dart
_lastParseMethod = switch (result.parseMethod) {
  ParseMethod.regex => 'parsed from your markdown',
  ParseMethod.llmSplit => 'split by AI — review',
  ParseMethod.naiveFallback => 'auto-segmented — review carefully',
};
```

In the `build` method's snackbar, change the existing message to include the method, and additionally render a small badge above the `Beats` heading when `_lastParseMethod` is non-null.

- [ ] **Step 4: Verify analyze + smoke**

```bash
flutter analyze
./scripts/run-app.sh
```

Paste a freeform Arabic story (no markdown) into the dialog, verify it splits into multiple beats and shows the AI-split badge.

- [ ] **Step 5: Commit**

```bash
git add lib/screens/new_run_screen.dart
git commit -m "feat(flutter): target_beats slider + parse_method badge in paste-script"
```

---

### Task 19: Extend `VideoPlayerScreen` to accept `clipIndex`

**Files:**
- Modify: `lib/screens/video_player_screen.dart`

- [ ] **Step 1: Add the param**

Update the constructor:

```dart
class VideoPlayerScreen extends StatefulWidget {
  final FacelessApiClient client;
  final String runId;
  final String? title;
  final int? clipIndex;   // NEW: when non-null, plays a single clip
  const VideoPlayerScreen({
    super.key,
    required this.client,
    required this.runId,
    this.title,
    this.clipIndex,
  });
```

- [ ] **Step 2: Use the right URL**

In `initState` (or wherever the URL is built), branch:

```dart
final url = widget.clipIndex == null
  ? widget.client.videoUrl(widget.runId)
  : widget.client.clipVideoUrl(widget.runId, widget.clipIndex!);
```

And update the AppBar title:

```dart
title: Text(
  widget.clipIndex == null
    ? (widget.title ?? widget.runId)
    : 'Clip ${widget.clipIndex!.toString().padLeft(2, "0")}'
      '${widget.title != null ? " — ${widget.title}" : ""}',
),
```

- [ ] **Step 3: Verify analyze**

```bash
flutter analyze
```

- [ ] **Step 4: Commit**

```bash
git add lib/screens/video_player_screen.dart
git commit -m "feat(flutter): VideoPlayerScreen optional clipIndex param"
```

---

### Task 20: Wire `_BeatTile` to tap-to-play + per-clip reroll

**Files:**
- Modify: `lib/screens/run_detail_screen.dart` (`_BeatTile` around line 500)

- [ ] **Step 1: Make the thumbnail tappable**

In `_BeatTile.build`, wrap the existing `_ClipThumbBox(...)` in an `InkWell`:

```dart
InkWell(
  onTap: hasClip
      ? () => Navigator.of(context).push(
            MaterialPageRoute(
              builder: (_) => VideoPlayerScreen(
                client: _clientOf(context),
                runId: runId,
                clipIndex: index,
                title: beat.speaker,
              ),
            ),
          )
      : null,
  borderRadius: BorderRadius.circular(8),
  child: _ClipThumbBox(runId: runId, clipIndex: index, hasClip: hasClip),
),
```

`_clientOf(context)` is a helper — easiest path: add a `final FacelessApiClient client;` field to `_BeatTile` and thread it down from `_ScriptPanel`. Alternatively, hoist the tap handler up to `_RunDetailScreenState` so it can access `widget.client` directly. Either is fine; pick the smallest diff.

- [ ] **Step 2: Add a per-clip reroll icon button**

After the speaker label `Text(beat.speaker, ...)` inside the beat tile (around line 543), add:

```dart
if (hasClip) ...[
  const SizedBox(width: 4),
  IconButton(
    icon: const Icon(Icons.refresh, size: 18),
    tooltip: 'Reroll this clip (~\$0.85)',
    onPressed: () => _confirmAndRerollSingle(context, index),
    visualDensity: VisualDensity.compact,
  ),
],
```

- [ ] **Step 3: Add `_confirmAndRerollSingle`**

In the same widget (or hoisted into `_RunDetailScreenState`), add:

```dart
Future<void> _confirmAndRerollSingle(BuildContext context, int clipIndex) async {
  final yes = await showDialog<bool>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: Text('Reroll clip ${clipIndex.toString().padLeft(2, "0")}?'),
      content: const Text('This regenerates one clip on Veo. ~\$0.85.'),
      actions: [
        TextButton(onPressed: () => Navigator.pop(ctx, false),
                   child: const Text('Keep')),
        FilledButton(onPressed: () => Navigator.pop(ctx, true),
                     child: const Text('Reroll (\$0.85)')),
      ],
    ),
  );
  if (yes != true) return;
  // ... thread back up to the parent state; the existing `rerollClips`
  //     method on the client already supports a single-element list.
}
```

The cleanest threading pattern: add a `final ValueChanged<int> onRerollSingle;` callback to `_BeatTile` / `_ScriptPanel`, set it from `_RunDetailScreenState` to a method that calls `widget.client.rerollClips(widget.runId, [clipIndex])` and then `_refresh()`.

- [ ] **Step 4: Verify analyze + manual run**

```bash
flutter analyze
./scripts/run-app.sh
```

Open a complete run, tap a beat thumbnail → fullscreen player loads that clip's mp4. Tap the reroll icon → confirmation dialog appears showing $0.85 → on confirm, the run flips back to `running_paid` and that one clip rerenders.

- [ ] **Step 5: Commit**

```bash
git add lib/screens/run_detail_screen.dart
git commit -m "feat(flutter): per-beat tap-to-play + single-clip reroll button"
```

---

## Final integration check

After all 20 tasks land:

- [ ] Run the full backend test suite:

```bash
uv run pytest -v
```

Expected: all green.

- [ ] Run `flutter analyze`:

```bash
flutter analyze
```

Expected: no new errors (pre-existing `lib/main.dart:31` / `:105` issues noted in CLAUDE.md may remain if not fixed separately).

- [ ] End-to-end smoke (with real API keys, costs ~$1):
  - Launch the app: `./scripts/run-app.sh`
  - **AI Write tab** — submit any premise; verify the run pauses at `awaiting_approval`, then after approve it pauses again at `awaiting_veo_approval` (NEW gate), shows the character-sheet image, lets you edit beats, and finally completes.
  - **AI Freeform tab** — submit a non-Sunstoriz premise (e.g. "a photographer in Cairo" with `dialect=egyptian`, `character_template=human`); verify the resulting script is in Egyptian dialect with human characters.
  - **Paste Script tab** — paste freeform Arabic prose (no markdown structure) with `target_beats=6`; verify it splits into 6 beats with the "split by AI — review" badge.
  - **Per-clip playback** — on a complete run, tap any beat thumbnail; verify the fullscreen player loads that one clip. Tap reroll; verify the $0.85 dialog and the clip rerenders.

- [ ] **Final commit (if any cleanup):**

```bash
git status   # nothing pending after all per-task commits, ideally
```

---

## Spec coverage check (self-review)

Quick map from spec sections to tasks — confirms nothing is missing:

| Spec section | Tasks |
|---|---|
| §1 Freeform AI mode (backend module) | Task 10 |
| §1 `--freeform` CLI flag | Task 11 |
| §1 `POST /runs/freeform` | Task 12 |
| §1 AI Freeform tab | Task 17 |
| §2 Hybrid parser (`script_splitter.py`) | Task 8 |
| §2 `/runs/parse-script` hybrid path | Task 9 |
| §2 target_beats slider + parse_method badge | Task 18 |
| §3 `--pause-after-character-sheet` flag | Task 1 |
| §3 `awaiting_veo_approval` status branch | Task 2 |
| §3 `/approve` adds new pause flag | Task 3 |
| §3 `POST /runs/{id}/approve-veo` | Task 4 |
| §3 `PUT /runs/{id}/script` loosened | Task 5 |
| §3 `POST /runs/{id}/character-sheet/reroll` | Task 6 |
| §3 `RunStatus.awaitingVeoApproval` enum | Task 13 |
| §3 New client methods (approveVeoRun, sheet reroll) | Task 14 |
| §3 Status banner copy | Task 15 |
| §3 Character-sheet preview panel + approval-bar wiring | Task 16 |
| §4 `GET /runs/{id}/clips/{i}/video` | Task 7 |
| §4 `clipVideoUrl` client helper | Task 14 |
| §4 `VideoPlayerScreen` clipIndex param | Task 19 |
| §4 `_BeatTile` tap-to-play + per-clip reroll | Task 20 |

Every spec requirement maps to at least one task. The freeform mode (§1) does not require a "freeform writes character sheet differently" task — the existing Flux character-sheet stage runs unchanged for freeform runs, since the script JSON shape is identical.
