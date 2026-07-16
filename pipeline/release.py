"""Release-package builder — Route B distribution (export MVP).

Assembles everything a distributor (DistroKid et al.) needs to put a song on
Spotify/Apple/etc into one zip: audio, store-compliant 3000x3000 cover,
metadata (json for the future LabelGrid automation + txt for humans), lyrics,
and an upload checklist. Pure functions; the API endpoint streams the zip.
Spec: docs/superpowers/specs/2026-07-16-distribution-export-design.md.
"""
from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path

from pipeline.artists import slugify_handle

COVER_SIZE = 3000
_SECTION_TAG_RE = re.compile(r"^\[[^\]]+\]\s*$", re.MULTILINE)


class ReleaseNotReady(RuntimeError):
    """The run is missing artifacts a release needs. `missing` lists them."""

    def __init__(self, missing: list[str]):
        self.missing = missing
        super().__init__(f"release not ready — missing: {', '.join(missing)}")


def song_slug(title: str) -> str:
    """URL/file-safe slug for the zip name. Arabic titles fall back to
    'song' (the zip name is cosmetic; metadata carries the real title)."""
    slug = slugify_handle(title or "", "x")
    return "song" if slug.startswith("artist-") else slug


def strip_section_tags(lyrics: str) -> str:
    """Remove Suno section tags ([Verse 1], [Chorus], …) for the store's
    plain-lyrics field; collapse the blank runs left behind."""
    out = _SECTION_TAG_RE.sub("", lyrics)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip() + "\n"


def derive_genre(style_prompt: str) -> str:
    """First comma-segment of the style prompt reads like a genre
    ('Arabic pop ballad, 88 BPM, …'). Empty → 'World'."""
    head = (style_prompt or "").split(",")[0].strip()
    return head if head else "World"


def upscale_cover(src: Path, dest: Path, size: int = COVER_SIZE) -> None:
    """Lanczos upscale to size×size JPEG q92 — stores want ≥1400px square;
    our covers are 1080×1080."""
    from PIL import Image
    with Image.open(src) as im:
        im = im.convert("RGB").resize((size, size), Image.LANCZOS)
        im.save(dest, "JPEG", quality=92)


_README = """FACELESS LAB — RELEASE PACKAGE
================================

How to put this song on Spotify / Apple Music / etc (via DistroKid or any
distributor):

1. You already downloaded this package — unzip it (done!).
2. Create an account at a distributor (e.g. distrokid.com).
3. Choose "Upload" and select audio.mp3 from this folder.
4. Use cover.jpg as the release artwork (3000x3000, store-compliant).
5. Copy the title / artist / genre / language from metadata.txt.
6. Paste lyrics.txt into the lyrics field when asked.
7. Submit. Stores typically go live in 1-7 days.
8. Back in Faceless Lab, tap "Mark as released" on the song.

metadata.json is machine-readable (used by upcoming automation).
"""


def build_release_package(
    run_dir: Path,
    artist: dict | None,
    out_zip: Path,
) -> Path:
    """Assemble the release zip. Raises ReleaseNotReady listing anything
    essential that's absent. A failed cover upscale degrades (audio is the
    irreplaceable part); the README notes the omission."""
    song_json_path = run_dir / "song.json"
    audio = run_dir / "song.mp3"
    cover = run_dir / "cover.png"

    missing = []
    if not song_json_path.exists():
        missing.append("song.json")
    if not audio.exists():
        missing.append("song.mp3")
    if missing:
        raise ReleaseNotReady(missing)

    script = json.loads(song_json_path.read_text(encoding="utf-8"))
    title = str(script.get("title") or "Untitled")
    lyrics = str(script.get("lyrics") or "")
    style_prompt = str(script.get("style_prompt") or "")
    language = str(script.get("language") or "ar")

    artist_name = (artist or {}).get("name") or "Faceless Artist"
    artist_handle = (artist or {}).get("handle") or ""

    metadata = {
        "title": title,
        "artist_name": artist_name,
        "artist_handle": artist_handle,
        "language": language,
        "lyrics_language": language,
        "explicit": False,
        "genre": derive_genre(style_prompt),
        "release_type": "single",
        "style_prompt": style_prompt,
        "generated_with": "Faceless Lab",
    }
    metadata_txt = (
        f"Title:    {title}\n"
        f"Artist:   {artist_name}\n"
        f"Genre:    {metadata['genre']}\n"
        f"Language: {language}\n"
        f"Explicit: no\n"
        f"Type:     single\n"
    )

    cover_jpg = run_dir / "release_cover.jpg"
    cover_ok = False
    if cover.exists():
        try:
            upscale_cover(cover, cover_jpg)
            cover_ok = True
        except Exception:
            cover_ok = False

    readme = _README
    if not cover_ok:
        readme += ("\nNOTE: cover.jpg could not be generated for this song — "
                   "export the cover from the app or make your own 3000x3000 "
                   "square image.\n")

    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(audio, "audio.mp3")
        if cover_ok:
            z.write(cover_jpg, "cover.jpg")
        z.writestr("metadata.json",
                   json.dumps(metadata, ensure_ascii=False, indent=2))
        z.writestr("metadata.txt", metadata_txt)
        z.writestr("lyrics.txt", strip_section_tags(lyrics))
        z.writestr("README.txt", readme)
    return out_zip
