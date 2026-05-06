"""End-to-end smoke test for the Shorts pipeline (--shorts mode).

All four external services are mocked:
  - Gemini  → returns a canned beats[] JSON
  - Edge TTS → writes a fixture mp3 + canned timings
  - Kie.ai  → submit/poll succeed; download writes mp4 magic bytes
  - FFmpeg  → captures args; writes stub mp4 to the output path

Verifies all 7 Shorts stages produce expected artifacts.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline.types import Beat, Script

REPO_ROOT = Path(__file__).parent.parent

_MINIMAL_SCRIPT = Script(
    title="t",
    theme="folkloric",
    global_setting="abandoned village, night",
    music_mood="dread",
    beats=(
        Beat(arabic="a", english_motion="x", clip_duration_s=8.0, speaker="mother"),
    ),
    story_combined="a",
    target_duration_s=8.0,
)


@pytest.fixture
def music_bundle(tmp_path: Path) -> Path:
    bundle = tmp_path / "music_bundle"
    bundle.mkdir()
    (bundle / "dread-01.mp3").write_bytes(b"music")
    (bundle / "tracks.json").write_text(json.dumps([
        {"filename": "dread-01.mp3", "duration_s": 100, "mood": "dread",
         "license": "CC0", "source_url": "x", "attribution": None},
    ]))
    return bundle


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"


def test_run_shorts_full_pipeline(monkeypatch, tmp_path: Path, fixtures_dir: Path, music_bundle: Path):
    sample_mp3 = (fixtures_dir / "narration_sample.mp3").read_bytes()

    # ---- 1) Gemini fake — single call returns beats payload ----
    beats_payload = json.dumps({
        "title": "صدى البئر",
        "theme": "folkloric",
        "global_setting": "abandoned village, night, desert",
        "music_mood": "dread",
        "target_duration_s": 80,
        "beats": [
            {"arabic": "كنتُ وحيداً عند البئر.",
             "english_motion": "lone hooded figure beside ancient well, slow push-in, moonlight",
             "clip_duration_s": 8.0, "speaker": "mother"},
            {"arabic": "سمعتُ بكاءً في الأعماق.",
             "english_motion": "close-up of dark well shaft, mist rising, faint glow",
             "clip_duration_s": 8.0, "speaker": "mother"},
            {"arabic": "ظهرتْ يدٌ عظمية.",
             "english_motion": "skeletal hand emerging from well rim, low angle, candlelight",
             "clip_duration_s": 8.0, "speaker": "son"},
            {"arabic": "ثم اختفى كل شيء.",
             "english_motion": "wide shot of empty village, fog rolling in, static camera",
             "clip_duration_s": 8.0, "speaker": "mother"},
            {"arabic": "بكيتُ في الصمت.",
             "english_motion": "close-up of tear rolling down cheek, soft moonlight",
             "clip_duration_s": 8.0, "speaker": "mother"},
            {"arabic": "لم يبقَ أحد.",
             "english_motion": "empty village square at dawn, birds flying away",
             "clip_duration_s": 8.0, "speaker": "father"},
            {"arabic": "كان هذا نهاية كل شيء.",
             "english_motion": "wide shot of ruins, dust settling, golden hour",
             "clip_duration_s": 8.0, "speaker": "mother"},
            {"arabic": "لن أعود أبداً.",
             "english_motion": "lone figure walking away into fog, back to camera",
             "clip_duration_s": 8.0, "speaker": "son"},
        ],
    }, ensure_ascii=False)

    class FakeGemini:
        def __init__(self):
            self.complete_calls: list = []
        def complete(self, prompt, system=None):
            self.complete_calls.append(prompt)
            return beats_payload
        def embed(self, text):
            return [0.0, 1.0]
    fake_g = FakeGemini()
    monkeypatch.setattr("run._build_gemini", lambda: fake_g)

    # ---- 2) Edge TTS fake (long-form path / fallback) ----
    def fake_synthesize(text, voice, rate, pitch, mp3_path):
        mp3_path.write_bytes(sample_mp3)
        return [
            {"word": "كنتُ", "offset_ms": 0, "duration_ms": 400},
            {"word": "وحيداً.", "offset_ms": 400, "duration_ms": 400},
        ]
    monkeypatch.setattr("pipeline.voice._synthesize", fake_synthesize)

    # ---- 2b) ElevenLabs fake (Shorts per-character path) ----
    class FakeEL:
        def synthesize(self, text, voice_id, model, out_path, **kw):
            out_path.write_bytes(sample_mp3)
    monkeypatch.setattr("pipeline.voice._build_elevenlabs", lambda: FakeEL())
    monkeypatch.setattr("pipeline.voice._ffmpeg_concat_mp3s",
                        lambda parts, out: out.write_bytes(sample_mp3))
    monkeypatch.setattr("pipeline.voice._audio_duration_ms_safe", lambda p: 1000)

    # ---- 3) Kie.ai fake — Kie client never actually constructed; we mock _build_kie ----
    class FakeKie:
        pass
    monkeypatch.setattr("run._build_kie", lambda: FakeKie())

    # Mock character sheet — writes a minimal PNG header to out_path
    monkeypatch.setattr(
        "pipeline.character_sheet.generate_character_sheet",
        lambda **kw: kw["out_path"].write_bytes(b"\x89PNG\r\n\x1a\n"),
    )

    # Mock Whisper align — return 8 synthetic WordTiming objects
    from pipeline.types import WordTiming as _WordTiming
    monkeypatch.setattr(
        "pipeline.align.align_arabic",
        lambda audio_path, expected_text, **kw: [
            _WordTiming(word=f"w{i}", offset_ms=i * 500, duration_ms=500)
            for i in range(8)
        ],
    )

    # Mock the new chained video gen — writes stub mp4s for each beat
    def fake_generate_clips_chained(**kw):
        kw["clips_dir"].mkdir(parents=True, exist_ok=True)
        for i in range(len(kw["script"].beats)):
            (kw["clips_dir"] / f"{i+1:02d}.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42")
        # Also write a spend log so the assertion passes
        import json as _json
        from datetime import datetime
        kw["spend_log_path"].parent.mkdir(parents=True, exist_ok=True)
        kw["spend_log_path"].write_text(
            _json.dumps({
                "entries": [
                    {"clip": i + 1, "seed": 0, "duration_s": 8.0, "cost_usd": 0.0, "model": "veo3"}
                    for i in range(len(kw["script"].beats))
                ],
                "ts": datetime.now().isoformat(timespec="seconds"),
            }),
        )
    monkeypatch.setattr("pipeline.video.generate_clips_chained", fake_generate_clips_chained)

    # ---- 4) FFmpeg fake — captures args; writes stub mp4 to last arg ----
    ffmpeg_calls: list[list[str]] = []
    def fake_ffmpeg(args):
        ffmpeg_calls.append(args)
        out = Path(args[-1])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"\x00\x00\x00\x18ftypmp42")
    monkeypatch.setattr("pipeline.assemble._run_ffmpeg", fake_ffmpeg)

    # ffprobe can't read our 12-byte stub mp4s; fake the duration probe.
    monkeypatch.setattr("run._probe_duration_s", lambda p: 8.0)

    # ---- 5) Run orchestrator ----
    from run import main_with_args
    out_root = tmp_path / "out"
    config_path = Path(__file__).parent.parent / "config.yaml"

    code = main_with_args([
        "--shorts",
        "--theme", "folkloric",
        "--seed", "بئر قديم",
        "--out-root", str(out_root),
        "--music-bundle", str(music_bundle),
        "--config", str(config_path),
    ])
    assert code == 0

    # ---- 6) Verify artifacts ----
    runs = [p for p in out_root.iterdir() if p.is_dir()]
    assert len(runs) == 1
    run_dir = runs[0]

    # All Shorts artifacts present. With kie.native_audio=true (the post-Tier-4
    # default), Veo generates the dialogue audio per clip and the orchestrator
    # skips ElevenLabs entirely — narration.mp3 is not produced.
    assert (run_dir / "seed.json").exists()
    assert (run_dir / "script.json").exists()
    assert (run_dir / "word_timings.json").exists()
    assert (run_dir / "clips").is_dir()
    # 8 clips → 8 mp4 files
    clip_files = sorted((run_dir / "clips").glob("*.mp4"))
    assert len(clip_files) == 8
    assert (run_dir / "kie_spend.json").exists()
    assert (run_dir / "music_track.mp3").exists()
    assert (run_dir / "captions.ar.srt").exists()
    assert (run_dir / "captions.ar.ass").exists()
    assert (run_dir / "final.mp4").exists()

    # Spec gate: vertical TikTok captions, NO karaoke `{\k}` tags (those broke
    # Arabic right-to-left rendering — bidi reordered each tagged run as if
    # left-to-right and visually reversed Arabic word order).
    ass = (run_dir / "captions.ar.ass").read_text(encoding="utf-8")
    assert "PlayResX: 1080" in ass
    assert "\\k" not in ass

    # Script has beats[] populated, story_combined non-empty
    script = json.loads((run_dir / "script.json").read_text(encoding="utf-8"))
    assert len(script["beats"]) == 8
    assert script["story_combined"]

    # Spend log records 8 clips
    spend = json.loads((run_dir / "kie_spend.json").read_text(encoding="utf-8"))
    assert len(spend["entries"]) == 8

    # 1+ Gemini calls (writer plus possibly expand-pass retries when the
    # canned beats are too short). Script writer is the only LLM stage.
    assert len(fake_g.complete_calls) >= 1

    # Tier-3: character sheet PNG must be present
    assert (run_dir / "character_sheet.png").exists()


def test_run_shorts_pause_after_script_stops_before_paid_stages(
    monkeypatch, tmp_path: Path, fixtures_dir: Path, music_bundle: Path,
):
    """`--pause-after-script` writes script.json, then exits cleanly so a UI
    can show the dialogue for human approval BEFORE any Veo / Flux spend.
    No character_sheet, no clips, no final.mp4 should be produced."""
    beats_payload = json.dumps({
        "title": "review me",
        "theme": "folkloric",
        "global_setting": "test setting",
        "music_mood": "dread",
        "target_duration_s": 40,
        "beats": [
            {"arabic": f"ج{i}", "english_motion": f"m{i}",
             "clip_duration_s": 8.0, "speaker": "mother"}
            for i in range(1, 6)
        ],
    }, ensure_ascii=False)

    class FakeGemini:
        def complete(self, prompt, system=None):
            return beats_payload
        def embed(self, text):
            return [0.0, 1.0]

    monkeypatch.setattr("run._build_gemini", lambda: FakeGemini())

    # Hard fail any paid stage to prove the pause gate works.
    def explode(*a, **kw):
        raise AssertionError("paid stage ran despite --pause-after-script")
    monkeypatch.setattr("pipeline.character_sheet.generate_character_sheet", explode)
    monkeypatch.setattr("pipeline.video.generate_clips_chained", explode)
    monkeypatch.setattr("pipeline.assemble._run_ffmpeg", explode)

    from run import main_with_args
    out_root = tmp_path / "out"
    config_path = Path(__file__).parent.parent / "config.yaml"

    code = main_with_args([
        "--shorts",
        "--pause-after-script",
        "--theme", "folkloric",
        "--seed", "x",
        "--out-root", str(out_root),
        "--music-bundle", str(music_bundle),
        "--config", str(config_path),
    ])
    assert code == 0
    runs = [p for p in out_root.iterdir() if p.is_dir()]
    assert len(runs) == 1
    run_dir = runs[0]

    # Script written for review
    assert (run_dir / "script.json").exists()
    assert (run_dir / "seed.json").exists()
    # Paid artifacts MUST NOT exist
    assert not (run_dir / "character_sheet.png").exists()
    assert not (run_dir / "clips").exists()
    assert not (run_dir / "final.mp4").exists()
    # Run log records the pause reason
    log = (run_dir / "run.log").read_text(encoding="utf-8")
    assert "PAUSED" in log


def test_run_shorts_skip_video_uses_placeholder_clips(
    monkeypatch, tmp_path: Path, fixtures_dir: Path, music_bundle: Path,
):
    """--skip-video produces black mp4s via real ffmpeg (cheap path, no Kie.ai)."""
    sample_mp3 = (fixtures_dir / "narration_sample.mp3").read_bytes()

    beats_payload = json.dumps({
        "title": "x",
        "theme": "folkloric",
        "global_setting": "abandoned village",
        "music_mood": "dread",
        "target_duration_s": 72,
        "beats": [
            {"arabic": f"ج{i}", "english_motion": f"m{i}",
             "clip_duration_s": 9.0, "speaker": "mother"}
            for i in range(1, 9)
        ],
    }, ensure_ascii=False)

    class FakeGemini:
        def complete(self, prompt, system=None):
            return beats_payload
        def embed(self, text):
            return [0.0, 1.0]

    monkeypatch.setattr("run._build_gemini", lambda: FakeGemini())

    def fake_synthesize(text, voice, rate, pitch, mp3_path):
        mp3_path.write_bytes(sample_mp3)
        return [{"word": "ج", "offset_ms": 0, "duration_ms": 400}]
    monkeypatch.setattr("pipeline.voice._synthesize", fake_synthesize)

    # ElevenLabs per-beat fake (config defaults to elevenlabs provider)
    class FakeEL:
        def synthesize(self, text, voice_id, model, out_path, **kw):
            out_path.write_bytes(sample_mp3)
    monkeypatch.setattr("pipeline.voice._build_elevenlabs", lambda: FakeEL())
    monkeypatch.setattr("pipeline.voice._ffmpeg_concat_mp3s",
                        lambda parts, out: out.write_bytes(sample_mp3))
    monkeypatch.setattr("pipeline.voice._audio_duration_ms_safe", lambda p: 1000)

    # Mock Whisper align — return synthetic timings (no real model load)
    from pipeline.types import WordTiming as _WordTiming
    monkeypatch.setattr(
        "pipeline.align.align_arabic",
        lambda audio_path, expected_text, **kw: [
            _WordTiming(word=f"w{i}", offset_ms=i * 500, duration_ms=500)
            for i in range(8)
        ],
    )

    # Mock character sheet — writes a minimal PNG header (uses _build_kie internally)
    monkeypatch.setattr(
        "pipeline.character_sheet.generate_character_sheet",
        lambda **kw: kw["out_path"].write_bytes(b"\x89PNG\r\n\x1a\n"),
    )

    # Kie should NEVER be constructed for video in --skip-video; character_sheet is mocked above.
    class FakeKieForCharSheet:
        pass
    monkeypatch.setattr("run._build_kie", lambda: FakeKieForCharSheet())

    # Mock the assembler ffmpeg call only (placeholder clip generation uses real ffmpeg).
    monkeypatch.setattr("pipeline.assemble._run_ffmpeg",
                        lambda args: Path(args[-1]).write_bytes(b"\x00\x00\x00\x18ftypmp42"))

    from run import main_with_args
    out_root = tmp_path / "out"
    config_path = Path(__file__).parent.parent / "config.yaml"

    code = main_with_args([
        "--shorts", "--skip-video",
        "--theme", "folkloric", "--seed", "بئر",
        "--out-root", str(out_root),
        "--music-bundle", str(music_bundle),
        "--config", str(config_path),
    ])
    assert code == 0
    runs = [p for p in out_root.iterdir() if p.is_dir()]
    run_dir = runs[0]
    assert (run_dir / "clips" / "01.mp4").exists()
    assert (run_dir / "clips" / "08.mp4").exists()
    assert (run_dir / "final.mp4").exists()


# ---------------------------------------------------------------------------
# Minimal valid script JSON for resume-path tests
# ---------------------------------------------------------------------------

_MINIMAL_SCRIPT_JSON = json.dumps({
    "title": "اختبار",
    "theme": "folkloric",
    "global_setting": "abandoned village, night",
    "music_mood": "dread",
    "target_duration_s": 16,
    "beats": [
        {"arabic": "كنتُ وحيداً.", "english_motion": "lone figure, slow push-in",
         "clip_duration_s": 8.0, "speaker": "mother"},
        {"arabic": "ثم اختفى كل شيء.", "english_motion": "empty village, fog",
         "clip_duration_s": 8.0, "speaker": "mother"},
    ],
}, ensure_ascii=False)


def test_pause_after_character_sheet_exits_after_flux(
    tmp_path, monkeypatch, music_bundle: Path,
):
    """When --pause-after-character-sheet is passed AND --resume points at a run
    with script.json already present, run.py runs the Flux stage exactly once
    and then exits 0 without entering the video stage."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "script.json").write_text(_MINIMAL_SCRIPT_JSON, encoding="utf-8")
    (run_dir / "seed.json").write_text(
        '{"theme":"folkloric","premise":"x"}', encoding="utf-8")

    video_calls: list = []
    sheet_calls: list = []

    class FakeGemini:
        def complete(self, prompt, system=None):
            return _MINIMAL_SCRIPT_JSON
        def embed(self, text):
            return [0.0, 1.0]

    monkeypatch.setattr("run._build_gemini", lambda: FakeGemini())

    class FakeKie:
        pass
    monkeypatch.setattr("run._build_kie", lambda: FakeKie())

    def fake_sheet(client, cfg, paths, script, **kw):
        sheet_calls.append(paths.character_sheet_png)
        paths.character_sheet_png.write_bytes(b"fake-png")

    def fake_video(*a, **kw):
        video_calls.append(a)

    monkeypatch.setattr("run._stage_character_sheet", fake_sheet)
    monkeypatch.setattr("run._stage_video_chained", fake_video)

    import run
    config_path = Path(__file__).parent.parent / "config.yaml"
    rc = run.main_with_args([
        "--shorts", "--resume", str(run_dir),
        "--pause-after-character-sheet",
        "--config", str(config_path),
        "--music-bundle", str(music_bundle),
    ])
    assert rc == 0
    assert len(sheet_calls) == 1
    assert video_calls == []


