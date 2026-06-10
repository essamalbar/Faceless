"""HTTP API for the faceless pipeline.

Wraps `run.py` so a mobile app can:
  1. Trigger a new run (writer pass only — pauses for human approval)
  2. Read the generated Arabic script
  3. Approve and start the paid stages (character_sheet + Veo + assembly)
  4. Resume after a transient failure
  5. List past runs and stream their final mp4

Pipeline runs as a subprocess of the API; we never call the orchestrator
in-process because each run takes 10–15 minutes and would block the event
loop. State is derived from filesystem contents (script.json exists, clips
exist, final.mp4 exists, plus a small state.json per run dir for
in-progress info like PID and last error).

Auth: a single bearer token from `FACELESS_API_TOKEN` env var. This is
solo-user software running on the user's Mac — no need for accounts.

Run with:  uv run uvicorn pipeline.api:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Request,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from pipeline.auth import User, require_user, require_user_header_or_query
from pipeline.spawn_backends import LocalSubprocessBackend, select_backend


def _process_alive(pid: int | None, run_dir: Path | None = None) -> bool:
    """Is the spawned worker still running?

    Delegates to the configured spawn backend. For the local-subprocess path
    only `pid` matters; for the Cloud Run Jobs path the backend reads the
    execution resource name out of `run_dir/api_state.json`.

    `run_dir` is optional purely for backwards compatibility with older test
    stubs that monkeypatch this function with a single-arg lambda — when it's
    None we fall back to the local-subprocess behavior (os.kill / waitpid).
    """
    if run_dir is None:
        return LocalSubprocessBackend().is_alive(pid=pid, run_dir=Path("/"))
    return select_backend().is_alive(pid=pid, run_dir=run_dir)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_ROOT = REPO_ROOT / "out"
RUNPY = REPO_ROOT / "run.py"

# Per-model Kie.ai pricing as of May 2026. Keep this in lockstep with the
# config.yaml `kie.model` selection — the budget guard reads the model
# field from script.json (or the loaded config) and looks up the rate
# here so the user-facing dollar figure on the approve gate is accurate
# regardless of which model the project is set to.
_COST_BY_MODEL: dict[str, float] = {
    # Veo family (legacy /api/v1/veo/generate)
    "veo3":       0.40,
    "veo3_fast":  0.10,
    "veo3_lite":  0.05,
    # Kling family (unified /api/v1/jobs/createTask)
    "kling/v2-1-standard":         0.025,
    "kling/v2-1-pro":              0.05,
    "kling/v2-1-master":           0.16,
    "kling/v2-1-master-image-to-video": 0.16,
    "kling-2.6/image-to-video":    0.056,
    "kling-2.6/text-to-video":     0.056,
}
DEFAULT_COST_PER_SECOND_USD = 0.10  # fallback for unmapped models — defensive
FLUX_COST_PER_RUN_USD = 0.05        # Single Flux character sheet per run
BUDGET_BUFFER_RATIO = 1.30          # ~30 % cushion for retries / Kie billing 9.5s when we asked for 9
BUDGET_BUFFER_FLAT_USD = 0.50       # Plus a small flat cushion for the Flux sheet


def _cost_per_second_for_model(model: str) -> float:
    """Look up the per-second USD rate for a Kie.ai model id.

    Falls back to DEFAULT_COST_PER_SECOND_USD for any model not in
    _COST_BY_MODEL (defensive — a misconfigured model name shouldn't
    underbill the budget guard and let the user accidentally overspend).
    """
    return _COST_BY_MODEL.get(model, DEFAULT_COST_PER_SECOND_USD)


# Back-compat alias for the legacy hardcoded value. Existing callers that
# import COST_PER_SECOND_USD keep working; new code uses the lookup.
COST_PER_SECOND_USD = DEFAULT_COST_PER_SECOND_USD


# ---------------------------------------------------------------------------
# State derivation
# ---------------------------------------------------------------------------

RunStatus = Literal[
    "creating",              # process starting, no script yet
    "awaiting_approval",     # script.json present, no character_sheet → user must approve
    "awaiting_veo_approval", # Flux done, character_sheet present, waiting for second approval
    "running_paid",          # character_sheet or clips appearing, paid stages in flight
    "complete",              # final.mp4 present
    "failed",                # state.json says last_error and process is dead
]


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


def _write_state(run_dir: Path, **kwargs) -> None:
    """Read-modify-write of api_state.json, with an atomic rename so a
    concurrent reader (the API serving GET /songs/{id}/status while the
    worker is writing) never sees a half-written file."""
    state = _read_state(run_dir)
    state.update(kwargs)
    state["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    path = _state_path(run_dir)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp.replace(path)




def _compute_max_spend_for_run(run_dir: Path) -> float | None:
    """Sum the script's projected video-model cost so we can pass
    --max-spend to the subprocess. The user already saw the estimate in
    the UI and approved — we shouldn't then trip the in-config cap and
    silently refuse.

    Adds a buffer (`BUDGET_BUFFER_RATIO` × `BUDGET_BUFFER_FLAT_USD`) so
    retries and Kie's tendency to bill 9.5 s when we requested 9 s don't
    push us over.

    Model-aware: reads kie.model from config.yaml so switching from
    veo3_fast → kling/v2-1-pro auto-updates the budget without manual edit.
    """
    script_path = run_dir / "script.json"
    if not script_path.exists():
        return None
    try:
        doc = json.loads(script_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    total_seconds = sum(
        float(b.get("clip_duration_s", 8.0))
        for b in (doc.get("beats") or [])
    )
    if total_seconds <= 0:
        return None
    rate = _cost_per_second_for_model(_active_video_model())
    return round(
        total_seconds * rate * BUDGET_BUFFER_RATIO + BUDGET_BUFFER_FLAT_USD,
        2,
    )


def _active_video_model() -> str:
    """Read kie.model from config.yaml so cost calculations follow the
    deployed setting. Defensive: returns 'veo3_fast' on any load failure
    (matches the legacy hardcoded behavior so we never overbill).

    load_config requires an explicit path — we pass the repo's
    config.yaml since the API runs from REPO_ROOT in both local dev
    and the Cloud Run image. Override via FACELESS_CONFIG env var when
    a different config is shipped (used by tests + Cloud Run Job).
    """
    try:
        from pipeline.config import load_config
        cfg_path_str = os.environ.get(
            "FACELESS_CONFIG",
            str(REPO_ROOT / "config.yaml"),
        )
        cfg = load_config(Path(cfg_path_str))
        return getattr(cfg.kie, "model", "veo3_fast")
    except Exception:
        return "veo3_fast"


_ERROR_LINE_RE = re.compile(r"\bERROR\b", re.IGNORECASE)


# Map well-known raw error patterns → "what the user should do" copy.
# Keep the raw error in `last_error` for transparency; present this hint
# alongside it. Order matters — first match wins.
_ERROR_HINTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"BudgetExceededError|exceeds cap", re.IGNORECASE),
     "Veo cost exceeded the safety cap. The cap auto-bumps based on the "
     "script's size when you Approve via the app — tap Resume and it should "
     "go through. If it persists, your script may have unusually long beats."),

    (re.compile(r"safety filters|content was flagged", re.IGNORECASE),
     "Veo's safety filter rejected this beat. Edit the script to soften the "
     "wording — avoid explicit references to death (\"يموت\", \"يقتل\"), wounds "
     "(\"جرح\"), or violence. Use indirect phrasing (\"راح\", \"خلصت أيامه\")."),

    (re.compile(r"unable to generate audio", re.IGNORECASE),
     "Veo's TTS couldn't speak this line. Usually means the dialogue is too "
     "short or whisper-direction was too strong. Make the line at least 6 "
     "words and remove \"بهمس\"/\"weak\"/\"barely\" type stage notes."),

    (re.compile(r"Connection reset|connection refused|TLS|tempfile\.aiquickdraw", re.IGNORECASE),
     "Your network blocked the Kie.ai CDN. Either turn on your VPN, or "
     "deploy the Cloudflare Worker proxy in cloudflare-worker/ and set "
     "KIE_DOWNLOAD_PROXY in .env (one-time, no more VPN needed)."),

    (re.compile(r"download failed after \d+ attempts", re.IGNORECASE),
     "Couldn't download a generated clip after retries. Network blip or Kie "
     "CDN hiccup. Tap Resume — completed clips are kept, only the missing "
     "ones re-render."),

    (re.compile(r"KIE_API_KEY not set|ANTHROPIC_API_KEY not set|GROQ_API_KEY not set",
                re.IGNORECASE),
     "An API key is missing from .env. Restart the launcher (./scripts/run-app.sh) "
     "after adding it — the API server caches env vars at startup."),

    (re.compile(r"writer returned \d+ beats, below min_beats", re.IGNORECASE),
     "The script writer returned fewer beats than required. Try a more "
     "detailed premise or switch to Paste Script and write the beats yourself."),

    (re.compile(r"timed out|timeout", re.IGNORECASE),
     "A pipeline stage timed out. Tap Resume — completed work is kept."),

    (re.compile(r"successFlag=2", re.IGNORECASE),
     "Veo job was rejected by Kie.ai (often a moderation or auth issue). "
     "Check the log for details, then Resume to retry."),

    (re.compile(r"successFlag=3", re.IGNORECASE),
     "Veo's generation failed (transient or content-flag). Tap Resume — if "
     "it keeps failing on the same clip, edit that beat's wording."),

    # User-facing: the upstream generation provider (Kie.ai) ran out of credit.
    # In the SaaS era this is what an end-user sees when their OWN credit
    # balance hits zero — we route them to the billing screen rather than
    # exposing the upstream error. The wording stays generic ("video credits")
    # so the same hint covers both the operator-pays-Kie and the end-user-
    # pays-Stripe paths.
    (re.compile(
        r"Credits? insufficient|Your current balance isn'?t enough|"
        r"code['\":\s]+402|out of credits",
        re.IGNORECASE,
     ),
     "You're out of video credits. Top up your plan and tap Resume — "
     "your script and characters are saved, only the unfinished clips "
     "will re-render."),

    (re.compile(r"cancelled by user", re.IGNORECASE),
     "You discarded this run. Use the Discard button on the run-detail "
     "screen to remove it from the gallery, or Resume to continue."),
]


def _hint_for_error(raw: str | None) -> str | None:
    if not raw:
        return None
    for pattern, hint in _ERROR_HINTS:
        if pattern.search(raw):
            return hint
    return None


def _last_error_from_log(run_dir: Path, max_chars: int = 400) -> str | None:
    """Find the most recent ERROR line in either log file the subprocess
    might have written so the UI can surface why a run failed.

    Both files are checked: `run.log` (the orchestrator's own runlog) and
    `api_subprocess.log` (uvicorn-side capture of stdout/stderr — Python
    logging defaults like `ERROR:pipeline:…` and uvicorn's `ERROR:` prefix
    don't have a leading space so we can't filter on `" ERROR "`)."""
    candidates: list[str] = []
    for fname in ("run.log", "api_subprocess.log"):
        path = run_dir / fname
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for ln in text.splitlines():
            if _ERROR_LINE_RE.search(ln):
                candidates.append(ln.strip())
    if not candidates:
        return None
    msg = candidates[-1]
    # Strip a leading "<timestamp> ERROR " or "ERROR:" prefix for readability
    msg = re.sub(r"^\S+\s+ERROR\s*", "", msg)
    msg = re.sub(r"^ERROR:\s*", "", msg)
    return msg[:max_chars]


def derive_status(run_dir: Path) -> RunStatus:
    """Filesystem-driven status — no in-memory state. Order matters."""
    if (run_dir / "final.mp4").exists():
        return "complete"
    state = _read_state(run_dir)
    pid = state.get("pid")
    last_error = state.get("last_error")
    process_running = _process_alive(pid, run_dir)
    script_exists = (run_dir / "script.json").exists()
    sheet_exists = (run_dir / "character_sheet.png").exists()
    clips_dir = run_dir / "clips"
    has_clips = clips_dir.exists() and any(clips_dir.glob("*.mp4"))

    if last_error and not process_running:
        return "failed"
    if not script_exists:
        return "creating" if process_running else "failed"
    # Script is on disk.
    # NEW: Flux finished, no clips yet, subprocess exited → second approval gate.
    if sheet_exists and not has_clips and not process_running:
        if _last_error_from_log(run_dir):
            return "failed"
        return "awaiting_veo_approval"
    if not sheet_exists and not has_clips:
        if process_running:
            # Subprocess still alive past the script stage but no character
            # sheet yet — Flux is generating. Show this as paid-stage progress.
            return "running_paid"
        # Subprocess died before producing a character sheet. If the log
        # has an ERROR (budget cap, safety filter, etc.) treat as failed
        # rather than stuck on awaiting_approval forever.
        if _last_error_from_log(run_dir):
            return "failed"
        # Genuinely paused for human approval
        return "awaiting_approval"
    # Catch-all: also covers (sheet exists + process still alive + no clips yet),
    # i.e. the brief window between Flux finishing and Veo starting in the same
    # subprocess. The catch-all returns "running_paid" via process_running below.
    return "running_paid" if process_running else (
        "complete" if (run_dir / "final.mp4").exists() else "failed"
    )


# ---------------------------------------------------------------------------
# Request / response shapes
# ---------------------------------------------------------------------------

VALID_THEMES = {
    "domestic", "wilderness", "urban", "workplace",
    "travel", "folkloric", "tech", "memory",
}


class CreateRunRequest(BaseModel):
    theme: str = Field(..., description="Theme tag, e.g. 'folkloric'")
    premise: str = Field(..., min_length=4, description="Arabic premise / seed")
    max_beats: int | None = Field(None, ge=1, le=20,
                                  description="Cap script to ≤ N beats (test runs)")


class CreateSongRequest(BaseModel):
    theme: str
    custom_lyrics: str | None = None
    style_hint: str | None = None
    language: str = "ar"
    # Voice-control (optional). Defaults to "m" (male) to match the
    # reference quality target — the production user has been re-rolling
    # to get male voices manually. See pipeline/song.py submit_song_job.
    vocal_gender: str | None = "m"  # 'm' | 'f' | None
    persona_id: str | None = None   # for pinned-voice future use
    # Optional Suno model override. Validated against
    # _ALLOWED_SUNO_MODELS below. None → use config default (V5_5).
    suno_model: str | None = None


# Whitelist of Suno model ids the user can pick from. V3_5 is the
# obvious-AI sound and explicitly excluded per spec quality gate.
_ALLOWED_SUNO_MODELS = frozenset({"V5_5", "V5", "V4_5", "V4"})


class SongScriptResponse(BaseModel):
    title: str
    lyrics: str
    style_prompt: str
    cover_prompt: str
    language: str
    cost_credits: int
    cost_usd: float


class CreatePersonaRequest(BaseModel):
    name: str
    description: str
    take: int | None = None  # defaults to the run's chosen_take


class PersonaSummary(BaseModel):
    id: str            # the Kie personaId
    name: str
    description: str
    source_run_id: str
    source_take: int
    created_at: str


class ShareInfo(BaseModel):
    token: str
    url: str  # the public /p/{token} URL


class SongRunSummary(BaseModel):
    id: str
    status: str
    kind: str  # always "song"
    title: str | None
    theme: str | None
    created_at: str
    has_video: bool
    chosen_take: int | None = None
    last_error: str | None = None
    # Which stage was running when failure hit:
    # generating_song / generating_cover / assembling. Lets the UI
    # show actionable hints (e.g. "Suno timeout — retry will re-charge"
    # vs "cover failed — retry is free").
    failure_stage: str | None = None


class RunProgress(BaseModel):
    """Live progress info for the UI's progress bar."""
    stage: str  # "script", "character_sheet", "video", "captions", "assemble"
    clips_done: int  # 0..N — how many beats have a clip on disk
    clips_total: int  # 0..N — script.beats length once known


class RunSummary(BaseModel):
    id: str
    status: RunStatus
    title: str | None = None
    theme: str | None = None
    premise: str | None = None
    created_at: str | None = None
    has_video: bool = False
    last_error: str | None = None
    error_hint: str | None = None  # human-readable "what to do" for known failures
    progress: RunProgress | None = None


class ScriptBeat(BaseModel):
    arabic: str
    english_motion: str
    speaker: str
    clip_duration_s: float
    character_name: str = ""           # NEW — free-form Arabic name, empty on legacy scripts


class ScriptResponse(BaseModel):
    title: str
    beats: list[ScriptBeat]
    target_duration_s: float
    estimated_cost_usd: float
    character_descriptions: dict[str, str] = {}  # NEW — per-character physical descriptions


class BalanceResponse(BaseModel):
    balance: int


class PlanResponse(BaseModel):
    plan: str                         # 'free' | 'starter' | 'creator' | 'pro'
    current_period_end: str | None    # ISO timestamp, null on 'free'
    cancel_at_period_end: bool = False  # true if user scheduled a cancel
    balance: int


class TransactionRow(BaseModel):
    id: str
    amount: int
    kind: str
    reference_id: str | None
    description: str | None
    created_at: str


class CheckoutSubscriptionRequest(BaseModel):
    plan: str = Field(..., description="'starter' | 'creator' | 'pro'")
    success_url: str
    cancel_url: str


class CheckoutTopupRequest(BaseModel):
    pack: str = Field(..., description="'topup_30' | 'topup_100' | 'topup_300'")
    success_url: str
    cancel_url: str


class PortalRequest(BaseModel):
    return_url: str


class CheckoutResponse(BaseModel):
    url: str


# ---------------------------------------------------------------------------
# Subprocess spawning — overridable in tests
# ---------------------------------------------------------------------------

from pipeline.spawn_backends import select_backend


def _spawn(args: list[str], run_dir: Path) -> int:
    """Start `run.py` in the background via the configured spawn backend
    (local Popen or Cloud Run Jobs — see pipeline.spawn_backends)."""
    backend = select_backend()
    return backend.spawn(
        args=args,
        run_dir=run_dir,
        runpy_path=RUNPY,
        repo_root=REPO_ROOT,
    )


# Indirection so tests can replace with a no-op
_SPAWN_FN = _spawn


def set_spawn_fn(fn) -> None:
    """Tests use this to replace _spawn with a stub that doesn't actually
    fork or call gcloud. The stub is responsible for whatever fake
    artifacts the test scenario expects."""
    global _SPAWN_FN
    _SPAWN_FN = fn


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Faceless Pipeline API",
    description="Mobile-app backend for the faceless TikTok generator.",
    version="0.1.0",
)

