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
from pipeline.captions import generate_captions
from pipeline.config import Config, load_config
from pipeline.images import generate_images
from pipeline.kie import KieClient
from pipeline.llm import GeminiClient
from pipeline.llm_groq import GroqClient
from pipeline.music import select_music_track
from pipeline.runlog import RunLog
from pipeline.script import generate_script_with_uniqueness, generate_shorts_script
from pipeline.seed import auto_seed, manual_seed, record_theme_use
from pipeline.shots import generate_shots
from pipeline.types import RunPaths, Script, Shot, ThemeSeed, WordTiming
from pipeline.video import generate_clips
from pipeline.voice import generate_narration


REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = REPO_ROOT / "config.yaml"
DEFAULT_OUT_ROOT = REPO_ROOT / "out"
DEFAULT_MUSIC_BUNDLE = REPO_ROOT / "assets" / "music"
DEFAULT_FONTS_DIR = REPO_ROOT / "assets" / "fonts"
PROJECT_THEME_LOG = DEFAULT_OUT_ROOT / "theme_log.json"
PROJECT_STORY_HISTORY = DEFAULT_OUT_ROOT / "story_history.jsonl"


def _build_gemini():
    """Build the LLM client used by stages.

    Prefer Groq if GROQ_API_KEY is set (Groq's free tier has way more headroom
    than Gemini's free tier — Llama 3.3 70B handles Arabic well). Otherwise
    fall back to Gemini. Both expose the same .complete()/.embed() interface,
    though Groq's .embed() raises NotImplementedError (only the long-form
    repetition guard uses embeddings; Shorts path never calls it).
    """
    if os.environ.get("GROQ_API_KEY"):
        return GroqClient()
    return GeminiClient()


def _build_kie() -> KieClient:
    """Indirection so tests can monkeypatch."""
    return KieClient()


def _make_run_dir(out_root: Path) -> Path:
    out_root.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d-%H%M")
    run_dir = out_root / ts
    # Ensure uniqueness if two runs start in the same minute.
    suffix = 0
    while run_dir.exists():
        suffix += 1
        run_dir = out_root / f"{ts}-{suffix}"
    run_dir.mkdir()
    return run_dir


def _resolve_run_dir(args, out_root: Path) -> Path:
    if args.resume:
        return Path(args.resume).resolve()
    if args.run_dir:
        return Path(args.run_dir).resolve()
    return _make_run_dir(out_root)


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

