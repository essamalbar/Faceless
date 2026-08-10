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
import uuid
import os
import re
import signal
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (
    FileResponse,
    JSONResponse,
    RedirectResponse,
    Response,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from pipeline.auth import User, require_user, require_user_header_or_query
from pipeline.observability import setup_logging, log_exception, get_logger
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

# Bump this to force every user to re-accept the ToS/Privacy policy before the
# next paid/generation action. `_require_terms_accepted` compares a profile's
# recorded `tos_accepted_version` against this exact string.
CURRENT_LEGAL_VERSION = "2026-08-05"

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
    # Video render mode. "static" = single cover still over audio (1 credit);
    # "cinematic" = beat-synced multi-scene pool (3 credits).
    video_mode: str = "static"
    # Make this song AS an artist: the artist's persona (voice) + default
    # style fill any fields the request left empty, and the run is stamped
    # with artist_id so it lands in the artist's discography. 404 if unknown.
    artist_id: str | None = None
    # Arabic dialect for the lyrics (msa/egyptian/khaleeji/levantine/iraqi).
    dialect: str | None = None
    # A&R quality pipeline (2026-08-03 spec). "standard" = today's single-job
    # path. "premium" = best-of-N + Gemini A&R judge + master, surcharged.
    quality_tier: str = "standard"   # "standard" | "premium" (best-of-N + A&R)
    # Tier-3 legal: the caller must attest they own / have the rights to the
    # source material before we generate. Defaults False so an omitting client
    # is rejected 400 (ownership_not_attested) rather than silently allowed.
    ownership_attested: bool = False

    @field_validator("dialect")
    @classmethod
    def _check_dialect(cls, v: str | None) -> str | None:
        if v is not None and v not in (
                "msa", "egyptian", "khaleeji", "levantine", "iraqi"):
            raise ValueError("unknown dialect")
        return v

    @field_validator("video_mode")
    @classmethod
    def _check_video_mode(cls, v: str) -> str:
        if v not in ("static", "cinematic"):
            raise ValueError("video_mode must be 'static' or 'cinematic'")
        return v

    @field_validator("quality_tier")
    @classmethod
    def _check_quality_tier(cls, v: str) -> str:
        if v not in ("standard", "premium"):
            raise ValueError("quality_tier must be 'standard' or 'premium'")
        return v


# Whitelist of Suno model ids the user can pick from. V3_5 is the
# obvious-AI sound and explicitly excluded per spec quality gate.
_ALLOWED_SUNO_MODELS = frozenset({"V5_5", "V5", "V4_5", "V4"})

_YOUTUBE_RE = re.compile(
    r"^https?://((?:www|m|music)\.)?(youtube\.com/watch\?[\w=&%-]*v=|youtu\.be/|"
    r"youtube\.com/shorts/)[\w-]{6,}", re.IGNORECASE)


class CreateSongImportRequest(BaseModel):
    youtube_url: str
    instruction: str | None = None
    language: str = "ar"
    video_mode: str = "static"
    vocal_gender: str | None = "m"
    suno_model: str | None = None
    # Tier-3 legal: attest ownership / rights to the imported source material.
    ownership_attested: bool = False

    @field_validator("youtube_url")
    @classmethod
    def _check_url(cls, v: str) -> str:
        if not _YOUTUBE_RE.match(v.strip()):
            raise ValueError("youtube_url must be a YouTube watch/share/shorts URL")
        return v.strip()

    @field_validator("video_mode")
    @classmethod
    def _check_video_mode(cls, v: str) -> str:
        if v not in ("static", "cinematic"):
            raise ValueError("video_mode must be 'static' or 'cinematic'")
        return v


class SongScriptResponse(BaseModel):
    title: str
    lyrics: str
    style_prompt: str
    cover_prompt: str
    language: str
    cost_credits: int
    cost_usd: float
    video_mode: str = "static"
    # Premium-tier disclosure shown at the approve gate before spend
    # (best-of-N + A&R + master — up to N takes, ~$X, N credits). None for
    # standard-tier songs.
    max_spend_note: str | None = None


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


class ArtistSummary(BaseModel):
    id: str
    name: str
    handle: str
    bio: str = ""
    persona_id: str | None = None
    avatar_run_id: str | None = None
    avatar_upload: str | None = None
    default_style: str = ""
    default_language: str = "ar"
    default_vocal_gender: str = "m"
    # Channel Autopilot: publish each finished song to YouTube automatically.
    auto_publish_youtube: bool = False
    # Channel Autopilot: a free draft each morning from the day's trends.
    morning_drafts: bool = False
    # Arabic dialect identity (msa/egyptian/khaleeji/levantine/iraqi, "" = unset).
    default_dialect: str = ""
    created_at: str
    song_count: int = 0


class CreateArtistRequest(BaseModel):
    name: str
    handle: str | None = None  # auto-slugged from name when omitted
    bio: str = ""
    default_style: str = ""
    default_language: str = "ar"
    default_vocal_gender: str = "m"


class PatchArtistRequest(BaseModel):
    name: str | None = None
    handle: str | None = None
    bio: str | None = None
    persona_id: str | None = None
    avatar_run_id: str | None = None
    default_style: str | None = None
    default_language: str | None = None
    default_vocal_gender: str | None = None
    auto_publish_youtube: bool | None = None
    morning_drafts: bool | None = None
    default_dialect: str | None = None


class CreateArtistFromSongRequest(BaseModel):
    run_id: str
    name: str
    handle: str | None = None
    take: int | None = None  # defaults to the run's chosen_take


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
    # True when the song's final.mp4 was assembled with the brand-mark
    # PNG overlay + MP4 container metadata. Songs from before the
    # watermark feature land with watermarked=False (missing key reads
    # as None → treated as False by the Flutter UI). Drives the
    # "Apply watermark" CTA on the song detail screen.
    watermarked: bool = False
    # "static" (single cover still) or "cinematic" (beat-synced multi-scene
    # pool). Older songs without the key read as "static".
    video_mode: str = "static"
    # Artist Core: which artist this song belongs to (None = unassigned).
    # artist_name is denormalized into summaries so lists render without
    # an extra /artists call.
    artist_id: str | None = None
    artist_name: str | None = None
    # Distribution: user-confirmed "this song is live on stores" flag
    # (set via POST /songs/{id}/mark-released after the manual upload).
    released: bool = False
    # YouTube auto-publish: the published video URL (None = not published).
    youtube_url: str | None = None
    # Morning drafts: how this song originated + the brief's "why now" line.
    source: str | None = None
    trend_rationale: str | None = None


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
    payment_status: str = "active"    # 'active' | 'past_due' (dunning flag)
    balance: int
    terms_current: bool = True        # false if the user must (re-)accept the ToS
    email_confirmed: bool = True      # false if the user's email is unconfirmed


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

setup_logging()


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception):
    # Catch-all for genuinely-unhandled 5xx. FastAPI routes HTTPException /
    # RequestValidationError to their own handlers, so 402/404/409/422 are
    # unaffected — this only fires for real server errors, surfacing them in
    # Cloud Error Reporting instead of a bare stack trace.
    log_exception(exc, where="api", path=request.url.path, method=request.method)
    return JSONResponse(status_code=500, content={"detail": "internal error"})