# CORS — the Flutter web app loads from localhost:5xxxx (or a Cloudflare
# Tunnel URL) and calls this API on a different origin. Browsers block
# cross-origin requests unless the server explicitly opts in. The bearer
# token is what actually gates access; the CORS allowlist is permissive
# because this is solo-user software running on the operator's Mac.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # we don't use cookies — token is in Authorization header
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


def _out_root() -> Path:
    return Path(os.environ.get("FACELESS_OUT_ROOT", DEFAULT_OUT_ROOT))


def _user_runs_root(user: "User") -> Path:
    """Per-user runs directory. All endpoints scope file reads/writes here."""
    return _out_root() / user.id


def _make_run_id(root: Path | None = None) -> str:
    if root is None:
        root = _out_root()
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M%S")
    base = root / ts
    suffix = 0
    while base.exists():
        suffix += 1
        base = root / f"{ts}-{suffix}"
    return base.name


_RUN_ID_RE = re.compile(r"^[A-Za-z0-9_\-]+$")


def _run_dir(run_id: str, user: "User") -> Path:
    """Resolve a run id to its on-disk directory under the user's runs root.

    Strict allowlist — only the chars our generator emits (digits, letters,
    `-`, `_`). This blocks `..`, `/`, NUL, backslash, control chars, and
    anything else that could escape the out-root."""
    if not _RUN_ID_RE.fullmatch(run_id):
        raise HTTPException(400, "invalid run_id")
    p = _user_runs_root(user) / run_id
    if not p.exists():
        raise HTTPException(404, f"run {run_id} not found")
    return p


def _cost_estimate_usd(beats: list[dict]) -> float:
    """Per-beat × seconds × active-model rate + one Flux character sheet.

    Reads the active video model from config.yaml so the dollar figure on
    /runs/{id}/script (which the Flutter approval gate displays) tracks the
    deployed model. Switching from Veo to Kling drops this by ~50–75%.
    """
    total_seconds = sum(float(b.get("clip_duration_s", 8.0)) for b in beats)
    rate = _cost_per_second_for_model(_active_video_model())
    return round(total_seconds * rate + FLUX_COST_PER_RUN_USD, 2)


def _build_llm():
    """Same LLM-selection logic as run.py:_build_gemini. Anthropic → Groq → Gemini.
    Inlined here so the script-gen call doesn't require importing run.py (which
    pulls every pipeline stage)."""
    import os
    if os.environ.get("ANTHROPIC_API_KEY"):
        from pipeline.llm_anthropic import AnthropicClient
        return AnthropicClient()
    if os.environ.get("GROQ_API_KEY"):
        from pipeline.llm import GroqClient
        return GroqClient()
    from pipeline.llm import GeminiClient
    return GeminiClient()


def _build_song_llm():
    """Same router as _build_llm — Anthropic > Groq > Gemini."""
    return _build_llm()


