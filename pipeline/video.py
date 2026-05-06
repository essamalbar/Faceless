"""Stage 5 (Shorts mode): clip generation via Kie.ai.

Replaces the still-image stage from the long-form pipeline. Reads the
script's beats, builds a Veo prompt per beat (style suffix + global
setting + beat motion), submits each as a Kie.ai job, downloads the
resulting MP4 to clips/NN.mp4. Resumable per-clip; supports rerolls
with bumped seeds. Refuses to start any run that exceeds max_spend_usd.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

import requests

from pipeline.kie import KieClient, generate_clip
from pipeline.types import Beat, Script

# Style suffix appended to every Veo prompt for visual consistency across clips.
# Veo on Kie.ai does NOT accept a separate negative_prompt — guidance about what
# NOT to show must be baked directly into the prompt text.
#
# This suffix targets @sunstoriz-style: 3D Pixar-quality animation with
# anthropomorphic fruit characters as humans (lemon mother, strawberry son,
# apple doctor, etc.). Photorealistic textures + dramatic emotional lighting.
VIDEO_STYLE_SUFFIX = (
    "3D Pixar-style animation, photorealistic CGI textures, "
    "anthropomorphic fruit characters wearing human clothing "
    "(hijab, traditional thobe, doctor coat, casual t-shirt), "
    "expressive emotional faces with sad detailed eyes, "
    "dramatic cinematic lighting, vertical 9:16 aspect ratio, "
    "high detail, professional rendering, "
    "no text overlay, no watermark, no logo, no captions burned into video"
)
VIDEO_NEGATIVE_PROMPT = ""  # unused (Veo ignores it); kept for API stability
REROLL_SEED_BUMP = 100_000

# Per-speaker character lock — the SAME description is injected into every
# beat's Veo prompt for that speaker, so visual identity stays consistent
# across clips. Each entry pins outfit, age, eye type, and signature
# accessory. We deliberately commit to ONE age band per character (no
# "child vs adult" variants) because Veo cannot age-shift a character
# mid-video without visible identity drift — the user noticed son being
# small in one clip and an adult in another.
SPEAKER_DESCRIPTIONS: dict[str, str] = {
    "mother": (
        "the LEMON MOTHER character — middle-aged anthropomorphic lemon-headed "
        "woman (mid-50s), bright yellow lemon-shaped head with smooth skin, "
        "large tired sad brown eyes, gentle wrinkles around eyes, "
        "wearing a plain BLACK hijab covering hair and a long dark grey dress "
        "with simple embroidery, weary maternal expression, thin frame"
    ),
    "son": (
        "the STRAWBERRY SON character — young adult anthropomorphic strawberry-headed "
        "man (early 20s), red strawberry-shaped head with small green leaves on top "
        "as hair, dark expressive eyes, light beard stubble, "
        "wearing a casual grey t-shirt and dark trousers, "
        "regretful tired expression, lean build "
        "(NEVER a child or boy — always an adult young man across all clips)"
    ),
    "father": (
        "the OLDER LEMON FATHER character — elderly anthropomorphic lemon-headed "
        "man (mid-60s), pale yellow lemon-shaped head with deep wrinkles, "
        "white beard and white moustache, hollow tired eyes, "
        "wearing a traditional white thobe with brown vest, "
        "weak weary expression, slightly stooped posture"
    ),
    "doctor": (
        "the APPLE DOCTOR character — middle-aged anthropomorphic red-apple-headed "
        "man (mid-40s), shiny red apple-shaped head with a small green leaf, "
        "round glasses, serious composed eyes, clean-shaven, "
        "wearing a crisp white doctor's coat over a blue shirt, "
        "stethoscope around neck, professional grim expression"
    ),
    "neighbor": (
        "the MANGO NEIGHBOR character — middle-aged anthropomorphic mango-headed "
        "man (early 50s), orange-yellow mango-shaped head, "
        "smug confident eyes, well-groomed, "
        "wearing a beige traditional dishdasha and gold watch, "
        "indifferent dismissive expression"
    ),
    "grandmother": (
        "the LEMON GRANDMOTHER character — elderly anthropomorphic lemon-headed "
        "woman (mid-70s), pale yellow wrinkled lemon-shaped head, "
        "kind sad eyes, white hair under a black headscarf, "
        "wearing a long dark dress with prayer beads in hand, "
        "gentle frail expression"
    ),
    "wife": (
        "the PEACH WIFE character — young adult anthropomorphic peach-headed "
        "woman (mid-20s), soft pink-orange peach-shaped head, "
        "anxious worried brown eyes, "
        "wearing a beige hijab and pale rose-colored dress, "
        "concerned tired expression"
    ),
    "daughter": (
        "the CHERRY DAUGHTER character — small child anthropomorphic cherry-headed "
        "girl (around 6 years old), red round cherry-shaped head with green stem hair, "
        "big innocent dark eyes, "
        "wearing a simple white dress with red details, "
        "frightened or confused expression"
    ),
    "friend": (
        "the BLUEBERRY FRIEND character — young adult anthropomorphic blueberry-headed "
        "man (early 20s, same age as the strawberry son), deep blue blueberry-shaped "
        "head with a small green leaf, kind dark eyes, "
        "wearing a navy blue tunic with leather straps, "
        "loyal warm expression "
        "(NEVER the same fruit as the son — always blueberry, distinct from him)"
    ),
    "enemy": (
        "the DARK GRAPE ENEMY soldier — anthropomorphic dark-purple grape-headed warrior, "
        "menacing glowing red eyes, sharp jagged scar across the face, "
        "wearing black scaled armor with spiked shoulders, "
        "cruel smirking expression, deeper raspy voice"
    ),
    "shadow": (
        "the SHADOW STRAWBERRY character — same young adult anthropomorphic "
        "strawberry-headed man (early 20s) as the regular son but corrupted "
        "by darkness: deep blood-red strawberry head with darker tones, "
        "glowing dark crimson eyes, swirling dark smoke around him, "
        "wearing tattered black robes, cold cruel smirk, deeper colder voice — "
        "this is the son's alter ego / inner darkness given form, NOT a different person"
    ),
}


def clip_seed(title: str, index: int) -> int:
    """Deterministic seed per (title, clip_index). Stable across runs."""
    h = hashlib.sha256(f"shorts::{title}::{index}".encode("utf-8")).hexdigest()
    return int(h[:8], 16)


def build_veo_prompt(
    beat: Beat,
    global_setting: str,
    *,
    with_dialogue: bool = False,
    cast_negation: str = "",
) -> str:
    """Compose the final Veo prompt for one beat.

    `with_dialogue=True` enables Veo 3's native lip-synced dialogue: the
    Arabic line is quoted in the prompt with a speaking instruction, and
    Veo generates the speech audio + matching mouth movement in one pass.
    No separate TTS stage runs. Voice characteristics are set by Veo, not
    by an external voice ID — so stability across clips is approximate,
    not pinned to ElevenLabs.

    `cast_negation` (from pipeline.cast_guidance.veo_clip_negation) is
    prepended to the prompt when non-empty so Veo sees it at the earliest
    token positions — where it has the most weight. Empty string leaves the
    prompt unchanged (Sunstoriz / ai_choose paths).
    """
    head = f"{cast_negation} " if cast_negation else ""
    base = f"{head}{global_setting}, {beat.english_motion}"
    if with_dialogue and beat.arabic:
        if cast_negation:
            # Freeform non-fruit cast: do NOT inject the hardcoded fruit-character
            # SPEAKER_DESCRIPTIONS entries (those overpower the cast_negation and
            # cause Veo to render the legacy fruit anyway). Use the character's
            # Arabic name from the script + the speaker enum as a generic label,
            # and tell Veo to match the lineup sheet for visual identity.
            name = (beat.character_name or "").strip()
            if name:
                speaker_desc = (
                    f"the character named {name} (the {beat.speaker} role) — "
                    f"appearance MUST match this character as drawn in the supplied "
                    f"character lineup reference image"
                )
            else:
                speaker_desc = (
                    f"the {beat.speaker} character — appearance MUST match this "
                    f"character as drawn in the supplied character lineup reference image"
                )
        else:
            # Sunstoriz / AI Write mode: keep the existing rich fruit-character map.
            speaker_desc = SPEAKER_DESCRIPTIONS.get(
                beat.speaker, "the speaking character"
            )
        # Stronger language lock — empirically Veo's TTS sometimes ignores
        # "speaks Syrian Arabic" and renders the line in English. The prompt
        # is mostly English (visuals, character desc), so the model can
        # default to English audio. We now (a) explicitly forbid English,
        # (b) re-state the language in Arabic itself (يجب أن يكون النطق
        # بالعربية), and (c) put the Arabic line in quotes adjacent to a
        # final reminder.
        base += (
            f". {speaker_desc} faces the camera at medium close-up, "
            f"mouth open mid-speech with realistic synchronized lip movement. "
            f"⚠️ AUDIO LANGUAGE LOCK: the spoken voice MUST be in ARABIC, "
            f"specifically Syrian / Levantine dialect (شامي / سوري, as "
            f"spoken in Damascus and Aleppo). "
            f"يجب أن يكون النطق باللغة العربية فقط، باللهجة الشامية، "
            f"وممنوع النطق بالإنجليزية أو أي لغة أخرى. "
            f"Use natural Syrian markers: عم / شو / كتير / بدي / ليش / "
            f"هلق / متل / ولا / منيح / تا / لإلي / يلي. "
            f"Voice MUST NOT be in: ENGLISH, Modern Standard Arabic / فصحى, "
            f"Egyptian / مصري, Gulf / خليجي, Iraqi / عراقي, Maghrebi / مغربي, "
            f"or any non-Arabic language. "
            f"The exact spoken line (in Arabic) is: \"{beat.arabic}\". "
            f"Repeat: spoken in Arabic, Syrian dialect, never English."
        )
    return f"{base}, {VIDEO_STYLE_SUFFIX}"


class BudgetExceededError(RuntimeError):
    """Raised before any API call when projected spend exceeds the cap."""


def estimate_spend_usd(num_clips: int, clip_duration_s: int, cost_per_sec: float) -> float:
    return num_clips * clip_duration_s * cost_per_sec


def _clip_filename(clips_dir: Path, index: int) -> Path:
    return clips_dir / f"{index:02d}.mp4"


def _record_spend(spend_path: Path, entries: list[dict]) -> None:
    spend_path.parent.mkdir(parents=True, exist_ok=True)
    spend_path.write_text(
        json.dumps({"entries": entries, "ts": datetime.now().isoformat(timespec="seconds")},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def generate_clips(
    client: KieClient,
    script: Script,
    clips_dir: Path,
    spend_log_path: Path,
    *,
    model: str,
    clip_duration_s: int,
    aspect_ratio: str,
    cost_per_second_usd: float,
    max_spend_usd: float,
    poll_interval_s: int,
    poll_timeout_s: int,
    reroll_indices: list[int] | None = None,
    character_template: str | None = None,
) -> None:
    """Render each beat to clips_dir/NN.mp4. Resumable + reroll-aware.

    Budget guard: refuses to start the run if projected spend exceeds max_spend_usd.
    A reroll only re-spends for the rerolled clips, so the guard uses the count
    of clips that would actually be (re)generated this run, not all of them.
    """
    if not script.beats:
        raise ValueError("script has no beats — Shorts mode requires beats[]")

    clips_dir.mkdir(parents=True, exist_ok=True)
    reroll_set = set(reroll_indices or [])

    # Determine which clips actually need to (re)generate this run.
    pending: list[int] = []
    for i, _beat in enumerate(script.beats):
        idx = i + 1
        out_path = _clip_filename(clips_dir, idx)
        already_done = out_path.exists() and idx not in reroll_set
        if not already_done:
            pending.append(idx)

    projected = estimate_spend_usd(len(pending), clip_duration_s, cost_per_second_usd)
    if projected > max_spend_usd:
        raise BudgetExceededError(
            f"projected spend ${projected:.2f} exceeds cap ${max_spend_usd:.2f} "
            f"({len(pending)} clips × {clip_duration_s}s × ${cost_per_second_usd}/s). "
            f"Override with --max-spend or change config.kie.max_spend_usd."
        )

    from pipeline.cast_guidance import veo_clip_negation
    cast_negation = veo_clip_negation(character_template)

    spend_entries: list[dict] = []
    for i, beat in enumerate(script.beats):
        idx = i + 1
        out_path = _clip_filename(clips_dir, idx)
        if idx not in pending:
            continue  # already on disk, skip

        seed = clip_seed(script.title, i)
        if idx in reroll_set:
            seed += REROLL_SEED_BUMP

        prompt = build_veo_prompt(beat, script.global_setting, cast_negation=cast_negation)
        generate_clip(
            client=client,
            prompt=prompt,
            model=model,
            duration_s=clip_duration_s,
            aspect_ratio=aspect_ratio,
            seed=seed,
            out_path=out_path,
            negative_prompt=VIDEO_NEGATIVE_PROMPT,
            poll_interval_s=poll_interval_s,
            timeout_s=poll_timeout_s,
        )
        spend_entries.append({
            "clip": idx,
            "seed": seed,
            "duration_s": clip_duration_s,
            "cost_usd": clip_duration_s * cost_per_second_usd,
            "model": model,
        })

    if spend_entries:
        _record_spend(spend_log_path, spend_entries)


def _extract_last_frame(clip_path: Path, out_path: Path) -> None:
    """Indirection over pipeline.frames.extract_last_frame for monkeypatching."""
    from pipeline.frames import extract_last_frame
    extract_last_frame(clip_path, out_path)


_UPLOAD_TIMEOUT_S = 180  # uguu.se can be slow for ~1MB images
_UPLOAD_MAX_RETRIES = 4
_UPLOAD_BACKOFFS_S = (3, 10, 30, 60)


def _upload_image_get_url(local_path: Path) -> str:
    """Upload a local image to uguu.se (free, anonymous, 24h retention) and
    return the public URL so Kie.ai's Veo can fetch it.

    Files stay for 24 hours; we only need them for a few minutes (one Veo
    job), so this fits. 0x0.st was the previous choice but is currently
    disabled ("AI botnet spam"); uguu.se is the de-facto replacement.

    Retries on read-timeout and connection errors — uguu.se has been
    intermittently slow during this project, and a single 60s timeout
    aborts a run that's already several dollars deep into Veo. Tests
    monkeypatch this function.
    """
    last_exc: Exception | None = None
    for attempt in range(_UPLOAD_MAX_RETRIES):
        try:
            with local_path.open("rb") as f:
                resp = requests.post(
                    "https://uguu.se/upload",
                    files={"files[]": (local_path.name, f, "image/png")},
                    headers={"User-Agent": "Mozilla/5.0 (faceless-pipeline)"},
                    timeout=_UPLOAD_TIMEOUT_S,
                )
            if resp.status_code >= 400:
                raise RuntimeError(
                    f"uguu.se upload failed: {resp.status_code}: {resp.text[:200]}"
                )
            data = resp.json()
            if not data.get("success") or not data.get("files"):
                raise RuntimeError(f"uguu.se upload returned no url: {data}")
            return str(data["files"][0]["url"])
        except (requests.exceptions.Timeout,
                requests.exceptions.ConnectionError,
                RuntimeError) as e:
            last_exc = e
            if attempt < _UPLOAD_MAX_RETRIES - 1:
                wait = _UPLOAD_BACKOFFS_S[attempt]
                print(f"[upload] uguu.se retry {attempt+1}/{_UPLOAD_MAX_RETRIES} "
                      f"after {wait}s ({type(e).__name__}: {e})")
                import time
                time.sleep(wait)
    raise RuntimeError(
        f"uguu.se upload failed after {_UPLOAD_MAX_RETRIES} attempts: {last_exc}"
    )


def generate_clips_chained(
    client: KieClient,
    script: Script,
    clips_dir: Path,
    last_frames_dir: Path,
    spend_log_path: Path,
    *,
    character_sheet_path: Path,
    model: str,
    aspect_ratio: str,
    cost_per_second_usd: float,
    max_spend_usd: float,
    poll_interval_s: int,
    poll_timeout_s: int,
    reroll_indices: list[int] | None = None,
    with_dialogue: bool = False,
    character_template: str | None = None,
) -> None:
    """Tier-3 video stage: REFERENCE_2_VIDEO with character sheet + chained last frames.

    For clip 1: image_urls = [character_sheet]
    For clip N (N>1): image_urls = [character_sheet, last_frame_of_clip_(N-1)]

    Per-beat clip duration from `beat.clip_duration_s`.
    """
    if not script.beats:
        raise ValueError("script has no beats — Tier-3 mode requires beats[]")
    clips_dir.mkdir(parents=True, exist_ok=True)
    last_frames_dir.mkdir(parents=True, exist_ok=True)

    reroll_set = set(reroll_indices or [])

    pending_durations: list[float] = []
    for i, beat in enumerate(script.beats):
        idx = i + 1
        out_path = _clip_filename(clips_dir, idx)
        if not (out_path.exists() and idx not in reroll_set):
            pending_durations.append(beat.clip_duration_s)

    projected = sum(pending_durations) * cost_per_second_usd
    if projected > max_spend_usd:
        raise BudgetExceededError(
            f"projected spend ${projected:.2f} exceeds cap ${max_spend_usd:.2f} "
            f"({len(pending_durations)} clips × ${cost_per_second_usd}/s). "
            f"Override with --max-spend or change config.kie.max_spend_usd."
        )

    from pipeline.cast_guidance import veo_clip_negation
    cast_negation = veo_clip_negation(character_template)

    sheet_url = _upload_image_get_url(character_sheet_path)
    spend_entries: list[dict] = []
    prev_last_frame_url: str | None = None

    for i, beat in enumerate(script.beats):
        idx = i + 1
        out_path = _clip_filename(clips_dir, idx)
        last_frame_path = last_frames_dir / f"{idx:02d}.png"
        if out_path.exists() and idx not in reroll_set:
            # Already done; still need to ensure last-frame is on disk for next iteration.
            if not last_frame_path.exists():
                _extract_last_frame(out_path, last_frame_path)
            prev_last_frame_url = _upload_image_get_url(last_frame_path)
            continue

        prompt = build_veo_prompt(
            beat, script.global_setting,
            with_dialogue=with_dialogue,
            cast_negation=cast_negation,
        )
        image_urls = [sheet_url]
        if prev_last_frame_url:
            image_urls.append(prev_last_frame_url)

        job_id = client.submit_video_job(
            prompt=prompt,
            model=model,
            aspect_ratio=aspect_ratio,
            generation_type="REFERENCE_2_VIDEO",
            image_urls=image_urls,
            duration_s=beat.clip_duration_s,
        )
        url = client.wait_for_video(
            job_id, poll_interval_s=poll_interval_s, timeout_s=poll_timeout_s,
        )
        client.download(url, out_path)
        # Move moov atom to the front so HTML5 players can stream progressively
        # instead of waiting for the full file. Silent no-op on failure.
        from pipeline.mp4_faststart import rewrite_with_faststart
        rewrite_with_faststart(out_path)
        _extract_last_frame(out_path, last_frame_path)
        prev_last_frame_url = _upload_image_get_url(last_frame_path)

        spend_entries.append({
            "clip": idx, "seed": clip_seed(script.title, i),
            "duration_s": beat.clip_duration_s,
            "cost_usd": beat.clip_duration_s * cost_per_second_usd,
            "model": model,
        })

    if spend_entries:
        _record_spend(spend_log_path, spend_entries)