# CORS — the Flutter web app loads from localhost:5xxxx (or a Cloudflare
# Tunnel URL) and calls this API on a different origin. Browsers block
# cross-origin requests unless the server explicitly opts in. The bearer
# token is what actually gates access; the CORS allowlist defaults to
# permissive (`*`) because this is solo-user software, but an operator can
# lock it down to specific origins via FACELESS_CORS_ORIGINS (comma list).
def _cors_origins() -> list[str]:
    """Allowed CORS origins. Default `["*"]`; override with a comma-separated
    FACELESS_CORS_ORIGINS (e.g. `https://a.com,https://b.com`). Blanks and
    surrounding whitespace are stripped."""
    raw = os.environ.get("FACELESS_CORS_ORIGINS", "*")
    return [o.strip() for o in raw.split(",") if o.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
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


def _admin_target_user(user_id: str) -> "User":
    """Validate a cross-user path param against traversal and wrap it as a
    role='user' target so refund logic credits the real user (a service user
    would no-op). Same allowlist as _run_dir's run_id check."""
    if not _RUN_ID_RE.fullmatch(user_id):
        raise HTTPException(400, "invalid user_id")
    return User(id=user_id, email=None, role="user")


def _admin_emails() -> set[str]:
    """Lowercased set of super-admin emails from FACELESS_ADMIN_EMAILS
    (comma-separated). Read fresh each call so config/tests take effect."""
    raw = os.environ.get("FACELESS_ADMIN_EMAILS", "")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def _is_admin(user: "User") -> bool:
    if user.role == "service":
        return True
    return bool(user.email and user.email.strip().lower() in _admin_emails())


def _require_admin(user: "User") -> None:
    """Gate for the control panel: the service token (CLI/cron) OR a logged-in
    user whose email is in the FACELESS_ADMIN_EMAILS allowlist. Everyone else 403."""
    if not _is_admin(user):
        raise HTTPException(403, "admin access required")


# ---------------------------------------------------------------------------
# Admin analytics — plan → USD pricing + shared revenue aggregation.
# ---------------------------------------------------------------------------

_PLAN_PRICE_CACHE: dict[str, float] = {}
_PLAN_BY_GRANT = {12: "starter", 60: "creator", 200: "pro"}  # grant credits → plan


def _plan_price_usd() -> dict[str, float]:
    """{plan: monthly_usd} from Stripe Prices (env STRIPE_PRICE_*), cached.
    Falls back to the published $9/$29/$79 if Stripe is unavailable so the
    dashboard still renders. Never raises."""
    global _PLAN_PRICE_CACHE
    if _PLAN_PRICE_CACHE:
        return _PLAN_PRICE_CACHE
    fallback = {"starter": 9.0, "creator": 29.0, "pro": 79.0}
    out = dict(fallback)
    try:
        import stripe
        stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
        for plan, env in (("starter", "STRIPE_PRICE_STARTER"),
                          ("creator", "STRIPE_PRICE_CREATOR"), ("pro", "STRIPE_PRICE_PRO")):
            pid = os.environ.get(env)
            if pid and stripe.api_key:
                p = stripe.Price.retrieve(pid)
                amt = getattr(p, "unit_amount", None)
                if amt:
                    out[plan] = round(amt / 100.0, 2)
    except Exception:
        pass
    _PLAN_PRICE_CACHE = out
    return out


def _revenue_dict() -> dict:
    """Full /admin/revenue payload. Derives dollar revenue from
    subscription_renewal rows (plan inferred from grant amount via
    _PLAN_BY_GRANT × _plan_price_usd), and credits_granted from all positive
    grant-side ledger rows. Shared by /admin/revenue and /admin/kpis."""
    from pipeline import db
    prices = _plan_price_usd()
    # One combined fetch of the grant-side kinds: subscription_renewal drives
    # $revenue + renewal counts; topup/admin_credit add to credits_granted.
    rows = db.list_transactions_by_kinds(
        ["subscription_renewal", "topup", "admin_credit"])
    now = datetime.now(timezone.utc)
    current_month = now.strftime("%Y-%m")
    cutoff_day = (now - timedelta(days=29)).strftime("%Y-%m-%d")

    renewals_by_plan = {"starter": 0, "creator": 0, "pro": 0}
    revenue_usd_total = 0.0
    revenue_usd_mtd = 0.0
    credits_granted = 0
    day_rev: dict[str, float] = {}
    day_cnt: dict[str, int] = {}

    for r in rows:
        amt = r.amount or 0
        if amt > 0:
            credits_granted += amt
        if r.kind != "subscription_renewal":
            continue
        created = r.created_at or ""
        day, month = created[:10], created[:7]
        plan = _PLAN_BY_GRANT.get(int(amt)) if amt else None
        if plan:
            renewals_by_plan[plan] += 1
            price = prices.get(plan, 0.0)
            revenue_usd_total += price
            if month == current_month:
                revenue_usd_mtd += price
            if day:
                day_rev[day] = day_rev.get(day, 0.0) + price
        if day:
            day_cnt[day] = day_cnt.get(day, 0) + 1

    by_day = [
        {"date": d, "revenue_usd": round(day_rev.get(d, 0.0), 2),
         "renewals": day_cnt[d]}
        for d in sorted(day_cnt) if d >= cutoff_day
    ]
    return {
        "prices": prices,
        "renewals_by_plan": renewals_by_plan,
        "revenue_usd_total": round(revenue_usd_total, 2),
        "revenue_usd_mtd": round(revenue_usd_mtd, 2),
        "credits_granted": credits_granted,
        "credits_outstanding": sum(db.list_balances().values()),
        "by_day": by_day,
    }


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
    """LLM router: Anthropic → Gemini → Groq, best-available-first.

    Quality order for Arabic lyrics: Anthropic (best, paid) > Gemini
    (very good, FREE tier via an AI Studio key) > Groq/Llama (weak — last
    resort only). Every configured provider is chained with FallbackLLM so
    an upstream failure (exhausted credits, outage) degrades one step
    instead of hard-failing; each hop records the degradation marker that
    drives the in-app quality banner. Inlined here so the script-gen call
    doesn't require importing run.py (which pulls every pipeline stage)."""
    import os
    providers = []
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
        from pipeline.llm import GeminiClient
        return GeminiClient()  # raises a clear GEMINI_API_KEY error
    from pipeline.llm import FallbackLLM
    from pipeline.llm_groq import GroqClient
    chain = providers[-1]
    for provider in reversed(providers[:-1]):
        # The quality-degraded banner only fires when we drop INTO the weak
        # writer (Groq). Anthropic→Gemini is a quality-fine hop — a permanent
        # banner there would just train the user to ignore alarms.
        into_weak = isinstance(chain, GroqClient)
        chain = FallbackLLM(
            provider, chain,
            on_fallback=_record_llm_fallback if into_weak else None)
    return chain


def _llm_fallback_marker() -> Path:
    return _out_root() / "llm_fallback.json"


def _writer_tier_status() -> dict:
    """Which LLM writer the API would use, plus whether a runtime degradation
    was recorded — surfaced on /healthz so an operator can spot a silent
    Anthropic→lower fallback (e.g. exhausted credits) without a paid render.

    `writer_tier` mirrors `_build_llm()`'s env-key preference order
    (ANTHROPIC → GEMINI → GROQ), reporting the top *configured* provider or
    `"none"` when no LLM key is set. `writer_degraded` is True when a
    runtime fallback marker exists under the out-root."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        tier = "anthropic"
    elif os.environ.get("GEMINI_API_KEY"):
        tier = "gemini"
    elif os.environ.get("GROQ_API_KEY"):
        tier = "groq"
    else:
        tier = "none"
    return {"writer_tier": tier, "writer_degraded": _llm_fallback_marker().exists()}


def _record_llm_fallback(exc: Exception) -> None:
    """Persist a 'lyrics quality degraded' marker when the primary LLM fails
    and Groq takes over — the UI banners off this instead of the user
    discovering weaker Arabic lyrics after a paid render. Best-effort."""
    try:
        p = _llm_fallback_marker()
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(json.dumps({
            "last_fallback_at":
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "error": str(exc)[:300],
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(p)
    except Exception:
        pass


@app.get("/system/llm-status")
def llm_status(user: User = Depends(require_user)):
    """degraded=True when the primary LLM fell back to Groq within the last
    24h → the app shows a 'lyric quality reduced' banner."""
    p = _llm_fallback_marker()
    if not p.exists():
        return {"degraded": False, "last_fallback_at": None, "error": None}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        ts = datetime.fromisoformat(data.get("last_fallback_at"))
        age_h = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
        return {
            "degraded": age_h <= 24,
            "last_fallback_at": data.get("last_fallback_at"),
            "error": data.get("error"),
        }
    except Exception:
        return {"degraded": False, "last_fallback_at": None, "error": None}


def _build_song_llm():
    """Same router as _build_llm — Anthropic > Groq > Gemini."""
    return _build_llm()


_TRENDS_TTL_H = float(os.environ.get("TRENDS_TTL_H", "12"))


@app.get("/trends/briefs")
def trend_briefs(refresh: bool = False, language: str = "ar",
                 user: User = Depends(require_user)):
    """Trend Engine: timely, ready-to-approve song briefs (cached per user,
    TRENDS_TTL_H freshness; ?refresh=1 forces new ideas). Chart data comes
    from the official YouTube trending-music charts (SA/EG/AE) when
    YOUTUBE_API_KEY is set; otherwise the LLM works calendar-only. On LLM
    failure a stale cache is returned (stale=true) rather than an error."""
    from pipeline import trends as trends_mod

    user_root = _user_runs_root(user)
    cached = trends_mod.load_cache(user_root)
    if cached and not refresh:
        try:
            age_h = (datetime.now(timezone.utc)
                     - datetime.fromisoformat(cached["generated_at"])
                     ).total_seconds() / 3600
            if age_h <= _TRENDS_TTL_H:
                return {**cached, "stale": False}
        except (KeyError, TypeError, ValueError):
            pass  # unreadable timestamp → regenerate

    api_key = os.environ.get("YOUTUBE_API_KEY", "")
    trending = trends_mod.fetch_trending_music(api_key) if api_key else []
    today = datetime.now(timezone.utc).date().isoformat()
    try:
        briefs = trends_mod.build_briefs(
            _build_song_llm(), trending, language=language, today=today)
    except Exception as e:
        if cached:
            return {**cached, "stale": True}
        raise HTTPException(502, f"trend briefs unavailable: {e}")
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    trends_mod.save_cache(user_root, generated_at, briefs)
    return {"generated_at": generated_at, "briefs": briefs, "stale": False}


# ---------------------------------------------------------------------------
# Morning drafts — the autopilot's second gear. Cloud Scheduler hits the
# admin endpoint daily; each opted-in artist gets a FREE draft written from
# the freshest trend brief. Approval (and billing) is untouched.
# Spec: docs/superpowers/specs/2026-07-17-morning-drafts-design.md.
# ---------------------------------------------------------------------------


def _write_song_draft(
    user_id: str,
    user_root: Path,
    *,
    theme: str,
    style_hint: str | None,
    language: str,
    artist: dict,
    source: str,
    trend_rationale: str | None,
) -> str:
    """Writer pass for a server-initiated draft (same shape create_song
    produces): run dir + state + LLM script + song.json + awaiting_approval.
    $0 by construction. Raises on LLM failure (run marked failed first)."""
    from pipeline.song_lyrics import generate_song_script

    user_root.mkdir(parents=True, exist_ok=True)
    run_id = _make_run_id(root=user_root)
    run_dir = user_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    _write_state(
        run_dir,
        kind="song",
        status="writing_lyrics",
        user_id=user_id,
        theme=theme,
        video_mode="static",
        artist_id=artist["id"],
        source=source,
        trend_rationale=trend_rationale,
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    try:
        script = generate_song_script(
            llm=_build_song_llm(), theme=theme, custom_lyrics=None,
            style_hint=style_hint, language=language,
            dialect=artist.get("default_dialect") or None)
    except Exception as e:
        _write_state(run_dir, status="failed",
                     last_error=f"lyrics LLM failed: {e}")
        raise
    (run_dir / "song.json").write_text(json.dumps({
        "title": script.title,
        "lyrics": script.lyrics,
        "style_prompt": script.style_prompt,
        "cover_prompt": script.cover_prompt,
        "language": script.language,
        "vocal_gender": artist.get("default_vocal_gender") or "m",
        "persona_id": artist.get("persona_id"),
        "suno_model": None,
        "video_mode": "static",
        "art_direction": script.art_direction,
        "scene_prompts": script.scene_prompts,
        # Producer-pass outputs — persist so run.py sends the genre-aware
        # negatives to Suno (not just the generic hardcoded fallback).
        "negative_tags": script.negative_tags,
        "style_source": script.style_source,
        "writer_tier": script.writer_tier,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "lyrics.txt").write_text(script.lyrics, encoding="utf-8")
    _write_state(run_dir, status="awaiting_approval", title=script.title)
    return run_id


def _has_morning_draft_today(user_root: Path, artist_id: str) -> bool:
    """Idempotency: a NON-FAILED morning draft for this artist created today
    already exists (failed ones don't block — the next run retries)."""
    today = datetime.now(timezone.utc).date().isoformat()
    if not user_root.exists():
        return False
    for d in user_root.iterdir():
        if not d.is_dir():
            continue
        st = _read_state(d)
        if (st.get("source") == "morning_draft"
                and st.get("artist_id") == artist_id
                and str(st.get("created_at", "")).startswith(today)
                and st.get("status") != "failed"):
            return True
    return False


@app.post("/admin/run-morning-drafts")
def run_morning_drafts(user: User = Depends(require_user)):
    """Service-token only (Cloud Scheduler). Sweeps every user; each artist
    with morning_drafts=true gets one free draft from the freshest trend
    briefs. Idempotent per day; per-artist failures never abort the sweep."""
    from pipeline import artists as artists_mod
    from pipeline import trends as trends_mod

    _require_admin(user)

    created = skipped = failed = 0
    details: list[dict] = []
    root = _out_root()
    if not root.exists():
        return {"created": 0, "skipped": 0, "failed": 0, "details": []}

    for user_dir in sorted(root.iterdir()):
        if not user_dir.is_dir():
            continue
        artists = [a for a in artists_mod.load_artists(user_dir)
                   if a.get("morning_drafts")]
        if not artists:
            continue
        uid = user_dir.name

        # Brief pool for this user: cached when fresh, else generated in the
        # first opted-in artist's language.
        briefs: list[dict] = []
        cached = trends_mod.load_cache(user_dir)
        if cached:
            try:
                age_h = (datetime.now(timezone.utc)
                         - datetime.fromisoformat(cached["generated_at"])
                         ).total_seconds() / 3600
                if age_h <= _TRENDS_TTL_H:
                    briefs = cached["briefs"]
            except (KeyError, TypeError, ValueError):
                pass
        if not briefs:
            try:
                api_key = os.environ.get("YOUTUBE_API_KEY", "")
                trending = (trends_mod.fetch_trending_music(api_key)
                            if api_key else [])
                briefs = trends_mod.build_briefs(
                    _build_song_llm(), trending,
                    language=artists[0].get("default_language", "ar"),
                    today=datetime.now(timezone.utc).date().isoformat())
                trends_mod.save_cache(
                    user_dir,
                    datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    briefs)
            except Exception as e:
                failed += len(artists)
                details.append({"user": uid, "error": f"briefs failed: {e}"})
                continue

        for i, artist in enumerate(artists):
            if _has_morning_draft_today(user_dir, artist["id"]):
                skipped += 1
                continue
            brief = briefs[i % len(briefs)]
            try:
                run_id = _write_song_draft(
                    uid, user_dir,
                    theme=brief["theme"],
                    # Artist's own style wins (voice/brand consistency);
                    # the brief's style is the fallback.
                    style_hint=(artist.get("default_style")
                                or brief.get("style_hint") or None),
                    language=artist.get("default_language", "ar"),
                    artist=artist,
                    source="morning_draft",
                    trend_rationale=brief.get("rationale"),
                )
                created += 1
                details.append({"user": uid, "artist": artist["name"],
                                "run_id": run_id})
            except Exception as e:
                failed += 1
                details.append({"user": uid, "artist": artist["name"],
                                "error": str(e)[:200]})
    return {"created": created, "skipped": skipped, "failed": failed,
            "details": details}


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
    return {"ok": True, **_writer_tier_status()}


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
            payment_status="active",
            balance=0,
            terms_current=True,
            email_confirmed=True,
        )
    from pipeline.db import get_balance, get_user_profile
    profile = get_user_profile(user.id)
    return PlanResponse(
        plan=(profile.current_plan if profile else "free"),
        current_period_end=(profile.current_period_end if profile else None),
        cancel_at_period_end=(profile.cancel_at_period_end if profile else False),
        payment_status=(profile.payment_status if profile else "active"),
        balance=get_balance(user.id),
        terms_current=(
            bool(profile)
            and profile.tos_accepted_version == CURRENT_LEGAL_VERSION
        ),
        email_confirmed=user.email_confirmed,
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require_terms_accepted(user: User) -> None:
    """Soft-gate for paid/generation actions. Service tokens bypass. Raises 403
    with a machine-readable code the app catches to prompt (re-)acceptance of
    the current ToS/Privacy policy."""
    if user.role == "service":
        return
    from pipeline.db import get_user_profile
    profile = get_user_profile(user.id)
    if profile is None or profile.tos_accepted_version != CURRENT_LEGAL_VERSION:
        raise HTTPException(
            status_code=403,
            detail={"code": "terms_not_accepted",
                    "version": CURRENT_LEGAL_VERSION},
        )


def _require_email_confirmed(user: User) -> None:
    """Email-confirmation backstop for paid/generation actions. Service tokens
    bypass. Raises 403 with a machine-readable code the app catches to prompt
    the user to confirm their email. Conservative default-allow: only fires
    when the token carried an EXPLICIT unconfirmed signal (see
    `verify_supabase_jwt`), so a legit user with an absent claim is never
    blocked. This is a code-layer backstop atop Supabase's project-level
    "Confirm email" toggle (the primary control)."""
    if user.role == "service":
        return
    if user.email_confirmed is False:
        raise HTTPException(
            status_code=403,
            detail={"code": "email_not_confirmed"},
        )


def _screen_content(*texts: str | None, user: User | None = None,
                    run_id: str | None = None) -> None:
    """Reject user-supplied free text that trips the moderation deny-list.

    Inputs-only: called on create/regenerate endpoints for their user-text
    fields, AFTER the terms/email/rate-limit gates and BEFORE any generation.
    Applies to ALL callers — service tokens are NOT exempt (moderation is a
    property of the content, not the caller). On a hit, logs a `[moderation]`
    WARNING carrying only the MATCH COUNT (never the matched terms or the
    text — the Tier-2 alert metric keys off the `[moderation]` token) and
    raises 400 `content_rejected`."""
    from pipeline import moderation
    try:
        moderation.assert_clean(*texts)
    except moderation.ModerationError as exc:
        get_logger().warning(
            "[moderation] content_rejected user=%s run=%s terms=%d",
            getattr(user, "id", None), run_id, len(exc.terms),
        )
        raise HTTPException(400, detail={"code": "content_rejected"})


class AcceptTermsResponse(BaseModel):
    ok: bool
    version: str


@app.post("/account/accept-terms", response_model=AcceptTermsResponse)
def accept_terms(user: User = Depends(require_user)):
    """Record that the caller accepted the current ToS/Privacy version.

    Service tokens (CLI / cron) have no profile row and skip the write."""
    if user.role != "service":
        from pipeline.db import upsert_user_profile
        upsert_user_profile(
            user.id,
            tos_accepted_version=CURRENT_LEGAL_VERSION,
            tos_accepted_at=_now_iso(),
        )
    return AcceptTermsResponse(ok=True, version=CURRENT_LEGAL_VERSION)


class DeleteAccountRequest(BaseModel):
    # Typed confirmation guard. Defaulted (not required) so an absent field is
    # a 400 from our own check — not a pydantic 422 — matching the wrong-value
    # path. The caller must type exactly "DELETE".
    confirm: str = ""


@app.get("/account/export", dependencies=[Depends(require_user)])
def export_account(user: User = Depends(require_user)):
    """GDPR data-portability: return everything we hold for the caller —
    profile, the full credit-transaction ledger, and metadata for their runs.

    Read-only; NOT gated behind terms/email acceptance (a user must be able to
    exercise their data rights regardless). Service tokens have no user data to
    export → 400."""
    if user.role == "service":
        raise HTTPException(400, "service tokens have no account data to export")
    from pipeline.db import get_user_profile, list_transactions

    profile = get_user_profile(user.id)
    transactions = list_transactions(user.id, limit=10_000)
    runs_root = _user_runs_root(user)
    runs: list[RunSummary] = []
    if runs_root.exists():
        for p in sorted(runs_root.iterdir()):
            if p.is_dir():
                runs.append(_summarize(p))
    return {
        "profile": profile,
        "transactions": transactions,
        "runs": runs,
    }


@app.post("/account/delete", dependencies=[Depends(require_user)])
def delete_account(req: DeleteAccountRequest, user: User = Depends(require_user)):
    """GDPR erasure. IRREVERSIBLE. Requires a typed `confirm == "DELETE"`.

    Steps (best-effort, each logged): purge the user's on-disk artifacts,
    scrub profile PII (`anonymize_user_profile`), then admin-delete the
    Supabase auth user. The financial ledger (`credit_transactions`) is
    RETAINED for tax/chargeback and is never touched here.

    Guards run BEFORE any side effect: service/admin tokens cannot self-delete
    (403), and a mistyped/absent confirmation is refused (400)."""
    if user.role == "service":
        raise HTTPException(403, "service tokens cannot self-delete")
    if req.confirm != "DELETE":
        raise HTTPException(400, 'confirm must be exactly "DELETE"')

    import shutil
    log = get_logger()

    runs_root = _user_runs_root(user)
    try:
        shutil.rmtree(runs_root, ignore_errors=True)
        log.info("[account_delete] purged artifacts user=%s", user.id)
    except Exception:  # pragma: no cover - rmtree(ignore_errors) rarely raises
        log.exception("[account_delete] artifact purge failed user=%s", user.id)

    from pipeline.db import anonymize_user_profile, delete_auth_user
    try:
        anonymize_user_profile(user.id)
        log.info("[account_delete] anonymized profile user=%s", user.id)
    except Exception:
        log.exception("[account_delete] profile anonymize failed user=%s", user.id)

    try:
        delete_auth_user(user.id)
        log.info("[account_delete] deleted auth user=%s", user.id)
    except Exception:
        log.exception("[account_delete] auth-user delete failed user=%s", user.id)

    return {"ok": True}


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
    _require_terms_accepted(user)
    _require_email_confirmed(user)
    # Script generation is free for all signed-in users. The paywall fires
    # in /runs/{id}/approve when they try to render the paid stages.
    if req.theme not in VALID_THEMES:
        raise HTTPException(400, f"theme must be one of {sorted(VALID_THEMES)}")
    for i, b in enumerate(req.beats, start=1):
        if not (b.speaker or "").strip():
            raise HTTPException(400, f"beat {i}: speaker cannot be empty")
        if not b.english_motion.strip():
            raise HTTPException(400, f"beat {i}: english_motion is required")
    # Pasted scripts carry the primary user free text in the beats — the
    # arabic/english_motion/character_name go verbatim into script.json and
    # on to Veo, so they are inputs and get screened alongside theme/title.
    _screen_content(
        req.theme, req.title, req.premise, req.music_mood, req.global_setting,
        *(t for b in req.beats
          for t in (b.arabic, b.english_motion, b.character_name)),
        user=user,
    )

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
    _require_terms_accepted(user)
    _require_email_confirmed(user)
    # Script generation is free for all signed-in users. The paywall fires
    # in /runs/{id}/approve when they try to render the paid stages.
    if req.theme not in VALID_THEMES:
        raise HTTPException(400, f"theme must be one of {sorted(VALID_THEMES)}")
    _screen_content(req.theme, req.premise, user=user)

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
    _require_terms_accepted(user)
    _require_email_confirmed(user)
    # Script generation is free for all signed-in users. The paywall fires
    # in /runs/{id}/approve when they try to render the paid stages.
    if req.theme not in VALID_THEMES:
        raise HTTPException(400, f"theme must be one of {sorted(VALID_THEMES)}")
    _screen_content(req.theme, req.premise, user=user)

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
    _require_terms_accepted(user)
    _require_email_confirmed(user)
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
    _require_terms_accepted(user)
    _require_email_confirmed(user)
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
    _require_admin(user)
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


# ---------------------------------------------------------------------------
# /admin/re-assemble-song — service-token-only ffmpeg re-run for one song.
#
# Backfills the watermark + container metadata + new lyric-aware ASS into
# songs that were assembled before those features shipped. One request per
# song so a 5–10-minute batch doesn't hit Cloud Run's request timeout; the
# caller loops externally (a small shell script per the share index).
#
# Idempotent in the lossy sense — calling it twice on the same song burns
# ffmpeg cycles but doesn't corrupt anything. The atomic .tmp+replace
# write semantics inside assemble_song_video keep the served final.mp4
# valid throughout the operation; readers either see the previous file
# or the new one, never a torn read.
# ---------------------------------------------------------------------------

class ReAssembleAck(BaseModel):
    ok: bool
    user_id: str
    run_id: str
    title: str | None
    watermark: bool
    share_token: str | None
    duration_s: float


@app.post(
    "/admin/re-assemble-song/{user_id}/{run_id}",
    response_model=ReAssembleAck,
    dependencies=[Depends(require_user)],
)
def admin_re_assemble_song(
    user_id: str,
    run_id: str,
    user: User = Depends(require_user),
):
    """Rebuild final.mp4 for a single complete song. Adds the
    watermark + MP4 metadata that newer assemblies bake in. Service
    token required — normal users can't trigger ffmpeg jobs against
    other users' runs."""
    _require_admin(user)
    if not _RUN_ID_RE.fullmatch(user_id):
        raise HTTPException(400, "invalid user_id")
    if not _RUN_ID_RE.fullmatch(run_id):
        raise HTTPException(400, "invalid run_id")
    from pipeline import song_assemble
    run_dir = _out_root() / user_id / run_id
    if not run_dir.exists():
        raise HTTPException(404, f"run not found: {user_id}/{run_id}")
    try:
        state = _read_state(run_dir)
    except Exception as e:
        raise HTTPException(500, f"corrupt api_state.json: {e}")
    if state.get("kind") != "song":
        raise HTTPException(400, "not a song run")
    if state.get("status") != "complete":
        raise HTTPException(
            409, f"status is {state.get('status')!r}, not complete",
        )
    cover_path = run_dir / "cover.png"
    song_mp3 = run_dir / "song.mp3"
    out_mp4 = run_dir / "final.mp4"
    lyrics_json = run_dir / "lyrics.json"
    song_json = run_dir / "song.json"
    missing = [
        p.name for p in (cover_path, song_mp3, song_json) if not p.exists()
    ]
    if missing:
        raise HTTPException(
            409, f"missing inputs: {', '.join(missing)}",
        )
    try:
        script = json.loads(song_json.read_text(encoding="utf-8"))
        title = script.get("title")
        share_token = state.get("share_token")
        t0 = time.time()
        song_assemble.assemble_song_video(
            cover_path=cover_path,
            song_mp3=song_mp3,
            out_mp4=out_mp4,
            lyrics_json=lyrics_json if lyrics_json.exists() else None,
            title=title,
            share_token=share_token,
        )
        dur = time.time() - t0
        # Flip the watermarked flag in state.json so the UI knows the
        # song's final.mp4 now carries the brand mark + container
        # metadata. Defensive merge with the existing state to avoid
        # racing with concurrent state writers.
        try:
            _write_state(run_dir, watermarked=True)
        except Exception:
            # Flag write is best-effort. The watermark itself is already
            # baked into the MP4 — at worst the UI will keep offering
            # the button until next pipeline run rewrites state.
            pass
    except Exception as e:
        raise HTTPException(500, f"assembly failed: {type(e).__name__}: {e}")
    return ReAssembleAck(
        ok=True,
        user_id=user_id,
        run_id=run_id,
        title=title,
        watermark=True,
        share_token=share_token,
        duration_s=round(dur, 1),
    )


# ---------------------------------------------------------------------------
# Admin cross-user media streaming — lets the control panel play any user's
# generated song. The panel fetches WITH the Authorization: Bearer header
# (fetch → blob → <audio>), so header auth via require_user is correct — no
# ?token= query auth, which would leak the admin token into URLs. Both gate on
# _require_admin first, then validate BOTH path params against _RUN_ID_RE.
# ---------------------------------------------------------------------------

@app.get("/admin/songs/{user_id}/{run_id}/audio", dependencies=[Depends(require_user)])
def admin_song_audio(user_id: str, run_id: str, user: User = Depends(require_user)):
    _require_admin(user)
    if not _RUN_ID_RE.fullmatch(user_id):
        raise HTTPException(400, "invalid user_id")
    if not _RUN_ID_RE.fullmatch(run_id):
        raise HTTPException(400, "invalid run_id")
    p = _out_root() / user_id / run_id / "song.mp3"
    if not p.exists():
        raise HTTPException(404, "song.mp3 not found")
    return FileResponse(str(p), media_type="audio/mpeg",
                        headers={"Cache-Control": "no-store"})


@app.get("/admin/songs/{user_id}/{run_id}/cover", dependencies=[Depends(require_user)])
def admin_song_cover(user_id: str, run_id: str, user: User = Depends(require_user)):
    _require_admin(user)
    if not _RUN_ID_RE.fullmatch(user_id):
        raise HTTPException(400, "invalid user_id")
    if not _RUN_ID_RE.fullmatch(run_id):
        raise HTTPException(400, "invalid run_id")
    d = _out_root() / user_id / run_id
    for name, mt in (("cover.png", "image/png"), ("cover_thumb.jpg", "image/jpeg")):
        p = d / name
        if p.exists():
            return FileResponse(str(p), media_type=mt)
    raise HTTPException(404, "cover not found")


# ---------------------------------------------------------------------------
# Super-admin dashboard — service-token-gated cross-user READ endpoints.
# All four require a service token (never a user JWT) and mutate nothing.
# ---------------------------------------------------------------------------

@app.get("/admin/overview", dependencies=[Depends(require_user)])
def admin_overview(user: User = Depends(require_user)):
    _require_admin(user)
    from pipeline import db
    health = _writer_tier_status()
    root = _out_root()
    user_dirs = [p for p in root.iterdir() if p.is_dir()] if root.exists() else []
    try:
        activation = {**db.probe_activation(),
                      "unprobed": ["deduct_credits_fn", "uq_credit_grant_ref",
                                   "uq_credit_clawback_ref"]}
    except Exception as e:
        activation = {"error": str(e)}
    return {"health": health,
            "counts": {"user_dirs": len(user_dirs)},
            "activation": activation}


@app.get("/admin/users", dependencies=[Depends(require_user)])
def admin_list_users(limit: int = 100, offset: int = 0,
                     user: User = Depends(require_user)):
    _require_admin(user)
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    from pipeline import db
    try:
        profiles = db.list_user_profiles(limit, offset)
    except Exception as e:
        # user_profiles is SELECTed with the payment_status / tos_accepted_version
        # columns that only exist after the pending migrations run. Before that,
        # PostgREST returns a "column does not exist" error — surface it as an
        # actionable 503 instead of an opaque 500, since this is the exact state
        # an operator is in until they apply docs/operator/APPLY-MIGRATIONS.sql.
        s = str(e).lower()
        if ("does not exist" in s or "could not find" in s
                or "pgrst204" in s or "42703" in s):
            raise HTTPException(
                503,
                "Users unavailable: apply the pending Supabase migrations "
                "(docs/operator/APPLY-MIGRATIONS.sql), then retry.",
            ) from None
        raise
    balances = db.list_balances()
    emails = db.list_auth_users()
    return [{"id": p.id, "email": emails.get(p.id), "balance": balances.get(p.id, 0),
             "plan": p.current_plan, "payment_status": p.payment_status,
             "tos_accepted_version": p.tos_accepted_version} for p in profiles]


@app.get("/admin/runs", dependencies=[Depends(require_user)])
def admin_list_runs(limit: int = 50, offset: int = 0,
                    user_id: str | None = None,
                    user: User = Depends(require_user)):
    _require_admin(user)
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    root = _out_root()
    if not root.exists():
        return []
    if user_id is not None:
        if not _RUN_ID_RE.fullmatch(user_id):
            raise HTTPException(400, "invalid user_id")
        user_dirs = [root / user_id] if (root / user_id).is_dir() else []
    else:
        user_dirs = sorted([p for p in root.iterdir() if p.is_dir()])
    # Cap the walk: prod out-root is GCS-Fuse — never summarize every run.
    # Collect lightweight (mtime, uid, run_dir) tuples, sort, slice, THEN
    # summarize only the requested page.
    entries = []  # (mtime, uid, run_dir)
    for ud in user_dirs:
        for rd in ud.iterdir():
            if rd.is_dir():
                try:
                    mtime = rd.stat().st_mtime
                except OSError:
                    mtime = 0.0
                entries.append((mtime, ud.name, rd))
    entries.sort(key=lambda e: e[0], reverse=True)
    page = entries[offset:offset + limit]
    out = []
    for _mtime, uid, rd in page:
        summary = _summarize(rd)
        row = summary.model_dump() if hasattr(summary, "model_dump") else summary.dict()
        try:
            kind = _read_state(rd).get("kind")
        except Exception:
            kind = None
        row["user_id"] = uid
        row["kind"] = kind
        out.append(row)
    return out


@app.get("/admin/transactions", dependencies=[Depends(require_user)])
def admin_list_transactions(limit: int = 200, user_id: str | None = None,
                            user: User = Depends(require_user)):
    _require_admin(user)
    limit = max(1, min(limit, 500))
    from pipeline import db
    if user_id is not None:
        txns = db.list_transactions(user_id, limit)
    else:
        txns = db.list_transactions_all(limit)
    import dataclasses
    return [dataclasses.asdict(t) for t in txns]


# ---------------------------------------------------------------------------
# Super-admin dashboard — subscription / revenue / KPI analytics cards.
# All read-only; gated by _require_admin (service token OR allowlisted email).
# ---------------------------------------------------------------------------

@app.get("/admin/subscriptions", dependencies=[Depends(require_user)])
def admin_subscriptions(user: User = Depends(require_user)):
    _require_admin(user)
    from pipeline import db
    try:
        profiles = db.list_all_user_profiles_min()
    except Exception as e:
        # Selects payment_status / cancel_at_period_end, which only exist after
        # the pending migrations. Surface the actionable 503 (same as /admin/users)
        # instead of an opaque 500 while the operator hasn't applied them yet.
        s = str(e).lower()
        if ("does not exist" in s or "could not find" in s
                or "pgrst204" in s or "42703" in s):
            raise HTTPException(
                503,
                "Subscriptions unavailable: apply the pending Supabase migrations "
                "(docs/operator/APPLY-MIGRATIONS.sql), then retry.",
            ) from None
        raise
    by_plan = {"starter": 0, "creator": 0, "pro": 0, "free": 0, "other": 0}
    active = past_due = cancel_at_period_end = 0
    for p in profiles:
        plan = p.get("current_plan")
        if plan in ("starter", "creator", "pro"):
            by_plan[plan] += 1
        elif plan in ("free", "deleted", None):
            by_plan["free"] += 1
        else:
            by_plan["other"] += 1
        status = p.get("payment_status")
        if status == "active":
            active += 1
        elif status == "past_due":
            past_due += 1
        if p.get("cancel_at_period_end"):
            cancel_at_period_end += 1
    return {"by_plan": by_plan, "active": active, "past_due": past_due,
            "cancel_at_period_end": cancel_at_period_end,
            "total_profiles": len(profiles)}


@app.get("/admin/revenue", dependencies=[Depends(require_user)])
def admin_revenue(user: User = Depends(require_user)):
    _require_admin(user)
    return _revenue_dict()


@app.get("/admin/kpis", dependencies=[Depends(require_user)])
def admin_kpis(user: User = Depends(require_user)):
    _require_admin(user)
    from pipeline import db
    # Each headline number is computed independently so one failing source
    # (e.g. the auth admin list) nulls only its own field instead of 500ing
    # the whole card.
    try:
        total_users = len(db.list_auth_users())
    except Exception:
        total_users = None
    try:
        profiles = db.list_all_user_profiles_min()
        active_subscribers = sum(
            1 for p in profiles
            if p.get("payment_status") == "active"
            and p.get("current_plan") in ("starter", "creator", "pro"))
    except Exception:
        active_subscribers = None
    try:
        credits_outstanding = sum(db.list_balances().values())
    except Exception:
        credits_outstanding = None
    try:
        revenue_usd_mtd = _revenue_dict()["revenue_usd_mtd"]
    except Exception:
        revenue_usd_mtd = None
    return {"total_users": total_users, "active_subscribers": active_subscribers,
            "credits_outstanding": credits_outstanding,
            "revenue_usd_mtd": revenue_usd_mtd}


# ---------------------------------------------------------------------------
# Super-admin dashboard — service-token-gated cross-user WRITE endpoints.
# Each reuses the same *_impl the user-facing route uses, but resolves the
# target via _admin_target_user(user_id) so refunds credit the TARGET user's
# ledger (a role="user" wrapper), never the service caller (which no-ops).
# ---------------------------------------------------------------------------

@app.post("/admin/runs/{user_id}/{run_id}/cancel", response_model=CancelAck,
          dependencies=[Depends(require_user)])
def admin_cancel_run(user_id: str, run_id: str, user: User = Depends(require_user)):
    _require_admin(user)
    return _cancel_run_impl(_admin_target_user(user_id), run_id)


@app.post("/admin/songs/{user_id}/{run_id}/cancel",
          dependencies=[Depends(require_user)])
def admin_cancel_song(user_id: str, run_id: str, user: User = Depends(require_user)):
    _require_admin(user)
    return _cancel_song_impl(_admin_target_user(user_id), run_id)


@app.delete("/admin/runs/{user_id}/{run_id}", response_model=DeleteAck,
            dependencies=[Depends(require_user)])
def admin_delete_run(user_id: str, run_id: str, user: User = Depends(require_user)):
    _require_admin(user)
    return _delete_run_impl(_admin_target_user(user_id), run_id)


@app.delete("/admin/songs/{user_id}/{run_id}", status_code=204,
            dependencies=[Depends(require_user)])
def admin_delete_song(user_id: str, run_id: str, user: User = Depends(require_user)):
    _require_admin(user)
    return _delete_song_impl(_admin_target_user(user_id), run_id)


# ---------------------------------------------------------------------------
# Email/password admin login — how an allowlisted operator authenticates for
# the control panel (NOT admin-gated itself). Exchanges email+password for a
# Supabase session, but only for addresses in FACELESS_ADMIN_EMAILS.
# ---------------------------------------------------------------------------

class AdminLoginRequest(BaseModel):
    email: str
    password: str


def _supabase_password_login(email: str, password: str) -> dict:
    """Exchange email+password for a Supabase session via gotrue. Returns the
    JSON (contains access_token, expires_in, user). Raises RuntimeError on a
    non-2xx (bad credentials / unconfirmed email). Separated so tests mock it."""
    import httpx
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    anon = os.environ.get("SUPABASE_ANON_KEY", "")
    if not url or not anon:
        raise RuntimeError("supabase auth not configured")
    resp = httpx.post(
        f"{url}/auth/v1/token?grant_type=password",
        headers={"apikey": anon, "Content-Type": "application/json"},
        json={"email": email, "password": password},
        timeout=15,
    )
    if resp.status_code // 100 != 2:
        raise RuntimeError(f"login failed: {resp.status_code}")
    return resp.json()


@app.post("/admin/login")
def admin_login(req: AdminLoginRequest):
    email = (req.email or "").strip().lower()
    if email not in _admin_emails():
        # Don't reveal whether the password was right for a non-admin.
        raise HTTPException(403, "not authorized as an administrator")
    try:
        data = _supabase_password_login(req.email, req.password)
    except Exception:
        raise HTTPException(401, "invalid email or password") from None
    token = data.get("access_token")
    if not token:
        raise HTTPException(401, "invalid email or password")
    # Confirm the returned identity matches the requested admin email.
    tok_email = ((data.get("user") or {}).get("email") or "").strip().lower()
    if tok_email and tok_email not in _admin_emails():
        raise HTTPException(403, "not authorized as an administrator")
    return {"access_token": token,
            "email": tok_email or email,
            "expires_in": data.get("expires_in")}


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


def _delete_run_impl(user: "User", run_id: str) -> DeleteAck:
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
    return _delete_run_impl(user, run_id)


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


def _cancel_run_impl(user: "User", run_id: str) -> CancelAck:
    from pipeline.credits import refund_run_charges

    run_dir = _run_dir(run_id, user)

    # Never refund an already-delivered video: cancelling a completed run
    # (final.mp4 on disk) would hand back a free finished render. Mirrors
    # cancel_song's complete-guard. Video completion is derived from
    # final.mp4 by derive_status(), not stored in state["status"].
    if derive_status(run_dir) == "complete":
        raise HTTPException(409, "run already complete")

    state = _read_state(run_dir)
    pid = state.get("pid")

    # Stop the worker FIRST and wait for it to actually exit, THEN refund.
    # Cancel is now the sole refund path (a failed render keeps its charge —
    # see run.py's post-clip stages), so the refund must not race an in-flight
    # per-clip deduction: if we refunded before SIGTERM, a clip that lands
    # between the refund and the kill would leave the user re-charged with no
    # video. Killing first closes that window.
    killed_pid = None
    if _process_alive(pid, run_dir):
        _stop_process_and_wait(pid, run_dir=run_dir)
        killed_pid = pid

    # Re-check after reaping: the worker may have written final.mp4 during the
    # kill/wait window. If it delivered, don't refund a now-completed video.
    if derive_status(run_dir) == "complete":
        raise HTTPException(409, "run already complete")

    # Always attempt the refund — even if the process was already dead
    # (cancel-after-failed-state). Net-safe: a no-op when the user has zero
    # net charges for this run, and for service tokens.
    refunded = 0
    try:
        refunded = refund_run_charges(
            user,
            run_id=run_id,
            reason="run cancelled by user before completion",
        )
    except Exception as _e:
        # Refund failure is a billing anomaly — surface it (alert metric
        # matches "[billing]"). Must still NOT fail the cancel itself: the
        # kill path is the user-facing action; log + move on.
        get_logger().error("[billing] refund failed during cancel",
                            exc_info=_e, extra={"where": "cancel", "run_id": run_id})

    _write_state(
        run_dir,
        last_error=(
            f"cancelled by user (refunded {refunded} credits)"
            if refunded
            else "cancelled by user"
        ),
        last_action="cancel",
    )
    return CancelAck(run_id=run_id, killed_pid=killed_pid)


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
    return _cancel_run_impl(user, run_id)


@app.get("/runs/{run_id}/video",
         dependencies=[Depends(require_user_header_or_query)])
def get_video(run_id: str, request: Request,
              user: User = Depends(require_user_header_or_query)):
    run_dir = _run_dir(run_id, user)
    p = run_dir / "final.mp4"
    if not p.exists():
        raise HTTPException(404, "final.mp4 not produced yet")
    # Range-aware (see _serve_video) so videos over Cloud Run's ~32 MiB
    # response cap still play. no-store so the Repair-playback flow surfaces
    # newly re-muxed bytes instead of Chrome's cached pre-faststart file.
    return _serve_video(p, request, extra_headers={"Cache-Control": "no-store"})


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
    _require_terms_accepted(user)
    _require_email_confirmed(user)
    _enforce_llm_rate_limit(user)
    _screen_content(req.theme, req.custom_lyrics, req.style_hint, user=user)
    if user.role != "service" and not req.ownership_attested:
        raise HTTPException(400, detail={"code": "ownership_not_attested"})
    from pipeline.song_lyrics import generate_song_script
    from pipeline.config import load_config
    from pipeline.db import get_balance

    cfg = load_config(Path(os.environ.get(
        "FACELESS_CONFIG",
        str(REPO_ROOT / "config.yaml"),
    )))
    # song.json isn't written yet at this point, so price from the request.
    credits_required = _song_credit_amount(req.video_mode, req.quality_tier, cfg)

    if user.role != "service" and get_balance(user.id) < credits_required:
        _raise_402_insufficient_credits(get_balance(user.id), credits_required)

    # Artist Core: songs made AS an artist inherit the artist's voice +
    # default style for any field the request left empty. Explicit request
    # values always win. Resolved BEFORE any work so an unknown id is a
    # clean 404.
    persona_id = req.persona_id
    style_hint = req.style_hint
    dialect = req.dialect
    if req.artist_id:
        from pipeline import artists as artists_mod
        artist = artists_mod.find_by_id(
            artists_mod.load_artists(_user_runs_root(user)), req.artist_id)
        if artist is None:
            raise HTTPException(404, f"artist {req.artist_id!r} not found")
        if persona_id is None:
            persona_id = artist.get("persona_id")
        if not style_hint:
            style_hint = artist.get("default_style") or None
        if not dialect:
            dialect = artist.get("default_dialect") or None

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
        video_mode=req.video_mode,
        artist_id=req.artist_id,
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        # Tier-3 legal audit: persist the ownership attestation from the first
        # create-time write (survives a failed lyrics pass). Service callers
        # bypass the gate, so record the actual flag value rather than assume.
        ownership_attested=req.ownership_attested,
        ownership_attested_version=(
            CURRENT_LEGAL_VERSION if req.ownership_attested else None),
        ownership_attested_at=(_now_iso() if req.ownership_attested else None),
    )

    try:
        llm = _build_song_llm()
        script = generate_song_script(
            llm=llm,
            theme=req.theme,
            custom_lyrics=req.custom_lyrics,
            style_hint=style_hint,
            language=req.language,
            dialect=dialect,
            vocal_gender=req.vocal_gender,
        )
    except Exception as e:
        _write_state(run_dir, status="failed", last_error=f"lyrics LLM failed: {e}")
        raise HTTPException(500, f"lyrics generation failed: {e}")

    (run_dir / "song.json").write_text(
        json.dumps({
            "title": script.title,
            "lyrics": script.lyrics,
            "style_prompt": script.style_prompt,
            "negative_tags": script.negative_tags,
            "style_source": script.style_source,
            "writer_tier": script.writer_tier,
            "cover_prompt": script.cover_prompt,
            "language": script.language,
            # Voice-control fields persist into the worker's Suno call.
            # vocal_gender defaults to 'm' on the API side, but pass
            # through whatever the request specified.
            "vocal_gender": req.vocal_gender,
            "persona_id": persona_id,
            # Optional Suno model override. Validated against
            # _ALLOWED_SUNO_MODELS; None falls back to config default.
            "suno_model": (
                req.suno_model
                if req.suno_model in _ALLOWED_SUNO_MODELS
                else None
            ),
            # Render mode + cinematic art direction. video_mode drives the
            # 1-vs-3 credit price and the static-vs-beat-synced render path.
            "video_mode": req.video_mode,
            # A&R quality pipeline tier. Drives the credit surcharge + the
            # premium best-of-N/regenerate/master path in run.py.
            "quality_tier": req.quality_tier,
            "art_direction": script.art_direction,
            "scene_prompts": script.scene_prompts,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (run_dir / "lyrics.txt").write_text(script.lyrics, encoding="utf-8")
    _write_state(run_dir, status="awaiting_approval", title=script.title)

    return {"run_id": run_id, "status": "awaiting_approval"}


@app.post("/songs/import", status_code=201)
def import_song(req: CreateSongImportRequest, user: User = Depends(require_user)):
    """Start a YouTube-import song run. Writes a draft run and spawns the
    worker for the `analyzing` pre-stage (download + analyse + write an
    original script). No spend until the user approves the result."""
    _require_terms_accepted(user)
    _require_email_confirmed(user)
    _screen_content(req.instruction, user=user)
    if user.role != "service" and not req.ownership_attested:
        raise HTTPException(400, detail={"code": "ownership_not_attested"})
    from pipeline.config import load_config
    from pipeline.db import get_balance

    cfg = load_config(Path(os.environ.get(
        "FACELESS_CONFIG", str(REPO_ROOT / "config.yaml"))))
    # CreateSongImportRequest has no quality_tier field yet — premium best-of-N
    # for the YouTube-import path is out of scope (spec follow-ups); price standard.
    credits_required = _song_credit_amount(req.video_mode, "standard", cfg)
    if user.role != "service":
        balance = get_balance(user.id)
        if balance < credits_required:
            _raise_402_insufficient_credits(balance, credits_required)

    user_root = _user_runs_root(user)
    user_root.mkdir(parents=True, exist_ok=True)
    run_id = _make_run_id(root=user_root)
    run_dir = user_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    _write_state(
        run_dir,
        kind="song",
        status="analyzing",
        user_id=user.id,
        theme="(importing from YouTube…)",
        youtube_url=req.youtube_url,
        import_instruction=req.instruction,
        video_mode=req.video_mode,
        language=req.language,
        vocal_gender=req.vocal_gender,
        suno_model=(req.suno_model if req.suno_model in _ALLOWED_SUNO_MODELS else None),
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        # Tier-3 legal audit: persist the ownership attestation at create time.
        ownership_attested=req.ownership_attested,
        ownership_attested_version=(
            CURRENT_LEGAL_VERSION if req.ownership_attested else None),
        ownership_attested_at=(_now_iso() if req.ownership_attested else None),
    )
    args = ["--mode", "song", "--resume", str(run_dir)]
    pid = _SPAWN_FN(args, run_dir)
    _write_state(run_dir, pid=pid)
    return {"run_id": run_id, "status": "analyzing"}


# Cloud Run buffers the whole request (~32 MiB cap); a typical song MP3 is far
# under this, but reject early with a clear hint rather than a 500.
_UPLOAD_AUDIO_MAX_BYTES = 30 * 1024 * 1024
_AUDIO_EXTS = (".mp3", ".m4a", ".aac", ".wav", ".flac", ".ogg", ".opus", ".webm")


@app.post("/songs/upload-cover", status_code=201)
def upload_cover_song(
    file: UploadFile = File(...),
    instruction: str | None = Form(None),
    language: str = Form("ar"),
    video_mode: str = Form("static"),
    vocal_gender: str | None = Form("m"),
    suno_model: str | None = Form(None),
    artist_id: str | None = Form(None),
    audio_weight: float | None = Form(None),
    # Tier-3 legal: attest ownership / rights to the uploaded source audio.
    ownership_attested: bool = Form(False),
    user: User = Depends(require_user),
):
    """Start a faithful-cover run from an UPLOADED audio file. Writes a draft
    run and spawns the worker for the `analyzing` pre-stage (detect tempo +
    transcribe, then build a cover script that keeps the words). The melody is
    retained by Suno's upload-cover endpoint at generate time. No spend until
    the user approves. See the song-upload-cover design spec."""
    _require_terms_accepted(user)
    _require_email_confirmed(user)
    if user.role != "service" and not ownership_attested:
        raise HTTPException(400, detail={"code": "ownership_not_attested"})
    from pipeline.config import load_config
    from pipeline.db import get_balance

    ext = Path(file.filename or "").suffix.lower()
    ctype = (file.content_type or "").lower()
    if not (ctype.startswith("audio/") or ctype == "application/octet-stream"
            or ext in _AUDIO_EXTS):
        raise HTTPException(
            status_code=422,
            detail="Upload must be an audio file (mp3, m4a, wav, …).",
        )
    if ext not in _AUDIO_EXTS:
        ext = ".mp3"  # trust content-type; default extension for the saved file

    cfg = load_config(Path(os.environ.get(
        "FACELESS_CONFIG", str(REPO_ROOT / "config.yaml"))))
    # upload_cover_song has no quality_tier form field — premium best-of-N for
    # the cover path is out of scope (spec follow-ups); price standard.
    credits_required = _song_credit_amount(video_mode, "standard", cfg)
    if user.role != "service":
        balance = get_balance(user.id)
        if balance < credits_required:
            _raise_402_insufficient_credits(balance, credits_required)

    # Faithfulness knob (Kie audioWeight): 0-1 or absent.
    if audio_weight is not None and not (0.0 <= audio_weight <= 1.0):
        raise HTTPException(422, "audio_weight must be between 0 and 1")

    # Artist Core: validate before any work so an unknown id is a clean 404.
    if artist_id:
        from pipeline import artists as artists_mod
        if artists_mod.find_by_id(
                artists_mod.load_artists(_user_runs_root(user)), artist_id) is None:
            raise HTTPException(404, f"artist {artist_id!r} not found")

    user_root = _user_runs_root(user)
    user_root.mkdir(parents=True, exist_ok=True)
    run_id = _make_run_id(root=user_root)
    run_dir = user_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # Stream the upload to disk with a hard size cap (Cloud Run request limit).
    reference_filename = f"reference{ext}"
    dest = run_dir / reference_filename
    total = 0
    with dest.open("wb") as out:
        while chunk := file.file.read(1 << 20):
            total += len(chunk)
            if total > _UPLOAD_AUDIO_MAX_BYTES:
                out.close()
                try:
                    dest.unlink()
                except OSError:
                    pass
                raise HTTPException(
                    status_code=413,
                    detail="Audio too large (max ~30 MB). Compress or trim to ≤8 min.",
                )
            out.write(chunk)
    if total == 0:
        raise HTTPException(status_code=422, detail="Uploaded file was empty.")

    _write_state(
        run_dir,
        kind="song",
        mode="cover",
        status="analyzing",
        user_id=user.id,
        theme="(cover from uploaded audio…)",
        audio_weight=audio_weight,
        reference_filename=reference_filename,
        import_instruction=instruction,
        video_mode=video_mode,
        language=language,
        vocal_gender=vocal_gender,
        suno_model=(suno_model if suno_model in _ALLOWED_SUNO_MODELS else None),
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        # Tier-3 legal audit: persist the ownership attestation at create time.
        ownership_attested=ownership_attested,
        ownership_attested_version=(
            CURRENT_LEGAL_VERSION if ownership_attested else None),
        ownership_attested_at=(_now_iso() if ownership_attested else None),
    )
    args = ["--mode", "song", "--resume", str(run_dir)]
    pid = _SPAWN_FN(args, run_dir)
    _write_state(run_dir, pid=pid)
    return {"run_id": run_id, "status": "analyzing"}


def _song_credit_amount(video_mode: str, quality_tier: str, cfg) -> int:
    """Credit cost for one song render given video_mode + quality_tier.
    Single source of truth so the create/script/approve/reroll paths can't
    drift. Falls back to hard-coded defaults only when SongConfig is absent."""
    if cfg.song:
        base = (cfg.song.cinematic_credits_per_song
                if video_mode == "cinematic"
                else cfg.song.credits_per_song)
        surcharge = cfg.song.premium_credit_surcharge if quality_tier == "premium" else 0
        return base + surcharge
    base = 3 if video_mode == "cinematic" else 1
    return base + (4 if quality_tier == "premium" else 0)


def _reconcile_downgrade_refund(run_dir: Path, user: "User") -> None:
    """If a cinematic run downgraded to static, refund the credit
    surcharge exactly once. Idempotent via the surcharge_refunded flag."""
    import pipeline.credits as _credits
    from pipeline.config import load_config
    state = _read_state(run_dir)
    if not state.get("video_downgraded") or state.get("surcharge_refunded"):
        return
    cfg_path = Path(os.environ.get("FACELESS_CONFIG", str(REPO_ROOT / "config.yaml")))
    cfg = load_config(cfg_path)
    if cfg.song:
        surcharge = cfg.song.cinematic_credits_per_song - cfg.song.credits_per_song
    else:
        surcharge = 2
    if surcharge > 0:
        # Refund first, then flag. If refund raises, the flag stays unset and the
        # next GET retries (safe direction). Two simultaneous GETs could double-
        # refund — accepted for a solo-user app, same non-locking tradeoff as
        # credits.check_or_deduct.
        _credits.refund(user, amount=surcharge, run_id=run_dir.name,
                        reason="cinematic-downgrade-refund")
    _write_state(run_dir, surcharge_refunded=True)


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


def _enforce_daily_song_limit(user: "User") -> None:
    """Raise 429 if the user has approved >= _SONG_DAILY_LIMIT songs in the
    last 24 hours. DB-backed (rate_events) so the cap is correct across all
    Cloud Run instances, not per-instance like the old JSON file it replaced.
    Service tokens bypass."""
    if user.role == "service":
        return
    from pipeline.db import count_rate_events
    if count_rate_events(user.id, "song_approve", 86400) >= _SONG_DAILY_LIMIT:
        raise HTTPException(
            429,
            f"daily song limit reached ({_SONG_DAILY_LIMIT} per 24h); "
            f"try again later",
        )


# Per-user hourly throttle on the unmetered LLM draft/regen endpoints
# (create_song's writer pass, regenerate-lyrics, regenerate-cover-prompt).
# Those make Anthropic/Gemini calls with no credit cost, so an account with
# the free script-gen could spam them into unbounded LLM spend. Soft cap via
# the same rate_events primitive; service tokens bypass.
_LLM_HOURLY_LIMIT = int(os.environ.get("FACELESS_LLM_HOURLY_LIMIT", "30"))


def _enforce_llm_rate_limit(user: "User") -> None:
    """Raise 429 {'code': 'llm_rate_limited'} if the user has made
    >= _LLM_HOURLY_LIMIT LLM-text calls in the last hour; otherwise record
    this call. Service tokens bypass (no count, no record)."""
    if user.role == "service":
        return
    from pipeline.db import count_rate_events, record_rate_event
    if count_rate_events(user.id, "llm_call", 3600) >= _LLM_HOURLY_LIMIT:
        raise HTTPException(429, detail={"code": "llm_rate_limited"})
    record_rate_event(user.id, "llm_call")


@app.get("/songs/{run_id}", response_model=SongRunSummary)
def get_song(run_id: str, user: User = Depends(require_user)):
    run_dir = _resolve_song_dir(run_id, user)
    _reconcile_downgrade_refund(run_dir, user)
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
        watermarked=bool(state.get("watermarked", False)),
        video_mode=state.get("video_mode", "static"),
        artist_id=state.get("artist_id"),
        artist_name=_artist_name_for(user, state.get("artist_id")),
        released=bool(state.get("released", False)),
        youtube_url=state.get("youtube_url"),
        source=state.get("source"),
        trend_rationale=state.get("trend_rationale"),
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
    video_mode = script.get("video_mode", "static")
    quality_tier = script.get("quality_tier", "standard")
    credits = _song_credit_amount(video_mode, quality_tier, cfg)
    if cfg.song and video_mode == "cinematic":
        usd = cfg.song.suno_cost_usd + cfg.song.cinematic_pool_size * cfg.song.cover_cost_usd
    elif cfg.song:
        usd = cfg.song.suno_cost_usd + cfg.song.cover_cost_usd
    else:
        usd = 0.08
    # Premium-tier disclosure so the app shows the best-of-N + A&R + master
    # spend ceiling at the approve gate, before any Suno job is submitted.
    max_spend_note = None
    if quality_tier == "premium" and cfg.song:
        max_takes = cfg.song.max_takes
        # ceil(max_takes/2) jobs (Suno returns 2 takes/job) — match run.py's
        # math.ceil(want/2) so the disclosed ceiling isn't understated for an
        # odd max_takes.
        max_usd = ((max_takes + 1) // 2) * cfg.song.suno_cost_usd
        max_spend_note = (
            f"Premium quality: best-of-N + AI A&R + master — up to "
            f"{max_takes} takes, ~${max_usd:.2f}, "
            f"{_song_credit_amount(video_mode, 'premium', cfg)} credits"
        )
    return SongScriptResponse(
        title=script["title"],
        lyrics=script["lyrics"],
        style_prompt=script["style_prompt"],
        cover_prompt=script["cover_prompt"],
        language=script["language"],
        cost_credits=credits,
        cost_usd=usd,
        video_mode=video_mode,
        max_spend_note=max_spend_note,
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
    # One artists.json read for the whole list (not per song).
    from pipeline import artists as artists_mod
    artist_names = {
        a["id"]: a.get("name")
        for a in artists_mod.load_artists(user_root)
    }
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
            video_mode=state.get("video_mode", "static"),
            artist_id=state.get("artist_id"),
            artist_name=artist_names.get(state.get("artist_id")),
            released=bool(state.get("released", False)),
            youtube_url=state.get("youtube_url"),
            source=state.get("source"),
            trend_rationale=state.get("trend_rationale"),
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
    _enforce_llm_rate_limit(user)
    from pipeline.song_lyrics import generate_song_script
    run_dir = _resolve_song_dir(run_id, user)
    _require_song_awaiting_approval(run_dir)
    script_path = run_dir / "song.json"
    current = json.loads(script_path.read_text())
    # Re-screen the seed theme (user-supplied at create time) before feeding
    # it back into generation. The generated style_prompt is NOT re-screened
    # (inputs-only).
    _screen_content(_read_state(run_dir).get("theme", ""),
                    user=user, run_id=run_id)
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
    _enforce_llm_rate_limit(user)
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


# Arabic harakat + tatweel — stripped to compare letter skeletons, so the
# diacritize pass can be VERIFIED to have only added pronunciation marks.
_HARAKAT_RE = re.compile(r"[ً-ٰٟـ]")

_DIACRITIZE_SYSTEM = """You add FULL Arabic diacritics (تشكيل كامل) to song
lyrics so a singing model pronounces every word correctly.

RULES:
- Add fatha/damma/kasra/sukun/shadda/tanwin to EVERY Arabic word.
- Do NOT add, remove, reorder, translate, or change ANY word.
- Keep section tags ([Verse 1], [Chorus], ...) and line breaks EXACTLY as-is.
- Non-Arabic words pass through untouched.
- Output ONLY the diacritized lyrics — no commentary, no markdown."""


def _letter_skeleton(text: str) -> str:
    """Text minus harakat/tatweel with whitespace normalized — two lyrics
    with the same skeleton contain exactly the same words."""
    return " ".join(_HARAKAT_RE.sub("", text).split())


@app.post("/songs/{run_id}/diacritize")
def diacritize_song(run_id: str, user: User = Depends(require_user)):
    """One LLM pass adds full tashkeel to the CURRENT lyrics (custom lyrics,
    old drafts, post-edit text). Verified: the result's letter skeleton must
    equal the input's — the model can only have added pronunciation marks,
    never changed words — else 502 and nothing is written."""
    run_dir = _resolve_song_dir(run_id, user)
    _require_song_awaiting_approval(run_dir)
    script_path = run_dir / "song.json"
    current = json.loads(script_path.read_text())
    lyrics = str(current.get("lyrics") or "")
    if not lyrics.strip():
        raise HTTPException(409, "no lyrics to diacritize")

    from pipeline.song_lyrics import diacritize_lyrics
    result = diacritize_lyrics(_build_song_llm(), lyrics)
    if result is None:
        raise HTTPException(
            502, "diacritize failed or changed the words — refused (retry)")

    current["lyrics"] = result
    _atomic_write_json(script_path, current)
    (run_dir / "lyrics.txt").write_text(result, encoding="utf-8")
    return {"lyrics": result}


def _cancel_song_impl(user: "User", run_id: str) -> dict:
    from pipeline.credits import refund_run_charges

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

    # Re-read state: the worker may have raced us to "complete" between
    # our first read (and the SIGTERM above) and here — i.e. the song was
    # delivered. Never clobber a completed song to canceled, and never
    # refund a song that was actually delivered.
    state = _read_state(run_dir)
    if state.get("status") == "complete":
        raise HTTPException(409, "song already complete")

    _write_state(run_dir, status="canceled")

    # Refund any net credits charged for this song. Net-safe: a song
    # canceled before approval was never charged, so this is a 0 no-op.
    # Refund telemetry must never fail the cancel itself.
    refunded = 0
    try:
        refunded = refund_run_charges(
            user, run_id=run_id, reason="song canceled by user")
    except Exception as _e:
        # Refund failure is a billing anomaly — surface it (alert metric
        # matches "[billing]"). Must still NOT fail the cancel itself.
        get_logger().error("[billing] refund failed during cancel",
                            exc_info=_e, extra={"where": "cancel", "run_id": run_id})
    return {"ok": True, "refunded": refunded}


@app.post("/songs/{run_id}/cancel")
def cancel_song(run_id: str, user: User = Depends(require_user)):
    return _cancel_song_impl(user, run_id)


@app.post("/songs/{run_id}/approve")
def approve_song(run_id: str, user: User = Depends(require_user)):
    _require_terms_accepted(user)
    _require_email_confirmed(user)
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
    script = json.loads((run_dir / "song.json").read_text())
    video_mode = script.get("video_mode", "static")
    quality_tier = script.get("quality_tier", "standard")
    amount = _song_credit_amount(video_mode, quality_tier, cfg)

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
    # Record this approval in the DB-backed rate log AFTER the spawn
    # succeeds. If spawning fails, no credit gets spent in the wrong
    # state — we let the user retry without it counting against quota.
    # Service tokens bypass the cap, so there's nothing to record for them.
    if user.role != "service":
        from pipeline.db import record_rate_event
        record_rate_event(user.id, "song_approve")
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


@app.get("/songs/{run_id}/release-package")
def get_release_package(
    run_id: str,
    user: User = Depends(require_user_header_or_query),
):
    """Distribution (Route B): download a store-ready release zip — audio,
    3000x3000 cover, metadata (json+txt), lyrics, upload checklist. 409 with
    the missing-items list when the run isn't releasable yet. Query-token
    auth: this is a browser download link."""
    from pipeline import artists as artists_mod
    from pipeline.release import (ReleaseNotReady, build_release_package,
                                  song_slug)

    run_dir = _resolve_song_dir(run_id, user)
    state = _read_state(run_dir)
    if state.get("kind") != "song":
        raise HTTPException(404, "not a song run")
    if state.get("status") != "complete":
        raise HTTPException(
            status_code=409,
            detail={"detail": "song is not complete yet",
                    "missing": [f"status={state.get('status')}"]},
        )

    artist = None
    if state.get("artist_id"):
        artist = artists_mod.find_by_id(
            artists_mod.load_artists(_user_runs_root(user)),
            state["artist_id"])

    out_zip = run_dir / "release.zip"
    try:
        build_release_package(run_dir, artist, out_zip)
    except ReleaseNotReady as e:
        raise HTTPException(
            status_code=409,
            detail={"detail": "release package not ready", "missing": e.missing},
        )
    slug = song_slug(state.get("title") or "")
    prefix = (artist or {}).get("handle") or "faceless"
    return FileResponse(
        out_zip,
        media_type="application/zip",
        headers={"Content-Disposition":
                 f'attachment; filename="{prefix}-{slug}-release.zip"'},
    )


class MarkReleasedRequest(BaseModel):
    released: bool = True


@app.post("/songs/{run_id}/mark-released")
def mark_released(
    run_id: str,
    req: MarkReleasedRequest,
    user: User = Depends(require_user),
):
    """User-confirmed 'this song is live on stores' toggle (after the manual
    distributor upload). Feeds the discography badge + future royalty UI."""
    run_dir = _resolve_song_dir(run_id, user)
    state = _read_state(run_dir)
    if state.get("kind") != "song":
        raise HTTPException(404, "not a song run")
    _write_state(run_dir, released=req.released)
    return {"run_id": run_id, "released": req.released}


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


# Cloud Run caps a single buffered HTTP response at ~32 MiB. A song's
# final.mp4 can exceed that (cinematic videos run ~38 MB), so FileResponse —
# which sets Content-Length for the whole file — makes Cloud Run 500 on the
# full-file GET the browser issues (Range: bytes=0-). The streamer below keeps
# every Range response well under the cap; the <video> element fetches the
# rest via follow-up ranges. A no-Range request (e.g. ?download=1) streams the
# whole file with chunked transfer (no Content-Length), which is not subject
# to the buffered-response limit.
_VIDEO_RANGE_CAP = 8 * 1024 * 1024  # max bytes per Range response (< 32 MiB)


def _serve_video(
    path: Path,
    request: Request,
    *,
    download_name: str | None = None,
    extra_headers: dict | None = None,
):
    file_size = path.stat().st_size
    range_header = request.headers.get("range")
    base = dict(extra_headers or {})

    if not range_header:
        # No Range (direct hit / download): stream the whole file chunked.
        def _iter_all():
            with open(path, "rb") as f:
                while True:
                    data = f.read(1024 * 1024)
                    if not data:
                        break
                    yield data
        headers = {**base, "Accept-Ranges": "bytes"}
        if download_name:
            headers["Content-Disposition"] = f'attachment; filename="{download_name}"'
        return StreamingResponse(_iter_all(), media_type="video/mp4", headers=headers)

    m = re.match(r"bytes=(\d+)-(\d*)", range_header.strip())
    start = int(m.group(1)) if m else 0
    end = int(m.group(2)) if (m and m.group(2)) else file_size - 1
    end = min(end, file_size - 1, start + _VIDEO_RANGE_CAP - 1)
    if start >= file_size or start > end:
        return Response(
            status_code=416, headers={"Content-Range": f"bytes */{file_size}"})
    length = end - start + 1

    def _iter_range():
        with open(path, "rb") as f:
            f.seek(start)
            remaining = length
            while remaining > 0:
                data = f.read(min(1024 * 1024, remaining))
                if not data:
                    break
                remaining -= len(data)
                yield data

    headers = {
        **base,
        "Accept-Ranges": "bytes",
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Content-Length": str(length),
    }
    if download_name:
        headers["Content-Disposition"] = f'attachment; filename="{download_name}"'
    return StreamingResponse(
        _iter_range(), status_code=206, media_type="video/mp4", headers=headers)


@app.get("/songs/{run_id}/video")
def get_song_video(
    run_id: str,
    request: Request,
    download: bool = False,
    user: User = Depends(require_user_header_or_query),
):
    """Stream the final.mp4 with HTTP Range support. With `?download=1` the
    server sets Content-Disposition: attachment so the browser saves the file
    instead of playing it inline."""
    run_dir = _resolve_song_dir(run_id, user)
    path = run_dir / "final.mp4"
    if not path.exists():
        raise HTTPException(404, "final.mp4 not yet assembled")
    # run_id is an ASCII timestamp; the Arabic title would need RFC 5987.
    name = f"faceless-song-{run_id}.mp4" if download else None
    return _serve_video(path, request, download_name=name)


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
    _require_terms_accepted(user)
    _require_email_confirmed(user)
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
    script = json.loads((run_dir / "song.json").read_text())
    video_mode = script.get("video_mode", "static")
    quality_tier = script.get("quality_tier", "standard")
    amount = _song_credit_amount(video_mode, quality_tier, cfg)

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
    # Count this cover regen toward the DB-backed daily cap (parity with the
    # old file-based _record_song_approval). Service tokens bypass the cap.
    if user.role != "service":
        from pipeline.db import record_rate_event
        record_rate_event(user.id, "song_approve")
    _write_state(run_dir, pid=pid)
    return {"ok": True, "balance_after": new_balance}


def _delete_song_impl(user: "User", run_id: str) -> None:
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
    # Snapshot the share token (if any) before nuking the run dir, then
    # remove the matching entry from the share index so old share links
    # surface the friendly "removed" page immediately rather than racing
    # with the file-existence check.
    share_token = state.get("share_token")
    try:
        shutil.rmtree(run_dir)
    except OSError as e:
        raise HTTPException(500, f"failed to remove run dir: {e}")
    if share_token:
        try:
            idx = _load_share_index()
            if idx.pop(share_token, None) is not None:
                _save_share_index(idx)
        except Exception:
            # Share-index hygiene is best-effort — the orphan token is
            # harmless (resolves to 404 anyway). Never block the
            # primary delete on this.
            pass
    return None


@app.delete("/songs/{run_id}", status_code=204)
def delete_song(run_id: str, user: User = Depends(require_user)):
    """Delete a song run entirely — removes the run dir and all
    artifacts (song.json, lyrics.txt, cover.png, take_*.mp3, song.mp3,
    final.mp4, api_state.json, etc.).

    Refuses with 409 if a worker is actively processing the run. The
    user must wait for it to complete (or fail), then delete.
    """
    return _delete_song_impl(user, run_id)


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
# Artists — the identity wrapper around a persona voice (Artist Core).
#
# An Artist = name + handle + pinned voice (persona_id) + visuals + default
# song settings. Songs made "as" an artist carry artist_id in state and form
# the artist's discography. Storage: pipeline/artists.py (artists.json per
# user). Spec: docs/superpowers/specs/2026-07-15-artist-core-design.md.
# ---------------------------------------------------------------------------


def _artist_name_for(user: "User", artist_id: str | None) -> str | None:
    """Denormalized artist name for a single-song summary. None-safe."""
    if not artist_id:
        return None
    from pipeline import artists as artists_mod
    a = artists_mod.find_by_id(
        artists_mod.load_artists(_user_runs_root(user)), artist_id)
    return a.get("name") if a else None


def _artist_song_count(user: "User", artist_id: str) -> int:
    root = _user_runs_root(user)
    if not root.exists():
        return 0
    n = 0
    for d in root.iterdir():
        if d.is_dir():
            st = _read_state(d)
            if st.get("kind") == "song" and st.get("artist_id") == artist_id:
                n += 1
    return n


def _artist_summary(user: "User", artist: dict) -> ArtistSummary:
    return ArtistSummary(**artist,
                         song_count=_artist_song_count(user, artist["id"]))


def _resolve_new_handle(
    user: "User", *, name: str, requested: str | None,
    artists: list[dict], exclude_id: str | None = None,
) -> str:
    """Validate/derive a handle. Explicit duplicates → 409 with a
    suggestion; auto-slugged ones silently get a -2 suffix."""
    from pipeline.artists import (
        ARTIST_HANDLE_RE, slugify_handle, unique_handle)
    taken = {a["handle"] for a in artists if a.get("id") != exclude_id}
    if requested:
        handle = requested.strip().lower()
        if not ARTIST_HANDLE_RE.match(handle):
            raise HTTPException(
                422, "handle must be 2-32 chars of a-z, 0-9, '-'")
        if handle in taken:
            raise HTTPException(
                status_code=409,
                detail={
                    "detail": f"handle {handle!r} is taken",
                    "suggested_handle": unique_handle(handle, taken),
                },
            )
        return handle
    # Auto-derive from the name; collisions auto-suffix (no 409 — the user
    # never typed this handle).
    seed = slugify_handle(name, uuid.uuid4().hex[:8])
    return unique_handle(seed, taken)


@app.get("/artists", response_model=list[ArtistSummary])
def list_artists(user: User = Depends(require_user)):
    from pipeline import artists as artists_mod
    return [_artist_summary(user, a)
            for a in artists_mod.load_artists(_user_runs_root(user))]


@app.post("/artists", response_model=ArtistSummary, status_code=201)
def create_artist(req: CreateArtistRequest, user: User = Depends(require_user)):
    from pipeline import artists as artists_mod
    name = req.name.strip()
    if not name:
        raise HTTPException(422, "artist name is required")
    if len(name) > 80:
        raise HTTPException(422, "artist name exceeds 80 chars")
    root = _user_runs_root(user)
    artists = artists_mod.load_artists(root)
    handle = _resolve_new_handle(
        user, name=name, requested=req.handle, artists=artists)
    artist = artists_mod.new_artist(
        name=name,
        handle=handle,
        bio=req.bio.strip(),
        default_style=req.default_style.strip(),
        default_language=req.default_language,
        default_vocal_gender=req.default_vocal_gender,
    )
    artists.append(artist)
    artists_mod.save_artists(root, artists)
    return _artist_summary(user, artist)


@app.patch("/artists/{artist_id}", response_model=ArtistSummary)
def patch_artist(
    artist_id: str,
    req: PatchArtistRequest,
    user: User = Depends(require_user),
):
    from pipeline import artists as artists_mod
    root = _user_runs_root(user)
    artists = artists_mod.load_artists(root)
    artist = artists_mod.find_by_id(artists, artist_id)
    if artist is None:
        raise HTTPException(404, "artist not found")
    if req.name is not None:
        if not req.name.strip():
            raise HTTPException(422, "artist name is required")
        artist["name"] = req.name.strip()
    if req.handle is not None:
        artist["handle"] = _resolve_new_handle(
            user, name=artist["name"], requested=req.handle,
            artists=artists, exclude_id=artist_id)
    for field in ("bio", "persona_id", "avatar_run_id", "default_style",
                  "default_language", "default_vocal_gender",
                  "auto_publish_youtube", "morning_drafts",
                  "default_dialect"):
        val = getattr(req, field)
        if val is not None:
            artist[field] = val
    artists_mod.save_artists(root, artists)
    return _artist_summary(user, artist)


@app.delete("/artists/{artist_id}", status_code=204)
def delete_artist(artist_id: str, user: User = Depends(require_user)):
    """Remove the artist. Their songs stay (detached: artist_id cleared);
    the persona voice is kept — it may be pinned by other artists later."""
    from pipeline import artists as artists_mod
    root = _user_runs_root(user)
    artists = artists_mod.load_artists(root)
    remaining = [a for a in artists if a.get("id") != artist_id]
    if len(remaining) == len(artists):
        raise HTTPException(404, "artist not found")
    artists_mod.save_artists(root, remaining)
    # Detach songs.
    if root.exists():
        for d in root.iterdir():
            if d.is_dir():
                st = _read_state(d)
                if st.get("kind") == "song" and st.get("artist_id") == artist_id:
                    _write_state(d, artist_id=None)
    return None


@app.post("/artists/from-song", response_model=ArtistSummary, status_code=201)
def create_artist_from_song(
    req: CreateArtistFromSongRequest,
    user: User = Depends(require_user),
):
    """One-step door: save the song take's voice as a persona AND create the
    artist wrapping it — avatar from the song's cover, default style from the
    song's style_prompt. The source song is assigned to the new artist."""
    from pipeline import artists as artists_mod

    # 1) Voice: reuse the existing persona flow (validations included).
    persona = save_persona_from_song(
        req.run_id,
        CreatePersonaRequest(name=req.name, description="", take=req.take),
        user,
    )

    # 2) Identity: defaults harvested from the source song.
    run_dir = _resolve_song_dir(req.run_id, user)
    song_json = {}
    sj = run_dir / "song.json"
    if sj.exists():
        try:
            song_json = json.loads(sj.read_text())
        except (OSError, json.JSONDecodeError):
            song_json = {}
    root = _user_runs_root(user)
    artists = artists_mod.load_artists(root)
    handle = _resolve_new_handle(
        user, name=req.name.strip(), requested=req.handle, artists=artists)
    artist = artists_mod.new_artist(
        name=req.name.strip(),
        handle=handle,
        persona_id=persona.id,
        avatar_run_id=req.run_id,
        default_style=str(song_json.get("style_prompt") or ""),
        default_language=str(song_json.get("language") or "ar"),
        default_vocal_gender=str(song_json.get("vocal_gender") or "m"),
    )
    artists.append(artist)
    artists_mod.save_artists(root, artists)
    # 3) The source song joins the discography.
    _write_state(run_dir, artist_id=artist["id"])
    return _artist_summary(user, artist)


_AVATAR_MAX_BYTES = 10 * 1024 * 1024
_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp")


@app.post("/artists/{artist_id}/avatar", response_model=ArtistSummary)
def upload_artist_avatar(
    artist_id: str,
    file: UploadFile = File(...),
    user: User = Depends(require_user),
):
    from pipeline import artists as artists_mod
    root = _user_runs_root(user)
    artists = artists_mod.load_artists(root)
    artist = artists_mod.find_by_id(artists, artist_id)
    if artist is None:
        raise HTTPException(404, "artist not found")
    ext = Path(file.filename or "").suffix.lower()
    ctype = (file.content_type or "").lower()
    if not (ctype.startswith("image/") or ext in _IMAGE_EXTS):
        raise HTTPException(422, "avatar must be an image (png, jpg, webp)")
    if ext not in _IMAGE_EXTS:
        ext = ".png"
    fname = f"avatar_{artist_id}{ext}"
    dest = root / fname
    total = 0
    root.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as out:
        while chunk := file.file.read(1 << 20):
            total += len(chunk)
            if total > _AVATAR_MAX_BYTES:
                out.close()
                try:
                    dest.unlink()
                except OSError:
                    pass
                raise HTTPException(413, "avatar too large (max 10 MB)")
            out.write(chunk)
    if total == 0:
        raise HTTPException(422, "uploaded file was empty")
    artist["avatar_upload"] = fname
    artists_mod.save_artists(root, artists)
    return _artist_summary(user, artist)


@app.get("/artists/{artist_id}/avatar")
def get_artist_avatar(
    artist_id: str,
    user: User = Depends(require_user_header_or_query),
):
    """Uploaded avatar, else the avatar run's cover.png, else 404 (the client
    falls back to a generated gradient). Query-token auth so <img> widgets
    (which can't set headers on web) can load it."""
    from pipeline import artists as artists_mod
    root = _user_runs_root(user)
    artist = artists_mod.find_by_id(artists_mod.load_artists(root), artist_id)
    if artist is None:
        raise HTTPException(404, "artist not found")
    if artist.get("avatar_upload"):
        p = root / artist["avatar_upload"]
        if p.exists():
            return FileResponse(p)
    if artist.get("avatar_run_id"):
        p = root / artist["avatar_run_id"] / "cover.png"
        if p.exists():
            return FileResponse(p)
    raise HTTPException(404, "no avatar")


# ---------------------------------------------------------------------------
# YouTube auto-publish — OAuth connect + one-tap upload (Channel Autopilot).
# Spec: docs/superpowers/specs/2026-07-16-youtube-auto-publish-design.md.
# Pre-audit, Google forces API uploads to private (YOUTUBE_PRIVACY_STATUS
# flips to "public" once the user's compliance audit passes).
# ---------------------------------------------------------------------------

_YT_STATE_TTL_S = 900  # signed OAuth state expires after 15 min


def _yt_oauth_config() -> tuple[str, str, str]:
    """(client_id, client_secret, redirect_uri) or 503 when unconfigured —
    the feature stays dark until the operator creates the OAuth client."""
    cid = os.environ.get("YT_OAUTH_CLIENT_ID", "")
    secret = os.environ.get("YT_OAUTH_CLIENT_SECRET", "")
    if not cid or not secret:
        raise HTTPException(503, "YouTube publishing is not configured "
                                 "(YT_OAUTH_CLIENT_ID/SECRET unset)")
    base = os.environ.get(
        "FACELESS_PUBLIC_URL",
        "https://faceless-api-uplzdtffeq-uc.a.run.app").rstrip("/")
    redirect = os.environ.get("YT_OAUTH_REDIRECT",
                              f"{base}/auth/youtube/callback")
    return cid, secret, redirect


def _yt_sign_state(user_id: str) -> str:
    import hashlib
    import hmac as _hmac
    import time as _time
    key = os.environ.get("FACELESS_API_TOKEN", "").encode()
    ts = str(int(_time.time()))
    sig = _hmac.new(key, f"{user_id}.{ts}".encode(), hashlib.sha256).hexdigest()
    return f"{user_id}.{ts}.{sig}"


def _yt_verify_state(state: str) -> str:
    """Returns the user_id or raises 403 (tampered/expired)."""
    import hashlib
    import hmac as _hmac
    import time as _time
    try:
        user_id, ts, sig = state.rsplit(".", 2)
    except ValueError:
        raise HTTPException(403, "bad state")
    key = os.environ.get("FACELESS_API_TOKEN", "").encode()
    expect = _hmac.new(key, f"{user_id}.{ts}".encode(), hashlib.sha256).hexdigest()
    if not _hmac.compare_digest(sig, expect):
        raise HTTPException(403, "bad state signature")
    if int(_time.time()) - int(ts) > _YT_STATE_TTL_S:
        raise HTTPException(403, "state expired — restart the connect flow")
    return user_id


def _user_root_for_id(user_id: str) -> Path:
    return _out_root() / user_id


@app.get("/auth/youtube/start")
def youtube_auth_start(user: User = Depends(require_user)):
    from pipeline import youtube as yt
    cid, _, redirect = _yt_oauth_config()
    return {"url": yt.auth_url(cid, redirect, _yt_sign_state(user.id))}


@app.get("/auth/youtube/callback", include_in_schema=False)
def youtube_auth_callback(code: str = "", state: str = "", error: str = ""):
    """PUBLIC — Google redirects the browser here. The signed state carries
    the user identity; verify it, exchange the code, store the token."""
    from fastapi.responses import HTMLResponse
    from pipeline import youtube as yt

    if error or not code:
        return HTMLResponse(
            f"<html><body style='font-family:sans-serif'>"
            f"<h3>YouTube connection cancelled</h3><p>{error or 'no code'}"
            f"</p></body></html>", status_code=400)
    user_id = _yt_verify_state(state)
    cid, secret, redirect = _yt_oauth_config()
    tokens = yt.exchange_code(cid, secret, code, redirect)
    refresh = tokens.get("refresh_token")
    if not refresh:
        raise HTTPException(502, "Google returned no refresh_token — remove "
                                 "the app at myaccount.google.com/permissions "
                                 "and reconnect")
    try:
        title = yt.channel_title(str(tokens.get("access_token") or ""))
    except Exception:
        title = "YouTube channel"
    yt.save_token(_user_root_for_id(user_id), {
        "refresh_token": refresh,
        "channel_title": title,
        "connected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })
    return HTMLResponse(
        "<html><body style='font-family:sans-serif;background:#F2EFF7;"
        "display:grid;place-items:center;height:100vh'><div>"
        f"<h2>✅ Connected: {title}</h2>"
        "<p>Return to the Faceless Lab app.</p></div></body></html>")


@app.get("/auth/youtube/status")
def youtube_auth_status(user: User = Depends(require_user)):
    from pipeline import youtube as yt
    tok = yt.load_token(_user_runs_root(user))
    return {"connected": tok is not None,
            "channel_title": (tok or {}).get("channel_title")}


@app.delete("/auth/youtube", status_code=204)
def youtube_disconnect(user: User = Depends(require_user)):
    from pipeline import youtube as yt
    yt.delete_token(_user_runs_root(user))
    return None


def _publish_song_to_youtube(run_dir: Path, user_root: Path,
                             artist: dict | None) -> tuple[str, str]:
    """Shared by the endpoint and the worker auto-publish hook.
    Returns (video_id, video_url); raises YouTubeError / RuntimeError."""
    from pipeline import youtube as yt

    tok = yt.load_token(user_root)
    if tok is None:
        raise RuntimeError("youtube not connected")
    cid, secret, _ = _yt_oauth_config()
    try:
        access = yt.refresh_access_token(cid, secret, tok["refresh_token"])
    except yt.YouTubeError:
        # Revoked on Google's side → drop the stale token so /status
        # reports disconnected instead of failing forever.
        yt.delete_token(user_root)
        raise
    song_json = json.loads((run_dir / "song.json").read_text(encoding="utf-8"))
    base = os.environ.get(
        "FACELESS_PUBLIC_URL",
        "https://faceless-api-uplzdtffeq-uc.a.run.app").rstrip("/")
    meta = yt.build_metadata(song_json, artist, base)
    privacy = os.environ.get("YOUTUBE_PRIVACY_STATUS", "private")
    video_id = yt.upload_video(
        access, run_dir / "final.mp4",
        title=meta["title"], description=meta["description"],
        tags=meta["tags"], privacy=privacy)
    return video_id, f"https://youtu.be/{video_id}"


@app.post("/songs/{run_id}/publish-youtube")
def publish_song_youtube(run_id: str, user: User = Depends(require_user)):
    from pipeline import artists as artists_mod
    from pipeline import youtube as yt

    run_dir = _resolve_song_dir(run_id, user)
    state = _read_state(run_dir)
    if state.get("kind") != "song":
        raise HTTPException(404, "not a song run")
    if state.get("youtube_url"):
        raise HTTPException(
            status_code=409,
            detail={"detail": "already published",
                    "video_url": state["youtube_url"]})
    if state.get("status") != "complete" or not (run_dir / "final.mp4").exists():
        raise HTTPException(409, "song has no finished video yet")
    if yt.load_token(_user_runs_root(user)) is None:
        raise HTTPException(409, "youtube not connected")

    artist = None
    if state.get("artist_id"):
        artist = artists_mod.find_by_id(
            artists_mod.load_artists(_user_runs_root(user)),
            state["artist_id"])
    try:
        video_id, url = _publish_song_to_youtube(
            run_dir, _user_runs_root(user), artist)
    except yt.YouTubeError as e:
        raise HTTPException(502, f"YouTube upload failed: {e}")
    _write_state(run_dir, youtube_video_id=video_id, youtube_url=url,
                 youtube_publish_error=None)
    return {"video_id": video_id, "video_url": url}


def _find_artist_public(handle: str) -> tuple[dict, Path] | None:
    """Locate an artist by handle across all user roots (public page has no
    auth context). Solo-scale linear scan — one artists.json read per user."""
    from pipeline import artists as artists_mod
    root = _out_root()
    if not root.exists():
        return None
    for user_dir in root.iterdir():
        if not user_dir.is_dir():
            continue
        artist = artists_mod.find_by_handle(
            artists_mod.load_artists(user_dir), handle)
        if artist:
            return artist, user_dir
    return None


@app.get("/admin", include_in_schema=False)
def admin_dashboard():
    """Self-contained super-admin operator console. The shell needs no auth
    (the service token is entered in-browser and attached to every /admin/*
    fetch as a bearer header); the endpoints it drives are service-gated."""
    from fastapi.responses import HTMLResponse
    from pipeline.admin_page import ADMIN_HTML
    return HTMLResponse(ADMIN_HTML)


@app.get("/a/{handle}", include_in_schema=False)
def public_artist_page(handle: str):
    """PUBLIC artist page (no auth): header + the artist's SHARED songs only
    (a song is public iff it has a share_token). Links go to the existing
    /p/{token} pages, so playback/OG reuse that machinery."""
    from fastapi.responses import HTMLResponse
    import html as _html

    found = _find_artist_public(handle)
    if found is None:
        return HTMLResponse(
            "<html><body style='font-family:sans-serif;background:#F2EFF7;"
            "color:#1B1E28;display:grid;place-items:center;height:100vh'>"
            "<div><h2>Artist not found</h2></div></body></html>",
            status_code=404)
    artist, user_dir = found

    songs = []
    for d in sorted(user_dir.iterdir(), key=lambda p: p.name, reverse=True):
        if not d.is_dir():
            continue
        st = _read_state(d)
        if (st.get("kind") == "song"
                and st.get("artist_id") == artist["id"]
                and st.get("share_token")):
            songs.append({
                "title": st.get("title") or "AI song",
                "token": st.get("share_token"),
            })

    name = _html.escape(artist.get("name", ""))
    bio = _html.escape(artist.get("bio", ""))
    initial = (artist.get("name") or "?")[:1]
    cards = "".join(
        f"<a class='song' href='/p/{s['token']}'>"
        f"<div class='art'>♪</div>"
        f"<div class='t'>{_html.escape(s['title'])}</div>"
        f"<div class='play'>▶</div></a>"
        for s in songs
    ) or "<p class='empty'>No public songs yet.</p>"

    return HTMLResponse(f"""<!doctype html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{name} — Faceless Lab</title>
<meta property="og:title" content="{name}">
<meta property="og:description" content="{bio or 'AI artist on Faceless Lab'}">
<style>
 body{{margin:0;font-family:Inter,system-ui,sans-serif;color:#1B1E28;
   background:linear-gradient(135deg,#FBF6EE,#F2EFF7 50%,#E9EBF2);min-height:100vh}}
 .wrap{{max-width:680px;margin:0 auto;padding:48px 20px}}
 .head{{display:flex;gap:20px;align-items:center;margin-bottom:8px}}
 .avatar{{width:96px;height:96px;border-radius:50%;display:grid;place-items:center;
   font-size:40px;font-weight:700;color:#fff;
   background:linear-gradient(135deg,#34A473,#38BFA6);flex:none}}
 h1{{margin:0;font-size:32px;letter-spacing:-.02em}}
 .bio{{color:#767C8C;margin:4px 0 0}}
 .count{{color:#A2A7B4;font-size:13px;margin:24px 0 12px}}
 .song{{display:flex;align-items:center;gap:14px;background:#fff;
   border:1px solid rgba(20,22,45,.07);border-radius:16px;padding:12px 16px;
   margin-bottom:10px;text-decoration:none;color:#1B1E28;
   box-shadow:0 12px 34px rgba(30,32,70,.08)}}
 .art{{width:44px;height:44px;border-radius:10px;display:grid;place-items:center;
   background:linear-gradient(135deg,#E7E1F4,#DCEBE6);flex:none}}
 .t{{flex:1;font-weight:600}}
 .play{{width:36px;height:36px;border-radius:50%;background:#232636;color:#fff;
   display:grid;place-items:center;font-size:13px}}
 .empty{{color:#767C8C}}
 .foot{{margin-top:36px;color:#A2A7B4;font-size:13px;text-align:center}}
 .foot a{{color:#2FA36B;text-decoration:none;font-weight:600}}
</style></head><body><div class="wrap">
 <div class="head">
   <div class="avatar">{_html.escape(initial)}</div>
   <div><h1>{name}</h1>{f"<p class='bio'>{bio}</p>" if bio else ""}</div>
 </div>
 <div class="count">{len(songs)} public song(s)</div>
 {cards}
 <div class="foot">Made with <a href="/app/">Faceless Lab</a> — create your own AI artist</div>
</div></body></html>""")


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
    script_path = run_dir / "song.json"
    # IMPORTANT: do NOT auto-evict the token if the run dir or song.json
    # look missing. GCS Fuse returns spurious False from exists() during
    # cold-starts and listing-eventual-consistency windows; a previous
    # version of this code self-corrupted the share index that way,
    # turning every fresh share into a 404 within minutes of being minted.
    # The /songs/{id} DELETE handler is now the only thing that removes
    # tokens from the index. Stale entries that genuinely point at a
    # deleted run will just keep 404'ing — harmless.
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


@app.post(
    "/songs/{run_id}/re-assemble",
    response_model=ReAssembleAck,
)
def re_assemble_song_user(
    run_id: str,
    user: User = Depends(require_user),
):
    """User-facing watermark backfill. Re-runs the ffmpeg assembler so
    the song's final.mp4 picks up the brand-mark PNG overlay + MP4
    container metadata that newer assemblies include automatically.
    Returns 409 if the song is already watermarked, 409 if status
    isn't complete, or 200 with the timing/title on success.

    Synchronous and blocking — assembly takes 3–6 minutes per song.
    The Cloud Run service timeout was bumped to 1800s alongside this
    feature so the request has runway; the Flutter caller should
    surface a banner during the wait. Owning the run is verified by
    _resolve_song_dir (raises 404 for someone else's run)."""
    from pipeline import song_assemble
    run_dir = _resolve_song_dir(run_id, user)
    state = _read_state(run_dir)
    if state.get("kind") != "song":
        raise HTTPException(404, "not a song run")
    if state.get("status") != "complete":
        raise HTTPException(
            409, f"status is {state.get('status')!r}, not complete",
        )
    if state.get("watermarked"):
        raise HTTPException(409, "song is already watermarked")
    cover_path = run_dir / "cover.png"
    song_mp3 = run_dir / "song.mp3"
    out_mp4 = run_dir / "final.mp4"
    lyrics_json = run_dir / "lyrics.json"
    song_json = run_dir / "song.json"
    missing = [
        p.name for p in (cover_path, song_mp3, song_json) if not p.exists()
    ]
    if missing:
        raise HTTPException(
            409, f"missing inputs: {', '.join(missing)}",
        )
    try:
        script = json.loads(song_json.read_text(encoding="utf-8"))
        title = script.get("title")
        share_token = state.get("share_token")
        t0 = time.time()
        song_assemble.assemble_song_video(
            cover_path=cover_path,
            song_mp3=song_mp3,
            out_mp4=out_mp4,
            lyrics_json=lyrics_json if lyrics_json.exists() else None,
            title=title,
            share_token=share_token,
        )
        dur = time.time() - t0
        try:
            _write_state(run_dir, watermarked=True)
        except Exception:
            pass
    except Exception as e:
        raise HTTPException(500, f"assembly failed: {type(e).__name__}: {e}")
    return ReAssembleAck(
        ok=True,
        user_id=user.id,
        run_id=run_id,
        title=title,
        watermark=True,
        share_token=share_token,
        duration_s=round(dur, 1),
    )


# ---------------------------------------------------------------------------
# Public-share social — view counts + likes for shared songs.
#
# Anonymous: no auth required, no account needed. We use a client-generated
# UUID (stored in the visitor's localStorage) as the "who liked this" key.
# This is best-effort: a determined visitor can clear localStorage to like
# again. That's fine — the goal is "thumb-stopping engagement signal,"
# not a tamper-resistant voting system.
#
# Storage: <run_dir>/social.json with shape
#     {"views": 12, "likes": 3, "liked_client_ids": ["abc...", "def..."]}
# Atomic writes via .tmp+rename (same pattern as the share index).
# ---------------------------------------------------------------------------

_VIEW_DEDUPE_WINDOW_S = 6 * 3600  # one view per (client, song) per 6 hours


def _social_path(run_dir: Path) -> Path:
    return run_dir / "social.json"


def _load_social(run_dir: Path) -> dict:
    p = _social_path(run_dir)
    if not p.exists():
        return {"views": 0, "likes": 0, "liked_client_ids": [], "views_seen": {}}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"views": 0, "likes": 0, "liked_client_ids": [], "views_seen": {}}
    # Backfill new fields on older files so we don't crash on read.
    data.setdefault("views", 0)
    data.setdefault("likes", 0)
    data.setdefault("liked_client_ids", [])
    data.setdefault("views_seen", {})
    return data


def _save_social(run_dir: Path, data: dict) -> None:
    p = _social_path(run_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)


class _LikePayload(BaseModel):
    client_id: str


class _ViewPayload(BaseModel):
    client_id: str


@app.post("/p/{token}/like", include_in_schema=False)
def like_shared_song(token: str, payload: _LikePayload):
    """Toggle a like. Anonymous — keyed by the visitor's localStorage
    client_id. Returns {"likes": int, "liked": bool} where `liked`
    reflects the visitor's new state after the toggle."""
    try:
        run_dir, _ = _resolve_shared_song(token)
    except HTTPException as e:
        if e.status_code == 404:
            raise HTTPException(404, "song unavailable")
        raise
    cid = (payload.client_id or "").strip()
    if len(cid) < 8 or len(cid) > 128:
        raise HTTPException(400, "invalid client_id")
    social = _load_social(run_dir)
    if cid in social["liked_client_ids"]:
        social["liked_client_ids"].remove(cid)
        social["likes"] = max(0, int(social["likes"]) - 1)
        liked = False
    else:
        social["liked_client_ids"].append(cid)
        social["likes"] = int(social["likes"]) + 1
        liked = True
    _save_social(run_dir, social)
    return {"likes": social["likes"], "liked": liked}


@app.post("/p/{token}/view", include_in_schema=False)
def view_shared_song(token: str, payload: _ViewPayload):
    """Record a view. Deduped per (client_id, song) inside
    _VIEW_DEDUPE_WINDOW_S so refreshes don't inflate counts."""
    try:
        run_dir, _ = _resolve_shared_song(token)
    except HTTPException as e:
        if e.status_code == 404:
            raise HTTPException(404, "song unavailable")
        raise
    cid = (payload.client_id or "").strip()
    if len(cid) < 8 or len(cid) > 128:
        raise HTTPException(400, "invalid client_id")
    social = _load_social(run_dir)
    now = int(time.time())
    last = int(social["views_seen"].get(cid, 0))
    if now - last >= _VIEW_DEDUPE_WINDOW_S:
        social["views"] = int(social["views"]) + 1
        social["views_seen"][cid] = now
        # Bound the views_seen map so it doesn't grow unbounded. Prune
        # entries older than the window — they'd dedupe nothing anyway.
        cutoff = now - _VIEW_DEDUPE_WINDOW_S
        social["views_seen"] = {
            k: v for k, v in social["views_seen"].items() if int(v) >= cutoff
        }
        _save_social(run_dir, social)
    return {"views": social["views"]}


@app.get("/p/{token}/stats", include_in_schema=False)
def get_shared_song_stats(token: str, client_id: str | None = None):
    """Fetch current stats. Used by the share page JS to refresh
    counts after a like toggle (so the UI matches the server state)."""
    try:
        run_dir, _ = _resolve_shared_song(token)
    except HTTPException as e:
        if e.status_code == 404:
            raise HTTPException(404, "song unavailable")
        raise
    social = _load_social(run_dir)
    liked = bool(client_id and client_id in social["liked_client_ids"])
    return {
        "views": int(social["views"]),
        "likes": int(social["likes"]),
        "liked": liked,
    }


def _render_removed_share_page() -> "HTMLResponse":
    """Friendly HTML 404 served when a share token is missing, corrupted,
    or its run was deleted. Used only on the HTML /p/{token} route — the
    /video and /cover sub-paths keep returning JSON 404 because browsers
    don't render HTML for video/img sources."""
    from fastapi.responses import HTMLResponse
    cta_url = os.environ.get("FACELESS_BRAND_URL", "https://faceless-lab.com")
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Song removed · Faceless Lab</title>
<meta name="robots" content="noindex">
<style>
  :root {{ --bg-0:#06080d; --fg-0:#f3f5fb; --fg-1:#c5cad9; --fg-2:#7f869c;
    --accent:#d7b46a; --accent-soft:rgba(215,180,106,0.16); }}
  * {{ box-sizing: border-box; }}
  html, body {{
    margin: 0; padding: 0;
    background: radial-gradient(120% 80% at 50% 0%, #131a2a 0%, var(--bg-0) 55%) fixed;
    color: var(--fg-0);
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
    min-height: 100vh; min-height: 100dvh;
    -webkit-font-smoothing: antialiased;
  }}
  .wrap {{
    max-width: 520px; margin: 0 auto;
    padding: 80px 24px 60px;
    text-align: center;
  }}
  .icon {{
    width: 64px; height: 64px;
    margin: 0 auto 28px;
    border-radius: 50%;
    background: var(--accent-soft);
    color: var(--accent);
    display: flex; align-items: center; justify-content: center;
    font-size: 28px;
  }}
  h1 {{
    font-size: 26px; font-weight: 700; letter-spacing: -0.01em;
    margin: 0 0 12px;
  }}
  p {{
    font-size: 15px; line-height: 1.55;
    color: var(--fg-1);
    margin: 0 0 32px;
  }}
  .cta {{
    display: inline-block;
    padding: 12px 28px;
    background: var(--accent);
    color: #0f0c06;
    text-decoration: none;
    border-radius: 999px;
    font-weight: 600;
    font-size: 15px;
    transition: transform 0.15s ease, box-shadow 0.15s ease;
  }}
  .cta:hover {{
    transform: translateY(-1px);
    box-shadow: 0 8px 24px -8px rgba(215, 180, 106, 0.5);
  }}
  .footer {{
    margin-top: 48px;
    font-size: 12px; letter-spacing: 0.12em; text-transform: uppercase;
    color: var(--fg-2);
  }}
</style>
</head>
<body>
<div class="wrap">
  <div class="icon">♪</div>
  <h1>This song has been removed</h1>
  <p>The creator deleted the share link. The song is no longer available — but you can create your own AI-generated Arabic song in a few minutes.</p>
  <a class="cta" href="{cta_url}">Try Faceless Lab →</a>
  <div class="footer">Faceless Lab · AI music & horror shorts</div>
</div>
</body>
</html>"""
    return HTMLResponse(
        html,
        status_code=404,
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


@app.get("/p/{token}", include_in_schema=False)
def shared_song_page(token: str):
    """Public share page (no auth) — embeds the video, displays the
    lyrics with proper RTL handling and section-tag styling, sets
    Open Graph / Twitter Card meta tags for link previews."""
    from fastapi.responses import HTMLResponse
    try:
        run_dir, script = _resolve_shared_song(token)
    except HTTPException as e:
        if e.status_code == 404:
            return _render_removed_share_page()
        raise
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
    # OG card fingerprint follows the cover's mtime so re-renders /
    # regenerated covers also bust the social-preview cache (WhatsApp,
    # Twitter, iMessage all hard-cache OG images aggressively).
    og_v = _mtime(run_dir / "og.png") or cover_v
    video_url = f"{base_url}/p/{token}/video?v={video_v}"
    cover_url = f"{base_url}/p/{token}/cover?v={cover_v}"
    og_url = f"{base_url}/p/{token}/og?v={og_v}"

    def esc(s: str) -> str:
        return (s.replace("&", "&amp;").replace("<", "&lt;")
                 .replace(">", "&gt;").replace('"', "&quot;"))

    # Render lyrics: each line is either a `[Verse 1]`-style section
    # header (rendered as a small chip) or a normal sung line.
    # Each line gets a `data-line` index. If lyrics.json exists (produced
    # by pipeline/song_align.py) we ALSO emit a cues array driving exact
    # audio-synced highlight. Otherwise we fall back to the legacy
    # stanza-divided linear approximation.
    is_rtl = language in ("ar", "he", "fa", "ur")
    text_dir = "rtl" if is_rtl else "ltr"

    aligned: dict | None = None
    aligned_path = run_dir / "lyrics.json"
    if aligned_path.exists():
        try:
            aligned = json.loads(aligned_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            aligned = None

    # New v3 model: group lines into <section class="stanza">…</section>
    # blocks. The whole stanza highlights together when its time range is
    # active (vs. the v2 per-line approach that drifted visibly on songs
    # where Whisper word-segmentation got jittery). Per-line click
    # handlers are still wired for tap-to-seek.
    #
    # Final cues_json shape (per stanza, not per line):
    #   [{"st": 1, "label": "Verse 1", "s": 0.0, "e": 14.5}, …]
    #
    # First pass parses the lyric stream into structured stanza records;
    # second pass renders HTML + builds the cues array.
    section_re = _re.compile(r"^\[([^\]]+)\]\s*$")

    def _entries_from_aligned(d: dict) -> list[dict]:
        return [
            {
                "kind": e.get("kind"),
                "text": e.get("text", ""),
                "stanza": int(e.get("stanza") or 0),
                "start": e.get("start"),
                "end": e.get("end"),
            }
            for e in d.get("lines", [])
        ]

    def _entries_from_raw(text: str) -> list[dict]:
        out: list[dict] = []
        st = 0
        in_st = False
        for raw in text.split("\n"):
            line = raw.strip()
            if not line:
                in_st = False
                continue
            m = section_re.match(line)
            if m:
                st += 1
                out.append({
                    "kind": "section", "text": m.group(1),
                    "stanza": st, "start": None, "end": None,
                })
                in_st = True
            else:
                if not in_st:
                    st += 1
                    in_st = True
                out.append({
                    "kind": "line", "text": line,
                    "stanza": st, "start": None, "end": None,
                })
        return out

    entries = (
        _entries_from_aligned(aligned) if aligned and aligned.get("lines")
        else _entries_from_raw(lyrics)
    )

    # Group entries by stanza index, preserving order.
    stanza_records: list[dict] = []
    by_stanza: dict[int, dict] = {}
    line_idx = 0
    for e in entries:
        sid = e["stanza"]
        rec = by_stanza.get(sid)
        if rec is None:
            rec = {"id": sid, "label": "", "lines": [], "starts": [], "ends": []}
            by_stanza[sid] = rec
            stanza_records.append(rec)
        if e["kind"] == "section":
            rec["label"] = e["text"]
        else:
            line_idx += 1
            rec["lines"].append({
                "line_id": line_idx,
                "text": e["text"],
                "start": e["start"],
                "end": e["end"],
            })
        if e.get("start") is not None:
            rec["starts"].append(float(e["start"]))
        if e.get("end") is not None:
            rec["ends"].append(float(e["end"]))

    # Compute per-stanza (start, end) ranges from constituent line times.
    # Stanzas with no aligned lines (legacy songs, edge cases) skip cues.
    cues: list[dict] = []
    for rec in stanza_records:
        s = min(rec["starts"]) if rec["starts"] else None
        e = max(rec["ends"]) if rec["ends"] else None
        if s is not None and e is not None and e > s:
            cues.append({
                "st": rec["id"],
                "label": rec["label"],
                "s": s,
                "e": e,
            })

    # Render HTML. Each stanza wraps its section label + lines.
    lyrics_html_parts: list[str] = []
    for rec in stanza_records:
        lyrics_html_parts.append(
            f'<section class="stanza" data-stanza="{rec["id"]}">'
        )
        if rec["label"]:
            lyrics_html_parts.append(
                f'<div class="section">{esc(rec["label"])}</div>'
            )
        for ln in rec["lines"]:
            seek_attr = ""
            if ln["start"] is not None:
                seek_attr = f' data-seek="{float(ln["start"]):.3f}"'
            lyrics_html_parts.append(
                f'<p class="line" data-line="{ln["line_id"]}"'
                f' data-stanza="{rec["id"]}"{seek_attr}>{esc(ln["text"])}</p>'
            )
        lyrics_html_parts.append("</section>")

    lyrics_html = "\n".join(lyrics_html_parts)
    total_stanzas = len(stanza_records)
    cues_json = json.dumps(cues, ensure_ascii=False)
    # Compact stanza-ribbon labels: short, accessible, used for the
    # nav-chip strip rendered between the player and lyrics.
    nav_chips_html = "".join(
        f'<button type="button" class="stanza-chip" '
        f'data-stanza-target="{rec["id"]}">'
        f'{esc(rec["label"]) if rec["label"] else str(rec["id"])}'
        f'</button>'
        for rec in stanza_records if rec["lines"]
    )

    html = f"""<!DOCTYPE html>
<html lang="{esc(language)}">
<head>
<meta charset="utf-8">
<title>{esc(title)} · faceless</title>
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="description" content="{esc(teaser)}">
<meta name="theme-color" content="#0a0d14">

<!-- Open Graph -->
<meta property="og:site_name" content="Faceless Lab">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(teaser)}">
<meta property="og:image" content="{og_url}">
<meta property="og:image:secure_url" content="{og_url}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
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
<meta name="twitter:image" content="{og_url}">
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
  /* Karaoke v3 — section-by-section, not line-by-line.
     Whole-stanza highlight is honest about the imperfect alignment:
     the active stanza glows together and all its lines stay readable.
     Per-line tap-to-seek is still wired (data-seek attributes on
     each <p>), so visitors can fine-tune position without watching
     a wobble that tries (and fails) to follow Whisper's word jitter. */
  .stanza {{
    position: relative;
    border-radius: 14px;
    padding: 12px 16px;
    margin: 6px -16px;
    transition:
      background-color 320ms ease,
      box-shadow 320ms ease,
      opacity 320ms ease,
      transform 320ms ease;
    opacity: 0.55;
  }}
  .lyrics.idle .stanza {{ opacity: 1; }}
  .stanza.active {{
    opacity: 1;
    background: linear-gradient(180deg,
      rgba(215, 180, 106, 0.10),
      rgba(215, 180, 106, 0.02));
    box-shadow:
      inset 0 0 0 1px rgba(215, 180, 106, 0.32),
      0 18px 40px -28px rgba(215, 180, 106, 0.35);
  }}
  .stanza.active .section {{
    color: var(--accent);
    background: rgba(215, 180, 106, 0.22);
  }}
  /* Per-line elements no longer animate opacity themselves —
     stanza-level opacity handles the dim/full state. */
  .lyrics .line, .lyrics .section {{
    transition: background-color 200ms ease, transform 200ms ease;
  }}

  /* ---------------- v2: polish + interactivity ---------------- */

  /* Bigger, more confident title typography. Subtle text-shadow keeps
     letters legible against the cover-glow that animates behind. */
  .title {{
    font-size: 32px;
    letter-spacing: -0.015em;
    text-shadow: 0 1px 24px rgba(0, 0, 0, 0.4);
  }}
  body[dir="rtl"] .title {{
    font-size: 38px;
    line-height: 1.25;
  }}
  @media (max-width: 480px) {{
    .title {{ font-size: 26px; }}
    body[dir="rtl"] .title {{ font-size: 30px; }}
  }}

  /* Audio-driven glow around the player. The JS sets --pulse on a
     timer driven by Web Audio's AnalyserNode; 0 when paused, 0.3–1.0
     when playing. The transform stays subtle so it doesn't compete
     with the actual content. */
  .player {{
    --pulse: 0;
    transition: box-shadow 220ms ease;
    box-shadow:
      0 30px 80px -20px rgba(0,0,0,0.7),
      0 0 0 1px rgba(255,255,255,0.04),
      0 0 calc(40px + var(--pulse) * 60px) calc(var(--pulse) * 14px)
        rgba(215, 180, 106, calc(0.10 + var(--pulse) * 0.18));
  }}

  /* Ken Burns on the poster element. Browsers show the <video>'s poster
     attribute until play(); we slow-zoom it via a CSS animation so the
     page doesn't feel static while the visitor reads the title.
     Animation is suppressed once the video starts (.playing class added
     by the JS) — at that point the burned-in zoompan from ffmpeg takes
     over. */
  .player.before-play::after {{
    content: '';
    position: absolute; inset: 0;
    background: radial-gradient(60% 40% at 50% 80%,
      rgba(215, 180, 106, 0.06), transparent 70%);
    pointer-events: none;
    animation: kenburns-glow 8s ease-in-out infinite alternate;
  }}
  @keyframes kenburns-glow {{
    0%   {{ transform: translate(0, 0)   scale(1); opacity: 0.7; }}
    100% {{ transform: translate(-2%, 2%) scale(1.04); opacity: 1; }}
  }}

  /* Lyric lines are now clickable — tapping seeks the audio to that
     cue's start time. The hover affordance has to stay subtle so the
     reading experience isn't fidgety. */
  .lyrics .line {{
    cursor: pointer;
    border-radius: 10px;
    padding: 4px 8px;
    margin-left: -8px;
    margin-right: -8px;
    transition:
      opacity 0.5s ease,
      color 0.5s ease,
      background-color 220ms ease,
      transform 220ms ease;
  }}
  .lyrics .line:hover {{
    background-color: rgba(215, 180, 106, 0.08);
  }}
  .lyrics .line:active {{
    transform: scale(0.985);
  }}

  /* Frosted-glass effect on the lyrics container — picks up the cover
     gradient subtly. WebKit/blink only; Firefox falls back to solid. */
  .lyrics {{
    background:
      linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.01)),
      rgba(13, 17, 25, 0.4);
    backdrop-filter: blur(14px) saturate(140%);
    -webkit-backdrop-filter: blur(14px) saturate(140%);
  }}

  /* Stat bar — heart + views. Sits between the artist tag and lyrics. */
  .stat-bar {{
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 18px;
    margin: 0 0 28px;
  }}
  .heart-btn {{
    display: inline-flex; align-items: center; gap: 8px;
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    color: var(--fg-1);
    border-radius: 999px;
    padding: 9px 18px;
    font-family: inherit;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition:
      background-color 200ms ease,
      border-color 200ms ease,
      color 200ms ease,
      transform 200ms ease;
    -webkit-tap-highlight-color: transparent;
  }}
  .heart-btn:hover {{
    background: rgba(215, 180, 106, 0.08);
    border-color: rgba(215, 180, 106, 0.35);
    color: var(--fg-0);
  }}
  .heart-btn:active {{ transform: scale(0.96); }}
  .heart-btn.liked {{
    background: rgba(215, 180, 106, 0.16);
    border-color: rgba(215, 180, 106, 0.55);
    color: var(--accent);
  }}
  .heart-btn .heart-icon {{
    width: 16px; height: 16px;
    transition: transform 220ms ease, fill 220ms ease;
    fill: none;
    stroke: currentColor;
    stroke-width: 2;
  }}
  .heart-btn.liked .heart-icon {{
    fill: var(--accent);
    animation: heart-pop 360ms ease-out;
  }}
  @keyframes heart-pop {{
    0%   {{ transform: scale(1); }}
    35%  {{ transform: scale(1.35); }}
    100% {{ transform: scale(1); }}
  }}
  .view-pill {{
    display: inline-flex; align-items: center; gap: 7px;
    font-size: 13px; color: var(--fg-2);
    background: transparent;
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 999px;
    padding: 8px 14px;
  }}
  .view-pill .eye-icon {{
    width: 14px; height: 14px;
    fill: none; stroke: currentColor; stroke-width: 1.7;
  }}

  /* ---------------- v3: nav ribbon, download, particles, entrance ---------------- */

  /* Section-jump nav chips below the player. Horizontally scrolling
     on mobile; centered on desktop. Active chip is the stanza the
     player is currently inside. */
  .stanza-nav {{
    display: flex;
    flex-wrap: nowrap;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
    gap: 8px;
    margin: 20px -20px 0;
    padding: 0 20px 4px;
  }}
  .stanza-nav::-webkit-scrollbar {{ display: none; }}
  .stanza-chip {{
    flex: 0 0 auto;
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    color: var(--fg-2);
    border-radius: 999px;
    padding: 7px 14px;
    font-family: inherit;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    cursor: pointer;
    white-space: nowrap;
    transition:
      background-color 200ms ease,
      border-color 200ms ease,
      color 200ms ease,
      transform 180ms ease;
    -webkit-tap-highlight-color: transparent;
  }}
  .stanza-chip:hover {{
    background: rgba(215, 180, 106, 0.06);
    border-color: rgba(215, 180, 106, 0.28);
    color: var(--fg-0);
  }}
  .stanza-chip.active {{
    background: rgba(215, 180, 106, 0.18);
    border-color: rgba(215, 180, 106, 0.55);
    color: var(--accent);
  }}
  .stanza-chip:active {{ transform: scale(0.96); }}

  /* Download button — same pill family as the heart, hosted in
     the stat bar. Subtle gold tint distinguishes it. */
  .download-btn {{
    display: inline-flex; align-items: center; gap: 8px;
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    color: var(--fg-1);
    border-radius: 999px;
    padding: 9px 18px;
    font-family: inherit;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    text-decoration: none;
    transition:
      background-color 200ms ease,
      border-color 200ms ease,
      color 200ms ease,
      transform 200ms ease;
    -webkit-tap-highlight-color: transparent;
  }}
  .download-btn:hover {{
    background: rgba(215, 180, 106, 0.08);
    border-color: rgba(215, 180, 106, 0.35);
    color: var(--fg-0);
  }}
  .download-btn:active {{ transform: scale(0.96); }}
  .download-btn .dl-icon {{
    width: 14px; height: 14px;
    fill: none; stroke: currentColor; stroke-width: 1.7;
  }}

  /* Heart burst — gold sparks fly out when a visitor likes the song.
     A small particle system on the heart's bounding box. */
  .heart-btn {{ position: relative; }}
  .heart-btn .spark {{
    position: absolute;
    top: 50%; left: 50%;
    width: 6px; height: 6px;
    margin: -3px 0 0 -3px;
    background: var(--accent);
    border-radius: 50%;
    pointer-events: none;
    opacity: 0;
  }}
  @keyframes spark-fly {{
    0%   {{ transform: translate(0, 0) scale(1);   opacity: 1; }}
    100% {{ transform: var(--spark-end) scale(0.2); opacity: 0; }}
  }}

  /* Atmospheric particle field behind the page — three slow-floating
     gold orbs, very low opacity. Pure CSS so no extra paint cost from
     a canvas. */
  .ambient {{
    position: fixed; inset: 0;
    pointer-events: none;
    z-index: 0;
    overflow: hidden;
  }}
  .ambient .orb {{
    position: absolute;
    border-radius: 50%;
    filter: blur(60px);
    opacity: 0.25;
    mix-blend-mode: screen;
  }}
  .ambient .orb-1 {{
    width: 320px; height: 320px;
    top: -80px; left: -60px;
    background: rgba(215, 180, 106, 0.5);
    animation: drift-1 18s ease-in-out infinite alternate;
  }}
  .ambient .orb-2 {{
    width: 280px; height: 280px;
    bottom: -100px; right: -80px;
    background: rgba(106, 130, 215, 0.32);
    animation: drift-2 22s ease-in-out infinite alternate;
  }}
  .ambient .orb-3 {{
    width: 200px; height: 200px;
    top: 50%; left: 75%;
    background: rgba(215, 106, 156, 0.18);
    animation: drift-3 28s ease-in-out infinite alternate;
  }}
  @keyframes drift-1 {{
    0%   {{ transform: translate(0,   0)   scale(1);   }}
    100% {{ transform: translate(40px, 60px) scale(1.15); }}
  }}
  @keyframes drift-2 {{
    0%   {{ transform: translate(0,   0)   scale(1);    }}
    100% {{ transform: translate(-30px, -40px) scale(1.1); }}
  }}
  @keyframes drift-3 {{
    0%   {{ transform: translate(0, 0) scale(1); opacity: 0.18; }}
    100% {{ transform: translate(-50px, 30px) scale(0.85); opacity: 0.32; }}
  }}
  .wrap {{ position: relative; z-index: 1; }}

  /* Entrance animation — page elements rise into place on first paint
     so the song reveal feels intentional. Reduces motion gracefully. */
  @keyframes rise-in {{
    0%   {{ opacity: 0; transform: translateY(14px); }}
    100% {{ opacity: 1; transform: translateY(0); }}
  }}
  .player, .title, .made-by, .stat-bar, .stanza-nav, .lyrics, footer {{
    animation: rise-in 800ms cubic-bezier(0.16, 0.84, 0.44, 1) backwards;
  }}
  .player {{ animation-delay: 0ms; }}
  .title  {{ animation-delay: 100ms; }}
  .made-by{{ animation-delay: 180ms; }}
  .stat-bar {{ animation-delay: 240ms; }}
  .stanza-nav {{ animation-delay: 300ms; }}
  .lyrics {{ animation-delay: 360ms; }}
  footer {{ animation-delay: 480ms; }}
  @media (prefers-reduced-motion: reduce) {{
    .player, .title, .made-by, .stat-bar, .stanza-nav, .lyrics, footer {{
      animation: none;
    }}
    .ambient .orb {{ animation: none; }}
    .player.before-play::after {{ animation: none; }}
  }}
</style>
</head>
<body dir="{text_dir}">
<div class="ambient" aria-hidden="true">
  <span class="orb orb-1"></span>
  <span class="orb orb-2"></span>
  <span class="orb orb-3"></span>
</div>
<div class="wrap">
  <div class="player before-play" id="player-wrap">
    <video id="player" controls playsinline poster="{cover_url}" preload="metadata">
      <source src="{video_url}" type="video/mp4">
      Your browser does not support embedded video.
    </video>
  </div>
  <h1 class="title">{esc(title)}</h1>
  <p class="made-by">Faceless Lab<span class="dot"></span>AI song</p>
  <div class="stat-bar" id="stat-bar" data-token="{token}">
    <button type="button" class="heart-btn" id="heart-btn" aria-pressed="false" aria-label="Like this song">
      <svg class="heart-icon" viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 20.5s-7.5-4.7-7.5-10.3a4.5 4.5 0 0 1 8-2.8 4.5 4.5 0 0 1 7 2.8C19.5 15.8 12 20.5 12 20.5z" />
      </svg>
      <span class="heart-count" id="heart-count">0</span>
    </button>
    <span class="view-pill" aria-label="View count">
      <svg class="eye-icon" viewBox="0 0 24 24" aria-hidden="true">
        <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" />
        <circle cx="12" cy="12" r="3" />
      </svg>
      <span class="view-count" id="view-count">0</span>
    </span>
    <a class="download-btn" id="download-btn" download href="{video_url}" aria-label="Download MP4">
      <svg class="dl-icon" viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 4v12m0 0l-5-5m5 5l5-5M4 20h16" />
      </svg>
      <span>Download</span>
    </a>
  </div>
  <nav class="stanza-nav" id="stanza-nav" aria-label="Jump to section">
    {nav_chips_html}
  </nav>
  <div class="lyrics idle" id="lyrics" data-total-stanzas="{total_stanzas}">
    {lyrics_html}
  </div>
  <script id="lyric-cues" type="application/json">{cues_json}</script>
  <footer>
    Made with <a href="{base_url}/app/">Faceless Lab</a> — AI-generated music
  </footer>
</div>
<script>
  // Karaoke v3 — SECTION-by-section, never line-by-line.
  //
  // The Whisper-derived per-line timestamps drift visibly because
  // Arabic sub-word boundaries are unreliable. Highlighting an entire
  // stanza for its whole sung range absorbs that drift: the visitor
  // sees the right *block* of lyrics for the moment they're hearing,
  // and individual lines never appear to lag or jump.
  //
  // Cue shape (one per stanza): {{st, label, s, e}}.
  (function() {{
    const player = document.getElementById('player');
    const lyrics = document.getElementById('lyrics');
    if (!player || !lyrics) return;
    const cuesEl = document.getElementById('lyric-cues');
    let cues = [];
    if (cuesEl) {{
      try {{ cues = JSON.parse(cuesEl.textContent || '[]'); }} catch (e) {{}}
    }}
    const stanzas = new Map();
    lyrics.querySelectorAll('.stanza[data-stanza]').forEach(function(el) {{
      stanzas.set(parseInt(el.dataset.stanza, 10), el);
    }});
    const navChips = new Map();
    document.querySelectorAll('.stanza-chip[data-stanza-target]').forEach(function(el) {{
      navChips.set(parseInt(el.dataset.stanzaTarget, 10), el);
    }});

    let activeStanza = -1;
    let activated = false;

    function setActive(stanzaId) {{
      if (stanzaId === activeStanza) return;
      activeStanza = stanzaId;
      stanzas.forEach(function(el, id) {{
        const on = (id === stanzaId);
        el.classList.toggle('active', on);
        if (on) {{
          // Scroll so the active stanza is visible without snapping the
          // whole page — use nearest, not center, so the lyric column
          // scrolls and the player overhead stays put.
          el.scrollIntoView({{behavior: 'smooth', block: 'nearest'}});
        }}
      }});
      navChips.forEach(function(chip, id) {{
        chip.classList.toggle('active', id === stanzaId);
      }});
    }}

    function findStanzaAt(t) {{
      // Linear scan is fine — songs have <20 stanzas.
      // Returns the latest cue whose start <= t. If we're past the last
      // cue's end, we still hold that stanza so the highlight doesn't
      // disappear during outro / instrumental tails.
      let best = -1;
      for (let i = 0; i < cues.length; i++) {{
        if (cues[i].s <= t + 0.05) best = i;
      }}
      if (best < 0) return -1;
      return cues[best].st;
    }}

    player.addEventListener('play', function() {{
      if (!activated) {{ lyrics.classList.remove('idle'); activated = true; }}
    }});
    player.addEventListener('timeupdate', function() {{
      const t = player.currentTime;
      if (cues.length > 0) {{
        setActive(findStanzaAt(t));
        return;
      }}
      // Legacy fallback: linearly partition the audio across stanzas
      // (old songs minted before lyrics.json existed).
      const dur = player.duration;
      if (!dur || isNaN(dur)) return;
      const total = parseInt(lyrics.dataset.totalStanzas || '0', 10);
      if (total <= 0) return;
      const stIdx = Math.min(total, Math.floor((t / dur) * total) + 1);
      setActive(stIdx);
    }});
    player.addEventListener('ended', function() {{
      setActive(-1);
      lyrics.classList.add('idle');
      activated = false;
    }});
  }})();

  // ------------------------------------------------------------------
  // Tap-to-seek: clicking any lyric line jumps the audio to that line.
  // Each <p class="line"> carries data-seek with its start time (set
  // by the Python side when lyrics.json is available). Tapping a
  // stanza nav chip jumps to the first line of that stanza.
  //
  // This is the manual recovery for any residual drift in the
  // automatic stanza highlight — the visitor can always click where
  // they want and the audio follows.
  // ------------------------------------------------------------------
  (function() {{
    const player = document.getElementById('player');
    const lyrics = document.getElementById('lyrics');
    if (!player || !lyrics) return;
    function seekAndPlay(t) {{
      try {{ player.currentTime = Math.max(0, t - 0.1); }} catch (e) {{ return; }}
      if (player.paused) {{
        const p = player.play();
        if (p && typeof p.catch === 'function') p.catch(function() {{}});
      }}
    }}
    lyrics.querySelectorAll('.line[data-seek]').forEach(function(el) {{
      el.addEventListener('click', function() {{
        const t = parseFloat(el.dataset.seek);
        if (!isNaN(t)) seekAndPlay(t);
      }});
    }});

    // Stanza ribbon: each chip jumps to the FIRST line of its stanza
    // (read the first .line[data-seek] inside that .stanza section).
    document.querySelectorAll('.stanza-chip[data-stanza-target]').forEach(function(chip) {{
      chip.addEventListener('click', function() {{
        const sid = chip.dataset.stanzaTarget;
        const stanza = lyrics.querySelector('.stanza[data-stanza="' + sid + '"]');
        if (!stanza) return;
        const firstLine = stanza.querySelector('.line[data-seek]');
        if (!firstLine) return;
        const t = parseFloat(firstLine.dataset.seek);
        if (!isNaN(t)) seekAndPlay(t);
      }});
    }});
  }})();

  // ------------------------------------------------------------------
  // Audio-driven glow: subtle pulse around the player driven by the
  // current audio's RMS amplitude. Created lazily on the first 'play'
  // because Chrome only allows AudioContext creation after a user
  // gesture; before that it's blocked.
  // ------------------------------------------------------------------
  (function() {{
    const player = document.getElementById('player');
    const wrap = document.getElementById('player-wrap');
    if (!player || !wrap) return;
    let ctx = null, src = null, analyser = null, data = null, raf = 0;

    function tick() {{
      if (!analyser) return;
      analyser.getByteFrequencyData(data);
      // Focus on bass + low-mid bins (0–~3 kHz at 44.1 kHz) so the pulse
      // tracks the actual music energy rather than vocal sibilance.
      let sum = 0;
      const cap = Math.min(data.length, 80);
      for (let i = 0; i < cap; i++) sum += data[i];
      const avg = sum / cap / 255; // 0..1
      // Smooth + clamp: ease pulse for visual stability.
      const cur = parseFloat(wrap.style.getPropertyValue('--pulse')) || 0;
      const next = Math.max(0, Math.min(1, cur * 0.65 + avg * 0.7));
      wrap.style.setProperty('--pulse', next.toFixed(3));
      raf = requestAnimationFrame(tick);
    }}

    function startIfPossible() {{
      if (ctx) return;
      const AC = window.AudioContext || window.webkitAudioContext;
      if (!AC) return;
      try {{
        ctx = new AC();
        src = ctx.createMediaElementSource(player);
        analyser = ctx.createAnalyser();
        analyser.fftSize = 256;
        analyser.smoothingTimeConstant = 0.75;
        data = new Uint8Array(analyser.frequencyBinCount);
        src.connect(analyser);
        analyser.connect(ctx.destination);
      }} catch (e) {{
        // Some browsers (Safari iOS) restrict createMediaElementSource
        // on cross-origin media. Fail silent — the static glow is fine.
        ctx = null;
        return;
      }}
      tick();
    }}

    player.addEventListener('play', function() {{
      wrap.classList.remove('before-play');
      startIfPossible();
      if (ctx && ctx.state === 'suspended') ctx.resume();
    }});
    player.addEventListener('pause', function() {{
      wrap.style.setProperty('--pulse', '0');
    }});
    player.addEventListener('ended', function() {{
      wrap.style.setProperty('--pulse', '0');
    }});
  }})();

  // ------------------------------------------------------------------
  // Social: anonymous likes + view counter.
  // Client identity is a random UUID in localStorage — survives across
  // pages, doesn't survive cache-clears (intentional; this is best-
  // effort engagement signal, not a voting system).
  // ------------------------------------------------------------------
  (function() {{
    const bar = document.getElementById('stat-bar');
    if (!bar) return;
    const token = bar.dataset.token;
    if (!token) return;
    const heartBtn = document.getElementById('heart-btn');
    const heartCount = document.getElementById('heart-count');
    const viewCount = document.getElementById('view-count');

    function getClientId() {{
      let cid = '';
      try {{ cid = localStorage.getItem('faceless_cid') || ''; }} catch (e) {{}}
      if (cid && cid.length >= 8) return cid;
      // Modest fallback for browsers that block localStorage (private
      // mode etc.) — keep it in-memory only; counts simply won't dedupe.
      cid = (
        (crypto && crypto.randomUUID) ? crypto.randomUUID()
                                      : Math.random().toString(36).slice(2) +
                                        Math.random().toString(36).slice(2)
      ).replace(/-/g, '');
      try {{ localStorage.setItem('faceless_cid', cid); }} catch (e) {{}}
      return cid;
    }}
    const cid = getClientId();

    function renderStats(s) {{
      if (typeof s.likes === 'number' && heartCount) {{
        heartCount.textContent = String(s.likes);
      }}
      if (typeof s.views === 'number' && viewCount) {{
        viewCount.textContent = String(s.views);
      }}
      if (typeof s.liked === 'boolean' && heartBtn) {{
        heartBtn.classList.toggle('liked', s.liked);
        heartBtn.setAttribute('aria-pressed', s.liked ? 'true' : 'false');
      }}
    }}

    // 1. Initial stats fetch (so any prior view/like state shows correctly).
    fetch('/p/' + encodeURIComponent(token) + '/stats?client_id=' +
          encodeURIComponent(cid))
      .then(function(r) {{ return r.ok ? r.json() : null; }})
      .then(function(s) {{ if (s) renderStats(s); }})
      .catch(function() {{}});

    // 2. Register a view. Deduped server-side per (cid, song) in a 6h
    //    window so refreshes don't inflate. Throttled here too via a
    //    localStorage timestamp to skip the network call entirely.
    const viewKey = 'faceless_v_' + token;
    let lastView = 0;
    try {{ lastView = parseInt(localStorage.getItem(viewKey) || '0', 10) || 0; }}
    catch (e) {{}}
    if (Date.now() - lastView > 6 * 3600 * 1000) {{
      fetch('/p/' + encodeURIComponent(token) + '/view', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ client_id: cid }})
      }})
        .then(function(r) {{ return r.ok ? r.json() : null; }})
        .then(function(s) {{
          if (s) renderStats(s);
          try {{ localStorage.setItem(viewKey, String(Date.now())); }}
          catch (e) {{}}
        }})
        .catch(function() {{}});
    }}

    // 3. Like toggle on click.
    if (heartBtn) {{
      heartBtn.addEventListener('click', function() {{
        // Optimistic UI — flip the state immediately, then reconcile
        // with server response.
        const wasLiked = heartBtn.classList.contains('liked');
        heartBtn.classList.toggle('liked', !wasLiked);
        heartBtn.setAttribute('aria-pressed', wasLiked ? 'false' : 'true');
        if (heartCount) {{
          const cur = parseInt(heartCount.textContent || '0', 10) || 0;
          heartCount.textContent = String(Math.max(0, cur + (wasLiked ? -1 : 1)));
        }}
        // Spark burst on transition into "liked". Six gold particles
        // fly outward from the heart's center then fade.
        if (!wasLiked) {{
          for (let i = 0; i < 6; i++) {{
            const spark = document.createElement('span');
            spark.className = 'spark';
            const angle = (i / 6) * Math.PI * 2 + (Math.random() - 0.5) * 0.3;
            const dist = 22 + Math.random() * 14;
            const dx = Math.cos(angle) * dist;
            const dy = Math.sin(angle) * dist;
            spark.style.setProperty('--spark-end',
              'translate(' + dx.toFixed(1) + 'px,' + dy.toFixed(1) + 'px)');
            spark.style.animation = 'spark-fly 620ms ease-out forwards';
            heartBtn.appendChild(spark);
            setTimeout(function(s) {{ return function() {{
              if (s.parentNode) s.parentNode.removeChild(s);
            }}; }}(spark), 700);
          }}
        }}
        fetch('/p/' + encodeURIComponent(token) + '/like', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ client_id: cid }})
        }})
          .then(function(r) {{ return r.ok ? r.json() : null; }})
          .then(function(s) {{ if (s) renderStats(s); }})
          .catch(function() {{
            // Rollback optimistic UI on failure
            heartBtn.classList.toggle('liked', wasLiked);
            heartBtn.setAttribute('aria-pressed', wasLiked ? 'true' : 'false');
          }});
      }});
    }}
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


