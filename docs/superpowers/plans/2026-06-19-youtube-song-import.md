# YouTube Song Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Paste a YouTube link → the worker downloads the audio, detects tempo + transcribes it (internally), an LLM writes an **original** improved song inspired by its theme/mood/structure plus the user's "touch" instruction → then the normal review/approve/generate song pipeline.

**Architecture:** A new front door (`POST /songs/import`) that writes a draft run and spawns the existing Cloud Run Job worker for an `analyzing` pre-stage; the worker calls a new `pipeline/song_import.py` (download → analyze → build original script), writes `song.json`, and flips to `awaiting_approval`. Everything after that reuses the existing pipeline unchanged. Original-lyrics generation reuses `song_lyrics.generate_song_script`; a 4-gram overlap guard prevents near-copies.

**Tech Stack:** Python 3 / FastAPI / yt-dlp (new) / librosa / openai-whisper / pytest; Flutter. Invariants: `from __future__ import annotations` first; `pathlib.Path`; absolute `pipeline.` imports; external services (yt-dlp/Whisper/librosa/LLM) mocked in tests; resumable artifacts.

**Spec:** `docs/superpowers/specs/2026-06-19-youtube-song-import-design.md`

---

## File Structure

| File | Create/Modify | Responsibility |
|---|---|---|
| `pyproject.toml` | Modify | add `yt-dlp` |
| `pipeline/song_import.py` | Create | download_audio, analyze_reference, build_inspired_script, overlap guard, `ImportFetchError` |
| `pipeline/api.py` | Modify | `CreateSongImportRequest`, `POST /songs/import`, URL validation |
| `run.py` | Modify | `_run_song_post_approve` gains an `analyzing` pre-stage branch |
| `lib/api/client.dart` | Modify | `importSong(...)` |
| `lib/screens/new_song_screen.dart` | Modify | "Import from YouTube" mode (URL + instruction) |
| `tests/test_song_import.py` | Create | unit tests for the module |
| `tests/test_api.py` | Modify | `/songs/import` endpoint tests |
| `tests/test_run_song_mode.py` | Modify | worker analyze pre-stage test |

---

## Task 1: Add yt-dlp dependency

**Files:** Modify `pyproject.toml`; Test: none (dependency only)

- [ ] **Step 1: Add the dep**

In `pyproject.toml`, add to the `dependencies` list (after `"librosa>=0.10",`):

```toml
    # yt-dlp: fetch reference audio for YouTube song import. Uses the ffmpeg
    # already in the image to extract audio. NOTE: YouTube blocks datacenter
    # IPs, so this may fail from Cloud Run — handled gracefully downstream.
    "yt-dlp>=2024.0",
```

- [ ] **Step 2: Sync + verify import**

Run: `uv sync && uv run python -c "import yt_dlp; print('yt-dlp', yt_dlp.version.__version__)"`
Expected: prints a version, exit 0.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "build: add yt-dlp for YouTube song import"
```

---

## Task 2: `download_audio` + `ImportFetchError`

**Files:** Create `pipeline/song_import.py`; Test: `tests/test_song_import.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_song_import.py`:

```python
from __future__ import annotations

import pytest

import pipeline.song_import as si
from pipeline.song_import import ImportFetchError, download_audio


def test_download_audio_returns_path(tmp_path, monkeypatch):
    # Fake yt-dlp: pretend it wrote the output file.
    out = tmp_path / "reference.m4a"
    def fake_run(url, out_template):
        out.write_bytes(b"\x00\x00")  # stand-in audio bytes
        return str(out)
    monkeypatch.setattr(si, "_ytdlp_download", fake_run)
    p = download_audio("https://www.youtube.com/watch?v=abc123", tmp_path)
    assert p.exists() and p.name == "reference.m4a"


def test_download_audio_raises_clear_error(tmp_path, monkeypatch):
    def boom(url, out_template):
        raise RuntimeError("Video unavailable")
    monkeypatch.setattr(si, "_ytdlp_download", boom)
    with pytest.raises(ImportFetchError):
        download_audio("https://youtu.be/abc123", tmp_path)