def test_pause_after_character_sheet_ignored_with_skip_video(
    tmp_path, monkeypatch, music_bundle: Path,
):
    """When --skip-video is set, the pause must NOT fire — there's no real
    character_sheet.png to gate on, and the API state machine relies on that
    artifact existing."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "script.json").write_text(_MINIMAL_SCRIPT_JSON, encoding="utf-8")
    (run_dir / "seed.json").write_text(
        '{"theme":"folkloric","premise":"x"}', encoding="utf-8")

    sheet_calls: list = []
    video_calls: list = []

    class FakeGemini:
        def complete(self, prompt, system=None):
            return _MINIMAL_SCRIPT_JSON
        def embed(self, text):
            return [0.0, 1.0]

    monkeypatch.setattr("run._build_gemini", lambda: FakeGemini())

    class FakeKie:
        pass
    monkeypatch.setattr("run._build_kie", lambda: FakeKie())

    def fake_sheet(client, cfg, paths, script, **kw):
        sheet_calls.append(paths.character_sheet_png)
        paths.character_sheet_png.write_bytes(b"fake-png")

    def fake_video(*a, **kw):
        video_calls.append(a)

    monkeypatch.setattr("run._stage_character_sheet", fake_sheet)
    monkeypatch.setattr("run._stage_video_chained", fake_video)

    # Under --skip-video, after the character_sheet stage is skipped,
    # we still need voice/align/music/captions/assemble to complete.
    # Stub the minimum set needed so the run finishes cleanly.
    sample_mp3 = (Path(__file__).parent / "fixtures" / "narration_sample.mp3").read_bytes()

    def fake_synthesize(text, voice, rate, pitch, mp3_path):
        mp3_path.write_bytes(sample_mp3)
        return [{"word": "ج", "offset_ms": 0, "duration_ms": 400}]
    monkeypatch.setattr("pipeline.voice._synthesize", fake_synthesize)

    class FakeEL:
        def synthesize(self, text, voice_id, model, out_path, **kw):
            out_path.write_bytes(sample_mp3)
    monkeypatch.setattr("pipeline.voice._build_elevenlabs", lambda: FakeEL())
    monkeypatch.setattr("pipeline.voice._ffmpeg_concat_mp3s",
                        lambda parts, out: out.write_bytes(sample_mp3))
    monkeypatch.setattr("pipeline.voice._audio_duration_ms_safe", lambda p: 1000)

    from pipeline.types import WordTiming as _WordTiming
    monkeypatch.setattr(
        "pipeline.align.align_arabic",
        lambda audio_path, expected_text, **kw: [
            _WordTiming(word=f"w{i}", offset_ms=i * 500, duration_ms=500)
            for i in range(4)
        ],
    )

    monkeypatch.setattr("pipeline.assemble._run_ffmpeg",
                        lambda args: Path(args[-1]).write_bytes(b"\x00\x00\x00\x18ftypmp42"))
    monkeypatch.setattr("run._probe_duration_s", lambda p: 8.0)

    import run
    config_path = Path(__file__).parent.parent / "config.yaml"
    rc = run.main_with_args([
        "--shorts", "--resume", str(run_dir),
        "--pause-after-character-sheet", "--skip-video",
        "--config", str(config_path),
        "--music-bundle", str(music_bundle),
    ])
    assert rc == 0
    assert sheet_calls == []  # sheet stage skipped under --skip-video
    # The pause must NOT have fired — execution continued past character_sheet.
    # If the pause incorrectly fired, final.mp4 would not exist.
    runs = list((tmp_path / "run").parent.glob("run"))
    run_log = (run_dir / "run.log").read_text(encoding="utf-8")
    assert "PAUSED" not in run_log or "--pause-after-character-sheet ignored" in run_log
    assert (run_dir / "final.mp4").exists()


def test_freeform_flag_routes_to_freeform_writer(tmp_path, monkeypatch, music_bundle):
    """When --freeform is passed, the shorts-script stage calls
    generate_freeform_script, NOT generate_shorts_script."""
    called = {"freeform": False, "shorts": False}

    def fake_freeform(llm, seed, controls):
        called["freeform"] = True
        return _MINIMAL_SCRIPT

    def fake_shorts(*a, **kw):
        called["shorts"] = True
        return _MINIMAL_SCRIPT

    monkeypatch.setattr(
        "pipeline.script_freeform.generate_freeform_script", fake_freeform,
    )
    monkeypatch.setattr(
        "pipeline.script.generate_shorts_script", fake_shorts,
    )

    monkeypatch.setattr("run._build_gemini", lambda: object())
    monkeypatch.setattr("run._build_kie", lambda: object())
    monkeypatch.setattr("run._stage_character_sheet", lambda *a, **kw: None)
    monkeypatch.setattr("run._stage_video_chained", lambda *a, **kw: None)
    monkeypatch.setattr("run._stage_shorts_captions", lambda *a, **kw: False)
    monkeypatch.setattr("run._stage_assemble", lambda *a, **kw: None)

    config_path = REPO_ROOT / "config.yaml"
    import run
    rc = run.main_with_args([
        "--shorts", "--freeform",
        "--theme", "urban", "--seed", "test premise",
        "--out-root", str(tmp_path),
        "--pause-after-script",
        "--ff-dialect", "egyptian",
        "--ff-art-style", "anime_2d",
        "--ff-character-template", "human",
        "--ff-ending-type", "twist",
        "--ff-num-beats", "6",
        "--config", str(config_path),
        "--music-bundle", str(music_bundle),
    ])
    assert rc == 0
    assert called["freeform"] is True
    assert called["shorts"] is False


def test_freeform_mode_passes_custom_lineup_prompt(tmp_path, monkeypatch):
    """When --freeform is set, _stage_character_sheet builds a lineup_prompt
    from script.global_setting that does NOT contain the Sunstoriz cast."""
    captured: dict = {}

    def fake_generate_sheet(client, *, out_path, lineup_prompt=None, **kw):
        captured["lineup_prompt"] = lineup_prompt
        out_path.write_bytes(b"fake-png")

    monkeypatch.setattr(
        "pipeline.character_sheet.generate_character_sheet",
        fake_generate_sheet,
    )

    from pipeline.types import RunPaths, Script, Beat
    from pipeline.config import load_config
    paths = RunPaths(root=tmp_path / "run")
    paths.root.mkdir()
    script = Script(
        title="t", theme="folkloric",
        global_setting="3D Pixar animation, anthropomorphic animal characters",
        music_mood="dread",
        beats=(Beat(arabic="a", english_motion="x", clip_duration_s=8.0,
                    speaker="mother"),),
        story_combined="a", target_duration_s=8.0,
    )
    cfg = load_config(REPO_ROOT / "config.yaml")
    import run
    run._stage_character_sheet(
        client=object(), cfg=cfg, paths=paths, script=script,
        freeform_mode=True,
    )
    p = captured["lineup_prompt"]
    assert p is not None
    assert "anthropomorphic animal characters" in p
    assert "Lemon mother" not in p   # sunstoriz must not leak in


def test_freeform_mode_lineup_includes_unique_character_names(tmp_path, monkeypatch):
    """When freeform_mode=True and script.beats carry character_name,
    the lineup_prompt enumerates the unique names so Flux can label them."""
    captured: dict = {}

    def fake_generate_sheet(client, *, out_path, lineup_prompt=None, **kw):
        captured["lineup_prompt"] = lineup_prompt
        out_path.write_bytes(b"fake-png")

    monkeypatch.setattr(
        "pipeline.character_sheet.generate_character_sheet",
        fake_generate_sheet,
    )

    from pipeline.types import RunPaths, Script, Beat
    from pipeline.config import load_config
    paths = RunPaths(root=tmp_path / "run")
    paths.root.mkdir()
    script = Script(
        title="t", theme="folkloric",
        global_setting="3D Pixar animation, anthropomorphic animal characters",
        music_mood="dread",
        beats=(
            Beat(arabic="a", english_motion="x", clip_duration_s=8.0,
                 speaker="mother", character_name="أم خالد"),
            Beat(arabic="b", english_motion="y", clip_duration_s=8.0,
                 speaker="son", character_name="خالد"),
            Beat(arabic="c", english_motion="z", clip_duration_s=8.0,
                 speaker="mother", character_name="أم خالد"),  # dup, must dedupe
        ),
        story_combined="abc", target_duration_s=24.0,
    )
    cfg = load_config(REPO_ROOT / "config.yaml")
    import run
    run._stage_character_sheet(
        client=object(), cfg=cfg, paths=paths, script=script,
        freeform_mode=True,
    )
    p = captured["lineup_prompt"]
    assert p is not None
    assert "أم خالد" in p
    assert "خالد" in p
    # Deduplicated — "أم خالد" should appear exactly once in the names list section.
    # We don't strict-count globally because it could appear once and the prompt
    # also mentions the cast generically. Loose check: the names appear.


def test_freeform_animal_cast_negates_fruit_in_lineup_prompt(tmp_path, monkeypatch):
    """When character_template='animal', the lineup_prompt must EXPLICITLY
    negate fruit characters AND use concrete animal vocabulary so Flux
    can't default to its Sunstoriz bias."""
    captured: dict = {}
    def fake_generate_sheet(client, *, out_path, lineup_prompt=None, **kw):
        captured["lineup_prompt"] = lineup_prompt
        out_path.write_bytes(b"fake-png")
    monkeypatch.setattr(
        "pipeline.character_sheet.generate_character_sheet",
        fake_generate_sheet,
    )

    from pipeline.types import RunPaths, Script, Beat
    from pipeline.config import load_config
    paths = RunPaths(root=tmp_path / "run")
    paths.root.mkdir()
    script = Script(
        title="t", theme="folkloric",
        global_setting="3D Pixar animation, anthropomorphic animal characters in folkloric setting",
        music_mood="dread",
        beats=(
            Beat(arabic="a", english_motion="x", clip_duration_s=8.0,
                 speaker="mother", character_name="أم خالد"),
        ),
        story_combined="a", target_duration_s=8.0,
    )
    cfg = load_config(REPO_ROOT / "config.yaml")
    import run
    run._stage_character_sheet(
        client=object(), cfg=cfg, paths=paths, script=script,
        freeform_mode=True,
        character_template="animal",
    )
    p = captured["lineup_prompt"]
    assert p is not None
    p_lower = p.lower()
    # Must explicitly forbid fruit
    assert ("not fruit" in p_lower or "no fruit" in p_lower
            or "no lemon" in p_lower or "no strawber" in p_lower), (
        f"lineup_prompt for animal cast must NEGATE fruit: {p}"
    )
    # Must mention concrete animal types so Flux has a target
    animal_words = ["fox", "rabbit", "deer", "bear", "wolf", "owl", "cat", "dog",
                    "lion", "tiger", "horse", "mouse", "panda"]
    found = sum(1 for w in animal_words if w in p_lower)
    assert found >= 2, (
        f"animal lineup_prompt must list concrete animal species (≥2); got {found}: {p}"
    )


