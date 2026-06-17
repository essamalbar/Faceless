"""ffmpeg assembly: cover.png + song.mp3 → final.mp4.

Quality gates (do not silently optimize away — see spec section
"Assembly (ffmpeg)"):
  - `-c:a copy` preserves Suno's mastering bit-for-bit. Do NOT re-encode.
  - No loudnorm/dynaudnorm filters — Suno is already at -14 LUFS.
  - `-movflags +faststart` puts moov atom at the front so the Flutter
    `<video>` player streams immediately.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

_FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"

FPS = 25
OUTPUT_SIZE = 1080
UPSCALE_SIZE = 2160  # pre-zoompan upscale to avoid resampling blur
ZOOM_END = 1.13  # target zoom at end of song


def ffprobe_duration(path: Path) -> float:
    """Authoritative duration in seconds (Suno's job metadata is sometimes off)."""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json",
         "-show_format", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(json.loads(out.stdout)["format"]["duration"])


_MIN_LINE_DUR_S = 0.6  # tiny cues feel like flashes — extend them


def _format_ass_time(t: float) -> str:
    """ASS expects H:MM:SS.cs (centiseconds, not milliseconds)."""
    if t < 0:
        t = 0
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _ass_escape(text: str) -> str:
    """Escape characters that ASS treats specially in a Dialogue line."""
    # ASS uses {} for inline tags and \N for line breaks. Strip them
    # rather than encode — none should occur in clean lyric input, but
    # be defensive. Keep newlines collapsed to spaces.
    return (
        text.replace("\n", " ")
            .replace("{", "(")
            .replace("}", ")")
    )


def _write_ass_subtitles(lyrics_data: dict, out_path: Path) -> bool:
    """Generate an Advanced SubStation Alpha file from a lyrics.json
    payload. Returns True if at least one Dialogue line was written
    (caller skips the subtitle filter otherwise).

    Style notes:
      * Scheherazade ships in the Docker image (apt
        fonts-sil-scheherazade). It's SIL's smart-font Naskh face,
        explicitly designed for large display use which is what
        burn-in captions are. Falls back to libass's default if not
        installed locally, which is fine for unit-test scenarios.
      * Encoding 178 is the ASS code for Arabic — required for some
        legacy libass builds to pick the right shaper.
      * Bottom alignment (8), 110-px margin from the bottom, keeps
        the captions clear of the player's progress bar in the
        share page and Instagram's UI chrome on reposts.
      * White fill, black outline (3px), shadow (2px) is the only
        combination that stays readable over both the dark and the
        bright cover-art regions Flux produces.
    """
    sung = [
        ln for ln in lyrics_data.get("lines", [])
        if ln.get("kind") == "line"
        and ln.get("start") is not None
        and ln.get("end") is not None
    ]
    if not sung:
        return False

    # Extend tiny cues and clip-end to the audio duration so the last
    # line lingers naturally rather than blinking off two beats early.
    audio_dur = float(lyrics_data.get("audio_duration") or 0.0)
    events: list[tuple[float, float, str]] = []
    for i, ln in enumerate(sung):
        start = float(ln["start"])
        end = float(ln["end"])
        if end - start < _MIN_LINE_DUR_S:
            end = start + _MIN_LINE_DUR_S
        # Don't overlap the next line.
        if i + 1 < len(sung):
            next_start = float(sung[i + 1]["start"])
            if end > next_start - 0.05:
                end = max(start + 0.3, next_start - 0.05)
        elif audio_dur > 0 and end > audio_dur:
            end = audio_dur
        events.append((start, end, _ass_escape(ln.get("text", ""))))

    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "PlayResX: 1080\n"
        "PlayResY: 1080\n"
        "WrapStyle: 0\n"
        "ScaledBorderAndShadow: yes\n"
        "YCbCr Matrix: TV.709\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: Default,Scheherazade,56,&H00FFFFFF,&H000000FF,"
        "&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,2,2,60,60,110,178\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, "
        "MarginV, Effect, Text\n"
    )
    body = "\n".join(
        f"Dialogue: 0,{_format_ass_time(s)},{_format_ass_time(e)},"
        f"Default,,0,0,0,,{text}"
        for (s, e, text) in events
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(header + body + "\n", encoding="utf-8")
    return True


def _ffmpeg_filter_path(p: Path) -> str:
    """Compatibility alias — drawtext's `fontfile` arg goes through the
    same filtergraph escaper as `ass`. Older callers still go through
    the legacy name below; this one keeps the call sites readable."""
    return _escape_ffmpeg_filter_path(p)


def _ffmpeg_drawtext_escape(text: str) -> str:
    """drawtext's `text=` value sits inside an already-escaped filter
    string. Three characters MUST be escaped: backslash, single-quote,
    and colon. Newlines are forbidden; replace with spaces."""
    return (
        text.replace("\\", "\\\\")
            .replace("'", r"\'")
            .replace(":", r"\:")
            .replace("\n", " ")
    )


def _escape_ffmpeg_filter_path(p: Path) -> str:
    """ffmpeg's filtergraph parser treats `:` as a delimiter and `'` /
    `\\` as escape chars. The ass= filter takes its path argument in
    that filtergraph string, so the path needs filtergraph-level
    escaping (NOT shell escaping). On the typical Cloud Run path
    `/mnt/runs/.../lyrics.ass` this matters mainly because of the
    leading `/` is fine but any colon (Windows drive letter, never
    seen on Linux) would otherwise break parsing."""
    s = str(p)
    s = s.replace("\\", "\\\\")
    s = s.replace(":", "\\:")
    s = s.replace("'", "\\'")
    return s


def build_metadata_args(title: str | None, share_token: str | None) -> list[str]:
    """MP4 container provenance tags — shared by the static and cinematic
    assemblers. Lives in the moov atom for ffprobe / content-ID tools."""
    args: list[str] = []
    if title:
        args += ["-metadata", f"title={title}"]
    args += [
        "-metadata", "artist=Faceless Lab",
        "-metadata", "encoded_by=Faceless Lab",
        "-metadata", (
            "copyright=© Faceless Lab — AI-generated. "
            "Not for unauthorized commercial reuse."
        ),
    ]
    if share_token:
        args += ["-metadata",
                 f"comment=Generated with Faceless Lab — "
                 f"https://faceless-lab.com/p/{share_token}"]
    else:
        args += ["-metadata", "comment=Generated with Faceless Lab — faceless-lab.com"]
    return args


def resolve_watermark() -> tuple[bool, Path]:
    """(has_watermark, path). Shared by both assemblers."""
    watermark_png = _FONT_DIR.parent / "watermark.png"
    return watermark_png.exists(), watermark_png


def assemble_song_video(
    *,
    cover_path: Path,
    song_mp3: Path,
    out_mp4: Path,
    lyrics_json: Path | None = None,
    title: str | None = None,
    share_token: str | None = None,
) -> None:
    """Build the music-video MP4. Raises subprocess.CalledProcessError on failure.

    When lyrics_json is provided, generates a sibling lyrics.ass file
    and burns line-by-line karaoke captions into the video via ffmpeg's
    ass filter. Captions are the same per-line cues that drive the
    share-page karaoke, so the two surfaces stay consistent.

    title and share_token power container-level provenance:
      * a top-right "▶ faceless-lab.com" text watermark is always burned
        into the video so re-uploads outside our share page carry
        attribution (cannot be cropped without losing visible image),
      * MP4 metadata tags (title, artist, copyright, comment with the
        share token, encoded_by) are written into the container so
        downstream tools (YouTube content-ID, ACRCloud, manual probes)
        can identify the work. Both are silently skipped when None."""
    duration_s = ffprobe_duration(song_mp3)
    total_frames = max(1, int(duration_s * FPS))
    zoom_step = (ZOOM_END - 1.0) / total_frames

    # If we have alignment data, render an ASS file alongside the lyrics.json.
    ass_filter = ""
    if lyrics_json is not None and lyrics_json.exists():
        try:
            data = json.loads(lyrics_json.read_text(encoding="utf-8"))
            ass_path = lyrics_json.with_name("lyrics.ass")
            if _write_ass_subtitles(data, ass_path):
                ass_filter = f",ass='{_escape_ffmpeg_filter_path(ass_path)}'"
        except (OSError, json.JSONDecodeError, ValueError):
            # Bad alignment payload — ship the video without captions
            # rather than fail the whole assembly.
            ass_filter = ""

    # Brand-mark watermark: composited PNG (logo + wordmark pill, see
    # pipeline/watermark.py) pinned top-right. The PNG ships with the
    # repo at assets/watermark.png so the Docker image always has it;
    # if the asset is missing locally (dev / tests) we silently skip
    # the watermark rather than crash the assembly.
    has_watermark, watermark_png = resolve_watermark()

    if has_watermark:
        # Two-input filter graph:
        #   [0:v] → scale/zoompan → [vbg]
        #   [vbg] + [ass-rendered subtitles if any] → [vsub]
        #   [vsub] + [2:v] (watermark) → overlay top-right → [v]
        # Watermark scaled to 240×55 on the 1080² canvas (~22% of the
        # frame width). 28px margin from both edges.
        filter_complex = (
            f"[0:v]scale={UPSCALE_SIZE}:{UPSCALE_SIZE},"
            f"zoompan=z='1+{zoom_step:.10f}*on':"
            f"d={total_frames}:s={OUTPUT_SIZE}x{OUTPUT_SIZE}:fps={FPS}"
            f"{ass_filter}[vsub];"
            f"[2:v]scale=240:55[wm];"
            f"[vsub][wm]overlay=W-w-28:28[v]"
        )
    else:
        filter_complex = (
            f"[0:v]scale={UPSCALE_SIZE}:{UPSCALE_SIZE},"
            f"zoompan=z='1+{zoom_step:.10f}*on':"
            f"d={total_frames}:s={OUTPUT_SIZE}x{OUTPUT_SIZE}:fps={FPS}"
            f"{ass_filter}[v]"
        )

    # Container metadata. Lives in the MP4's moov atom so tools like
    # ffprobe, ACRCloud and YouTube's manual review can identify the
    # source. share_token is the load-bearing field — it's a one-way
    # cryptographic fingerprint linking re-uploaded copies back to the
    # original share page on faceless-lab.com.
    metadata_args = build_metadata_args(title, share_token)

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(cover_path),
        "-i", str(song_mp3),
    ]
    if has_watermark:
        # Third input — watermark PNG. -loop 1 so the still image
        # decodes as a constant stream that the overlay filter can
        # composite onto every frame.
        cmd += ["-loop", "1", "-i", str(watermark_png)]
    cmd += [
        "-filter_complex", filter_complex,
        "-map", "[v]", "-map", "1:a",
        *metadata_args,
        # preset=veryfast: a still cover with slow zoompan has zero
        # motion-compensation benefit from slower presets. On Cloud Run's
        # 2 vCPU, `slow` was taking 15-40 min per song; `veryfast` does
        # the same in 1-2 min with imperceptible visual difference.
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        # Audio MUST be AAC inside an MP4 container — browsers (Chrome,
        # Safari, Firefox) reject MP3 audio in MP4 with
        # MEDIA_ERR_SRC_NOT_SUPPORTED. Suno's output is MP3, so we
        # transcode here. The earlier `-c:a copy` design was wrong;
        # it produced files that wouldn't play in the Flutter video
        # player. At 192k AAC the loss from MP3→AAC is imperceptible.
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        "-movflags", "+faststart",
        "-threads", "0",  # use all available vCPUs
        # Force MP4 muxer — ffmpeg infers format from the output
        # file extension, but we're writing to "<name>.mp4.tmp" so
        # the autodetect fails. -f mp4 makes the format explicit.
        "-f", "mp4",
        # Write to a temp file then atomic-rename. Without this, a
        # killed worker or a crashed ffmpeg leaves a half-written
        # final.mp4 on disk that the API happily serves as broken
        # video. Two concurrent assemblers also corrupt each other.
        str(out_mp4) + ".tmp",
    ]
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = Path(str(out_mp4) + ".tmp")
    # Pre-delete any stale .tmp from a previous failed attempt. Without
    # this, GCS Fuse's streaming-writes mode can latch onto the partial
    # file's existing data, then crash with
    #   BufferedWriteHandler.OutOfOrderError ... expectedOffset: <N>,
    #   actualOffset: 40
    # when ffmpeg seeks back to position 40 to rewrite the moov atom
    # for +faststart. Atomic unlink before write keeps each run clean.
    if tmp_path.exists():
        try:
            tmp_path.unlink()
        except OSError:
            # GCS Fuse occasionally refuses unlink on .tmp paths it
            # considers in-flight. Truncate as a fallback so ffmpeg's
            # `-y` starts from offset 0 with no leftover bytes.
            try:
                tmp_path.write_bytes(b"")
            except OSError:
                pass
    subprocess.run(cmd, check=True, capture_output=True)
    # Atomic rename — POSIX guarantees readers see either the old
    # file or the new one, never a torn read. GCS Fuse supports
    # atomic rename on objects without the .tmp prefix conflict.
    tmp_path.replace(out_mp4)