```

- [ ] **Step 2: Run — expect FAIL**

Run: `uv run pytest tests/test_song_import.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pipeline.song_import'`.

- [ ] **Step 3: Implement (module + download_audio)**

Create `pipeline/song_import.py`:

```python
"""YouTube song import: fetch a reference track and turn it into an ORIGINAL
inspired song script.

The reference is used for inspiration only — tempo, genre, mood, theme and
section structure. The verbatim transcript is transient and is never stored,
displayed, or used to reproduce/paraphrase the source. See
docs/superpowers/specs/2026-06-19-youtube-song-import-design.md.
"""
from __future__ import annotations

import re
from pathlib import Path


class ImportFetchError(RuntimeError):
    """Raised when the reference audio can't be fetched (private, region-
    locked, age-restricted, network, or a datacenter-IP block)."""


def _ytdlp_download(url: str, out_template: str) -> str:
    """Download bestaudio to out_template via yt-dlp. Isolated so tests can
    monkeypatch it without invoking the network/binary."""
    import yt_dlp
    opts = {
        "format": "bestaudio/best",
        "outtmpl": out_template,
        "quiet": True,
        "noplaylist": True,
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "m4a"}
        ],
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])
    return out_template


def download_audio(url: str, out_dir: Path) -> Path:
    """Fetch the reference audio to out_dir/reference.m4a. Raises
    ImportFetchError with a clear message on any failure."""
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / "reference.m4a"
    try:
        _ytdlp_download(url, str(dest))
    except Exception as e:  # yt-dlp raises many error types
        raise ImportFetchError(
            f"Couldn't fetch that link — it may be private, region-locked, "
            f"or blocked. ({e})"
        ) from e
    if not dest.exists():
        raise ImportFetchError("Couldn't fetch that link — no audio downloaded.")
    return dest
```

- [ ] **Step 4: Run — expect PASS**

Run: `uv run pytest tests/test_song_import.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add pipeline/song_import.py tests/test_song_import.py
git commit -m "feat(song): download_audio + ImportFetchError (yt-dlp wrapper)"
```

---

## Task 3: `_ngram_overlap` (pure originality metric)

**Files:** Modify `pipeline/song_import.py`; Test: `tests/test_song_import.py`

- [ ] **Step 1: Write the failing test** — append to `tests/test_song_import.py`:

```python
from pipeline.song_import import _ngram_overlap


def test_ngram_overlap_detects_near_copy():
    src = "alpha beta gamma delta epsilon zeta eta theta"
    # Same 8 words -> all 4-grams overlap -> 1.0
    assert _ngram_overlap(src, src) == 1.0


def test_ngram_overlap_distinct_is_low():
    src = "alpha beta gamma delta epsilon zeta eta theta"
    new = "one two three four five six seven eight"
    assert _ngram_overlap(new, src) == 0.0


def test_ngram_overlap_empty_is_zero():
    assert _ngram_overlap("", "anything here at all") == 0.0
    assert _ngram_overlap("too short", "x y z a b c", n=4) == 0.0
```

- [ ] **Step 2: Run — expect FAIL**

Run: `uv run pytest tests/test_song_import.py -k ngram -v`
Expected: FAIL — `cannot import name '_ngram_overlap'`.

- [ ] **Step 3: Implement** — add to `pipeline/song_import.py`:

```python
def _ngram_overlap(generated: str, source: str, n: int = 4) -> float:
    """Fraction of the generated text's word n-grams that also appear in the
    source. Used to catch lyrics that drift too close to the reference."""
    def grams(text: str) -> set:
        words = re.findall(r"\w+", text.lower())
        if len(words) < n:
            return set()
        return {tuple(words[i:i + n]) for i in range(len(words) - n + 1)}
    g = grams(generated)
    if not g:
        return 0.0
    return len(g & grams(source)) / len(g)
```

