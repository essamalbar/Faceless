"""YouTube song import: fetch a reference track and turn it into an ORIGINAL
inspired song script.

The reference is used for inspiration only — tempo, genre, mood, theme and
section structure. The verbatim transcript is transient and is never stored,
displayed, or used to reproduce/paraphrase the source. See
docs/superpowers/specs/2026-06-19-youtube-song-import-design.md.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

from pipeline.song_lyrics import SongScript, generate_song_script


class ImportFetchError(RuntimeError):
    """Raised when the reference audio can't be fetched (private, region-
    locked, age-restricted, network, or a datacenter-IP block)."""


def _ytdlp_opts(out_template: str, *, cookiefile: str | None = None) -> dict:
    """Build the yt-dlp options dict. Adds a residential proxy (YTDLP_PROXY)
    and/or a cookies file when configured — YouTube blocks datacenter IPs and
    increasingly requires session cookies, so without these the download fails
    from Cloud Run. Pure + testable (no network)."""
    opts: dict = {
        "format": "bestaudio/best",
        "outtmpl": out_template,
        "quiet": True,
        "noplaylist": True,
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "m4a"}
        ],
    }
    proxy = os.environ.get("YTDLP_PROXY")
    if proxy:
        opts["proxy"] = proxy
    if cookiefile:
        opts["cookiefile"] = cookiefile
    return opts


def _ytdlp_download(url: str, out_template: str) -> str:
    """Download bestaudio to out_template via yt-dlp. Isolated so tests can
    monkeypatch it without invoking the network/binary.

    Honors YTDLP_PROXY (a residential proxy URL, e.g. http://user:pass@host:port
    or socks5://...) and YTDLP_COOKIES (the body of a Netscape cookies.txt from
    a logged-in YouTube session). The cookies body is written to a temp file for
    yt-dlp's cookiefile and removed afterwards."""
    import yt_dlp
    cookiefile = None
    cookies_body = os.environ.get("YTDLP_COOKIES")
    tmp = None
    if cookies_body:
        tmp = tempfile.NamedTemporaryFile(
            "w", suffix=".txt", delete=False, encoding="utf-8")
        tmp.write(cookies_body)
        tmp.close()
        cookiefile = tmp.name
    try:
        opts = _ytdlp_opts(out_template, cookiefile=cookiefile)
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
    finally:
        if tmp is not None:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass
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


def _llm_descriptors(llm, user_msg: str, *, bpm: float, language: str) -> dict:
    """Run the analysis LLM call and parse it into the descriptors dict.
    Shared by the audio path (analyze_reference) and the metadata path
    (analyze_from_metadata)."""
    raw = llm.complete(user_msg, system=_ANALYZE_SYSTEM).strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?|\n?```$", "", raw, flags=re.MULTILINE).strip()
    parsed = json.loads(raw, strict=False)
    return {
        "bpm": bpm,
        "genre": str(parsed.get("genre", "")),
        "mood": str(parsed.get("mood", "")),
        "instrumentation": str(parsed.get("instrumentation", "")),
        "language": str(parsed.get("language", language)),
        "one_line_theme": parsed.get("one_line_theme"),
        "section_structure": str(parsed.get("section_structure", "")),
    }


def analyze_reference(audio: Path, *, llm, language: str) -> tuple[dict, str]:
    """Audio path: detect tempo + transcribe (internal), distill descriptors.
    Returns (descriptors, transcript) — transcript for the transient overlap
    check only; it must NOT be persisted."""
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

    return _llm_descriptors(llm, user_msg, bpm=bpm, language=language), transcript


# --- Free metadata fallback: YouTube Data API (no audio download) -----------
# Used when the audio download is blocked (the common Cloud Run case). Reads
# only the public title + description and produces an original song from them —
# never the source lyrics, so it's the safest path for originality too.

_YT_ID_RE = re.compile(r"(?:[?&]v=|youtu\.be/|/shorts/)([\w-]{6,})")
_YT_API_URL = "https://www.googleapis.com/youtube/v3/videos"


def _yt_video_id(url: str) -> str | None:
    m = _YT_ID_RE.search(url)
    return m.group(1) if m else None


def _youtube_api_metadata(video_id: str, api_key: str) -> dict:
    """Call YouTube Data API videos.list(snippet). Isolated for tests."""
    import requests
    r = requests.get(
        _YT_API_URL,
        params={"part": "snippet", "id": video_id, "key": api_key},
        timeout=30,
    )
    if r.status_code >= 400:
        raise ImportFetchError(
            f"YouTube Data API error {r.status_code}: {r.text[:200]}")
    items = r.json().get("items") or []
    if not items:
        raise ImportFetchError("video not found via YouTube Data API")
    snippet = items[0].get("snippet", {})
    return {"title": snippet.get("title", ""),
            "description": snippet.get("description", "")}


def fetch_youtube_metadata(url: str) -> dict:
    """Free, ToS-clean metadata (title + description) via the YouTube Data API.
    Requires YOUTUBE_API_KEY. Raises ImportFetchError when unavailable."""
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        raise ImportFetchError("metadata fallback unavailable (set YOUTUBE_API_KEY)")
    video_id = _yt_video_id(url)
    if not video_id:
        raise ImportFetchError("couldn't read a YouTube video id from the link")
    return _youtube_api_metadata(video_id, api_key)


def analyze_from_metadata(meta: dict, *, llm, language: str) -> tuple[dict, str]:
    """Metadata path: distill descriptors from the video title + description
    (no audio). Returns (descriptors, "") — no transcript, so the overlap guard
    is a no-op and no source lyrics are ever involved."""
    user_msg = (
        f"YouTube title: {meta.get('title', '')}\n"
        f"Description (context only):\n{(meta.get('description') or '')[:2000]}\n"
        f"Language hint: {language}\n"
        "(No audio available — infer genre/mood/theme from the title + description.)"
    )
    return _llm_descriptors(llm, user_msg, bpm=0.0, language=language), ""


def analyze_youtube(url: str, out_dir: Path, *, llm, language: str) -> tuple[dict, str]:
    """Audio-first, metadata-fallback. Tries to download + analyse the audio
    (works locally / through YTDLP_PROXY); if the download is blocked (the
    common Cloud Run case), falls back to free YouTube Data API metadata."""
    try:
        audio = download_audio(url, out_dir)
        return analyze_reference(audio, llm=llm, language=language)
    except ImportFetchError as e:
        print(f"[song_import] audio fetch failed ({e}); trying metadata fallback")
        meta = fetch_youtube_metadata(url)  # raises ImportFetchError if no key
        return analyze_from_metadata(meta, llm=llm, language=language)


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
