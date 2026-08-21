"""Build an ASS subtitle file with kinetic lyrics: karaoke (\\k) on verses,
hook-word emphasis on chorus lines, line-snap fallback on low-confidence (or
word-timing-less) lines. Styled per VisualTemplate. Burned by song_animate
via libass `ass=`.

Branch order (deliberately confidence-first, not section-first): a line with
missing `words[]` or `align_confidence` below `min_confidence` ALWAYS falls
back to line-snap, even if it belongs to the chorus — per the design spec's
"Error handling / fallbacks" (the confidence gate applies uniformly). Only
once a line clears that gate do we split on section: chorus stanzas get
hook-word emphasis, everything else sung gets word-by-word karaoke.
"""
from __future__ import annotations

import re
from pathlib import Path

from pipeline.song_ass_util import _ass_escape, _format_ass_time
from pipeline.song_lyrics import _SECTION_TAG_RE
from pipeline.song_visual_style import VisualTemplate

# Short stopwords excluded from hook-word selection (Arabic + English).
_STOP = {"يا", "في", "من", "على", "the", "a", "and", "of", "to", "في"}

# Style-suffix strip so a font FILENAME (e.g. "Amiri-Regular.ttf") resolves
# to the actual font-family NAME libass/fontconfig matches by ("Amiri").
# ASS's Fontname field is a family name, not a path — the existing
# song_assemble._write_ass_subtitles header follows the same convention
# (it hardcodes the family name "Scheherazade", not a file path).
_FONT_STYLE_SUFFIX_RE = re.compile(
    r"-(Regular|Bold|Italic|BoldItalic|Light|Medium|SemiBold|ExtraBold)$"
)


def pick_hook_word(text: str) -> str:
    """Pick the salient content word for chorus hook-word emphasis: the
    longest word that isn't a short stopword. Falls back to the first word
    if every word is a stopword (or the text is empty)."""
    words = [w for w in re.findall(r"[^\s]+", text) if w not in _STOP]
    if not words:
        return text.split()[0] if text.split() else text
    return max(words, key=len)


def _font_family(font_file: str) -> str:
    stem = Path(font_file).stem
    return _FONT_STYLE_SUFFIX_RE.sub("", stem) or stem


def _chorus_stanzas(lines: list[dict]) -> set[int]:
    """Stanza numbers whose section header is a Chorus tag. Reuses
    pipeline.song_lyrics._SECTION_TAG_RE (which expects bracketed tags like
    "[Chorus]") by re-wrapping the already-unbracketed `text` field that
    lyrics_timing stores for `kind: "section"` items."""
    out: set[int] = set()
    for it in lines:
        if it.get("kind") != "section":
            continue
        m = _SECTION_TAG_RE.search(f"[{it.get('text', '')}]")
        if m and m.group(1).lower() == "chorus":
            stanza = it.get("stanza")
            if stanza is not None:
                out.add(stanza)
    return out


def _karaoke_text(words: list[dict]) -> str:
    """One `{\\kNN}` tag per word, NN in centiseconds (ASS's \\k unit).
    Pre-sung vs sung colors come from the Kinetic style's Secondary/Primary
    colours (see `_ass_header`) — no per-word color tag needed here.

    ASS `\\k` durations are CUMULATIVE from the Dialogue event's start, not
    independent per-word spans. Whisper word timings are frequently
    non-contiguous (gaps at pauses/breaths/instrumental hits), so using each
    word's own `end-start` as its `\\k` value drops those gaps and makes the
    highlight run progressively EARLY within the line. Instead, derive each
    word's `\\k` from the gap to the NEXT word's start (so the gap gets
    absorbed into the preceding word's highlight and each highlight still
    STARTS at the word's real start time); the last word falls back to its
    own duration since there's no next start to measure to."""
    parts = []
    for i, w in enumerate(words):
        if i + 1 < len(words):
            cs = round((words[i + 1]["start"] - w["start"]) * 100)
        else:
            cs = round((w["end"] - w["start"]) * 100)
        cs = max(1, cs)
        parts.append(f"{{\\k{cs}}}{_ass_escape(w['text'])} ")
    return "".join(parts).rstrip()


