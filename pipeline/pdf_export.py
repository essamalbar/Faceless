"""Render an Arabic script.json into a downloadable PDF.

This is the free-tier hook — anyone can write a script (no subscription
required) and export it as a PDF. Only video rendering requires credits.

The PDF embeds Amiri-Regular.ttf (SIL OFL, bundled in assets/fonts/) so it
renders on systems with no Arabic system fonts (e.g. Cloud Run's slim
python image). Arabic text is reshaped + bidi-mapped before drawing
because fpdf2 does not handle Arabic shaping or RTL flow natively.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import arabic_reshaper
from bidi.algorithm import get_display
from fpdf import FPDF

_FONT_PATH = (
    Path(__file__).resolve().parent.parent / "assets" / "fonts" / "Amiri-Regular.ttf"
)

# Family name we register inside fpdf2 — independent of the file name.
_FONT_NAME = "Amiri"


def _shape(text: str) -> str:
    """Apply Arabic shaping + bidi reorder so glyphs render correctly when
    drawn left-to-right by fpdf2. Without this, Arabic letters appear in
    their isolated forms and out-of-order."""
    if not text:
        return ""
    reshaped = arabic_reshaper.reshape(text)
    return get_display(reshaped)


def render_script_pdf(script: dict[str, Any], out_path: Path) -> None:
    """Render `script.json`-shaped dict into a PDF at `out_path`.

    Layout:
        - Title at top (centered, large, Amiri)
        - Subtitle: "<N> beats"
        - For each beat:
            * Beat index + speaker (English label, LTR)
            * Arabic dialogue, RTL, justified left margin

    Raises FileNotFoundError if the Amiri font is missing — the caller
    should treat that as a deployment bug, not a user error.
    """
    if not _FONT_PATH.exists():
        raise FileNotFoundError(
            f"Amiri font missing at {_FONT_PATH}; bundle it before deploy."
        )

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_font(_FONT_NAME, "", str(_FONT_PATH))
    pdf.add_page()

    # Title
    title = str(script.get("title") or "").strip()
    if title:
        pdf.set_font(_FONT_NAME, size=22)
        pdf.multi_cell(0, 11, _shape(title), align="C")
        pdf.ln(2)

    # Beat count subtitle (uses fpdf2's core Helvetica since it's English)
    beats = list(script.get("beats") or [])
    pdf.set_font("Helvetica", size=10)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 6, f"{len(beats)} beats", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)
    pdf.set_text_color(0, 0, 0)

    # Beats
    for i, beat in enumerate(beats, start=1):
        speaker = str(beat.get("speaker") or "narrator")
        character = str(beat.get("character_name") or "").strip()
        arabic = str(beat.get("arabic") or "").strip()
        is_silent = bool(beat.get("is_silent"))

        # Beat header: "01 · NARRATOR · 8s" (English, LTR)
        duration_s = float(beat.get("clip_duration_s") or 0)
        header_bits = [f"{i:02d}", speaker.upper()]
        if character:
            header_bits.append(character)
        if duration_s > 0:
            header_bits.append(f"{duration_s:.0f}s")
        header = "  ·  ".join(header_bits)

        pdf.set_font("Helvetica", style="B", size=10)
        pdf.set_text_color(80, 80, 80)
        pdf.cell(0, 6, header, new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
        pdf.ln(1)

        # Arabic body — shaped + RTL-aligned
        pdf.set_font(_FONT_NAME, size=14)
        if is_silent or not arabic:
            # Silent action beat - italic English note, no Arabic to draw.
            # Use ASCII-only punctuation: fpdf2's core Helvetica is latin-1
            # and chokes on em-dashes / smart quotes.
            pdf.set_font("Helvetica", style="I", size=11)
            pdf.set_text_color(140, 140, 140)
            pdf.multi_cell(0, 6, "(silent action beat - no dialogue)")
            pdf.set_text_color(0, 0, 0)
        else:
            pdf.multi_cell(0, 8, _shape(arabic), align="R")
        pdf.ln(4)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(out_path))
