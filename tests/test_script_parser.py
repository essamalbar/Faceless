"""Markdown episode-script parser tests.

Verifies dialogue is preserved verbatim, speakers are mapped correctly,
and silent scenes produce silent beats. The parser is regex-only — these
tests double as the spec for what input shapes are recognized.
"""
from __future__ import annotations

import textwrap

from pipeline.script_parser import (
    parse_arabic_speaker,
    parse_episode_markdown,
)


def _norm(s: str) -> str:
    return textwrap.dedent(s).strip()


def test_parse_title_from_episode_header():
    raw = _norm("""
        **العنوان: القلادة المقدسة – الحلقة الرابعة**

        **المشهد 1 – بداية**

        **الشاب:**
        "أنا هنا"
    """)
    out = parse_episode_markdown(raw)
    assert out.title == "القلادة المقدسة – الحلقة الرابعة"


def test_dialogue_preserved_exactly():
    """The parser must NEVER alter a single character of the user's
    Arabic dialogue. This is the whole point of the paste-script feature."""
    raw = _norm("""
        **العنوان: x**

        **المشهد 1 – test**

        **الشاب (بهمس):**
        "أنا… وين…؟"
    """)
    out = parse_episode_markdown(raw)
    assert len(out.beats) == 1
    assert out.beats[0].arabic == "أنا… وين…؟"   # exact match incl. ellipsis
    assert out.beats[0].speaker == "son"


def test_arabic_speaker_with_parenthetical_stage_direction():
    raw = _norm("""
        **المشهد 1 – x**

        **الأم (قوي):**
        "الخوف مو عدوك"
    """)
    out = parse_episode_markdown(raw)
    assert out.beats[0].speaker == "mother"
    assert out.beats[0].arabic == "الخوف مو عدوك"


def test_shadow_speaker_for_alter_ego():
    """النسخة (alter ego) maps to 'shadow' — a new speaker added for EP4-style
    inner-conflict episodes where the protagonist confronts his dark self."""
    raw = _norm("""
        **المشهد 2 – المواجهة**

        **النسخة الأخرى (بابتسامة باردة):**
        "كنت مفكر التضحية رح تنقذك؟"

        **النسخة:**
        "أنا… خوفك. ضعفك."
    """)
    out = parse_episode_markdown(raw)
    assert len(out.beats) == 2
    assert out.beats[0].speaker == "shadow"
    assert out.beats[0].arabic == "كنت مفكر التضحية رح تنقذك؟"
    assert out.beats[1].speaker == "shadow"


def test_multiple_speakers_in_one_scene_become_separate_beats():
    raw = _norm("""
        **المشهد 1 – x**

        **النسخة:**
        "إما تسيطر… أو تختفي."

        صوت أمه يعود.

        **الأم (قوي):**
        "الخوف سلاحك."

        **الشاب:**
        "فهمت يا إمي."
    """)
    out = parse_episode_markdown(raw)
    assert [b.speaker for b in out.beats] == ["shadow", "mother", "son"]
    assert [b.arabic for b in out.beats] == [
        "إما تسيطر… أو تختفي.",
        "الخوف سلاحك.",
        "فهمت يا إمي.",
    ]


def test_silent_scene_produces_silent_beat():
    """A scene with only stage directions and no `**SPEAKER:**` blocks
    becomes a single silent beat (arabic empty), so the user can render
    a wordless action sequence."""
    raw = _norm("""
        **المشهد 5 – العودة**

        قطع مفاجئ. ساحة المعركة. القلادة على الأرض.
        فجأة تتحرك. ومضة ضوء.
    """)
    out = parse_episode_markdown(raw)
    assert len(out.beats) == 1
    assert out.beats[0].arabic == ""
    assert "Scene 5" in out.beats[0].english_motion


def test_unknown_speaker_falls_back_to_son():
    raw = _norm("""
        **المشهد 1 – x**

        **شخصية مجهولة:**
        "test line"
    """)
    out = parse_episode_markdown(raw)
    assert out.beats[0].speaker == "son"   # safe default


