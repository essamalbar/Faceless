from __future__ import annotations

import pytest

from pipeline.song_scenes import Segment, build_cut_schedule, extract_sections


def _beats(n, step=0.5, start=0.0):
    return [start + i * step for i in range(n)]


def test_extract_sections_pulls_labels_and_starts():
    data = {"audio_duration": 30.0, "lines": [
        {"kind": "section", "text": "Verse 1", "start": 0.0},
        {"kind": "line", "text": "x", "start": 0.5, "end": 1.0},
        {"kind": "section", "text": "Chorus", "start": 8.0},
    ]}
    secs = extract_sections(data)
    assert secs == [{"label": "Verse 1", "start": 0.0},
                    {"label": "Chorus", "start": 8.0}]


def test_cut_every_n_bars_lands_on_beats():
    # 32 beats @ 0.5s = 16s; 4 bars * 4 beats = 16 beats/cut -> cut at beat 0 and 16
    sched = build_cut_schedule(
        beat_times=_beats(32), sections=[{"label": "Verse 1", "start": 0.0}],
        pool_size=4, audio_duration=16.0, bars_per_cut=4, beats_per_bar=4,
    )
    starts = [round(s.start, 3) for s in sched]
    assert starts == [0.0, 8.0]  # beat[0]=0.0, beat[16]=8.0
    assert sched[-1].end == 16.0


def test_chorus_image_recurs():
    sections = [
        {"label": "Verse 1", "start": 0.0},
        {"label": "Chorus", "start": 8.0},
        {"label": "Verse 2", "start": 16.0},
        {"label": "Chorus", "start": 24.0},
    ]
    sched = build_cut_schedule(
        beat_times=[], sections=sections, pool_size=8, audio_duration=32.0,
    )
    # Fallback (no beats) -> one segment per section start.
    img_at = {round(s.start): s.image_idx for s in sched}
    assert img_at[8] == img_at[24]      # both choruses share an image
    assert img_at[0] != img_at[16]      # verse 1 != verse 2


def test_zoom_dir_alternates():
    sched = build_cut_schedule(
        beat_times=_beats(48), sections=[{"label": "Verse 1", "start": 0.0}],
        pool_size=2, audio_duration=24.0, bars_per_cut=2, beats_per_bar=4,
    )
    dirs = [s.zoom_dir for s in sched]
    assert dirs[0] == "in" and dirs[1] == "out"
    assert all(d in ("in", "out") for d in dirs)


def test_short_segments_merged():
    # A trailing beat that would create a <0.6s sliver folds into the prior segment.
    sched = build_cut_schedule(
        beat_times=[0.0, 8.0, 15.9], sections=[{"label": "Verse 1", "start": 0.0}],
        pool_size=2, audio_duration=16.0, bars_per_cut=1, beats_per_bar=1,
        min_segment_s=0.6,
    )
    assert all((s.end - s.start) >= 0.6 for s in sched)
    assert sched[-1].end == 16.0


def test_empty_beats_fall_back_to_sections():
    sections = [{"label": "Verse 1", "start": 0.0}, {"label": "Chorus", "start": 10.0}]
    sched = build_cut_schedule(
        beat_times=[], sections=sections, pool_size=4, audio_duration=20.0,
    )
    assert [round(s.start) for s in sched] == [0, 10]


def test_pool_smaller_than_sections_cycles():
    sections = [{"label": f"Verse {i}", "start": float(i * 5)} for i in range(5)]
    sched = build_cut_schedule(
        beat_times=[], sections=sections, pool_size=2, audio_duration=25.0,
    )
    assert all(0 <= s.image_idx < 2 for s in sched)
    assert [s.image_idx for s in sched] == [0, 1, 0, 1, 0]


def test_single_section_song():
    sched = build_cut_schedule(
        beat_times=_beats(16), sections=[{"label": "Verse 1", "start": 0.0}],
        pool_size=1, audio_duration=8.0, bars_per_cut=4, beats_per_bar=4,
    )
    assert all(s.image_idx == 0 for s in sched)
    assert sched[-1].end == 8.0


def test_segment_cap_enforced():
    sched = build_cut_schedule(
        beat_times=_beats(2000, step=0.1), sections=[{"label": "V", "start": 0.0}],
        pool_size=4, audio_duration=200.0, bars_per_cut=1, beats_per_bar=1,
        max_segments=60,
    )
    assert len(sched) <= 60
    assert sched[-1].end == 200.0


def test_pool_size_zero_raises():
    with pytest.raises(ValueError):
        build_cut_schedule(beat_times=[], sections=[], pool_size=0, audio_duration=5.0)


def test_zoom_dir_alternates_after_coarsen():
    # 2000 beats * 0.5s = 1000s of beats; audio_duration=200.0 so ~400 segs survive.
    # min_segment_s=0.4 < 0.5s beat step, so nothing merges; _coarsen folds to 5.
    # zoom must alternate by FINAL index, not pre-merge boundary index.
    sched = build_cut_schedule(
        beat_times=_beats(2000, step=0.5), sections=[{"label": "V", "start": 0.0}],
        pool_size=4, audio_duration=200.0, bars_per_cut=1, beats_per_bar=1,
        min_segment_s=0.4, max_segments=5,
    )
    dirs = [s.zoom_dir for s in sched]
    assert dirs == ["in", "out", "in", "out", "in"]


def test_extract_sections_drops_unaligned():
    data = {"lines": [
        {"kind": "section", "text": "Verse 1", "start": None},
        {"kind": "section", "text": "Chorus", "start": 4.0},
    ]}
    assert extract_sections(data) == [{"label": "Chorus", "start": 4.0}]


def test_non_positive_duration_raises():
    with pytest.raises(ValueError):
        build_cut_schedule(beat_times=[], sections=[], pool_size=2, audio_duration=0.0)
