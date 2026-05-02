# @sunstoriz-Quality TikTok Pipeline — Tier 3 Design Spec

**Date:** 2026-05-02
**Status:** Awaiting user review of this spec; then writing-plans → implementation.
**Replaces:** earlier `--shorts` Tier 1 design (kept as legacy code path).

---

## 1. Summary

Upgrade the existing `--shorts` pipeline to produce **60–120 second** vertical TikTok videos — length determined by **story complexity**, not a fixed clip count — that match the visual + narrative quality of the reference channel **@sunstoriz**. Five concrete fixes target the user's five specific complaints from the last viewing:

| Complaint | This spec's fix |
|---|---|
| "Clips feel disconnected" | Image-to-video **chaining** — last frame of clip N becomes first frame of clip N+1. Plus a shared character sheet that all clips reference. |
| "Audio doesn't match events" | Per-beat clip alignment: each clip's duration is the duration of its narration beat. |
| "Subtitles not synced" | **Whisper force-alignment** of Arabic captions against the actual audio (not synthesized from word counts). |
| "AI voice sounds artificial" | **ElevenLabs Multilingual v2** Arabic voice (replaces Edge TTS). |
| "Like a world-class filmmaker" | **Veo 3 (full quality)**, not Veo 3 Fast. ~4× the per-second cost; materially better composition + character continuity. |

Lip sync (mouth movements matching audio) is **explicitly out of scope** — the @sunstoriz reference itself does not lip-sync; narration is over-the-shoulder. Adding HeyGen lip sync is a Tier 4 future spec.

## 2. Goals & non-goals

### Goals

- **Quality bar:** indistinguishable from @sunstoriz to a casual viewer.
- **Length:** 60–120 seconds, **chosen by the script writer per-story** (a simple twist may need 60s; a multi-stage tragedy may need 120s).
- **Cost ceiling:** ≤ $50 per finished video (range ~$26 for 60s up to ~$48 for 120s).
- **Wall time:** ≤ 35 min per video at the longest length.
- **Cohesion:** characters, setting, lighting consistent across **all** clips in a video.
- **Audio honesty:** narration audio actually corresponds to what's on screen at each moment.

### Non-goals (Tier 4 or later)

- HeyGen / SadTalker lip sync.
- Multi-character voice (currently single narrator only).
- Manual scene curation / regeneration UI.
- YouTube/TikTok auto-publishing.
- Multi-channel scheduling.

## 3. Success criteria

The Tier-3 pipeline succeeds when, for ≥3 generated videos across different story lengths (one ~60s, one ~90s, one ~120s):

1. The user watches and answers **yes** to: *"Could this go live on @sunstoriz right now without me feeling bad about quality?"*
2. Cost per video ≤ $50 and wall time ≤ 35 min.
3. Length actually fits the story — short twists are short, slow tragedies are longer; not artificially padded or truncated.
4. Characters look like the **same** lemon mother / strawberry son etc. across all clips in a video.
5. Subtitles change exactly when the narrator says the next word.
6. Voice does not sound AI to a native Arabic listener.

## 4. Architecture changes

### 4.1 New pipeline order

```
[1] Topic seeder
        ↓
[2] Script writer (Groq Llama 3.3 70B)
    → variable beats: writer picks 8–15 beats AND target length (60–120s) based on
      how much story the premise needs. ~30 Arabic words / beat (~7s narration each).
      Returns target_duration_s in the JSON so downstream stages know.
        ↓
[3] Voice generator (ElevenLabs Multilingual v2)         ← REPLACES Edge TTS
    → narration.mp3 (single continuous Arabic file)
    → ElevenLabs returns alignment data per character — we keep it as a hint
        ↓
[4] Whisper force-aligner                                ← NEW
    → reads narration.mp3 + the Arabic story text
    → outputs accurate word_timings.json (per-word ms offsets)
        ↓
[5] Character sheet generator (Kie.ai Flux)              ← NEW
    → ONE 1024×1024 reference image: "8 anthropomorphic fruit characters
      lined up — lemon mother in black hijab, strawberry son child & adult,
      apple doctor, mango neighbor, etc., 3D Pixar style"
        ↓
[6] First-keyframe generator (Kie.ai Flux + ref image)   ← NEW
    → ONE vertical 720×1280 keyframe for clip 1 from beat 1's motion prompt,
      using the character sheet as `imageUrls` reference.
        ↓
[7] Video clips (Kie.ai Veo 3, FIRST_AND_LAST_FRAMES_2_VIDEO mode)  ← UPGRADED
    For each beat i (1..N) where N is whatever the script writer chose (8–15):
      - input first_frame   = (i==1 ? frame_01.png : last_frame_of_clip_(i-1))
      - input last_frame    = (optional) Flux-generated target frame for beat i
      - prompt              = beat i's english_motion + global style suffix
      - duration            = matches beat i's narration audio duration
                              (variable per beat — typically 6–9 sec)
      - returns clip_i.mp4 + extracts last frame for next clip
        ↓
[8] Music selector (unchanged)
        ↓
[9] Captions (Whisper-timed yellow karaoke .ass — already implemented; just feed real timings)
        ↓
[10] Assembler (FFmpeg vertical concat, ~250ms crossfade between matched clips)
```