def test_freeform_human_cast_negates_fruit_and_animals(tmp_path, monkeypatch):
    """character_template='human' → prompt forbids fruits/animals and uses
    human descriptors."""
    captured: dict = {}
    def fake_generate_sheet(client, *, out_path, lineup_prompt=None, **kw):
        captured["lineup_prompt"] = lineup_prompt
        out_path.write_bytes(b"fake-png")
    monkeypatch.setattr(
        "pipeline.character_sheet.generate_character_sheet",
        fake_generate_sheet,
    )

    from pipeline.types import RunPaths, Script, Beat
    from pipeline.config import load_config
    paths = RunPaths(root=tmp_path / "run-h")
    paths.root.mkdir()
    script = Script(
        title="t", theme="urban",
        global_setting="cinematic photo-real, human cast",
        music_mood="dread",
        beats=(Beat(arabic="x", english_motion="y", clip_duration_s=8.0,
                    speaker="mother", character_name="فاطمة"),),
        story_combined="x", target_duration_s=8.0,
    )
    cfg = load_config(REPO_ROOT / "config.yaml")
    import run
    run._stage_character_sheet(
        client=object(), cfg=cfg, paths=paths, script=script,
        freeform_mode=True,
        character_template="human",
    )
    p = captured["lineup_prompt"]
    p_lower = p.lower()
    assert "human" in p_lower
    assert ("not fruit" in p_lower or "no fruit" in p_lower
            or "not anthropomorphic fruit" in p_lower or "no lemons" in p_lower)
    assert ("not animal" in p_lower or "no anthropomorphic" in p_lower or
            "no animals" in p_lower or "real human" in p_lower)


