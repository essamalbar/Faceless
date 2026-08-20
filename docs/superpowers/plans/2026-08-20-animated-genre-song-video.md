# Animated Genre-Adaptive Song Video — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a per-song `video_mode: "animated"` that renders a layered, beat-synced, genre-adaptive song video (moving cover/stills + kinetic lyrics + genre-reactive FX) at ~$0/render.

**Architecture:** A new orchestrator `pipeline/song_animate.py` composes five units — a genre visual-template registry, word-level lyric timing (extended aligner), a kinetic-lyric ASS builder, a genre FX compositor (one ffmpeg filtergraph), and an overlay-loop library — into `final.mp4`. Reuses the existing forced alignment, beat grid, `[Verse]/[Chorus]` tags, and ASS/ffmpeg helpers. run.py routes `animated` mode; api.py validators accept it.

**Tech Stack:** Python 3.13, ffmpeg (libass `ass=` filter), librosa (via existing `song_beats`), pytest with monkeypatch mocks.

**Design doc:** `docs/superpowers/specs/2026-08-20-animated-genre-song-video-design.md`

## Global Constraints

- Every Python file starts with `from __future__ import annotations`; use `pathlib.Path` (never `os.path`); imports are absolute from the package root (`from pipeline.x import y`).
- **External tools are mocked in tests** (ffmpeg subprocess, librosa, `align_arabic`). Never invoke real ffmpeg/librosa or hit any network in tests.
- All artifacts live under `out/<run>/`; every stage is **resumable** (skip if its output exists).
- **Whisper's Arabic transcription is never displayed or persisted** — consume word-boundary timings only (existing `align_arabic` contract).
- **ffmpeg filtergraph discipline:** use `asplit`/`split` to fan out any label consumed more than once; keep the graph valid on **Debian ffmpeg 5.1.x** (prod), not local 8.x; bound `zoompan`/`-loop` frame counts; write `final.mp4` to a local temp then move onto the gcsfuse mount, with `+faststart` applied off-Fuse.
- **~$0/render** — no AI/network calls in this path; do not touch the Kie/Veo budget guard.
- `genre_key` values are exactly the keys of `GENRE_RECIPES` in `pipeline/song_style.py` (arabic_pop, arabic_ballad, khaleeji, tarab_classic, arabic_trap, folk_shaabi, hiphop_rap, rnb_soul, pop, rock, edm_electropop, cinematic_ost, generic) plus `generic` as the default.
- Reuse the ASS helpers already in `pipeline/song_assemble.py` (`_format_ass_time`, `_ass_escape`, `_escape_ffmpeg_filter_path`); do not duplicate them — Task 3 extracts them to a shared module if needed.

---

## File Structure

- Create: `pipeline/song_visual_style.py` — genre → `VisualTemplate` registry (Task 1)
- Modify: `pipeline/song_align.py` — persist per-word timings + `align_confidence` (Task 2)
- Create: `pipeline/song_ass_util.py` — shared ASS helpers extracted from song_assemble (Task 3)
- Create: `pipeline/song_kinetic_ass.py` — kinetic-lyric ASS builder (Task 3)
- Create: `pipeline/song_overlays.py` — overlay-loop lookup convention (Task 4)
- Create: `scripts/gen_overlays.py` — offline generator for the starter loop library (Task 4)
- Create: `assets/overlays/<genre_key>/*.webm` — generated starter loops (Task 4, committed assets)
- Create: `pipeline/song_animate.py` — FX compositor + `build_animated_video` (Task 5)
- Modify: `pipeline/api.py` — accept `video_mode="animated"` in both validators (Task 6)
- Modify: `run.py` — route `animated` mode (align + beats + build_animated_video, static fallback) (Task 6)
- Tests: `tests/test_song_visual_style.py`, `tests/test_song_align.py` (extend), `tests/test_song_kinetic_ass.py`, `tests/test_song_overlays.py`, `tests/test_song_animate.py`, `tests/test_song_api.py` (extend), `tests/test_run_song_mode.py` (extend)

---

### Task 1: Genre visual-template registry

**Files:**
- Create: `pipeline/song_visual_style.py`
- Test: `tests/test_song_visual_style.py`

**Interfaces:**
- Consumes: the `genre_key` strings from `pipeline.song_style.GENRE_RECIPES`.
- Produces: `LyricStyle`, `VisualTemplate` dataclasses; `visual_template_for(genre_key: str) -> VisualTemplate`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_song_visual_style.py
from __future__ import annotations

