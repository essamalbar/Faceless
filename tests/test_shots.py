"""Scene splitter tests."""
from __future__ import annotations

import json
from pathlib import Path

from pipeline.shots import (
    NEGATIVE_PROMPT,
    STYLE_SUFFIX,
    chunk_by_timing,
    generate_shots,
)
from pipeline.types import Script, WordTiming


def _wt(word: str, offset: int, duration: int = 400) -> WordTiming:
    return WordTiming(word=word, offset_ms=offset, duration_ms=duration)


def test_chunk_targets_15_20_seconds():
    timings = [_wt("w", i * 500) for i in range(80)]  # 80 words × 500ms = 40s
    chunks = chunk_by_timing(timings, target_ms=18000, sentence_ends=set())
    # 40s / 18s ≈ 2-3 chunks
    assert 2 <= len(chunks) <= 3
    for c in chunks:
        assert c["end_ms"] - c["start_ms"] <= 25_000  # honored upper bound roughly


def test_chunk_snaps_to_sentence_end():
    timings = [_wt(str(i), i * 1000) for i in range(20)]
    sentence_ends = {5, 12}  # word indices where sentences end
    chunks = chunk_by_timing(timings, target_ms=8000, sentence_ends=sentence_ends)
    end_indices = [c["last_word_index"] for c in chunks]
    # Boundaries must align with sentence ends (the last chunk ends at the last word)
    for idx in end_indices[:-1]:
        assert idx in sentence_ends


def test_seed_assignment_deterministic_per_title():
    from pipeline.shots import shot_seed
    s1 = shot_seed("a-title", index=0)
    s2 = shot_seed("a-title", index=0)
    s3 = shot_seed("a-title", index=1)
    s4 = shot_seed("other", index=0)
    assert s1 == s2
    assert s1 != s3
    assert s1 != s4


def test_generate_shots_writes_shots_json(fake_gemini, tmp_run_dir: Path):
    script = Script(
        title="بئر قديم", theme="folkloric",
        global_setting="abandoned village, night, desert",
        music_mood="dread",
        hook="الفقرة الأولى. الفقرة الثانية.",
        story="فقرة1.\n\nفقرة2. فقرة3.",
        word_count=6,
    )
    timings = [
        _wt("الفقرة1", 0), _wt(".", 500),
        _wt("الفقرة2", 1000), _wt(".", 1500),
        _wt("الفقرة3", 2000), _wt(".", 2500),
    ]
    # New batched API: one Gemini call returns a JSON array of N prompts.
    # The fake responds to the batch-translate image prompt (identified by the
    # stable phrase "image prompt") with a JSON array large enough to cover any
    # plausible chunk count for this short timing input.
    fake_gemini.when(
        lambda p: "image prompt" in p.lower(),
        json.dumps(["lone figure on a moonlit dune"] * 10),
    )
    out = tmp_run_dir / "shots.json"
    generate_shots(
        gemini=fake_gemini,
        script=script,
        timings=timings,
        out_path=out,
        target_segment_ms=2000,
    )
    data = json.loads(out.read_text())
    assert len(data) >= 1
    first = data[0]
    assert "lone figure" in first["english_prompt"]
    assert STYLE_SUFFIX.split(",")[0] in first["english_prompt"]  # suffix appended
    assert first["negative_prompt"] == NEGATIVE_PROMPT
    assert first["seed"] != 0
    # New invariant: only ONE Gemini call regardless of chunk count.
    assert len(fake_gemini.complete_calls) == 1


def test_generate_shots_skips_if_exists(fake_gemini, tmp_run_dir: Path):
    out = tmp_run_dir / "shots.json"
    out.write_text("[]")  # already exists
    script = Script(
        title="t", theme="folkloric", global_setting="x",
        music_mood="dread", hook="h", story="s", word_count=1,
    )
    generate_shots(
        gemini=fake_gemini, script=script,
        timings=[_wt("x", 0)],
        out_path=out, target_segment_ms=18000,
    )
    assert fake_gemini.complete_calls == []  # skipped
