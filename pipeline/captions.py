"""Stage 7: caption generation. SRT (default) + optional .ass for FFmpeg burn-in."""
from __future__ import annotations

from pathlib import Path

from pipeline.types import WordTiming

SENTENCE_END_CHARS = {".", "؟", "!", "…"}


def _is_sentence_end(word: str) -> bool:
    return bool(word) and word.strip()[-1:] in SENTENCE_END_CHARS


def chunk_into_caption_lines(
    timings: list[WordTiming],
    max_words: int = 10,
    max_duration_ms: int = 4000,
) -> list[dict]:
    """Group word timings into caption lines.

    Rules:
    - <= max_words words per line
    - <= max_duration_ms duration per line
    - Break at sentence-end words when possible (preferred boundary)
    """
    if not timings:
        return []
    lines: list[dict] = []
    current: list[WordTiming] = []
    current_start = timings[0].offset_ms
    for wt in timings:
        if not current:
            current_start = wt.offset_ms
        current.append(wt)
        elapsed = (wt.offset_ms + wt.duration_ms) - current_start
        too_long = elapsed >= max_duration_ms
        too_many = len(current) >= max_words
        sentence_break = _is_sentence_end(wt.word)

        should_close = (sentence_break and len(current) >= 1) or too_long or too_many
        if should_close:
            lines.append({
                "start_ms": current_start,
                "end_ms": wt.offset_ms + wt.duration_ms,
                "words": list(current),
                "text": " ".join(w.word for w in current).strip(),
            })
            current = []
    if current:
        last = current[-1]
        lines.append({
            "start_ms": current[0].offset_ms,
            "end_ms": last.offset_ms + last.duration_ms,
            "words": list(current),
            "text": " ".join(w.word for w in current).strip(),
        })
    return lines


def _ms_to_srt_time(ms: int) -> str:
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def format_srt(lines: list[dict]) -> str:
    out: list[str] = []
    for i, line in enumerate(lines, start=1):
        out.append(str(i))
        out.append(f"{_ms_to_srt_time(line['start_ms'])} --> {_ms_to_srt_time(line['end_ms'])}")
        out.append(line["text"])
        out.append("")  # blank line separator
    return "\n".join(out)


def _ms_to_ass_time(ms: int) -> str:
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    cs = ms // 10  # centiseconds
    return f"{h:01d}:{m:02d}:{s:02d}.{cs:02d}"


def format_ass(lines: list[dict], font: str, font_size: int) -> str:
    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "PlayResX: 1920\n"
        "PlayResY: 1080\n"
        "WrapStyle: 0\n"
        "ScaledBorderAndShadow: yes\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, "
        "BackColour, Bold, Italic, BorderStyle, Outline, Shadow, Alignment, "
        "MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,{font},{font_size},&H00FFFFFF,&H00000000,"
        f"&H80000000,1,0,3,4,0,2,40,40,180,1\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    events: list[str] = []
    for line in lines:
        events.append(
            f"Dialogue: 0,{_ms_to_ass_time(line['start_ms'])},"
            f"{_ms_to_ass_time(line['end_ms'])},Default,,0,0,0,,{line['text']}"
        )
    return header + "\n".join(events) + "\n"


def generate_captions(
    timings: list[WordTiming],
    srt_path: Path,
    ass_path: Path | None,
    font: str,
    font_size: int,
) -> None:
    """Resumable: skips if srt_path already exists. .ass written if path given."""
    if srt_path.exists():
        return
    lines = chunk_into_caption_lines(timings)
    srt_path.parent.mkdir(parents=True, exist_ok=True)
    srt_path.write_text(format_srt(lines), encoding="utf-8")
    if ass_path is not None:
        ass_path.write_text(format_ass(lines, font=font, font_size=font_size), encoding="utf-8")
