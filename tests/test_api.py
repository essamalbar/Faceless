"""FastAPI backend tests. The pipeline subprocess is mocked — _SPAWN_FN is
replaced with a closure that creates whatever fake artifacts each scenario
needs (script.json after create_run, final.mp4 after approve, etc.).

We never actually run run.py, so these tests are fast and free."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def api_token() -> str:
    return "test-token-abc"


@pytest.fixture
def client(monkeypatch, tmp_path: Path, api_token: str):
    """A TestClient with FACELESS_API_TOKEN + FACELESS_OUT_ROOT pointing at tmp."""
    monkeypatch.setenv("FACELESS_API_TOKEN", api_token)
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path / "out"))

    # Reload the api module so it re-reads env vars / out root via _out_root().
    # (Our module reads env at request time, so this works without reload.)
    from pipeline import api as api_mod
    # Default: _spawn does nothing — the test scripts that need to fake
    # specific artifacts will replace this per-test via api_mod.set_spawn_fn.
    api_mod.set_spawn_fn(lambda args, run_dir: 999999)
    return TestClient(api_mod.app)


@pytest.fixture
def auth(api_token: str) -> dict:
    return {"Authorization": f"Bearer {api_token}"}


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def test_healthz_no_auth_required(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_protected_endpoint_requires_authorization_header(client):
    r = client.get("/runs")
    assert r.status_code == 401
    assert "Authorization" in r.json()["detail"]


def test_protected_endpoint_rejects_wrong_token(client):
    r = client.get("/runs", headers={"Authorization": "Bearer wrong"})
    # /runs is now guarded by require_user (T3); it treats an invalid
    # bearer as 401 Unauthorized rather than 403 Forbidden.
    assert r.status_code == 401


def test_protected_endpoint_rejects_non_bearer_scheme(client):
    r = client.get("/runs", headers={"Authorization": "Basic Zm9vOmJhcg=="})
    assert r.status_code == 401


def test_returns_503_when_token_not_configured(monkeypatch, tmp_path: Path):
    """If the operator forgot to set FACELESS_API_TOKEN, the API refuses
    every authenticated call rather than letting anyone in."""
    monkeypatch.delenv("FACELESS_API_TOKEN", raising=False)
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path / "out"))
    from pipeline import api as api_mod
    c = TestClient(api_mod.app)
    r = c.get("/runs", headers={"Authorization": "Bearer anything"})
    assert r.status_code == 503


# ---------------------------------------------------------------------------
# POST /runs — start a new pipeline (paused after script)
# ---------------------------------------------------------------------------

def test_create_run_rejects_unknown_theme(client, auth):
    r = client.post("/runs", json={"theme": "foo", "premise": "x x x x"}, headers=auth)
    assert r.status_code == 400
    assert "theme" in r.json()["detail"]


def test_create_run_rejects_short_premise(client, auth):
    r = client.post("/runs", json={"theme": "folkloric", "premise": "ab"}, headers=auth)
    assert r.status_code == 422


def test_create_run_generates_script_inline_returns_awaiting_approval(
    client, auth, tmp_path: Path,
):
    """POST /runs now generates the script SYNCHRONOUSLY (inline LLM call)
    instead of spawning a Cloud Run Job with --pause-after-script. The
    response should already say `awaiting_approval` and `script.json` should
    be on disk by the time we return."""
    r = client.post("/runs",
                    json={"theme": "folkloric", "premise": "أم سورية فقيرة من الشام"},
                    headers=auth)
    assert r.status_code == 201
    body = r.json()
    assert body["theme"] == "folkloric"
    assert body["premise"].startswith("أم سورية")
    assert body["status"] == "awaiting_approval"

    # The autouse _auto_mock_inline_script_gen fixture wrote a fake script.json
    # under the admin (service-token) user. Confirm the path layout.
    run_dir = tmp_path / "out" / "admin" / body["id"]
    assert (run_dir / "script.json").exists()
    assert (run_dir / "seed.json").exists()


TOKEN = "test-token-abc"


def test_post_runs_proxies_to_freeform(tmp_path, client, monkeypatch):
    """PA-3: POST /runs writes Sunstoriz-style defaults into freeform_controls.json
    (character_template=fruit_sunstoriz + narration_style=first_person_monologue
    + dialect=syrian) before generating the script. The script writer reads
    those controls; we verify them via the persisted JSON file."""
    # `client` fixture already sets FACELESS_OUT_ROOT=tmp_path/out — keep that.
    resp = client.post(
        "/runs",
        json={"theme": "folkloric", "premise": "أم سورية فقدت ابنها"},
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    controls = json.loads(
        (tmp_path / "out" / "admin" / body["id"] / "freeform_controls.json")
        .read_text(encoding="utf-8")
    )
    assert controls["character_template"] == "fruit_sunstoriz"
    assert controls["narration_style"] == "first_person_monologue"
    assert controls["dialect"] == "syrian"


def test_parse_script_endpoint_returns_structured_beats(client, auth):
    """The HTTP path of /runs/parse-script. Unit tests in test_script_parser.py
    cover the parser itself; this test verifies the endpoint wires it up,
    enforces auth, and returns the expected JSON shape."""
    body = {
        "raw_text":
            "**Title: Test EP**\n\n"
            "**Scene 1 – Opening**\n\n"
            "Stage direction: mother stands at door.\n\n"
            "**Mother:**\n"
            "\"Be careful, my son.\"\n\n"
            "**Son:**\n"
            "\"I'll be back.\"\n",
    }
    r = client.post("/runs/parse-script", json=body, headers=auth)
    assert r.status_code == 200
    data = r.json()
    assert data["title"] == "Test EP"
    assert len(data["beats"]) == 2
    assert [b["speaker"] for b in data["beats"]] == ["mother", "son"]
    assert data["beats"][0]["arabic"] == "Be careful, my son."
    # Per-beat stage direction included in english_motion
    assert "Scene 1" in data["beats"][0]["english_motion"]


def test_parse_script_endpoint_requires_auth(client):
    r = client.post("/runs/parse-script", json={"raw_text": "x" * 50})
    assert r.status_code == 401


def test_parse_script_endpoint_rejects_too_short_text(client, auth):
    """Pydantic min_length=4 — the empty / too-short body returns 422."""
    r = client.post("/runs/parse-script", json={"raw_text": "x"}, headers=auth)
    assert r.status_code == 422


def test_parse_script_regex_path(client, auth):
    """Structured markdown still uses regex (parse_method=regex)."""
    raw = (
        "**العنوان: Episode 1**\n\n"
        "**المشهد 1 – Opening**\n\n"
        '**الأم:**\n"كلام الأم"\n\n'
        '**الابن:**\n"كلام الابن"\n'
    )
    resp = client.post(
        "/runs/parse-script",
        json={"raw_text": raw},
        headers=auth,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["parse_method"] == "regex"
    assert len(body["beats"]) >= 2


def test_parse_script_llm_fallback(client, auth, monkeypatch):
    """Freeform prose with no dialogue markers → llm_split."""
    from pipeline import api as api_mod
    raw = "أنا قاعدة بالمطبخ. ابني نسي. قلبي مكسور."
    fake_response = (
        '{"beats":['
        '{"arabic":"أنا قاعدة بالمطبخ.","english_motion":"x","speaker":"mother","clip_duration_s":7},'
        '{"arabic":"ابني نسي.","english_motion":"y","speaker":"son","clip_duration_s":7},'
        '{"arabic":"قلبي مكسور.","english_motion":"z","speaker":"mother","clip_duration_s":7}'
        ']}'
    )

    class _Stub:
        def complete(self, prompt, system=""):
            return fake_response

    monkeypatch.setattr(api_mod, "_get_splitter_llm", lambda: _Stub())

    resp = client.post(
        "/runs/parse-script",
        json={"raw_text": raw, "target_beats": 4},
        headers=auth,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["parse_method"] == "llm_split"
    assert len(body["beats"]) == 3


def test_parse_script_llm_populates_character_name(client, auth, monkeypatch):
    """When the LLM splitter returns character_name, /parse-script propagates it."""
    from pipeline import api as api_mod
    raw = "أنا قاعدة بالمطبخ. ابني نسي. قلبي مكسور. هذا الفقد لا يطاق."
    fake_response = (
        '{"beats":['
        '{"arabic":"أنا قاعدة بالمطبخ.","english_motion":"x","speaker":"mother","clip_duration_s":7,"character_name":"أم خالد"},'
        '{"arabic":"ابني نسي.","english_motion":"y","speaker":"son","clip_duration_s":7,"character_name":"خالد"},'
        '{"arabic":"قلبي مكسور.","english_motion":"z","speaker":"mother","clip_duration_s":7,"character_name":"أم خالد"},'
        '{"arabic":"هذا الفقد لا يطاق.","english_motion":"w","speaker":"mother","clip_duration_s":7,"character_name":"أم خالد"}'
        ']}'
    )
    class _Stub:
        def complete(self, prompt, system=""): return fake_response
    monkeypatch.setattr(api_mod, "_get_splitter_llm", lambda: _Stub())
    resp = client.post("/runs/parse-script",
                       json={"raw_text": raw, "target_beats": 4},
                       headers=auth)
    assert resp.status_code == 200
    body = resp.json()
    assert body["parse_method"] == "llm_split"
    assert body["beats"][0]["character_name"] == "أم خالد"
    assert body["beats"][1]["character_name"] == "خالد"


def test_run_id_path_traversal_blocked(client, auth, tmp_path: Path):
    """Strict allowlist: only [A-Za-z0-9_-]+ accepted. ../ and absolute paths
    must 400, not let the request reach the filesystem."""
    for evil in ["../etc", "..%2Fetc", "/etc/passwd", "abc/../def",
                 "abc def", "abc.def", "abc;rm"]:
        r = client.get(f"/runs/{evil}", headers=auth)
        # FastAPI may convert some sequences before our handler sees them,
        # so 400 (our handler), 404 (not found), and 405 are all acceptable;
        # 200 would be a security failure.
        assert r.status_code in (400, 404, 405), \
            f"path traversal {evil!r} returned {r.status_code}"


def test_create_from_script_writes_script_and_seed_no_llm(client, auth, tmp_path: Path):
    """Critical fix: when the user already has the dialogue, they post the
    full script and the API writes script.json + seed.json verbatim. NO
    spawning of run.py — the LLM never runs and never rewrites their text."""
    from pipeline import api as api_mod
    spawned: list = []
    api_mod.set_spawn_fn(
        lambda args, run_dir: spawned.append(args) or 1,
    )

    body = {
        "title": "العقد المقدس - الحلقة 4",
        "theme": "folkloric",
        "premise": "الحلقة الرابعة من سلسلة العقد",
        "music_mood": "dread",
        "beats": [
            {"arabic": "هذا هو السطر الذي كتبتُه أنا حرفياً، لا يجب تغييره",
             "english_motion": "Strawberry son in his home, golden necklace at chest",
             "speaker": "son",
             "clip_duration_s": 9.0},
            {"arabic": "الأم تردُ على ابنها بحب",
             "english_motion": "Lemon mother facing camera, soft warm light",
             "speaker": "mother",
             "clip_duration_s": 8.0},
        ],
    }
    r = client.post("/runs/from-script", json=body, headers=auth)
    assert r.status_code == 201
    body_out = r.json()
    assert body_out["status"] == "awaiting_approval"
    assert body_out["title"] == "العقد المقدس - الحلقة 4"
    # NO subprocess spawned — the LLM never ran
    assert spawned == []

    # Files on disk match input verbatim — scoped under the admin user
    out_root = Path(api_mod._out_root()) / "admin"  # service token → admin
    rd = out_root / body_out["id"]
    seed = json.loads((rd / "seed.json").read_text(encoding="utf-8"))
    assert seed["theme"] == "folkloric"
    script = json.loads((rd / "script.json").read_text(encoding="utf-8"))
    assert script["title"] == "العقد المقدس - الحلقة 4"
    assert len(script["beats"]) == 2
    assert script["beats"][0]["arabic"].startswith("هذا هو السطر")
    assert script["beats"][0]["speaker"] == "son"
    assert script["target_duration_s"] == 17.0


def test_create_from_script_rejects_empty_speaker(client, auth):
    """PA-1: empty speaker is rejected; 'narrator' and any other non-empty value are now valid."""
    body = {
        "title": "x",
        "theme": "folkloric",
        "beats": [{"arabic": "ج", "english_motion": "m",
                   "speaker": "",  # empty → forbidden
                   "clip_duration_s": 8.0}],
    }
    r = client.post("/runs/from-script", json=body, headers=auth)
    assert r.status_code == 400
    assert "speaker" in r.json()["detail"]


def test_create_from_script_rejects_unknown_theme(client, auth):
    body = {
        "title": "x",
        "theme": "scifi",
        "beats": [{"arabic": "ج", "english_motion": "m",
                   "speaker": "mother", "clip_duration_s": 8.0}],
    }
    r = client.post("/runs/from-script", json=body, headers=auth)
    assert r.status_code == 400


def test_create_from_script_rejects_empty_beats(client, auth):
    body = {"title": "x", "theme": "folkloric", "beats": []}
    r = client.post("/runs/from-script", json=body, headers=auth)
    assert r.status_code == 422  # pydantic min_length=1


def test_create_run_passes_max_beats(client, auth, tmp_path: Path):
    """PA-3: max_beats on CreateRunRequest now maps to num_beats in
    freeform_controls.json (which the inline script generator reads)."""
    resp = client.post(
        "/runs",
        json={"theme": "folkloric", "premise": "تجربة قصيرة جداً", "max_beats": 3},
        headers=auth,
    )
    assert resp.status_code == 201
    body = resp.json()
    controls = json.loads(
        (tmp_path / "out" / "admin" / body["id"] / "freeform_controls.json")
        .read_text(encoding="utf-8")
    )
    assert controls["num_beats"] == 3


# ---------------------------------------------------------------------------
# Status derivation
# ---------------------------------------------------------------------------

def _make_run_dir(tmp_path: Path, run_id: str = "2026-05-05-r1") -> Path:
    p = tmp_path / "out" / "admin" / run_id
    p.mkdir(parents=True)
    return p


def test_status_creating_when_no_script_yet(client, auth, tmp_path: Path):
    rd = _make_run_dir(tmp_path)
    # No process tracked → "failed" because no script and no pid
    r = client.get(f"/runs/{rd.name}", headers=auth)
    assert r.status_code == 200
    assert r.json()["status"] == "failed"


def test_status_awaiting_approval_when_script_only(client, auth, tmp_path: Path):
    rd = _make_run_dir(tmp_path)
    (rd / "script.json").write_text(json.dumps({
        "title": "x", "theme": "folkloric", "global_setting": "g",
        "music_mood": "dread", "beats": [],
    }))
    r = client.get(f"/runs/{rd.name}", headers=auth)
    assert r.json()["status"] == "awaiting_approval"


def test_status_complete_when_final_mp4_present(client, auth, tmp_path: Path):
    rd = _make_run_dir(tmp_path)
    (rd / "script.json").write_text("{}")
    (rd / "character_sheet.png").write_bytes(b"png-bytes")
    (rd / "clips").mkdir()
    (rd / "clips" / "01.mp4").write_bytes(b"mp4-bytes")
    (rd / "final.mp4").write_bytes(b"mp4-bytes")
    r = client.get(f"/runs/{rd.name}", headers=auth)
    body = r.json()
    assert body["status"] == "complete"
    assert body["has_video"] is True


def test_get_run_returns_404_for_unknown_id(client, auth):
    r = client.get("/runs/not-a-real-run", headers=auth)
    assert r.status_code == 404


def test_script_pdf_returns_bytes(client, auth, tmp_path: Path):
    """Free-tier export: GET /runs/{id}/script.pdf streams a real PDF.

    This is the differentiator for users on the Free plan — they can
    write a script and walk away with a PDF without ever subscribing.
    No credit charge, no plan check; just bearer auth + the run must
    have a script.json.
    """
    rd = _make_run_dir(tmp_path)
    (rd / "script.json").write_text(json.dumps({
        "title": "بئر السواد",
        "theme": "folkloric",
        "global_setting": "village at dusk",
        "music_mood": "dread",
        "beats": [
            {"arabic": "ليلة باردة جدًا", "speaker": "narrator",
             "clip_duration_s": 8.0, "is_silent": False,
             "english_motion": "wide shot", "character_name": ""},
        ],
    }, ensure_ascii=False))
    r = client.get(f"/runs/{rd.name}/script.pdf", headers=auth)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF-")
    # The on-disk artifact is cached for future requests
    assert (rd / "script.pdf").exists()


def test_script_pdf_returns_409_before_script_exists(client, auth, tmp_path: Path):
    rd = _make_run_dir(tmp_path)
    # No script.json written
    r = client.get(f"/runs/{rd.name}/script.pdf", headers=auth)
    assert r.status_code == 409


def test_get_run_rejects_path_traversal(client, auth):
    r = client.get("/runs/..%2Fetc/passwd", headers=auth)
    # FastAPI's path matching converts %2F so we may get 404 or 400; both are safe
    assert r.status_code in (400, 404)


# ---------------------------------------------------------------------------
# GET /runs — listing
# ---------------------------------------------------------------------------

def test_list_runs_empty_when_no_runs(client, auth):
    r = client.get("/runs", headers=auth)
    assert r.status_code == 200
    assert r.json() == []


def test_list_runs_returns_summaries(client, auth, tmp_path: Path):
    # T3: /runs is scoped per-user. The service-token fixture authenticates
    # as User(id="admin"), so seeds need to live under out/admin/.
    rd1 = tmp_path / "out" / "admin" / "2026-05-05-A"
    rd1.mkdir(parents=True)
    (rd1 / "script.json").write_text(json.dumps({
        "title": "حسرة الأم", "theme": "folkloric",
        "global_setting": "x", "music_mood": "dread",
    }, ensure_ascii=False))
    (rd1 / "seed.json").write_text(json.dumps({
        "theme": "folkloric", "premise": "premise text",
    }, ensure_ascii=False))

    rd2 = tmp_path / "out" / "admin" / "2026-05-05-B"
    rd2.mkdir(parents=True)
    (rd2 / "script.json").write_text("{}")
    (rd2 / "final.mp4").write_bytes(b"x")

    r = client.get("/runs", headers=auth)
    runs = r.json()
    assert len(runs) == 2
    by_id = {x["id"]: x for x in runs}
    assert by_id["2026-05-05-A"]["title"] == "حسرة الأم"
    assert by_id["2026-05-05-A"]["premise"] == "premise text"
    assert by_id["2026-05-05-B"]["has_video"] is True


# ---------------------------------------------------------------------------
# GET /runs/{id}/script
# ---------------------------------------------------------------------------

def test_get_script_returns_409_when_not_yet_generated(client, auth, tmp_path: Path):
    rd = _make_run_dir(tmp_path)
    r = client.get(f"/runs/{rd.name}/script", headers=auth)
    assert r.status_code == 409


def test_get_script_returns_beats_with_cost_estimate(client, auth, tmp_path: Path):
    rd = _make_run_dir(tmp_path)
    (rd / "script.json").write_text(json.dumps({
        "title": "العقد",
        "theme": "folkloric",
        "global_setting": "g",
        "music_mood": "dread",
        "target_duration_s": 24,
        "beats": [
            {"arabic": "أ", "english_motion": "m1",
             "clip_duration_s": 8.0, "speaker": "mother"},
            {"arabic": "ب", "english_motion": "m2",
             "clip_duration_s": 9.0, "speaker": "son"},
            {"arabic": "ج", "english_motion": "m3",
             "clip_duration_s": 7.0, "speaker": "mother"},
        ],
    }, ensure_ascii=False), encoding="utf-8")
    r = client.get(f"/runs/{rd.name}/script", headers=auth)
    body = r.json()
    assert body["title"] == "العقد"
    assert len(body["beats"]) == 3
    assert body["beats"][1]["speaker"] == "son"
    # cost estimate: (8+9+7) × $0.10 + $0.05 Flux = $2.45
    assert body["estimated_cost_usd"] == 2.45


# ---------------------------------------------------------------------------
# POST /runs/{id}/approve
# ---------------------------------------------------------------------------

def test_approve_rejects_when_not_awaiting_approval(client, auth, tmp_path: Path):
    """Cannot approve a run that hasn't paused for review (e.g. one with
    no script yet, or one that's already running paid stages)."""
    rd = _make_run_dir(tmp_path)
    r = client.post(f"/runs/{rd.name}/approve", headers=auth)
    assert r.status_code == 409


