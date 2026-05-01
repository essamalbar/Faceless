# Arabic Horror Faceless YouTube System — Design Spec

**Date:** 2026-05-01
**Status:** Design approved (sections 1–5). Pending: written spec review by user, then writing-plans.
**Scope:** MVP of Phase 1 only (local CLI, no publishing).

---

## 1. Summary

A Python CLI that runs on the user's M3 Pro 48GB Mac and produces, in a single command, one finished Arabic-language horror video (10–15 minutes, 1920×1080, MP4) styled after the *Mr. Nightmare* aesthetic. Every stage runs locally or against free APIs — total recurring cost is $0.

The MVP **does not publish** to YouTube or anywhere else. The user watches the output file and decides whether quality is acceptable. Only after that gate is passed do later phases (uploader, scheduler, dashboard, trend miner) get designed.

This is intentional: the project's biggest risk is producing low-quality output. We discover that in a weekend at zero infrastructure cost rather than after building a dashboard, server, queue, and credentials system around content nobody wants to watch.

## 2. Goals & non-goals

### Goals (MVP)

- **Output quality bar:** generated videos visually and audibly indistinguishable from current top-grossing Arabic faceless horror channels (target reference: Mr. Nightmare aesthetic, in Arabic).
- **Cost:** $0 per video (free APIs and local compute only).
- **Cadence:** one video per `run.py` invocation; pipeline must complete in ≤45 minutes wall-clock on the target hardware.
- **Resumability:** any stage can be re-run in isolation without redoing earlier stages.
- **Determinism where it helps:** image seeds are fixed per shot so re-rolls only re-roll what's needed.

### Non-goals (explicitly deferred — do NOT design here)

- YouTube or TikTok upload / publishing
- Trend mining from social media
- Scheduling, automation, or daemonization
- Multi-channel support
- The Flutter mobile dashboard (existing Flutter app is untouched)
- Backend server, database, queue, or web API
- TikTok-specific vertical (9:16) reframe
- Reddit scraping (we generate stories with the LLM)

These each become their own brainstorm → spec → plan cycle after the MVP quality gate is passed.

## 3. Success criteria

The MVP is "done" when:

1. `python run.py` produces an `out/<run-timestamp>/final.mp4` without manual intervention.
2. Total run time on the target M3 Pro 48GB is ≤45 minutes.
3. The user watches three generated videos and answers yes to: *"would I subscribe to this channel?"*

If the user answers no, MVP is not done — iterate the offending stage in isolation. Disk-checkpoint architecture supports this without full pipeline replays.

## 4. High-level architecture

### 4.1 Pipeline (8 stages, sequential)

```
[1] Topic seeder      → seed (theme + Arabic premise)
        ↓
[2] Script writer     → script.json (Arabic story, 2000–2400 words)
        ↓
[3] Voice generator   → narration.mp3 + word_timings.json
        ↓
[4] Scene splitter    → shots.json (30–50 timed shots, English Flux prompts)
        ↓
[5] Image generator   → images/01.png … NN.png (1280×720)
        ↓
[6] Music selector    → music_track.mp3 (from local CC bundle)
        ↓
[7] Captions          → captions.ar.srt
        ↓
[8] Video assembler   → final.mp4 (1920×1080, H.264, AAC)
```

### 4.2 Disk-checkpointed dataflow

Every stage writes its complete output to `out/<run-timestamp>/` before the next stage runs. The orchestrator inspects files on disk to decide whether each stage needs to run, so a crashed run resumes from where it stopped. A user can also hand-edit any artifact (e.g. tweak a script line) and re-run downstream stages.

### 4.3 Module layout

