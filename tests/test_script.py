"""Script writer tests — first pass only."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline.script import build_writer_prompt, generate_script_first_pass
from pipeline.types import Script, ThemeSeed


def test_writer_prompt_includes_seed_and_constraints():
    seed = ThemeSeed(theme="folkloric", premise="بئر قديم")
    p = build_writer_prompt(seed, target_words=2200, tolerance=200)
    assert "بئر قديم" in p
    assert "folkloric" in p
    assert "2200" in p or "2,200" in p
    assert "ضمير المتكلم" in p
    assert "MSA" in p or "الفصحى" in p


def test_first_pass_parses_valid_json(fake_gemini):
    seed = ThemeSeed(theme="folkloric", premise="بئر قديم")
    fake_gemini.when(lambda p: "بئر قديم" in p, json.dumps({
        "title": "بئر",
        "theme": "folkloric",
        "global_setting": "مدينة فجر, شتاء",
        "music_mood": "dread",
        "hook": "افتتاح",
        "story": "نص" * 1100,
        "word_count": 2200,
    }, ensure_ascii=False))
    s = generate_script_first_pass(fake_gemini, seed, target_words=2200, tolerance=200)
    assert isinstance(s, Script)
    assert s.title == "بئر"


def test_first_pass_overrides_theme_to_match_seed(fake_gemini):
    """If Gemini returns a different theme tag, we trust the seed."""
    seed = ThemeSeed(theme="folkloric", premise="بئر")
    fake_gemini.when(lambda p: True, json.dumps({
        "title": "x", "theme": "domestic",  # WRONG theme returned
        "global_setting": "x", "music_mood": "drone",
        "hook": "x", "story": "x" * 100, "word_count": 100,
    }, ensure_ascii=False))
    s = generate_script_first_pass(fake_gemini, seed, target_words=100, tolerance=10)
    assert s.theme == "folkloric"  # corrected to match seed


def test_first_pass_strips_markdown_code_fence(fake_gemini):
    """Gemini sometimes wraps JSON in ```json ... ``` fences."""
    seed = ThemeSeed(theme="folkloric", premise="x")
    payload = json.dumps({
        "title": "x", "theme": "folkloric", "global_setting": "x",
        "music_mood": "drone", "hook": "x", "story": "y" * 100, "word_count": 100,
    }, ensure_ascii=False)
    fake_gemini.when(lambda p: True, f"```json\n{payload}\n```")
    s = generate_script_first_pass(fake_gemini, seed, target_words=100, tolerance=10)
    assert s.title == "x"


def test_first_pass_raises_on_invalid_json(fake_gemini):
    seed = ThemeSeed(theme="folkloric", premise="x")
    fake_gemini.when(lambda p: True, "this is not json")
    with pytest.raises(ValueError):
        generate_script_first_pass(fake_gemini, seed, target_words=100, tolerance=10)


def test_critique_pass_revises_when_flagged(fake_gemini):
    seed = ThemeSeed(theme="folkloric", premise="x")
    draft = Script(
        title="t", theme="folkloric", global_setting="x",
        music_mood="dread", hook="weak", story="y" * 100, word_count=100,
    )
    revised_payload = json.dumps({
        "title": "t-revised", "theme": "folkloric", "global_setting": "x",
        "music_mood": "dread", "hook": "stronger hook", "story": "z" * 100,
        "word_count": 100,
    }, ensure_ascii=False)
    fake_gemini.when(lambda p: "نقد" in p or "critique" in p.lower(), revised_payload)

    from pipeline.script import critique_pass
    out = critique_pass(fake_gemini, seed, draft)
    assert out.title == "t-revised"
    assert out.hook == "stronger hook"


def test_generate_script_full_pipeline_with_critique(fake_gemini):
    """End-to-end: first pass + critique pass."""
    seed = ThemeSeed(theme="folkloric", premise="بئر")
    first = json.dumps({
        "title": "v1", "theme": "folkloric", "global_setting": "x",
        "music_mood": "dread", "hook": "h", "story": "s" * 100, "word_count": 100,
    }, ensure_ascii=False)
    second = json.dumps({
        "title": "v2", "theme": "folkloric", "global_setting": "x",
        "music_mood": "dread", "hook": "h2", "story": "s" * 100, "word_count": 100,
    }, ensure_ascii=False)
    # First call returns first; second (critique) returns second.
    seq = [first, second]
    fake_gemini.when(lambda p: bool(seq), "")  # placeholder; we override below

    # Replace responses list with a sequencer
    fake_gemini._responses.clear()
    def sequencer(prompt: str):
        return seq.pop(0) if seq else None
    fake_gemini._responses.append(sequencer)

    from pipeline.script import generate_script
    out = generate_script(fake_gemini, seed, target_words=100, tolerance=10, enable_critique=True)
    assert out.title == "v2"


def test_generate_script_skips_critique_when_disabled(fake_gemini):
    seed = ThemeSeed(theme="folkloric", premise="بئر")
    fake_gemini.when(lambda p: True, json.dumps({
        "title": "v1", "theme": "folkloric", "global_setting": "x",
        "music_mood": "dread", "hook": "h", "story": "s" * 100, "word_count": 100,
    }, ensure_ascii=False))
    from pipeline.script import generate_script
    out = generate_script(fake_gemini, seed, target_words=100, tolerance=10, enable_critique=False)
    assert out.title == "v1"
    assert len(fake_gemini.complete_calls) == 1  # only first pass


def test_cosine_similarity():
    from pipeline.script import _cosine
    assert abs(_cosine([1, 0], [1, 0]) - 1.0) < 1e-9
    assert abs(_cosine([1, 0], [0, 1])) < 1e-9
    assert abs(_cosine([1, 0], [-1, 0]) + 1.0) < 1e-9


def test_repetition_guard_appends_when_unique(fake_gemini, tmp_path: Path):
    from pipeline.script import check_and_record_uniqueness

    # No history file → unique by default
    fake_gemini.set_embedding("story text", [1.0, 0.0, 0.0])
    history = tmp_path / "story_history.jsonl"

    is_unique, similarity = check_and_record_uniqueness(
        fake_gemini, "story text", history, threshold=0.85,
    )
    assert is_unique is True
    assert similarity == 0.0
    assert history.exists()
    line = history.read_text().strip()
    assert "[1.0" in line


def test_repetition_guard_rejects_when_too_similar(fake_gemini, tmp_path: Path):
    from pipeline.script import check_and_record_uniqueness
    history = tmp_path / "story_history.jsonl"
    history.write_text(json.dumps({"embedding": [1.0, 0.0, 0.0], "ts": "2026-04-30"}) + "\n")
    fake_gemini.set_embedding("near-dup", [0.99, 0.01, 0.0])  # cos ≈ 1.0

    is_unique, similarity = check_and_record_uniqueness(
        fake_gemini, "near-dup", history, threshold=0.85,
    )
    assert is_unique is False
    assert similarity > 0.85


def test_run_full_regenerates_on_repetition(fake_gemini, tmp_path: Path):
    """End-to-end: first attempt is too similar → regenerate, second succeeds."""
    seed = ThemeSeed(theme="folkloric", premise="x")

    # Two distinct payloads. Embeddings: first matches history, second is distant.
    payload_a = json.dumps({
        "title": "a", "theme": "folkloric", "global_setting": "x",
        "music_mood": "dread", "hook": "h", "story": "story-a" * 20, "word_count": 100,
    }, ensure_ascii=False)
    payload_b = json.dumps({
        "title": "b", "theme": "folkloric", "global_setting": "x",
        "music_mood": "dread", "hook": "h", "story": "story-b" * 20, "word_count": 100,
    }, ensure_ascii=False)

    seq = [payload_a, payload_b]
    fake_gemini._responses.clear()
    fake_gemini._responses.append(lambda p: seq.pop(0) if seq else None)

    fake_gemini.set_embedding("story-a" * 20, [1.0, 0.0])
    fake_gemini.set_embedding("story-b" * 20, [0.0, 1.0])

    history = tmp_path / "story_history.jsonl"
    history.write_text(json.dumps({"embedding": [1.0, 0.0], "ts": "p"}) + "\n")

    from pipeline.script import generate_script_with_uniqueness
    out = generate_script_with_uniqueness(
        fake_gemini, seed,
        target_words=100, tolerance=10,
        enable_critique=False,
        history_path=history,
        repetition_threshold=0.85,
        max_attempts=3,
    )
    assert out.title == "b"


# ============================================================================
# Shorts mode tests
# ============================================================================

def test_shorts_prompt_includes_seed_and_beat_count():
    from pipeline.script import build_shorts_writer_prompt
    seed = ThemeSeed(theme="folkloric", premise="بئر قديم")
    p = build_shorts_writer_prompt(seed, min_beats=1, max_beats=20, words_per_beat=20)
    assert "بئر قديم" in p
    assert "folkloric" in p
    assert "1" in p  # min_beats present
    assert "20" in p  # max_beats present
    # Confirm @sunstoriz-style constraints are present
    assert "ميلودراما" in p or "مأساوية" in p  # tragic-family-drama theme
    assert "FRUIT" in p                          # anthropomorphic fruit characters
    assert "english_motion" in p


def test_shorts_parse_valid_response(fake_gemini):
    from pipeline.script import generate_shorts_script
    seed = ThemeSeed(theme="folkloric", premise="بئر")
    fake_gemini.when(lambda p: True, json.dumps({
        "title": "صدى البئر",
        "theme": "folkloric",
        "global_setting": "abandoned village, night, desert",
        "music_mood": "dread",
        "beats": [
            {"arabic": "كنتُ وحيداً عند البئر.", "english_motion": "lone hooded figure beside ancient well, slow push-in, moonlight", "speaker": "mother"},
            {"arabic": "سمعتُ بكاءً في الأعماق.", "english_motion": "close-up of dark well shaft, mist, faint glow rising", "speaker": "mother"},
            {"arabic": "ظهرتْ يدٌ عظمية.", "english_motion": "skeletal hand emerging from well rim, low angle, candlelight flicker", "speaker": "son"},
            {"arabic": "ثم اختفى كل شيء.", "english_motion": "wide shot of empty village, fog rolling in, static camera", "speaker": "mother"},
        ],
    }, ensure_ascii=False))
    s = generate_shorts_script(fake_gemini, seed, min_beats=1, max_beats=20)
    assert s.title == "صدى البئر"
    assert len(s.beats) == 4
    assert s.beats[0].arabic == "كنتُ وحيداً عند البئر."
    assert "push-in" in s.beats[0].english_motion
    assert s.story_combined.startswith("كنتُ وحيداً")
    # All four arabic strings concatenated
    assert "اختفى كل شيء" in s.story_combined
    # Long-form fields stay empty
    assert s.story == ""
    assert s.hook == ""


def test_shorts_overrides_theme_to_match_seed(fake_gemini):
    from pipeline.script import generate_shorts_script
    seed = ThemeSeed(theme="folkloric", premise="x")
    # Gemini returns wrong theme — we must force it back to seed.theme
    fake_gemini.when(lambda p: True, json.dumps({
        "title": "x", "theme": "domestic",  # WRONG
        "global_setting": "x", "music_mood": "drone",
        "beats": [{"arabic": "ج1", "english_motion": "m1", "speaker": "mother"}],
    }, ensure_ascii=False))
    s = generate_shorts_script(fake_gemini, seed, min_beats=1, max_beats=20)
    assert s.theme == "folkloric"


def test_shorts_normalizes_sloppy_music_mood(fake_gemini):
    from pipeline.script import generate_shorts_script
    seed = ThemeSeed(theme="folkloric", premise="x")
    fake_gemini.when(lambda p: True, json.dumps({
        "title": "x", "theme": "folkloric", "global_setting": "x",
        "music_mood": "drone | dread | cosmic | discovery",  # sloppy LLM output
        "beats": [{"arabic": "ج1", "english_motion": "m1", "speaker": "mother"}],
    }, ensure_ascii=False))
    s = generate_shorts_script(fake_gemini, seed, min_beats=1, max_beats=20)
    assert s.music_mood == "drone"  # normalizer extracts first valid mood


def test_shorts_rejects_empty_beats(fake_gemini):
    from pipeline.script import generate_shorts_script
    seed = ThemeSeed(theme="folkloric", premise="x")
    fake_gemini.when(lambda p: True, json.dumps({
        "title": "x", "theme": "folkloric", "global_setting": "x",
        "music_mood": "dread", "beats": [],
    }, ensure_ascii=False))
    with pytest.raises(ValueError, match="non-empty 'beats'"):
        generate_shorts_script(fake_gemini, seed, min_beats=1, max_beats=20)


def test_shorts_rejects_beat_missing_field(fake_gemini):
    from pipeline.script import generate_shorts_script
    seed = ThemeSeed(theme="folkloric", premise="x")
    fake_gemini.when(lambda p: True, json.dumps({
        "title": "x", "theme": "folkloric", "global_setting": "x",
        "music_mood": "dread",
        "beats": [{"arabic": "only arabic", "speaker": "mother"}],  # missing english_motion
    }, ensure_ascii=False))
    with pytest.raises(ValueError, match="missing"):
        generate_shorts_script(fake_gemini, seed, min_beats=1, max_beats=20)


def test_shorts_strips_code_fence(fake_gemini):
    """Gemini sometimes wraps output in ```json ... ```."""
    from pipeline.script import generate_shorts_script
    seed = ThemeSeed(theme="folkloric", premise="x")
    payload = json.dumps({
        "title": "x", "theme": "folkloric", "global_setting": "x",
        "music_mood": "dread",
        "beats": [{"arabic": "ج", "english_motion": "m", "speaker": "mother"}],
    }, ensure_ascii=False)
    fake_gemini.when(lambda p: True, f"```json\n{payload}\n```")
    s = generate_shorts_script(fake_gemini, seed, min_beats=1, max_beats=20)
    assert len(s.beats) == 1


def test_shorts_writer_picks_num_beats_in_range(fake_gemini):
    """Writer chooses 8-15 beats based on premise; orchestrator reads len(script.beats)."""
    from pipeline.script import generate_shorts_script
    seed = ThemeSeed(theme="folkloric", premise="x")
    fake_gemini.when(lambda p: True, json.dumps({
        "title": "long tragedy",
        "theme": "folkloric",
        "global_setting": "x",
        "music_mood": "dread",
        "target_duration_s": 100,
        "beats": [
            {"arabic": "ج" + str(i), "english_motion": "m",
             "clip_duration_s": 8.5, "speaker": "mother"}
            for i in range(12)
        ],
    }, ensure_ascii=False))
    s = generate_shorts_script(fake_gemini, seed, min_beats=8, max_beats=15,
                                words_per_beat=30)
    assert len(s.beats) == 12
    assert s.target_duration_s == 100
    assert s.beats[0].clip_duration_s == 8.5


def test_shorts_rejects_narrator_speaker(fake_gemini):
    """Every beat must be a CHARACTER speaking, not a third-person narrator.
    The user explicitly said the script must be the people inside the video
    talking — not an external voiceover."""
    from pipeline.script import generate_shorts_script
    seed = ThemeSeed(theme="folkloric", premise="x")
    fake_gemini.when(lambda p: True, json.dumps({
        "title": "x", "theme": "folkloric", "global_setting": "x",
        "music_mood": "dread",
        "beats": [
            {"arabic": "ج1", "english_motion": "m1", "speaker": "mother"},
            {"arabic": "ج2", "english_motion": "m2", "speaker": "narrator"},  # NOT ALLOWED
        ],
    }, ensure_ascii=False))
    with pytest.raises(ValueError, match="invalid speaker"):
        generate_shorts_script(fake_gemini, seed, min_beats=1, max_beats=20)


def test_shorts_rejects_missing_speaker(fake_gemini):
    """Beats without a `speaker` field are rejected — the writer must label every line."""
    from pipeline.script import generate_shorts_script
    seed = ThemeSeed(theme="folkloric", premise="x")
    fake_gemini.when(lambda p: True, json.dumps({
        "title": "x", "theme": "folkloric", "global_setting": "x",
        "music_mood": "dread",
        "beats": [{"arabic": "ج1", "english_motion": "m1"}],  # no speaker
    }, ensure_ascii=False))
    with pytest.raises(ValueError, match="invalid speaker"):
        generate_shorts_script(fake_gemini, seed, min_beats=1, max_beats=20)


def test_shorts_writer_clamps_to_min_beats_when_too_few(fake_gemini):
    """If LLM returns < min_beats, raise — that's a serious failure not silent fallback."""
    from pipeline.script import generate_shorts_script
    import pytest
    seed = ThemeSeed(theme="folkloric", premise="x")
    fake_gemini.when(lambda p: True, json.dumps({
        "title": "x", "theme": "folkloric", "global_setting": "x",
        "music_mood": "dread",
        "beats": [
            {"arabic": f"ج{i}", "english_motion": "m", "speaker": "mother"}
            for i in range(5)
        ],
    }, ensure_ascii=False))
    with pytest.raises(ValueError, match="below min_beats"):
        generate_shorts_script(fake_gemini, seed, min_beats=8, max_beats=15)


