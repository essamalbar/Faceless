"""Stage 6: music selection from a hand-curated CC0/CC-BY bundle."""
from __future__ import annotations

import json
import random
import shutil
from pathlib import Path


def select_music_track(
    bundle_dir: Path,
    mood: str,
    out_path: Path,
    rng_seed: int | None = None,
) -> None:
    """Pick a track matching `mood` and copy it to `out_path`. Resumable."""
    if out_path.exists():
        return
    if not bundle_dir.exists():
        raise FileNotFoundError(f"music bundle dir not found: {bundle_dir}")
    tracks_json = bundle_dir / "tracks.json"
    if not tracks_json.exists():
        raise FileNotFoundError(f"tracks.json missing in {bundle_dir}")
    tracks = json.loads(tracks_json.read_text())
    candidates = [t for t in tracks if t["mood"] == mood]
    if not candidates:
        raise RuntimeError(f"no tracks for mood={mood} in bundle (have {sorted({t['mood'] for t in tracks})})")
    rng = random.Random(rng_seed)
    chosen = rng.choice(candidates)
    src = bundle_dir / chosen["filename"]
    if not src.exists():
        raise FileNotFoundError(f"track file missing: {src}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, out_path)
