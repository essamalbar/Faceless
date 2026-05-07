"""Captions generator tests."""
from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.captions import (
    SENTENCE_END_CHARS,
    chunk_into_caption_lines,
    format_srt,
    generate_captions,
)
from pipeline.types import WordTiming


def _wt(word, off, dur=400):
    return WordTiming(word=word, offset_ms=off, duration_ms=dur)


def test_chunk_respects_max_words():
    timings = [_wt(f"w{i}", i * 200, 200) for i in range(20)]
    lines = chunk_into_caption_lines(timings, max_words=10, max_duration_ms=4000)
    for line in lines:
        assert len(line["words"]) <= 10


def test_chunk_respects_max_duration():
    timings = [_wt(f"w{i}", i * 1000, 1000) for i in range(10)]  # each word 1s
    lines = chunk_into_caption_lines(timings, max_words=10, max_duration_ms=4000)
    for line in lines:
        assert (line["end_ms"] - line["start_ms"]) <= 4500  # small tolerance


def test_chunk_breaks_at_sentence_end():
    timings = [_wt("w1", 0), _wt("w2.", 500), _wt("w3", 1000), _wt("w4", 1500)]
    lines = chunk_into_caption_lines(timings, max_words=10, max_duration_ms=10_000)
    assert len(lines) == 2
    assert lines[0]["words"][-1].word.endswith(".")


def test_format_srt_indexing():
    lines = [
        {"start_ms": 0, "end_ms": 1500, "text": "السطر الأول"},
        {"start_ms": 1500, "end_ms": 3000, "text": "السطر الثاني"},
    ]
    srt = format_srt(lines)
    assert srt.startswith("1\n")
    assert "السطر الأول" in srt
    assert "00:00:00,000 --> 00:00:01,500" in srt
    assert "\n2\n" in srt
    assert "00:00:01,500 --> 00:00:03,000" in srt


def test_generate_captions_writes_srt(tmp_run_dir: Path):
    timings = [_wt("كلمة", 0), _wt("ثانية.", 500), _wt("ثالثة", 1000)]
    srt_path = tmp_run_dir / "captions.ar.srt"
    generate_captions(
        timings=timings, srt_path=srt_path, ass_path=None,
        font="Cairo-Bold", font_size=60,
    )
    assert srt_path.exists()
    text = srt_path.read_text(encoding="utf-8")
    assert "كلمة" in text


def test_generate_captions_writes_ass_when_requested(tmp_run_dir: Path):
    timings = [_wt("كلمة", 0), _wt("ثانية.", 500)]
    srt_path = tmp_run_dir / "captions.ar.srt"
    ass_path = tmp_run_dir / "captions.ar.ass"
    generate_captions(
        timings=timings, srt_path=srt_path, ass_path=ass_path,
        font="Cairo-Bold", font_size=60,
    )
    assert ass_path.exists()
    text = ass_path.read_text(encoding="utf-8")
    assert "[Script Info]" in text
    assert "Cairo-Bold" in text


def test_generate_captions_skips_when_srt_exists(tmp_run_dir: Path):
    timings = [_wt("ك", 0)]
    srt_path = tmp_run_dir / "captions.ar.srt"
    srt_path.write_text("preexisting", encoding="utf-8")
    generate_captions(
        timings=timings, srt_path=srt_path, ass_path=None,
        font="Cairo-Bold", font_size=60,
    )
    assert srt_path.read_text() == "preexisting"


# ============================================================================
# TikTok-style karaoke captions
# ============================================================================

def test_chunk_tiktok_max_3_words_per_line():
    from pipeline.captions import chunk_into_tiktok_lines
    timings = [WordTiming(word=f"w{i}", offset_ms=i * 200, duration_ms=200) for i in range(10)]
    lines = chunk_into_tiktok_lines(timings)
    for line in lines:
        assert len(line["words"]) <= 3


def test_format_ass_tiktok_no_karaoke_tags_arabic_rtl_safe():
    """Per-word `{\\k}` tags broke Arabic RTL: each tag is a separate text
    run, libass+FriBidi treated runs as left-to-right, and word ORDER
    visually reversed. The TikTok formatter now emits one Arabic line per
    Dialogue event with no inline tags so bidi handles it as one run."""
    from pipeline.captions import chunk_into_tiktok_lines, format_ass_tiktok_karaoke
    timings = [
        WordTiming(word="كنتُ", offset_ms=0, duration_ms=400),
        WordTiming(word="وحيداً", offset_ms=400, duration_ms=500),
        WordTiming(word="هناك.", offset_ms=900, duration_ms=600),
    ]
    lines = chunk_into_tiktok_lines(timings)
    ass = format_ass_tiktok_karaoke(lines, font="Cairo-Black", font_size=90,
                                     play_res_x=1080, play_res_y=1920)
    # Vertical play resolution
    assert "PlayResX: 1080" in ass
    assert "PlayResY: 1920" in ass
    # Regression guard: NO karaoke tags anywhere in the dialogue text
    assert "\\k" not in ass
    # Alignment 5 (middle-center) is in the Style line
    assert "Cairo-Black" in ass
    # Words preserved verbatim, in script order, as one Arabic run
    assert "كنتُ" in ass
    assert "وحيداً" in ass
    assert "هناك." in ass


def test_generate_captions_tiktok_style(tmp_run_dir: Path):
    from pipeline.captions import generate_captions
    timings = [
        WordTiming(word="كلمة1", offset_ms=0, duration_ms=400),
        WordTiming(word="كلمة2", offset_ms=400, duration_ms=400),
    ]
    srt = tmp_run_dir / "captions.ar.srt"
    ass = tmp_run_dir / "captions.ar.ass"
    generate_captions(
        timings=timings, srt_path=srt, ass_path=ass,
        font="Cairo-Black", font_size=90,
        style="tiktok", play_res_x=1080, play_res_y=1920,
    )
    assert ass.exists()
    text = ass.read_text(encoding="utf-8")
    assert "PlayResX: 1080" in text
    # No karaoke tags — single-run Arabic text per Dialogue event for bidi safety
    assert "\\k" not in text


def test_generate_captions_default_style_unchanged(tmp_run_dir: Path):
    """Existing default behavior must not break."""
    from pipeline.captions import generate_captions
    timings = [WordTiming(word="ك", offset_ms=0, duration_ms=400)]
    srt = tmp_run_dir / "c.srt"
    ass = tmp_run_dir / "c.ass"
    generate_captions(
        timings=timings, srt_path=srt, ass_path=ass,
        font="Cairo-Bold", font_size=60,
    )
    assert "PlayResX: 1920" in ass.read_text()  # horizontal default
    assert "\\k" not in ass.read_text()  # no karaoke
