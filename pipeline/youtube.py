"""YouTube publishing — OAuth + resumable upload via plain requests.

Uploads a finished song's final.mp4 to the user's own channel with metadata
built from the song + artist. No google-api-python-client dependency: the
three HTTP calls involved are simple enough to do directly, which also keeps
every function trivially mockable (repo invariant: tests never hit real APIs).

Pre-audit reality: Google forces uploads from unaudited API projects to
private — privacyStatus comes from env YOUTUBE_PRIVACY_STATUS (default
"private") and flips to "public" once the user's compliance audit passes.
Spec: docs/superpowers/specs/2026-07-16-youtube-auto-publish-design.md.
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlencode

import requests

OAUTH_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"
UPLOAD_URL = ("https://www.googleapis.com/upload/youtube/v3/videos"
              "?uploadType=resumable&part=snippet,status")
SCOPES = ("https://www.googleapis.com/auth/youtube.upload "
          "https://www.googleapis.com/auth/youtube.readonly")

_TIMEOUT = 60
_UPLOAD_TIMEOUT = 600  # final.mp4 can be ~50-100 MB from GCS Fuse


class YouTubeError(RuntimeError):
    """Upload/auth failure with the API's message surfaced."""


def auth_url(client_id: str, redirect_uri: str, state: str) -> str:
    """Google consent URL. offline+consent forces a refresh_token grant."""
    return OAUTH_AUTH_URL + "?" + urlencode({
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    })


def exchange_code(client_id: str, client_secret: str, code: str,
                  redirect_uri: str) -> dict:
    r = requests.post(OAUTH_TOKEN_URL, data={
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    }, timeout=_TIMEOUT)
    if r.status_code >= 400:
        raise YouTubeError(f"OAuth exchange failed: {r.status_code} {r.text[:300]}")
    return r.json()


def refresh_access_token(client_id: str, client_secret: str,
                         refresh_token: str) -> str:
    r = requests.post(OAUTH_TOKEN_URL, data={
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }, timeout=_TIMEOUT)
    if r.status_code >= 400:
        raise YouTubeError(f"token refresh failed: {r.status_code} {r.text[:300]}")
    token = r.json().get("access_token")
    if not token:
        raise YouTubeError(f"token refresh returned no access_token: {r.text[:200]}")
    return str(token)


def channel_title(access_token: str) -> str:
    r = requests.get(CHANNELS_URL,
                     params={"part": "snippet", "mine": "true"},
                     headers={"Authorization": f"Bearer {access_token}"},
                     timeout=_TIMEOUT)
    if r.status_code >= 400:
        raise YouTubeError(f"channel lookup failed: {r.status_code} {r.text[:300]}")
    items = r.json().get("items") or []
    if not items:
        return "YouTube channel"
    return str(items[0].get("snippet", {}).get("title") or "YouTube channel")


def upload_video(access_token: str, video_path: Path, *, title: str,
                 description: str, tags: list[str], privacy: str) -> str:
    """Two-step resumable upload; returns the videoId."""
    body = {
        "snippet": {
            "title": title[:100],  # YouTube title cap
            "description": description[:4900],
            "tags": tags,
            "categoryId": "10",  # Music
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }
    init = requests.post(
        UPLOAD_URL,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Type": "video/mp4",
        },
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        timeout=_TIMEOUT,
    )
    if init.status_code >= 400:
        raise YouTubeError(f"upload init failed: {init.status_code} {init.text[:300]}")
    location = init.headers.get("Location")
    if not location:
        raise YouTubeError("upload init returned no resumable Location")

    with video_path.open("rb") as f:
        put = requests.put(
            location,
            headers={"Content-Type": "video/mp4"},
            data=f,
            timeout=_UPLOAD_TIMEOUT,
        )
    if put.status_code >= 400:
        raise YouTubeError(f"upload failed: {put.status_code} {put.text[:300]}")
    video_id = put.json().get("id")
    if not video_id:
        raise YouTubeError(f"upload response missing video id: {put.text[:200]}")
    return str(video_id)


def build_metadata(song_json: dict, artist: dict | None,
                   base_url: str) -> dict:
    """Title/description/tags from the song + artist. Never includes the raw
    style prompt verbatim in the description (it reads like a prompt, not
    marketing copy)."""
    from pipeline.release import strip_section_tags

    song_title = str(song_json.get("title") or "AI Song")
    artist_name = (artist or {}).get("name") or ""
    title = f"{song_title} — {artist_name}" if artist_name else song_title

    lyrics = strip_section_tags(str(song_json.get("lyrics") or ""))
    teaser = " · ".join(
        [ln.strip() for ln in lyrics.splitlines() if ln.strip()][:2])[:200]

    lines = [teaser] if teaser else []
    handle = (artist or {}).get("handle")
    if handle:
        lines.append(f"More from {artist_name}: {base_url.rstrip('/')}/a/{handle}")
    lang = str(song_json.get("language") or "ar")
    lines.append("#AIMusic #Music" + (" #اغاني" if lang == "ar" else ""))
    description = "\n\n".join(lines)

    # Tags from the style prompt's comma segments; YouTube caps total ~500ch.
    tags: list[str] = []
    total = 0
    for seg in str(song_json.get("style_prompt") or "").split(","):
        seg = seg.strip()
        if not seg or len(seg) > 30:
            continue
        if total + len(seg) > 400:
            break
        tags.append(seg)
        total += len(seg)

    return {"title": title, "description": description, "tags": tags}


# --- per-user token storage (same pattern as artists/personas) --------------

def token_path(user_root: Path) -> Path:
    return user_root / "youtube_token.json"


def load_token(user_root: Path) -> dict | None:
    p = token_path(user_root)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) and data.get("refresh_token") else None
    except (OSError, json.JSONDecodeError):
        return None


def save_token(user_root: Path, token: dict) -> None:
    user_root.mkdir(parents=True, exist_ok=True)
    p = token_path(user_root)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(token, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    tmp.replace(p)


def delete_token(user_root: Path) -> bool:
    p = token_path(user_root)
    if p.exists():
        try:
            p.unlink()
            return True
        except OSError:
            return False
    return False