def test_scenes_separated_by_horizontal_rules():
    """Many scripts use `---` between scenes. The scene regex doesn't
    require those to exist; what matters is `**المشهد N` headers."""
    raw = _norm("""
        **المشهد 1 – أ**

        **الشاب:**
        "خط أول"

        ---

        **المشهد 2 – ب**

        **الأم:**
        "خط ثاني"
    """)
    out = parse_episode_markdown(raw)
    assert len(out.beats) == 2
    assert out.beats[0].speaker == "son"
    assert out.beats[1].speaker == "mother"


def test_full_ep4_style_script():
    """End-to-end on a realistic EP4-shaped input — multiple scenes, mix of
    dialogue + silent beats, shadow + son + mother + enemy + final reveal."""
    raw = _norm("""
        **العنوان: القلادة المقدسة – الحلقة الرابعة**

        **الأسلوب:** ملحمي مظلم
        **الموسيقى:** حزن

        ---

        **المشهد 1 – الفراغ**

        سكون مطلق. الشاب يفتح عيونه.

        **الشاب (بهمس):**
        "أنا… وين…؟"

        ---

        **المشهد 2 – المواجهة**

        **النسخة الأخرى:**
        "كنت مفكر التضحية رح تنقذك؟"

        **الشاب:**
        "مين أنت؟"

        ---

        **المشهد 5 – العودة**

        ساحة المعركة. القلادة تتحرك. ومضة.

        ---

        **المشهد الأخير – الأم**

        **الأم (بهمس):**
        "هلق… صار جاهز."
    """)
    # Note: scene 5 has no dialogue → silent beat
    out = parse_episode_markdown(raw)
    assert out.title == "القلادة المقدسة – الحلقة الرابعة"
    speakers = [b.speaker for b in out.beats]
    # 1 (son) + 2 (shadow, son) + 1 silent scene 5 → default son + 1 (mother)
    # Note "المشهد الأخير" ("the final scene") doesn't have a number, so the
    # scene-num regex won't match — it's NOT counted as a scene. The mother
    # line still appears under scene 5 in this layout.
    assert "shadow" in speakers
    assert "son" in speakers
    assert "mother" in speakers
    # The shadow's exact line preserved
    assert any(b.arabic == "كنت مفكر التضحية رح تنقذك؟" for b in out.beats)


def test_speaker_lookup_strips_parentheticals():
    assert parse_arabic_speaker("الشاب (بهمس)") == "son"
    assert parse_arabic_speaker("الأم (قوي):") == "mother"
    assert parse_arabic_speaker("الكيان") == "enemy"


# ===========================================================================
# English markdown support — was previously broken (regex was Arabic-only)
# ===========================================================================

def test_english_title_recognized():
    raw = _norm("""
        **Title: The Sacred Necklace – Episode 4**

        **Scene 1 – Farewell**

        **Mother:**
        "Don't be afraid"
    """)
    out = parse_episode_markdown(raw)
    assert out.title == "The Sacred Necklace – Episode 4"


def test_english_dialogue_one_beat_per_speaker_line():
    """The bug the user hit: pasting an English script produced only ONE
    beat because the speaker regex required Arabic letters. Now both
    languages parse correctly with one beat per `**SPEAKER:**` block."""
    raw = _norm("""
        **Scene 1 – Farewell**

        **Mother (soft, emotional):**
        "Don't be afraid, my soul… God is with you."

        **Son (smiling):**
        "I'm coming back, Mom… I promise."

        **Mother:**
        "Take this necklace. There's a blessing in it."
    """)
    out = parse_episode_markdown(raw)
    assert [b.speaker for b in out.beats] == ["mother", "son", "mother"]
    assert out.beats[0].arabic.startswith("Don't be afraid")
    assert out.beats[1].arabic == "I'm coming back, Mom… I promise."
    assert out.beats[2].arabic.startswith("Take this necklace")


def test_english_speaker_aliases():
    """English speaker labels with various wordings still resolve to the
    correct internal speaker."""
    cases = [
        ("Young Man", "son"),
        ("the young man", "son"),
        ("Mom", "mother"),
        ("Dad", "father"),
        ("the doctor", "doctor"),
        ("entity", "enemy"),
        ("the entity", "enemy"),
        ("Other Self", "shadow"),
        ("alter ego", "shadow"),
        ("his shadow", "shadow"),
    ]
    for label, expected in cases:
        assert parse_arabic_speaker(label) == expected, \
            f"{label!r} should map to {expected}"