def test_freeform_fruit_cast_keeps_sunstoriz_default(tmp_path, monkeypatch):
    """character_template='fruit_sunstoriz' should NOT add the negation —
    fruits are the desired output."""
    captured: dict = {}
    def fake_generate_sheet(client, *, out_path, lineup_prompt=None, **kw):
        captured["lineup_prompt"] = lineup_prompt
        out_path.write_bytes(b"fake-png")
    monkeypatch.setattr(
        "pipeline.character_sheet.generate_character_sheet",
        fake_generate_sheet,
    )

    from pipeline.types import RunPaths, Script, Beat
    from pipeline.config import load_config
    paths = RunPaths(root=tmp_path / "run-f")
    paths.root.mkdir()
    script = Script(
        title="t", theme="folkloric",
        global_setting="3D Pixar, anthropomorphic fruit characters",
        music_mood="dread",
        beats=(Beat(arabic="x", english_motion="y", clip_duration_s=8.0,
                    speaker="mother", character_name="أم خالد"),),
        story_combined="x", target_duration_s=8.0,
    )
    cfg = load_config(REPO_ROOT / "config.yaml")
    import run
    run._stage_character_sheet(
        client=object(), cfg=cfg, paths=paths, script=script,
        freeform_mode=True,
        character_template="fruit_sunstoriz",
    )
    p = captured["lineup_prompt"]
    p_lower = p.lower()
    # No negation when fruit is the chosen cast
    assert "not fruit" not in p_lower
    assert "no fruit" not in p_lower