def test_approve_passes_auto_computed_max_spend(client, auth, tmp_path: Path):
    """User saw the cost in the UI and approved → backend bumps the
    in-config budget cap so the subprocess doesn't refuse for an exceeded
    cap. The cost is computed from beats × $0.10/sec × 1.30 buffer."""
    rd = _make_run_dir(tmp_path)
    # 24 beats × 8s × $0.10 × 1.30 + buffer ≈ $25.46
    (rd / "script.json").write_text(json.dumps({
        "title": "x", "theme": "folkloric", "global_setting": "g",
        "music_mood": "dread",
        "beats": [
            {"arabic": "ج", "english_motion": "m",
             "speaker": "mother", "clip_duration_s": 8.0}
            for _ in range(24)
        ],
    }, ensure_ascii=False), encoding="utf-8")

    captured: dict = {}
    from pipeline import api as api_mod
    api_mod.set_spawn_fn(lambda args, run_dir: captured.update(args=args) or 1)

    r = client.post(f"/runs/{rd.name}/approve", headers=auth)
    assert r.status_code == 200
    args = captured["args"]
    assert "--max-spend" in args
    # Index right after the flag
    spend_str = args[args.index("--max-spend") + 1]
    spend = float(spend_str)
    # 24 × 8 = 192 sec × $0.10 = $19.20 × 1.30 + 0.50 ≈ $25.46
    assert 24 < spend < 30, f"unexpected max-spend: {spend}"