- [ ] **Step 4: Run — expect PASS**

Run: `uv run pytest tests/test_song_import.py -k ngram -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add pipeline/song_import.py tests/test_song_import.py
git commit -m "feat(song): n-gram overlap metric for originality guard"
```

---

## Task 4: `analyze_reference`

**Files:** Modify `pipeline/song_import.py`; Test: `tests/test_song_import.py`

- [ ] **Step 1: Write the failing test** — append:

```python
from pipeline.song_import import analyze_reference


class _FakeLLM:
    def __init__(self, payload):
        self._payload = payload
    def complete(self, prompt, system=None):
        import json
        return json.dumps(self._payload, ensure_ascii=False)


_DESC = {
    "genre": "Arabic pop ballad",
    "mood": "melancholic",
    "instrumentation": "oud, strings, light percussion",
    "language": "ar",
    "one_line_theme": "longing for a distant home",
    "section_structure": "Verse, Pre-Chorus, Chorus, Verse, Chorus, Bridge, Chorus",
}


def test_analyze_reference_returns_descriptors_and_transcript(tmp_path, monkeypatch):
    import pipeline.song_import as si
    audio = tmp_path / "reference.m4a"; audio.write_bytes(b"\x00")
    monkeypatch.setattr(si, "_detect_bpm", lambda p: 92.0)
    monkeypatch.setattr(si, "_transcribe", lambda p, language: "la la la one two three")
    desc, transcript = analyze_reference(audio, llm=_FakeLLM(_DESC), language="ar")
    assert desc["bpm"] == 92.0
    assert desc["one_line_theme"] == "longing for a distant home"
    assert transcript == "la la la one two three"


def test_analyze_reference_degrades_when_transcription_fails(tmp_path, monkeypatch):
    import pipeline.song_import as si
    audio = tmp_path / "reference.m4a"; audio.write_bytes(b"\x00")
    monkeypatch.setattr(si, "_detect_bpm", lambda p: 0.0)
    def boom(p, language):
        raise RuntimeError("whisper failed")
    monkeypatch.setattr(si, "_transcribe", boom)
    # LLM still asked to characterise from no transcript -> style-only payload
    payload = dict(_DESC); payload["one_line_theme"] = None
    desc, transcript = analyze_reference(audio, llm=_FakeLLM(payload), language="ar")
    assert transcript == ""           # no transcript available
    assert desc["one_line_theme"] is None  # style-only
```

- [ ] **Step 2: Run — expect FAIL**

Run: `uv run pytest tests/test_song_import.py -k analyze -v`
Expected: FAIL — `cannot import name 'analyze_reference'`.

- [ ] **Step 3: Implement** — add to `pipeline/song_import.py`:

```python
import json

_ANALYZE_SYSTEM = """You analyze a reference song to seed an ORIGINAL new song.
You are given the detected tempo and (optionally) a rough transcript.

Return ONLY a JSON object (no markdown) with these keys:
  genre:            short genre/sub-genre descriptor
  mood:             one or two mood words
  instrumentation:  comma-separated instruments
  language:         BCP-ish language code of the song
  one_line_theme:   ONE short sentence describing the THEME (not the lyrics).
                    null if no transcript was provided.
  section_structure: e.g. "Verse, Pre-Chorus, Chorus, Verse, Chorus, Bridge"

Describe the THEME and STYLE only. Do NOT copy or quote the transcript text."""


def _detect_bpm(audio: Path) -> float:
    """Tempo via librosa; 0.0 if detection fails. Isolated for tests."""
    try:
        from pipeline.song_beats import _librosa_beat_track
        tempo, _ = _librosa_beat_track(audio)
        return float(tempo)
    except Exception:
        return 0.0


def _transcribe(audio: Path, language: str) -> str:
    """Whisper transcript (internal use only). Isolated for tests."""
    from pipeline.align import _load_whisper
    model = _load_whisper("base")
    result = model.transcribe(str(audio), language=language or None)
    return str(result.get("text", "")).strip()


def analyze_reference(audio: Path, *, llm, language: str) -> tuple[dict, str]:
    """Return ({bpm, genre, mood, instrumentation, language, one_line_theme,
    section_structure}, transcript). The transcript is returned for the
    caller's transient overlap check only — it must NOT be persisted."""
    bpm = _detect_bpm(audio)
    try:
        transcript = _transcribe(audio, language)
    except Exception as e:
        print(f"[song_import] transcription failed ({e}); style-only analysis")
        transcript = ""

    user_msg = f"Detected tempo: {round(bpm) or 'unknown'} BPM\nLanguage hint: {language}"
    if transcript:
        user_msg += f"\nRough transcript (context only):\n{transcript[:4000]}"
    else:
        user_msg += "\n(No transcript available — infer style from tempo + language.)"

    raw = llm.complete(user_msg, system=_ANALYZE_SYSTEM).strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?|\n?```$", "", raw, flags=re.MULTILINE).strip()
    parsed = json.loads(raw, strict=False)

    descriptors = {
        "bpm": bpm,
        "genre": str(parsed.get("genre", "")),
        "mood": str(parsed.get("mood", "")),
        "instrumentation": str(parsed.get("instrumentation", "")),
        "language": str(parsed.get("language", language)),
        "one_line_theme": parsed.get("one_line_theme"),
        "section_structure": str(parsed.get("section_structure", "")),
    }
    return descriptors, transcript
```

- [ ] **Step 4: Run — expect PASS**

Run: `uv run pytest tests/test_song_import.py -k analyze -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add pipeline/song_import.py tests/test_song_import.py
git commit -m "feat(song): analyze_reference — tempo + transcript-distilled descriptors"
```

---

## Task 5: `build_inspired_script` + originality guard

**Files:** Modify `pipeline/song_import.py`; Test: `tests/test_song_import.py`

This reuses the existing, tested `song_lyrics.generate_song_script` (which already
emits original lyrics + section tags + art_direction + scene_prompts and parses
the LLM JSON robustly). The reference's words never reach it — only the derived
theme + style descriptors do.

- [ ] **Step 1: Write the failing test** — append:

```python
from pipeline.song_import import build_inspired_script, OVERLAP_THRESHOLD
import pipeline.song_import as si2
from pipeline.song_lyrics import SongScript


def _script(lyrics):
    return SongScript(title="t", lyrics=lyrics, style_prompt="pop, 90 BPM",
                      cover_prompt="c", language="ar",
                      art_direction="moonlit", scene_prompts=["a", "b"])


def test_build_inspired_script_passes_clean_output(monkeypatch):
    calls = {"n": 0}
    def fake_gen(**kw):
        calls["n"] += 1
        return _script("[Verse 1]\nfresh original words\n\n[Chorus]\nbrand new hook\n")
    monkeypatch.setattr(si2, "generate_song_script", fake_gen)
    s = build_inspired_script(
        llm=object(),
        analysis={"genre": "pop", "bpm": 90, "mood": "sad",
                  "instrumentation": "oud", "one_line_theme": "loss"},
        instruction="make it Gulf dialect",
        language="ar",
        transcript="totally different reference words here please",
    )
    assert "[Chorus]" in s.lyrics
    assert calls["n"] == 1   # no regeneration needed


def test_build_inspired_script_regenerates_on_near_copy(monkeypatch):
    src = "one two three four five six seven eight nine ten"
    outputs = [
        _script("one two three four five six seven eight nine ten"),  # near-copy
        _script("[Verse 1]\nwholly distinct alpha bravo charlie\n[Chorus]\ndelta echo\n"),
    ]
    calls = {"n": 0}
    def fake_gen(**kw):
        out = outputs[min(calls["n"], len(outputs) - 1)]
        calls["n"] += 1
        return out
    monkeypatch.setattr(si2, "generate_song_script", fake_gen)
    s = build_inspired_script(
        llm=object(),
        analysis={"genre": "pop", "bpm": 90, "mood": "sad",
                  "instrumentation": "oud", "one_line_theme": "loss"},
        instruction=None, language="ar", transcript=src,
    )
    assert calls["n"] == 2          # regenerated once after the near-copy
    assert "alpha bravo charlie" in s.lyrics