Stages are independent Python modules under `pipeline/` (top-level — `lib/` is reserved for the existing Flutter app's Dart code). The orchestrator (`run.py`) is a thin sequencer. Each module is standalone-runnable for debugging:

```
pipeline/
├── seed.py        # topic + premise selection
├── script.py      # Gemini script generation + critique pass
├── voice.py       # edge-tts wrapper, returns audio + timings
├── shots.py       # timing-aware splitter + Gemini prompt translator
├── images.py      # mflux Flux.1 dev invocation, resumable
├── music.py       # mood-matched bundle picker
├── captions.py    # SRT generator (+ optional .ass burn-in)
├── assemble.py    # FFmpeg Ken Burns + crossfade + audio mix
├── llm.py         # Gemini wrapper (completion + embeddings)
├── runlog.py      # per-run structured logger
├── config.py      # config.yaml loader
└── types.py       # shared dataclasses
```

## 5. Component design

### 5.1 Topic seeder (Stage 1)

**Modes:**

- **Manual:** `run.py --theme folkloric --seed "بئر قديم في قرية مهجورة"` — user supplies theme tag and premise.
- **Auto** (default): pick a random theme from the bank → ask Gemini to generate a one-sentence horror premise in Arabic within that theme → premise becomes the seed.

**Theme bank** (8 categories, tagged for both seed selection and prompt enrichment):

| Tag | Description (Arabic seed examples) |
|---|---|
| `domestic` | البيت، الجيران، شلل النوم، أشخاص الظل |
| `wilderness` | الصحراء، الجبال، الرحلات الصحراوية، الضائعون |
| `urban` | شوارع فارغة، مبانٍ مهجورة، المترو في الثالثة فجراً |
| `workplace` | الورديات الليلية، الحراس، المستشفيات، الفنادق |
| `travel` | سيارات الأجرة، رحلات على طرق سريعة فارغة |
| `folkloric` | الجن، الغول، القرى المهجورة، الآبار القديمة |
| `tech` | مكالمات هاتفية غريبة، كاميرات تتعطل، تسجيلات قديمة |
| `memory` | الأصدقاء المتخيلون، أحلام متكررة، ذكريات نصف منسية |

`folkloric` is the channel's competitive edge over English horror — Middle Eastern folklore (jinn, ghoul, abandoned villages, old wells) is under-exploited and culturally grounded for the target audience.

**Theme rotation guard:** `out/theme_log.json` records every auto-picked theme with its run timestamp. Auto mode rejects any theme used in the most recent 3 runs.

### 5.2 Script writer (Stage 2)

The single most important component — every downstream stage's quality is capped by script quality.

**Story structure (Mr. Nightmare beat sheet):**

1. **Hook** — first 30 seconds. First-person narrator shows a normal moment that hints at wrongness. Dropping the hook = dropping the viewer.
2. **Setup** (1–2 min) — location, time, character. Mundane and grounded.
3. **First disturbance** (2–3 min) — small wrong thing; narrator dismisses it.
4. **Escalation** (3–4 min) — disturbances multiply; denial weakens.
5. **Confrontation** (2–3 min) — narrator faces what's happening.
6. **Climax** (1–2 min) — peak horror, fast pacing, short sentences.
7. **Unresolved ending** (final 30s) — never explain. Leave the unanswered question hanging.

**Target length:** 2,000–2,400 Arabic words (= 10–15 min of `ar-SA-HamedNeural` narration at slow rate).

**Gemini prompt enforces:**

- Modern Standard Arabic (الفصحى), not dialect.
- First-person POV (ضمير المتكلم).
- Banned tropes: "فجأة سمعت صوتاً" / "كان كل شيء حلماً" / explicit gore / supernatural deus ex machina / jump-scare clichés.
- Required uncanny-mundane moment — one ordinary thing slightly wrong.
- Required ambiguous ending — never explain what the entity was.
- Word count target: 2,200 ± 200.

**Two-pass generation:**

1. First pass writes the story.
2. Second pass critiques its own draft (*"is the hook strong? is the ending too explanatory? any clichés?"*) and rewrites weak sections.

**Repetition guard:** new story embedding (Gemini free embeddings) is compared against the last 30 stories in `out/story_history.jsonl`. If cosine similarity > 0.85 with any recent story, regenerate with a new premise.

**Output (`script.json`):**

```json
{
  "title": "صوت الجار في الطابق العلوي",
  "theme": "domestic",
  "global_setting": "modern apartment building, urban Saudi Arabia, winter night",
  "music_mood": "dread",
  "hook": "...الفقرة الافتتاحية...",
  "story": "...النص الكامل...",
  "word_count": 2187
}
```

`global_setting` is extracted by the script writer for use in every shot prompt (visual consistency lever — see 5.4). `music_mood` is one of `drone | dread | cosmic | discovery` and feeds the music selector.

### 5.3 Voice generator (Stage 3)

**Tool:** `edge-tts` Python package — wraps Microsoft's Edge browser TTS service. Free, no API key, neural voices, exposes `WordBoundary` events for word-level timings.

**Configuration:**

- Voice: **`ar-SA-HamedNeural`** (default — MSA male, deep, atmospheric).
- Alternative for A/B testing later: `ar-EG-ShakirNeural` (Egyptian, more conversational).
- Rate: **-20%** (slower than default — matches Mr. Nightmare pacing).
- Pitch: **-5%** (slight depth boost for atmosphere).
- Output: MP3 at 192 kbps mono.

**SSML pause injection (pre-processing the script before sending to Edge TTS):**

- Period `.` → `<break time="600ms"/>`
- Em-dash `—` or ellipsis `...` → `<break time="1200ms"/>`
- Paragraph break → `<break time="1500ms"/>`

Without these the narration sounds rushed and dread evaporates. Edge TTS will not pause dramatically on its own.

**Outputs:**

- `out/<run>/narration.mp3`
- `out/<run>/word_timings.json` — `[{word, offset_ms, duration_ms}, ...]`. Feeds the scene splitter (Stage 4) and captions generator (Stage 7).

### 5.4 Scene splitter (Stage 4)

**Input:** `script.json` + `word_timings.json`.

**Algorithm:**

1. Walk the word-timing list, accumulating words until ≈15–20 seconds of audio elapsed (~30–50 Arabic words at slow rate).
2. Snap each chunk boundary to the nearest **sentence end** within ±2 seconds — never cut mid-sentence.
3. Total chunks per video: 30–50 shots for a 10–15 min video.
4. For each chunk, send the Arabic text to Gemini with the prompt: *"Here is a paragraph from an Arabic horror story. The story is set in: {global_setting}. Output a single English image prompt for an atmospheric horror image illustrating this moment. No text in image. Photographic, dark, eerie. Describe environment, lighting, time of day, key visual element. Approximately 25 words."*
5. Append the **fixed style suffix** to every returned prompt.

**Style suffix (every shot, no exceptions):**

```
dark atmospheric horror photography, dim moonlight, slight film grain,
35mm aesthetic, low light, cinematic composition, eerie mood,
muted desaturated colors, ultra-realistic, 16:9
```

**Negative prompt (every shot):**

```
text, watermark, logo, blurry, low quality, deformed faces,
clear faces, multiple subjects, busy composition, cartoon, illustration
```

**Seed assignment:** `base_seed = hash(script.title) mod 2^31`; per-shot seed = `base_seed + shot_index`. Re-running image gen with the same seed produces the identical image, so manual re-rolls only re-roll specific shots without disturbing the rest.

**Output (`shots.json`):**

```json
[
  {
    "index": 1,
    "start_ms": 0,
    "end_ms": 18420,
    "arabic_text": "كنت أسير في الصحراء وحيداً تحت ضوء القمر...",
    "english_prompt": "lone figure walking distant on a moonlit desert dune, vast empty sky, footprints, silver light, cold air, [+ style suffix]",
    "negative_prompt": "[standard negative]",
    "seed": 1729384721
  }
]
```

### 5.5 Image generator (Stage 5)

**Tool:** Flux.1 dev via [`mflux`](https://github.com/filipstrand/mflux) — Apple Silicon-native Flux, MLX-optimized for M3.

**Settings:**

- Resolution: **1280×720** (16:9). FFmpeg upscales to 1920×1080 with Lanczos at assembly time.
- Steps: **25** (Flux dev hits high quality at 25; diminishing returns above).
- Guidance: **3.5**.

**Performance budget:** ~45s per image on M3 Pro 48GB. 40 images → ~30 minutes — the pipeline's biggest single time cost.

**Resumability:** the module checks `out/<run>/images/NN.png` for each shot and skips already-generated files. Crash at image 23 → re-run resumes at 23.

**Manual re-roll:** `python -m pipeline.images --reroll 23,27,31 --run-dir out/<run>` regenerates only those shots, with new seeds (existing seeds are bumped by `+10000` to ensure a different result).

**Visual consistency strategy** (the four levers, ranked by effect):

1. **Fixed style suffix** on every prompt — biggest single driver.
2. **`global_setting` injection** from `script.json` — every shot inherits locale/lighting/era.
3. **Negative prompt suppresses faces** — Mr. Nightmare rarely shows clear human faces; this also avoids the "AI weird face" failure mode.
4. **Seed family per video** — adjacent shots share visual DNA via consecutive seeds.

### 5.6 Music selector (Stage 6)

**Approach:** hand-curated local bundle. **Not** a runtime API.

**Setup (one-time):** `scripts/setup_music.sh` downloads ~20 CC0 / CC-BY atmospheric horror tracks from Pixabay Music and Free Music Archive into `assets/music/`. All royalty-free for commercial / monetized YouTube use. Bundle ≈150 MB.

**Metadata (`assets/music/tracks.json`):**

```json
[
  {
    "filename": "drone-01.mp3",
    "duration_s": 312,
    "mood": "drone",
    "license": "CC0",
    "source_url": "https://pixabay.com/...",
    "attribution": null
  }
]
```

**Selection:** read `script.json`'s `music_mood` field, filter the bundle, pick a random matching track. Track is copied (not linked) into the run output folder so runs are self-contained.

**Why a static bundle, not an API:** Pixabay/FMA APIs work but track quality is inconsistent. Listening to 20 hand-picked tracks once guarantees every video sounds professional. API-based dynamic selection is a phase-2 upgrade if variety becomes a felt need.

### 5.7 Captions generator (Stage 7)

**Two outputs from one source (word timings):**

**Primary: SRT subtitle file (`captions.ar.srt`)** — for YouTube long-form.

- Group word timings into caption lines: 6–10 words per line, max 4 seconds per line, never split mid-sentence.
- UTF-8 Arabic. Renders RTL correctly in YouTube and all modern players.
- Uploaded alongside the video for toggleable subs and free auto-translation to other languages (extends reach without effort).

**Optional: burned-in captions (`.ass` file consumed by FFmpeg in Stage 8)** — for TikTok / Shorts in Phase 2.

- Disabled by default for MVP. Toggle via CLI flag `--burn-captions`.
- FFmpeg + libass. Font: **Cairo Bold** (Google Fonts, free, excellent Arabic rendering, shipped in `assets/fonts/`).
- Style: 60px white, 4px black outline, semi-transparent black bar in the bottom third of frame.

For Mr. Nightmare-style long-form: SRT only. The burn-in path is implemented but disabled — Phase 2 just flips a flag.

### 5.8 Video assembler (Stage 8)

**Tool:** FFmpeg via `ffmpeg-python`.

**Per-shot rendering — Ken Burns motion:**

- Slow zoom (110% over the shot duration) plus slight pan.
- **Direction alternates** to prevent monotony: shot 1 zoom-in; shot 2 zoom-out + pan-right; shot 3 zoom-in + pan-left; etc. Cycle of four motion patterns.
- FFmpeg `zoompan` filter handles this. Scaling to 1920×1080 with Lanczos.

**Between shots:** 800ms crossfade (`xfade` filter). Soft transitions match the Mr. Nightmare aesthetic.

**Audio mix:**

- Voice: 0 dB.
- Music: looped to length, then sidechain-compressed by voice — `-18 dB` during narration, `-8 dB` during silence.
- 3-second fade-in at video start; 3-second fade-out at end.

**Output:** `final.mp4` — H.264, AAC, MP4 container, ~150–250 MB for a 12-min 1080p video. YouTube-ready.

**Performance:** ~3–5 minutes on M3 Pro. Combined with image generation (~30 min), full pipeline run is ~35–45 minutes.

## 6. Configuration

### 6.1 `config.yaml` (defaults; CLI flags override)

```yaml
voice:
  name: ar-SA-HamedNeural
  rate: -20%
  pitch: -5%

script:
  word_count_target: 2200
  word_count_tolerance: 200
  enable_critique_pass: true
  repetition_threshold: 0.85

flux:
  steps: 25
  guidance: 3.5
  width: 1280
  height: 720

assemble:
  output_width: 1920
  output_height: 1080
  shot_crossfade_ms: 800
  music_duck_db: -18
  music_silence_db: -8
  fade_in_s: 3
  fade_out_s: 3

captions:
  burn_in: false
  font: Cairo-Bold
  font_size: 60
```

### 6.2 CLI surface

```bash
# default — auto-pick theme, full pipeline
python run.py

# manual seed
python run.py --theme folkloric --seed "بئر قديم في قرية مهجورة"

# resume a crashed run (auto-detected from disk state)
python run.py --resume out/2026-05-01-1430

# re-roll specific failed shots, keep everything else
python run.py --reroll-images 23,27,31 --run-dir out/2026-05-01-1430

# debug — placeholder PNGs instead of running Flux
python run.py --skip-images

# choose alternative voice without editing config
python run.py --voice ar-EG-ShakirNeural

# burn captions into the video (for Shorts experimentation)
python run.py --burn-captions
```

## 7. Project layout

```
faceless/                       # repo root (existing Flutter project)
├── pyproject.toml              # uv-managed Python deps
├── config.yaml                 # defaults, see §6.1
├── run.py                      # CLI entry / orchestrator
├── pipeline/                   # Python package (separate from Flutter's lib/)
│   ├── __init__.py
│   ├── seed.py
│   ├── script.py
│   ├── voice.py
│   ├── shots.py
│   ├── images.py
│   ├── music.py
│   ├── captions.py
│   ├── assemble.py
│   ├── llm.py                  # Gemini wrapper (chat + embeddings + prompt translation)
│   ├── runlog.py
│   ├── config.py
│   └── types.py
├── tests/
│   ├── conftest.py             # shared fakes (Gemini, EdgeTTS, mflux, FFmpeg)
│   └── ... (one test_*.py per pipeline module)
├── assets/
│   ├── music/                  # 20 CC0/CC-BY tracks + tracks.json
│   └── fonts/
│       └── Cairo-Bold.ttf
├── scripts/
│   └── setup_music.sh
├── out/                        # gitignored — every run writes here
│   └── 2026-05-01-1430/
│       ├── script.json
│       ├── narration.mp3
│       ├── word_timings.json
│       ├── shots.json
│       ├── images/01.png … NN.png
│       ├── music_track.mp3
│       ├── captions.ar.srt
│       ├── final.mp4
│       └── run.log
└── (existing Flutter app — lib/, android/, ios/, web/, macos/, etc. — UNTOUCHED)
```

## 8. Error handling and resumability

- Every stage is idempotent on disk: it writes the next artifact only if the artifact doesn't already exist (or `--force` is passed).
- Stage failures preserve all prior artifacts. The orchestrator inspects the output folder to decide where to resume.
- Each stage retries transient errors (network blips on Gemini / Edge TTS) with exponential backoff (3 attempts, 1s / 5s / 30s).
- Permanent failures abort with a clear error and the run folder is left intact for inspection or `--resume`.
- Per-run log at `out/<run>/run.log` records every stage start, end, duration, and any retries.

## 9. Verification plan

After implementation, the bar is one question per generated video: **would I subscribe to this channel?**

Iteration loop:

| Failure | Cheapest fix |
|---|---|
| Script weak, hook flat, ending too neat | Tune `lib/pipeline/script.py` prompt; iterate (Gemini is fast). |
| Images incoherent or off-style | Adjust style suffix, negative prompt, Flux settings; re-roll. |
| Voice rushed or robotic | Tune rate/pitch; try `ar-EG-ShakirNeural`. |
| Pacing or mixing off | Adjust `assemble.py` crossfade / ducking levels. |
| Captions break mid-sentence | Tune chunking thresholds in `captions.py`. |

The disk-checkpointed architecture means each iteration only re-runs the affected stage. No full pipeline replays.

**Gate to Phase 2:** the user has watched ≥3 generated videos and answered yes to the subscribe question. Until then, no work begins on uploaders, schedulers, dashboards, or trend miners.

## 10. Phase 2+ roadmap (out of scope for this spec)

Each becomes its own brainstorm → spec → plan → build cycle:

1. **YouTube Data API uploader** — single channel, manually triggered.
2. **Scheduler** — cron / GitHub Actions wrapper, runs the CLI daily.
3. **Multi-channel** — same code, per-channel credentials and theme bias.
4. **Mobile dashboard** — the existing Flutter app gets a small backend to talk to.
5. **Trend miner** — replaces auto-theme selection with trending-topic-driven seeding.
6. **TikTok adaptation** — vertical (9:16) reframe + always-on burned captions.

Explicitly **not designed in this spec.** Do not implement them as part of the MVP.

## 11. Decisions locked

| Decision | Choice | Rationale |
|---|---|---|
| First sub-project | CLI that produces one finished video, no publishing | Cheapest way to test the riskiest assumption (output quality). |
| Genre | Reddit-style scary stories (sub-genre: r/nosleep style) | Highest watch time → highest YouTube RPM; less saturated than AITA; AI horror imagery forgives uncanny aesthetic; least competitive in Arabic. |
| Format | F2: long-form single story, 10–15 min, daily | Passes 8-min mid-roll-ad threshold; daily cadence is YouTube algorithm sweet spot; single visual mood per video. |
| Source | Original AI-generated stories (not Reddit scraped) | Free, unlimited, no copyright/demonetization risk, tunable. |
| Style reference | Mr. Nightmare aesthetic | Most-copied template in genre; AI-friendly visuals; matches Edge TTS deep-voice capability. |
| Language | Full Arabic (L2) — narration + captions | Far less competition; user is native Arabic speaker (can quality-check); strong Gulf monetization. |
| Voice | `ar-SA-HamedNeural` (MSA male, atmospheric) | Best fit for horror per Edge TTS catalog. `ar-EG-ShakirNeural` available as A/B alternative. |
| Captions | SRT only (toggleable on YouTube) for MVP | Mr. Nightmare style is minimal text. Burned-in path built but disabled until Phase 2 Shorts. |
| Music | Hand-curated CC0/CC-BY local bundle (~20 tracks) | Quality consistency over API variety. Tagged by mood, picked at runtime via `script.music_mood`. |
| Story length | 2,000–2,400 Arabic words = 10–15 min | Crosses 8-min mid-roll threshold; manageable Flux cost. |
| Aspect ratio | 16:9 (1920×1080) | Long-form YouTube. Vertical reframe deferred to Phase 2 TikTok work. |
| Tech stack | Python 3.11+, uv, Gemini API, mflux, edge-tts, ffmpeg-python | All free; all native or efficient on M3 Pro 48GB. |
