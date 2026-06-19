from __future__ import annotations

import pytest

import pipeline.song_import as si
from pipeline.song_import import ImportFetchError, download_audio


def test_download_audio_returns_path(tmp_path, monkeypatch):
    # Fake yt-dlp: pretend it wrote the output file.
    out = tmp_path / "reference.m4a"
    def fake_run(url, out_template):
        out.write_bytes(b"\x00\x00")  # stand-in audio bytes
        return str(out)
    monkeypatch.setattr(si, "_ytdlp_download", fake_run)
    p = download_audio("https://www.youtube.com/watch?v=abc123", tmp_path)
    assert p.exists() and p.name == "reference.m4a"


def test_download_audio_raises_clear_error(tmp_path, monkeypatch):
    def boom(url, out_template):
        raise RuntimeError("Video unavailable")
    monkeypatch.setattr(si, "_ytdlp_download", boom)
    with pytest.raises(ImportFetchError):
        download_audio("https://youtu.be/abc123", tmp_path)


from pipeline.song_import import _ngram_overlap


def test_ngram_overlap_detects_near_copy():
    src = "alpha beta gamma delta epsilon zeta eta theta"
    # Same 8 words -> all 4-grams overlap -> 1.0
    assert _ngram_overlap(src, src) == 1.0


def test_ngram_overlap_distinct_is_low():
    src = "alpha beta gamma delta epsilon zeta eta theta"
    new = "one two three four five six seven eight"
    assert _ngram_overlap(new, src) == 0.0


def test_ngram_overlap_empty_is_zero():
    assert _ngram_overlap("", "anything here at all") == 0.0
    assert _ngram_overlap("too short", "x y z a b c", n=4) == 0.0


from pipeline.song_import import analyze_reference


class _FakeLLM:
    def __init__(self, payload):
        self._payload = payload
    def complete(self, prompt, system=None):
        import json
        return json.dumps(self._payload, ensure_ascii=False)


_DESC = {
    "genre": "Arabic pop ballad",
    "mood": "melancholic",
    "instrumentation": "oud, strings, light percussion",
    "language": "ar",
    "one_line_theme": "longing for a distant home",
    "section_structure": "Verse, Pre-Chorus, Chorus, Verse, Chorus, Bridge, Chorus",
}


def test_analyze_reference_returns_descriptors_and_transcript(tmp_path, monkeypatch):
    import pipeline.song_import as si
    audio = tmp_path / "reference.m4a"; audio.write_bytes(b"\x00")
    monkeypatch.setattr(si, "_detect_bpm", lambda p: 92.0)
    monkeypatch.setattr(si, "_transcribe", lambda p, language: "la la la one two three")
    desc, transcript = analyze_reference(audio, llm=_FakeLLM(_DESC), language="ar")
    assert desc["bpm"] == 92.0
    assert desc["one_line_theme"] == "longing for a distant home"
    assert transcript == "la la la one two three"


def test_analyze_reference_degrades_when_transcription_fails(tmp_path, monkeypatch):
    import pipeline.song_import as si
    audio = tmp_path / "reference.m4a"; audio.write_bytes(b"\x00")
    monkeypatch.setattr(si, "_detect_bpm", lambda p: 0.0)
    def boom(p, language):
        raise RuntimeError("whisper failed")
    monkeypatch.setattr(si, "_transcribe", boom)
    payload = dict(_DESC); payload["one_line_theme"] = None
    desc, transcript = analyze_reference(audio, llm=_FakeLLM(payload), language="ar")
    assert transcript == ""
    assert desc["one_line_theme"] is None


from pipeline.song_import import build_inspired_script, OVERLAP_THRESHOLD
import pipeline.song_import as si2
from pipeline.song_lyrics import SongScript


def _script(lyrics):
    return SongScript(title="t", lyrics=lyrics, style_prompt="pop, 90 BPM",
                      cover_prompt="c", language="ar",
                      art_direction="moonlit", scene_prompts=["a", "b"])


def test_build_inspired_script_passes_clean_output(monkeypatch):
    calls = {"n": 0}
    def fake_gen(**kw):
        calls["n"] += 1
        return _script("[Verse 1]\nfresh original words\n\n[Chorus]\nbrand new hook\n")
    monkeypatch.setattr(si2, "generate_song_script", fake_gen)
    s = build_inspired_script(
        llm=object(),
        analysis={"genre": "pop", "bpm": 90, "mood": "sad",
                  "instrumentation": "oud", "one_line_theme": "loss"},
        instruction="make it Gulf dialect",
        language="ar",
        transcript="totally different reference words here please",
    )
    assert "[Chorus]" in s.lyrics
    assert calls["n"] == 1   # no regeneration needed


def test_build_inspired_script_regenerates_on_near_copy(monkeypatch):
    src = "one two three four five six seven eight nine ten"
    outputs = [
        _script("one two three four five six seven eight nine ten"),  # near-copy
        _script("[Verse 1]\nwholly distinct alpha bravo charlie\n[Chorus]\ndelta echo\n"),
    ]
    calls = {"n": 0}
    def fake_gen(**kw):
        out = outputs[min(calls["n"], len(outputs) - 1)]
        calls["n"] += 1
        return out
    monkeypatch.setattr(si2, "generate_song_script", fake_gen)
    s = build_inspired_script(
        llm=object(),
        analysis={"genre": "pop", "bpm": 90, "mood": "sad",
                  "instrumentation": "oud", "one_line_theme": "loss"},
        instruction=None, language="ar", transcript=src,
    )
    assert calls["n"] == 2          # regenerated once after the near-copy
    assert "alpha bravo charlie" in s.lyrics