### 4.2 Why each change

- **ElevenLabs (vs Edge TTS):** their Arabic Multilingual v2 voices (Cassidy, Hala, Sara) are trained on real human recordings. Edge TTS is rule-based concatenation that always sounds robotic. For TikTok content this is the single biggest quality win.

- **Whisper alignment:** Edge TTS gives word boundaries for English but not Arabic. We've been synthesizing per-word timings by dividing total audio duration by word count — a guess. Whisper transcribes the actual audio, gives ms-precise word starts/ends, and we map them onto the known Arabic text.

- **Character sheet + image-to-video chaining:** Veo text-to-video can't keep characters consistent across calls because each call has no shared reference. Generating one Flux character sheet image up front and feeding it as a reference to every Veo call (via `imageUrls`) anchors the appearance. Chaining the last frame of each clip into the first frame of the next means cuts feel like edits, not jumps to a different world.

- **Veo 3 (full) vs Veo 3 Fast:** Veo 3 Fast prioritizes throughput; quality is noticeably below Veo 3. For this use case (~8 clips per video, 1 video at a time) the quality matters far more than the speed.

- **Per-beat clip duration:** Currently all clips are forced to 8 seconds and the narration determines final length, so clip content doesn't sync to what's being said. By generating each clip with the duration of its specific beat's narration, the visual always matches the audio.

- **Variable total length (60–120s):** Hard-coding 8 clips makes some stories feel rushed and others padded. The script writer is told the **target range** and picks the number of beats that fits the premise. A simple "neighbor reveals affair" twist might need 8 beats / 60s; a multi-stage "mother's life of sacrifice → son's downfall → death" tragedy needs 12–15 beats / 100–120s. The orchestrator reads the writer's chosen `num_beats` and budgets accordingly.

## 5. Component-level changes

### 5.1 `pipeline/elevenlabs.py` (NEW)

Thin HTTP client for ElevenLabs Text-to-Speech API.

- **Auth:** `xi-api-key` header (not Bearer)
- **Endpoint:** `POST /v1/text-to-speech/{voice_id}` with model `eleven_multilingual_v2`
- **Body:** `{"text": "<Arabic story>", "model_id": "eleven_multilingual_v2", "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}}`
- **Output:** raw mp3 bytes streamed to disk
- **Same interface contract as `pipeline/voice.py`'s `generate_narration`** — drop-in replaceable based on which provider is configured.

### 5.2 `pipeline/voice.py` (MODIFIED)

- Becomes a router: dispatches to `elevenlabs` or `edge_tts` based on `config.voice.provider`.
- Existing Edge TTS code path stays as fallback / for when no ElevenLabs key is set.

### 5.3 `pipeline/align.py` (NEW)

- Wraps OpenAI Whisper (local model `small` or `large-v3` for Arabic accuracy).
- Function: `align_arabic(audio_path, expected_text) -> list[WordTiming]`
- Uses Whisper's `word_timestamps=True` mode + force-alignment via the known Arabic text.
- ~30 sec on M3 Pro for ~75-sec audio.

### 5.4 `pipeline/character_sheet.py` (NEW)

- Calls Kie.ai's Flux endpoint (`/api/v1/flux/generate` — verify exact path during impl).
- Generates ONE 1024×1024 image showing all named fruit characters together.
- Saved as `out/<run>/character_sheet.png`.
- Resumable (skip if exists).

### 5.5 `pipeline/video.py` (MODIFIED)

- Switch from `TEXT_2_VIDEO` to `FIRST_AND_LAST_FRAMES_2_VIDEO` (or `IMAGE_2_VIDEO` if simpler).
- Each Veo call's `imageUrls` includes the character sheet + prior clip's last frame.
- After each clip downloads, run `ffmpeg -ss <duration-0.1> -i clip.mp4 -frames:v 1 last_frame.png` to extract its last frame for the next call.
- Per-beat clip duration: passes `duration_seconds` per call computed from beat's narration length.
- Model name in config bumped from `veo3_fast` → `veo3` (full).

### 5.6 `pipeline/captions.py` (MINOR FIX)

- No change to formatting logic — already karaoke-style yellow.
- But the .ass file now consumes Whisper-aligned timings, so cues finally match speech.

### 5.7 `config.yaml` (UPDATED)

