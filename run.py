"""Faceless pipeline CLI orchestrator.

Usage (long-form slideshow, free, local Flux):
  python run.py                                  # auto theme, full pipeline
  python run.py --theme folkloric --seed "بئر"   # manual seed
  python run.py --resume out/2026-05-01-1430     # resume crashed run
  python run.py --reroll-images 23,27 --run-dir out/2026-05-01-1430
  python run.py --skip-images
  python run.py --voice ar-EG-ShakirNeural
  python run.py --burn-captions

Usage (Shorts mode, paid via Kie.ai):
  python run.py --shorts                         # ~30 sec vertical TikTok video
  python run.py --shorts --theme folkloric --seed "بئر"
  python run.py --shorts --reroll-clips 3 --run-dir out/2026-05-02-1430
  python run.py --shorts --skip-video            # placeholder mp4s, dev only
  python run.py --shorts --max-spend 5.00        # raise per-run budget cap
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import pipeline.align
import pipeline.character_sheet
import pipeline.video as _pipeline_video
from pipeline.assemble import assemble_shorts_video, assemble_video
from pipeline.auth import User as _User
from pipeline.captions import generate_captions
from pipeline.config import Config, load_config
from pipeline.images import generate_images
from pipeline.kie import KieClient
from pipeline.llm import GeminiClient
from pipeline.llm_groq import GroqClient
from pipeline.music import select_music_track
from pipeline.runlog import RunLog
from pipeline.script import generate_script_with_uniqueness
from pipeline.seed import auto_seed, manual_seed, record_theme_use
from pipeline.shots import generate_shots
from pipeline.types import RunPaths, Script, Shot, ThemeSeed, WordTiming
from pipeline.video import generate_clips
from pipeline.voice import generate_narration, generate_narration_per_beat


REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = REPO_ROOT / "config.yaml"
DEFAULT_OUT_ROOT = REPO_ROOT / "out"
DEFAULT_MUSIC_BUNDLE = REPO_ROOT / "assets" / "music"
DEFAULT_FONTS_DIR = REPO_ROOT / "assets" / "fonts"
PROJECT_THEME_LOG = DEFAULT_OUT_ROOT / "theme_log.json"
PROJECT_STORY_HISTORY = DEFAULT_OUT_ROOT / "story_history.jsonl"


def _build_gemini():
    """Build the LLM client used by stages.

    Priority (most-to-least preferred for the Shorts writer):
      1. Anthropic Claude — strongest Arabic narrative quality, no Latin /
         CJK character contamination, reliable first-person perspective.
         Costs ~$0.02 per shorts script via Sonnet 4.6.
      2. Groq Llama 3.3 — free tier with high RPM. Acceptable for cheap
         iteration but slips foreign characters and confuses speakers.
      3. Gemini — free fallback when neither key is present. Long-form path
         uses .embed() which only Gemini implements.

    All clients expose the same .complete()/.embed() interface, though
    Anthropic and Groq raise NotImplementedError on .embed() (only the
    long-form repetition guard calls it; Shorts never does).
    """
    if os.environ.get("ANTHROPIC_API_KEY"):
        from pipeline.llm_anthropic import AnthropicClient
        return AnthropicClient()
    if os.environ.get("GROQ_API_KEY"):
        return GroqClient()
    return GeminiClient()


def _build_kie() -> KieClient:
    """Indirection so tests can monkeypatch."""
    return KieClient()


def _make_run_dir(out_root: Path, user_id: str = "admin") -> Path:
    user_root = out_root / user_id
    user_root.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d-%H%M")
    run_dir = user_root / ts
    # Ensure uniqueness if two runs start in the same minute.
    suffix = 0
    while run_dir.exists():
        suffix += 1
        run_dir = user_root / f"{ts}-{suffix}"
    run_dir.mkdir()
    return run_dir


def _resolve_run_dir(args, out_root: Path) -> Path:
    if args.resume:
        return Path(args.resume).resolve()
    if args.run_dir:
        return Path(args.run_dir).resolve()
    return _make_run_dir(out_root, user_id=args.user_id)


def _stage_seed(args, gemini, log: RunLog, paths: RunPaths,
                project_theme_log: Path) -> ThemeSeed:
    seed_path = paths.root / "seed.json"
    if seed_path.exists():
        log.info("seed: already exists, skipping")
        return ThemeSeed.from_dict(json.loads(seed_path.read_text(encoding="utf-8")))
    if args.theme and args.seed:
        seed = manual_seed(args.theme, args.seed)
    elif args.theme and not args.seed:
        # Theme given, no premise — let auto_seed pick the premise but constrain to that theme.
        # Implemented inline: ask Gemini using AUTO_PREMISE_PROMPT format.
        from pipeline.seed import AUTO_PREMISE_PROMPT
        premise = gemini.complete(AUTO_PREMISE_PROMPT.format(theme=args.theme)).strip()
        seed = ThemeSeed(theme=args.theme, premise=premise)
    else:
        seed = auto_seed(gemini, project_theme_log)
    seed_path.write_text(json.dumps(seed.to_dict(), ensure_ascii=False, indent=2),
                         encoding="utf-8")
    record_theme_use(project_theme_log, seed.theme)
    return seed


def _stage_script(gemini, cfg: Config, seed: ThemeSeed, paths: RunPaths,
                  story_history: Path) -> Script:
    if paths.script_json.exists():
        return Script.from_dict(json.loads(paths.script_json.read_text(encoding="utf-8")))
    script = generate_script_with_uniqueness(
        gemini=gemini, seed=seed,
        target_words=cfg.script.word_count_target,
        tolerance=cfg.script.word_count_tolerance,
        enable_critique=cfg.script.enable_critique_pass,
        history_path=story_history,
        repetition_threshold=cfg.script.repetition_threshold,
    )
    paths.script_json.write_text(
        json.dumps(script.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return script


def _stage_voice(args, cfg: Config, script: Script, paths: RunPaths) -> list[WordTiming]:
    voice = args.voice or cfg.voice.name
    generate_narration(
        text=script.story,
        voice=voice, rate=cfg.voice.rate, pitch=cfg.voice.pitch,
        mp3_path=paths.narration_mp3, timings_path=paths.word_timings_json,
    )
    return [WordTiming.from_dict(d)
            for d in json.loads(paths.word_timings_json.read_text(encoding="utf-8"))]


def _stage_shots(gemini, script: Script, timings: list[WordTiming], paths: RunPaths) -> list[Shot]:
    return generate_shots(
        gemini=gemini, script=script, timings=timings,
        out_path=paths.shots_json,
    )


def _stage_images(args, cfg: Config, shots: list[Shot], paths: RunPaths) -> None:
    if args.skip_images:
        # Write tiny placeholder PNGs so downstream stages can still run.
        from PIL import Image
        paths.images_dir.mkdir(parents=True, exist_ok=True)
        for shot in shots:
            p = paths.images_dir / f"{shot.index:02d}.png"
            if not p.exists():
                Image.new("RGB", (cfg.flux.width, cfg.flux.height), "black").save(p)
        return
    reroll = []
    if args.reroll_images:
        reroll = [int(x) for x in args.reroll_images.split(",")]
    generate_images(
        shots=shots, images_dir=paths.images_dir,
        steps=cfg.flux.steps, guidance=cfg.flux.guidance,
        width=cfg.flux.width, height=cfg.flux.height,
        reroll_indices=reroll,
    )


def _stage_music(script: Script, music_bundle: Path, paths: RunPaths) -> None:
    select_music_track(
        bundle_dir=music_bundle, mood=script.music_mood,
        out_path=paths.music_track_mp3,
    )


def _stage_captions(args, cfg: Config, timings: list[WordTiming], paths: RunPaths) -> Path | None:
    burn = args.burn_captions or cfg.captions.burn_in
    ass_path = paths.captions_ass if burn else None
    generate_captions(
        timings=timings, srt_path=paths.captions_srt,
        ass_path=ass_path, font=cfg.captions.font, font_size=cfg.captions.font_size,
    )
    return ass_path if burn else None


def _stage_assemble(cfg: Config, shots: list[Shot], paths: RunPaths,
                    burn_caption_ass: Path | None) -> None:
    assemble_video(
        shots=shots,
        images_dir=paths.images_dir,
        narration_path=paths.narration_mp3,
        music_path=paths.music_track_mp3,
        out_path=paths.final_mp4,
        burn_caption_ass=burn_caption_ass,
        output_width=cfg.assemble.output_width,
        output_height=cfg.assemble.output_height,
        crossfade_ms=cfg.assemble.shot_crossfade_ms,
        music_duck_db=cfg.assemble.music_duck_db,
        music_silence_db=cfg.assemble.music_silence_db,
        fade_in_s=cfg.assemble.fade_in_s,
        fade_out_s=cfg.assemble.fade_out_s,
    )


# ============================================================================
# Shorts mode stages — operate on script.beats, produce vertical 9:16 mp4.
# ============================================================================

from pipeline.cast_guidance import flux_lineup_override


def _stage_shorts_voice(args, cfg: Config, script: Script, paths: RunPaths) -> list[WordTiming]:
    """Voice stage for Shorts mode.

    Uses per-beat synthesis when speakers are tagged AND character voices
    are configured (the @sunstoriz path: mother voice + son voice routed by
    each beat's `speaker` field). Falls back to single-voice narration of
    the concatenated story_combined for older scripts without speaker tags.
    """
    use_per_beat = (
        cfg.voice.provider == "elevenlabs"
        and bool(cfg.voice.character_voices)
        and any(b.speaker != "narrator" for b in script.beats)
    )
    if use_per_beat:
        generate_narration_per_beat(
            beats=list(script.beats),
            character_voices=dict(cfg.voice.character_voices),
            parts_dir=paths.root / "narration_beats",
            combined_mp3_path=paths.narration_mp3,
            timings_path=paths.word_timings_json,
            elevenlabs_model=cfg.voice.elevenlabs_model,
            fallback_voice_id=cfg.voice.elevenlabs_voice_id,
        )
    else:
        voice = args.voice or cfg.voice.name
        generate_narration(
            text=script.story_combined,
            voice=voice, rate=cfg.voice.rate, pitch=cfg.voice.pitch,
            mp3_path=paths.narration_mp3, timings_path=paths.word_timings_json,
            provider=cfg.voice.provider,
            elevenlabs_voice_id=cfg.voice.elevenlabs_voice_id,
            elevenlabs_model=cfg.voice.elevenlabs_model,
            fallback_to_edge_tts=cfg.voice.fallback_to_edge_tts,
        )
    return [WordTiming.from_dict(d)
            for d in json.loads(paths.word_timings_json.read_text(encoding="utf-8"))]


def _stage_video(args, cfg: Config, script: Script, paths: RunPaths) -> None:
    """Generate Veo clips (or placeholder mp4s with --skip-video)."""
    if args.skip_video:
        # Placeholder: write a tiny black-frame mp4 per beat so downstream stages can run.
        # Uses ffmpeg directly since we already depend on it for assembly.
        import subprocess
        paths.clips_dir.mkdir(parents=True, exist_ok=True)
        for i, _ in enumerate(script.beats):
            p = paths.clips_dir / f"{i+1:02d}.mp4"
            if p.exists():
                continue
            subprocess.run([
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", f"color=c=black:s=1080x1920:d={cfg.kie.clip_duration_s}",
                "-f", "lavfi", "-i", f"anullsrc=r=24000:cl=stereo:d={cfg.kie.clip_duration_s}",
                "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "128k", "-shortest",
                str(p),
            ], check=True)
        return

    reroll = []
    if args.reroll_clips:
        reroll = [int(x) for x in args.reroll_clips.split(",")]
    max_spend = args.max_spend if args.max_spend is not None else cfg.kie.max_spend_usd
    client = _build_kie()
    generate_clips(
        client=client, script=script,
        clips_dir=paths.clips_dir,
        spend_log_path=paths.kie_spend_json,
        model=cfg.kie.model,
        clip_duration_s=cfg.kie.clip_duration_s,
        aspect_ratio=cfg.kie.aspect_ratio,
        cost_per_second_usd=cfg.kie.cost_per_second_usd,
        max_spend_usd=max_spend,
        poll_interval_s=cfg.kie.poll_interval_s,
        poll_timeout_s=cfg.kie.poll_timeout_s,
        reroll_indices=reroll,
    )


def _stage_character_sheet(
    client, cfg: Config, paths: RunPaths, script: Script,
    *, freeform_mode: bool = False,
    character_template: str | None = None,
) -> None:
    """Generate a Flux character sheet for visual consistency across Veo clips.

    Always composes the lineup prompt from the script's actual content:
    unique character_name values + script.global_setting + per-cast Flux
    guidance from pipeline.cast_guidance. There is no hardcoded fruit-cast
    fallback after Phase A — when character_template is fruit_sunstoriz, the
    cast guidance produces the Sunstoriz lineup. When unknown / None /
    ai_choose, the script's global_setting + character_names drive Flux
    on their own.

    `freeform_mode` is now a no-op parameter kept for call-site compatibility.
    """
    # Collect unique character names from beats, preserving first-seen order.
    seen: set[str] = set()
    names: list[str] = []
    for beat in script.beats:
        n = (beat.character_name or "").strip()
        if n and n not in seen:
            seen.add(n)
            names.append(n)
    n = len(names)
    if n == 0:
        count_phrase = (
            "Character mood-board for an animated short. "
            "A single representative character (or atmospheric placeholder) "
            "standing centered, "
        )
        names_clause = ""
    elif n == 1:
        count_phrase = (
            "Character lineup sheet for an animated short. "
            "EXACTLY 1 character standing centered, full body, "
        )
        names_clause = f" The character: {names[0]}."
    else:
        count_phrase = (
            f"Character lineup sheet for an animated short. "
            f"EXACTLY {n} characters and ONLY {n} characters standing side by side "
            f"(no extra characters, no background figures, no crowd), "
            f"full body, "
        )
        names_clause = f" The {n} characters in order: {', '.join(names)}."

    cast_override = flux_lineup_override(character_template)
    cast_clause = f" {cast_override}" if cast_override else ""

    lineup_prompt = (
        f"{count_phrase}"
        "facing camera, neutral expressions, plain warm-grey background, "
        "consistent rendering style and color palette across all characters."
        f"{cast_clause}"
        f"{names_clause} "
        f"Style and visual treatment: "
        f"{script.global_setting.strip() or 'cinematic 3D animation, vertical 9:16'}. "
        "Design-sheet aesthetic, high detail. NO text, NO watermark, NO logo."
    )
    # Match the character_sheet aspect ratio to the downstream video model:
    #   Veo accepts any reference and renders to its own configured aspect_ratio.
    #   Kling 2.1 INHERITS the reference image's aspect ratio — a 1:1 sheet
    #   produces 1:1 square clips (verified on the 2026-05-19-095639 test run,
    #   where every output came back 1440x1440). Use 9:16 when shipping to Kling
    #   so clips arrive vertical and don't need an ffmpeg crop in post.
    from pipeline.kie import is_unified_model
    sheet_aspect = "9:16" if is_unified_model(cfg.kie.model) else "1:1"
    pipeline.character_sheet.generate_character_sheet(
        client=client,
        out_path=paths.character_sheet_png,
        lineup_prompt=lineup_prompt,
        model=cfg.kie.flux_model,
        aspect_ratio=sheet_aspect,
        poll_interval_s=cfg.kie.poll_interval_s,
        poll_timeout_s=cfg.kie.poll_timeout_s,
    )


def _stage_align(paths: RunPaths, script: Script) -> list[WordTiming]:
    """Refine word_timings.json with Whisper force-alignment.

    Skipped when the per-beat narration path already produced deterministic
    timings (parts_dir is present): per-beat boundaries are exact, so
    Whisper would only add transcription error.
    """
    if (paths.root / "narration_beats").exists():
        return [WordTiming.from_dict(d)
                for d in json.loads(paths.word_timings_json.read_text(encoding="utf-8"))]
    real_timings = pipeline.align.align_arabic(
        audio_path=paths.narration_mp3,
        expected_text=script.story_combined,
    )
    paths.word_timings_json.write_text(
        json.dumps([t.to_dict() for t in real_timings], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return real_timings


def _stage_native_audio_timings(paths: RunPaths, script: Script) -> list[WordTiming]:
    """Build word_timings.json by Whisper-aligning each Veo clip's audio.

    Veo generates dialogue audio inside each clip; the audio's actual start /
    end / pacing is unpredictable. Whisper runs as a stopwatch on each clip
    (its Arabic transcription is discarded — it's wrong anyway), then we
    render the ORIGINAL script text at the timings Whisper produced. Result:
    captions stay in lockstep with whatever Veo actually said, even when
    dialogue starts late or ends early in a clip.

    Falls back to a uniform-distribution-across-clip estimate per beat only
    if Whisper returns no spans for that clip (very short / silent audio).
    """
    if not script.beats:
        return []
    timings: list[dict] = []
    cursor_ms = 0
    for i, beat in enumerate(script.beats, start=1):
        clip_path = paths.clips_dir / f"{i:02d}.mp4"
        clip_ms = int(_probe_duration_s(clip_path) * 1000) if clip_path.exists() else 0
        words = [w for w in beat.arabic.split() if w.strip()]
        if not words or clip_ms <= 0:
            cursor_ms += clip_ms
            continue

        try:
            beat_timings = pipeline.align.align_arabic(
                audio_path=clip_path,
                expected_text=beat.arabic,
            )
        except Exception as e:
            # Whisper failure on one clip shouldn't blow up the whole run.
            # Fall back to uniform distribution for this beat only.
            print(f"[align] clip {i:02d}: whisper failed ({type(e).__name__}: {e}); "
                  f"using uniform distribution")
            beat_timings = []

        if beat_timings:
            for t in beat_timings:
                timings.append({
                    "word": t.word,
                    "offset_ms": cursor_ms + t.offset_ms,
                    "duration_ms": t.duration_ms,
                })
        else:
            # Last-resort fallback per-beat
            per_word = max(int(clip_ms * 0.85) // len(words), 1)
            for j, w in enumerate(words):
                timings.append({
                    "word": w,
                    "offset_ms": cursor_ms + j * per_word,
                    "duration_ms": per_word,
                })
        cursor_ms += clip_ms

    paths.word_timings_json.write_text(
        json.dumps(timings, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return [WordTiming.from_dict(t) for t in timings]


def _stage_video_chained(
    args, cfg: Config, script: Script, paths: RunPaths,
    *, character_template: str | None = None,
    dialect: str | None = None,
    art_style: str | None = None,
) -> None:
    """Tier-3 video stage: REFERENCE_2_VIDEO with character sheet + chained last frames.

    Replaces _stage_video for the --shorts path. --skip-video uses the same
    black-frame placeholder approach (per beat's clip_duration_s).
    """
    if args.skip_video:
        # Black mp4 placeholder per beat (same approach as old _stage_video).
        import subprocess
        paths.clips_dir.mkdir(parents=True, exist_ok=True)
        for i, beat in enumerate(script.beats):
            p = paths.clips_dir / f"{i+1:02d}.mp4"
            if p.exists():
                continue
            subprocess.run([
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i",
                f"color=c=black:s=1080x1920:d={beat.clip_duration_s}",
                "-f", "lavfi", "-i",
                f"anullsrc=r=24000:cl=stereo:d={beat.clip_duration_s}",
                "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "128k", "-shortest",
                str(p),
            ], check=True)
        return

    reroll = []
    if args.reroll_clips:
        reroll = [int(x) for x in args.reroll_clips.split(",")]
    max_spend = args.max_spend if args.max_spend is not None else cfg.kie.max_spend_usd
    client = _build_kie()
    role = "service" if args.user_id == "admin" else "user"
    user = _User(id=args.user_id, email=None, role=role)
    run_id = paths.root.name  # the run dir's name = the run_id
    _pipeline_video.generate_clips_chained(
        client=client,
        script=script,
        clips_dir=paths.clips_dir,
        last_frames_dir=paths.last_frames_dir,
        spend_log_path=paths.kie_spend_json,
        character_sheet_path=paths.character_sheet_png,
        model=cfg.kie.model,
        aspect_ratio=cfg.kie.aspect_ratio,
        cost_per_second_usd=cfg.kie.cost_per_second_usd,
        max_spend_usd=max_spend,
        poll_interval_s=cfg.kie.poll_interval_s,
        poll_timeout_s=cfg.kie.poll_timeout_s,
        reroll_indices=reroll,
        with_dialogue=cfg.kie.native_audio,
        character_template=character_template,
        dialect=dialect,
        character_descriptions=script.character_descriptions or None,
        art_style=art_style,
        user=user,
        run_id=run_id,
    )


def _stage_shorts_captions(cfg: Config, timings: list[WordTiming], paths: RunPaths) -> Path:
    """Generate yellow burned-in Arabic captions in @sunstoriz style.

    Returns the .ass path so the assembler burns it into the final mp4.
    Set --no-burn-captions if you want voice-only (overrides this default).
    """
    generate_captions(
        timings=timings, srt_path=paths.captions_srt,
        ass_path=paths.captions_ass,
        font="Cairo-Black", font_size=110,  # bigger for vertical readability
        style="tiktok", play_res_x=1080, play_res_y=1920,
    )
    return paths.captions_ass


def _probe_duration_s(path: Path) -> float:
    """ffprobe a media file's duration in seconds."""
    import subprocess
    out = subprocess.check_output([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "csv=p=0",
        str(path),
    ], text=True).strip()
    return float(out)


def _stage_shorts_assemble(cfg: Config, script: Script, paths: RunPaths,
                            burn_caption_ass: Path | None,
                            *, native_audio: bool = False) -> None:
    clip_paths = [paths.clips_dir / f"{i+1:02d}.mp4" for i in range(len(script.beats))]
    # Probe ACTUAL clip durations — Veo often returns 8s even when we ask for 10s,
    # and using config's expected duration breaks xfade offsets.
    clip_durations = [_probe_duration_s(p) for p in clip_paths]
    narration_path = None if native_audio else paths.narration_mp3
    narration_duration = (
        None if native_audio else _probe_duration_s(paths.narration_mp3)
    )
    assemble_shorts_video(
        clip_paths=clip_paths,
        clip_durations_s=clip_durations,
        narration_path=narration_path,
        music_path=paths.music_track_mp3,
        out_path=paths.final_mp4,
        burn_caption_ass=burn_caption_ass,
        output_width=1080, output_height=1920,
        crossfade_ms=cfg.assemble.shot_crossfade_ms,
        narration_duration_s=narration_duration,
    )


def main_with_args(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Arabic horror faceless pipeline")
    p.add_argument("--theme", help="Theme tag (manual mode)")
    p.add_argument("--seed", help="Arabic premise (manual mode)")
    p.add_argument("--resume", help="Resume an existing run dir")
    p.add_argument("--run-dir", help="Use a specific run dir (advanced)")
    p.add_argument(
        "--user-id",
        default="admin",
        help="User who owns this run. Defaults to 'admin' for CLI / cron use. "
             "Runs land in out/<user_id>/<timestamp>/ unless --run-dir is given.",
    )
    p.add_argument("--reroll-images", help="Comma-separated 1-based indices to regenerate")
    p.add_argument("--skip-images", action="store_true", help="Use placeholder images (dev only)")
    p.add_argument("--voice", help="Override Edge TTS voice (e.g. ar-EG-ShakirNeural)")
    p.add_argument("--burn-captions", action="store_true",
                   help="Burn captions into video (default: SRT only)")
    p.add_argument("--config", default=str(DEFAULT_CONFIG))
    p.add_argument("--out-root", default=str(DEFAULT_OUT_ROOT))
    p.add_argument("--music-bundle", default=str(DEFAULT_MUSIC_BUNDLE))
    # Pipeline mode selector -----------------------------------------------
    p.add_argument(
        "--mode", choices=["horror", "song"], default="horror",
        help="Pipeline mode. 'song' runs the AI song pipeline after a user "
             "approval (Suno → Flux cover → ffmpeg assemble).",
    )
    # Shorts mode (Kie.ai) ------------------------------------------------
    p.add_argument("--shorts", action="store_true",
                   help="Use Shorts/TikTok pipeline (Kie.ai Veo, vertical 9:16, ~30s)")
    p.add_argument("--reroll-clips", help="Comma-separated 1-based clip indices to regenerate (Shorts mode)")
    p.add_argument("--skip-video", action="store_true",
                   help="Use placeholder black mp4 clips (Shorts dev only)")
    p.add_argument("--max-spend", type=float, default=None,
                   help="Override config.kie.max_spend_usd for this run")
    p.add_argument("--pause-after-script", action="store_true",
                   help="Exit cleanly after the script stage. Used by the API server "
                        "to gate paid stages on human approval. Resume with --resume "
                        "<dir> (use --pause-after-character-sheet to also gate after Flux).")
    p.add_argument("--pause-after-character-sheet", action="store_true",
                   help="Exit cleanly after Flux character_sheet.png is written. "
                        "Used by the API server to gate Veo spend on a second "
                        "human approval. Resume with --resume <dir>.")
    p.add_argument("--no-burn-captions", action="store_true",
                   help="Skip burned-in Arabic captions (Shorts default = burn-in)")
    # Freeform script writer (premise-driven, no fixed template) ---------------
    p.add_argument("--freeform", action="store_true",
                   help="Use the freeform script writer (premise-driven, "
                        "no fixed character/dialect/ending). Requires --shorts.")
    p.add_argument("--ff-dialect", default="msa",
                   choices=["msa", "syrian", "egyptian", "khaliji",
                             "maghrebi", "iraqi"])
    p.add_argument("--ff-art-style", default="cinematic_photo_real",
                   choices=["pixar_3d", "anime_2d", "cinematic_photo_real",
                             "claymation", "hand_drawn", "ghibli"])
    p.add_argument("--ff-character-template", default="ai_choose",
                   choices=["human", "fruit_sunstoriz", "animal",
                             "surreal", "ai_choose"])
    p.add_argument("--ff-ending-type", default="ai_choose",
                   choices=["open", "closed_tragic", "closed_happy",
                             "twist", "ai_choose"])
    p.add_argument("--ff-num-beats", type=int, default=8)
    p.add_argument("--ff-per-beat-seconds", type=int, default=8)
    p.add_argument("--ff-narration-style", default="cinematic",
                   choices=["cinematic", "first_person_monologue", "ai_choose"])
    args = p.parse_args(argv)

    # When resuming a run, look for freeform_controls.json next to script.json
    # and replay the chosen controls. This makes freeform mode survive
    # /approve, /reroll, /character-sheet-reroll spawns from the API server,
    # which today only pass --shorts --resume <dir> with no --freeform flag.
    def _maybe_load_freeform_controls_from_disk(args):
        if not args.resume:
            return
        if args.freeform:
            return  # explicit CLI flag wins
        controls_path = Path(args.resume) / "freeform_controls.json"
        if not controls_path.exists():
            return
        try:
            d = json.loads(controls_path.read_text(encoding="utf-8"))
        except Exception:
            return
        args.freeform = True
        # Only override defaults the file actually carries — be defensive.
        for k, attr in [
            ("dialect", "ff_dialect"),
            ("art_style", "ff_art_style"),
            ("character_template", "ff_character_template"),
            ("ending_type", "ff_ending_type"),
            ("num_beats", "ff_num_beats"),
            ("per_beat_seconds", "ff_per_beat_seconds"),
            ("narration_style", "ff_narration_style"),
        ]:
            if k in d:
                setattr(args, attr, d[k])

    _maybe_load_freeform_controls_from_disk(args)

    cfg = load_config(Path(args.config))
    out_root = Path(args.out_root)
    music_bundle = Path(args.music_bundle)
    project_theme_log = out_root / "theme_log.json"
    project_story_history = out_root / "story_history.jsonl"

    run_dir = _resolve_run_dir(args, out_root)
    paths = RunPaths(root=run_dir)
    log = RunLog(run_dir)

    try:
        if args.mode == "song":
            return _run_song_post_approve(args)

        gemini = _build_gemini()
        log.info(f"run dir: {run_dir}  mode={'shorts' if args.shorts else 'long-form'}")

        if args.shorts:
            # Native-audio mode: Veo generates voice + lip sync per clip from
            # the dialogue baked into the prompt. We skip ElevenLabs and the
            # Whisper align stage; word timings are derived from clip lengths
            # after the video stage runs.
            #
            # `--skip-video` keeps using the ElevenLabs path so the placeholder
            # run still has audio to verify captions/duration logic against.
            use_native_audio = cfg.kie.native_audio and not args.skip_video

            with log.stage("seed"):
                seed = _stage_seed(args, gemini, log, paths, project_theme_log)
            with log.stage("script"):
                if paths.script_json.exists():
                    from pipeline.types import Script as _Script
                    import json as _json
                    script = _Script.from_dict(
                        _json.loads(paths.script_json.read_text(encoding="utf-8"))
                    )
                else:
                    from pipeline.script_freeform import (
                        FreeformControls, generate_freeform_script,
                    )
                    controls = FreeformControls(
                        dialect=args.ff_dialect,
                        art_style=args.ff_art_style,
                        character_template=args.ff_character_template,
                        ending_type=args.ff_ending_type,
                        num_beats=args.ff_num_beats,
                        per_beat_seconds=args.ff_per_beat_seconds,
                        narration_style=args.ff_narration_style,
                    )
                    script = generate_freeform_script(gemini, seed, controls)
                    import json as _json
                    paths.script_json.write_text(
                        _json.dumps(script.to_dict(), ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
            with log.stage("coherence_pass"):
                # Cross-clip continuity sweep — rewrites english_motion for any
                # beat that breaks role/location/causality with its neighbors.
                # Idempotent: the sidecar marker prevents re-running on resume,
                # so user-approved scripts are never mutated after approval.
                marker = paths.root / "coherence_pass_v1.applied"
                if not marker.exists():
                    try:
                        from pipeline.coherence_pass import apply_coherence_pass
                        before = tuple(b.english_motion for b in script.beats)
                        script = apply_coherence_pass(script, gemini)
                        after = tuple(b.english_motion for b in script.beats)
                        n_rewritten = sum(1 for a, b in zip(before, after) if a != b)
                        if n_rewritten > 0:
                            import json as _json
                            paths.script_json.write_text(
                                _json.dumps(script.to_dict(), ensure_ascii=False, indent=2),
                                encoding="utf-8",
                            )
                            log.info(
                                f"coherence_pass: rewrote {n_rewritten}/"
                                f"{len(before)} beats"
                            )
                        else:
                            log.info(
                                f"coherence_pass: 0 rewrites "
                                f"({len(before)} beats already coherent)"
                            )
                        marker.write_text("v1", encoding="utf-8")
                    except Exception as _ce:
                        # Never block the render on coherence pass failure.
                        log.info(f"coherence_pass: skipped ({type(_ce).__name__})")
            if args.pause_after_script:
                # Approval gate for the mobile-app workflow. Script is on disk;
                # bail out before any paid stage so a human reviewer can decide.
                # Resume with --resume <dir> to continue past character_sheet.
                log.info("PAUSED: script generated, awaiting approval. "
                         f"Resume with: uv run python run.py --shorts --resume {run_dir}")
                return 0
            if not use_native_audio:
                with log.stage("voice"):
                    _stage_shorts_voice(args, cfg, script, paths)
                with log.stage("align"):
                    timings = _stage_align(paths, script)
            else:
                log.info("voice/align: skipped (kie.native_audio=true — Veo will "
                         "generate dialogue audio with lip sync per clip)")
            with log.stage("character_sheet"):
                if args.skip_video:
                    log.info("character_sheet: skipped (--skip-video; sheet is only "
                             "used as a Veo reference)")
                else:
                    _stage_character_sheet(
                        _build_kie(), cfg, paths, script,
                        freeform_mode=True,
                        character_template=args.ff_character_template,
                    )
            if args.pause_after_character_sheet:
                if args.skip_video:
                    log.info("--pause-after-character-sheet ignored under --skip-video "
                             "(no character sheet was generated). Continuing.")
                else:
                    log.info("PAUSED: character_sheet generated, awaiting Veo approval. "
                             f"Resume with: uv run python run.py --shorts --resume {run_dir}")
                    return 0
            with log.stage("video"):
                _stage_video_chained(
                    args, cfg, script, paths,
                    character_template=args.ff_character_template,
                    dialect=args.ff_dialect,
                    art_style=args.ff_art_style,
                )
            # Everything below charges the user no money but consumes
            # already-charged clips. If any of these stages crashes,
            # the user has paid for clips and won't get a video — refund
            # them. This wraps native_audio_timings → music → captions
            # → assemble in a single try/except so one helper call
            # restores credits no matter where the failure lands.
            try:
                if use_native_audio:
                    with log.stage("native_audio_timings"):
                        timings = _stage_native_audio_timings(paths, script)
                with log.stage("music"):
                    _stage_music(script, music_bundle, paths)
                with log.stage("captions"):
                    burn_ass = _stage_shorts_captions(cfg, timings, paths)
                    # @sunstoriz style burns yellow captions by default; allow opt-out.
                    if args.no_burn_captions:
                        burn_ass = None
                with log.stage("assemble"):
                    _stage_shorts_assemble(cfg, script, paths, burn_ass,
                                            native_audio=use_native_audio)
            except Exception as assembly_exc:
                # Refund every credit charged for this run — clips were
                # generated but no final video was produced. Best-effort:
                # if the refund itself fails we still re-raise the
                # original failure (the user is the one who needs to
                # know what went wrong, not the refund logger).
                try:
                    from pipeline.auth import User as _U
                    from pipeline.credits import refund_run_charges
                    _refund_role = "service" if args.user_id == "admin" else "user"
                    _refund_user = _U(id=args.user_id, email=None, role=_refund_role)
                    refunded = refund_run_charges(
                        _refund_user,
                        run_id=paths.root.name,
                        reason=(
                            f"post-video stage failed "
                            f"({type(assembly_exc).__name__}): clips were "
                            f"generated but no final mp4 was produced"
                        ),
                    )
                    if refunded > 0:
                        log.error(
                            f"REFUNDED {refunded} credits to user {args.user_id} "
                            f"for run {paths.root.name} (assembly failed)"
                        )
                except Exception as refund_exc:
                    log.error(
                        f"REFUND FAILED for user {args.user_id} run "
                        f"{paths.root.name}: {type(refund_exc).__name__}: "
                        f"{refund_exc}. Manual credit return required."
                    )
                raise
        else:
            with log.stage("seed"):
                seed = _stage_seed(args, gemini, log, paths, project_theme_log)
            with log.stage("script"):
                script = _stage_script(gemini, cfg, seed, paths, project_story_history)
            with log.stage("voice"):
                timings = _stage_voice(args, cfg, script, paths)
            with log.stage("shots"):
                shots = _stage_shots(gemini, script, timings, paths)
            with log.stage("images"):
                _stage_images(args, cfg, shots, paths)
            with log.stage("music"):
                _stage_music(script, music_bundle, paths)
            with log.stage("captions"):
                burn_ass = _stage_captions(args, cfg, timings, paths)
            with log.stage("assemble"):
                _stage_assemble(cfg, shots, paths, burn_ass)
        log.info(f"DONE: {paths.final_mp4}")
        return 0
    except Exception as exc:
        log.error(f"FAILED: {type(exc).__name__}: {exc}")
        return 1
    finally:
        log.close()


def _run_song_post_approve(args) -> int:
    """Song-mode post-approve stage: Suno → cover → assemble.

    Reads song.json (written by POST /songs inline) from --resume dir.
    Writes api_state.json transitions: generating_song → generating_cover
    → assembling → complete (or failed).
    """
    import json
    import shutil
    import sys as _sys
    from pathlib import Path as _Path

    from pipeline import song, song_cover, song_assemble, song_align, song_og
    from pipeline import song_beats, song_cinematic, song_scenes
    from pipeline import song_import
    from pipeline.api import _build_song_llm  # Anthropic→Groq fallback router
    from pipeline.config import load_config
    from pipeline.kie import KieClient

    if not args.resume:
        print("--mode song requires --resume <run-dir>", file=_sys.stderr)
        return 2
    run_dir = _Path(args.resume)
    if not run_dir.is_dir():
        print(f"run dir not found: {run_dir}", file=_sys.stderr)
        return 2

    script_path = run_dir / "song.json"
    state_path = run_dir / "api_state.json"
    # Use REPO_ROOT/config.yaml as the default (matches api.py's pattern).
    # Relative "config.yaml" breaks on Cloud Run Jobs where the worker's
    # CWD isn't REPO_ROOT.
    import os as _os
    cfg_path_str = _os.environ.get(
        "FACELESS_CONFIG",
        str(REPO_ROOT / "config.yaml"),
    )
    cfg = load_config(_Path(cfg_path_str))

    def write_state(**patch):
        """Atomic state write — temp+rename so the API side can't read a
        torn JSON file mid-update."""
        state = json.loads(state_path.read_text()) if state_path.exists() else {}
        state.update(patch)
        tmp = state_path.with_suffix(state_path.suffix + ".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2))
        tmp.replace(state_path)

    try:
        # --- Import pre-stage: download + analyse a YouTube reference, then
        # write an ORIGINAL song.json and pause for approval. Import-mode only;
        # exits before the normal generation path. ---
        # NOTE: in this function song.json is normally read FIRST (below), and
        # current_state is loaded later. The import pre-stage runs when there is
        # no song.json yet, so we load current_state here at the top of the try
        # body, guard on it, and exit before the song.json read can crash.
        current_state = json.loads(state_path.read_text()) if state_path.exists() else {}
        if current_state.get("status") == "analyzing" and not (run_dir / "song.json").exists():
            write_state(status="analyzing")
            try:
                _llm = _build_song_llm()
                lang = current_state.get("language", "ar")
                if current_state.get("mode") == "cover":
                    # Upload-cover path: analyse the user's uploaded audio
                    # (real tempo + transcript) and KEEP its words. No
                    # download — the file is already on disk.
                    ref_name = current_state.get("reference_filename")
                    ref = run_dir / ref_name if ref_name else None
                    if not ref or not ref.exists():
                        raise RuntimeError(
                            "run is missing the uploaded reference audio")
                    analysis, transcript = song_import.analyze_reference(
                        ref, llm=_llm, language=lang)
                    script = song_import.build_cover_script(
                        llm=_llm, analysis=analysis, transcript=transcript,
                        instruction=current_state.get("import_instruction"),
                        language=lang,
                    )
                else:
                    url = current_state.get("youtube_url")
                    if not url:
                        raise song_import.ImportFetchError(
                            "run is missing a youtube_url")
                    # Audio-first; on a blocked download, falls back to free
                    # YouTube Data API metadata (title + description).
                    analysis, transcript = song_import.analyze_youtube(
                        url, run_dir, llm=_llm, language=lang)
                    script = song_import.build_inspired_script(
                        llm=_llm, analysis=analysis,
                        instruction=current_state.get("import_instruction"),
                        language=lang, transcript=transcript,
                    )
            except Exception as e:
                write_state(status="failed", failure_stage="analyzing", last_error=str(e))
                return 1
            (run_dir / "analysis.json").write_text(
                json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
            (run_dir / "song.json").write_text(json.dumps({
                "title": script.title, "lyrics": script.lyrics,
                "style_prompt": script.style_prompt, "cover_prompt": script.cover_prompt,
                "language": script.language, "art_direction": script.art_direction,
                "scene_prompts": script.scene_prompts,
                "vocal_gender": current_state.get("vocal_gender"),
                "persona_id": None,
                "suno_model": current_state.get("suno_model"),
                "video_mode": current_state.get("video_mode", "static"),
                # Cover mode carries through so the post-approve submit branch
                # picks the upload-cover endpoint + finds the reference audio.
                "mode": current_state.get("mode"),
                "reference_filename": current_state.get("reference_filename"),
            }, ensure_ascii=False, indent=2), encoding="utf-8")
            (run_dir / "lyrics.txt").write_text(script.lyrics, encoding="utf-8")
            write_state(status="awaiting_approval", title=script.title)
            return 0

        script = json.loads(script_path.read_text())
        client = KieClient()
        takes_dir = run_dir / "takes"
        song_mp3 = run_dir / "song.mp3"
        raw_cover_path = run_dir / "cover_raw.png"
        final_cover_path = run_dir / "cover.png"
        final_mp4 = run_dir / "final.mp4"

        # --- Stage 0: swap_to_take handling ---
        # If the API set swap_to_take=N in state, this run was
        # triggered by POST /songs/{id}/swap-take. Copy the requested
        # take's mp3 to song.mp3, update chosen_take, and let stages
        # 1 + 2 + 3 short-circuit (Suno + Flux skipped, only assemble
        # runs).
        current_state = json.loads(state_path.read_text()) if state_path.exists() else {}

        # Cinematic vs static video path. State wins over song.json so a
        # /resume after an upgrade can flip the mode; defaults to static.
        video_mode = current_state.get("video_mode") or script.get("video_mode", "static")
        scene_paths: list[_Path] = []

        swap_to = current_state.get("swap_to_take")
        if swap_to in (1, 2):
            print(f"[song-post-approve] swap-to-take {swap_to}")
            take_path = takes_dir / f"take_{swap_to}.mp3"
            if take_path.exists():
                with take_path.open("rb") as src, song_mp3.open("wb") as dst:
                    while chunk := src.read(1 << 20):
                        dst.write(chunk)
                write_state(chosen_take=swap_to, swap_to_take=None)
            else:
                print(f"[song-post-approve] WARN swap target {take_path} missing — skipping")
                write_state(swap_to_take=None)

        # --- Stage 1: Suno song ---
        # Skip if BOTH takes are already on disk from a prior partial run.
        # This is the spec's deferred "stage-aware /resume" — it lets the
        # user retry a Flux/assemble failure without re-spending on Suno
        # (the expensive stage).
        existing_takes = sorted(takes_dir.glob("take_*.mp3")) if takes_dir.exists() else []
        if len(existing_takes) >= 2 and song_mp3.exists():
            print(f"[song-post-approve] skipping Suno — {len(existing_takes)} takes already on disk")
            write_state(status="generating_song")  # status moment so UI shows progress
        else:
            write_state(status="generating_song")
            # Voice-control params from song.json (set by POST /songs):
            #   vocal_gender: 'm' / 'f' — increases probability of gender
            #   persona_id:   pins specific singer voice across runs
            # See pipeline/song.py submit_song_job docstring.
            _model = (
                script.get("suno_model")
                or (cfg.song.suno_model if cfg.song else song.SUNO_MODEL_ID)
            )
            is_cover = (current_state.get("mode") == "cover"
                        or script.get("mode") == "cover")
            if is_cover:
                # Faithful cover: hand Suno the uploaded reference so it keeps
                # the source's core melody, singing the reviewed words.
                from pipeline import video as _video
                ref_name = (current_state.get("reference_filename")
                            or script.get("reference_filename"))
                ref_path = run_dir / ref_name if ref_name else None
                if not ref_path or not ref_path.exists():
                    raise FileNotFoundError(
                        f"cover run missing reference audio: {ref_name!r}")
                upload_url = _video._upload_file_get_url(
                    ref_path, content_type="audio/mpeg")
                print(f"[song-post-approve] cover mode — uploaded reference to {upload_url}")
                task_id = song.submit_cover_job(
                    client,
                    upload_url=upload_url,
                    lyrics=script["lyrics"],
                    style_prompt=script["style_prompt"],
                    title=script["title"],
                    model=_model,
                    vocal_gender=script.get("vocal_gender"),
                    # Faithfulness knob from the upload form (state-stored;
                    # None → Suno's default).
                    audio_weight=current_state.get("audio_weight"),
                )
            else:
                task_id = song.submit_song_job(
                    client,
                    lyrics=script["lyrics"],
                    style_prompt=script["style_prompt"],
                    title=script["title"],
                    # Per-song model override (set by POST /songs) wins
                    # over config default, falling back to V5_5 baseline.
                    model=_model,
                    vocal_gender=script.get("vocal_gender"),
                    persona_id=script.get("persona_id"),
                )
            takes = song.wait_for_song(client, task_id)
            takes_dir.mkdir(exist_ok=True)
            for i, take in enumerate(takes, start=1):
                song.download_take(client, take.url, takes_dir / f"take_{i}.mp3")

            # Persist Suno taskId + per-take audioIds so a future
            # /save-persona call has the references it needs (Kie's
            # persona/generate endpoint requires both).
            write_state(
                suno_task_id=task_id,
                take_audio_ids=[t.audio_id for t in takes],
            )

            # Pick the longer take (Suno truncates one ~20% of the time)
            if len(takes) >= 2:
                chosen = 1 if takes[0].duration_s >= takes[1].duration_s else 2
            else:
                chosen = 1
            chosen_path = takes_dir / f"take_{chosen}.mp3"
            # GCS Fuse (Cloud Run mount) refuses unlink with EPERM, but
            # accepts truncate-on-write. Copy via binary write rather
            # than shutil.copy(.., unlink-first) so the same code path
            # works on local disk AND on the production GCS Fuse mount.
            with chosen_path.open("rb") as src, song_mp3.open("wb") as dst:
                while chunk := src.read(1 << 20):
                    dst.write(chunk)
            write_state(chosen_take=chosen)

        # --- Stage 2: cover ---
        # Skip the Flux call if cover_raw.png is already on disk; just
        # re-do the title overlay (which is free and deterministic).
        # POST /songs/{id}/regenerate-cover sets regenerate_cover=true
        # in state to force a fresh Flux call even when cover_raw.png
        # already exists.
        write_state(status="generating_cover")
        # Re-read state in case the API set regenerate_cover after
        # we initially loaded it.
        current_state = json.loads(state_path.read_text()) if state_path.exists() else {}
        force_regen_cover = current_state.get("regenerate_cover", False)
        if raw_cover_path.exists() and not force_regen_cover:
            print(f"[song-post-approve] skipping Flux — cover_raw.png already on disk")
        else:
            if force_regen_cover:
                print(f"[song-post-approve] regenerate_cover flag set — calling Flux fresh")
            raw_cover_path = song_cover.generate_cover_image(
                client=client,
                cover_prompt=script["cover_prompt"],
                out_dir=run_dir,
            )
            # Clear the flag — single-use
            if force_regen_cover:
                write_state(regenerate_cover=False)
        song_cover.apply_title_overlay(
            raw_path=raw_cover_path,
            title=script["title"],
            language=script.get("language", "ar"),
            out_path=final_cover_path,
        )

        # --- Stage 2b: cinematic scene pool ---
        # Render the per-section image pool that the beat-synced video
        # cuts between. Style-locked to art_direction; falls back to the
        # cover for any scene that fails to render. Static mode skips this.
        if video_mode == "cinematic":
            scene_paths = song_cover.generate_scene_images(
                client=client,
                art_direction=script.get("art_direction", ""),
                scene_prompts=script.get("scene_prompts") or [script["cover_prompt"]],
                out_dir=run_dir,
                cover_fallback=final_cover_path,
            )

        # --- Stage 2.1: compose Open Graph card ---
        # Per-song 1200x630 OG image so social previews (WhatsApp,
        # Twitter, Instagram, iMessage) show the actual cover + title
        # rather than the generic Faceless Lab placeholder. Lazy
        # endpoint at /p/{token}/og will regenerate this on demand if
        # missing, so failure here is non-blocking — the rest of the
        # pipeline can continue.
        try:
            teaser_lines: list[str] = []
            for raw in (script.get("lyrics") or "").split("\n"):
                line = raw.strip()
                if not line or line.startswith("["):
                    continue
                teaser_lines.append(line)
                if len(teaser_lines) >= 2:
                    break
            song_og.compose_og_image(
                cover_path=final_cover_path,
                title=script["title"],
                language=script.get("language", "ar"),
                teaser=" · ".join(teaser_lines),
                out_path=run_dir / "og.png",
            )
        except Exception as og_err:
            print(f"[song-post-approve] OG compose failed (non-blocking): {og_err}")

        # --- Stage 2.5: align lyrics to audio ---
        # Whisper-as-stopwatch produces lyrics.json with per-line timings.
        # Drives BOTH the share-page karaoke (replaces the old N/duration
        # linear approximation) AND the burned-in MP4 captions. Idempotent:
        # if lyrics.json exists from a previous run, skips Whisper. See
        # pipeline/song_align.py.
        write_state(status="aligning")
        lyrics_json = run_dir / "lyrics.json"
        try:
            song_align.align_song_lyrics(
                song_mp3=song_mp3,
                lyrics=script["lyrics"],
                out_json=lyrics_json,
            )
        except Exception as align_err:
            # Alignment is best-effort — if Whisper fails we still want the
            # MP4 to ship (just without burned-in captions). The share page
            # falls back to the legacy stanza-divided timing.
            print(f"[song-post-approve] lyrics alignment failed, "
                  f"continuing without captions: {align_err}")

        # --- Stage 2.6: beat detection (cinematic only) ---
        # New resumable status. detect_beats() never raises (it falls back
        # to a fixed-BPM grid internally) and caches beats.json, so a
        # /resume after this point is cheap.
        beats_data = None
        if video_mode == "cinematic":
            write_state(status="detecting_beats")
            beats_data = song_beats.detect_beats(
                song_mp3, out_json=run_dir / "beats.json",
            )

        # --- Stage 3: assemble ---
        write_state(status="assembling")
        # share_token may already exist from a prior /songs/{id}/share
        # POST. If not, the watermark MP4 will simply name the project
        # without a deep link (still attributes; just no per-share URL).
        share_token = current_state.get("share_token") or None
        lyrics_arg = lyrics_json if lyrics_json.exists() else None

        if video_mode == "cinematic" and scene_paths:
            sections = song_scenes.extract_sections(
                json.loads(lyrics_json.read_text(encoding="utf-8"))
                if lyrics_json.exists() else {"lines": []}
            )
            schedule = song_scenes.build_cut_schedule(
                beat_times=(beats_data or {}).get("beat_times", []),
                sections=sections,
                pool_size=len(scene_paths),
                audio_duration=song_assemble.ffprobe_duration(song_mp3),
                bars_per_cut=cfg.song.bars_per_cut if cfg.song else 4,
            )
            try:
                song_cinematic.assemble_cinematic_song_video(
                    scene_paths=scene_paths, song_mp3=song_mp3, out_mp4=final_mp4,
                    schedule=schedule, lyrics_json=lyrics_arg,
                    title=script.get("title"), share_token=share_token,
                )
            except Exception as cine_err:
                # Cinematic render failed — fall back to the static cover
                # video so the user still gets a playable file. The API
                # refunds the cinematic surcharge when it sees this flag.
                print(f"[song-post-approve] cinematic assemble failed ({cine_err}); "
                      f"falling back to static cover video")
                song_assemble.assemble_song_video(
                    cover_path=final_cover_path, song_mp3=song_mp3, out_mp4=final_mp4,
                    lyrics_json=lyrics_arg, title=script.get("title"),
                    share_token=share_token,
                )
                write_state(video_downgraded=True)
        else:
            song_assemble.assemble_song_video(
                cover_path=final_cover_path, song_mp3=song_mp3, out_mp4=final_mp4,
                lyrics_json=lyrics_arg, title=script.get("title"),
                share_token=share_token,
            )
            # A cinematic-priced run that reaches the static path (e.g. no
            # scene pool was produced) owes the surcharge back, same as a
            # cinematic render failure. The API reconciles the refund.
            if video_mode == "cinematic":
                write_state(video_downgraded=True)

        # watermarked=True signals to the API + Flutter UI that this
        # song's final.mp4 carries the brand-mark PNG overlay + container
        # metadata from the launch-readiness work. Songs assembled before
        # this flag was added show watermarked=False (or missing) and
        # surface a "Apply watermark" button in the song detail UI.
        write_state(status="complete", watermarked=True)

        # --- Channel Autopilot: per-artist YouTube auto-publish ---
        # If this song belongs to an artist with the toggle ON and the user
        # has connected YouTube, publish now. Failures NEVER fail the
        # completed run — they land in youtube_publish_error for the UI.
        try:
            final_state = json.loads(state_path.read_text())
            aid = final_state.get("artist_id")
            if aid and not final_state.get("youtube_url"):
                from pipeline import artists as _artists
                from pipeline import youtube as _yt
                user_root = run_dir.parent
                artist = _artists.find_by_id(
                    _artists.load_artists(user_root), aid)
                if (artist and artist.get("auto_publish_youtube")
                        and _yt.load_token(user_root) is not None):
                    from pipeline.api import _publish_song_to_youtube
                    vid, url = _publish_song_to_youtube(
                        run_dir, user_root, artist)
                    write_state(youtube_video_id=vid, youtube_url=url,
                                youtube_publish_error=None)
                    print(f"[song-post-approve] auto-published to YouTube: {url}")
        except Exception as e:
            print(f"[song-post-approve] WARN auto-publish failed: {e}")
            write_state(youtube_publish_error=str(e))
        return 0
    except Exception as e:
        # Tag the failure with the stage we were in, so the API can
        # surface "Suno timeout" vs "cover failed" vs "ffmpeg error"
        # to the user instead of an opaque message.
        prev_status = json.loads(state_path.read_text()).get("status", "unknown") \
            if state_path.exists() else "unknown"
        write_state(
            status="failed",
            failure_stage=prev_status,
            last_error=f"{type(e).__name__}: {e}",
        )
        print(f"[song-post-approve] failed: {e}", file=_sys.stderr)
        return 1


def main() -> int:
    return main_with_args(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