def _hook_line_text(text: str, template: VisualTemplate) -> str:
    """Chorus rendering: the picked hook word is scaled up and pulses via a
    \\t(...) transform in the chorus hook color; every other word is plain."""
    hook = pick_hook_word(text)
    return " ".join(
        (f"{{\\fscx160\\fscy160\\1c{template.lyric.hook_color}"
         f"\\t(0,300,\\fscx185\\fscy185)}}{_ass_escape(w)}{{\\r}}"
         if w == hook else _ass_escape(w))
        for w in text.split()
    )


def _snap_line_text(text: str) -> str:
    """Line-snap fallback: whole line scales+fades in at line start rather
    than sweeping word-by-word (used when we don't trust the word-level
    timing enough for karaoke)."""
    return f"{{\\fad(120,120)\\t(0,180,\\fscx112\\fscy112)}}{_ass_escape(text)}"


def build_kinetic_ass(*, lyrics_timing: dict, template: VisualTemplate,
                      out_path: Path, min_confidence: float = 0.6) -> Path:
    lines = lyrics_timing.get("lines", [])
    chorus_stanzas = _chorus_stanzas(lines)
    events: list[str] = []
    for it in lines:
        if it.get("kind") != "line":
            continue
        start = float(it.get("start") or 0.0)
        end = float(it.get("end") or 0.0)
        s, e = _format_ass_time(start), _format_ass_time(end)
        conf = float(it.get("align_confidence", 0.0))
        words = it.get("words") or []
        text = it.get("text", "")

        if not words or conf < min_confidence:
            # Line-snap fallback — no reliable word timing to karaoke with,
            # regardless of section (chorus or verse).
            rendered = _snap_line_text(text)
        elif it.get("stanza") in chorus_stanzas:
            rendered = _hook_line_text(text, template)
        else:
            rendered = _karaoke_text(words)

        events.append(f"Dialogue: 0,{s},{e},Kinetic,,0,0,0,,{rendered}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(_ass_header(template) + "\n".join(events) + "\n",
                        encoding="utf-8")
    return out_path


def _ass_header(t: VisualTemplate) -> str:
    """[Script Info] + one [V4+ Styles] line named "Kinetic", modeled on
    song_assemble._write_ass_subtitles's header (same Format lines, same
    Encoding=178 Arabic-shaper hint, same bottom alignment) but sized for
    the 1080x1920 vertical animated render and carrying the per-genre
    VisualTemplate's lyric styling instead of the static caption defaults.

    Karaoke (\\k) color convention: PrimaryColour is the "sung" color
    (karaoke_fill) and SecondaryColour is the "not yet sung" color
    (karaoke_base) — the pre-sung portion of a \\k run displays in
    SecondaryColour until its timer elapses, then switches to
    PrimaryColour.
    """
    lyric = t.lyric
    fontsize = 84  # bigger canvas (1920 tall) + kinetic type needs to read as the star, not a caption
    margin_v = 220  # clear of the share-page progress bar / OS chrome on the taller vertical frame
    return (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "PlayResX: 1080\n"
        "PlayResY: 1920\n"
        "WrapStyle: 0\n"
        "ScaledBorderAndShadow: yes\n"
        "YCbCr Matrix: TV.709\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Kinetic,{_font_family(lyric.font_file)},{fontsize},"
        f"{lyric.karaoke_fill},{lyric.karaoke_base},{lyric.outline},"
        f"&H80000000&,-1,0,0,0,100,100,0,0,1,{lyric.outline_w},2,2,"
        f"60,60,{margin_v},178\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, "
        "MarginV, Effect, Text\n"
    )
