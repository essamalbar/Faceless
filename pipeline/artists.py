"""Artist storage — the identity wrapper around a Suno Persona voice.

An Artist = name + handle (public URL slug) + optional pinned voice
(persona_id) + visual identity + default song settings. Stored as a single
artists.json under each user's run-root, same pattern as personas.json.
See docs/superpowers/specs/2026-07-15-artist-core-design.md.
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

ARTIST_HANDLE_RE = re.compile(r"^[a-z0-9-]{2,32}$")


def slugify_handle(name: str, artist_id: str) -> str:
    """Slug a display name into a valid handle. Arabic/symbol-only names
    produce an empty slug — fall back to artist-<id> so the public URL
    always exists."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    slug = slug[:32].strip("-")
    if len(slug) < 2:
        slug = f"artist-{artist_id}"
    return slug


def unique_handle(handle: str, taken: set[str]) -> str:
    """Return handle, or handle-2 / handle-3… if taken. Suffixes respect the
    32-char cap."""
    if handle not in taken:
        return handle
    n = 2
    while True:
        suffix = f"-{n}"
        candidate = handle[: 32 - len(suffix)].rstrip("-") + suffix
        if candidate not in taken:
            return candidate
        n += 1


def new_artist(
    *,
    name: str,
    handle: str,
    bio: str = "",
    persona_id: str | None = None,
    avatar_run_id: str | None = None,
    avatar_upload: str | None = None,
    default_style: str = "",
    default_language: str = "ar",
    default_vocal_gender: str = "m",
) -> dict:
    return {
        "id": f"art_{uuid.uuid4().hex[:8]}",
        "name": name,
        "handle": handle,
        "bio": bio,
        "persona_id": persona_id,
        "avatar_run_id": avatar_run_id,
        "avatar_upload": avatar_upload,
        "default_style": default_style,
        "default_language": default_language,
        "default_vocal_gender": default_vocal_gender,
        # Channel Autopilot: publish finished songs to YouTube automatically.
        "auto_publish_youtube": False,
        # Channel Autopilot: a free draft each morning from the day's trends.
        "morning_drafts": False,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def artists_path(user_root: Path) -> Path:
    return user_root / "artists.json"


def load_artists(user_root: Path) -> list[dict]:
    p = artists_path(user_root)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def save_artists(user_root: Path, artists: list[dict]) -> None:
    """Atomic write (temp+rename) so a concurrent reader never sees torn
    JSON — same discipline as the run-state writes."""
    user_root.mkdir(parents=True, exist_ok=True)
    p = artists_path(user_root)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(artists, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    tmp.replace(p)


def find_by_id(artists: list[dict], artist_id: str) -> dict | None:
    return next((a for a in artists if a.get("id") == artist_id), None)


def find_by_handle(artists: list[dict], handle: str) -> dict | None:
    return next((a for a in artists if a.get("handle") == handle), None)