def test_failed_run_includes_actionable_error_hint(client, auth, tmp_path: Path):
    """Common failures (budget, safety, network) get a `error_hint` that
    tells the user what to do next, not just the raw exception text."""
    rd = _make_run_dir(tmp_path)
    (rd / "script.json").write_text(json.dumps({
        "title": "x", "theme": "folkloric", "global_setting": "g",
        "music_mood": "dread",
        "beats": [{"arabic": "ج", "english_motion": "m",
                   "speaker": "mother", "clip_duration_s": 8.0}],
    }, ensure_ascii=False), encoding="utf-8")
    (rd / "run.log").write_text(
        "ERROR pipeline.video.BudgetExceededError: projected spend $19.20 exceeds cap $13.00\n",
        encoding="utf-8",
    )
    body = client.get(f"/runs/{rd.name}", headers=auth).json()
    assert body["status"] == "failed"
    assert "BudgetExceededError" in body["last_error"]
    assert body["error_hint"] is not None
    assert "Resume" in body["error_hint"]


def test_safety_filter_error_hint_suggests_softer_wording(
    client, auth, tmp_path: Path,
):
    rd = _make_run_dir(tmp_path)
    (rd / "script.json").write_text("{}")
    (rd / "run.log").write_text(
        "ERROR Request blocked: The input content was flagged by safety filters\n",
        encoding="utf-8",
    )
    body = client.get(f"/runs/{rd.name}", headers=auth).json()
    assert body["error_hint"] is not None
    assert "soften" in body["error_hint"].lower()


def test_credits_exhausted_error_hint_is_user_friendly(
    client, auth, tmp_path: Path,
):
    """When the upstream generator (Kie.ai) returns code 402, the user must
    see a friendly 'top up your plan' hint — not the raw KieError JSON."""
    rd = _make_run_dir(tmp_path)
    (rd / "script.json").write_text("{}")
    # The actual error string emitted by pipeline.kie.submit_video_job
    (rd / "run.log").write_text(
        "ERROR pipeline.kie.KieError: submit response missing taskId: "
        "{'code': 402, 'msg': 'Credits insufficient : Your current balance "
        "isn’t enough to run this request. Please top up to continue.', "
        "'data': None}\n",
        encoding="utf-8",
    )
    body = client.get(f"/runs/{rd.name}", headers=auth).json()
    assert body["error_hint"] is not None
    hint = body["error_hint"].lower()
    assert "credit" in hint
    # Must not leak vendor names — end users shouldn't see "Kie", "Veo", etc.
    assert "kie" not in hint
    assert "veo" not in hint
    # Must include a clear call-to-action
    assert "top up" in hint or "upgrade" in hint or "subscribe" in hint


def test_cleanup_failed_removes_only_failed_runs(client, auth, tmp_path: Path):
    """Bulk-discards every run in `failed` status; leaves complete + running
    runs alone."""
    out = tmp_path / "out" / "admin"
    # Failed run #1 (script + log error)
    rd1 = out / "2026-05-05-fail1"; rd1.mkdir(parents=True)
    (rd1 / "script.json").write_text("{}")
    (rd1 / "run.log").write_text("ERROR x\n", encoding="utf-8")
    # Complete run — must NOT be touched
    rd2 = out / "2026-05-05-good"; rd2.mkdir()
    (rd2 / "script.json").write_text("{}")
    (rd2 / "final.mp4").write_bytes(b"x")
    # Failed run #2
    rd3 = out / "2026-05-05-fail2"; rd3.mkdir()
    (rd3 / "script.json").write_text("{}")
    (rd3 / "run.log").write_text("ERROR y\n", encoding="utf-8")

    r = client.post("/runs/cleanup-failed", headers=auth)
    assert r.status_code == 200
    deleted = r.json()["deleted_run_ids"]
    assert set(deleted) == {"2026-05-05-fail1", "2026-05-05-fail2"}
    assert not rd1.exists()
    assert rd2.exists()  # complete run preserved
    assert not rd3.exists()


def test_cleanup_failed_skips_runs_with_live_subprocess(
    client, auth, tmp_path: Path, monkeypatch,
):
    """Defensive: never bulk-delete a run whose pipeline is still running.
    The user can manually Discard those — bulk cleanup is for orphans."""
    out = tmp_path / "out" / "admin"
    rd = out / "2026-05-05-live"; rd.mkdir(parents=True)
    (rd / "script.json").write_text("{}")
    (rd / "run.log").write_text("ERROR transient\n", encoding="utf-8")
    from pipeline import api as api_mod
    api_mod._write_state(rd, pid=4242)
    monkeypatch.setattr(api_mod, "_process_alive", lambda pid, run_dir=None: pid == 4242)
    r = client.post("/runs/cleanup-failed", headers=auth)
    assert rd.exists()
    assert "2026-05-05-live" not in r.json()["deleted_run_ids"]


def test_spend_summary_aggregates_kie_spend_logs(client, auth, tmp_path: Path):
    """The /spend endpoint sums kie_spend.json across all runs and returns
    per-run totals + grand total. Useful for monthly cost tracking."""
    out = tmp_path / "out" / "admin"
    rd1 = out / "ep1"; rd1.mkdir(parents=True)
    (rd1 / "script.json").write_text(json.dumps({"title": "EP 1"}), encoding="utf-8")
    (rd1 / "kie_spend.json").write_text(json.dumps({
        "entries": [{"clip": 1, "duration_s": 8, "cost_usd": 0.80, "model": "veo3_fast"},
                    {"clip": 2, "duration_s": 9, "cost_usd": 0.90, "model": "veo3_fast"}],
    }), encoding="utf-8")
    rd2 = out / "ep2"; rd2.mkdir()
    (rd2 / "script.json").write_text(json.dumps({"title": "EP 2"}), encoding="utf-8")
    (rd2 / "kie_spend.json").write_text(json.dumps({
        "entries": [{"clip": 1, "duration_s": 8, "cost_usd": 0.80, "model": "veo3_fast"}],
    }), encoding="utf-8")
    # Run with no spend file — should be skipped
    rd3 = out / "ep3"; rd3.mkdir()

    body = client.get("/spend", headers=auth).json()
    assert body["run_count"] == 2
    assert body["total_usd"] == 2.50
    by_run = {r["run_id"]: r for r in body["by_run"]}
    assert by_run["ep1"]["usd"] == 1.70
    assert by_run["ep1"]["title"] == "EP 1"
    assert by_run["ep2"]["usd"] == 0.80


def test_failed_run_surfaces_subprocess_log_error(client, auth, tmp_path: Path):
    """Without this, the UI would show a stuck 'Awaiting Approval' even
    though the subprocess died with a budget-exceeded / safety-filter
    error. We tail the run log for ERROR lines and bubble up the message."""
    rd = _make_run_dir(tmp_path)
    (rd / "script.json").write_text(json.dumps({
        "title": "x", "theme": "folkloric", "global_setting": "g",
        "music_mood": "dread",
        "beats": [{"arabic": "ج", "english_motion": "m",
                   "speaker": "mother", "clip_duration_s": 8.0}],
    }, ensure_ascii=False), encoding="utf-8")
    # Simulate a dead subprocess that left an ERROR in run.log
    (rd / "run.log").write_text(
        "2026-05-05T12:00:00 INFO stage start: video\n"
        "2026-05-05T12:00:00 ERROR BudgetExceededError: projected spend "
        "$19.20 exceeds cap $13.00\n",
        encoding="utf-8",
    )
    r = client.get(f"/runs/{rd.name}", headers=auth)
    body = r.json()
    assert body["status"] == "failed"
    assert "BudgetExceededError" in (body["last_error"] or "")


def test_approve_spawns_resume_subprocess(client, auth, tmp_path: Path):
    rd = _make_run_dir(tmp_path)
    (rd / "script.json").write_text("{}")
    captured: dict = {"args": None}
    from pipeline import api as api_mod

    def fake_spawn(args, run_dir):
        captured["args"] = args
        # Simulate paid stage starting: drop a character_sheet to flip status
        (run_dir / "character_sheet.png").write_bytes(b"png")
        return 999

    api_mod.set_spawn_fn(fake_spawn)
    r = client.post(f"/runs/{rd.name}/approve", headers=auth)
    assert r.status_code == 200
    assert "--shorts" in captured["args"]
    assert "--resume" in captured["args"]
    # NEVER passes --pause-after-script on approve — we want paid stages to run
    assert "--pause-after-script" not in captured["args"]


