from __future__ import annotations

from pipeline.song_visual_style import visual_template_for
from pipeline.song_kinetic_ass import build_kinetic_ass, pick_hook_word


def _timing():
    return {"audio_duration": 12.0, "lines": [
        {"kind": "section", "text": "Verse 1", "start": 0.0, "end": 0.0, "stanza": 1},
        {"kind": "line", "text": "في ليل بعيد", "start": 0.0, "end": 2.0, "stanza": 1,
         "words": [{"text": "في", "start": 0.0, "end": 0.5},
                   {"text": "ليل", "start": 0.5, "end": 1.2},
                   {"text": "بعيد", "start": 1.2, "end": 2.0}],
         "align_confidence": 1.0},
        {"kind": "section", "text": "Chorus", "start": 2.0, "end": 2.0, "stanza": 2},
        {"kind": "line", "text": "يا قمر الليل", "start": 2.0, "end": 4.0, "stanza": 2,
         "words": [{"text": "يا", "start": 2.0, "end": 2.3},
                   {"text": "قمر", "start": 2.3, "end": 3.0},
                   {"text": "الليل", "start": 3.0, "end": 4.0}],
         "align_confidence": 1.0},
        {"kind": "line", "text": "سطر غير مضبوط", "start": 4.0, "end": 6.0, "stanza": 1,
         "words": [], "align_confidence": 0.0},
    ]}


def test_verse_line_uses_karaoke_k_tags_one_per_word(tmp_path):
    out = build_kinetic_ass(lyrics_timing=_timing(),
                            template=visual_template_for("arabic_trap"),
                            out_path=tmp_path / "k.ass")
    body = out.read_text(encoding="utf-8")
    verse_event = [ln for ln in body.splitlines()
                   if ln.startswith("Dialogue:") and "بعيد" in ln][0]
    assert verse_event.count("\\k") == 3  # one \k per word


def test_chorus_line_emphasizes_a_hook_word(tmp_path):
    out = build_kinetic_ass(lyrics_timing=_timing(),
                            template=visual_template_for("arabic_trap"),
                            out_path=tmp_path / "k.ass")
    body = out.read_text(encoding="utf-8")
    # hook word gets a scale transform \t(...\fscx...) that a plain karaoke line lacks
    chorus_events = [ln for ln in body.splitlines()
                     if ln.startswith("Dialogue:") and "قمر" in ln]
    assert any("\\t(" in ln and "\\fscx" in ln for ln in chorus_events)


def test_low_confidence_line_falls_back_to_line_snap(tmp_path):
    out = build_kinetic_ass(lyrics_timing=_timing(),
                            template=visual_template_for("arabic_trap"),
                            out_path=tmp_path / "k.ass", min_confidence=0.6)
    body = out.read_text(encoding="utf-8")
    snap = [ln for ln in body.splitlines()
            if ln.startswith("Dialogue:") and "مضبوط" in ln][0]
    assert "\\k" not in snap          # no karaoke on a fallback line
    assert "\\fad" in snap or "\\t(" in snap  # a snap/fade-in transform instead


def test_pick_hook_word_prefers_long_content_word():
    assert pick_hook_word("يا قمر الليل") in ("الليل", "قمر")
