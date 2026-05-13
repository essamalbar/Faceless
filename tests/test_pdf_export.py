"""Tests for pipeline.pdf_export — script.json -> PDF for the free-tier export."""
from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.pdf_export import render_script_pdf


def _script(**overrides):
    """Minimal script.json fixture — overridable per test."""
    doc = {
        "title": "بئر السواد",
        "target_duration_s": 16.0,
        "beats": [
            {
                "arabic": "في قرية معزولة عند سفح الجبل، كان البئر القديم …",
                "english_motion": "wide shot of an old well at dusk",
                "speaker": "narrator",
                "clip_duration_s": 8.0,
                "character_name": "",
                "is_silent": False,
            },
            {
                "arabic": "",
                "english_motion": "silent: a hand reaches into the well",
                "speaker": "narrator",
                "clip_duration_s": 8.0,
                "character_name": "",
                "is_silent": True,
            },
        ],
    }
    doc.update(overrides)
    return doc


def test_render_produces_pdf_file(tmp_path: Path):
    out = tmp_path / "script.pdf"
    render_script_pdf(_script(), out)
    assert out.exists()
    # %PDF-1.x magic header — quick sanity that we wrote a real PDF
    assert out.read_bytes().startswith(b"%PDF-")
    # Non-trivial size (embedded font subset alone is several KB)
    assert out.stat().st_size > 2_000


def test_render_handles_empty_beats(tmp_path: Path):
    out = tmp_path / "empty.pdf"
    render_script_pdf(_script(beats=[]), out)
    assert out.exists()
    assert out.read_bytes().startswith(b"%PDF-")


def test_render_handles_missing_title(tmp_path: Path):
    out = tmp_path / "no_title.pdf"
    render_script_pdf(_script(title=""), out)
    assert out.exists()


def test_render_handles_silent_beat_only(tmp_path: Path):
    """All-silent script must not crash on empty arabic strings."""
    silent = {
        "beats": [
            {"arabic": "", "speaker": "narrator", "clip_duration_s": 6.0,
             "is_silent": True, "character_name": ""},
        ],
    }
    out = tmp_path / "silent.pdf"
    render_script_pdf(silent, out)
    assert out.exists()


def test_render_handles_arabic_character_name(tmp_path: Path):
    """Regression: real scripts often carry Arabic character_name values
    (e.g. 'حورية'). Earlier versions concatenated those into a Helvetica
    header cell and crashed in production with
        FPDFUnicodeEncodingException: Character "س" ... outside
        the range of characters supported by the font used: "helveticaB"
    """
    arabic_named = {
        "title": "بئر السواد",
        "beats": [
            {"arabic": "السلام عليكم", "speaker": "character",
             "character_name": "حورية", "clip_duration_s": 6.0,
             "is_silent": False, "english_motion": "close up"},
        ],
    }
    out = tmp_path / "arabic_name.pdf"
    render_script_pdf(arabic_named, out)
    assert out.exists()
    assert out.read_bytes().startswith(b"%PDF-")


def test_render_raises_when_font_missing(tmp_path: Path, monkeypatch):
    """Treat a missing Amiri font as a deployment bug — a clear error
    beats a fpdf2 internal stacktrace."""
    monkeypatch.setattr("pipeline.pdf_export._FONT_PATH", tmp_path / "nope.ttf")
    out = tmp_path / "script.pdf"
    with pytest.raises(FileNotFoundError, match="Amiri font missing"):
        render_script_pdf(_script(), out)
