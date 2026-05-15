"""In-place mp4 faststart re-mux.

Veo clips arrive from Kie with the `moov` atom at the END of the file,
which forces HTML5 video players to download the full mp4 before
playback can begin. Re-muxing with `ffmpeg -movflags +faststart` moves
`moov` to the front; no re-encoding, ~100ms per clip.

The function fails silently — if ffmpeg is missing or the input is
unparseable, we leave the file as-is. A slow-loading clip is better
than a missing one."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def rewrite_with_faststart(path: Path) -> None:
    """Atomically re-mux `path` so `moov` atom moves to the front.

    On any failure, leaves the original file untouched. Side effects:
    writes a temporary file `<path>.faststart.mp4` during the operation
    and removes it on success or failure.
    """
    if not path.exists() or not path.is_file():
        return
    tmp = path.with_name(path.stem + ".faststart.mp4")
    try:
        result = subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error",
                "-i", str(path),
                "-c", "copy", "-movflags", "+faststart",
                str(tmp),
            ],
            check=False,
            capture_output=True,
        )
        if result.returncode != 0 or not tmp.exists() or tmp.stat().st_size == 0:
            tmp.unlink(missing_ok=True)
            return
        # When ffmpeg can only partially read a corrupt mp4 it produces
        # a tiny-but-non-zero output (a few hundred bytes of moov
        # header with no media). Refuse to overwrite the original
        # unless the re-muxed file is plausibly the full asset. Pre-
        # production cost: one extra stat call. Failure cost: the
        # original was overwritten with garbage and the user could
        # not recover even by re-running ffmpeg with smarter flags.
        in_size = path.stat().st_size
        out_size = tmp.stat().st_size
        if in_size > 0 and out_size < max(50_000, in_size * 0.5):
            tmp.unlink(missing_ok=True)
            return
        # Atomic replace on POSIX
        shutil.move(str(tmp), str(path))
    except (FileNotFoundError, OSError):
        tmp.unlink(missing_ok=True)
        return