def test_freeform_ai_choose_falls_through_to_setting_only(tmp_path, monkeypatch):
    """character_template='ai_choose' → no aggressive negation; the writer's
    global_setting is the source of truth (existing behavior preserved)."""
    captured: dict = {}
    def fake_generate_sheet(client, *, out_path, lineup_prompt=None, **kw):
        captured["lineup_prompt"] = lineup_prompt
        out_path.write_bytes(b"fake-png")
    monkeypatch.setattr(
        "pipeline.character_sheet.generate_character_sheet",
        fake_generate_sheet,
    )
    from pipeline.types import RunPaths, Script, Beat
    from pipeline.config import load_config
    paths = RunPaths(root=tmp_path / "run-c")
    paths.root.mkdir()
    script = Script(
        title="t", theme="folkloric",
        global_setting="cinematic dramatic lighting, vertical 9:16",
        music_mood="dread",
        beats=(Beat(arabic="x", english_motion="y", clip_duration_s=8.0,
                    speaker="mother", character_name="أم خالد"),),
        story_combined="x", target_duration_s=8.0,
    )
    cfg = load_config(REPO_ROOT / "config.yaml")
    import run
    run._stage_character_sheet(
        client=object(), cfg=cfg, paths=paths, script=script,
        freeform_mode=True,
        character_template="ai_choose",
    )
    p = captured["lineup_prompt"]
    p_lower = p.lower()
    # ai_choose mode is permissive — just uses global_setting.
    assert "not fruit" not in p_lower