# ---------------------------------------------------------------------------
# POST /runs/{id}/resume
# ---------------------------------------------------------------------------

def test_resume_spawns_subprocess(client, auth, tmp_path: Path):
    rd = _make_run_dir(tmp_path)
    (rd / "script.json").write_text("{}")
    captured: dict = {"args": None}
    from pipeline import api as api_mod
    api_mod.set_spawn_fn(lambda args, run_dir: captured.update(args=args) or 1)

    r = client.post(f"/runs/{rd.name}/resume", headers=auth)
    assert r.status_code == 200
    assert "--resume" in captured["args"]


def _seed_with_clips(rd: Path, n: int = 5, has_clips: bool = True) -> None:
    rd.mkdir(parents=True, exist_ok=True)
    (rd / "script.json").write_text(json.dumps({
        "title": "x", "theme": "folkloric", "global_setting": "g",
        "music_mood": "dread",
        "beats": [
            {"arabic": f"ج{i}", "english_motion": f"m{i}",
             "speaker": "mother", "clip_duration_s": 8.0}
            for i in range(n)
        ],
    }, ensure_ascii=False), encoding="utf-8")
    (rd / "character_sheet.png").write_bytes(b"png")
    if has_clips:
        clips = rd / "clips"
        clips.mkdir()
        for i in range(1, n + 1):
            (clips / f"{i:02d}.mp4").write_bytes(b"x")


def test_reroll_deletes_targeted_clips_and_spawns_resume(
    client, auth, tmp_path: Path,
):
    rd = _make_run_dir(tmp_path)
    _seed_with_clips(rd, n=5)
    captured: dict = {}
    from pipeline import api as api_mod
    api_mod.set_spawn_fn(lambda args, run_dir: captured.update(args=args) or 1)

    r = client.post(f"/runs/{rd.name}/reroll", json={"clips": [2, 4]}, headers=auth)
    assert r.status_code == 200
    # Targeted clips removed so pipeline regenerates them
    assert not (rd / "clips" / "02.mp4").exists()
    assert not (rd / "clips" / "04.mp4").exists()
    # Untouched clips still on disk
    assert (rd / "clips" / "01.mp4").exists()
    assert (rd / "clips" / "03.mp4").exists()
    assert (rd / "clips" / "05.mp4").exists()
    # Pipeline spawned with --reroll-clips
    assert "--reroll-clips" in captured["args"]
    assert "2,4" in captured["args"]


def test_reroll_rejects_out_of_range_clips(client, auth, tmp_path: Path):
    rd = _make_run_dir(tmp_path)
    _seed_with_clips(rd, n=3)
    r = client.post(f"/runs/{rd.name}/reroll", json={"clips": [99]}, headers=auth)
    assert r.status_code == 400
    assert "out of range" in r.json()["detail"]


def test_reroll_refuses_without_script(client, auth, tmp_path: Path):
    rd = _make_run_dir(tmp_path)  # no script.json
    r = client.post(f"/runs/{rd.name}/reroll", json={"clips": [1]}, headers=auth)
    assert r.status_code == 409


def test_reroll_refuses_when_pipeline_already_running(
    client, auth, tmp_path: Path, monkeypatch,
):
    rd = _make_run_dir(tmp_path)
    _seed_with_clips(rd)
    from pipeline import api as api_mod
    api_mod._write_state(rd, pid=4242)
    monkeypatch.setattr(api_mod, "_process_alive", lambda pid, run_dir=None: pid == 4242)
    r = client.post(f"/runs/{rd.name}/reroll", json={"clips": [1]}, headers=auth)
    assert r.status_code == 409


def test_resume_refuses_when_a_process_is_already_running(
    client, auth, tmp_path: Path, monkeypatch,
):
    """We don't want two subprocesses fighting over the same run dir.
    The check uses os.kill(pid, 0) — patch _process_alive to return True."""
    rd = _make_run_dir(tmp_path)
    (rd / "script.json").write_text("{}")
    from pipeline import api as api_mod
    # Write a state with a fake pid; monkeypatch process-alive check.
    api_mod._write_state(rd, pid=4242, last_action="approve")
    monkeypatch.setattr(api_mod, "_process_alive", lambda pid, run_dir=None: pid == 4242)

    r = client.post(f"/runs/{rd.name}/resume", headers=auth)
    assert r.status_code == 409


# ---------------------------------------------------------------------------
# POST /runs/{id}/cancel
# ---------------------------------------------------------------------------

def test_cancel_kills_running_process(client, auth, tmp_path: Path, monkeypatch):
    rd = _make_run_dir(tmp_path)
    from pipeline import api as api_mod
    api_mod._write_state(rd, pid=4242)
    monkeypatch.setattr(api_mod, "_process_alive", lambda pid, run_dir=None: pid == 4242)

    killed: list = []
    monkeypatch.setattr(api_mod.os, "kill", lambda pid, sig: killed.append((pid, sig)))
    r = client.post(f"/runs/{rd.name}/cancel", headers=auth)
    assert r.status_code == 200
    assert r.json()["killed_pid"] == 4242
    assert killed and killed[0][0] == 4242


def test_cancel_returns_null_pid_when_no_process_running(client, auth, tmp_path: Path):
    rd = _make_run_dir(tmp_path)
    r = client.post(f"/runs/{rd.name}/cancel", headers=auth)
    assert r.status_code == 200
    assert r.json()["killed_pid"] is None


# ---------------------------------------------------------------------------
# GET /runs/{id}/video and /thumbnail
# ---------------------------------------------------------------------------

def test_get_video_404_until_final_mp4_exists(client, auth, tmp_path: Path):
    rd = _make_run_dir(tmp_path)
    r = client.get(f"/runs/{rd.name}/video", headers=auth)
    assert r.status_code == 404


def test_get_video_streams_final_mp4(client, auth, tmp_path: Path):
    rd = _make_run_dir(tmp_path)
    (rd / "final.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42abc")
    r = client.get(f"/runs/{rd.name}/video", headers=auth)
    assert r.status_code == 200
    assert r.headers["content-type"] == "video/mp4"
    assert r.content.startswith(b"\x00\x00\x00\x18ftypmp42")


def test_repair_video_404_when_no_final_mp4(client, auth, tmp_path: Path):
    rd = _make_run_dir(tmp_path)
    r = client.post(f"/runs/{rd.name}/repair-video", headers=auth)
    assert r.status_code == 404


