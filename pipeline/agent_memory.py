"""Per-artist agent memory — the Autonomous Artist Agent's learning store.

Records the human's approve/reject/edit decisions on agent-proposed runs and
periodically distills them into a short natural-language preference summary
via one cheap LLM call. Stored as a single JSON file per artist under the
user's run-root, atomically written (temp+rename), same discipline as
`pipeline/artists.py`. No DB migration — the DB stays financial-only.

See docs/superpowers/specs/2026-09-25-autonomous-artist-agent-design.md §5.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Cap the stored decision history so the memory file doesn't grow unbounded
# across hundreds of runs.
MAX_DECISIONS = 100

_VALID_DECISIONS = {"approved", "rejected", "edited"}

_DISTILL_SYSTEM = (
    "You distill a music artist's approve/reject/edit history into one tight "
    "preference summary (2-3 sentences) an autonomous songwriting agent will "
    "read before proposing new songs. Be concrete and specific about what to "
    "do more of and what to avoid. Output only the summary, no preamble."
)


def memory_path(user_root: Path, artist_id: str) -> Path:
    return user_root / "agent" / f"{artist_id}.json"


def load_memory(user_root: Path, artist_id: str) -> dict[str, Any]:
    """Return the artist's agent memory, or empty defaults if absent/corrupt."""
    p = memory_path(user_root, artist_id)
    if not p.exists():
        return {
            "artist_id": artist_id,
            "preferences_summary": "",
            "decisions": [],
            "updated_at": None,
        }
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    return {
        "artist_id": data.get("artist_id", artist_id),
        "preferences_summary": data.get("preferences_summary", ""),
        "decisions": data.get("decisions") if isinstance(data.get("decisions"), list) else [],
        "updated_at": data.get("updated_at"),
    }


def _save_memory(user_root: Path, artist_id: str, memory: dict[str, Any]) -> None:
    """Atomic write (temp+rename) so a concurrent reader never sees torn
    JSON — mirrors pipeline/artists.py:save_artists."""
    p = memory_path(user_root, artist_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    memory["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(memory, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)


def record_decision(
    user_root: Path,
    artist_id: str,
    *,
    run_id: str,
    decision: str,
    reason: str = "",
    self_score: float | None = None,
) -> None:
    """Append a decision to the artist's memory and atomically persist it.

    `decision` must be one of "approved", "rejected", "edited".
    """
    if decision not in _VALID_DECISIONS:
        raise ValueError(f"decision must be one of {sorted(_VALID_DECISIONS)}, got {decision!r}")

    memory = load_memory(user_root, artist_id)
    memory["decisions"].append(
        {
            "run_id": run_id,
            "decision": decision,
            "reason": reason,
            "self_score": self_score,
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
    )
    # Bound file size: keep only the most recent MAX_DECISIONS entries.
    memory["decisions"] = memory["decisions"][-MAX_DECISIONS:]
    _save_memory(user_root, artist_id, memory)


def distill_preferences(user_root: Path, artist_id: str, llm: Any) -> str:
    """Rewrite `preferences_summary` from recent decisions via one LLM call.

    Returns the new summary (also stored). If there are no decisions yet,
    returns "" without calling the LLM.
    """
    memory = load_memory(user_root, artist_id)
    decisions = memory["decisions"]
    if not decisions:
        return ""

    lines = []
    for d in decisions:
        line = f"- {d.get('decision')}"
        if d.get("reason"):
            line += f": {d['reason']}"
        if d.get("self_score") is not None:
            line += f" (self_score={d['self_score']})"
        lines.append(line)
    prompt = (
        "Here is an artist's recent approve/reject/edit history, oldest first:\n"
        + "\n".join(lines)
        + "\n\nWrite the preference summary."
    )

    summary = llm.complete(prompt, system=_DISTILL_SYSTEM)
    memory["preferences_summary"] = summary
    _save_memory(user_root, artist_id, memory)
    return summary
