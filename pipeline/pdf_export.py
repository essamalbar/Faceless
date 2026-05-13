"""Render an Arabic script.json into a director-grade PDF.

This is the free-tier hook — anyone can write a script (no subscription
required) and export it as a usable shooting document. The PDF embeds
Amiri-Regular.ttf (SIL OFL, bundled in assets/fonts/) so it renders on
systems with no Arabic system fonts (e.g. Cloud Run's slim python image).
Arabic text is reshaped + bidi-mapped before drawing because fpdf2 does
not handle Arabic shaping or RTL flow natively.

Layout:
    Cover page  ── title, theme/mood/runtime block, faceless branding
    Cast page   ── (skipped when character_descriptions is empty)
    Beat pages  ── one beat = beat header + VISUAL + DIALOGUE sections,
                   continuous flow with auto page-break

Every non-cover page carries a footer (page number + Faceless wordmark).
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import arabic_reshaper
from bidi.algorithm import get_display
from fpdf import FPDF

_FONT_PATH = (
    Path(__file__).resolve().parent.parent / "assets" / "fonts" / "Amiri-Regular.ttf"
)

_FONT_NAME = "Amiri"

# Gold accent — pinned to the Flutter UI's FacelessTheme.accent so the PDF
# feels like the same product. If FacelessTheme.accent changes in the app,
# update both: there's no shared source of truth across the python/dart split.
_GOLD = (231, 181, 60)         # #E7B53C
_DARK = (10, 14, 26)           # #0A0E1A
_SUBTLE = (130, 130, 130)
_RULE = (220, 220, 220)


def _shape(text: str) -> str:
    """Apply Arabic shaping + bidi reorder so glyphs render correctly when
    drawn left-to-right by fpdf2. Without this, Arabic letters appear in
    their isolated forms and out-of-order."""
    if not text:
        return ""
    reshaped = arabic_reshaper.reshape(text)
    return get_display(reshaped)


def _ascii_safe(text: str) -> str:
    """Strip non-latin-1 chars so fpdf2's core Helvetica doesn't crash on
    smart quotes / em-dashes / Arabic. Used for any string drawn in
    Helvetica — Amiri-rendered strings should NOT go through this."""
    return text.encode("latin-1", errors="replace").decode("latin-1")


class _DirectorPDF(FPDF):
    """FPDF subclass that paints a faceless-branded footer on every page
    after the cover. The cover skips the footer (it has its own branding
    bar at the bottom)."""

    def __init__(self) -> None:
        super().__init__(orientation="P", unit="mm", format="A4")
        self.set_auto_page_break(auto=True, margin=22)
        self.add_font(_FONT_NAME, "", str(_FONT_PATH))
        self._draw_footer = False

    def footer(self) -> None:  # type: ignore[override]
        if not self._draw_footer:
            return
        self.set_y(-15)
        self.set_font("Helvetica", size=8)
        self.set_text_color(*_SUBTLE)
        # Left: wordmark · Right: page number
        self.cell(0, 5, "FACELESS", align="L")
        self.set_xy(-30, self.get_y())
        self.cell(20, 5, f"Page {self.page_no() - 1}", align="R")
        self.set_text_color(0, 0, 0)


def _draw_cover(pdf: _DirectorPDF, script: dict[str, Any]) -> None:
    """First page: brand glyph, title, metadata grid, bottom rule."""
    pdf._draw_footer = False
    pdf.add_page()

    # Brand mark: gold disc with a dark crescent + small star — matches
    # the Flutter widget in lib/widgets/faceless_logo.dart so the brand
    # reads identically in the app and on paper.
    cx, cy, r = 105.0, 50.0, 11.0
    pdf.set_fill_color(*_GOLD)
    pdf.circle(x=cx, y=cy, radius=r, style="F")

    # Crescent: subtractive — paint a smaller dark circle slightly inside
    # the disc to leave a crescent of gold along the left edge. Using the
    # cover background color (white) for the cutout keeps it clean.
    pdf.set_fill_color(255, 255, 255)
    pdf.circle(x=cx + r * 0.20, y=cy - r * 0.04, radius=r * 0.78, style="F")

    # Re-fill the inner crescent body in dark so the mark reads as a
    # crescent silhouette (not just a thin gold rim).
    pdf.set_fill_color(*_DARK)
    pdf.circle(x=cx - r * 0.08, y=cy, radius=r * 0.55, style="F")
    pdf.set_fill_color(255, 255, 255)
    pdf.circle(x=cx + r * 0.20, y=cy - r * 0.04, radius=r * 0.50, style="F")

    # Accent star — small 4-point diamond pair at the upper-right.
    pdf.set_fill_color(*_GOLD)
    sx, sy, sr = cx + r * 0.40, cy - r * 0.45, r * 0.13
    # Vertical diamond
    pdf.polygon([(sx, sy - sr), (sx + sr * 0.35, sy),
                 (sx, sy + sr), (sx - sr * 0.35, sy)], style="F")
    # Horizontal diamond — fpdf2's polygon accepts a list of (x,y) tuples
    pdf.polygon([(sx - sr, sy), (sx, sy + sr * 0.35),
                 (sx + sr, sy), (sx, sy - sr * 0.35)], style="F")
    pdf.set_fill_color(0, 0, 0)

    # Title
    pdf.set_y(cy + r + 14)
    title = str(script.get("title") or "").strip()
    if title:
        pdf.set_font(_FONT_NAME, size=26)
        pdf.multi_cell(0, 12, _shape(title), align="C")
    pdf.ln(2)

    # Subtitle: "Director's Script" + Arabic equivalent on the next line
    pdf.set_font("Helvetica", style="B", size=10)
    pdf.set_text_color(*_SUBTLE)
    pdf.cell(0, 5, "DIRECTOR'S SCRIPT", align="C",
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(_FONT_NAME, size=12)
    pdf.cell(0, 7, _shape("سيناريو المخرج"), align="C",
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(10)

    # Metadata grid: 2 columns of label/value pairs
    beats = list(script.get("beats") or [])
    total_s = float(script.get("target_duration_s") or 0)
    if total_s == 0:
        total_s = sum(float(b.get("clip_duration_s") or 0) for b in beats)
    runtime_label = f"{int(total_s // 60)}:{int(total_s % 60):02d}" if total_s else "—"

    rows = [
        ("THEME", _ascii_safe(str(script.get("theme") or "—")).title()),
        ("MOOD", _ascii_safe(str(script.get("music_mood") or "—")).title()),
        ("BEATS", str(len(beats))),
        ("RUNTIME", runtime_label),
    ]
    pdf.set_font("Helvetica", size=9)
    col_w = 75
    pad_x = (210 - col_w * 2) / 2
    for i in range(0, len(rows), 2):
        # Top row of the pair: labels
        pdf.set_x(pad_x)
        pdf.set_text_color(*_SUBTLE)
        pdf.cell(col_w, 5, rows[i][0])
        pdf.cell(col_w, 5, rows[i + 1][0],
                 new_x="LMARGIN", new_y="NEXT")
        # Bottom row: values
        pdf.set_x(pad_x)
        pdf.set_text_color(*_DARK)
        pdf.set_font("Helvetica", style="B", size=14)
        pdf.cell(col_w, 7, rows[i][1])
        pdf.cell(col_w, 7, rows[i + 1][1],
                 new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", size=9)
        pdf.ln(4)
    pdf.set_text_color(0, 0, 0)

    # Bottom rule + generation stamp
    pdf.set_y(-32)
    pdf.set_draw_color(*_GOLD)
    pdf.set_line_width(0.6)
    pdf.line(40, pdf.get_y(), 170, pdf.get_y())
    pdf.set_draw_color(0, 0, 0)
    pdf.ln(4)
    pdf.set_font("Helvetica", size=8)
    pdf.set_text_color(*_SUBTLE)
    stamp = datetime.now(timezone.utc).strftime("Generated %Y-%m-%d")
    pdf.cell(0, 5, f"FACELESS  ·  {stamp}", align="C")
    pdf.set_text_color(0, 0, 0)


def _draw_cast(pdf: _DirectorPDF, characters: dict[str, str]) -> None:
    """Optional cast page — one row per character with the Arabic name
    on the right and English physical description on the left."""
    if not characters:
        return
    pdf._draw_footer = True
    pdf.add_page()
    _section_header(pdf, en="CAST", ar="الشخصيات")

    pdf.ln(4)
    for name, desc in characters.items():
        if not name and not desc:
            continue
        # Arabic name right-aligned, big. Reset x explicitly: fpdf2's
        # multi_cell with align="R" can leave the cursor at the right
        # margin and break subsequent left-aligned multi_cells with
        # "Not enough horizontal space to render a single character".
        pdf.set_x(pdf.l_margin)
        pdf.set_font(_FONT_NAME, size=14)
        pdf.set_text_color(*_DARK)
        pdf.multi_cell(0, 8, _shape(name or ""), align="R",
                       new_x="LMARGIN", new_y="NEXT")
        # English description left-aligned, smaller
        if desc:
            pdf.set_x(pdf.l_margin)
            pdf.set_font("Helvetica", style="I", size=10)
            pdf.set_text_color(*_SUBTLE)
            pdf.multi_cell(0, 5, _ascii_safe(desc),
                           new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
        pdf.ln(4)


def _section_header(pdf: _DirectorPDF, *, en: str, ar: str) -> None:
    """Gold rule + English/Arabic bilingual section title."""
    pdf.set_draw_color(*_GOLD)
    pdf.set_line_width(0.8)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + 14, pdf.get_y())
    pdf.set_draw_color(0, 0, 0)
    pdf.ln(2)
    pdf.set_font("Helvetica", style="B", size=11)
    pdf.set_text_color(*_DARK)
    pdf.cell(0, 6, en, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(_FONT_NAME, size=11)
    pdf.set_text_color(*_SUBTLE)
    pdf.cell(0, 6, _shape(ar), new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)


def _draw_beats(pdf: _DirectorPDF, beats: list[dict[str, Any]]) -> None:
    """One section per beat: header strip, VISUAL block, DIALOGUE block."""
    pdf._draw_footer = True
    pdf.add_page()
    _section_header(pdf, en="SCRIPT", ar="السيناريو")
    pdf.ln(2)

    for i, beat in enumerate(beats, start=1):
        _draw_beat(pdf, i, beat)


def _draw_beat(pdf: _DirectorPDF, index: int, beat: dict[str, Any]) -> None:
    speaker = str(beat.get("speaker") or "narrator")
    character = str(beat.get("character_name") or "").strip()
    arabic = str(beat.get("arabic") or "").strip()
    # Prefer arabic_motion when the LLM produced it (new scripts); fall
    # back to english_motion for legacy script.json files that pre-date
    # the field. The PDF stays bilingual-capable either way.
    motion_ar = str(beat.get("arabic_motion") or "").strip()
    motion_en = str(beat.get("english_motion") or "").strip()
    is_silent = bool(beat.get("is_silent"))
    duration_s = float(beat.get("clip_duration_s") or 0)

    # Estimate the height this beat will use; if we'd cross the bottom
    # margin, force a new page so we never split a beat across pages.
    needed = 36
    if motion_ar or motion_en:
        needed += 14
    if arabic and not is_silent:
        needed += max(14, len(arabic) // 30 * 6)
    if pdf.get_y() + needed > pdf.h - pdf.b_margin:
        pdf.add_page()

    # ── Beat strip: big gold "01" + speaker label + duration on the right
    strip_y = pdf.get_y()
    pdf.set_font("Helvetica", style="B", size=22)
    pdf.set_text_color(*_GOLD)
    idx_label = f"{index:02d}"
    pdf.cell(18, 12, idx_label)
    pdf.set_text_color(0, 0, 0)

    # Right side: duration · speaker (ASCII only — Helvetica latin-1)
    pdf.set_xy(pdf.l_margin + 18, strip_y + 2)
    pdf.set_font("Helvetica", style="B", size=9)
    pdf.set_text_color(*_SUBTLE)
    bits = []
    if duration_s > 0:
        bits.append(f"{duration_s:.0f}s")
    bits.append(_ascii_safe(speaker).upper())
    pdf.cell(0, 5, "  ·  ".join(bits),
             new_x="LMARGIN", new_y="NEXT")

    # Character name (Arabic, Amiri-shaped, on its own line so latin-1
    # Helvetica doesn't choke).
    if character:
        pdf.set_x(pdf.l_margin + 18)
        pdf.set_font(_FONT_NAME, size=12)
        pdf.set_text_color(*_DARK)
        pdf.multi_cell(0, 6, _shape(character),
                       new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)

    # Skip past the gold "NN" baseline to start the body block flush left
    pdf.set_y(strip_y + 14)

    # ── VISUAL block (director's blocking)
    # Prefer arabic_motion (new scripts), fall back to english_motion
    # (legacy scripts) so the document is still informative either way.
    if motion_ar or motion_en:
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", style="B", size=8)
        pdf.set_text_color(*_SUBTLE)
        # Bilingual label: المشهد / VISUAL — using two cells so we get
        # both languages without mixing fonts on one cell.
        pdf.cell(40, 4, "VISUAL")
        pdf.set_font(_FONT_NAME, size=9)
        pdf.cell(0, 4, _shape("المشهد"), align="R",
                 new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(*_DARK)
        if motion_ar:
            pdf.set_x(pdf.l_margin)
            pdf.set_font(_FONT_NAME, size=12)
            pdf.multi_cell(0, 7, _shape(motion_ar), align="R",
                           new_x="LMARGIN", new_y="NEXT")
        else:
            pdf.set_x(pdf.l_margin)
            pdf.set_font("Helvetica", style="I", size=10)
            pdf.multi_cell(0, 5, _ascii_safe(motion_en),
                           new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
        pdf.ln(2)

    # ── DIALOGUE block (or silent-beat marker)
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", style="B", size=8)
    pdf.set_text_color(*_SUBTLE)
    pdf.cell(0, 4, "DIALOGUE", new_x="LMARGIN", new_y="NEXT")
    if is_silent or not arabic:
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", style="I", size=10)
        pdf.set_text_color(*_SUBTLE)
        pdf.multi_cell(0, 5, "(silent action - no dialogue)",
                       new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
    else:
        pdf.set_x(pdf.l_margin)
        pdf.set_font(_FONT_NAME, size=14)
        pdf.set_text_color(0, 0, 0)
        pdf.multi_cell(0, 8, _shape(arabic), align="R",
                       new_x="LMARGIN", new_y="NEXT")

    # Thin separator between beats
    pdf.ln(3)
    pdf.set_draw_color(*_RULE)
    pdf.set_line_width(0.2)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.set_draw_color(0, 0, 0)
    pdf.ln(5)


def render_script_pdf(script: dict[str, Any], out_path: Path) -> None:
    """Render `script.json`-shaped dict into a director-grade PDF.

    Raises FileNotFoundError if the Amiri font is missing — caller should
    treat that as a deployment bug, not a user error.
    """
    if not _FONT_PATH.exists():
        raise FileNotFoundError(
            f"Amiri font missing at {_FONT_PATH}; bundle it before deploy."
        )

    pdf = _DirectorPDF()
    _draw_cover(pdf, script)
    chars = dict(script.get("character_descriptions") or {})
    _draw_cast(pdf, chars)
    _draw_beats(pdf, list(script.get("beats") or []))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(out_path))