```

- [ ] **Step 2: Run — expect FAIL**

Run: `uv run pytest tests/test_song_import.py -k inspired -v`
Expected: FAIL — `cannot import name 'build_inspired_script'`.

- [ ] **Step 3: Implement** — add to `pipeline/song_import.py`:

```python
from pipeline.song_lyrics import SongScript, generate_song_script

OVERLAP_THRESHOLD = 0.15  # regenerate if >15% of 4-grams echo the reference


def _theme_and_style(analysis: dict, instruction: str | None) -> tuple[str, str]:
    theme = analysis.get("one_line_theme") or "an original song"
    if instruction:
        theme = f"{theme}. Direction: {instruction}"
    bpm = round(analysis.get("bpm") or 0) or "moderate"
    style = ", ".join(
        x for x in (
            analysis.get("genre"),
            f"{bpm} BPM" if bpm else None,
            analysis.get("instrumentation"),
            analysis.get("mood"),
        ) if x
    )
    return theme, style


def build_inspired_script(*, llm, analysis: dict, instruction: str | None,
                          language: str, transcript: str = "") -> SongScript:
    """Generate an ORIGINAL song inspired by the analysed descriptors. The
    reference's words never reach the generator — only the derived theme +
    style do. If the result echoes the transcript too closely, regenerate once
    with a stronger originality nudge."""
    theme, style = _theme_and_style(analysis, instruction)

    def gen(extra: str = "") -> SongScript:
        return generate_song_script(
            llm=llm, theme=theme + extra, custom_lyrics=None,
            style_hint=style, language=language,
        )

    script = gen()
    if transcript and _ngram_overlap(script.lyrics, transcript) > OVERLAP_THRESHOLD:
        script = gen(". Write ENTIRELY ORIGINAL lyrics — do not echo any "
                     "existing song's words or lines.")
        if _ngram_overlap(script.lyrics, transcript) > OVERLAP_THRESHOLD:
            print("[song_import] WARN: generated lyrics still overlap the "
                  "reference; shipping but flagged for review")
    return script
```

- [ ] **Step 4: Run — expect PASS**

Run: `uv run pytest tests/test_song_import.py -k inspired -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add pipeline/song_import.py tests/test_song_import.py
git commit -m "feat(song): build_inspired_script — original lyrics + overlap guard"
```

---

## Task 6: API — `POST /songs/import`

**Files:** Modify `pipeline/api.py`; Test: `tests/test_api.py`

- [ ] **Step 1: Write the failing tests** — add to `tests/test_api.py` (reuse the module's existing authed `client`/`auth` fixtures and `_stub_song_llm`-style helpers; the worker spawn is already stubbed in this test module via `_SPAWN_FN` — match how the existing approve tests stub the spawn):

```python
def test_import_song_creates_analyzing_run(client, auth, monkeypatch):
    r = client.post("/songs/import",
                    json={"youtube_url": "https://www.youtube.com/watch?v=abc123",
                          "instruction": "make it Gulf dialect"},
                    headers=auth)
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "analyzing"
    assert body["run_id"]


def test_import_song_rejects_non_youtube_url(client, auth):
    r = client.post("/songs/import",
                    json={"youtube_url": "https://example.com/not-youtube"},
                    headers=auth)
    assert r.status_code == 422
