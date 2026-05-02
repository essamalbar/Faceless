"""Voice generator tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline.voice import generate_narration, inject_ssml_pauses


def test_inject_ssml_period_no_break():
    """Periods are NOT padded with SSML breaks (TTS handles them naturally)."""
    out = inject_ssml_pauses("جملة أولى. جملة ثانية.")
    assert "<break" not in out
    # Period itself preserved (downstream uses it for sentence-end detection)
    assert "." in out


def test_inject_ssml_ellipsis():
    out = inject_ssml_pauses("جملة... ثم")
    assert "<break time=\"400ms\"/>" in out


def test_inject_ssml_paragraph():
    out = inject_ssml_pauses("فقرة1\n\nفقرة2")
    assert "<break time=\"600ms\"/>" in out


def test_generate_narration_writes_outputs(monkeypatch, tmp_run_dir: Path, fixtures_dir: Path):
    """`_synthesize` is replaced with a fake that writes a known fixture."""
    sample_mp3 = (fixtures_dir / "narration_sample.mp3").read_bytes()
    fake_timings = [
        {"word": "كنت", "offset_ms": 0, "duration_ms": 480},
        {"word": "أسير", "offset_ms": 510, "duration_ms": 620},
    ]

    def fake_synthesize(text, voice, rate, pitch, mp3_path: Path):
        mp3_path.write_bytes(sample_mp3)
        return fake_timings

    monkeypatch.setattr("pipeline.voice._synthesize", fake_synthesize)

    out_mp3 = tmp_run_dir / "narration.mp3"
    out_timings = tmp_run_dir / "word_timings.json"
    generate_narration(
        text="كنت أسير.",
        voice="ar-SA-HamedNeural", rate="-20%", pitch="-5%",
        mp3_path=out_mp3, timings_path=out_timings,
    )
    assert out_mp3.exists() and out_mp3.stat().st_size > 0
    timings = json.loads(out_timings.read_text())
    assert timings[0]["word"] == "كنت"
    assert len(timings) == 2


def test_generate_narration_skips_if_already_exists(monkeypatch, tmp_run_dir: Path, fixtures_dir: Path):
    """Resumability: if both files exist, synthesize is not called."""
    sample_mp3 = (fixtures_dir / "narration_sample.mp3").read_bytes()
    out_mp3 = tmp_run_dir / "narration.mp3"
    out_timings = tmp_run_dir / "word_timings.json"
    out_mp3.write_bytes(sample_mp3)
    out_timings.write_text(json.dumps([{"word": "x", "offset_ms": 0, "duration_ms": 100}]))

    called = {"count": 0}
    def fake_synthesize(*a, **kw):
        called["count"] += 1
        return []
    monkeypatch.setattr("pipeline.voice._synthesize", fake_synthesize)

    generate_narration(
        text="...",
        voice="x", rate="0%", pitch="0%",
        mp3_path=out_mp3, timings_path=out_timings,
    )
    assert called["count"] == 0


def test_synthesize_retries_then_succeeds(monkeypatch, tmp_path: Path):
    """The internal _synthesize retries transient edge-tts failures."""
    from pipeline import voice as voice_mod

    attempts = {"n": 0}

    def flaky_run(text, voice, rate, pitch, mp3_path):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RuntimeError("transient")
        mp3_path.write_bytes(b"\x00")
        return [{"word": "ok", "offset_ms": 0, "duration_ms": 100}]

    async def fake_run(*a, **kw):
        return flaky_run(*a, **kw)

    monkeypatch.setattr(voice_mod, "_edge_tts_run", fake_run)
    monkeypatch.setattr(voice_mod, "_SLEEP", lambda _s: None)

    out = tmp_path / "n.mp3"
    timings = voice_mod._synthesize("hi", "v", "0%", "0%", out)
    assert attempts["n"] == 3
    assert timings[0]["word"] == "ok"


def test_synthesize_raises_after_max_retries(monkeypatch, tmp_path: Path):
    from pipeline import voice as voice_mod

    async def always_fail(*a, **kw):
        raise RuntimeError("permanent")

    monkeypatch.setattr(voice_mod, "_edge_tts_run", always_fail)
    monkeypatch.setattr(voice_mod, "_SLEEP", lambda _s: None)

    with pytest.raises(RuntimeError, match="edge-tts failed"):
        voice_mod._synthesize("hi", "v", "0%", "0%", tmp_path / "n.mp3")


def test_generate_narration_dispatches_to_elevenlabs(monkeypatch, tmp_run_dir: Path,
                                                       fixtures_dir: Path):
    """provider='elevenlabs' must call ElevenLabsClient.synthesize, not edge-tts."""
    sample = (fixtures_dir / "narration_sample.mp3").read_bytes()
    captured: dict = {}

    class FakeEL:
        def synthesize(self, text, voice_id, model, out_path, **kw):
            captured["text"] = text
            captured["voice_id"] = voice_id
            captured["out"] = out_path
            out_path.write_bytes(sample)

    monkeypatch.setattr("pipeline.voice._build_elevenlabs", lambda: FakeEL())

    out_mp3 = tmp_run_dir / "narration.mp3"
    out_timings = tmp_run_dir / "word_timings.json"
    from pipeline.voice import generate_narration
    generate_narration(
        text="مرحبا",
        voice="ar-EG-SalmaNeural", rate="+0%", pitch="+0Hz",
        mp3_path=out_mp3, timings_path=out_timings,
        provider="elevenlabs",
        elevenlabs_voice_id="vid-1",
        elevenlabs_model="eleven_multilingual_v2",
    )
    assert out_mp3.exists()
    assert captured["voice_id"] == "vid-1"
    assert captured["text"] == "مرحبا"
    # Synthetic timings still written (Whisper align stage refines them later)
    import json
    timings = json.loads(out_timings.read_text(encoding="utf-8"))
    assert len(timings) >= 1


def test_generate_narration_falls_back_to_edge_tts_when_no_eleven_key(
    monkeypatch, tmp_run_dir: Path, fixtures_dir: Path,
):
    """provider='elevenlabs' but no key → fall back to edge_tts when fallback=True."""
    sample = (fixtures_dir / "narration_sample.mp3").read_bytes()

    def fake_build_el():
        from pipeline.elevenlabs import ElevenLabsError
        raise ElevenLabsError("ELEVENLABS_API_KEY not set")

    def fake_edge(text, voice, rate, pitch, mp3_path):
        mp3_path.write_bytes(sample)
        return [{"word": "ك", "offset_ms": 0, "duration_ms": 100}]

    monkeypatch.setattr("pipeline.voice._build_elevenlabs", fake_build_el)
    monkeypatch.setattr("pipeline.voice._synthesize", fake_edge)

    from pipeline.voice import generate_narration
    generate_narration(
        text="مرحبا",
        voice="ar-EG-SalmaNeural", rate="+0%", pitch="+0Hz",
        mp3_path=tmp_run_dir / "n.mp3",
        timings_path=tmp_run_dir / "t.json",
        provider="elevenlabs",
        elevenlabs_voice_id="vid-1",
        elevenlabs_model="eleven_multilingual_v2",
        fallback_to_edge_tts=True,
    )
    assert (tmp_run_dir / "n.mp3").exists()