def _generate_script_inline(
    *,
    run_dir: Path,
    theme: str,
    premise: str,
    controls: dict,
) -> None:
    """Synchronously generate the Arabic script + persist seed.json + script.json.

    Called by /runs and /runs/freeform instead of spawning the Cloud Run Job
    just to write the script. Skips the ~2-min Job cold-start; the Anthropic
    call itself takes ~25-35 sec. HTTPException(500) on LLM failure so the
    Flutter UI surfaces it cleanly rather than leaving an empty run_dir.
    """
    from pipeline.types import ThemeSeed
    from pipeline.seed import manual_seed
    from pipeline.script_freeform import FreeformControls, generate_freeform_script

    seed = manual_seed(theme, premise)
    seed_path = run_dir / "seed.json"
    seed_path.write_text(
        json.dumps(seed.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    ff_controls = FreeformControls(
        dialect=controls["dialect"],
        art_style=controls["art_style"],
        character_template=controls["character_template"],
        ending_type=controls["ending_type"],
        num_beats=int(controls["num_beats"]),
        per_beat_seconds=int(controls["per_beat_seconds"]),
        narration_style=controls["narration_style"],
    )

    try:
        llm = _build_llm()
        script = generate_freeform_script(llm, seed, ff_controls)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Script generation failed: {e}",
        ) from None

    # Cross-clip coherence pass — rewrites english_motion on any beat that
    # would cause Veo to swap roles or jump locations. Runs BEFORE the user
    # reviews the script, so what they approve is what gets rendered.
    # Failures (Anthropic outage, etc) fall back silently to the raw script.
    from pipeline.coherence_pass import apply_coherence_pass
    marker = run_dir / "coherence_pass_v1.applied"
    if not marker.exists():
        try:
            script = apply_coherence_pass(script, llm)
            marker.write_text("v1", encoding="utf-8")
        except Exception:
            # Never block run creation on coherence-pass failure — the user
            # can still approve and render with the raw script.
            pass

    script_path = run_dir / "script.json"
    script_path.write_text(
        json.dumps(script.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _estimate_credits_for_request(req) -> int:
    """Estimate the credits a request will consume.

    1 credit = 1 clip (one beat in the script). The actual charge happens
    per-clip in the worker; this is a worst-case pre-flight that matches the
    number of beats the writer will emit.
    """
    beats = getattr(req, "beats", None)
    if beats:
        return len(beats)
    return int(
        getattr(req, "max_beats", None)
        or getattr(req, "num_beats", None)
        or 8,
    )


def _clips_needed_for_run(run_dir: Path) -> int:
    """Count remaining beats that still need a clip generated. Used by the
    approve endpoint to compute the pre-flight credit cost. Reads from
    script.json (which is already on disk by approval time)."""
    script_path = run_dir / "script.json"
    if not script_path.exists():
        return 0
    try:
        doc = json.loads(script_path.read_text(encoding="utf-8"))
    except Exception:
        return 0
    beats = doc.get("beats") or []
    if not beats:
        return 0
    clips_dir = run_dir / "clips"
    already = 0
    if clips_dir.exists():
        already = sum(1 for _ in clips_dir.glob("*.mp4"))
    return max(0, len(beats) - already)


def _raise_402_insufficient_credits(balance: int, required: int) -> None:
    """Raise HTTPException(402) with the structured detail the Flutter paywall
    dialog expects. Vendor-agnostic copy — never mentions Veo/Flux/Kie."""
    raise HTTPException(
        status_code=status.HTTP_402_PAYMENT_REQUIRED,
        detail={
            "code": "insufficient_credits",
            "message": (
                "This video needs more credits than you have. "
                "Subscribe to continue — your script is saved and ready."
            ),
            "balance": balance,
            "required": required,
        },
    )


def _preflight_approve_credits(run_dir: Path, user: "User") -> None:
    """Credit check that runs when the user clicks Approve, NOT when they
    generate the script. Script generation is free; the paid stages (paid
    video clip generation + assembly) require credits.

    Service tokens (CLI / admin) bypass — they don't consume credits.
    Raises HTTPException(402) if the script's clip count exceeds the user's
    balance.
    """
    if user.role == "service":
        return
    from pipeline.db import get_balance
    required = _clips_needed_for_run(run_dir)
    balance = get_balance(user.id)
    if balance < required:
        _raise_402_insufficient_credits(balance, required)


@app.get("/healthz")
@app.get("/health")
def healthz():
    return {"ok": True}


@app.get(
    "/runs",
    response_model=list[RunSummary],
    dependencies=[Depends(require_user)],
)
def list_runs(user: User = Depends(require_user)):
    out = _user_runs_root(user)
    if not out.exists():
        return []
    runs: list[RunSummary] = []
    for p in sorted(out.iterdir()):
        if not p.is_dir():
            continue
        runs.append(_summarize(p))
    return runs


# ---------------------------------------------------------------------------
# Billing — read-only (balance, plan, transactions).
# Write endpoints (checkout / portal / webhook) live below in T7-T9.
# ---------------------------------------------------------------------------


@app.get(
    "/billing/balance",
    response_model=BalanceResponse,
    dependencies=[Depends(require_user)],
)
def get_balance_endpoint(user: User = Depends(require_user)):
    # Service tokens (CLI / admin) aren't real billing customers and their
    # user_id ("admin") isn't a UUID — querying Postgres would 500 with 22P02.
    # Skip the DB and report 0; the worker's service-token bypass means
    # the admin never actually spends anything anyway.
    if user.role == "service":
        return BalanceResponse(balance=0)
    from pipeline.db import get_balance
    return BalanceResponse(balance=get_balance(user.id))


@app.get(
    "/billing/plan",
    response_model=PlanResponse,
    dependencies=[Depends(require_user)],
)
def get_plan_endpoint(user: User = Depends(require_user)):
    if user.role == "service":
        return PlanResponse(
            plan="free",
            current_period_end=None,
            cancel_at_period_end=False,
            balance=0,
        )
    from pipeline.db import get_balance, get_user_profile
    profile = get_user_profile(user.id)
    return PlanResponse(
        plan=(profile.current_plan if profile else "free"),
        current_period_end=(profile.current_period_end if profile else None),
        cancel_at_period_end=(profile.cancel_at_period_end if profile else False),
        balance=get_balance(user.id),
    )


@app.get(
    "/billing/transactions",
    response_model=list[TransactionRow],
    dependencies=[Depends(require_user)],
)
def get_transactions_endpoint(
    user: User = Depends(require_user),
    limit: int = 50,
):
    if user.role == "service":
        return []
    from pipeline.db import list_transactions
    rows = list_transactions(user.id, limit=min(limit, 200))
    return [
        TransactionRow(
            id=t.id, amount=t.amount, kind=t.kind,
            reference_id=t.reference_id, description=t.description,
            created_at=t.created_at,
        )
        for t in rows
    ]


@app.post(
    "/billing/checkout-subscription",
    response_model=CheckoutResponse,
    dependencies=[Depends(require_user)],
)
def billing_checkout_subscription(
    req: CheckoutSubscriptionRequest,
    user: User = Depends(require_user),
):
    if user.role == "service":
        raise HTTPException(400, "service tokens have no subscription")
    from pipeline.stripe_billing import create_subscription_checkout
    try:
        url = create_subscription_checkout(user, req.plan, req.success_url, req.cancel_url)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    return CheckoutResponse(url=url)


@app.post(
    "/billing/checkout-topup",
    response_model=CheckoutResponse,
    dependencies=[Depends(require_user)],
)
def billing_checkout_topup(
    req: CheckoutTopupRequest,
    user: User = Depends(require_user),
):
    if user.role == "service":
        raise HTTPException(400, "service tokens have no top-ups")
    from pipeline.stripe_billing import create_topup_checkout
    try:
        url = create_topup_checkout(user, req.pack, req.success_url, req.cancel_url)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    return CheckoutResponse(url=url)


@app.post(
    "/billing/portal",
    response_model=CheckoutResponse,
    dependencies=[Depends(require_user)],
)
def billing_portal(req: PortalRequest, user: User = Depends(require_user)):
    if user.role == "service":
        raise HTTPException(400, "service tokens have no portal")
    from pipeline.stripe_billing import create_portal_session
    url = create_portal_session(user, req.return_url)
    return CheckoutResponse(url=url)


@app.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    """Stripe → us. No bearer auth; signature is the proof.

    Returns 200 even for ignored event types so Stripe doesn't keep retrying;
    400 only for bad signatures (treat as malicious / misconfigured).
    """
    raw = await request.body()
    signature = request.headers.get("stripe-signature", "")
    from pipeline.stripe_billing import handle_webhook
    import stripe as _stripe
    try:
        outcome = handle_webhook(raw, signature)
    except _stripe.SignatureVerificationError:
        raise HTTPException(400, "invalid signature")
    return {"received": True, "handled": outcome.handled, "note": outcome.note}


def _derive_progress(run_dir: Path, status: str) -> RunProgress | None:
    """Compute live progress from filesystem artifacts.

    Stage detection:
      - no script.json    → "script"
      - no character_sheet → "character_sheet"
      - clips < total     → "video" (with clips_done/total)
      - no final.mp4      → "captions" or "assemble"
      - final.mp4 exists  → done (returns None)
    """
    if status == "complete":
        return None
    script_path = run_dir / "script.json"
    if not script_path.exists():
        return RunProgress(stage="script", clips_done=0, clips_total=0)
    try:
        doc = json.loads(script_path.read_text(encoding="utf-8"))
        clips_total = len(doc.get("beats") or [])
    except Exception:
        clips_total = 0
    if not (run_dir / "character_sheet.png").exists():
        return RunProgress(
            stage="character_sheet", clips_done=0, clips_total=clips_total,
        )
    clips_dir = run_dir / "clips"
    clips_done = (
        len(list(clips_dir.glob("*.mp4"))) if clips_dir.exists() else 0
    )
    if clips_done < clips_total:
        return RunProgress(
            stage="video", clips_done=clips_done, clips_total=clips_total,
        )
    if not (run_dir / "captions.ar.ass").exists():
        return RunProgress(
            stage="captions", clips_done=clips_done, clips_total=clips_total,
        )
    return RunProgress(
        stage="assemble", clips_done=clips_done, clips_total=clips_total,
    )


def _summarize(run_dir: Path) -> RunSummary:
    state = _read_state(run_dir)
    script_path = run_dir / "script.json"
    title = None
    theme = None
    if script_path.exists():
        try:
            doc = json.loads(script_path.read_text(encoding="utf-8"))
            title = doc.get("title")
            theme = doc.get("theme")
        except Exception:
            pass
    seed_path = run_dir / "seed.json"
    premise = None
    if seed_path.exists():
        try:
            premise = json.loads(seed_path.read_text(encoding="utf-8")).get("premise")
        except Exception:
            pass
    status = derive_status(run_dir)
    last_error = state.get("last_error")
    if not last_error and status == "failed":
        last_error = _last_error_from_log(run_dir)
    return RunSummary(
        id=run_dir.name,
        status=status,
        title=title,
        theme=theme,
        premise=premise,
        created_at=state.get("created_at"),
        has_video=(run_dir / "final.mp4").exists(),
        last_error=last_error,
        error_hint=_hint_for_error(last_error) if status == "failed" else None,
        progress=_derive_progress(run_dir, status),
    )


_DEFAULT_GLOBAL_SETTING = (
    "3D Pixar animation, anthropomorphic fruit characters as humans, "
    "cinematic dramatic fantasy episode, dramatic emotional lighting, "
    "vertical 9:16, high detail"
)


class PasteScriptBeat(BaseModel):
    arabic: str
    english_motion: str
    speaker: str
    clip_duration_s: float = 8.0
    character_name: str = ""           # NEW — free-form Arabic name, empty on legacy scripts


class CreateFromScriptRequest(BaseModel):
    title: str = Field(..., min_length=1)
    theme: str
    premise: str = Field(default="", description="optional context — saved to seed.json")
    music_mood: str = Field(default="dread")
    global_setting: str | None = None
    beats: list[PasteScriptBeat] = Field(..., min_length=1)


class ParseScriptRequest(BaseModel):
    raw_text: str = Field(..., min_length=4)
    target_beats: int = Field(default=8, ge=4, le=15,
                              description="Target beats for the LLM splitter "
                                          "(ignored on the regex path)")


class ParseScriptResponse(BaseModel):
    title: str
    beats: list[PasteScriptBeat]
    parse_method: Literal["regex", "llm_split", "naive_fallback"]


def _get_splitter_llm():
    """Lazy-import + return the configured LLM client. Indirection point so
    tests can monkeypatch this without touching the actual router."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        from pipeline.llm_anthropic import AnthropicClient
        return AnthropicClient()
    if os.environ.get("GROQ_API_KEY"):
        from pipeline.llm_groq import GroqClient
        return GroqClient()
    from pipeline.llm import GeminiClient
    return GeminiClient()


@app.post(
    "/runs/parse-script",
    response_model=ParseScriptResponse,
    dependencies=[Depends(require_user)],
)
def parse_script(req: ParseScriptRequest):
    """Hybrid parser. Step 1: try the regex parser (fast, free, exact for
    structured markdown). If it found ≥2 dialogue beats, return that result.
    Otherwise step 2: send the prose to the LLM splitter with a verbatim
    guard. If even that fails, the splitter falls back to a naive sentence
    split — the user always gets >1 beat."""
    from pipeline.script_parser import parse_episode_markdown
    from pipeline.script_splitter import (
        NAIVE_FALLBACK_SENTINEL,
        split_prose_into_beats,
    )
    parsed = parse_episode_markdown(req.raw_text)
    dialogue_beats = [b for b in parsed.beats if b.arabic.strip()]
    if len(dialogue_beats) >= 2:
        return ParseScriptResponse(
            title=parsed.title,
            beats=[
                PasteScriptBeat(
                    arabic=b.arabic, english_motion=b.english_motion,
                    speaker=b.speaker, clip_duration_s=b.clip_duration_s,
                    character_name=b.character_name,
                )
                for b in parsed.beats
            ],
            parse_method="regex",
        )
    # Regex miss — fall through to LLM splitter
    llm = _get_splitter_llm()
    split_beats = split_prose_into_beats(
        llm, req.raw_text,
        target_beats=req.target_beats, per_beat_seconds=8,
    )
    is_naive = any(
        b.english_motion == NAIVE_FALLBACK_SENTINEL
        for b in split_beats
    )
    return ParseScriptResponse(
        title=parsed.title or "Untitled",
        beats=[
            PasteScriptBeat(
                arabic=b.arabic, english_motion=b.english_motion,
                speaker=b.speaker, clip_duration_s=b.clip_duration_s,
                character_name=b.character_name,
            )
            for b in split_beats
        ],
        parse_method="naive_fallback" if is_naive else "llm_split",
    )


@app.post(
    "/runs/from-script",
    response_model=RunSummary,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_user)],
)
def create_run_from_script(req: CreateFromScriptRequest, user: User = Depends(require_user)):
    """Create a run with a HAND-WRITTEN script (no LLM call). Use this when
    you already have the exact Arabic dialogue + scene descriptions and want
    Veo to render them verbatim — the writer/critique pass cannot rewrite
    your text, and you skip ~$0.05 of LLM cost.

    The run lands in `awaiting_approval` immediately; the same Edit / Approve
    flow applies, so you can still tweak before paying for Veo."""
    # Script generation is free for all signed-in users. The paywall fires
    # in /runs/{id}/approve when they try to render the paid stages.
    if req.theme not in VALID_THEMES:
        raise HTTPException(400, f"theme must be one of {sorted(VALID_THEMES)}")
    for i, b in enumerate(req.beats, start=1):
        if not (b.speaker or "").strip():
            raise HTTPException(400, f"beat {i}: speaker cannot be empty")
        if not b.english_motion.strip():
            raise HTTPException(400, f"beat {i}: english_motion is required")

    run_id = _make_run_id()
    run_dir = _user_runs_root(user) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    seed = {"theme": req.theme, "premise": req.premise or req.title}
    (run_dir / "seed.json").write_text(
        json.dumps(seed, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    script = {
        "title": req.title,
        "theme": req.theme,
        "global_setting": req.global_setting or _DEFAULT_GLOBAL_SETTING,
        "music_mood": req.music_mood or "dread",
        "hook": req.title,
        "story": "",
        "word_count": 0,
        "target_duration_s": round(
            sum(b.clip_duration_s for b in req.beats), 2,
        ),
        "story_combined": " ".join(b.arabic for b in req.beats if b.arabic),
        "beats": [
            {
                "arabic": b.arabic,
                "english_motion": b.english_motion,
                "speaker": b.speaker.strip().lower(),
                "clip_duration_s": float(b.clip_duration_s),
                "character_name": b.character_name,
            }
            for b in req.beats
        ],
    }
    (run_dir / "script.json").write_text(
        json.dumps(script, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_state(
        run_dir,
        pid=None,
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        last_error=None,
        last_action="create_run_from_script",
    )
    return _summarize(run_dir)


@app.post(
    "/runs",
    response_model=RunSummary,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_user)],
)
def create_run(req: CreateRunRequest, user: User = Depends(require_user)):
    """Legacy endpoint — proxies to the freeform pipeline with
    Sunstoriz-style defaults. Kept for back-compat with old API clients;
    new clients should call POST /runs/freeform directly with their
    chosen controls."""
    # Script generation is free for all signed-in users. The paywall fires
    # in /runs/{id}/approve when they try to render the paid stages.
    if req.theme not in VALID_THEMES:
        raise HTTPException(400, f"theme must be one of {sorted(VALID_THEMES)}")

    run_id = _make_run_id()
    run_dir = _user_runs_root(user) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # Persist freeform controls so reroll/approve survive (matches /runs/freeform)
    controls_doc = {
        "dialect": "syrian",
        "art_style": "pixar_3d",
        "character_template": "fruit_sunstoriz",
        "ending_type": "ai_choose",
        "num_beats": req.max_beats or 8,
        "per_beat_seconds": 8,
        "narration_style": "first_person_monologue",
    }
    (run_dir / "freeform_controls.json").write_text(
        json.dumps(controls_doc, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    _generate_script_inline(
        run_dir=run_dir,
        theme=req.theme,
        premise=req.premise,
        controls=controls_doc,
    )
    _write_state(
        run_dir,
        pid=None,
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        last_error=None,
        last_action="create_run",
    )
    return _summarize(run_dir)


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
    narration_style: Literal["cinematic", "first_person_monologue",
                             "ai_choose"] = "cinematic"


@app.post(
    "/runs/freeform",
    response_model=RunSummary,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_user)],
)
def create_freeform_run(req: CreateFreeformRunRequest, user: User = Depends(require_user)):
    """Create a new run and synchronously generate its Arabic script.

    Originally this spawned a Cloud Run Job with `--pause-after-script` and
    let the worker write script.json before exiting. That meant every script
    paid a ~2-min Job cold-start, so the user waited 2:30+ to see the script.
    Now we generate the script INLINE in this endpoint (~30 sec — pure
    Anthropic latency) and only spawn the Job at approval time for the paid
    stages (Flux + Veo). Script regeneration / rerolls still flow through
    the worker.
    """
    # Script generation is free for all signed-in users. The paywall fires
    # in /runs/{id}/approve when they try to render the paid stages.
    if req.theme not in VALID_THEMES:
        raise HTTPException(400, f"theme must be one of {sorted(VALID_THEMES)}")

    run_id = _make_run_id()
    run_dir = _user_runs_root(user) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    controls_doc = {
        "dialect": req.dialect,
        "art_style": req.art_style,
        "character_template": req.character_template,
        "ending_type": req.ending_type,
        "num_beats": req.num_beats,
        "per_beat_seconds": req.per_beat_seconds,
        "narration_style": req.narration_style,
    }
    (run_dir / "freeform_controls.json").write_text(
        json.dumps(controls_doc, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    _generate_script_inline(
        run_dir=run_dir,
        theme=req.theme,
        premise=req.premise,
        controls=controls_doc,
    )
    _write_state(
        run_dir,
        pid=None,  # no worker spawned yet — happens at approval time
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        last_error=None,
        last_action="create_freeform_run",
    )
    return _summarize(run_dir)


@app.get(
    "/runs/{run_id}",
    response_model=RunSummary,
    dependencies=[Depends(require_user)],
)
def get_run(run_id: str, user: User = Depends(require_user)):
    return _summarize(_run_dir(run_id, user))


@app.get(
    "/runs/{run_id}/script",
    response_model=ScriptResponse,
    dependencies=[Depends(require_user)],
)
def get_script(run_id: str, user: User = Depends(require_user)):
    run_dir = _run_dir(run_id, user)
    script_path = run_dir / "script.json"
    if not script_path.exists():
        raise HTTPException(409, "script not generated yet")
    doc = json.loads(script_path.read_text(encoding="utf-8"))
    beats = doc.get("beats") or []
    return ScriptResponse(
        title=str(doc.get("title", "")),
        beats=[
            ScriptBeat(
                arabic=str(b.get("arabic", "")),
                english_motion=str(b.get("english_motion", "")),
                speaker=str(b.get("speaker", "narrator")),
                clip_duration_s=float(b.get("clip_duration_s", 8.0)),
                character_name=str(b.get("character_name", "")),
            )
            for b in beats
        ],
        target_duration_s=float(doc.get("target_duration_s", 0.0)),
        estimated_cost_usd=_cost_estimate_usd(beats),
        character_descriptions=dict(doc.get("character_descriptions") or {}),
    )


@app.get(
    "/runs/{run_id}/script.pdf",
    response_class=FileResponse,
    dependencies=[Depends(require_user_header_or_query)],
)
def get_script_pdf(
    run_id: str,
    user: User = Depends(require_user_header_or_query),
):
    """Free-tier hook: anyone with a script can download it as a PDF — no
    subscription, no credit charge. The video render is the paid step;
    writing the story is always free."""
    from pipeline.pdf_export import render_script_pdf

    run_dir = _run_dir(run_id, user)
    script_path = run_dir / "script.json"
    if not script_path.exists():
        raise HTTPException(409, "script not generated yet")
    pdf_path = run_dir / "script.pdf"
    # Regenerate every time — script edits during the awaiting_approval
    # phase are common and stale PDFs would be confusing.
    doc = json.loads(script_path.read_text(encoding="utf-8"))
    render_script_pdf(doc, pdf_path)
    title = str(doc.get("title") or run_id).strip() or run_id
    # Browser-side filename hint; ASCII-fold so older browsers don't barf.
    safe_name = "".join(c if c.isascii() and (c.isalnum() or c in " -_") else "_"
                        for c in title).strip() or run_id
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"{safe_name}.pdf",
    )


class ApprovalAck(BaseModel):
    run_id: str
    status: RunStatus
    started_paid_stages: bool


@app.post(
    "/runs/{run_id}/approve",
    response_model=ApprovalAck,
    dependencies=[Depends(require_user)],
)
def approve_run(run_id: str, user: User = Depends(require_user)):
    run_dir = _run_dir(run_id, user)
    s = derive_status(run_dir)
    if s != "awaiting_approval":
        raise HTTPException(
            409,
            f"cannot approve from status={s} (expected awaiting_approval)",
        )
    # Idempotency guard: if a worker for this run is already running
    # (double-tap on the Approve button, browser back-and-forward,
    # mobile re-submit on flaky network), reject. Without this the
    # second call spawns a second worker and the user gets billed for
    # two character-sheet generations on the same script.
    existing_pid = _read_state(run_dir).get("pid")
    if _process_alive(existing_pid, run_dir):
        raise HTTPException(
            409,
            "an approve worker is already running for this run; "
            "wait for it to finish or call /cancel first",
        )
    # The paywall lives here, not on /runs/freeform. Anyone can write a
    # script; only subscribers can render it to video. Raises HTTP 402.
    _preflight_approve_credits(run_dir, user)
    args = ["--shorts", "--resume", str(run_dir),
            "--pause-after-character-sheet"]
    max_spend = _compute_max_spend_for_run(run_dir)
    if max_spend is not None:
        args += ["--max-spend", f"{max_spend:.2f}"]
    pid = _SPAWN_FN(args, run_dir)
    _write_state(run_dir, pid=pid, last_error=None, last_action="approve")
    return ApprovalAck(run_id=run_id, status=derive_status(run_dir),
                      started_paid_stages=True)


@app.post(
    "/runs/{run_id}/approve-veo",
    response_model=ApprovalAck,
    dependencies=[Depends(require_user)],
)
def approve_veo_run(run_id: str, user: User = Depends(require_user)):
    """Second approval gate. The user has reviewed the Flux character sheet
    and wants Veo to start spending. Only valid from awaiting_veo_approval.
    Spawns run.py --resume with NO pause flags so the pipeline runs Veo +
    captions + assemble end-to-end."""
    run_dir = _run_dir(run_id, user)
    s = derive_status(run_dir)
    if s != "awaiting_veo_approval":
        raise HTTPException(
            409,
            f"cannot approve-veo from status={s} "
            f"(expected awaiting_veo_approval)",
        )
    # Idempotency: see approve_run for rationale. A second tap here is
    # MUCH more expensive — it spawns Veo clip generation in parallel,
    # so credits get deducted twice for the same beats.
    existing_pid = _read_state(run_dir).get("pid")
    if _process_alive(existing_pid, run_dir):
        raise HTTPException(
            409,
            "a Veo render worker is already running for this run",
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


@app.post(
    "/runs/{run_id}/character-sheet/reroll",
    response_model=ApprovalAck,
    dependencies=[Depends(require_user)],
)
def reroll_character_sheet(run_id: str, user: User = Depends(require_user)):
    """Throw away the current Flux character sheet and regenerate it. Costs
    another $0.05 of Flux. Only valid from awaiting_veo_approval — by
    construction, you only reroll when you can SEE the sheet is wrong."""
    run_dir = _run_dir(run_id, user)
    s = derive_status(run_dir)
    if s != "awaiting_veo_approval":
        raise HTTPException(
            409,
            f"cannot reroll character sheet from status={s} "
            f"(expected awaiting_veo_approval)",
        )
    state = _read_state(run_dir)
    if _process_alive(state.get("pid"), run_dir):
        raise HTTPException(409, "a pipeline process is already running")
    (run_dir / "character_sheet.png").unlink(missing_ok=True)
    args = ["--shorts", "--resume", str(run_dir),
            "--pause-after-character-sheet"]
    pid = _SPAWN_FN(args, run_dir)
    _write_state(run_dir, pid=pid, last_error=None,
                 last_action="reroll_character_sheet")
    return ApprovalAck(run_id=run_id, status=derive_status(run_dir),
                      started_paid_stages=True)


@app.post(
    "/runs/{run_id}/resume",
    response_model=ApprovalAck,
    dependencies=[Depends(require_user)],
)
def resume_run(run_id: str, user: User = Depends(require_user)):
    """Force a resume regardless of current status — used after a transient
    failure (TLS reset, Kie 500, etc.). Idempotent: spawning while already
    running just produces a duplicate process which will see all artifacts
    on disk and exit quickly. We try to avoid that by checking PID first."""
    run_dir = _run_dir(run_id, user)
    state = _read_state(run_dir)
    if _process_alive(state.get("pid"), run_dir):
        raise HTTPException(409, "a pipeline process is already running for this run")
    args = ["--shorts", "--resume", str(run_dir)]
    max_spend = _compute_max_spend_for_run(run_dir)
    if max_spend is not None:
        args += ["--max-spend", f"{max_spend:.2f}"]
    pid = _SPAWN_FN(args, run_dir)
    _write_state(run_dir, pid=pid, last_error=None, last_action="resume")
    return ApprovalAck(run_id=run_id, status=derive_status(run_dir),
                      started_paid_stages=True)


class CancelAck(BaseModel):
    run_id: str
    killed_pid: int | None


# ---------------------------------------------------------------------------
# Edit script before approval — replace dialogue / fix LLM slips without
# regenerating from scratch
# ---------------------------------------------------------------------------

class EditScriptBeat(BaseModel):
    arabic: str
    english_motion: str
    speaker: str
    clip_duration_s: float
    character_name: str = ""           # NEW — free-form Arabic name, empty on legacy scripts


class EditScriptRequest(BaseModel):
    title: str | None = None
    beats: list[EditScriptBeat]


# _VALID_SPEAKERS removed in PA-1 — speaker is now a free-form non-empty string.


@app.put(
    "/runs/{run_id}/script",
    response_model=ScriptResponse,
    dependencies=[Depends(require_user)],
)
def edit_script(run_id: str, req: EditScriptRequest, user: User = Depends(require_user)):
    """Replace beats in script.json. Only allowed when the run is paused
    awaiting human approval — once paid stages start the dialogue is locked
    into the (already-generated) Veo clips and editing it does nothing."""
    run_dir = _run_dir(run_id, user)
    s = derive_status(run_dir)
    if s not in ("awaiting_approval", "awaiting_veo_approval"):
        raise HTTPException(
            409,
            f"cannot edit script from status={s} "
            f"(only awaiting_approval / awaiting_veo_approval are editable)",
        )
    if not req.beats:
        raise HTTPException(400, "at least one beat required")
    for i, b in enumerate(req.beats, start=1):
        if not (b.speaker or "").strip():
            raise HTTPException(400, f"beat {i}: speaker cannot be empty")
        if not b.english_motion.strip():
            raise HTTPException(400, f"beat {i}: english_motion is required")

    # Load existing script for fields we don't replace. The status check
    # above already implies awaiting_approval (which requires script.json),
    # but guard explicitly for the race where the file was deleted between
    # the check and the read.
    script_path = run_dir / "script.json"
    if not script_path.exists():
        raise HTTPException(409, "script.json missing — cannot edit")
    try:
        doc = json.loads(script_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise HTTPException(500, f"could not read script.json: {e}") from e
    if req.title is not None and req.title.strip():
        doc["title"] = req.title.strip()
    doc["beats"] = [
        {
            "arabic": b.arabic,
            "english_motion": b.english_motion,
            "speaker": b.speaker.strip().lower(),
            "clip_duration_s": float(b.clip_duration_s),
            "character_name": b.character_name,
        }
        for b in req.beats
    ]
    # Round to 2 decimals — without this, float sum gives 16.000000000000002 etc.
    doc["target_duration_s"] = round(
        sum(b.clip_duration_s for b in req.beats), 2,
    )
    doc["story_combined"] = " ".join(b.arabic for b in req.beats if b.arabic)
    script_path.write_text(
        json.dumps(doc, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return get_script(run_id, user)


# ---------------------------------------------------------------------------
# Delete a run — solo-user cleanup of failed / abandoned runs
# ---------------------------------------------------------------------------

class DeleteAck(BaseModel):
    run_id: str
    deleted: bool


def _stop_process_and_wait(
    pid: int | None,
    *,
    run_dir: Path | None = None,
    soft_timeout_s: float = 5.0,
) -> bool:
    """Best-effort: SIGTERM, wait up to `soft_timeout_s` for the process to
    actually exit, then SIGKILL if it's still running. Returns True if the
    process is dead by the time we return.

    `run_dir` is forwarded to _process_alive so the right spawn backend
    is picked — on Cloud Run the "pid" is a hash of the execution name,
    not a local OS pid, and falling back to LocalSubprocessBackend
    overflowed os.waitpid (real production crash on /delete).
    """
    if not _process_alive(pid, run_dir):
        return True
    # On a Cloud Run Jobs backend the "pid" is a hash, not a kernel
    # pid — we can't signal it. The backend handles cancellation via
    # its own API in delete_run / cancel_run paths.
    if not isinstance(pid, int) or pid <= 0 or pid > 2**31 - 1:
        return False
    import time
    try:
        os.kill(pid, signal.SIGTERM)  # type: ignore[arg-type]
    except (OSError, OverflowError):
        return not _process_alive(pid, run_dir)
    deadline = time.monotonic() + soft_timeout_s
    while time.monotonic() < deadline:
        time.sleep(0.05)
        if not _process_alive(pid, run_dir):
            return True
    # Still alive — escalate to SIGKILL
    try:
        os.kill(pid, signal.SIGKILL)  # type: ignore[arg-type]
    except (OSError, OverflowError):
        pass
    # Give the kernel a moment to reap
    time.sleep(0.3)
    return not _process_alive(pid, run_dir)


class CleanupAck(BaseModel):
    deleted_run_ids: list[str]


@app.post(
    "/runs/cleanup-failed",
    response_model=CleanupAck,
    dependencies=[Depends(require_user)],
)
def cleanup_failed_runs(user: User = Depends(require_user)):
    """Bulk-discard every run currently in `failed` status. Saves the user
    from having to long-press each broken run individually.

    Skips any run with a live (non-zombie) subprocess — those need an
    explicit cancel first. Won't touch complete or in-progress runs."""
    out = _user_runs_root(user)
    if not out.exists():
        return CleanupAck(deleted_run_ids=[])
    deleted: list[str] = []
    import shutil
    for p in sorted(out.iterdir()):
        if not p.is_dir():
            continue
        if derive_status(p) != "failed":
            continue
        state = _read_state(p)
        # Defensive: never bulk-delete a run with a live subprocess
        if _process_alive(state.get("pid"), p):
            continue
        try:
            shutil.rmtree(p)
            deleted.append(p.name)
        except OSError:
            continue
    return CleanupAck(deleted_run_ids=deleted)


# ---------------------------------------------------------------------------
# /runs/{id}/test-assemble — free smoke test using black-frame
# placeholder clips. Runs the same assemble + captions + faststart
# pipeline as a real render so any breakage downstream of Veo gets
# caught WITHOUT spending money on Kie. Required gating before any
# new paid render after a deploy.
# ---------------------------------------------------------------------------

class TestAssembleAck(BaseModel):
    run_id: str
    status: RunStatus
    started: bool


@app.post(
    "/runs/{run_id}/test-assemble",
    response_model=TestAssembleAck,
    dependencies=[Depends(require_user)],
)
def test_assemble_run(run_id: str, user: User = Depends(require_user)):
    """Spawn run.py with --skip-video on the existing run. Generates
    black-frame placeholder mp4s for each beat, then runs the full
    music + captions + assemble + faststart stack. Verifies the
    pipeline end-to-end without burning Veo credits.

    Caveats:
      - Requires a script.json (run must be at awaiting_approval or
        later); we don't bootstrap a new script for you.
      - Skips the character-sheet stage (`--skip-video` short-circuits
        that branch in run.py:739).
      - Overwrites the existing clips/*.mp4 with black frames if a
        previous real render exists. Run this on a throwaway run if
        you care about preserving past output.
    """
    run_dir = _run_dir(run_id, user)
    script_path = run_dir / "script.json"
    if not script_path.exists():
        raise HTTPException(
            409,
            "no script.json — generate a script first before running "
            "the assembly smoke test",
        )
    existing_pid = _read_state(run_dir).get("pid")
    if _process_alive(existing_pid, run_dir):
        raise HTTPException(
            409,
            "a worker is already running for this run; wait for it "
            "to finish before kicking off the assembly smoke test",
        )
    # Wipe any prior clips so the placeholder regenerator can start clean
    clips_dir = run_dir / "clips"
    if clips_dir.exists():
        for f in clips_dir.glob("*.mp4"):
            f.unlink(missing_ok=True)
    args = ["--shorts", "--resume", str(run_dir), "--skip-video"]
    pid = _SPAWN_FN(args, run_dir)
    _write_state(run_dir, pid=pid, last_error=None, last_action="test_assemble")
    return TestAssembleAck(
        run_id=run_id,
        status=derive_status(run_dir),
        started=True,
    )


# ---------------------------------------------------------------------------
# /admin/credit-back — service-token-only restore for users whose
# renders failed and burned credits. The audit found four bugs that
# could leave a user net-charged with no video to show for it:
# assembly-stage crashes, mid-run cancels, refund failures inside
# _charge_and_submit_clip, and the legacy non-chained code path. The
# refund_run_charges helper now handles those automatically — this
# endpoint is the manual escape hatch for credits lost BEFORE those
# fixes deployed (e.g. Essam's pre-fix $100 of dead renders).
# ---------------------------------------------------------------------------

class CreditBackRequest(BaseModel):
    user_id: str
    amount: int
    reason: str


class CreditBackAck(BaseModel):
    user_id: str
    amount: int
    new_balance: int


@app.post(
    "/admin/credit-back",
    response_model=CreditBackAck,
    dependencies=[Depends(require_user)],
)
def admin_credit_back(
    req: CreditBackRequest,
    user: User = Depends(require_user),
):
    """Insert a positive credit transaction for a user. Service token
    only — fails 403 for normal users so a malicious caller with a
    Supabase JWT can't credit their own account."""
    if user.role != "service":
        raise HTTPException(403, "admin endpoint — service token required")
    if req.amount <= 0:
        raise HTTPException(400, "amount must be positive")
    if not req.reason.strip():
        raise HTTPException(400, "reason is required for the ledger entry")

    from pipeline.db import get_balance, record_transaction
    record_transaction(
        user_id=req.user_id,
        amount=req.amount,
        kind="admin_credit",
        reference_id=None,
        description=req.reason,
    )
    new_balance = get_balance(req.user_id)
    return CreditBackAck(
        user_id=req.user_id,
        amount=req.amount,
        new_balance=new_balance,
    )


class SpendSummary(BaseModel):
    total_usd: float
    by_run: list[dict]  # [{"run_id": "...", "title": "...", "usd": 8.05}, ...]
    run_count: int


@app.get(
    "/spend",
    response_model=SpendSummary,
    dependencies=[Depends(require_user)],
)
def get_spend_summary(user: User = Depends(require_user)):
    """Total Kie.ai (Veo + Flux) spend across all runs, plus per-run breakdown.

    Reads kie_spend.json artifacts written by the pipeline. Doesn't include
    ElevenLabs / LLM costs (those don't write spend logs). Useful for
    answering 'how much have I spent this month'."""
    out = _user_runs_root(user)
    if not out.exists():
        return SpendSummary(total_usd=0.0, by_run=[], run_count=0)
    rows: list[dict] = []
    total = 0.0
    for p in sorted(out.iterdir(), reverse=True):
        if not p.is_dir():
            continue
        spend_file = p / "kie_spend.json"
        if not spend_file.exists():
            continue
        try:
            doc = json.loads(spend_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        run_total = sum(
            float(e.get("cost_usd", 0))
            for e in (doc.get("entries") or [])
        )
        if run_total <= 0:
            continue
        # Prefer the script's title for readability
        title = None
        sp = p / "script.json"
        if sp.exists():
            try:
                title = json.loads(sp.read_text(encoding="utf-8")).get("title")
            except (OSError, json.JSONDecodeError):
                pass
        rows.append({
            "run_id": p.name,
            "title": title,
            "usd": round(run_total, 2),
        })
        total += run_total
    return SpendSummary(
        total_usd=round(total, 2),
        by_run=rows,
        run_count=len(rows),
    )


@app.delete(
    "/runs/{run_id}",
    response_model=DeleteAck,
    dependencies=[Depends(require_user)],
)
def delete_run(run_id: str, user: User = Depends(require_user)):
    """Discard a run entirely.

    If a pipeline subprocess is still running, this stops it (SIGTERM,
    wait up to 5s, SIGKILL fallback) BEFORE removing the directory — the
    user just wants the run gone, they shouldn't have to call /cancel
    first and then race the OS to clean it up."""
    run_dir = _run_dir(run_id, user)
    state = _read_state(run_dir)
    pid = state.get("pid")
    if _process_alive(pid, run_dir):
        if not _stop_process_and_wait(pid, run_dir=run_dir):
            raise HTTPException(
                500,
                f"could not stop pipeline subprocess (pid={pid}) — "
                f"please retry or kill it manually",
            )
    import shutil
    shutil.rmtree(run_dir)
    return DeleteAck(run_id=run_id, deleted=True)


class RerollRequest(BaseModel):
    clips: list[int] = Field(..., min_length=1,
                             description="1-based clip indices to regenerate")


@app.post(
    "/runs/{run_id}/reroll",
    response_model=ApprovalAck,
    dependencies=[Depends(require_user)],
)
def reroll_clips(run_id: str, req: RerollRequest, user: User = Depends(require_user)):
    """Regenerate specific clips without losing the others.

    Use cases:
      - Veo's TTS rendered clip 6 in English by mistake → reroll just 6
      - A clip's visual is off → reroll without re-paying for the rest
      - The script.json hasn't changed; the assembler will re-run too

    Pre-removes the targeted .mp4 files so the pipeline's resume logic sees
    them as "missing" and regenerates only those. Then spawns `run.py
    --resume --reroll-clips N,M,...` to do the work.
    """
    run_dir = _run_dir(run_id, user)
    state = _read_state(run_dir)
    if _process_alive(state.get("pid"), run_dir):
        raise HTTPException(409, "a pipeline process is already running for this run")
    if not (run_dir / "script.json").exists():
        raise HTTPException(409, "script.json missing — nothing to reroll against")

    # Validate clip indices are within range
    script_doc = json.loads((run_dir / "script.json").read_text(encoding="utf-8"))
    n_beats = len(script_doc.get("beats") or [])
    for idx in req.clips:
        if idx < 1 or idx > n_beats:
            raise HTTPException(
                400,
                f"clip {idx} out of range (script has {n_beats} beats)",
            )

    # Remove the existing clips so resume regenerates them. The pipeline
    # itself also handles `--reroll-clips` by bumping seeds, but we delete
    # here so a half-corrupt mp4 (e.g. partial download) doesn't trick the
    # `out_path.exists()` skip-logic into reusing it.
    clips_dir = run_dir / "clips"
    last_frames_dir = run_dir / "last_frames"
    if clips_dir.exists():
        for idx in req.clips:
            (clips_dir / f"{idx:02d}.mp4").unlink(missing_ok=True)
    if last_frames_dir.exists():
        for idx in req.clips:
            (last_frames_dir / f"{idx:02d}.png").unlink(missing_ok=True)
    # Also remove final.mp4 — the assembler must re-stitch with the new clips
    (run_dir / "final.mp4").unlink(missing_ok=True)

    args = [
        "--shorts", "--resume", str(run_dir),
        "--reroll-clips", ",".join(str(i) for i in req.clips),
    ]
    max_spend = _compute_max_spend_for_run(run_dir)
    if max_spend is not None:
        args += ["--max-spend", f"{max_spend:.2f}"]
    pid = _SPAWN_FN(args, run_dir)
    _write_state(run_dir, pid=pid, last_error=None,
                 last_action=f"reroll {req.clips}")
    return ApprovalAck(run_id=run_id, status=derive_status(run_dir),
                      started_paid_stages=True)


@app.post(
    "/runs/{run_id}/cancel",
    response_model=CancelAck,
    dependencies=[Depends(require_user)],
)
def cancel_run(run_id: str, user: User = Depends(require_user)):
    """Stop a running pipeline subprocess. Waits for the process to actually
    exit (SIGTERM → wait → SIGKILL fallback) before returning, so a
    follow-up resume/reroll never races with a half-dead process.

    Refunds any net credits the user has been charged for this run.
    Cancelling mid-render previously left the user with the bill for
    any clips that completed before SIGTERM but no finished video.
    """
    from pipeline.credits import refund_run_charges

    run_dir = _run_dir(run_id, user)
    state = _read_state(run_dir)
    pid = state.get("pid")

    # Always attempt the refund — even if the process is already dead
    # (cancel-after-failed-state). It's a no-op when the user has
    # zero net charges for this run.
    refunded = 0
    try:
        refunded = refund_run_charges(
            user,
            run_id=run_id,
            reason="run cancelled by user before completion",
        )
    except Exception:
        # Don't fail the cancel because the refund failed. The kill
        # path is the user-facing action; log + move on.
        import logging
        logging.exception("refund_run_charges failed during cancel")

    if not _process_alive(pid, run_dir):
        return CancelAck(run_id=run_id, killed_pid=None)
    _stop_process_and_wait(pid, run_dir=run_dir)
    _write_state(
        run_dir,
        last_error=(
            f"cancelled by user (refunded {refunded} credits)"
            if refunded
            else "cancelled by user"
        ),
        last_action="cancel",
    )
    return CancelAck(run_id=run_id, killed_pid=pid)


@app.get("/runs/{run_id}/video",
         dependencies=[Depends(require_user_header_or_query)])
def get_video(run_id: str, user: User = Depends(require_user_header_or_query)):
    run_dir = _run_dir(run_id, user)
    p = run_dir / "final.mp4"
    if not p.exists():
        raise HTTPException(404, "final.mp4 not produced yet")
    # no-store so that the Repair-playback flow actually surfaces the
    # newly re-muxed bytes. Without it, Chrome was caching the broken
    # pre-faststart file and serving it back to the <video> element
    # even after the API replaced the bytes on disk.
    return FileResponse(
        path=str(p),
        media_type="video/mp4",
        filename=f"{run_id}.mp4",
        headers={"Cache-Control": "no-store"},
    )


class RepairAck(BaseModel):
    run_id: str
    repaired: bool
    note: str


@app.post(
    "/runs/{run_id}/repair-video",
    response_model=RepairAck,
    dependencies=[Depends(require_user)],
)
def repair_video(run_id: str, user: User = Depends(require_user)):
    """Fix old runs whose final.mp4 won't play in browsers ("FFmpeg
    demuxer open context failed").

    Two passes — cheap one first, full re-encode if it still smells
    broken:

      1. `ffmpeg -c copy -movflags +faststart` — moves the moov atom
         to the start of the file. Fixes the common case (moov-at-end
         pre-faststart-fix), takes ~1 sec, no Veo spend, no quality loss.

      2. If step 1 produces a suspiciously small file (< 50 KB or
         smaller than the input), fall back to a full H.264 + AAC
         re-encode with explicit yuv420p / profile high / level 4.0.
         Slower but produces a known-good file regardless of the
         input codec's quirks.
    """
    import subprocess
    from pipeline.mp4_faststart import rewrite_with_faststart

    run_dir = _run_dir(run_id, user)
    final = run_dir / "final.mp4"
    if not final.exists():
        raise HTTPException(404, "no final.mp4 to repair")

    # First, probe whether ffmpeg can even read the input. If the moov
    # atom is missing the file is unrecoverable by any normal means —
    # tell the caller to re-render instead of silently spinning ffmpeg.
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", str(final)],
        capture_output=True,
    )
    if probe.returncode != 0:
        raise HTTPException(
            422,  # 422 = the request is well-formed but the resource can't be processed
            "final.mp4 is corrupted beyond automatic repair (moov atom "
            "missing or stream metadata unreadable). Re-render the run "
            "to produce a fresh file.",
        )

    original_size = final.stat().st_size

    # Pass 1: cheap +faststart re-mux (rewrite_with_faststart is now
    # safe — it refuses to overwrite the original if the output is
    # suspiciously small).
    rewrite_with_faststart(final)
    note = "final.mp4 re-muxed with +faststart"

    # Pass 2: if re-mux made the file smaller than half its original
    # size, the input had something more wrong with it than a wandering
    # moov atom — fall through to a full transcode for a known-good
    # output regardless of input quirks.
    new_size = final.stat().st_size
    if new_size < 50_000 or new_size < original_size * 0.5:
        tmp = final.with_name("final.repaired.mp4")
        try:
            subprocess.run(
                [
                    "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                    "-i", str(final),
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                    "-pix_fmt", "yuv420p",
                    "-profile:v", "high", "-level", "4.0",
                    "-c:a", "aac", "-b:a", "160k",
                    "-movflags", "+faststart",
                    str(tmp),
                ],
                check=True,
            )
            tmp.replace(final)
            note = "final.mp4 fully re-encoded to H.264 + AAC + faststart"
        except subprocess.CalledProcessError:
            tmp.unlink(missing_ok=True)
            raise HTTPException(
                422,
                "final.mp4 readable but won't transcode cleanly. "
                "Re-render the run to produce a fresh file.",
            ) from None

    # Bust the thumbnail cache — may be stale.
    (run_dir / "thumbnail.jpg").unlink(missing_ok=True)
    return RepairAck(run_id=run_id, repaired=True, note=note)


@app.get("/runs/{run_id}/thumbnail",
         dependencies=[Depends(require_user_header_or_query)])
def get_thumbnail(run_id: str, user: User = Depends(require_user_header_or_query)):
    """First frame as a JPG, extracted on demand (cached on disk)."""
    run_dir = _run_dir(run_id, user)
    cache = run_dir / "thumbnail.jpg"
    if cache.exists():
        return FileResponse(str(cache), media_type="image/jpeg")
    # Prefer character_sheet (already a still) over re-extracting from mp4
    sheet = run_dir / "character_sheet.png"
    if sheet.exists():
        return FileResponse(str(sheet), media_type="image/png")
    final = run_dir / "final.mp4"
    if not final.exists():
        raise HTTPException(404, "no thumbnail source yet")
    _extract_thumbnail(final, cache)
    return FileResponse(str(cache), media_type="image/jpeg")


def _extract_thumbnail(video_path: Path, out_path: Path) -> None:
    """ffmpeg → first frame jpg. Replaceable in tests."""
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(video_path),
        "-vframes", "1", "-q:v", "2",
        str(out_path),
    ], check=True)


@app.get(
    "/runs/{run_id}/clips/{clip_index}/thumbnail",
    dependencies=[Depends(require_user_header_or_query)],
)
def get_clip_thumbnail(run_id: str, clip_index: int, user: User = Depends(require_user_header_or_query)):
    """First-frame JPG of a specific clip. Lets the run-detail screen
    show a small thumbnail next to each beat so the user can spot which
    clip rendered wrong without playing the full mp4. Cached on disk."""
    if clip_index < 1 or clip_index > 99:
        raise HTTPException(400, "clip_index out of range")
    run_dir = _run_dir(run_id, user)
    clip_path = run_dir / "clips" / f"{clip_index:02d}.mp4"
    if not clip_path.exists():
        raise HTTPException(404, "clip not generated yet")
    cache = run_dir / "clips" / f"{clip_index:02d}.jpg"
    if not cache.exists():
        try:
            _extract_thumbnail(clip_path, cache)
        except subprocess.CalledProcessError as e:
            raise HTTPException(500, f"ffmpeg thumbnail failed: {e}") from e
    return FileResponse(str(cache), media_type="image/jpeg")


@app.get(
    "/runs/{run_id}/clips/{clip_index}/video",
    dependencies=[Depends(require_user_header_or_query)],
)
def get_clip_video(run_id: str, clip_index: int, user: User = Depends(require_user_header_or_query)):
    """Stream a single Veo clip's mp4. Mirrors /clips/{i}/thumbnail but for
    full-motion playback. Used by the run-detail screen's tap-to-play UX.

    Auth via header OR query-string token because the Flutter video_player
    plugin on web silently drops httpHeaders — same workaround as the
    /runs/{id}/video endpoint."""
    if clip_index < 1 or clip_index > 99:
        raise HTTPException(400, "clip_index out of range")
    run_dir = _run_dir(run_id, user)
    clip_path = run_dir / "clips" / f"{clip_index:02d}.mp4"
    if not clip_path.exists():
        raise HTTPException(404, "clip not generated yet")
    return FileResponse(
        path=str(clip_path),
        media_type="video/mp4",
        filename=f"{run_id}-clip-{clip_index:02d}.mp4",
    )


@app.get(
    "/runs/{run_id}/log",
    dependencies=[Depends(require_user)],
)
def get_log(run_id: str, lines: int = 200, user: User = Depends(require_user)):
    """Tail of the subprocess log — useful for showing the user what failed."""
    run_dir = _run_dir(run_id, user)
    log_path = run_dir / "api_subprocess.log"
    if not log_path.exists():
        return Response(content="", media_type="text/plain")
    text = log_path.read_text(encoding="utf-8", errors="replace")
    tail = "\n".join(text.splitlines()[-max(1, lines):])
    return Response(content=tail, media_type="text/plain")


# ---------------------------------------------------------------------------
# Song mode endpoints
# ---------------------------------------------------------------------------


@app.post("/songs", status_code=201)
def create_song(
    req: CreateSongRequest,
    user: User = Depends(require_user),
):
    """Writer pass: generate lyrics + style + cover prompt inline.
    No spend; returns awaiting_approval immediately."""
    from pipeline.song_lyrics import generate_song_script
    from pipeline.config import load_config
    from pipeline.db import get_balance

    cfg = load_config(Path(os.environ.get(
        "FACELESS_CONFIG",
        str(REPO_ROOT / "config.yaml"),
    )))
    credits_required = cfg.song.credits_per_song if cfg.song else 1

    if user.role != "service" and get_balance(user.id) < credits_required:
        _raise_402_insufficient_credits(get_balance(user.id), credits_required)

    user_root = _user_runs_root(user)
    user_root.mkdir(parents=True, exist_ok=True)
    run_id = _make_run_id(root=user_root)
    run_dir = user_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    _write_state(
        run_dir,
        kind="song",
        status="writing_lyrics",
        user_id=user.id,
        theme=req.theme,
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )

    try:
        llm = _build_song_llm()
        script = generate_song_script(
            llm=llm,
            theme=req.theme,
            custom_lyrics=req.custom_lyrics,
            style_hint=req.style_hint,
            language=req.language,
        )
    except Exception as e:
        _write_state(run_dir, status="failed", last_error=f"lyrics LLM failed: {e}")
        raise HTTPException(500, f"lyrics generation failed: {e}")

    (run_dir / "song.json").write_text(
        json.dumps({
            "title": script.title,
            "lyrics": script.lyrics,
            "style_prompt": script.style_prompt,
            "cover_prompt": script.cover_prompt,
            "language": script.language,
            # Voice-control fields persist into the worker's Suno call.
            # vocal_gender defaults to 'm' on the API side, but pass
            # through whatever the request specified.
            "vocal_gender": req.vocal_gender,
            "persona_id": req.persona_id,
            # Optional Suno model override. Validated against
            # _ALLOWED_SUNO_MODELS; None falls back to config default.
            "suno_model": (
                req.suno_model
                if req.suno_model in _ALLOWED_SUNO_MODELS
                else None
            ),
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (run_dir / "lyrics.txt").write_text(script.lyrics, encoding="utf-8")
    _write_state(run_dir, status="awaiting_approval", title=script.title)

    return {"run_id": run_id, "status": "awaiting_approval"}


def _resolve_song_dir(run_id: str, user: "User") -> Path:
    """Locate the run dir; 404 if missing or owned by someone else."""
    run_dir = _run_dir(run_id, user)
    if not run_dir.exists():
        raise HTTPException(404, "run not found")
    return run_dir


# Statuses that indicate a worker is actively processing this run.
# Used by /songs/{id}/resume to refuse a second spawn while the first
# is still in flight.
_SONG_ACTIVE_STATUSES = frozenset({
    "generating_song",
    "generating_cover",
    "assembling",
})


# Per-user concurrent active song run cap. Stops users from
# accidentally approving / resuming multiple songs simultaneously
# and burning multiple Suno spends in parallel before the first one
# even finishes.
_SONG_CONCURRENT_LIMIT = int(
    os.environ.get("FACELESS_SONG_CONCURRENT_LIMIT", "1")
)


def _count_active_song_runs(user: "User") -> int:
    """Count the user's song runs whose status is currently
    generating_* or assembling. O(N) over the user's run dirs —
    fine for any realistic N (a few hundred max)."""
    user_root = _user_runs_root(user)
    if not user_root.exists():
        return 0
    count = 0
    for d in user_root.iterdir():
        if not d.is_dir():
            continue
        state = _read_state(d)
        if (state.get("kind") == "song"
                and state.get("status") in _SONG_ACTIVE_STATUSES):
            count += 1
    return count


def _enforce_concurrent_song_limit(user: "User") -> None:
    """Raise 429 if the user already has at least
    _SONG_CONCURRENT_LIMIT active song runs. Service tokens
    bypass the cap."""
    if user.role == "service":
        return
    active = _count_active_song_runs(user)
    if active >= _SONG_CONCURRENT_LIMIT:
        raise HTTPException(
            429,
            f"you already have {active} song generation(s) in progress; "
            f"wait for them to finish before starting another",
        )


# Per-user daily song-approve rate limit. Hard cap on how many songs
# a single account can spawn in 24 hours, independent of credits.
# Stops bill-shock attacks (compromised account or a runaway script
# trying to drain credits + max out Kie usage).
_SONG_DAILY_LIMIT = int(
    os.environ.get("FACELESS_SONG_DAILY_LIMIT", "30")
)


def _rate_limit_path(user: "User") -> Path:
    return _user_runs_root(user) / "_rate_limit.json"


def _load_rate_log(user: "User") -> list[float]:
    """Load timestamps of recent song approvals (epoch seconds)."""
    p = _rate_limit_path(user)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text())
        return data.get("approvals", []) if isinstance(data, dict) else []
    except (OSError, json.JSONDecodeError):
        return []


def _record_song_approval(user: "User") -> None:
    """Append now() to the user's approval log, dropping entries older
    than 24h. Atomic write."""
    import time
    p = _rate_limit_path(user)
    p.parent.mkdir(parents=True, exist_ok=True)
    now = time.time()
    cutoff = now - 86400
    log = [t for t in _load_rate_log(user) if t > cutoff]
    log.append(now)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps({"approvals": log}, ensure_ascii=False),
                   encoding="utf-8")
    tmp.replace(p)


def _enforce_daily_song_limit(user: "User") -> None:
    """Raise 429 if the user has approved >= _SONG_DAILY_LIMIT songs
    in the last 24 hours. Service tokens bypass."""
    if user.role == "service":
        return
    import time
    cutoff = time.time() - 86400
    recent = sum(1 for t in _load_rate_log(user) if t > cutoff)
    if recent >= _SONG_DAILY_LIMIT:
        raise HTTPException(
            429,
            f"daily song limit reached ({_SONG_DAILY_LIMIT} per 24h); "
            f"try again later",
        )


@app.get("/songs/{run_id}", response_model=SongRunSummary)
def get_song(run_id: str, user: User = Depends(require_user)):
    run_dir = _resolve_song_dir(run_id, user)
    state = _read_state(run_dir)
    if state.get("kind") != "song":
        raise HTTPException(404, "not a song run")
    return SongRunSummary(
        id=run_id,
        status=state.get("status", "unknown"),
        kind="song",
        title=state.get("title"),
        theme=state.get("theme"),
        created_at=state.get("created_at", ""),
        has_video=(run_dir / "final.mp4").exists(),
        chosen_take=state.get("chosen_take"),
        last_error=state.get("last_error"),
        failure_stage=state.get("failure_stage"),
    )


@app.get("/songs/{run_id}/script", response_model=SongScriptResponse)
def get_song_script(run_id: str, user: User = Depends(require_user)):
    run_dir = _resolve_song_dir(run_id, user)
    script_path = run_dir / "song.json"
    if not script_path.exists():
        raise HTTPException(404, "song.json not yet written")
    script = json.loads(script_path.read_text())
    from pipeline.config import load_config
    cfg_path = Path(os.environ.get("FACELESS_CONFIG", str(REPO_ROOT / "config.yaml")))
    cfg = load_config(cfg_path)
    return SongScriptResponse(
        title=script["title"],
        lyrics=script["lyrics"],
        style_prompt=script["style_prompt"],
        cover_prompt=script["cover_prompt"],
        language=script["language"],
        cost_credits=cfg.song.credits_per_song if cfg.song else 1,
        cost_usd=(cfg.song.suno_cost_usd + cfg.song.cover_cost_usd) if cfg.song else 0.08,
    )


_FAILED_RUN_TTL_DAYS = int(
    os.environ.get("FACELESS_FAILED_RUN_TTL_DAYS", "30")
)


def _cleanup_old_failed_song_runs(user: "User") -> int:
    """Delete song runs that have been in `failed` status for more
    than _FAILED_RUN_TTL_DAYS. Cheap to run lazily from /songs (the
    list endpoint walks the dirs anyway). Returns count deleted."""
    import shutil
    import time
    user_root = _user_runs_root(user)
    if not user_root.exists():
        return 0
    cutoff = time.time() - (_FAILED_RUN_TTL_DAYS * 86400)
    deleted = 0
    for d in user_root.iterdir():
        if not d.is_dir():
            continue
        state = _read_state(d)
        if state.get("kind") != "song":
            continue
        if state.get("status") != "failed":
            continue
        # Last update older than TTL → drop it.
        updated_at = state.get("updated_at")
        if not updated_at:
            continue
        try:
            from datetime import datetime as _dt
            ts = _dt.fromisoformat(updated_at).timestamp()
        except (TypeError, ValueError):
            continue
        if ts < cutoff:
            try:
                shutil.rmtree(d)
                deleted += 1
            except OSError:
                continue
    return deleted


@app.get("/songs", response_model=list[SongRunSummary])
def list_songs(user: User = Depends(require_user)):
    # Lazy cleanup of stale failed runs. ~30 days TTL by default.
    # Runs in the request path because /songs is already iterating
    # the user's run dirs; the extra cost is just a couple stat()
    # calls per failed entry.
    try:
        _cleanup_old_failed_song_runs(user)
    except Exception:
        # Cleanup failures must never block a successful list. Swallow.
        pass
    out = []
    user_root = _user_runs_root(user)
    if not user_root.exists():
        return out
    for d in sorted(user_root.iterdir(), key=lambda p: p.name, reverse=True):
        if not d.is_dir():
            continue
        state = _read_state(d)
        if state.get("kind") != "song":
            continue
        out.append(SongRunSummary(
            id=d.name,
            status=state.get("status", "unknown"),
            kind="song",
            title=state.get("title"),
            theme=state.get("theme"),
            created_at=state.get("created_at", ""),
            has_video=(d / "final.mp4").exists(),
            chosen_take=state.get("chosen_take"),
            last_error=state.get("last_error"),
            failure_stage=state.get("failure_stage"),
        ))
    return out


# ---------------------------------------------------------------------------
# Song mode mutations — state-guarded (awaiting_approval only)
# ---------------------------------------------------------------------------


class EditSongRequest(BaseModel):
    lyrics: str | None = None
    style_prompt: str | None = None
    cover_prompt: str | None = None


def _require_song_awaiting_approval(run_dir: Path) -> dict:
    state = _read_state(run_dir)
    if state.get("kind") != "song":
        raise HTTPException(404, "not a song run")
    if state.get("status") != "awaiting_approval":
        raise HTTPException(
            409,
            f"song is in state {state.get('status')!r}, edits not allowed",
        )
    return state


def _atomic_write_json(path: Path, data: dict) -> None:
    """Write JSON atomically via temp + rename."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp.replace(path)


@app.post("/songs/{run_id}/regenerate-lyrics")
def regenerate_song_lyrics(run_id: str, user: User = Depends(require_user)):
    from pipeline.song_lyrics import generate_song_script
    run_dir = _resolve_song_dir(run_id, user)
    _require_song_awaiting_approval(run_dir)
    script_path = run_dir / "song.json"
    current = json.loads(script_path.read_text())
    llm = _build_song_llm()
    new_script = generate_song_script(
        llm=llm,
        theme=_read_state(run_dir).get("theme", ""),
        custom_lyrics=None,
        style_hint=current.get("style_prompt"),  # preserve style direction
        language=current["language"],
    )
    new_data = {
        "title": new_script.title,
        "lyrics": new_script.lyrics,
        "style_prompt": new_script.style_prompt,
        "cover_prompt": current["cover_prompt"],  # keep cover prompt
        "language": new_script.language,
    }
    _atomic_write_json(script_path, new_data)
    (run_dir / "lyrics.txt").write_text(new_script.lyrics, encoding="utf-8")
    _write_state(run_dir, title=new_script.title)
    return {"ok": True}


@app.post("/songs/{run_id}/regenerate-cover-prompt")
def regenerate_song_cover_prompt(run_id: str, user: User = Depends(require_user)):
    from pipeline.song_lyrics import generate_song_script
    run_dir = _resolve_song_dir(run_id, user)
    _require_song_awaiting_approval(run_dir)
    script_path = run_dir / "song.json"
    current = json.loads(script_path.read_text())
    llm = _build_song_llm()
    new_script = generate_song_script(
        llm=llm,
        theme=_read_state(run_dir).get("theme", ""),
        custom_lyrics=current["lyrics"],  # keep lyrics
        style_hint=current["style_prompt"],
        language=current["language"],
    )
    current["cover_prompt"] = new_script.cover_prompt
    _atomic_write_json(script_path, current)
    return {"ok": True}


@app.post("/songs/{run_id}/edit")
def edit_song(
    run_id: str,
    req: EditSongRequest,
    user: User = Depends(require_user),
):
    run_dir = _resolve_song_dir(run_id, user)
    _require_song_awaiting_approval(run_dir)
    if req.lyrics is not None and len(req.lyrics) > 4000:
        raise HTTPException(422, "lyrics exceeds 4000 chars")
    if req.style_prompt is not None and len(req.style_prompt) > 500:
        raise HTTPException(422, "style_prompt exceeds 500 chars")
    if req.cover_prompt is not None and len(req.cover_prompt) > 500:
        raise HTTPException(422, "cover_prompt exceeds 500 chars")
    script_path = run_dir / "song.json"
    current = json.loads(script_path.read_text())
    for field in ("lyrics", "style_prompt", "cover_prompt"):
        v = getattr(req, field)
        if v is not None:
            current[field] = v
    _atomic_write_json(script_path, current)
    if req.lyrics is not None:
        (run_dir / "lyrics.txt").write_text(req.lyrics, encoding="utf-8")
    return {"ok": True}


@app.post("/songs/{run_id}/cancel")
def cancel_song(run_id: str, user: User = Depends(require_user)):
    run_dir = _resolve_song_dir(run_id, user)
    state = _read_state(run_dir)
    if state.get("kind") != "song":
        raise HTTPException(404, "not a song run")
    if state.get("status") == "complete":
        raise HTTPException(409, "song already complete")
    pid = state.get("pid")
    if pid and _process_alive(pid, run_dir):
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    _write_state(run_dir, status="canceled")
    return {"ok": True}


@app.post("/songs/{run_id}/approve")
def approve_song(run_id: str, user: User = Depends(require_user)):
    import pipeline.credits as _credits
    from pipeline.config import load_config

    run_dir = _resolve_song_dir(run_id, user)
    state = _read_state(run_dir)
    if state.get("kind") != "song":
        raise HTTPException(404, "not a song run")

    # Idempotency: second call after the spawn already happened
    if state.get("status") != "awaiting_approval":
        return {"run_id": run_id, "balance_after": _credits.get_balance(user.id),
                "status": state.get("status")}

    # Per-user concurrent-runs cap. Stops users from accidentally
    # tapping Approve on multiple drafts and burning multiple
    # Suno spends in parallel.
    _enforce_concurrent_song_limit(user)
    # Per-user daily-rate cap. Stops a runaway script or compromised
    # account from draining credits + maxing out Kie usage.
    _enforce_daily_song_limit(user)

    cfg_path = Path(os.environ.get("FACELESS_CONFIG", str(REPO_ROOT / "config.yaml")))
    cfg = load_config(cfg_path)
    amount = cfg.song.credits_per_song if cfg.song else 1

    if user.role != "service":
        balance = _credits.get_balance(user.id)
        if balance < amount:
            _raise_402_insufficient_credits(balance, amount)

    new_balance = _credits.check_or_deduct(
        user, amount=amount, run_id=run_id, reason="song-spend",
    )

    # Race avoidance: set status BEFORE spawning so the subprocess can't
    # write its own progress (e.g. "generating_cover") before we get a
    # chance to write "generating_song". The subprocess's first action
    # is also write_state(status="generating_song") which is idempotent
    # with this write. After spawning, only record the pid via a
    # read-modify-write that preserves whatever status the worker has
    # already written.
    _write_state(run_dir, status="generating_song")
    args = ["--mode", "song", "--resume", str(run_dir)]
    pid = _SPAWN_FN(args, run_dir)
    # Record this approval in the rate-limit log AFTER the spawn
    # succeeds. If spawning fails, no credit gets spent in the wrong
    # state — we let the user retry without it counting against quota.
    _record_song_approval(user)
    # Re-read so we don't clobber a worker-side status update that ran
    # synchronously between _SPAWN_FN returning and us getting here
    # (only happens with the in-process spawn used in integration tests).
    current = _read_state(run_dir)
    if current.get("status") in (None, "generating_song"):
        _write_state(run_dir, pid=pid)
    else:
        # Worker already advanced past generating_song. Record pid without
        # touching status.
        _write_state(run_dir, pid=pid)

    return {"run_id": run_id, "balance_after": new_balance,
            "status": current.get("status") or "generating_song"}


# ---------------------------------------------------------------------------
# Song mode — take-swap, streaming, log tail, resume
# ---------------------------------------------------------------------------


class SwapTakeRequest(BaseModel):
    take: int  # 1 or 2


@app.post("/songs/{run_id}/swap-take")
def swap_take(
    run_id: str,
    req: SwapTakeRequest,
    user: User = Depends(require_user),
):
    """Switch the active take and re-assemble final.mp4 in the
    background worker.

    The previous synchronous design (run ffmpeg inside the request)
    caused three real problems:
      1. Cloud Run kills the request → partial final.mp4 left on disk
      2. Two concurrent calls raced on song.mp3 + final.mp4
      3. The mobile UI showed a spinner for 2 minutes blocking the user

    Now it just queues the swap: sets a swap_to_take flag in state,
    spawns the worker, and returns immediately. run.py reads the
    flag, copies the take, and re-assembles atomically.
    """
    if req.take not in (1, 2):
        raise HTTPException(422, "take must be 1 or 2")
    run_dir = _resolve_song_dir(run_id, user)
    state = _read_state(run_dir)
    if state.get("kind") != "song":
        raise HTTPException(404, "not a song run")
    if state.get("status") != "complete":
        raise HTTPException(
            409,
            f"swap-take only valid for a complete song "
            f"(state: {state.get('status')!r})",
        )
    take_path = run_dir / "takes" / f"take_{req.take}.mp3"
    if not take_path.exists():
        raise HTTPException(404, f"take_{req.take}.mp3 not found")

    # No-op if the requested take is already chosen — saves a worker
    # spawn for accidental re-tap.
    if state.get("chosen_take") == req.take:
        return {"ok": True, "chosen_take": req.take, "noop": True}

    _enforce_concurrent_song_limit(user)

    # Set the swap flag + status BEFORE spawning so the concurrency
    # cap blocks any double-tap that arrives between now and the
    # worker writing its first status update.
    _write_state(
        run_dir,
        status="assembling",
        swap_to_take=req.take,
        last_error=None,
    )
    args = ["--mode", "song", "--resume", str(run_dir)]
    pid = _SPAWN_FN(args, run_dir)
    _write_state(run_dir, pid=pid)
    return {"ok": True, "chosen_take": req.take, "queued": True}


# Binary streaming endpoints accept the token via ?token=... query
# string in addition to the Authorization header, because browsers
# cannot set Authorization on <video>, <audio>, or <img> requests.
# Same pattern as the horror /runs/{id}/video endpoint.
@app.get("/songs/{run_id}/audio")
def get_song_audio(
    run_id: str,
    take: int | None = None,
    download: bool = False,
    user: User = Depends(require_user_header_or_query),
):
    """Stream the song MP3. With ?download=1 the browser saves it
    via Content-Disposition: attachment instead of inline playback."""
    run_dir = _resolve_song_dir(run_id, user)
    if take is not None:
        path = run_dir / "takes" / f"take_{take}.mp3"
    else:
        path = run_dir / "song.mp3"
    if not path.exists():
        raise HTTPException(404, "audio not found")
    headers = {}
    if download:
        suffix = f"-take-{take}" if take is not None else ""
        headers["Content-Disposition"] = (
            f'attachment; filename="faceless-song-{run_id}{suffix}.mp3"'
        )
    return FileResponse(path, media_type="audio/mpeg", headers=headers)


@app.get("/songs/{run_id}/cover")
def get_song_cover(run_id: str,
                   thumb: bool = False,
                   user: User = Depends(require_user_header_or_query)):
    """Serve the cover image. ?thumb=1 returns the small 256px JPEG
    (15-25 KB) — used by the song-list to keep scroll snappy.
    Without thumb, returns the full 1080x1080 PNG (~1.2 MB)."""
    run_dir = _resolve_song_dir(run_id, user)
    if thumb:
        thumb_path = run_dir / "cover_thumb.jpg"
        if thumb_path.exists():
            return FileResponse(thumb_path, media_type="image/jpeg")
        # Older runs predate the thumbnail-on-assemble change; fall
        # through to the full-size cover. Better one slow first-load
        # than a broken image.
    path = run_dir / "cover.png"
    if not path.exists():
        raise HTTPException(404, "cover not yet generated")
    return FileResponse(path, media_type="image/png")


@app.get("/songs/{run_id}/video")
def get_song_video(
    run_id: str,
    download: bool = False,
    user: User = Depends(require_user_header_or_query),
):
    """Stream the final.mp4. With `?download=1` the server sets
    Content-Disposition: attachment so the browser saves the file
    instead of playing it inline."""
    run_dir = _resolve_song_dir(run_id, user)
    path = run_dir / "final.mp4"
    if not path.exists():
        raise HTTPException(404, "final.mp4 not yet assembled")
    headers = {}
    if download:
        # Filename uses the run_id; the song's title would be nicer but
        # contains Arabic characters that need RFC 5987 encoding to be
        # safe in the header. run_id is ASCII timestamp — keep it simple.
        headers["Content-Disposition"] = (
            f'attachment; filename="faceless-song-{run_id}.mp4"'
        )
    return FileResponse(path, media_type="video/mp4", headers=headers)


@app.get("/songs/{run_id}/log")
def get_song_log(
    run_id: str,
    lines: int = 200,
    user: User = Depends(require_user),
):
    run_dir = _resolve_song_dir(run_id, user)
    path = run_dir / "run.log"
    if not path.exists():
        return {"log": ""}
    text = path.read_text(errors="replace")
    tail = "\n".join(text.splitlines()[-lines:])
    return {"log": tail}


@app.get("/songs/{run_id}/events")
async def song_events(
    run_id: str,
    user: User = Depends(require_user_header_or_query),
):
    """Server-Sent Events stream for a song run's live status.

    Replaces the Flutter app's 3-second polling loop with a push
    channel — status flips are observable within ~200ms instead of
    averaging 1.5s of polling lag. The stream emits one event per
    state transition and ends when the run reaches a terminal status
    (complete / failed / canceled).

    Uses ?token=... query auth so EventSource can connect (it can't
    set Authorization headers).
    """
    import asyncio
    run_dir = _resolve_song_dir(run_id, user)
    if _read_state(run_dir).get("kind") != "song":
        raise HTTPException(404, "not a song run")

    _TERMINAL = frozenset({"complete", "failed", "canceled"})

    async def generator():
        last_serialized: str | None = None
        # Send one immediate snapshot so the client doesn't sit on a
        # blank screen for up to a poll interval before the first
        # state change.
        deadline = asyncio.get_event_loop().time() + 600  # 10 min cap
        while True:
            state = _read_state(run_dir)
            # Build a small status payload — full state.json has
            # internal fields the UI doesn't need.
            payload = {
                "status": state.get("status"),
                "chosen_take": state.get("chosen_take"),
                "failure_stage": state.get("failure_stage"),
                "last_error": state.get("last_error"),
            }
            serialized = json.dumps(payload, sort_keys=True)
            if serialized != last_serialized:
                yield f"data: {serialized}\n\n"
                last_serialized = serialized
            if payload.get("status") in _TERMINAL:
                # One final event then close.
                yield "event: done\ndata: {}\n\n"
                return
            if asyncio.get_event_loop().time() > deadline:
                # Hard cap so a stuck connection doesn't tie up a
                # Cloud Run instance forever. Client can reconnect.
                yield "event: timeout\ndata: {}\n\n"
                return
            await asyncio.sleep(0.5)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store",
            "X-Accel-Buffering": "no",  # disable nginx buffering if proxied
        },
    )


@app.post("/songs/{run_id}/resume")
def resume_song(run_id: str, user: User = Depends(require_user)):
    """Retry a failed song run.

    Concurrency guard: if a worker is already actively processing this
    run (status is generating_song / generating_cover / assembling),
    refuse with 409. This stops the race we saw in production where a
    rapid double-tap on Retry, or simultaneous Retry + automatic
    /resume from the detail screen, spawned two workers that both
    wrote to song.mp3 and final.mp4, producing a truncated output.

    Only `failed` is a valid starting state for /resume — terminal
    successes (`complete`, `canceled`) and pre-spend states
    (`awaiting_approval`, `writing_lyrics`) are also rejected.
    """
    run_dir = _resolve_song_dir(run_id, user)
    state = _read_state(run_dir)
    if state.get("kind") != "song":
        raise HTTPException(404, "not a song run")

    status = state.get("status")
    if status in _SONG_ACTIVE_STATUSES:
        raise HTTPException(
            409,
            f"a worker is already processing this song "
            f"(current state: {status!r}); wait for it to complete or fail",
        )
    if status != "failed":
        raise HTTPException(
            409,
            f"song is in state {status!r}, cannot resume (must be 'failed')",
        )

    # Per-user concurrent-runs cap.
    _enforce_concurrent_song_limit(user)

    args = ["--mode", "song", "--resume", str(run_dir)]
    pid = _SPAWN_FN(args, run_dir)
    _write_state(run_dir, status="generating_song", pid=pid, last_error=None)
    return {"ok": True}


@app.post("/songs/{run_id}/regenerate-cover")
def regenerate_song_cover(run_id: str, user: User = Depends(require_user)):
    """Re-render the cover image (and the final MP4 with the new
    cover baked in) without re-generating the song.

    Useful when the Flux output came back ugly or when the cover
    prompt was tweaked after the song completed. Suno is skipped
    (takes/song.mp3 already on disk); only Flux + ffmpeg run.

    Sets a `regenerate_cover` flag in api_state.json that run.py
    reads to bypass its normal "cover_raw.png exists → skip Flux"
    optimization for this run.
    """
    run_dir = _resolve_song_dir(run_id, user)
    state = _read_state(run_dir)
    if state.get("kind") != "song":
        raise HTTPException(404, "not a song run")
    if state.get("status") != "complete":
        raise HTTPException(
            409,
            f"can only regenerate cover for a complete song "
            f"(state: {state.get('status')!r})",
        )

    # Per-user concurrent-runs cap.
    _enforce_concurrent_song_limit(user)

    _write_state(
        run_dir,
        status="generating_cover",
        regenerate_cover=True,
        last_error=None,
    )
    args = ["--mode", "song", "--resume", str(run_dir)]
    pid = _SPAWN_FN(args, run_dir)
    _write_state(run_dir, pid=pid)
    return {"ok": True}


@app.post("/songs/{run_id}/reroll-takes")
def reroll_song_takes(run_id: str, user: User = Depends(require_user)):
    """Generate fresh Suno takes for this song (keeps the same lyrics,
    style, and cover prompt). Charges credits like a new approval —
    this is full Suno re-generation, not a free retry.

    Use when both Suno takes came back bad. Cheaper than canceling +
    starting over because the lyrics + cover are reused.
    """
    import pipeline.credits as _credits
    from pipeline.config import load_config

    run_dir = _resolve_song_dir(run_id, user)
    state = _read_state(run_dir)
    if state.get("kind") != "song":
        raise HTTPException(404, "not a song run")
    if state.get("status") != "complete":
        raise HTTPException(
            409,
            f"can only re-roll takes from a complete song "
            f"(state: {state.get('status')!r})",
        )

    _enforce_concurrent_song_limit(user)
    _enforce_daily_song_limit(user)

    cfg_path = Path(os.environ.get("FACELESS_CONFIG", str(REPO_ROOT / "config.yaml")))
    cfg = load_config(cfg_path)
    amount = cfg.song.credits_per_song if cfg.song else 1

    if user.role != "service":
        balance = _credits.get_balance(user.id)
        if balance < amount:
            _raise_402_insufficient_credits(balance, amount)

    new_balance = _credits.check_or_deduct(
        user, amount=amount, run_id=run_id, reason="song-spend (reroll)",
    )

    # Delete the existing take files so the worker's
    # "skip Suno if takes exist" logic doesn't skip the regen.
    takes_dir = run_dir / "takes"
    if takes_dir.exists():
        for f in takes_dir.glob("take_*.mp3"):
            try:
                f.unlink()
            except OSError:
                pass
    # song.mp3 will be overwritten by the worker after Suno returns.

    _write_state(run_dir, status="generating_song", last_error=None)
    args = ["--mode", "song", "--resume", str(run_dir)]
    pid = _SPAWN_FN(args, run_dir)
    _record_song_approval(user)
    _write_state(run_dir, pid=pid)
    return {"ok": True, "balance_after": new_balance}


@app.delete("/songs/{run_id}", status_code=204)
def delete_song(run_id: str, user: User = Depends(require_user)):
    """Delete a song run entirely — removes the run dir and all
    artifacts (song.json, lyrics.txt, cover.png, take_*.mp3, song.mp3,
    final.mp4, api_state.json, etc.).

    Refuses with 409 if a worker is actively processing the run. The
    user must wait for it to complete (or fail), then delete.
    """
    import shutil
    run_dir = _resolve_song_dir(run_id, user)
    state = _read_state(run_dir)
    if state.get("kind") != "song":
        raise HTTPException(404, "not a song run")
    if state.get("status") in _SONG_ACTIVE_STATUSES:
        raise HTTPException(
            409,
            f"a worker is processing this song (state: {state.get('status')!r}); "
            f"wait for it to finish before deleting",
        )
    try:
        shutil.rmtree(run_dir)
    except OSError as e:
        raise HTTPException(500, f"failed to remove run dir: {e}")
    return None


# ---------------------------------------------------------------------------
# Personas — voice locking across songs.
#
# Suno V5/V5.5 supports a personaId parameter that pins the singer's
# voice across generations. A Persona is created from an existing
# Suno taskId+audioId pair via Kie's /api/v1/persona/generate.
#
# Storage: a single personas.json file under each user's run-root.
# Small footprint, easy to list, atomic temp+rename writes.
# ---------------------------------------------------------------------------


def _personas_path(user: "User") -> Path:
    return _user_runs_root(user) / "personas.json"


def _load_personas(user: "User") -> list[dict]:
    p = _personas_path(user)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text())
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _save_personas(user: "User", personas: list[dict]) -> None:
    p = _personas_path(user)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(personas, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    tmp.replace(p)


@app.post("/songs/{run_id}/save-persona", response_model=PersonaSummary,
          status_code=201)
def save_persona_from_song(
    run_id: str,
    req: CreatePersonaRequest,
    user: User = Depends(require_user),
):
    """Create a Suno Persona from a finished song's take.

    The run must have status=complete and a recorded suno_task_id +
    take_audio_ids (saved by run.py during the post-approve stage).
    """
    from pipeline.song import submit_persona_job, PersonaSourceNotFound
    from pipeline.kie import KieClient

    run_dir = _resolve_song_dir(run_id, user)
    state = _read_state(run_dir)
    if state.get("kind") != "song":
        raise HTTPException(404, "not a song run")
    if state.get("status") != "complete":
        raise HTTPException(
            409,
            f"persona can only be saved from a complete song "
            f"(current state: {state.get('status')!r})",
        )

    suno_task_id = state.get("suno_task_id")
    audio_ids = state.get("take_audio_ids") or []
    if not suno_task_id or not audio_ids:
        raise HTTPException(
            409,
            "this run pre-dates persona support (no suno_task_id "
            "or audio_ids saved) — generate a new song first",
        )

    take_index = (req.take or state.get("chosen_take") or 1) - 1
    if not (0 <= take_index < len(audio_ids)):
        raise HTTPException(
            422, f"invalid take {req.take!r}; this run has {len(audio_ids)} take(s)",
        )
    audio_id = audio_ids[take_index]
    if not audio_id:
        raise HTTPException(
            500, f"audio_id for take {take_index + 1} missing — Kie didn't return it",
        )

    if not req.name.strip():
        raise HTTPException(422, "persona name is required")
    if len(req.name) > 80:
        raise HTTPException(422, "persona name exceeds 80 chars")
    if len(req.description) > 500:
        raise HTTPException(422, "persona description exceeds 500 chars")

    client = KieClient()
    try:
        persona_id = submit_persona_job(
            client,
            source_task_id=suno_task_id,
            source_audio_id=audio_id,
            name=req.name.strip(),
            description=req.description.strip(),
        )
    except PersonaSourceNotFound as e:
        # Kie's retention window expired (or this run pre-dates the
        # voice-saving code). Surface a user-actionable 422 instead
        # of a generic 500 — the message tells them what to do next.
        raise HTTPException(422, str(e))

    record = {
        "id": persona_id,
        "name": req.name.strip(),
        "description": req.description.strip(),
        "source_run_id": run_id,
        "source_take": take_index + 1,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    personas = _load_personas(user)
    personas.append(record)
    _save_personas(user, personas)
    return PersonaSummary(**record)


@app.get("/personas", response_model=list[PersonaSummary])
def list_personas(user: User = Depends(require_user)):
    return [PersonaSummary(**p) for p in _load_personas(user)]


@app.delete("/personas/{persona_id}", status_code=204)
def delete_persona(persona_id: str, user: User = Depends(require_user)):
    personas = _load_personas(user)
    new_list = [p for p in personas if p.get("id") != persona_id]
    if len(new_list) == len(personas):
        raise HTTPException(404, "persona not found")
    _save_personas(user, new_list)
    return None


# ---------------------------------------------------------------------------
# Public sharing — /p/{token} pages anyone can view (no auth).
#
# When a user taps "Share" on a song, the API mints a random token
# and writes a mapping {token → (user_id, run_id)} into a shared
# index file. The public-facing /p/{token} page reads the index,
# loads the song's metadata + cover + video, and renders an HTML
# page with Open Graph + Twitter Card meta so links preview nicely
# in WhatsApp / Twitter / Facebook.
#
# Privacy posture: tokens are 128-bit URL-safe random (secrets.token_
# urlsafe(16)). Security is share-by-link — anyone with the URL can
# play the song. Owner can revoke at any time by deleting the token.
# ---------------------------------------------------------------------------

_SHARE_INDEX_PATH = lambda: _out_root() / "_share_index.json"  # noqa: E731


def _load_share_index() -> dict:
    p = _SHARE_INDEX_PATH()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def _save_share_index(idx: dict) -> None:
    p = _SHARE_INDEX_PATH()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(idx, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    tmp.replace(p)


def _resolve_shared_song(token: str) -> tuple[Path, dict]:
    """Look up a shared run by token. Returns (run_dir, song_json).
    Raises 404 if the token doesn't exist or the run dir was deleted."""
    idx = _load_share_index()
    entry = idx.get(token)
    if not entry:
        raise HTTPException(404, "shared link not found")
    user_id = entry.get("user_id")
    run_id = entry.get("run_id")
    if not user_id or not run_id:
        raise HTTPException(404, "shared link corrupted")
    run_dir = _out_root() / user_id / run_id
    if not run_dir.exists():
        # Run was deleted — stale index entry; clean it up.
        idx.pop(token, None)
        _save_share_index(idx)
        raise HTTPException(404, "shared song was deleted")
    script_path = run_dir / "song.json"
    if not script_path.exists():
        raise HTTPException(404, "song data missing")
    return run_dir, json.loads(script_path.read_text())


@app.post("/songs/{run_id}/share", response_model=ShareInfo)
def share_song(run_id: str, user: User = Depends(require_user)):
    """Mint a public share token for this song. Idempotent — repeat
    calls return the same token if one was already issued.

    Refuses if the song isn't complete (no point sharing an
    in-progress run)."""
    import secrets
    run_dir = _resolve_song_dir(run_id, user)
    state = _read_state(run_dir)
    if state.get("kind") != "song":
        raise HTTPException(404, "not a song run")
    if state.get("status") != "complete":
        raise HTTPException(
            409,
            f"can only share a complete song (state: {state.get('status')!r})",
        )

    existing_token = state.get("share_token")
    if existing_token:
        token = existing_token
    else:
        token = secrets.token_urlsafe(16)
        _write_state(run_dir, share_token=token)
        idx = _load_share_index()
        idx[token] = {"user_id": user.id, "run_id": run_id}
        _save_share_index(idx)

    base_url = os.environ.get(
        "FACELESS_PUBLIC_URL",
        "https://faceless-api-uplzdtffeq-uc.a.run.app",
    ).rstrip("/")
    return ShareInfo(token=token, url=f"{base_url}/p/{token}")


@app.delete("/songs/{run_id}/share", status_code=204)
def unshare_song(run_id: str, user: User = Depends(require_user)):
    """Revoke a song's share link. Existing links 404 after this."""
    run_dir = _resolve_song_dir(run_id, user)
    state = _read_state(run_dir)
    token = state.get("share_token")
    if not token:
        return None  # idempotent no-op
    idx = _load_share_index()
    idx.pop(token, None)
    _save_share_index(idx)
    _write_state(run_dir, share_token=None)
    return None


@app.get("/p/{token}", include_in_schema=False)
def shared_song_page(token: str):
    """Public share page (no auth) — embeds the video, displays the
    lyrics with proper RTL handling and section-tag styling, sets
    Open Graph / Twitter Card meta tags for link previews."""
    from fastapi.responses import HTMLResponse
    run_dir, script = _resolve_shared_song(token)
    title = script.get("title", "AI song")
    lyrics = script.get("lyrics", "")
    language = script.get("language", "ar")
    # OG description is a single-line teaser — first stanza of the
    # lyrics, cleaned of section tags and capped to a sensible length.
    import re as _re
    teaser_lines = []
    for line in lyrics.split("\n"):
        line = line.strip()
        if not line or _re.match(r"^\[", line):
            continue
        teaser_lines.append(line)
        if len(teaser_lines) >= 2:
            break
    teaser = " · ".join(teaser_lines)[:160] or "Listen to this AI-generated song."

    base_url = os.environ.get(
        "FACELESS_PUBLIC_URL",
        "https://faceless-api-uplzdtffeq-uc.a.run.app",
    ).rstrip("/")
    page_url = f"{base_url}/p/{token}"
    # Fingerprint the video + cover URLs with their file mtimes so
    # regenerating the cover or swapping a take produces NEW URLs.
    # Without this, browsers / WhatsApp / Twitter cache the first
    # version they fetched forever and show the old cover even
    # after the user regenerates. The HTML page itself sends
    # Cache-Control: no-cache (below) so each fresh visit gets the
    # current mtime values.
    def _mtime(p: Path) -> int:
        try:
            return int(p.stat().st_mtime)
        except OSError:
            return 0
    cover_v = _mtime(run_dir / "cover.png")
    video_v = _mtime(run_dir / "final.mp4")
    video_url = f"{base_url}/p/{token}/video?v={video_v}"
    cover_url = f"{base_url}/p/{token}/cover?v={cover_v}"

    def esc(s: str) -> str:
        return (s.replace("&", "&amp;").replace("<", "&lt;")
                 .replace(">", "&gt;").replace('"', "&quot;"))

    # Render lyrics: each line is either a `[Verse 1]`-style section
    # header (rendered as a small chip) or a normal sung line.
    # Each STANZA (group of lines between two section headers OR
    # blanks) gets a data-stanza index so the JS karaoke highlighter
    # can scroll to the currently-playing one.
    is_rtl = language in ("ar", "he", "fa", "ur")
    text_dir = "rtl" if is_rtl else "ltr"
    lyrics_html_parts: list[str] = []
    section_re = _re.compile(r"^\[([^\]]+)\]\s*$")
    stanza_idx = 0
    in_stanza = False
    for raw in lyrics.split("\n"):
        line = raw.strip()
        if not line:
            lyrics_html_parts.append('<div class="gap"></div>')
            in_stanza = False
            continue
        m = section_re.match(line)
        if m:
            stanza_idx += 1
            lyrics_html_parts.append(
                f'<div class="section" data-stanza="{stanza_idx}">'
                f'{esc(m.group(1))}</div>'
            )
            in_stanza = True
        else:
            if not in_stanza:
                stanza_idx += 1
                in_stanza = True
            lyrics_html_parts.append(
                f'<p class="line" data-stanza="{stanza_idx}">'
                f'{esc(line)}</p>'
            )
    lyrics_html = "\n".join(lyrics_html_parts)
    total_stanzas = stanza_idx

    html = f"""<!DOCTYPE html>
<html lang="{esc(language)}">
<head>
<meta charset="utf-8">
<title>{esc(title)} · faceless</title>
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="description" content="{esc(teaser)}">
<meta name="theme-color" content="#0a0d14">

<!-- Open Graph -->
<meta property="og:site_name" content="faceless">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(teaser)}">
<meta property="og:image" content="{cover_url}">
<meta property="og:image:secure_url" content="{cover_url}">
<meta property="og:image:width" content="1080">
<meta property="og:image:height" content="1080">
<meta property="og:image:alt" content="{esc(title)}">
<meta property="og:video" content="{video_url}">
<meta property="og:video:secure_url" content="{video_url}">
<meta property="og:video:type" content="video/mp4">
<meta property="og:video:width" content="1080">
<meta property="og:video:height" content="1080">
<meta property="og:type" content="video.other">
<meta property="og:url" content="{page_url}">

<!-- Twitter -->
<meta name="twitter:card" content="player">
<meta name="twitter:site" content="@faceless">
<meta name="twitter:title" content="{esc(title)}">
<meta name="twitter:description" content="{esc(teaser)}">
<meta name="twitter:image" content="{cover_url}">
<meta name="twitter:image:alt" content="{esc(title)}">
<meta name="twitter:player" content="{page_url}">
<meta name="twitter:player:width" content="1080">
<meta name="twitter:player:height" content="1080">
<meta name="twitter:player:stream" content="{video_url}">
<meta name="twitter:player:stream:content_type" content="video/mp4">

<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Amiri:wght@400;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">

<style>
  :root {{
    --bg-0: #06080d;
    --bg-1: #0d1119;
    --bg-2: #161b27;
    --fg-0: #f3f5fb;
    --fg-1: #c5cad9;
    --fg-2: #7f869c;
    --fg-3: #4a5266;
    --accent: #d7b46a;
    --accent-soft: rgba(215, 180, 106, 0.16);
  }}
  * {{ box-sizing: border-box; }}
  html, body {{
    margin: 0; padding: 0;
    background: radial-gradient(120% 80% at 50% 0%, #131a2a 0%, var(--bg-0) 55%) fixed;
    color: var(--fg-0);
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
    min-height: 100vh; min-height: 100dvh;
    -webkit-font-smoothing: antialiased;
    text-rendering: optimizeLegibility;
  }}
  body[dir="rtl"] .line, body[dir="rtl"] .title {{
    font-family: 'Amiri', 'Inter', serif;
  }}
  .wrap {{
    max-width: 640px; margin: 0 auto;
    padding: 32px 20px 80px;
  }}
  .player {{
    position: relative;
    border-radius: 20px;
    overflow: hidden;
    background: black;
    box-shadow: 0 30px 80px -20px rgba(0,0,0,0.7),
                0 0 0 1px rgba(255,255,255,0.04);
    aspect-ratio: 1 / 1;
  }}
  .player video {{
    width: 100%; height: 100%; display: block;
    object-fit: cover;
  }}
  .title {{
    font-size: 28px; font-weight: 700; letter-spacing: -0.01em;
    text-align: center; margin: 28px 0 6px;
    color: var(--fg-0);
  }}
  .made-by {{
    text-align: center; font-size: 12px; letter-spacing: 0.16em;
    text-transform: uppercase; color: var(--fg-3);
    margin: 0 0 32px;
  }}
  .made-by .dot {{
    display: inline-block; width: 4px; height: 4px; border-radius: 50%;
    background: var(--accent); margin: 0 8px; vertical-align: middle;
  }}
  .lyrics {{
    background: linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0));
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 18px;
    padding: 28px 24px;
    line-height: 1.85;
  }}
  .lyrics .section {{
    display: inline-block;
    font-size: 11px;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: var(--accent);
    background: var(--accent-soft);
    padding: 4px 10px;
    border-radius: 999px;
    margin: 18px 0 8px;
  }}
  .lyrics .section:first-child {{ margin-top: 0; }}
  .lyrics .line {{
    margin: 0;
    font-size: 18px;
    color: var(--fg-0);
    font-weight: 500;
  }}
  body[dir="rtl"] .lyrics .line {{ font-size: 21px; line-height: 2.0; }}
  .lyrics .gap {{ height: 10px; }}
  footer {{
    margin-top: 40px;
    text-align: center;
    font-size: 12px;
    color: var(--fg-3);
    letter-spacing: 0.02em;
  }}
  footer a {{
    color: var(--fg-1);
    text-decoration: none;
    border-bottom: 1px solid var(--fg-3);
    padding-bottom: 1px;
  }}
  footer a:hover {{ color: var(--accent); border-color: var(--accent); }}
  @media (max-width: 480px) {{
    .wrap {{ padding: 20px 16px 60px; }}
    .title {{ font-size: 24px; }}
    .lyrics {{ padding: 20px 18px; }}
    .lyrics .line {{ font-size: 16px; }}
    body[dir="rtl"] .lyrics .line {{ font-size: 19px; }}
  }}
  /* Karaoke highlighter — lines outside the currently-playing
     stanza dim slightly; active stanza gets a subtle gold rim. */
  .lyrics .line, .lyrics .section {{
    transition: opacity 0.5s ease, color 0.5s ease;
    opacity: 0.45;
  }}
  .lyrics .line.active, .lyrics .section.active {{
    opacity: 1;
  }}
  .lyrics.idle .line, .lyrics.idle .section {{ opacity: 1; }}
</style>
</head>
<body dir="{text_dir}">
<div class="wrap">
  <div class="player">
    <video id="player" controls playsinline poster="{cover_url}" preload="metadata">
      <source src="{video_url}" type="video/mp4">
      Your browser does not support embedded video.
    </video>
  </div>
  <h1 class="title">{esc(title)}</h1>
  <p class="made-by">faceless<span class="dot"></span>AI song</p>
  <div class="lyrics idle" id="lyrics" data-total-stanzas="{total_stanzas}">
    {lyrics_html}
  </div>
  <footer>
    Made with <a href="{base_url}/app/">faceless</a> — AI-generated music
  </footer>
</div>
<script>
  // Karaoke-style lyric highlight. Honest about its limits: Suno
  // doesn't return per-line timestamps, so we divide the song's
  // total duration evenly across the stanza count. Close enough
  // for a song that's roughly verse-chorus-verse-chorus; will
  // drift on songs with big tempo changes.
  (function() {{
    const player = document.getElementById('player');
    const lyrics = document.getElementById('lyrics');
    if (!player || !lyrics) return;
    const total = parseInt(lyrics.dataset.totalStanzas || '0', 10);
    if (total <= 0) return;
    const items = lyrics.querySelectorAll('[data-stanza]');
    let activeIdx = -1;
    let activated = false;
    player.addEventListener('play', function() {{
      if (!activated) {{ lyrics.classList.remove('idle'); activated = true; }}
    }});
    player.addEventListener('timeupdate', function() {{
      const dur = player.duration;
      if (!dur || isNaN(dur)) return;
      const idx = Math.min(total, Math.floor((player.currentTime / dur) * total) + 1);
      if (idx === activeIdx) return;
      activeIdx = idx;
      items.forEach(function(el) {{
        if (parseInt(el.dataset.stanza, 10) === idx) {{
          el.classList.add('active');
          el.scrollIntoView({{behavior: 'smooth', block: 'center'}});
        }} else {{
          el.classList.remove('active');
        }}
      }});
    }});
    player.addEventListener('ended', function() {{
      items.forEach(function(el) {{ el.classList.remove('active'); }});
      lyrics.classList.add('idle');
      activated = false;
      activeIdx = -1;
    }});
  }})();
</script>
</body>
</html>"""
    # no-cache on the HTML so each fresh visit re-evaluates the
    # cover/video mtimes; the embedded URLs are themselves
    # fingerprinted, so the actual binary fetches are cache-friendly.
    return HTMLResponse(
        html,
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


# Public binary endpoints use mtime-fingerprinted URLs (?v=N in the
# share page HTML), so the same URL is always the same bytes — safe
# to mark immutable. WhatsApp / Twitter / iMessage will cache these
# aggressively which is what we want; cache invalidation happens
# automatically via the new ?v= when the file changes.
_PUBLIC_BINARY_CACHE_HEADERS = {
    "Cache-Control": "public, max-age=604800, immutable",
}


@app.get("/p/{token}/video", include_in_schema=False)
def shared_song_video(token: str):
    """No-auth video endpoint for the public share page."""
    run_dir, _ = _resolve_shared_song(token)
    path = run_dir / "final.mp4"
    if not path.exists():
        raise HTTPException(404, "video not found")
    return FileResponse(
        path, media_type="video/mp4", headers=_PUBLIC_BINARY_CACHE_HEADERS,
    )


@app.get("/p/{token}/cover", include_in_schema=False)
def shared_song_cover(token: str):
    """No-auth cover endpoint for the public share page (used by
    OG image meta + the <video> poster)."""
    run_dir, _ = _resolve_shared_song(token)
    path = run_dir / "cover.png"
    if not path.exists():
        raise HTTPException(404, "cover not found")
    return FileResponse(
        path, media_type="image/png", headers=_PUBLIC_BINARY_CACHE_HEADERS,
    )


# ---------------------------------------------------------------------------
# Flutter web SPA — served at /app/* from the same Cloud Run service.
#
# This intentionally lives at the BOTTOM of the file, after every API
# route is registered, so that:
#   1. The /app mount only ever catches paths under /app/...
#   2. The "/" handler is the LAST root-level route registered, and only
#      claims paths nothing else has claimed.
#
# Bundling the SPA on the same origin avoids CORS for the app and keeps
# us on a single deploy unit. The /app/ subpath is encoded into the
# Flutter build via --base-href /app/ in scripts/build-and-push.sh.
# ---------------------------------------------------------------------------
_STATIC_WEB_DIR = Path(__file__).resolve().parent.parent / "static" / "web"
if _STATIC_WEB_DIR.exists() and (_STATIC_WEB_DIR / "index.html").exists():
    app.mount(
        "/app",
        StaticFiles(directory=str(_STATIC_WEB_DIR), html=True),
        name="spa",
    )


# Cache-Control middleware for SPA entry points.
#
# The default StaticFiles response has no Cache-Control header, which
# means browsers and CDNs may cache flutter_service_worker.js and
# flutter_bootstrap.js for an undefined duration. When that happens,
# users keep loading the OLD bundle even after a deploy because their
# browser never re-checks the SW file with the server.
#
# Fix: explicitly mark the SW + bootstrap files as no-cache. Their
# contents change every build (each carries a fresh version hash), so
# caching them is always wrong.
_NO_CACHE_PATHS = frozenset({
    "/app/flutter_service_worker.js",
    "/app/flutter_bootstrap.js",
    "/app/index.html",
    "/app/",
})


@app.middleware("http")
async def _no_cache_spa_entry_points(request, call_next):
    response = await call_next(request)
    if request.url.path in _NO_CACHE_PATHS:
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


@app.get("/", include_in_schema=False)
def _root():
    """Visitors at the bare Cloud Run URL get bounced to the SPA when it's
    bundled, or a tiny JSON breadcrumb when the image was built without it
    (e.g. backend-only iteration)."""
    if (_STATIC_WEB_DIR / "index.html").exists():
        return RedirectResponse("/app/")
    return {"service": "faceless-api", "ok": True}