```

(If the test module's spawn isn't already a no-op, monkeypatch `pipeline.api._SPAWN_FN` to a lambda returning a fake pid, mirroring the existing song-approve tests.)

- [ ] **Step 2: Run — expect FAIL**

Run: `uv run pytest tests/test_api.py -k import_song -v`
Expected: FAIL — 404 (no such route) / 405.

- [ ] **Step 3a: Add the request model**

In `pipeline/api.py`, near `CreateSongRequest` (~line 380), add:

```python
_YOUTUBE_RE = re.compile(
    r"^https?://(www\.)?(youtube\.com/watch\?[\w=&%-]*v=|youtu\.be/|"
    r"youtube\.com/shorts/)[\w-]{6,}", re.IGNORECASE)


class CreateSongImportRequest(BaseModel):
    youtube_url: str
    instruction: str | None = None
    language: str = "ar"
    video_mode: str = "static"
    vocal_gender: str | None = "m"
    suno_model: str | None = None

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
```

(`field_validator` and `re` are already imported.)

- [ ] **Step 3b: Add the endpoint**

Add near `create_song` (~line 2360):

```python
@app.post("/songs/import", status_code=201)
def import_song(req: CreateSongImportRequest, user: User = Depends(require_user)):
    """Start a YouTube-import song run. Writes a draft run and spawns the
    worker for the `analyzing` pre-stage (download + analyse + write an
    original script). No spend until the user approves the result."""
    from pipeline.config import load_config
    from pipeline.db import get_balance

    cfg = load_config(Path(os.environ.get(
        "FACELESS_CONFIG", str(REPO_ROOT / "config.yaml"))))
    credits_required = _song_credit_amount(req.video_mode, cfg)
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
    )
    args = ["--mode", "song", "--resume", str(run_dir)]
    pid = _SPAWN_FN(args, run_dir)
    _write_state(run_dir, pid=pid)
    return {"run_id": run_id, "status": "analyzing"}
```

- [ ] **Step 4: Run — expect PASS**

Run: `uv run pytest tests/test_api.py -k import_song -v`
Expected: PASS (2 tests). Then `uv run pytest tests/test_api.py -q` — no NEW failures (the pre-existing `test_approve_passes_auto_computed_max_spend` may still fail; ignore).

- [ ] **Step 5: Commit**

```bash
git add pipeline/api.py tests/test_api.py
git commit -m "feat(api): POST /songs/import — start a YouTube-import song run"
```

---

## Task 7: Worker — `analyzing` pre-stage in `run.py`

**Files:** Modify `run.py` (`_run_song_post_approve`); Test: `tests/test_run_song_mode.py`

- [ ] **Step 1: Write the failing test** — add to `tests/test_run_song_mode.py` (reuse the existing harness that drives `main_with_args(["--mode","song","--resume",dir])`; mirror `_setup_cinematic_run`'s state/fixture style):

```python
def test_import_analyze_stage_writes_script(tmp_path, monkeypatch, song_run_env):
    # song_run_env: existing helper that makes a run_dir + stubs KIE. Here we
    # set up an IMPORT-mode run (status analyzing, youtube_url, NO song.json).
    run_dir = song_run_env(status="analyzing",
                           youtube_url="https://youtu.be/abc123",
                           import_instruction="make it Gulf dialect")
    import pipeline.song_import as si
    from pipeline.song_lyrics import SongScript
    monkeypatch.setattr(si, "download_audio", lambda url, d: d / "reference.m4a")
    monkeypatch.setattr(si, "analyze_reference",
                        lambda audio, *, llm, language: (
                            {"bpm": 90, "genre": "pop", "mood": "sad",
                             "instrumentation": "oud", "language": "ar",
                             "one_line_theme": "loss", "section_structure": "V,C"},
                            "ref transcript"))
    monkeypatch.setattr(si, "build_inspired_script",
                        lambda **kw: SongScript(
                            title="ليل", lyrics="[Verse 1]\nx\n\n[Chorus]\ny\n",
                            style_prompt="pop, 90 BPM", cover_prompt="c",
                            language="ar", art_direction="moonlit",
                            scene_prompts=["a", "b"]))
    rc = run_mod.main_with_args(["--mode", "song", "--resume", str(run_dir)])
    import json
    assert rc == 0
    assert (run_dir / "song.json").exists()
    state = json.loads((run_dir / "api_state.json").read_text())
    assert state["status"] == "awaiting_approval"