def test_repair_video_invokes_faststart_remux(client, auth, tmp_path: Path, monkeypatch):
    """The endpoint should call pipeline.mp4_faststart.rewrite_with_faststart
    on the existing final.mp4 and report success. We mock the re-muxer
    so the test doesn't actually shell out to ffmpeg."""
    rd = _make_run_dir(tmp_path)
    final = rd / "final.mp4"
    final.write_bytes(b"\x00\x00\x00\x18ftypmp42 old moov at end")
    # Leftover thumbnail from the broken file — endpoint should nuke it
    (rd / "thumbnail.jpg").write_bytes(b"stale-jpg")

    called: list[Path] = []
    def fake_rewrite(path):
        called.append(path)
    monkeypatch.setattr("pipeline.mp4_faststart.rewrite_with_faststart", fake_rewrite)

    r = client.post(f"/runs/{rd.name}/repair-video", headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["repaired"] is True
    assert called == [final]
    # Thumbnail cache busted
    assert not (rd / "thumbnail.jpg").exists()


def test_get_video_accepts_query_token_for_browser_video_element(
    client, api_token, tmp_path: Path,
):
    """Flutter video_player on Chrome web drops Authorization headers; the
    only way the browser <video> element can authenticate is via a query
    string token. This endpoint must support both header and query auth."""
    rd = _make_run_dir(tmp_path)
    (rd / "final.mp4").write_bytes(b"mp4-bytes")
    # No Authorization header — auth via query string only
    r = client.get(f"/runs/{rd.name}/video?token={api_token}")
    assert r.status_code == 200
    assert r.headers["content-type"] == "video/mp4"


def test_get_video_query_token_must_match(client, tmp_path: Path):
    rd = _make_run_dir(tmp_path)
    (rd / "final.mp4").write_bytes(b"mp4-bytes")
    r = client.get(f"/runs/{rd.name}/video?token=wrong")
    # T4: require_user_header_or_query treats an invalid token as 401 Unauthorized
    # (consistent with require_user) rather than the old 403 Forbidden.
    assert r.status_code == 401


def test_get_thumbnail_accepts_query_token(client, api_token, tmp_path: Path):
    rd = _make_run_dir(tmp_path)
    (rd / "character_sheet.png").write_bytes(b"\x89PNG\r\n\x1a\nfake")
    r = client.get(f"/runs/{rd.name}/thumbnail?token={api_token}")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"


def test_thumbnail_uses_character_sheet_when_no_extracted_thumbnail(
    client, auth, tmp_path: Path,
):
    rd = _make_run_dir(tmp_path)
    (rd / "character_sheet.png").write_bytes(b"\x89PNG\r\n\x1a\nfake-png")
    r = client.get(f"/runs/{rd.name}/thumbnail", headers=auth)
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"


def test_clip_thumbnail_extracts_and_caches(client, auth, tmp_path: Path, monkeypatch):
    """Per-clip thumbnail endpoint: extracts the first frame of clips/NN.mp4
    on demand and caches the JPG so subsequent requests skip ffmpeg."""
    rd = _make_run_dir(tmp_path)
    clips = rd / "clips"
    clips.mkdir()
    (clips / "03.mp4").write_bytes(b"fake-mp4")
    extracted: list[Path] = []

    def fake_extract(video_path, out_path):
        extracted.append(out_path)
        out_path.write_bytes(b"\xff\xd8\xff\xe0fake-jpg")

    from pipeline import api as api_mod
    monkeypatch.setattr(api_mod, "_extract_thumbnail", fake_extract)
    r = client.get(f"/runs/{rd.name}/clips/3/thumbnail", headers=auth)
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/jpeg"
    assert (clips / "03.jpg").exists()
    # Cached on second hit — no second ffmpeg call
    r2 = client.get(f"/runs/{rd.name}/clips/3/thumbnail", headers=auth)
    assert r2.status_code == 200
    assert len(extracted) == 1


def test_clip_thumbnail_404_when_clip_missing(client, auth, tmp_path: Path):
    rd = _make_run_dir(tmp_path)
    (rd / "clips").mkdir()
    r = client.get(f"/runs/{rd.name}/clips/5/thumbnail", headers=auth)
    assert r.status_code == 404


def test_get_clip_video_serves_mp4(client, auth, tmp_path: Path):
    """Streams clips/NN.mp4 with content-type video/mp4."""
    rd = _make_run_dir(tmp_path)
    clips = rd / "clips"
    clips.mkdir()
    (clips / "03.mp4").write_bytes(b"fake-mp4-bytes")

    resp = client.get(
        f"/runs/{rd.name}/clips/3/video",
        headers=auth,
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "video/mp4"
    assert resp.content == b"fake-mp4-bytes"


def test_get_clip_video_404_when_missing(client, auth, tmp_path: Path):
    """If clips/NN.mp4 doesn't exist, returns 404."""
    rd = _make_run_dir(tmp_path)
    resp = client.get(
        f"/runs/{rd.name}/clips/2/video",
        headers=auth,
    )
    assert resp.status_code == 404


def test_get_clip_video_query_token_works(client, api_token, tmp_path: Path):
    """The query-string token path used by Flutter web — same auth works."""
    rd = _make_run_dir(tmp_path)
    clips = rd / "clips"
    clips.mkdir()
    (clips / "01.mp4").write_bytes(b"x")
    resp = client.get(f"/runs/{rd.name}/clips/1/video?token={api_token}")
    assert resp.status_code == 200


def test_clip_thumbnail_accepts_query_token(client, api_token, tmp_path: Path, monkeypatch):
    """Image elements in browsers can't always pass auth headers — the
    endpoint must also accept ?token=… like /video and /thumbnail."""
    rd = _make_run_dir(tmp_path)
    (rd / "clips").mkdir()
    (rd / "clips" / "01.mp4").write_bytes(b"x")
    from pipeline import api as api_mod
    monkeypatch.setattr(api_mod, "_extract_thumbnail",
                        lambda v, o: o.write_bytes(b"\xff\xd8\xff\xe0jpg"))
    r = client.get(f"/runs/{rd.name}/clips/1/thumbnail?token={api_token}")
    assert r.status_code == 200


def test_thumbnail_404_when_nothing_to_show(client, auth, tmp_path: Path):
    rd = _make_run_dir(tmp_path)
    r = client.get(f"/runs/{rd.name}/thumbnail", headers=auth)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# GET /runs/{id}/log
# ---------------------------------------------------------------------------

def test_get_log_returns_empty_when_no_log_yet(client, auth, tmp_path: Path):
    rd = _make_run_dir(tmp_path)
    r = client.get(f"/runs/{rd.name}/log", headers=auth)
    assert r.status_code == 200
    assert r.text == ""


# ---------------------------------------------------------------------------
# DELETE /runs/{id}
# ---------------------------------------------------------------------------

def test_delete_removes_run_dir(client, auth, tmp_path: Path):
    rd = _make_run_dir(tmp_path)
    (rd / "script.json").write_text("{}")
    (rd / "final.mp4").write_bytes(b"x")
    r = client.delete(f"/runs/{rd.name}", headers=auth)
    assert r.status_code == 200
    assert r.json() == {"run_id": rd.name, "deleted": True}
    assert not rd.exists()


def test_delete_kills_subprocess_then_removes_dir(
    client, auth, tmp_path: Path, monkeypatch,
):
    """The user just wants the run gone. Backend should stop any live
    pipeline subprocess (SIGTERM → wait → SIGKILL fallback) atomically
    inside the DELETE handler, not return 409 and force a separate cancel
    call (which races the OS reaper anyway)."""
    rd = _make_run_dir(tmp_path)
    from pipeline import api as api_mod
    api_mod._write_state(rd, pid=4242)

    # Simulate a process that "dies" after the first SIGTERM call
    state = {"alive": True}
    monkeypatch.setattr(api_mod, "_process_alive",
                        lambda pid, run_dir=None: pid == 4242 and state["alive"])
    killed: list = []

    def fake_kill(pid, sig):
        killed.append((pid, sig))
        state["alive"] = False

    monkeypatch.setattr(api_mod.os, "kill", fake_kill)

    r = client.delete(f"/runs/{rd.name}", headers=auth)
    assert r.status_code == 200
    assert r.json() == {"run_id": rd.name, "deleted": True}
    assert killed, "should have sent at least SIGTERM"
    assert not rd.exists()


def test_process_alive_reaps_zombie_children(monkeypatch):
    """Subprocess zombies have a PID in the table but are dead. `os.kill(pid, 0)`
    returns success for them, falsely reporting "alive". We must reap them
    via WNOHANG first so derive_status correctly transitions running →
    awaiting_approval / failed / complete after the subprocess exits."""
    from pipeline import api as api_mod

    # Fake state machine: WNOHANG reaps the zombie, after which kill returns
    # ESRCH because the PID is gone.
    state = {"reaped": False}

    def fake_waitpid(pid, flags):
        if not state["reaped"]:
            state["reaped"] = True
            return (pid, 0)  # reaped
        return (0, 0)        # nothing to reap

    def fake_kill(pid, sig):
        if state["reaped"]:
            raise ProcessLookupError("ESRCH: no such process")
        # Before we reap, kill returns success (zombie behavior)
        return None

    monkeypatch.setattr(api_mod.os, "waitpid", fake_waitpid)
    monkeypatch.setattr(api_mod.os, "kill", fake_kill)

    # First call reaps the zombie and reports dead
    assert api_mod._process_alive(4242) is False
    # Subsequent calls also report dead (subprocess truly gone)
    assert api_mod._process_alive(4242) is False


def test_process_alive_reports_truly_running_process(monkeypatch):
    """If WNOHANG finds nothing to reap (process is genuinely still running)
    and kill(pid, 0) succeeds, we correctly report alive."""
    from pipeline import api as api_mod

    def fake_waitpid(pid, flags):
        # No zombie children
        return (0, 0)

    def fake_kill(pid, sig):
        return None  # alive

    monkeypatch.setattr(api_mod.os, "waitpid", fake_waitpid)
    monkeypatch.setattr(api_mod.os, "kill", fake_kill)
    assert api_mod._process_alive(4242) is True


def test_stop_process_escalates_to_sigkill_when_sigterm_ignored(monkeypatch):
    """Direct unit test for the helper — easier than mocking through HTTP.
    A stuck process ignoring SIGTERM must be SIGKILL'd so the user is never
    stuck with an undeletable run."""
    import signal as _signal
    from pipeline import api as api_mod

    sent: list = []
    state = {"alive": True}

    def fake_kill(pid, sig):
        sent.append(sig)
        if sig == _signal.SIGKILL:
            state["alive"] = False

    monkeypatch.setattr(api_mod.os, "kill", fake_kill)
    monkeypatch.setattr(api_mod, "_process_alive",
                        lambda pid, run_dir=None: pid == 4242 and state["alive"])
    # Speed up: zero out sleeps inside the helper
    import time as _time
    monkeypatch.setattr(_time, "sleep", lambda _s: None)

    ok = api_mod._stop_process_and_wait(4242, soft_timeout_s=0.05)
    assert ok is True
    assert _signal.SIGTERM in sent
    assert _signal.SIGKILL in sent


def test_delete_404_for_unknown_run(client, auth):
    r = client.delete("/runs/not-a-real-run", headers=auth)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# PUT /runs/{id}/script
# ---------------------------------------------------------------------------

def _seed_awaiting_approval(rd: Path) -> None:
    """Make a run dir look like it's paused for approval."""
    rd.mkdir(parents=True, exist_ok=True)
    (rd / "script.json").write_text(json.dumps({
        "title": "old title",
        "theme": "folkloric",
        "global_setting": "x",
        "music_mood": "dread",
        "target_duration_s": 16,
        "beats": [
            {"arabic": "ج1", "english_motion": "m1",
             "clip_duration_s": 8.0, "speaker": "mother"},
            {"arabic": "ج2", "english_motion": "m2",
             "clip_duration_s": 8.0, "speaker": "son"},
        ],
    }, ensure_ascii=False), encoding="utf-8")


def test_edit_script_replaces_beats(client, auth, tmp_path: Path):
    rd = _make_run_dir(tmp_path)
    _seed_awaiting_approval(rd)
    body = {
        "title": "new title",
        "beats": [
            {"arabic": "بدلت السطر",
             "english_motion": "new motion",
             "speaker": "mother",
             "clip_duration_s": 9.0},
        ],
    }
    r = client.put(f"/runs/{rd.name}/script", json=body, headers=auth)
    assert r.status_code == 200
    out = r.json()
    assert out["title"] == "new title"
    assert len(out["beats"]) == 1
    assert out["beats"][0]["arabic"] == "بدلت السطر"
    # File on disk reflects the edit
    doc = json.loads((rd / "script.json").read_text(encoding="utf-8"))
    assert doc["title"] == "new title"
    assert doc["target_duration_s"] == 9.0


def test_edit_script_rejected_after_approval(client, auth, tmp_path: Path):
    """Once the user has approved + Veo started (clips exist), dialogue is baked
    into Veo clips and editing the file does nothing — refuse to mislead."""
    rd = _make_run_dir(tmp_path)
    _seed_with_clips(rd, n=1)  # At least one clip means Veo started
    body = {
        "title": "x",
        "beats": [{"arabic": "ج", "english_motion": "m",
                   "speaker": "mother", "clip_duration_s": 8.0}],
    }
    r = client.put(f"/runs/{rd.name}/script", json=body, headers=auth)
    assert r.status_code == 409


def test_edit_script_rejects_empty_speaker(client, auth, tmp_path: Path):
    """PA-1: empty speaker is rejected; 'narrator' and any other non-empty value are now valid."""
    rd = _make_run_dir(tmp_path)
    _seed_awaiting_approval(rd)
    body = {
        "title": "x",
        "beats": [{"arabic": "ج", "english_motion": "m",
                   "speaker": "", "clip_duration_s": 8.0}],
    }
    r = client.put(f"/runs/{rd.name}/script", json=body, headers=auth)
    assert r.status_code == 400
    assert "speaker" in r.json()["detail"]


def test_edit_script_allowed_in_awaiting_veo_approval(tmp_path, client, auth):
    """The PUT /runs/{id}/script endpoint must accept edits when the run
    is paused at awaiting_veo_approval, not just awaiting_approval."""
    run_id = _create_run_in_awaiting_veo_approval(tmp_path)
    # Seed a script.json that has at least one beat (the helper from Task 4
    # may write a minimal one — we ensure it has real beats).
    script_path = (tmp_path / "out" / "admin" / run_id / "script.json")
    script_path.write_text(
        '{"title":"original","beats":[{"arabic":"old","english_motion":"x",'
        '"speaker":"mother","clip_duration_s":8.0}],"target_duration_s":8.0,'
        '"theme":"folkloric","global_setting":"x","music_mood":"dread"}',
        encoding="utf-8",
    )
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
        headers=auth,
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "edited"


# ---------------------------------------------------------------------------
# Progress info
# ---------------------------------------------------------------------------

def test_progress_video_stage_clips_done(client, auth, tmp_path: Path):
    """Mid-run with 3 of 8 clips on disk → progress reports clips_done=3."""
    rd = _make_run_dir(tmp_path)
    (rd / "script.json").write_text(json.dumps({
        "title": "x", "theme": "folkloric", "global_setting": "x",
        "music_mood": "dread",
        "beats": [
            {"arabic": f"ج{i}", "english_motion": f"m{i}",
             "clip_duration_s": 8.0, "speaker": "mother"}
            for i in range(8)
        ],
    }, ensure_ascii=False), encoding="utf-8")
    (rd / "character_sheet.png").write_bytes(b"png")
    (rd / "clips").mkdir()
    for i in range(1, 4):
        (rd / "clips" / f"{i:02d}.mp4").write_bytes(b"x")

    r = client.get(f"/runs/{rd.name}", headers=auth)
    progress = r.json().get("progress")
    assert progress is not None
    assert progress["stage"] == "video"
    assert progress["clips_done"] == 3
    assert progress["clips_total"] == 8


def test_progress_none_when_complete(client, auth, tmp_path: Path):
    rd = _make_run_dir(tmp_path)
    (rd / "script.json").write_text("{}")
    (rd / "final.mp4").write_bytes(b"x")
    r = client.get(f"/runs/{rd.name}", headers=auth)
    assert r.json()["progress"] is None


def test_progress_script_stage_when_no_script_yet(client, auth, tmp_path: Path):
    rd = _make_run_dir(tmp_path)
    # Need a state to make derive_status not return failed
    from pipeline import api as api_mod
    api_mod._write_state(rd, pid=4242)
    monkeypatch_alive = lambda pid, run_dir=None: pid == 4242  # noqa: E731
    # Patch via app module instead — but TestClient won't see monkeypatch
    # without a fixture. Just check the progress endpoint when script-less.
    r = client.get(f"/runs/{rd.name}", headers=auth)
    progress = r.json().get("progress")
    # Even when status=failed, progress is computed if not complete
    assert progress is not None
    assert progress["stage"] == "script"
    assert progress["clips_total"] == 0


def test_get_log_returns_tail(client, auth, tmp_path: Path):
    rd = _make_run_dir(tmp_path)
    (rd / "api_subprocess.log").write_text(
        "\n".join(f"line {i}" for i in range(1, 11)),
        encoding="utf-8",
    )
    r = client.get(f"/runs/{rd.name}/log?lines=3", headers=auth)
    body = r.text.splitlines()
    assert body == ["line 8", "line 9", "line 10"]


# ---------------------------------------------------------------------------
# awaiting_veo_approval status — Task 2
# ---------------------------------------------------------------------------

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


def test_derive_status_failed_when_post_flux_log_has_error(tmp_path, monkeypatch):
    """sheet_exists + no clips + dead process + ERROR line in run.log
    → 'failed', not 'awaiting_veo_approval'. Exercises the inner _last_error_from_log
    guard inside the new branch."""
    from pipeline.api import derive_status
    run_dir = tmp_path / "test-run-3"
    run_dir.mkdir()
    (run_dir / "script.json").write_text('{"beats":[]}', encoding="utf-8")
    (run_dir / "character_sheet.png").write_bytes(b"fake-png")
    (run_dir / "api_state.json").write_text('{"pid": null}', encoding="utf-8")
    # _last_error_from_log scans for an ERROR line in run.log or api_subprocess.log
    (run_dir / "api_subprocess.log").write_text(
        "2026-05-06 ERROR Flux call failed: 502 Bad Gateway\n",
        encoding="utf-8",
    )
    assert derive_status(run_dir) == "failed"


# ---------------------------------------------------------------------------
# Task 3: /approve must include --pause-after-character-sheet
# ---------------------------------------------------------------------------

def test_approve_passes_pause_after_character_sheet(client, auth, tmp_path: Path):
    """After /approve, the spawned subprocess MUST include
    --pause-after-character-sheet so Veo doesn't auto-start."""
    from pipeline import api as api_mod

    captured: list[list[str]] = []

    def stub_spawn(args, run_dir):
        captured.append(args)
        return 9999

    api_mod.set_spawn_fn(stub_spawn)

    # Set up a run in awaiting_approval state (script.json present, no character_sheet)
    rd = _make_run_dir(tmp_path)
    _seed_awaiting_approval(rd)

    resp = client.post(f"/runs/{rd.name}/approve", headers=auth)
    assert resp.status_code == 200
    assert len(captured) == 1, "expected exactly one subprocess spawn"
    assert any(a == "--pause-after-character-sheet" for a in captured[0]), (
        f"--pause-after-character-sheet missing from spawn args: {captured[0]}"
    )


# ---------------------------------------------------------------------------
# Task 4: POST /runs/{id}/approve-veo — second approval gate
# ---------------------------------------------------------------------------

def _create_run_in_awaiting_veo_approval(tmp_path: Path, run_id: str = "2026-05-06-veo") -> str:
    """Create a run dir in awaiting_veo_approval state:
    - script.json present
    - character_sheet.png present (Flux done)
    - api_state.json with pid=null (no live process)
    - no clips/, no final.mp4
    Returns the run_id string."""
    rd = tmp_path / "out" / "admin" / run_id
    rd.mkdir(parents=True, exist_ok=True)
    (rd / "script.json").write_text(json.dumps({
        "title": "x", "theme": "folkloric", "global_setting": "g",
        "music_mood": "dread",
        "beats": [
            {"arabic": "ج1", "english_motion": "m1",
             "clip_duration_s": 8.0, "speaker": "mother"},
        ],
    }, ensure_ascii=False), encoding="utf-8")
    (rd / "character_sheet.png").write_bytes(b"fake-png")
    (rd / "api_state.json").write_text('{"pid": null}', encoding="utf-8")
    return run_id


def test_approve_veo_happy_path(tmp_path, monkeypatch, client, auth):
    """From awaiting_veo_approval, /approve-veo spawns run.py --resume with NO
    pause flags so Veo runs to completion."""
    from pipeline import api as api_mod

    captured: list[list[str]] = []

    def stub_spawn(args, run_dir):
        captured.append(args)
        return 9999

    api_mod.set_spawn_fn(stub_spawn)
    run_id = _create_run_in_awaiting_veo_approval(tmp_path)
    resp = client.post(
        f"/runs/{run_id}/approve-veo",
        headers=auth,
    )
    assert resp.status_code == 200
    assert "--pause-after-character-sheet" not in captured[0]
    assert "--pause-after-script" not in captured[0]
    assert "--resume" in captured[0]


def test_approve_veo_rejected_from_wrong_status(tmp_path, monkeypatch, client, auth):
    """From awaiting_approval (no character_sheet.png yet), /approve-veo
    returns 409."""
    rd = _make_run_dir(tmp_path)
    _seed_awaiting_approval(rd)  # awaiting_approval state (no character_sheet)
    resp = client.post(
        f"/runs/{rd.name}/approve-veo",
        headers=auth,
    )
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Task 6: POST /runs/{id}/character-sheet/reroll
# ---------------------------------------------------------------------------

def test_character_sheet_reroll_deletes_and_respawns(tmp_path, client, auth):
    """Happy path: from awaiting_veo_approval, the endpoint deletes
    character_sheet.png and spawns run.py --shorts --resume --pause-after-character-sheet."""
    from pipeline import api as api_mod

    captured: list[list[str]] = []

    def stub_spawn(args, run_dir):
        captured.append(args)
        return 5555

    api_mod.set_spawn_fn(stub_spawn)

    run_id = _create_run_in_awaiting_veo_approval(tmp_path)
    sheet = tmp_path / "out" / "admin" / run_id / "character_sheet.png"
    assert sheet.exists(), "test setup: helper must put a sheet on disk"

    resp = client.post(
        f"/runs/{run_id}/character-sheet/reroll",
        headers=auth,
    )
    assert resp.status_code == 200
    assert not sheet.exists(), "reroll must delete existing sheet"
    assert "--pause-after-character-sheet" in captured[0]
    assert "--resume" in captured[0]
    assert "--shorts" in captured[0]


def test_character_sheet_reroll_rejected_from_wrong_status(tmp_path, client, auth):
    """Returns 409 from awaiting_approval (no character_sheet yet)."""
    rd = _make_run_dir(tmp_path)
    _seed_awaiting_approval(rd)  # awaiting_approval state (no character_sheet)
    resp = client.post(
        f"/runs/{rd.name}/character-sheet/reroll",
        headers=auth,
    )
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Task 12: POST /runs/freeform
# ---------------------------------------------------------------------------

def test_freeform_endpoint_persists_controls_to_disk(tmp_path, client, auth, monkeypatch):
    """POST /runs/freeform writes freeform_controls.json with the chosen controls
    (egyptian / anime_2d / human / twist / 8 beats × 8s). The inline script
    generator reads those controls; the worker re-reads them at approval time."""
    # `client` fixture already sets FACELESS_OUT_ROOT=tmp_path/out — keep that.
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
    resp = client.post("/runs/freeform", json=payload, headers=auth)
    assert resp.status_code == 201
    body = resp.json()
    controls = json.loads(
        (tmp_path / "out" / "admin" / body["id"] / "freeform_controls.json")
        .read_text(encoding="utf-8")
    )
    assert controls["dialect"] == "egyptian"
    assert controls["art_style"] == "anime_2d"
    assert controls["character_template"] == "human"
    assert controls["ending_type"] == "twist"
    assert controls["num_beats"] == 8
    assert controls["per_beat_seconds"] == 8


def test_freeform_endpoint_validates_dialect(client, tmp_path, auth, monkeypatch):
    """Unknown dialect → 422 (Pydantic) or 400."""
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path))
    payload = {
        "theme": "urban", "premise": "x" * 10, "dialect": "klingon",
        "art_style": "anime_2d", "character_template": "human",
        "ending_type": "twist", "num_beats": 8, "per_beat_seconds": 8,
    }
    resp = client.post(
        "/runs/freeform", json=payload,
        headers=auth,
    )
    assert resp.status_code in (400, 422)


