"""Force-align lyric lines to the actual song audio so the share-page
karaoke and burned-in MP4 captions both stay in sync.

The previous share-page implementation divided song duration evenly
across stanza count, which drifted noticeably on songs with tempo
changes. This module reuses pipeline.align (the same Whisper-as-stopwatch
approach used for horror narration) but collapses the result to
LINE granularity, per the spec decision in
docs/superpowers/specs/2026-06-11-song-karaoke-burn-in-design.md.

Whisper's Arabic *transcription* is never displayed — we only consume
its word-boundary timestamps and pair them with the user-supplied
lyric words by index. See pipeline/align.py for the rationale.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from pipeline.align import _audio_duration_s, align_arabic

_SECTION_TAG_RE = re.compile(r"^\[([^\]]+)\]\s*$")


def align_song_lyrics(*, song_mp3: Path, lyrics: str, out_json: Path) -> dict:
    """Produce a lyrics.json with per-line audio timings.

    Output shape:
        {
          "audio_duration": float,                # seconds
          "lines": [
            {"kind": "section", "text": "Verse 1", "start": 12.3, "end": 12.3, "stanza": 1},
            {"kind": "line", "text": "في ليل بعيد", "start": 12.3, "end": 17.9, "stanza": 1},
            ...
          ]
        }

    Section headers (`[Verse 1]`) get start = the next sung line's start
    so the share-page scroll can land on them at the right moment.

    Idempotent: if out_json already exists, returns its parsed contents
    and skips Whisper. Same resumable pattern as the rest of the pipeline.
    """
    if out_json.exists():
        return json.loads(out_json.read_text(encoding="utf-8"))

    parsed = _parse_lyrics(lyrics)
    sung_words = " ".join(item["text"] for item in parsed if item["kind"] == "line")

    audio_dur = _audio_duration_s(song_mp3)

    if not sung_words.strip():
        result = {"audio_duration": audio_dur, "lines": parsed}
        _write_atomic(out_json, result)
        return result

    word_timings = align_arabic(song_mp3, sung_words)

    out_lines: list[dict] = []
    word_idx = 0
    for item in parsed:
        if item["kind"] == "section":
            out_lines.append({
                "kind": "section",
                "text": item["text"],
                "stanza": item["stanza"],
                "start": None,
                "end": None,
            })
            continue
        n = len(item["text"].split())
        if n == 0 or word_idx >= len(word_timings):
            last_end = (
                (word_timings[-1].offset_ms + word_timings[-1].duration_ms) / 1000.0
                if word_timings else 0.0
            )
            out_lines.append({
                "kind": "line",
                "text": item["text"],
                "stanza": item["stanza"],
                "start": last_end,
                "end": min(last_end + 2.0, audio_dur),
            })
            continue
        taken = word_timings[word_idx : word_idx + n]
        start = taken[0].offset_ms / 1000.0
        end = (taken[-1].offset_ms + taken[-1].duration_ms) / 1000.0
        out_lines.append({
            "kind": "line",
            "text": item["text"],
            "stanza": item["stanza"],
            "start": start,
            "end": end,
        })
        word_idx += n

    # Second pass: section headers inherit the next sung line's start so
    # they highlight just before that line begins.
    next_start: float | None = None
    for entry in reversed(out_lines):
        if entry["kind"] == "line":
            next_start = entry["start"]
        elif entry["kind"] == "section":
            anchor = next_start if next_start is not None else 0.0
            entry["start"] = anchor
            entry["end"] = anchor

    result = {"audio_duration": audio_dur, "lines": out_lines}
    _write_atomic(out_json, result)
    return result


def _parse_lyrics(lyrics: str) -> list[dict]:
    """Parse raw lyric text into a structured stream.

    Blank lines are dropped from the output but DO bump the stanza
    counter when the next sung line appears, matching the share-page
    rendering (pipeline/api.py:shared_song_page)."""
    out: list[dict] = []
    stanza = 0
    in_stanza = False
    for raw in lyrics.split("\n"):
        line = raw.strip()
        if not line:
            in_stanza = False
            continue
        m = _SECTION_TAG_RE.match(line)
        if m:
            stanza += 1
            out.append({"kind": "section", "text": m.group(1), "stanza": stanza})
            in_stanza = True
        else:
            if not in_stanza:
                stanza += 1
                in_stanza = True
            out.append({"kind": "line", "text": line, "stanza": stanza})
    return out


def _write_atomic(path: Path, data: dict) -> None:
    """Write JSON via .tmp + replace so a crash mid-write doesn't leave a
    half-written file that future runs will keep loading."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