def _branded_filename(title: str | None, ext: str) -> str:
    """Slugify the song title into a download-safe filename so the
    file lands as faceless-lab-<title>.mp4 instead of final.mp4.
    Falls back to a generic name when the title is empty/missing.
    The returned slug may contain non-ASCII characters; callers that
    place it into an HTTP header must use `_content_disposition` below
    (which handles RFC 5987 percent-encoding)."""
    import re as _re
    if title:
        slug = _re.sub(r"[^\w\-]+", "-", title.strip(), flags=_re.UNICODE)
        slug = slug.strip("-")[:80] or "song"
    else:
        slug = "song"
    return f"faceless-lab-{slug}.{ext}"


def _content_disposition(filename: str, disposition: str = "inline") -> str:
    """Build a Content-Disposition value that handles non-ASCII safely.

    HTTP headers are encoded as latin-1. A filename like
    `faceless-lab-وَشْمُ.mp4` crashes Starlette's header writer with
    UnicodeEncodeError if we use a raw `filename=...` parameter.

    RFC 5987 solves this with `filename*=UTF-8''<percent-encoded>`.
    For backwards compatibility we also include an ASCII-only
    `filename=...` (any non-ASCII rune is stripped). Modern clients
    prefer `filename*=` when both are present, legacy clients fall
    back to the ASCII one."""
    from urllib.parse import quote
    ascii_only = "".join(c if ord(c) < 128 else "_" for c in filename) or "song.mp4"
    encoded = quote(filename, safe="")
    return (
        f'{disposition}; filename="{ascii_only}"; '
        f"filename*=UTF-8''{encoded}"
    )