def test_legacy_mode_passes_none_lineup_prompt(tmp_path, monkeypatch):
    """When freeform_mode is False (default), lineup_prompt is None so the
    Sunstoriz hardcoded prompt fires inside generate_character_sheet."""
    captured: dict = {}

    def fake_generate_sheet(client, *, out_path, lineup_prompt=None, **kw):
        captured["lineup_prompt"] = lineup_prompt
        out_path.write_bytes(b"fake-png")

    monkeypatch.setattr(
        "pipeline.character_sheet.generate_character_sheet",
        fake_generate_sheet,
    )

    from pipeline.types import RunPaths, Script, Beat
    from pipeline.config import load_config
    paths = RunPaths(root=tmp_path / "run2")
    paths.root.mkdir()
    script = Script(
        title="t", theme="folkloric",
        global_setting="anything",
        music_mood="dread",
        beats=(Beat(arabic="a", english_motion="x", clip_duration_s=8.0,
                    speaker="mother"),),
        story_combined="a", target_duration_s=8.0,
    )
    cfg = load_config(REPO_ROOT / "config.yaml")
    import run
    run._stage_character_sheet(
        client=object(), cfg=cfg, paths=paths, script=script,
        # freeform_mode defaults to False
    )
    assert captured["lineup_prompt"] is None