```

- [ ] **Step 2: Run — expect FAIL**

Run: `uv run pytest tests/test_run_song_mode.py -k import_analyze -v`
Expected: FAIL — no song.json written / wrong status (analyze branch absent).

- [ ] **Step 3: Implement the pre-stage**

In `run.py`, add these imports near the other song imports inside `_run_song_post_approve` (alongside `song, song_cover, song_assemble, song_align, song_og`):

```python
from pipeline import song_import
from pipeline.api import _build_song_llm  # Anthropic→Groq fallback router
```
(`pipeline.api` does NOT import `run.py` — see the comment at its `_build_llm` — so this lazy, in-function import is safe and reuses the exact LLM router the manual song writer uses.)

At the **very top** of `_run_song_post_approve`'s `try:` body — BEFORE it reads `song.json` — add the analyze branch:

```python
        current_state = json.loads(state_path.read_text()) if state_path.exists() else {}
        # --- Import pre-stage: download + analyse a YouTube reference, then
        # write an ORIGINAL song.json and pause for approval. Runs only for
        # import-mode runs; exits before the normal generation path. ---
        if current_state.get("status") == "analyzing" and not (run_dir / "song.json").exists():
            write_state(status="analyzing")
            try:
                _llm = _build_song_llm()
                audio = song_import.download_audio(current_state["youtube_url"], run_dir)
                analysis, transcript = song_import.analyze_reference(
                    audio, llm=_llm, language=current_state.get("language", "ar"))
                script = song_import.build_inspired_script(
                    llm=_llm, analysis=analysis,
                    instruction=current_state.get("import_instruction"),
                    language=current_state.get("language", "ar"),
                    transcript=transcript,
                )
            except song_import.ImportFetchError as e:
                write_state(status="failed", failure_stage="analyzing", last_error=str(e))
                return 1
            # Persist descriptors only (never the transcript) for debugging.
            (run_dir / "analysis.json").write_text(
                json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
            (run_dir / "song.json").write_text(json.dumps({
                "title": script.title, "lyrics": script.lyrics,
                "style_prompt": script.style_prompt, "cover_prompt": script.cover_prompt,
                "language": script.language, "art_direction": script.art_direction,
                "scene_prompts": script.scene_prompts,
                "vocal_gender": current_state.get("vocal_gender"),
                "persona_id": None,
                "suno_model": current_state.get("suno_model"),
                "video_mode": current_state.get("video_mode", "static"),
            }, ensure_ascii=False, indent=2), encoding="utf-8")
            (run_dir / "lyrics.txt").write_text(script.lyrics, encoding="utf-8")
            write_state(status="awaiting_approval", title=script.title)
            return 0
```

NOTES for the implementer:
- `_build_song_llm` (imported from `pipeline.api` in Step 3) is the existing Anthropic→Groq→Gemini router with the Fallback wrapper — the same one the manual song writer uses. Build it once and pass the instance to both `analyze_reference` and `build_inspired_script` (don't build twice).
- `state_path`, `run_dir`, `write_state`, `json` are already in scope in `_run_song_post_approve` (verify by reading the function). The per-run state file is `api_state.json` (per the existing code).
- The existing post-approve generation code (Suno → cover → assemble) is unchanged and runs on the *second* worker spawn (after `approve_song`), when `song.json` already exists and status is `generating_song`.

- [ ] **Step 4: Run — expect PASS**

Run: `uv run pytest tests/test_run_song_mode.py -v`
Expected: PASS — the new import test passes AND the existing song-mode + cinematic tests still pass.

- [ ] **Step 5: Commit**

```bash
git add run.py tests/test_run_song_mode.py
git commit -m "feat(song): worker analyze pre-stage for YouTube import"
```

---

## Task 8: Flutter — "Import from YouTube" UI

**Files:** Modify `lib/api/client.dart`, `lib/screens/new_song_screen.dart`; Verify: `flutter analyze`

- [ ] **Step 1: Add the client call**

In `lib/api/client.dart`, add next to `createSong`:

```dart
  Future<String> importSong({
    required String youtubeUrl,
    String? instruction,
    String language = 'ar',
    String videoMode = 'static',
    String vocalGender = 'm',
  }) async {
    final body = <String, dynamic>{
      'youtube_url': youtubeUrl,
      if (instruction != null && instruction.isNotEmpty) 'instruction': instruction,
      'language': language,
      'video_mode': videoMode,
      'vocal_gender': vocalGender,
    };
    final r = await _http.post(
      await _uri('/songs/import'),
      headers: {...await _headers(), 'Content-Type': 'application/json'},
      body: jsonEncode(body),
    );
    return _parse(r, (j) => (j as Map<String, dynamic>)['run_id'] as String);
  }
```

- [ ] **Step 2: Add the import mode to `new_song_screen.dart`**

READ `new_song_screen.dart` first. Add a mode toggle at the top of the form — "Write a theme" (existing) vs "Import from YouTube" — via a `SegmentedButton<String>` bound to a new `String _createMode = 'theme'` state field. When `_createMode == 'youtube'`, show a YouTube URL `TextField` (bound to `_youtubeController`) plus the existing "your touch" instruction field and the static/cinematic toggle; hide the theme field. On submit in youtube mode, call `client.importSong(youtubeUrl: _youtubeController.text, instruction: <instruction field>, videoMode: _videoMode, language: _language)` instead of `createSong(...)`, then navigate to the run the same way the theme path does. Match the screen's existing widget style + validation (show an error if the URL is empty).

- [ ] **Step 3: Verify analyzer**

Run: `flutter analyze` and compare to the baseline (`git stash` → analyze → pop → analyze). Your change must add ZERO new errors in `client.dart` / `new_song_screen.dart`.

- [ ] **Step 4: Commit**

```bash
git add lib/api/client.dart lib/screens/new_song_screen.dart
git commit -m "feat(app): Import from YouTube mode on the new-song screen"
```

---

## Task 9: Full suite + manual smoke + PR

**Files:** none (verification)

- [ ] **Step 1: Full Python suite**

Run: `uv run pytest -q`
Expected: green except the known pre-existing failures (missing `ELEVENLABS_API_KEY` shorts smoke, `test_approve_passes_auto_computed_max_spend`, mp4_faststart env). No NEW failures.

- [ ] **Step 2: Manual smoke (optional; needs network + real keys)**

```bash
source .env
# create an import run via the API, then watch the worker log
curl -s -X POST "$FACELESS_API_URL/songs/import" -H "Authorization: Bearer $FACELESS_API_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"youtube_url":"https://youtu.be/<id>","instruction":"make it Gulf dialect"}'
```
Expected: a run that goes `analyzing` → `awaiting_approval` with an original `song.json`. (May fail at download from a datacenter IP — that's the documented yt-dlp risk; locally it should work.)

- [ ] **Step 3: Push + PR**

```bash
git push -u origin feat/youtube-song-import
gh pr create --fill
```

---

## Notes for the implementer

- **TDD throughout** — test first, watch it fail, implement, watch it pass, commit.
- **Originality is structural:** the generator (`generate_song_script`) only ever receives the derived theme + style descriptors — never the reference's words. The transcript exists only to (a) let `analyze_reference`'s LLM distill a one-line theme and (b) power the overlap guard, then it's discarded. Never persist or display it.
- **Never hit real services in tests** — yt-dlp, Whisper, librosa, and the LLM are all monkeypatched.
- **yt-dlp from prod may be blocked** (datacenter IPs) — the worker fails gracefully to `failed`/`analyzing`-stage with an actionable message; no spend occurs pre-approval.