@app.get("/p/{token}/video", include_in_schema=False)
def shared_song_video(token: str, request: Request):
    """No-auth video endpoint for the public share page.

    Range-aware (see _serve_video): a cinematic final.mp4 can exceed
    Cloud Run's ~32 MiB buffered-response cap, which 500'd the full-file
    GET browsers issue and broke playback on the share page.

    `Content-Disposition: inline; filename=...` lets browsers stream
    the video in-place while supplying a branded filename to "Save
    video as…" downloads. The slug is `faceless-lab-<title>.mp4` so
    re-uploaded copies on disk still advertise the product."""
    run_dir, script = _resolve_shared_song(token)
    path = run_dir / "final.mp4"
    if not path.exists():
        raise HTTPException(404, "video not found")
    fname = _branded_filename(script.get("title"), "mp4")
    headers = dict(_PUBLIC_BINARY_CACHE_HEADERS)
    headers["Content-Disposition"] = _content_disposition(fname)
    return _serve_video(path, request, extra_headers=headers)


@app.get("/p/{token}/cover", include_in_schema=False)
def shared_song_cover(token: str):
    """No-auth cover endpoint for the public share page (used by
    the <video> poster + thumbnail UIs)."""
    run_dir, _ = _resolve_shared_song(token)
    path = run_dir / "cover.png"
    if not path.exists():
        raise HTTPException(404, "cover not found")
    return FileResponse(
        path, media_type="image/png", headers=_PUBLIC_BINARY_CACHE_HEADERS,
    )


