"""Per-run structured logger writing to stdout + out/<run>/run.log."""
from __future__ import annotations

import sys
import time
import traceback
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import IO


class RunLog:
    def __init__(self, run_dir: Path):
        self.run_dir = run_dir
        run_dir.mkdir(parents=True, exist_ok=True)
        self._fh: IO[str] = (run_dir / "run.log").open("a", encoding="utf-8")

    def _write(self, level: str, msg: str) -> None:
        ts = datetime.now().isoformat(timespec="seconds")
        line = f"{ts} {level} {msg}"
        print(line, file=sys.stdout, flush=True)
        self._fh.write(line + "\n")
        self._fh.flush()

    def info(self, msg: str) -> None:
        self._write("INFO", msg)

    def warn(self, msg: str) -> None:
        self._write("WARN", msg)

    def error(self, msg: str) -> None:
        self._write("ERROR", msg)

    @contextmanager
    def stage(self, name: str):
        self._write("INFO", f"stage start: {name}")
        t0 = time.monotonic()
        try:
            yield
        except Exception as exc:
            duration_ms = int((time.monotonic() - t0) * 1000)
            self._write("ERROR", f"stage failed: {name} duration_ms={duration_ms}")
            self._write("ERROR", f"{type(exc).__name__}: {exc}")
            for line in traceback.format_exc().splitlines():
                self._write("ERROR", line)
            raise
        duration_ms = int((time.monotonic() - t0) * 1000)
        self._write("INFO", f"stage end: {name} duration_ms={duration_ms}")

    def close(self) -> None:
        try:
            self._fh.close()
        except Exception:
            pass
