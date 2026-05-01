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


def chunk_into_tiktok_lines(
    timings: list[WordTiming],
    max_words: int = 3,
    max_duration_ms: int = 2000,
) -> list[dict]:
    """Tighter chunker for TikTok / Shorts captions: ~3 words on screen at a time."""
    return chunk_into_caption_lines(
        timings, max_words=max_words, max_duration_ms=max_duration_ms,
    )


def format_ass_tiktok_karaoke(
    lines: list[dict],
    font: str,
    font_size: int,
    play_res_x: int = 1080,
    play_res_y: int = 1920,
) -> str:
    """Vertical TikTok-style karaoke .ass.

    Each line renders for its full span; individual words light up via {\\k<cs>}
    karaoke tags. Style is centered horizontally, slightly above middle vertically
    (Alignment=5 = middle-center; MarginV nudges toward the upper third).
    Bold white text, thick black outline + shadow — readable on any background.
    """
    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {play_res_x}\n"
        f"PlayResY: {play_res_y}\n"
        "WrapStyle: 0\n"
        "ScaledBorderAndShadow: yes\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, "
        "Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
        "MarginL, MarginR, MarginV, Encoding\n"
        # @sunstoriz reference uses bright YELLOW Arabic captions, centered,
        # ~70% down the frame. ASS color format is &HBBGGRR (BGR + alpha).
        # PrimaryColour:  &H0000FFFF  = pure yellow (FF FF 00 in RGB).
        # SecondaryColour: same yellow (no karaoke color shift — read-on-read).
        # OutlineColour: &H00000000   = black outline.
        # BackColour: &H80000000      = 50% black shadow for legibility.
        # Alignment 2 = bottom-center; MarginV 600 = ~30% from bottom (560/1920).
        # Outline 8, Shadow 4 — chunky for vertical readability over busy 3D scenes.
        f"Style: Default,{font},{font_size},"
        "&H0000FFFF,&H0000FFFF,&H00000000,&H80000000,"
        "1,0,0,0,100,100,0,0,1,8,4,2,60,60,560,1\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )

    events: list[str] = []
    for line in lines:
        words: list[WordTiming] = list(line["words"])
        if not words:
            continue
        # Build the karaoke text: {\k<cs>}<word> per word.
        parts: list[str] = []
        for w in words:
            cs = max(int(round(w.duration_ms / 10)), 1)  # min 1cs to avoid zero
            parts.append(f"{{\\k{cs}}}{w.word}")
        text = " ".join(parts)
        events.append(
            f"Dialogue: 0,{_ms_to_ass_time(line['start_ms'])},"
            f"{_ms_to_ass_time(line['end_ms'])},Default,,0,0,0,,{text}"
        )
    return header + "\n".join(events) + "\n"


def generate_captions(
    timings: list[WordTiming],
    srt_path: Path,
    ass_path: Path | None,
    font: str,
    font_size: int,
    style: str = "default",
    play_res_x: int = 1920,
    play_res_y: int = 1080,
) -> None:
    """Resumable: skips if srt_path already exists. .ass written if path given.

    style:
      - "default" — bottom subtitle bar, ~6-10 words/line, no per-word animation.
      - "tiktok"  — vertical karaoke, ~3 words/line, word-by-word reveal,
                    centered slightly above middle. Uses (play_res_x, play_res_y).
    """
    if srt_path.exists():
        return
    if style == "tiktok":
        lines = chunk_into_tiktok_lines(timings)
    else:
        lines = chunk_into_caption_lines(timings)
    srt_path.parent.mkdir(parents=True, exist_ok=True)
    srt_path.write_text(format_srt(lines), encoding="utf-8")
    if ass_path is not None:
        if style == "tiktok":
            ass_path.write_text(
                format_ass_tiktok_karaoke(
                    lines, font=font, font_size=font_size,
                    play_res_x=play_res_x, play_res_y=play_res_y,
                ),
                encoding="utf-8",
            )
        else:
            ass_path.write_text(
                format_ass(lines, font=font, font_size=font_size),
                encoding="utf-8",
            )