# ---------------------------------------------------------------------------
# CN-A: character_name field on Beat + API schemas
# ---------------------------------------------------------------------------

TOKEN = "test-token-abc"


def _create_run_with_script_json(tmp_path: Path) -> str:
    """Write a minimal run dir with a script.json (no character_name) and
    return the run_id. Uses the same out-root the `client` fixture points at."""
    run_id = "2026-05-06-cn-a"
    rd = tmp_path / "out" / "admin" / run_id
    rd.mkdir(parents=True, exist_ok=True)
    (rd / "script.json").write_text(json.dumps({
        "title": "t", "theme": "folkloric",
        "global_setting": "x", "music_mood": "dread",
        "target_duration_s": 8.0,
        "story_combined": "م",
        "beats": [{
            "arabic": "م", "english_motion": "x",
            "clip_duration_s": 8.0, "speaker": "mother",
        }],
    }, ensure_ascii=False), encoding="utf-8")
    return run_id


def test_get_script_returns_character_name(tmp_path, client):
    """When script.json carries character_name on each beat, the API serves it."""
    run_id = _create_run_with_script_json(tmp_path)
    # Overwrite the helper-written script with one that has character_name
    sp = tmp_path / "out" / "admin" / run_id / "script.json"
    sp.write_text(json.dumps({
        "title": "t", "theme": "folkloric",
        "global_setting": "x", "music_mood": "dread",
        "target_duration_s": 8.0,
        "story_combined": "م",
        "beats": [{
            "arabic": "م", "english_motion": "x",
            "clip_duration_s": 8.0, "speaker": "mother",
            "character_name": "أم خالد",
        }],
    }, ensure_ascii=False), encoding="utf-8")
    resp = client.get(
        f"/runs/{run_id}/script",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["beats"][0]["character_name"] == "أم خالد"


def test_edit_script_roundtrips_character_name(tmp_path, client):
    """PUT /runs/{id}/script accepts character_name and writes it back."""
    run_id = _create_run_with_script_json(tmp_path)
    payload = {
        "title": "edited",
        "beats": [{
            "arabic": "ح", "english_motion": "x", "speaker": "son",
            "clip_duration_s": 8.0, "character_name": "خالد",
        }],
    }
    resp = client.put(
        f"/runs/{run_id}/script",
        json=payload,
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert resp.status_code == 200
    assert resp.json()["beats"][0]["character_name"] == "خالد"


def test_from_script_accepts_character_name(tmp_path, client):
    """POST /runs/from-script accepts character_name on each beat."""
    payload = {
        "title": "Hand", "theme": "folkloric",
        "beats": [{
            "arabic": "م", "english_motion": "x", "speaker": "mother",
            "clip_duration_s": 8.0, "character_name": "أم يوسف",
        }],
    }
    resp = client.post(
        "/runs/from-script", json=payload,
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    run_id = body["id"]
    resp2 = client.get(f"/runs/{run_id}/script",
                       headers={"Authorization": f"Bearer {TOKEN}"})
    assert resp2.status_code == 200
    assert resp2.json()["beats"][0]["character_name"] == "أم يوسف"


# ---------------------------------------------------------------------------
# CIN-C: narration_style field on POST /runs/freeform
# ---------------------------------------------------------------------------

def test_freeform_endpoint_accepts_narration_style(tmp_path, client, monkeypatch):
    """POST /runs/freeform accepts narration_style and persists it to
    freeform_controls.json so the script generator + worker both see it."""
    # Don't override FACELESS_OUT_ROOT — the `client` fixture already sets it
    # to tmp_path/out. Run dir will land at tmp_path/out/admin/<id>/.
    resp = client.post(
        "/runs/freeform",
        json={
            "theme": "urban", "premise": "A photographer who loses memory.",
            "dialect": "msa", "art_style": "cinematic_photo_real",
            "character_template": "human", "ending_type": "twist",
            "num_beats": 8, "per_beat_seconds": 8,
            "narration_style": "cinematic",
        },
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    controls = json.loads(
        (tmp_path / "out" / "admin" / body["id"] / "freeform_controls.json")
        .read_text(encoding="utf-8")
    )
    assert controls["narration_style"] == "cinematic"


def test_freeform_endpoint_default_narration_style_cinematic(tmp_path, client, monkeypatch):
    """If narration_style is omitted, the request defaults to 'cinematic'."""
    # Don't override FACELESS_OUT_ROOT — the `client` fixture already sets it
    # to tmp_path/out. Run dir will land at tmp_path/out/admin/<id>/.
    resp = client.post(
        "/runs/freeform",
        json={
            "theme": "urban", "premise": "x" * 4,
            "dialect": "msa", "art_style": "cinematic_photo_real",
            "character_template": "human", "ending_type": "twist",
            "num_beats": 8, "per_beat_seconds": 8,
        },  # narration_style omitted
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    controls = json.loads(
        (tmp_path / "out" / "admin" / body["id"] / "freeform_controls.json")
        .read_text(encoding="utf-8")
    )
    assert controls["narration_style"] == "cinematic"


def test_create_freeform_run_writes_controls_file(tmp_path, client, monkeypatch):
    """POST /runs/freeform persists the chosen controls to freeform_controls.json
    so subsequent /approve and /reroll spawns can reload them."""
    import json as _json
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path))
    from pipeline.api import set_spawn_fn
    captured = []
    def stub_spawn(args, run_dir):
        captured.append(args); return 1234
    set_spawn_fn(stub_spawn)
    payload = {
        "theme": "folkloric", "premise": "قصة حب في الثلج",
        "dialect": "syrian", "art_style": "pixar_3d",
        "character_template": "animal", "ending_type": "closed_tragic",
        "num_beats": 8, "per_beat_seconds": 8,
        "narration_style": "cinematic",
    }
    resp = client.post("/runs/freeform", json=payload,
                       headers={"Authorization": f"Bearer {TOKEN}"})
    assert resp.status_code == 201
    run_id = resp.json()["id"]
    controls_path = tmp_path / "admin" / run_id / "freeform_controls.json"
    assert controls_path.exists(), "freeform_controls.json must be persisted on creation"
    persisted = _json.loads(controls_path.read_text(encoding="utf-8"))
    assert persisted["dialect"] == "syrian"
    assert persisted["character_template"] == "animal"
    assert persisted["narration_style"] == "cinematic"
    assert persisted["num_beats"] == 8


# ===========================================================================
# PA-1: free-form speaker enum in API
# ===========================================================================

def test_from_script_accepts_any_speaker_string(tmp_path, client):
    """Loosened enum: speaker can be any non-empty string."""
    payload = {
        "title": "Hand", "theme": "folkloric",
        "beats": [{
            "arabic": "x", "english_motion": "y", "speaker": "warrior",
            "clip_duration_s": 8.0, "character_name": "خالد",
        }],
    }
    resp = client.post("/runs/from-script", json=payload,
                       headers={"Authorization": f"Bearer {TOKEN}"})
    assert resp.status_code == 201


def test_from_script_rejects_empty_speaker(tmp_path, client):
    payload = {
        "title": "Hand", "theme": "folkloric",
        "beats": [{
            "arabic": "x", "english_motion": "y", "speaker": "",
            "clip_duration_s": 8.0, "character_name": "خالد",
        }],
    }
    resp = client.post("/runs/from-script", json=payload,
                       headers={"Authorization": f"Bearer {TOKEN}"})
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# PB-2: character_descriptions in ScriptResponse
# ---------------------------------------------------------------------------

def test_get_script_returns_character_descriptions(tmp_path, client):
    """The /script endpoint propagates the character_descriptions field."""
    run_id = _create_run_with_script_json(tmp_path)
    import json as _json
    sp = tmp_path / "out" / "admin" / run_id / "script.json"
    sp.write_text(_json.dumps({
        "title": "t", "theme": "folkloric",
        "global_setting": "g", "music_mood": "dread",
        "target_duration_s": 8.0,
        "story_combined": "م",
        "character_descriptions": {"خالد": "young man mid-20s"},
        "beats": [{
            "arabic": "م", "english_motion": "x",
            "clip_duration_s": 8.0, "speaker": "son",
            "character_name": "خالد",
        }],
    }, ensure_ascii=False), encoding="utf-8")
    resp = client.get(
        f"/runs/{run_id}/script",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["character_descriptions"]["خالد"].startswith("young man")


def test_get_script_returns_empty_character_descriptions_for_legacy(tmp_path, client):
    """Legacy script.json without character_descriptions → empty dict in response."""
    run_id = _create_run_with_script_json(tmp_path)
    resp = client.get(
        f"/runs/{run_id}/script",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["character_descriptions"] == {}


# ---------------------------------------------------------------------------
# Per-user run isolation (Task 3 of B2 Supabase Auth)
# ---------------------------------------------------------------------------

def test_user_a_cannot_see_user_b_runs(monkeypatch, tmp_path, client_factory):
    """A run created under one user_id must not appear in another user's listing."""
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path))
    # Stage one run under "alice", one under "bob"
    (tmp_path / "alice" / "run-1").mkdir(parents=True)
    (tmp_path / "alice" / "run-1" / "manifest.json").write_text('{"theme":"a"}')
    (tmp_path / "bob" / "run-2").mkdir(parents=True)
    (tmp_path / "bob" / "run-2" / "manifest.json").write_text('{"theme":"b"}')

    alice = client_factory(user_id="alice")
    bob = client_factory(user_id="bob")

    a_runs = alice.get("/runs").json()
    b_runs = bob.get("/runs").json()

    assert {r["id"] for r in a_runs} == {"run-1"}
    assert {r["id"] for r in b_runs} == {"run-2"}


def test_get_balance_returns_db_value(client_factory, monkeypatch):
    monkeypatch.setattr("pipeline.db.get_balance",
                       lambda uid: 137 if uid == "alice" else 0)
    c = client_factory(user_id="alice")
    r = c.get("/billing/balance")
    assert r.status_code == 200
    assert r.json() == {"balance": 137}


def test_get_plan_falls_back_to_free_for_new_users(client_factory, monkeypatch):
    monkeypatch.setattr("pipeline.db.get_user_profile", lambda uid: None)
    monkeypatch.setattr("pipeline.db.get_balance", lambda uid: 0)
    c = client_factory(user_id="alice")
    r = c.get("/billing/plan")
    assert r.status_code == 200
    body = r.json()
    assert body["plan"] == "free"
    assert body["current_period_end"] is None
    assert body["balance"] == 0


def test_get_plan_returns_subscription_for_existing_user(client_factory, monkeypatch):
    from pipeline.db import UserProfile
    monkeypatch.setattr(
        "pipeline.db.get_user_profile",
        lambda uid: UserProfile(
            id=uid, stripe_customer_id="cus_1",
            current_plan="creator", current_period_end="2026-06-11T00:00:00Z",
        ),
    )
    monkeypatch.setattr("pipeline.db.get_balance", lambda uid: 234)
    c = client_factory(user_id="alice")
    body = c.get("/billing/plan").json()
    assert body == {
        "plan": "creator",
        "current_period_end": "2026-06-11T00:00:00Z",
        "cancel_at_period_end": False,
        "balance": 234,
    }


def test_get_transactions_returns_list(client_factory, monkeypatch):
    from pipeline.db import Transaction
    monkeypatch.setattr(
        "pipeline.db.list_transactions",
        lambda uid, limit: [
            Transaction(id="t1", user_id=uid, amount=60, kind="signup_grant",
                        reference_id=None, description=None,
                        created_at="2026-05-11T00:00:00Z"),
            Transaction(id="t2", user_id=uid, amount=-10, kind="run_charge",
                        reference_id="r1", description="1 clip",
                        created_at="2026-05-11T00:01:00Z"),
        ],
    )
    c = client_factory(user_id="alice")
    body = c.get("/billing/transactions").json()
    assert len(body) == 2
    assert body[0]["kind"] == "signup_grant"
    assert body[1]["amount"] == -10


# ---------------------------------------------------------------------------
# T6: pre-flight credit check on run-creation endpoints
# ---------------------------------------------------------------------------

def test_freeform_run_does_not_paywall_zero_balance_user(client_factory, monkeypatch, tmp_path):
    """As of 2026-05-13: script generation is FREE. Users with 0 credits can
    still write scripts; the paywall fires only at /runs/{id}/approve."""
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path))
    monkeypatch.setattr("pipeline.db.get_balance", lambda uid: 0)
    c = client_factory(user_id="alice", role="user")
    r = c.post("/runs/freeform", json={
        "theme": "folkloric",
        "premise": "بئر قديم",
        "max_beats": 8,
    })
    assert r.status_code == 201, f"expected free script gen, got {r.status_code} {r.text}"
    body = r.json()
    assert body["status"] == "awaiting_approval"


def test_freeform_run_passes_when_balance_sufficient(client_factory, monkeypatch, tmp_path):
    """When the user has enough credits, /runs/freeform succeeds — script.json
    lands inline (no spawn needed for the script stage)."""
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path))
    monkeypatch.setattr("pipeline.db.get_balance", lambda uid: 100)
    c = client_factory(user_id="alice", role="user")
    r = c.post("/runs/freeform", json={
        "theme": "folkloric",
        "premise": "بئر قديم",
        "max_beats": 8,
    })
    assert r.status_code == 201
    body = r.json()
    # script.json was written inline by the autouse fixture.
    # FACELESS_OUT_ROOT=tmp_path (no /out suffix), so the run lands at tmp_path/<user>/<id>/.
    assert (tmp_path / "alice" / body["id"] / "script.json").exists()