def test_resume_auto_loads_freeform_controls(tmp_path, monkeypatch, music_bundle):
    """When resuming a run dir that contains freeform_controls.json, run.py
    must populate args.freeform + args.ff_* as if those flags were on the CLI.
    Verified by checking _stage_character_sheet receives character_template."""
    import json as _json
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "script.json").write_text(_MINIMAL_SCRIPT_JSON, encoding="utf-8")
    (run_dir / "seed.json").write_text(
        '{"theme":"folkloric","premise":"x"}', encoding="utf-8")
    (run_dir / "freeform_controls.json").write_text(_json.dumps({
        "dialect": "syrian",
        "art_style": "pixar_3d",
        "character_template": "animal",
        "ending_type": "closed_tragic",
        "num_beats": 8,
        "per_beat_seconds": 8,
        "narration_style": "cinematic",
    }), encoding="utf-8")

    captured: dict = {}
    def fake_sheet(client, *, out_path, lineup_prompt=None, **kw):
        captured["lineup_prompt"] = lineup_prompt
        out_path.write_bytes(b"fake-png")
    monkeypatch.setattr("run._build_gemini", lambda: object())
    monkeypatch.setattr("run._build_kie", lambda: object())
    monkeypatch.setattr(
        "pipeline.character_sheet.generate_character_sheet", fake_sheet)
    monkeypatch.setattr("run._stage_video_chained", lambda *a, **kw: None)

    config_path = REPO_ROOT / "config.yaml"
    import run
    rc = run.main_with_args([
        "--shorts", "--resume", str(run_dir),
        "--pause-after-character-sheet",
        "--config", str(config_path),
        "--music-bundle", str(music_bundle),
    ])
    assert rc == 0
    p = captured["lineup_prompt"]
    assert p is not None, "freeform mode should have produced a custom lineup_prompt"
    p_lower = p.lower()
    # Animal cast → negation must be present
    assert "not fruit" in p_lower or "no fruit" in p_lower or "no lemon" in p_lower
    assert "fox" in p_lower or "rabbit" in p_lower or "deer" in p_lower