def test_shorts_parser_reads_character_name():
    """When the writer returns character_name on each beat, it appears on Beat."""
    from pipeline.script import _parse_shorts_script_json
    from pipeline.types import ThemeSeed
    raw = '''{
      "title": "t", "theme": "folkloric",
      "global_setting": "g", "music_mood": "dread",
      "target_duration_s": 16,
      "beats": [
        {"arabic":"x","english_motion":"y","clip_duration_s":8,"speaker":"mother","character_name":"أم خالد"},
        {"arabic":"x","english_motion":"y","clip_duration_s":8,"speaker":"son","character_name":"خالد"}
      ]
    }'''
    seed = ThemeSeed(theme="folkloric", premise="x")
    script = _parse_shorts_script_json(raw, seed)
    assert script.beats[0].character_name == "أم خالد"
    assert script.beats[1].character_name == "خالد"


def test_shorts_parser_legacy_omits_character_name():
    """Legacy LLM responses without character_name still parse — default ''."""
    from pipeline.script import _parse_shorts_script_json
    from pipeline.types import ThemeSeed
    raw = '''{
      "title": "t", "theme": "folkloric",
      "global_setting": "g", "music_mood": "dread",
      "target_duration_s": 8,
      "beats": [{"arabic":"x","english_motion":"y","clip_duration_s":8,"speaker":"mother"}]
    }'''
    script = _parse_shorts_script_json(raw, ThemeSeed(theme="folkloric", premise="x"))
    assert script.beats[0].character_name == ""


def test_writer_prompt_mentions_character_name():
    """The Sunstoriz writer prompt instructs the LLM to pick consistent
    Arabic character names per speaker."""
    from pipeline.script import build_shorts_writer_prompt
    from pipeline.types import ThemeSeed
    p = build_shorts_writer_prompt(ThemeSeed(theme="folkloric", premise="x"))
    # The prompt must reference the new field by its JSON key
    assert "character_name" in p