def test_freeform_run_bypasses_credit_check_for_service_token(client_factory, monkeypatch, tmp_path):
    monkeypatch.setenv("FACELESS_OUT_ROOT", str(tmp_path))
    # Even with balance=0, service tokens should pass through.
    monkeypatch.setattr("pipeline.db.get_balance", lambda uid: 0)
    monkeypatch.setattr("pipeline.api._SPAWN_FN", lambda args, run_dir: 4242)
    c = client_factory(user_id="admin", role="service")
    r = c.post("/runs/freeform", json={
        "theme": "folkloric",
        "premise": "بئر قديم",
        "max_beats": 8,
    })
    assert r.status_code == 201


# ---------------------------------------------------------------------------
# T8: Stripe checkout / portal endpoints
# ---------------------------------------------------------------------------


def test_checkout_subscription_returns_url(client_factory, monkeypatch):
    monkeypatch.setattr(
        "pipeline.stripe_billing.create_subscription_checkout",
        lambda user, plan, s, c: f"https://checkout/{plan}",
    )
    c = client_factory(user_id="alice", role="user")
    r = c.post("/billing/checkout-subscription", json={
        "plan": "starter",
        "success_url": "https://app/success",
        "cancel_url": "https://app/cancel",
    })
    assert r.status_code == 200
    assert r.json() == {"url": "https://checkout/starter"}


