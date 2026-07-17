# Arabic Quality Pack — Design Spec

**Date:** 2026-07-17
**Status:** Approved (user chose "all five")
**Context:** Trust-the-autopilot hardening. The user's two explicit asks
(tashkeel, editable style at review) plus three compounding quality levers.
Everything the system produces (manual songs, trend-brief creates, morning
drafts, covers) inherits these.

## 1. Tashkeel (التشكيل) — correct pronunciation

- **Lyrics contract** (`song_lyrics._SYSTEM_PROMPT`): Arabic lyrics MUST be
  fully diacritized (تشكيل كامل) — Suno reads the harakat and pronounces
  correctly. Non-Arabic languages unaffected.
- **Cover transcripts** (`song_import._SECTION_SYSTEM`): while sectioning,
  ADD full tashkeel — the words themselves stay untouched (diacritics
  disambiguate, they don't rewrite).
- **`POST /songs/{run_id}/diacritize`** (awaiting_approval only): one LLM
  pass adds full tashkeel to the CURRENT lyrics (user-typed customs, old
  drafts, post-edit). Guard: the LLM must not add/remove/reorder words or
  section tags — prompt-enforced + a letters-only comparison check (strip
  harakat from the result; its letter skeleton must equal the input's,
  else 502 and no write). Updates song.json + lyrics.txt, returns the lyrics.
- Flutter review screen: a **"تشكيل"** button (visible when language==ar)
  calling the endpoint and refreshing the lyrics box.

## 2. Editable style at review

Backend `POST /songs/{id}/edit` already accepts `style_prompt`/`cover_prompt`
— UI-only gap. The approve screen's style section gets the same edit
affordance as lyrics (multiline field, Save → edit endpoint → refresh).

## 3. Singability contract

`_SYSTEM_PROMPT` additions: consistent rhyme scheme (قافية موحّدة) per
section; singable, consistent meter (syllable counts roughly even across a
section's lines); the chorus hook repeats VERBATIM; simple emotional words
over literary flourish; no tongue-twisters.

## 4. Default negative tags

`run.py` passes `negative_tags` (params already exist on both submit
functions, never used): default
`"robotic vocal, autotune artifacts, off-key, muffled, low quality"` on both
the generate and cover branches; `song.json`'s `negative_tags` overrides when
present (future editability).

## 5. Arabic dialect selector

- Values: `msa` (فصحى), `egyptian`, `khaleeji`, `levantine`, `iraqi`.
- `generate_song_script(..., dialect=None)`: adds a dialect instruction to
  the user msg ("Write the lyrics in {dialect} Arabic dialect").
- `CreateSongRequest.dialect` (optional, validated) → passed through.
- Artists gain `default_dialect` (new_artist/Summary/Patch); New Song
  prefills from the artist; morning drafts + trend-brief creates pass it.
- Flutter: dialect dropdown on New Song (shown when language==ar) + artist
  edit; bilingual labels.

## Testing (externals mocked)

- lyrics: system prompt carries tashkeel + rhyme/meter/hook contract;
  dialect lands in the user msg.
- diacritize endpoint: happy path updates lyrics; skeleton-mismatch (LLM
  changed words) → 502, file untouched; non-awaiting → 409.
- run.py: both submit branches receive the default negative_tags (extend
  the existing fakes' captures).
- artists: default_dialect round-trips; morning draft passes it.
- Flutter: analyzer zero errors; ARB parity.

## Non-goals

Automatic dialect detection; per-line phonetic hints; mastering/EQ.
