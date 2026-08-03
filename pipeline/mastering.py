"""Master the winning take. Matchering (reference-based) preferred; ffmpeg
tonal chain as the no-reference fallback. Never raises — returns False so the
worker ships the unmastered winner. See spec 2026-08-03."""
from __future__ import annotations

import subprocess
from pathlib import Path

_REFERENCE_DIR = Path(__file__).resolve().parent.parent / "assets" / "reference_masters"


def _reference_for(genre_key: str) -> Path | None:
    ref = _REFERENCE_DIR / f"{genre_key}.wav"
    return ref if ref.exists() else None


def _master_matchering(in_path: Path, out_path: Path, reference: Path) -> bool:
    import matchering as mg
    # matchering's pcm16 result must be a PCM-capable container (WAV) — it
    # raises "MP3 format does not have PCM_16 subtype" on an .mp3 target. So
    # master to a temp WAV, then deliver out_path's actual container.
    tmp_wav = out_path.with_suffix(".mastered.wav")
    mg.process(
        target=str(in_path),
        reference=str(reference),
        results=[mg.pcm16(str(tmp_wav))],
    )
    if not tmp_wav.exists():
        return False
    if out_path.suffix.lower() == ".wav":
        tmp_wav.replace(out_path)
    else:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(tmp_wav),
             "-c:a", "libmp3lame", "-q:a", "2", str(out_path)],
            check=True, capture_output=True,
        )
        try:
            tmp_wav.unlink()
        except OSError:
            pass
    return out_path.exists()


def _master_ffmpeg(in_path: Path, out_path: Path) -> bool:
    # HPF rumble cut + de-ess-ish high shelf tame + gentle comp + true-peak
    # limiter at -1 dBTP. NO loudnorm — Suno already ships ~-14 LUFS.
    af = ("highpass=f=30,acompressor=threshold=-18dB:ratio=2:attack=20:release=250,"
          "alimiter=limit=0.891")  # 0.891 ≈ -1 dBTP
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(in_path), "-af", af,
         "-c:a", "libmp3lame", "-q:a", "2", str(out_path)],
        check=True, capture_output=True,
    )
    return out_path.exists()


def master_track(in_path, out_path, *, genre_key: str, cfg) -> bool:
    """Return True if a master was written to out_path, else False (ship
    unmastered). Never raises."""
    in_path, out_path = Path(in_path), Path(out_path)
    engine = "ffmpeg"
    if cfg and getattr(cfg, "song", None):
        engine = getattr(cfg.song, "master_engine", "ffmpeg")
    try:
        if engine == "matchering":
            ref = _reference_for(genre_key)
            if ref:
                try:
                    if _master_matchering(in_path, out_path, ref):
                        return True
                    print("[mastering] matchering produced no output; ffmpeg fallback")
                except Exception as e:
                    # Matchering errored (bad reference, transcode fail, ...) —
                    # fall back to ffmpeg per spec ("ffmpeg when Matchering errors
                    # OR no reference"), not straight to unmastered.
                    print(f"[mastering] matchering failed ({e}); ffmpeg fallback")
                return _master_ffmpeg(in_path, out_path)
            print(f"[mastering] no reference master for {genre_key!r}; ffmpeg fallback")
            return _master_ffmpeg(in_path, out_path)
        if engine == "api":
            print("[mastering] 'api' engine reserved/not built; ffmpeg fallback")
            return _master_ffmpeg(in_path, out_path)
        return _master_ffmpeg(in_path, out_path)
    except Exception as e:
        print(f"[mastering] failed ({e}); shipping unmastered")
        return False