def test_checkout_topup_returns_url(client_factory, monkeypatch):
    monkeypatch.setattr(
        "pipeline.stripe_billing.create_topup_checkout",
        lambda user, pack, s, c: f"https://checkout/pack/{pack}",
    )
    c = client_factory(user_id="alice", role="user")
    r = c.post("/billing/checkout-topup", json={
        "pack": "topup_100",
        "success_url": "https://app/success",
        "cancel_url": "https://app/cancel",
    })
    assert r.status_code == 200
    assert r.json()["url"].endswith("/pack/topup_100")


def test_portal_returns_url(client_factory, monkeypatch):
    monkeypatch.setattr(
        "pipeline.stripe_billing.create_portal_session",
        lambda user, return_url: f"https://portal?return={return_url}",
    )
    c = client_factory(user_id="alice", role="user")
    r = c.post("/billing/portal", json={"return_url": "https://app/home"})
    assert r.status_code == 200
    assert "portal" in r.json()["url"]


def test_billing_endpoints_reject_service_tokens(client_factory):
    c = client_factory(user_id="admin", role="service")
    for path, body in [
        ("/billing/checkout-subscription",
         {"plan": "starter", "success_url": "x", "cancel_url": "y"}),
        ("/billing/checkout-topup",
         {"pack": "topup_30", "success_url": "x", "cancel_url": "y"}),
        ("/billing/portal", {"return_url": "x"}),
    ]:
        r = c.post(path, json=body)
        assert r.status_code == 400, f"{path} should reject service token"


def test_stripe_webhook_calls_handler(monkeypatch):
    """The webhook endpoint forwards raw bytes + signature header to the
    handler, with NO bearer auth required."""
    captured = {}
    from pipeline.stripe_billing import WebhookOutcome
    def fake_handle(raw, sig):
        captured["raw"] = raw
        captured["sig"] = sig
        return WebhookOutcome(event_type="checkout.session.completed",
                              handled=True, note="ok")
    monkeypatch.setattr("pipeline.stripe_billing.handle_webhook", fake_handle)
    # No client_factory / bearer here — webhook is unauthenticated.
    from fastapi.testclient import TestClient
    from pipeline.api import app
    c = TestClient(app)
    r = c.post("/stripe/webhook",
               content=b'{"event":"x"}',
               headers={"stripe-signature": "sig=test"})
    assert r.status_code == 200
    body = r.json()
    assert body["received"] is True
    assert body["handled"] is True
    assert captured["raw"] == b'{"event":"x"}'
    assert captured["sig"] == "sig=test"


def test_stripe_webhook_rejects_bad_signature(monkeypatch):
    """Bad signature → 400. Stripe will retry, but at that point it's
    clearly misconfigured or being spoofed."""
    import stripe
    def fake_handle(raw, sig):
        raise stripe.SignatureVerificationError("bad sig", sig)
    monkeypatch.setattr("pipeline.stripe_billing.handle_webhook", fake_handle)
    from fastapi.testclient import TestClient
    from pipeline.api import app
    c = TestClient(app)
    r = c.post("/stripe/webhook", content=b"{}", headers={"stripe-signature": "wrong"})
    assert r.status_code == 400


def test_billing_get_endpoints_bypass_db_for_service_tokens(client_factory, monkeypatch):
    """Service tokens (admin / CLI) have id='admin' which isn't a UUID — querying
    Postgres would 500 with 22P02. The 3 GET billing endpoints must short-circuit
    on role='service' BEFORE hitting the DB."""
    db_was_called = []
    monkeypatch.setattr(
        "pipeline.db.get_balance",
        lambda uid: db_was_called.append(("balance", uid)) or 99,
    )
    monkeypatch.setattr(
        "pipeline.db.get_user_profile",
        lambda uid: db_was_called.append(("profile", uid)) or None,
    )
    monkeypatch.setattr(
        "pipeline.db.list_transactions",
        lambda uid, limit: db_was_called.append(("txs", uid)) or [],
    )

    c = client_factory(user_id="admin", role="service")
    assert c.get("/billing/balance").json() == {"balance": 0}
    assert c.get("/billing/plan").json() == {
        "plan": "free",
        "current_period_end": None,
        "cancel_at_period_end": False,
        "balance": 0,
    }
    assert c.get("/billing/transactions").json() == []

    # Critical: the DB was NEVER called with the synthetic "admin" id.
    assert db_was_called == []