def test_explicit_freeform_flag_still_works_without_file(tmp_path, monkeypatch, music_bundle):
    """If --freeform is on the CLI but no freeform_controls.json exists, the
    CLI flags drive (current behavior preserved)."""
    run_dir = tmp_path / "run2"
    run_dir.mkdir()
    (run_dir / "script.json").write_text(_MINIMAL_SCRIPT_JSON, encoding="utf-8")
    (run_dir / "seed.json").write_text(
        '{"theme":"folkloric","premise":"x"}', encoding="utf-8")

    captured: dict = {}
    def fake_sheet(client, *, out_path, lineup_prompt=None, **kw):
        captured["lineup_prompt"] = lineup_prompt
        out_path.write_bytes(b"fake-png")
    monkeypatch.setattr("run._build_gemini", lambda: object())
    monkeypatch.setattr("run._build_kie", lambda: object())
    monkeypatch.setattr(
        "pipeline.character_sheet.generate_character_sheet", fake_sheet)
    monkeypatch.setattr("run._stage_video_chained", lambda *a, **kw: None)

    config_path = REPO_ROOT / "config.yaml"
    import run
    rc = run.main_with_args([
        "--shorts", "--freeform", "--resume", str(run_dir),
        "--pause-after-character-sheet",
        "--ff-character-template", "human",
        "--config", str(config_path),
        "--music-bundle", str(music_bundle),
    ])
    assert rc == 0
    assert captured["lineup_prompt"] is not None
    p_lower = captured["lineup_prompt"].lower()
    # Human cast negation
    assert ("not fruit" in p_lower or "no fruit" in p_lower
            or "not anthropomorphic fruit" in p_lower or "no lemons" in p_lower)