def test_english_scene_headers():
    raw = _norm("""
        **Scene 3 – The Reveal**

        **Father:**
        "I have something to tell you."
    """)
    out = parse_episode_markdown(raw)
    assert len(out.beats) == 1
    # Scene heading is parsed → english_motion mentions the actual scene
    assert "Scene 3" in out.beats[0].english_motion
    assert "The Reveal" in out.beats[0].english_motion


# ===========================================================================
# Per-beat english_motion includes scene-specific stage directions
# ===========================================================================

def test_per_beat_english_motion_includes_scene_stage_directions():
    """The user's complaint: every beat had identical english_motion. Fix:
    each beat now includes the prose that came before its dialogue line,
    so two beats in the same scene get DIFFERENT visual seeds."""
    raw = _norm("""
        **Scene 1 – Farewell**

        Mother stands at the door at sunset, holding her son's face gently.

        **Mother:**
        "Don't be afraid, my soul"

        She slowly removes the necklace from her neck. Hands trembling.

        **Mother:**
        "Take this — there's a blessing in it"
    """)
    out = parse_episode_markdown(raw)
    assert len(out.beats) == 2
    # Both beats are the same speaker but their english_motion must DIFFER —
    # beat 1 sees the doorway-sunset prose, beat 2 sees the necklace-removal
    # prose.
    assert out.beats[0].english_motion != out.beats[1].english_motion
    assert "doorway" in out.beats[0].english_motion.lower() or \
           "door" in out.beats[0].english_motion.lower() or \
           "sunset" in out.beats[0].english_motion.lower()
    assert "necklace" in out.beats[1].english_motion.lower() or \
           "trembling" in out.beats[1].english_motion.lower()


def test_arabic_stage_directions_preserved_in_english_motion():
    """Arabic prose between dialogue blocks is included verbatim in the
    beat's english_motion (Veo will interpret it). Two beats with different
    stage context still get different motions."""
    raw = _norm("""
        **المشهد 1 – بداية**

        الشاب واقف في غرفة مظلمة.

        **الشاب:**
        "أنا هنا"

        فجأة يظهر ضوء قوي. القلادة تلمع.

        **الشاب:**
        "شو هاد"
    """)
    out = parse_episode_markdown(raw)
    assert len(out.beats) == 2
    # Different prose → different motion
    assert out.beats[0].english_motion != out.beats[1].english_motion
    # Beat 1 should reference the dark room
    assert "مظلمة" in out.beats[0].english_motion or \
           "غرفة" in out.beats[0].english_motion
    # Beat 2 should reference the light / glowing necklace
    assert "ضوء" in out.beats[1].english_motion or \
           "تلمع" in out.beats[1].english_motion


def test_silent_beat_motion_uses_scene_prose():
    raw = _norm("""
        **Scene 5 – Silent Battle**

        Massive explosion. Strawberries flying. The young man dodges them.
        Slow motion. Smoke everywhere.
    """)
    out = parse_episode_markdown(raw)
    assert len(out.beats) == 1
    assert out.beats[0].arabic == ""
    motion = out.beats[0].english_motion.lower()
    # The scene's prose appears in the visual seed
    assert "explosion" in motion or "smoke" in motion or "strawberries" in motion


# ===========================================================================
# Mixed English + Arabic (the user's original EP1-3 style)
# ===========================================================================

def test_mixed_english_structure_arabic_dialogue():
    """English scene/title headers + Arabic dialogue — the format used
    in the user's earlier episode scripts."""
    raw = _norm("""
        **Title: The Necklace**

        **Scene 1 – Farewell (sunset)**

        Mother stands at the doorway holding her son's face.

        **Mother:**
        "ما تخاف يا روحي... الله معك"

        **Son:**
        "أنا راجع يا إمي"
    """)
    out = parse_episode_markdown(raw)
    assert out.title == "The Necklace"
    assert len(out.beats) == 2
    assert out.beats[0].speaker == "mother"
    assert out.beats[0].arabic == "ما تخاف يا روحي... الله معك"
    assert out.beats[1].speaker == "son"
    assert out.beats[1].arabic == "أنا راجع يا إمي"
