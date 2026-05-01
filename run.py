"""Faceless pipeline CLI orchestrator.

Usage:
  python run.py                                  # auto theme, full pipeline
  python run.py --theme folkloric --seed "بئر"   # manual seed
  python run.py --resume out/2026-05-01-1430     # resume crashed run
  python run.py --reroll-images 23,27 --run-dir out/2026-05-01-1430
  python run.py --skip-images
  python run.py --voice ar-EG-ShakirNeural
  python run.py --burn-captions
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from pipeline.assemble import assemble_video
from pipeline.captions import generate_captions
from pipeline.config import Config, load_config
from pipeline.images import generate_images
from pipeline.llm import GeminiClient
from pipeline.music import select_music_track
from pipeline.runlog import RunLog
from pipeline.script import generate_script_with_uniqueness
from pipeline.seed import auto_seed, manual_seed, record_theme_use
from pipeline.shots import generate_shots
from pipeline.types import RunPaths, Script, Shot, ThemeSeed, WordTiming
from pipeline.voice import generate_narration


REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = REPO_ROOT / "config.yaml"
DEFAULT_OUT_ROOT = REPO_ROOT / "out"
DEFAULT_MUSIC_BUNDLE = REPO_ROOT / "assets" / "music"
DEFAULT_FONTS_DIR = REPO_ROOT / "assets" / "fonts"
PROJECT_THEME_LOG = DEFAULT_OUT_ROOT / "theme_log.json"
PROJECT_STORY_HISTORY = DEFAULT_OUT_ROOT / "story_history.jsonl"


def _build_gemini() -> GeminiClient:
    """Indirection so tests can monkeypatch."""
    return GeminiClient()


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
        log.info(f"run dir: {run_dir}")

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
