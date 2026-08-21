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
