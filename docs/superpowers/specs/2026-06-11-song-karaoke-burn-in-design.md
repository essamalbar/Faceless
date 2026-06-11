# Song Karaoke & MP4 Burn-In Design

> Status: approved 2026-06-11 by essam (one-pass spec, no separate brainstorm)
> Scope: small enough to spec inline; ~5 hr implementation in 3 commits

## Problem

Three connected gaps in the AI-song mode:

1. **Share-page karaoke drifts.** Current implementation in `pipeline/api.py:3637` evenly divides song duration across stanza count — comment honestly says "will drift on songs with big tempo changes." Visible to anyone who opens a share link.

2. **Downloaded MP4 has no lyrics.** `pipeline/song_assemble.py` produces cover.png + song.mp3 in MP4 container — when users repost on WhatsApp/Instagram/TikTok the visual is just the static cover with no text. Half the song's value (the lyrics) is invisible.

3. **404 on deleted shares is hostile.** Three branches in `pipeline/api.py` (`_resolve_shared_song`) raise `HTTPException(404, "shared link not found"|"shared link corrupted"|"shared song was deleted")`. Friends opening the link see raw JSON, not a branded page.

## Approach

One shared timing artifact drives both features.

**New pipeline stage**: `pipeline/song_align.py` runs after Suno (or after take-swap) and before assembly. Output: `<run>/song/lyrics.json` of the shape:

```json
{
  "lines": [
    {"text": "في ليلٍ بعيد", "start": 12.34, "end": 17.89, "stanza": 1},
    {"text": "تذكّرتُكِ", "start": 17.91, "end": 22.11, "stanza": 1}
  ],
  "audio_duration": 192.4
}
```

Section tags (`[Verse 1]`, `[Chorus]`) are stripped before alignment and re-attached to the first line of each stanza for display purposes.

### Forced alignment: Whisper word-stream + sequential consumption

Pure-Python approach using the Whisper model that's already in the Docker image (and warm in the `whisper-cache` volume per `CLAUDE.md`). No new dependencies; no espeak; no PyTorch alignment models.

1. Run `whisper.transcribe(song_mp3, language="ar", word_timestamps=True)`.
2. Flatten every segment's `words` array into a single chronological stream `[(detected_text, start, end), ...]`. We ignore `detected_text` — only timestamps matter (memory: never display Whisper's Arabic transcription, but its segmentation is reliable).
3. For each lyric line, count its non-tag words (whitespace split after stripping diacritics and `[…]`). Pop that many words off the Whisper stream; the line's `start` is the first popped word's `start`, `end` is the last's `end`.
4. If the Whisper stream runs out before lyrics do (Whisper missed a word in a quiet passage), fall back to linear interpolation across the remaining audio for the tail.

Trade-offs honestly stated:
- **Line-level only**, per user decision — word-level highlighting inside a line would require sub-word forced alignment which is brittle on RTL Arabic with diacritics.
- Whisper's Arabic word boundaries are reliable at the *whitespace* level; mid-word over-segmentation is rare. If it happens, line cues shift by a fraction of a second — visually fine.
- Whisper transcription itself is not displayed — only its segmentation is consumed. This sidesteps the documented "never show Whisper Arabic output" rule.

### MP4 burn-in

`pipeline/song_assemble.py` is extended to:
1. Read `lyrics.json` next to `song.mp3`.
2. Generate `lyrics.ass` (Advanced SubStation Alpha) — one Dialogue line per lyric line, with `Style: Karaoke` defining a Cairo/Naskh Arabic font, white fill, black outline, drop shadow, centered, 8% from bottom.
3. Add `-vf "ass=lyrics.ass"` to the existing ffmpeg command. Output stays `final.mp4`.
4. Atomic-write semantics already in place (`.tmp + replace`) — no change.

Docker image gets one new package: `fonts-noto-naskh-arabic` (small, ~5 MB).

### Friendly deleted-share page

`pipeline/api.py:_resolve_shared_song` currently raises `HTTPException(404, …)` from inside helpers consumed by all three `/p/{token}{,/video,/cover}` endpoints. Rather than thread HTML through every consumer, add a single FastAPI exception handler that converts any 404 whose detail starts with `shared link `/`shared song ` into a branded HTML response: heading "This song has been removed", subtitle "The creator deleted the share link — try making your own.", CTA button to `https://faceless-lab.com`. Cover-art and video binary endpoints keep returning 404 with a small JSON body (browsers don't render those directly so HTML doesn't help there).

## File-by-file changes

| File | Change |
|---|---|
| `pipeline/song_align.py` | NEW — Whisper-driven line alignment, ~90 lines |
| `pipeline/song_assemble.py` | Read `lyrics.json`; generate `lyrics.ass`; add `ass=` filter |
| `pipeline/api.py` | (a) Friendly 404 exception handler. (b) Share page reads `lyrics.json` if present and emits the timing array as JSON in the script tag instead of relying on `data-total-stanzas` |
| `run.py` | Insert `song_align` stage between Suno-and-swap and assembly; skip if `lyrics.json` already exists (resumable) |
| `Dockerfile` | `apt install fonts-noto-naskh-arabic` |
| `pipeline/song.py` | No change (alignment is downstream of Suno output) |

## Testing

- Existing test suite has no song-mode tests (tracked separately). For this change: smoke-test on one real shared run (`OzRVHubhk_MaC8rbVdJjQA` is the test subject — user has it open).
- Verify: (1) share page karaoke lines flip in time with audio playback, (2) MP4 download has burned-in lyrics, (3) `/p/<deleted-token>` returns the branded HTML page, (4) `/p/<token>/video` for a deleted token returns a small JSON 404 (binary endpoint — browsers don't see this).

## Out of scope

- Word-level karaoke (decided line-level).
- Reusing forced alignment for horror-mode captions (separate workstream; horror's captions are already produced from script segments which already have timings).
- Editing share-page styling beyond what's needed to surface the new timing data.

## Commit plan

1. **Commit 1**: friendly 404 page — independent of alignment, ships immediately.
2. **Commit 2**: `song_align.py` + run.py wiring + share page consumes timings — ships the karaoke fix.
3. **Commit 3**: Dockerfile font + `song_assemble.py` burn-in — ships the burned-in MP4.

Each commit is self-contained and produces a shippable Cloud Run image.