def _stage_shorts_script(gemini, seed: ThemeSeed, cfg: Config, paths: RunPaths) -> Script:
    if paths.script_json.exists():
        return Script.from_dict(json.loads(paths.script_json.read_text(encoding="utf-8")))
    script = generate_shorts_script(
        gemini, seed, min_beats=cfg.kie.num_clips, max_beats=max(cfg.kie.num_clips, 15),
    )
    paths.script_json.write_text(
        json.dumps(script.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return script


def _stage_shorts_voice(args, cfg: Config, script: Script, paths: RunPaths) -> list[WordTiming]:
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


def _stage_character_sheet(client, cfg: Config, paths: RunPaths, script: Script) -> None:
    """Generate a Flux character sheet for visual consistency across Veo clips."""
    pipeline.character_sheet.generate_character_sheet(
        client=client,
        out_path=paths.character_sheet_png,
        global_setting=script.global_setting,
        model=cfg.kie.flux_model,
        poll_interval_s=cfg.kie.poll_interval_s,
        poll_timeout_s=cfg.kie.poll_timeout_s,
    )


def _stage_align(paths: RunPaths, script: Script) -> list[WordTiming]:
    """Refine word_timings.json with Whisper force-alignment."""
    real_timings = pipeline.align.align_arabic(
        audio_path=paths.narration_mp3,
        expected_text=script.story_combined,
    )
    paths.word_timings_json.write_text(
        json.dumps([t.to_dict() for t in real_timings], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return real_timings


def _stage_video_chained(args, cfg: Config, script: Script, paths: RunPaths) -> None:
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
                            burn_caption_ass: Path | None) -> None:
    clip_paths = [paths.clips_dir / f"{i+1:02d}.mp4" for i in range(len(script.beats))]
    # Probe ACTUAL clip durations — Veo often returns 8s even when we ask for 10s,
    # and using config's expected duration breaks xfade offsets.
    clip_durations = [_probe_duration_s(p) for p in clip_paths]
    assemble_shorts_video(
        clip_paths=clip_paths,
        clip_durations_s=clip_durations,
        narration_path=paths.narration_mp3,
        music_path=paths.music_track_mp3,
        out_path=paths.final_mp4,
        burn_caption_ass=burn_caption_ass,
        output_width=1080, output_height=1920,
        crossfade_ms=cfg.assemble.shot_crossfade_ms,
    )


def main_with_args(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Arabic horror faceless pipeline")
    p.add_argument("--theme", help="Theme tag (manual mode)")
    p.add_argument("--seed", help="Arabic premise (manual mode)")
    p.add_argument("--resume", help="Resume an existing run dir")
    p.add_argument("--run-dir", help="Use a specific run dir (advanced)")
    p.add_argument("--reroll-images", help="Comma-separated 1-based indices to regenerate")
    p.add_argument("--skip-images", action="store_true", help="Use placeholder images (dev only)")
    p.add_argument("--voice", help="Override Edge TTS voice (e.g. ar-EG-ShakirNeural)")
    p.add_argument("--burn-captions", action="store_true",
                   help="Burn captions into video (default: SRT only)")
    p.add_argument("--config", default=str(DEFAULT_CONFIG))
    p.add_argument("--out-root", default=str(DEFAULT_OUT_ROOT))
    p.add_argument("--music-bundle", default=str(DEFAULT_MUSIC_BUNDLE))
    # Shorts mode (Kie.ai) ------------------------------------------------
    p.add_argument("--shorts", action="store_true",
                   help="Use Shorts/TikTok pipeline (Kie.ai Veo, vertical 9:16, ~30s)")
    p.add_argument("--reroll-clips", help="Comma-separated 1-based clip indices to regenerate (Shorts mode)")
    p.add_argument("--skip-video", action="store_true",
                   help="Use placeholder black mp4 clips (Shorts dev only)")
    p.add_argument("--max-spend", type=float, default=None,
                   help="Override config.kie.max_spend_usd for this run")
    p.add_argument("--no-burn-captions", action="store_true",
                   help="Skip burned-in Arabic captions (Shorts default = burn-in)")
    args = p.parse_args(argv)

    cfg = load_config(Path(args.config))
    out_root = Path(args.out_root)
    music_bundle = Path(args.music_bundle)
    project_theme_log = out_root / "theme_log.json"
    project_story_history = out_root / "story_history.jsonl"

    run_dir = _resolve_run_dir(args, out_root)
    paths = RunPaths(root=run_dir)
    log = RunLog(run_dir)

    try:
        gemini = _build_gemini()
        log.info(f"run dir: {run_dir}  mode={'shorts' if args.shorts else 'long-form'}")

        if args.shorts:
            with log.stage("seed"):
                seed = _stage_seed(args, gemini, log, paths, project_theme_log)
            with log.stage("script"):
                script = _stage_shorts_script(gemini, seed, cfg, paths)
            with log.stage("voice"):
                _stage_shorts_voice(args, cfg, script, paths)
            with log.stage("align"):
                timings = _stage_align(paths, script)
            with log.stage("character_sheet"):
                _stage_character_sheet(_build_kie(), cfg, paths, script)
            with log.stage("video"):
                _stage_video_chained(args, cfg, script, paths)
            with log.stage("music"):
                _stage_music(script, music_bundle, paths)
            with log.stage("captions"):
                burn_ass = _stage_shorts_captions(cfg, timings, paths)
                # @sunstoriz style burns yellow captions by default; allow opt-out.
                if args.no_burn_captions:
                    burn_ass = None
            with log.stage("assemble"):
                _stage_shorts_assemble(cfg, script, paths, burn_ass)
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


def main() -> int:
    return main_with_args(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
