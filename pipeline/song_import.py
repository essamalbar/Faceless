"""YouTube song import: fetch a reference track and turn it into an ORIGINAL
inspired song script.

The reference is used for inspiration only — tempo, genre, mood, theme and
section structure. The verbatim transcript is transient and is never stored,
displayed, or used to reproduce/paraphrase the source. See
docs/superpowers/specs/2026-06-19-youtube-song-import-design.md.
"""
from __future__ import annotations

import json
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