@app.get("/p/{token}/og", include_in_schema=False)
def shared_song_og(token: str):
    """No-auth OG card endpoint — 1200×630 composed image used as
    og:image / twitter:image. Generated lazily on first request if
    not already cached on disk (covers shares minted before the
    feature shipped). All future runs pre-compose the card during
    the song pipeline so this endpoint is cache-hit on the hot path."""
    run_dir, script = _resolve_shared_song(token)
    og_path = run_dir / "og.png"
    cover_path = run_dir / "cover.png"
    if not og_path.exists():
        if not cover_path.exists():
            raise HTTPException(404, "no cover to compose OG from")
        try:
            from pipeline.song_og import compose_og_image
            teaser_lines: list[str] = []
            for raw in (script.get("lyrics") or "").split("\n"):
                line = raw.strip()
                if not line or line.startswith("["):
                    continue
                teaser_lines.append(line)
                if len(teaser_lines) >= 2:
                    break
            compose_og_image(
                cover_path=cover_path,
                title=script.get("title", "AI song"),
                language=script.get("language", "ar"),
                teaser=" · ".join(teaser_lines),
                out_path=og_path,
            )
        except Exception:  # noqa: BLE001  composition is best-effort
            # If composition fails, fall back to the raw cover so
            # social previews still show something.
            return FileResponse(
                cover_path, media_type="image/png",
                headers=_PUBLIC_BINARY_CACHE_HEADERS,
            )
    return FileResponse(
        og_path, media_type="image/png", headers=_PUBLIC_BINARY_CACHE_HEADERS,
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