```yaml
voice:
  provider: elevenlabs
  elevenlabs_voice_id: <Arabic Egyptian female voice id from dashboard>
  elevenlabs_model: eleven_multilingual_v2
  fallback_to_edge_tts: true

script:
  min_beats: 8                 # ≈ 60s
  max_beats: 15                # ≈ 120s
  words_per_beat: 30           # ~7s narration per beat

kie:
  model: veo3                  # was veo3_fast
  cost_per_second_usd: 0.40    # was 0.10 (Veo 3 full pricing)
  max_spend_usd: 50.00         # buffer for 15-clip / ~$48 video

  flux_model: flux-pro         # for character sheet + first frame
  flux_cost_per_image_usd: 0.05
```

`num_clips` is no longer a fixed config value — the script writer picks it per-story within `[min_beats, max_beats]` and the orchestrator reads `len(script.beats)` to drive the video stage.

### 5.8 `.env` additions

```
export ELEVENLABS_API_KEY=<your key>
```

## 6. Cost & time per video (variable by length)

Costs scale with the script writer's chosen length. Three reference points:

| | **Short story (~60s, 8 beats)** | **Medium (~90s, 12 beats)** | **Long tragedy (~120s, 15 beats)** |
|---|---:|---:|---:|
| Script (Groq) | $0 | $0 | $0 |
| Voice (ElevenLabs) | ~$0.30 | ~$0.45 | ~$0.60 |
| Whisper align (local) | $0 | $0 | $0 |
| Character sheet (Flux) | $0.05 | $0.05 | $0.05 |
| First keyframe (Flux) | $0.05 | $0.05 | $0.05 |
| Video clips (Veo 3 × $0.40/sec) | $25.60 | $38.40 | $48.00 |
| Music + Captions + Assembly | $0 | $0 | $0 |
| **TOTAL** | **~$26** | **~$39** | **~$49** |
| **Wall time** | ~25 min | ~30 min | ~35 min |

The hard cap (`max_spend_usd: 50`) refuses any run whose projected cost exceeds $50, so you never get a surprise bill.

## 7. User pre-requisites before we run

1. **ElevenLabs account + API key** (free tier won't be enough — needs a paid plan, $5–22/month depending on character volume).
2. **Kie.ai credits ≥ $50** to safely run a single 120-sec video (currently ~$10 left from the original $50; needs a top-up of at least $50).
3. Whisper-`small` Arabic model — auto-downloaded on first run (~480 MB).

I'll guide you through ElevenLabs signup the same way we did Kie.ai when implementation starts.

## 8. Implementation phases

1. **Phase A — wiring (no real $$ spent):** ElevenLabs client + tests, Whisper align + tests, character_sheet + tests, video.py upgrade + tests. All mocked. ~1 day.
2. **Phase B — first real run:** end-to-end against ElevenLabs + Kie.ai with real money. Watch the result. ~30 min wait + watch.
3. **Phase C — tune:** adjust prompts, voice settings, music levels based on what's off in B. Iterate 2–3 videos.

## 9. Risks I want you to know

- **Veo 3 full might still produce inconsistent characters** even with image-to-video chaining; the underlying model isn't trained for true continuity. Worst case, characters drift across clips even with the sheet reference. Mitigation: generate each clip's first AND last frame via Flux explicitly with character sheet reference, force Veo to interpolate between them.

- **ElevenLabs Arabic voices are mostly trained on Egyptian/Lebanese accents.** If you want Syrian specifically, choices are limited. Best Arabic-natural voices: Hala, Cassidy, Sara. We pick one in implementation.

- **Per-beat duration** depends on Whisper alignment being accurate. If Whisper gets confused on parts of fast Arabic, beat boundaries may be a few hundred ms off. Acceptable for TikTok pacing.

- **Kie.ai's Flux endpoint isn't identical to Veo's.** Need to confirm endpoint paths during implementation; same workaround as before (env var override).

- **Cost overrun:** if a clip is rejected by Veo's safety filter (like beat 8 last time), reroll spends another $3.20. Mitigation: stronger prompt sanitization (no "buried", "die", "blood", etc.).

## 10. Decisions locked

| Decision | Choice | Why |
|---|---|---|
| Voice provider | **ElevenLabs Multilingual v2** | Only realistic-sounding free-form Arabic option. |
| Video model | **Kie.ai Veo 3 (full)** | Quality matches @sunstoriz; Fast doesn't. |
| Continuity strategy | **Image-to-video chain + character sheet ref** | Anchors fruit characters across clips. |
| Subtitle alignment | **Whisper local** | Free, accurate, runs on M3. |
| Lip sync | **NOT in this tier** | @sunstoriz doesn't have it; HeyGen is too expensive ($8–40 extra per video). |
| Cost cap per video | **$50** | Buffer over $48 max for the longest 120-sec stories. |
| Length | **60–120 sec, story-driven** | Writer picks 8–15 beats based on premise complexity; orchestrator follows. |
| Tests | **Mock all paid APIs** | Same pattern as Kie.ai tests today. |