from pipeline.song_style import GENRE_RECIPES
from pipeline.song_visual_style import VisualTemplate, visual_template_for


def test_every_genre_key_resolves_to_a_full_template():
    for key in GENRE_RECIPES:
        t = visual_template_for(key)
        assert isinstance(t, VisualTemplate)
        assert t.genre_key == key
        assert t.bg and t.accent1 and t.text
        assert t.lyric.font_file and t.lyric.karaoke_fill and t.lyric.hook_color
        assert isinstance(t.fx_set, tuple) and t.fx_set  # at least one FX


def test_unknown_key_falls_back_to_generic():
    t = visual_template_for("does-not-exist")
    assert t.genre_key == "generic"


def test_trap_is_high_energy_and_ballad_is_soft():
    trap = visual_template_for("arabic_trap")
    ballad = visual_template_for("arabic_ballad")
    assert "beat_flash" in trap.fx_set and "rgb_glitch" in trap.fx_set
    assert "beat_flash" not in ballad.fx_set  # ballad is bold-but-soft, not strobing
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_song_visual_style.py -v`
Expected: FAIL (module `pipeline.song_visual_style` not found).

- [ ] **Step 3: Write minimal implementation**

```python
# pipeline/song_visual_style.py
"""genre_key -> VisualTemplate. The single place the per-genre animated look
(palette, font, lyric styling, FX set, transition, overlay dir) is defined.
Pure data + a lookup; no I/O."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"


@dataclass(frozen=True)
class LyricStyle:
    font_file: str      # absolute path string under assets/fonts
    karaoke_fill: str   # ASS &HAABBGGRR& color swept in as each word is sung
    karaoke_base: str   # not-yet-sung word color
    hook_color: str     # chorus hook-word color
    outline: str        # outline color
    outline_w: int = 3
    glow: bool = False


@dataclass(frozen=True)
class VisualTemplate:
    genre_key: str
    bg: str            # hex, backdrop grade anchor
    accent1: str
    accent2: str
    text: str
    lyric: LyricStyle
    fx_set: tuple[str, ...]   # ids consumed by song_animate: grade_*, beat_flash, rgb_glitch, light_sweep, grain, vignette, push_in
    overlay_dir: str | None   # "assets/overlays/<genre_key>" or None -> procedural only
    transition: str           # "hardcut" | "dip" | "glitch"


def _font(name: str) -> str:
    return str(_FONT_DIR / name)

# One shared default font that ships with the repo (Task confirms the actual
# filename present in assets/fonts and uses it here for every template).
_DEFAULT_FONT = "NotoSansArabic-Bold.ttf"

_TEMPLATES: dict[str, VisualTemplate] = {
    "arabic_trap": VisualTemplate(
        genre_key="arabic_trap", bg="#0b0016", accent1="#ff00e5", accent2="#00fff7",
        text="#ffffff",
        lyric=LyricStyle(_font(_DEFAULT_FONT), "&H00F7FF00&", "&H80FFFFFF&",
                         "&H00E500FF&", "&H00000000&", 4, glow=True),
        fx_set=("grade_neon", "beat_flash", "rgb_glitch", "grain"),
        overlay_dir="assets/overlays/arabic_trap", transition="glitch"),
    "arabic_ballad": VisualTemplate(
        genre_key="arabic_ballad", bg="#17060f", accent1="#ffd3a8", accent2="#b8607e",
        text="#ffe3d2",
        lyric=LyricStyle(_font(_DEFAULT_FONT), "&H00D2E3FF&", "&H80D2E3FF&",
                         "&H00A8D3FF&", "&H00000000&", 3, glow=True),
        fx_set=("grade_warm", "push_in", "light_sweep", "grain"),
        overlay_dir="assets/overlays/arabic_ballad", transition="dip"),
    # ... one entry per GENRE_RECIPES key (see design doc for the vibe of each) ...
    "generic": VisualTemplate(
        genre_key="generic", bg="#0d0d12", accent1="#7c5cff", accent2="#33e0ff",
        text="#ffffff",
        lyric=LyricStyle(_font(_DEFAULT_FONT), "&H00FFD07C&", "&H80FFFFFF&",
                         "&H00FF5CE0&", "&H00000000&", 3, glow=True),
        fx_set=("grade_cool", "push_in", "light_sweep", "grain"),
        overlay_dir=None, transition="dip"),
}


def visual_template_for(genre_key: str) -> VisualTemplate:
    return _TEMPLATES.get(genre_key, _TEMPLATES["generic"])
```

Implementer note: fill in a `VisualTemplate` for EVERY key in `GENRE_RECIPES` (the test enforces this), matching the design doc's per-genre vibe. Confirm the real bold-Arabic font filename in `assets/fonts/` and use it for `_DEFAULT_FONT` (the test only checks it is non-empty; a wrong filename would fail Task 3's render).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_song_visual_style.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/song_visual_style.py tests/test_song_visual_style.py
git commit -m "feat(song-visual): genre -> VisualTemplate registry"
```

---

### Task 2: Word-level lyric timing + confidence

**Files:**
- Modify: `pipeline/song_align.py` (the `align_song_lyrics` line-building loop)
- Test: `tests/test_song_align.py`

**Interfaces:**
- Consumes: `pipeline.align.align_arabic(song_mp3, sung_words) -> list[WordTiming]` where each item has `.offset_ms` and `.duration_ms` (existing).
- Produces: same `align_song_lyrics(*, song_mp3, lyrics, out_json) -> dict` output, with each `{"kind":"line", ...}` item additionally carrying `"words": [{"text","start","end"}, ...]` and `"align_confidence": float` in [0,1].

- [ ] **Step 1: Write the failing test**

```python
# tests/test_song_align.py  (add these; keep existing tests)
from __future__ import annotations

import json
from pathlib import Path

import pipeline.song_align as song_align


class _WT:
    def __init__(self, offset_ms, duration_ms):
        self.offset_ms = offset_ms
        self.duration_ms = duration_ms


def test_line_items_carry_word_timings_and_confidence(monkeypatch, tmp_path):
    lyrics = "[Verse 1]\nفي ليل بعيد\n[Chorus]\nيا قمر"
    # 5 sung words -> 5 word timings, 200ms each, back to back.
    wts = [_WT(i * 200, 200) for i in range(5)]
    monkeypatch.setattr(song_align, "align_arabic", lambda mp3, words: wts)
    monkeypatch.setattr(song_align, "_audio_duration_s", lambda p: 10.0)
    out = tmp_path / "lyrics_timing.json"
    data = song_align.align_song_lyrics(
        song_mp3=tmp_path / "song.mp3", lyrics=lyrics, out_json=out)
    lines = [it for it in data["lines"] if it["kind"] == "line"]
    v = lines[0]
    assert [w["text"] for w in v["words"]] == ["في", "ليل", "بعيد"]
    assert v["words"][0]["start"] == 0.0 and abs(v["words"][0]["end"] - 0.2) < 1e-6
    assert v["align_confidence"] == 1.0  # all words got a timing


def test_confidence_drops_when_timings_run_out(monkeypatch, tmp_path):
    lyrics = "[Verse 1]\nكلمة كلمة كلمة كلمة"  # 4 words
    monkeypatch.setattr(song_align, "align_arabic",
                        lambda mp3, words: [_WT(0, 200), _WT(200, 200)])  # only 2
    monkeypatch.setattr(song_align, "_audio_duration_s", lambda p: 10.0)
    data = song_align.align_song_lyrics(
        song_mp3=tmp_path / "song.mp3", lyrics=lyrics, out_json=tmp_path / "o.json")
    line = [it for it in data["lines"] if it["kind"] == "line"][0]
    assert line["align_confidence"] == 0.5  # 2 of 4 words timed
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_song_align.py -k word_timings -v`
Expected: FAIL (`KeyError: 'words'`).

- [ ] **Step 3: Write minimal implementation**

In `align_song_lyrics`, where each sung line is emitted (currently sets `start`/`end` from `taken = word_timings[word_idx:word_idx+n]`), also attach the per-word list and a confidence, then advance `word_idx`:

```python
        taken = word_timings[word_idx : word_idx + n]
        got = len(taken)
        words = [
            {"text": w_txt,
             "start": round(wt.offset_ms / 1000.0, 3),
             "end": round((wt.offset_ms + wt.duration_ms) / 1000.0, 3)}
            for w_txt, wt in zip(line_words, taken)  # line_words = this line split on whitespace
        ]
        start = taken[0].offset_ms / 1000.0 if taken else last_end
        end = ((taken[-1].offset_ms + taken[-1].duration_ms) / 1000.0
               if taken else min(last_end + 2.0, audio_dur))
        out_lines.append({
            "kind": "line", "text": line_text, "stanza": stanza,
            "start": round(start, 3), "end": round(end, 3),
            "words": words,
            "align_confidence": round(got / n, 3) if n else 0.0,
        })
        word_idx += n
```

Implementer note: derive `line_words = line_text.split()` and `n = len(line_words)` consistent with how the existing loop computes `n`. Keep every existing key so downstream `song_assemble._write_ass_subtitles` is unaffected (it ignores `words`/`align_confidence`).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_song_align.py -v`
Expected: PASS (existing align tests still green).

- [ ] **Step 5: Commit**

```bash
git add pipeline/song_align.py tests/test_song_align.py
git commit -m "feat(song-align): expose per-word timings + align_confidence"
```

---

### Task 3: Kinetic-lyric ASS builder

**Files:**
- Create: `pipeline/song_ass_util.py` (extract `_format_ass_time`, `_ass_escape` from song_assemble; re-import them there to avoid duplication)
- Create: `pipeline/song_kinetic_ass.py`
- Test: `tests/test_song_kinetic_ass.py`

**Interfaces:**
- Consumes: the Task 2 `lyrics_timing` dict; a Task 1 `VisualTemplate`.
- Produces: `pick_hook_word(text: str) -> str`; `build_kinetic_ass(*, lyrics_timing: dict, template: VisualTemplate, out_path: Path, min_confidence: float = 0.6) -> Path`.
- Section classification: a line is "chorus" iff its stanza's section header matches `Chorus` (reuse `pipeline.song_lyrics._SECTION_TAG_RE`); everything else sung is a verse.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_song_kinetic_ass.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_song_kinetic_ass.py -v`
Expected: FAIL (module not found).

- [ ] **Step 3: Write minimal implementation**

Create `pipeline/song_ass_util.py` by moving `_format_ass_time` and `_ass_escape` from `song_assemble.py` verbatim, then re-import them in `song_assemble.py` (`from pipeline.song_ass_util import _format_ass_time, _ass_escape`) so behavior is unchanged. Then:

```python
# pipeline/song_kinetic_ass.py
"""Build an ASS subtitle file with kinetic lyrics: karaoke (\\k) on verses,
hook-word emphasis on chorus lines, line-snap fallback on low-confidence lines.
Styled per VisualTemplate. Burned by song_animate via libass `ass=`."""
from __future__ import annotations

import re
from pathlib import Path

from pipeline.song_ass_util import _ass_escape, _format_ass_time
from pipeline.song_lyrics import _SECTION_TAG_RE
from pipeline.song_visual_style import VisualTemplate

# Short stopwords excluded from hook-word selection (Arabic + English).
_STOP = {"يا", "في", "من", "على", "the", "a", "and", "of", "to", "في"}


def pick_hook_word(text: str) -> str:
    words = [w for w in re.findall(r"[^\s]+", text) if w not in _STOP]
    if not words:
        return text.split()[0] if text.split() else text
    return max(words, key=len)


def _chorus_stanzas(lines: list[dict]) -> set[int]:
    out = set()
    for it in lines:
        if it["kind"] == "section" and re.search(r"chorus", it["text"], re.I):
            out.add(it["stanza"])
    return out


def _karaoke_text(words: list[dict], style: VisualTemplate) -> str:
    parts = []
    for w in words:
        cs = max(1, round((w["end"] - w["start"]) * 100))  # \k is centiseconds
        parts.append(f"{{\\k{cs}}}{_ass_escape(w['text'])} ")
    return "".join(parts).rstrip()


def build_kinetic_ass(*, lyrics_timing: dict, template: VisualTemplate,
                      out_path: Path, min_confidence: float = 0.6) -> Path:
    lines = lyrics_timing.get("lines", [])
    chorus = _chorus_stanzas(lines)
    events: list[str] = []
    for it in lines:
        if it["kind"] != "line":
            continue
        s, e = _format_ass_time(it["start"]), _format_ass_time(it["end"])
        conf = float(it.get("align_confidence", 0.0))
        words = it.get("words") or []
        if it["stanza"] in chorus and words:
            hook = pick_hook_word(it["text"])
            # hook word scaled up + pulsed; rest normal.
            rendered = " ".join(
                (f"{{\\fscx160\\fscy160\\1c{template.lyric.hook_color}"
                 f"\\t(0,300,\\fscx185\\fscy185)}}{_ass_escape(w)}{{\\r}}"
                 if w == hook else _ass_escape(w))
                for w in it["text"].split())
            events.append(f"Dialogue: 0,{s},{e},Kinetic,,0,0,0,,{rendered}")
        elif conf >= min_confidence and words:
            events.append(
                f"Dialogue: 0,{s},{e},Kinetic,,0,0,0,,{_karaoke_text(words, template)}")
        else:  # line-snap fallback
            events.append(
                f"Dialogue: 0,{s},{e},Kinetic,,0,0,0,,"
                f"{{\\fad(120,120)\\t(0,180,\\fscx112\\fscy112)}}{_ass_escape(it['text'])}")
    out_path.write_text(_ass_header(template) + "\n".join(events) + "\n",
                        encoding="utf-8")
    return out_path


def _ass_header(t: VisualTemplate) -> str:
    # [Script Info] + [V4+ Styles] "Kinetic" style built from the template
    # (font, primary=karaoke_base, secondary=karaoke_fill for \k sweep, outline).
    # Reuse the resolution + margin conventions from song_assemble._write_ass_subtitles.
    ...
```

Implementer note: build `_ass_header` to emit `[Script Info]` (PlayResX/Y matching the 1080×1920 render) and one `[V4+ Styles]` line named `Kinetic` whose Fontname points at `template.lyric.font_file`, `PrimaryColour = karaoke_base`, `SecondaryColour = karaoke_fill` (libass sweeps Primary→ nothing; for `\k` the *pre-sung* colour is SecondaryColour and *sung* is PrimaryColour — verify against the model already used in `song_assemble._write_ass_subtitles` and match its convention), `OutlineColour`, `Outline = outline_w`, bottom margin clear of the progress bar. Keep RTL working (the input text is already RTL; libass + the Arabic font handle shaping as in the existing captions).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_song_kinetic_ass.py tests/test_song_assemble.py -v`
Expected: PASS (kinetic tests green AND the extracted-helper move didn't break song_assemble).

- [ ] **Step 5: Commit**

```bash
git add pipeline/song_ass_util.py pipeline/song_kinetic_ass.py pipeline/song_assemble.py tests/test_song_kinetic_ass.py
git commit -m "feat(song-kinetic): karaoke/hook-word/line-snap ASS builder"
```

---

### Task 4: Overlay-loop lookup + offline generator

**Files:**
- Create: `pipeline/song_overlays.py`
- Create: `scripts/gen_overlays.py`
- Create: `assets/overlays/<genre_key>/*.webm` (generated, committed)
- Test: `tests/test_song_overlays.py`

**Interfaces:**
- Consumes: a `genre_key` and the repo root.
- Produces: `overlay_clips_for(genre_key: str) -> list[Path]` (existing clips, or `[]`); `build_overlay_cmd(kind: str, out: Path, size, seconds) -> list[str]` (ffmpeg argv the generator runs — unit-tested for construction).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_song_overlays.py
from __future__ import annotations

from pathlib import Path

from pipeline.song_overlays import overlay_clips_for, build_overlay_cmd


def test_missing_overlay_dir_returns_empty(monkeypatch, tmp_path):
    monkeypatch.setattr("pipeline.song_overlays.REPO_ROOT", tmp_path)
    assert overlay_clips_for("arabic_trap") == []


def test_present_overlay_dir_returns_clips(monkeypatch, tmp_path):
    d = tmp_path / "assets" / "overlays" / "arabic_trap"
    d.mkdir(parents=True)
    (d / "particles.webm").write_bytes(b"x")
    monkeypatch.setattr("pipeline.song_overlays.REPO_ROOT", tmp_path)
    clips = overlay_clips_for("arabic_trap")
    assert [p.name for p in clips] == ["particles.webm"]


def test_build_overlay_cmd_is_alpha_and_looODable():
    cmd = build_overlay_cmd("particles", Path("/tmp/p.webm"), (1080, 1920), 6)
    assert "ffmpeg" in cmd[0]
    assert "libvpx-vp9" in cmd  # webm w/ alpha
    assert "yuva420p" in cmd    # alpha pixel format
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_song_overlays.py -v`
Expected: FAIL (module not found).

- [ ] **Step 3: Write minimal implementation**

```python
# pipeline/song_overlays.py
from __future__ import annotations
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def overlay_clips_for(genre_key: str) -> list[Path]:
    d = REPO_ROOT / "assets" / "overlays" / genre_key
    return sorted(d.glob("*.webm")) if d.is_dir() else []


def build_overlay_cmd(kind: str, out: Path, size: tuple[int, int],
                      seconds: int) -> list[str]:
    w, h = size
    # Each `kind` maps to an ffmpeg lavfi source that renders a seamless,
    # alpha-transparent loop (particles/bokeh/light_sweep/geometric/grain).
    src = _LAVFI[kind](w, h, seconds)  # returns a -filter_complex string
    return ["ffmpeg", "-y", "-filter_complex", src, "-t", str(seconds),
            "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", str(out)]
```

Implementer note: `_LAVFI` is a dict of `kind -> callable(w,h,secs) -> str` producing lavfi graphs (e.g. particles via `life`/`noise`+`colorkey`, bokeh via blurred `gradients`, light_sweep via animated `gradients`, grain via `noise`). Keep each loop seamless (first frame == last). `scripts/gen_overlays.py` iterates the genre→kinds map (from the design's per-genre FX) and runs `build_overlay_cmd`, writing into `assets/overlays/<genre_key>/`.

- [ ] **Step 4: Run tests + generate the starter assets**

Run: `uv run pytest tests/test_song_overlays.py -v` → PASS.
Then generate + eyeball the real loops (developer machine, real ffmpeg):
Run: `uv run python scripts/gen_overlays.py --genres arabic_trap,arabic_ballad,tarab_classic,edm_electropop`
Expected: `assets/overlays/<genre>/*.webm` created; open a couple to confirm they loop and have alpha.

- [ ] **Step 5: Commit**

```bash
git add pipeline/song_overlays.py scripts/gen_overlays.py assets/overlays tests/test_song_overlays.py
git commit -m "feat(song-overlays): loop lookup + offline generator + starter assets"
```

---

### Task 5: Genre FX compositor (`build_animated_video`)

**Files:**
- Create: `pipeline/song_animate.py`
- Test: `tests/test_song_animate.py`

**Interfaces:**
- Consumes: Task 1 `VisualTemplate`, Task 4 `overlay_clips_for`, a beats dict (`{"beat_times": [...]}`), an `.ass` path, a backdrop (cover `Path` or list of still `Path`s), `song_mp3`.
- Produces: `build_filtergraph(*, template, beats, has_overlay, size) -> str` (pure, unit-tested); `build_animated_video(*, backdrop, song_mp3, ass_path, beats, template, out_path, size=(1080,1920)) -> Path`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_song_animate.py
from __future__ import annotations

from pathlib import Path

import pipeline.song_animate as sa
from pipeline.song_visual_style import visual_template_for


def test_filtergraph_uses_asplit_when_a_label_is_reused():
    fg = sa.build_filtergraph(template=visual_template_for("arabic_trap"),
                              beats={"beat_times": [0.5, 1.0, 1.5]},
                              has_overlay=True, size=(1080, 1920))
    assert "asplit" in fg or "split" in fg  # no label consumed twice un-split
    assert "ass=" in fg                      # lyrics burned last


def test_beat_flash_enable_exprs_come_from_beat_times():
    fg = sa.build_filtergraph(template=visual_template_for("arabic_trap"),
                              beats={"beat_times": [0.5, 1.0]},
                              has_overlay=False, size=(1080, 1920))
    assert "between(t,0.5" in fg and "between(t,1.0" in fg


def test_build_animated_video_invokes_ffmpeg_and_writes_output(monkeypatch, tmp_path):
    calls = {}
    def fake_run(cmd, **kw):
        calls["cmd"] = cmd
        Path(cmd[-1]).write_bytes(b"mp4")  # emulate ffmpeg writing the temp out
        class R: returncode = 0; stderr = b""
        return R()
    monkeypatch.setattr(sa.subprocess, "run", fake_run)
    monkeypatch.setattr(sa, "overlay_clips_for", lambda k: [])
    out = tmp_path / "final.mp4"
    cover = tmp_path / "cover.png"; cover.write_bytes(b"png")
    song = tmp_path / "song.mp3"; song.write_bytes(b"mp3")
    ass = tmp_path / "k.ass"; ass.write_text("[Script Info]\n")
    res = sa.build_animated_video(backdrop=cover, song_mp3=song, ass_path=ass,
                                  beats={"beat_times": [0.5]},
                                  template=visual_template_for("arabic_trap"),
                                  out_path=out)
    assert res == out and out.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_song_animate.py -v`
Expected: FAIL (module not found).

- [ ] **Step 3: Write minimal implementation**

```python
# pipeline/song_animate.py
"""Animated song-video compositor: one ffmpeg filtergraph layering a moving
backdrop + genre procedural FX (beat-synced) + overlay loops + burned kinetic
ASS. ~$0/render. Validate the graph on Debian ffmpeg 5.1.x (prod)."""
from __future__ import annotations

import subprocess
from pathlib import Path

from pipeline.song_overlays import overlay_clips_for
from pipeline.song_visual_style import VisualTemplate
from pipeline.song_ass_util import _escape_ffmpeg_filter_path  # add to util in Task 3


def _beat_flash(beats: dict) -> str:
    # brightness pop on each beat; short window so it reads as a flash
    exprs = "+".join(f"between(t,{b:.3f},{b + 0.08:.3f})"
                     for b in beats.get("beat_times", []))
    return (f"eq=brightness=0.12:enable='{exprs}'" if exprs else "null")


def build_filtergraph(*, template: VisualTemplate, beats: dict,
                      has_overlay: bool, size: tuple[int, int]) -> str:
    w, h = size
    chain = [f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}"]
    if "push_in" in template.fx_set:
        chain.append(f"zoompan=z='min(1.0+0.0006*on,1.25)':d=1:s={w}x{h}:fps=30")
    if "grade_neon" in template.fx_set or "grade_warm" in template.fx_set \
            or "grade_cool" in template.fx_set:
        chain.append("curves=preset=medium_contrast")   # template-specific in impl
    if "beat_flash" in template.fx_set:
        chain.append(_beat_flash(beats))
    if "rgb_glitch" in template.fx_set:
        chain.append("rgbashift=rh=2:bh=-2:enable='" +
                     "+".join(f"between(t,{b:.3f},{b + 0.05:.3f})"
                              for b in beats.get('beat_times', [])) + "'")
    if "grain" in template.fx_set:
        chain.append("noise=alls=8:allf=t")
    base = "[0:v]" + ",".join(chain) + "[bg]"
    # If an overlay is present it's input [1:v]; blend over [bg] -> [bg]. Any label
    # consumed twice MUST be asplit first (see Global Constraints).
    if has_overlay:
        graph = (base + ";"
                 f"[1:v]scale={w}:{h},format=yuva420p[ov];"
                 "[bg][ov]overlay=shortest=0[bg2];"
                 "[bg2]ass={ASS}[v]")
    else:
        graph = base + ";[bg]ass={ASS}[v]"
    return graph


def build_animated_video(*, backdrop, song_mp3: Path, ass_path: Path,
                         beats: dict, template: VisualTemplate, out_path: Path,
                         size: tuple[int, int] = (1080, 1920)) -> Path:
    if out_path.exists():
        return out_path  # resumable
    clips = overlay_clips_for(template.genre_key)
    has_overlay = bool(clips)
    fg = build_filtergraph(template=template, beats=beats,
                           has_overlay=has_overlay, size=size).replace(
        "{ASS}", _escape_ffmpeg_filter_path(ass_path))
    tmp = out_path.with_suffix(".tmp.mp4")  # write off-Fuse-safe, then move
    cover = backdrop if isinstance(backdrop, Path) else backdrop[0]
    cmd = ["ffmpeg", "-y", "-loop", "1", "-i", str(cover)]
    if has_overlay:
        cmd += ["-stream_loop", "-1", "-i", str(clips[0])]
    cmd += ["-i", str(song_mp3), "-filter_complex", fg,
            "-map", "[v]", "-map", f"{2 if has_overlay else 1}:a",
            "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
            "-shortest", "-movflags", "+faststart", str(tmp)]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(f"animated assemble failed: {r.stderr[-800:]!r}")
    tmp.replace(out_path)
    return out_path
```

Implementer note: make the grade/curves and zoompan bounds genre-specific from the template; ensure any intermediate label consumed more than once is `asplit`/`split` first; keep `-t`/`-shortest` so `-loop 1` and `-stream_loop -1` cannot run away. **Validate the emitted `-filter_complex` once in a Debian ffmpeg 5.1.x container before Task 6 ships.** For cinematic backdrops (a list of stills), extend to the beat-cut concat used by `song_cinematic`; a single cover uses `-loop 1`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_song_animate.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/song_animate.py tests/test_song_animate.py
git commit -m "feat(song-animate): genre FX compositor (build_animated_video)"
```

---

### Task 6: Wire `animated` mode into api + run

**Files:**
- Modify: `pipeline/api.py` (both `video_mode` field-validators + doc comments)
- Modify: `run.py` (route `animated`: align + beats + build_animated_video, static fallback)
- Test: `tests/test_song_api.py` (extend), `tests/test_run_song_mode.py` (extend)

**Interfaces:**
- Consumes: everything from Tasks 1–5.
- Produces: `video_mode="animated"` accepted by the API; run.py assembles via `song_animate.build_animated_video` when `video_mode == "animated"`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_song_api.py  (add)
def test_create_song_accepts_animated_video_mode(app):
    fastapi_app, token = app
    from fastapi.testclient import TestClient
    c = TestClient(fastapi_app)
    r = c.post("/songs", json={"theme": "x", "video_mode": "animated"},
               headers={"Authorization": f"Bearer {token}"})
    assert r.status_code in (200, 201), r.text
```

```python
# tests/test_run_song_mode.py  (add) — routing calls the animated assembler
def test_animated_mode_calls_build_animated_video(monkeypatch, tmp_path):
    import run as run_mod
    from pipeline import song_animate
    called = {}
    monkeypatch.setattr(song_animate, "build_animated_video",
                        lambda **k: called.setdefault("hit", True) or k["out_path"])
    # ... arrange a resumed run_dir with video_mode="animated", song.mp3, lyrics,
    #     and monkeypatch align_song_lyrics + detect_beats to write their jsons ...
    # ... invoke the post-approve song path ...
    assert called.get("hit") is True
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_song_api.py -k animated tests/test_run_song_mode.py -k animated -v`
Expected: FAIL (422 from the validator; `build_animated_video` not called).

- [ ] **Step 3: Implement**

In `pipeline/api.py`, both validators (≈ lines 449 and 490):

```python
        if v not in ("static", "cinematic", "animated"):
            raise ValueError("video_mode must be 'static', 'cinematic', or 'animated'")
```

Update the nearby doc comments (lines ~417-419, ~602-604) to mention `animated`.

In `run.py` post-approve song path: (a) extend the beats gate (line ~1472) so beats are detected for `animated` too: `if video_mode in ("cinematic", "animated"):`; ensure `align_song_lyrics` (line ~1455) also runs for `animated` (word timing is required). (b) add an `animated` branch alongside the cinematic branch (≈ line 1486):

```python
        elif video_mode == "animated":
            from pipeline import song_animate, song_kinetic_ass, song_visual_style
            template = song_visual_style.visual_template_for(_genre_key_from(script))
            ass_path = run_dir / "lyrics.ass"
            song_kinetic_ass.build_kinetic_ass(
                lyrics_timing=json.loads((run_dir / "lyrics_timing.json").read_text()),
                template=template, out_path=ass_path)
            try:
                song_animate.build_animated_video(
                    backdrop=run_dir / "cover.png", song_mp3=song_mp3,
                    ass_path=ass_path, beats=beats_data, template=template,
                    out_path=final_mp4)
            except Exception as anim_err:
                print(f"[song-post-approve] animated assemble failed ({anim_err}); "
                      "falling back to static")
                song_assemble.assemble_song_video(...)  # same args as the existing static call
```

Implementer note: match the exact variable names already in scope at that point (`beats_data`, `song_mp3`, `final_mp4`, `_genre_key_from`, the static-call argument list). Reuse the existing lyrics-timing artifact written by `align_song_lyrics` at line ~1455 (its output path). Keep the stage resumable (skip if `final_mp4` exists) and never clobber the song's top-level `status`.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_song_api.py tests/test_run_song_mode.py -v`
Expected: PASS.

- [ ] **Step 5: Full suite + commit**

Run: `uv run pytest -q` (clean env — do NOT source .env) → all green.

```bash
git add pipeline/api.py run.py tests/test_song_api.py tests/test_run_song_mode.py
git commit -m "feat(song): wire animated video_mode into api + run routing"
```

---

## Self-Review notes (for the executor)

- Every `GENRE_RECIPES` key must have a `VisualTemplate` (Task 1 test enforces).
- The Task 2 schema change is additive — `song_assemble._write_ass_subtitles` must keep working unchanged (Task 3 runs its tests).
- The FX filtergraph MUST be validated once against **Debian ffmpeg 5.1.x** (prod) before Task 6 ships — local ffmpeg 8.x is not proof (see Global Constraints / memory).
- No task introduces an AI/network call; per-render cost stays $0.
