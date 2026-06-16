"""Pure cut-schedule builder for the cinematic (beat-synced) song video.

No I/O, no ffmpeg, no network -- given beat times + section markers, it
returns a deterministic list of Segments that song_cinematic turns into
an ffmpeg filtergraph. This is the brain of the feature, kept pure so it
can be exhaustively unit-tested. See
docs/superpowers/specs/2026-06-16-beat-synced-song-video-design.md.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Segment:
    image_idx: int   # index into the pool, 0 <= image_idx < pool_size
    start: float     # seconds
    end: float       # seconds
    zoom_dir: str    # "in" | "out"


def extract_sections(lyrics_data: dict) -> list[dict]:
    """Pull [{label, start}] from a lyrics.json payload (kind=="section").

    Sections whose start is None (unaligned) are dropped -- they carry no
    timing to cut on."""
    out: list[dict] = []
    for ln in lyrics_data.get("lines", []):
        if ln.get("kind") != "section":
            continue
        start = ln.get("start")
        if start is None:
            continue
        out.append({"label": str(ln.get("text", "")).strip(), "start": float(start)})
    return out


def _norm_label(label: str) -> str:
    """Normalize a section label for image assignment. Every [Chorus*]
    collapses to one key so the recurring hook reuses one image; other
    sections (Verse 1, Verse 2, Bridge) stay distinct."""
    low = label.strip().lower()
    if low.startswith("chorus"):
        return "chorus"
    return low


def _assign_section_images(sections: list[dict], pool_size: int) -> list[int]:
    """Image index per section occurrence (parallel to `sections`)."""
    label_to_idx: dict[str, int] = {}
    next_idx = 0
    out: list[int] = []
    for sec in sections:
        key = _norm_label(sec["label"])
        if key not in label_to_idx:
            label_to_idx[key] = next_idx % pool_size
            next_idx += 1
        out.append(label_to_idx[key])
    return out


def _image_for_time(t: float, starts: list[float], imgs: list[int]) -> int:
    """The image of the latest section whose start <= t."""
    chosen = imgs[0] if imgs else 0
    for start, img in zip(starts, imgs):
        if start <= t + 1e-6:
            chosen = img
        else:
            break
    return chosen


def _merge_short(segs: list[Segment], min_s: float, audio_duration: float) -> list[Segment]:
    """Fold sub-`min_s` segments into the previous one (or the next, for
    the first segment). Guarantees every segment >= min_s and the last
    ends at audio_duration."""
    if not segs:
        return segs
    merged: list[Segment] = []
    for seg in segs:
        if merged and (seg.end - seg.start) < min_s:
            prev = merged[-1]
            merged[-1] = Segment(prev.image_idx, prev.start, seg.end, prev.zoom_dir)
        else:
            merged.append(seg)
    # First segment too short -> extend its end into the second (rare).
    if len(merged) >= 2 and (merged[0].end - merged[0].start) < min_s:
        second = merged[1]
        merged[0] = Segment(merged[0].image_idx, merged[0].start, second.end, merged[0].zoom_dir)
        del merged[1]
    last = merged[-1]
    merged[-1] = Segment(last.image_idx, last.start, audio_duration, last.zoom_dir)
    return merged


def _coarsen(segs: list[Segment], max_segments: int) -> list[Segment]:
    """Drop cut density to <= max_segments by merging runs of segments.
    Keeps image assignment of the first segment in each merged run."""
    if len(segs) <= max_segments:
        return segs
    group = (len(segs) + max_segments - 1) // max_segments
    out: list[Segment] = []
    for i in range(0, len(segs), group):
        chunk = segs[i:i + group]
        head = chunk[0]
        out.append(Segment(head.image_idx, head.start, chunk[-1].end, head.zoom_dir))
    return out


def build_cut_schedule(
    *,
    beat_times: list[float],
    sections: list[dict],
    pool_size: int,
    audio_duration: float,
    bars_per_cut: int = 4,
    beats_per_bar: int = 4,
    min_segment_s: float = 0.6,
    max_segments: int = 60,
) -> list[Segment]:
    """Build the cinematic cut timeline. See module docstring."""
    if pool_size < 1:
        raise ValueError("pool_size must be >= 1")

    section_starts = [float(s["start"]) for s in sections] if sections else [0.0]
    section_imgs = _assign_section_images(sections, pool_size) if sections else [0]

    beats_per_cut = max(1, bars_per_cut * beats_per_bar)
    if beat_times:
        cuts = [float(beat_times[i]) for i in range(0, len(beat_times), beats_per_cut)]
        if not cuts or cuts[0] > 0.0:
            cuts = [0.0] + cuts
    else:
        cuts = sorted({0.0, *section_starts})

    boundaries = sorted({c for c in cuts if 0.0 <= c < audio_duration})
    if not boundaries:
        boundaries = [0.0]
    boundaries.append(audio_duration)

    segs: list[Segment] = []
    for i in range(len(boundaries) - 1):
        start, end = boundaries[i], boundaries[i + 1]
        if end <= start:
            continue
        img = _image_for_time(start, section_starts, section_imgs)
        zoom = "in" if i % 2 == 0 else "out"
        segs.append(Segment(image_idx=img, start=start, end=end, zoom_dir=zoom))

    segs = _merge_short(segs, min_segment_s, audio_duration)
    segs = _coarsen(segs, max_segments)
    return segs
