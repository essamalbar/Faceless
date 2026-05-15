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
import math
from datetime import datetime
from pathlib import Path

import requests

from pipeline import credits as _credits
from pipeline.auth import User as _User
from pipeline.kie import KieClient, generate_clip, submit_and_wait_with_retry
from pipeline.types import Beat, Script


def _charge_and_submit_clip(
    *,
    user: "_User",
    run_id: str,
    beat,
    clip_index: int,
    submit_fn,
):
    """Deduct 1 credit, submit the clip, refund on failure.

    Pricing (locked 2026-05-13): 1 credit = 1 clip regardless of duration.
    `beat` accepted as dataclass or dict for test-friendliness.

    `submit_fn(beat, *, clip_index)` is the actual generation submission —
    passed in so this function is independently testable. Raises propagate
    after a refund is recorded.
    """
    # Resolve via the module so pytest monkeypatch.setattr("pipeline.credits.X")
    # is honored both from tests and from production callers.
    _credits.check_or_deduct(
        user,
        amount=1,
        run_id=run_id,
        reason=f"clip {clip_index + 1}",
    )
    try:
        return submit_fn(beat, clip_index=clip_index)
    except Exception as submit_exc:
        # Refund is best-effort — if THIS call also raises (DB down,
        # Supabase 5xx, etc.) we still want the original failure to
        # surface so the run is marked failed properly. But we leave
        # a paper trail so admin can credit the user manually.
        try:
            _credits.refund(
                user,
                amount=1,
                run_id=run_id,
                reason=f"clip {clip_index + 1} failed",
            )
        except Exception as refund_exc:
            import logging
            logging.error(
                "REFUND FAILED user=%s run=%s clip=%s submit_err=%s refund_err=%s. "
                "Manual credit return required.",
                getattr(user, "id", "?"),
                run_id,
                clip_index + 1,
                type(submit_exc).__name__,
                f"{type(refund_exc).__name__}: {refund_exc}",
            )
        raise

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

# SPEAKER_DESCRIPTIONS was removed in PA-1. Character identity is now provided
# exclusively via beat.character_name. See commit "refactor(speaker): drop
# SPEAKER_DESCRIPTIONS + free-form speaker enum".


def clip_seed(title: str, index: int) -> int:
    """Deterministic seed per (title, clip_index). Stable across runs."""
    h = hashlib.sha256(f"shorts::{title}::{index}".encode("utf-8")).hexdigest()
    return int(h[:8], 16)


# Default audio-lock per dialect — keep Syrian as the back-compat default.
_DIALECT_AUDIO_LOCK: dict[str, str] = {
    "syrian": (
        "Syrian / Levantine dialect (شامي / سوري, as spoken in Damascus and "
        "Aleppo). Use natural Syrian markers: عم / شو / كتير / بدي / ليش / "
        "هلق / متل / ولا / منيح / تا / لإلي / يلي. "
        "Voice MUST NOT be in: ENGLISH, Modern Standard Arabic / فصحى, "
        "Egyptian / مصري, Gulf / خليجي, Iraqi / عراقي, Maghrebi / مغربي, or "
        "any non-Arabic language."
    ),
    "egyptian": (
        "Egyptian dialect (مصري, as spoken in Cairo). Use natural Egyptian "
        "markers: ازاي / دلوقتي / مفيش / عايز / كده / يعني / فين / امبارح / بس / "
        "خالص / اوي. Voice MUST NOT be in: ENGLISH, Modern Standard Arabic / "
        "فصحى, Syrian / شامي, Gulf / خليجي, Iraqi / عراقي, Maghrebi / مغربي, "
        "or any non-Arabic language."
    ),
    "khaliji": (
        "Khaliji / Gulf dialect (خليجي, as spoken in Saudi Arabia / UAE). "
        "Use natural Khaliji markers: شلون / وايد / لي / تره / ابي / يبي / "
        "ها / مرة / حلو / يبه. Voice MUST NOT be in: ENGLISH, Modern "
        "Standard Arabic / فصحى, Syrian / شامي, Egyptian / مصري, Iraqi / "
        "عراقي, Maghrebi / مغربي, or any non-Arabic language."
    ),
    "maghrebi": (
        "Maghrebi / North-African dialect (مغربي, as spoken in Morocco / "
        "Algeria / Tunisia). Voice MUST NOT be in: ENGLISH, Modern Standard "
        "Arabic / فصحى, Syrian / شامي, Egyptian / مصري, Khaliji / خليجي, "
        "Iraqi / عراقي, or any non-Arabic language."
    ),
    "iraqi": (
        "Iraqi dialect (عراقي, as spoken in Baghdad). Use natural Iraqi "
        "markers: شلون / هسه / اكو / ماكو / ليش / شنو / هواية / كلش. Voice "
        "MUST NOT be in: ENGLISH, Modern Standard Arabic / فصحى, Syrian / "
        "شامي, Egyptian / مصري, Khaliji / خليجي, Maghrebi / مغربي, or any "
        "non-Arabic language."
    ),
    "msa": (
        "Modern Standard Arabic (الفصحى, MSA). Voice MUST NOT be in: ENGLISH, "
        "Syrian / شامي, Egyptian / مصري, Khaliji / خليجي, Iraqi / عراقي, "
        "Maghrebi / مغربي, or any non-Arabic language."
    ),
}


# Style-lock preambles prepended at the START of every Veo prompt so the
# visual style is enforced PER CLIP, not just hoped for via the LLM's
# global_setting text. Without this, runs with art_style=cinematic_photo_real
# would occasionally produce cartoon/illustration clips in the middle of an
# otherwise photoreal set (real user-reported regression).
_STYLE_LOCKS: dict[str, str] = {
    "cinematic_photo_real": (
        "STYLE LOCK: live-action cinematic photo-real footage, real human actors, "
        "realistic skin, hair, fabric, lighting, depth of field. "
        "Absolutely NOT animation, NOT cartoon, NOT illustration, NOT 3D-rendered, "
        "NOT anime. Treat as documentary-grade footage."
    ),
    "pixar_3d": (
        "STYLE LOCK: Pixar-style 3D animation, glossy CGI characters, stylized "
        "lighting, polished render. NOT live-action, NOT photoreal, NOT anime."
    ),
    "anime_2d": (
        "STYLE LOCK: 2D anime cel-shaded animation, hand-drawn line art, flat "
        "colour fills with cel highlights. NOT live-action, NOT 3D, NOT photoreal."
    ),
    "claymation": (
        "STYLE LOCK: claymation stop-motion, visible clay texture and seams, "
        "tactile handmade lighting. NOT live-action, NOT photoreal, NOT CGI."
    ),
    "hand_drawn": (
        "STYLE LOCK: hand-drawn 2D animation, visible brush/pencil strokes, "
        "painterly textures. NOT live-action, NOT 3D, NOT photoreal."
    ),
    "ghibli": (
        "STYLE LOCK: Studio Ghibli watercolour anime, soft pastel palette, "
        "hand-painted backgrounds, expressive 2D characters. NOT live-action, NOT 3D."
    ),
}


def build_veo_prompt(
    beat: Beat,
    global_setting: str,
    *,
    with_dialogue: bool = False,
    cast_negation: str = "",
    dialect: str | None = None,
    character_descriptions: dict[str, str] | None = None,
    art_style: str | None = None,
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

    `dialect` selects which entry from `_DIALECT_AUDIO_LOCK` is injected
    into the audio-lock clause. Defaults to "syrian" for back-compat.

    `character_descriptions` maps Arabic character_name → short English
    physical description. When non-empty, the descriptions for any character
    that appears in this beat (the speaker + any name found in english_motion)
    are prepended as a preamble so Veo locks identity visually across clips.
    Empty dict (or None) → no preamble, fully backwards-compatible.
    """
    descs = character_descriptions or {}

    def _physical_only(desc: str) -> str:
        """Return the physical part of a description, stripping any voice section.

        Descriptions may include '; voice: ...' or ', voice: ...' suffix added
        in PE-2. The visual preamble only needs the physical appearance part so
        that voice-specific text does not appear before the audio-lock block
        (which is where Veo should read voice guidance).
        """
        for sep in ("; voice:", ", voice:", ";voice:", ",voice:"):
            idx = desc.lower().find(sep)
            if idx != -1:
                return desc[:idx].strip()
        return desc

    # Determine which characters appear in this beat:
    #   1. The speaking character (beat.character_name)
    #   2. Any character_name found by substring match in english_motion
    active: list[tuple[str, str]] = []
    seen: set[str] = set()
    speaker_name = (beat.character_name or "").strip()
    if speaker_name and speaker_name in descs:
        active.append((speaker_name, descs[speaker_name]))
        seen.add(speaker_name)
    for name, desc in descs.items():
        if name in seen:
            continue
        if name and name in beat.english_motion:
            active.append((name, desc))
            seen.add(name)

    desc_preamble = ""
    if active:
        lines = "; ".join(f"{n}: {_physical_only(d)}" for n, d in active)
        desc_preamble = (
            f"Character physical descriptions (consistent across all clips, "
            f"MUST match the supplied character lineup): {lines}. "
        )

    # Style lock prepended FIRST — Veo weights early tokens highest, so
    # this is the single strongest place to pin the visual style.
    style_lock = _STYLE_LOCKS.get(art_style or "", "")
    style_prefix = f"{style_lock} " if style_lock else ""
    head = f"{cast_negation} " if cast_negation else ""
    base = f"{style_prefix}{head}{desc_preamble}{global_setting}, {beat.english_motion}"

    if with_dialogue:
        if beat.arabic:
            # Dialogue beat — character_name (per-script) is the primary identifier.
            name = (beat.character_name or "").strip()
            is_voice_over = (
                beat.speaker.strip().lower() == "narrator" and not name
            )

            dialect_key = (dialect or "syrian").lower()
            lock = _DIALECT_AUDIO_LOCK.get(dialect_key, _DIALECT_AUDIO_LOCK["syrian"])

            if is_voice_over:
                # Voice-over narration — audio yes, on-camera speaker no.
                # The visual is whatever english_motion described; do NOT add
                # frontal-MCU framing or speaker descriptor.
                voice_profile = ""
                narrator_desc = (descs.get("narrator") or "").strip()
                if narrator_desc:
                    voice_profile = (
                        f"Voice profile for the narrator (consistent across ALL "
                        f"voice-over beats in this video — same voice every time): "
                        f"{narrator_desc}. "
                    )
                base += (
                    ". This beat is a VOICE-OVER narration: an off-screen narrator "
                    "speaks the line below over the visual described above. NO "
                    "on-screen character speaks; NO mouth movement; NO close-up "
                    "of a speaker. The narrator is heard but not seen — the "
                    "visual stays exactly as described in the shot direction. "
                    f"⚠️ AUDIO LANGUAGE LOCK: the narrator's voice MUST be in "
                    f"ARABIC. {lock} "
                    f"يجب أن يكون النطق باللغة العربية فقط، وممنوع النطق "
                    f"بالإنجليزية أو أي لغة أخرى. "
                    f"{voice_profile}"
                    f"The exact narration line (in Arabic) is: \"{beat.arabic}\". "
                    f"Final reminder: narrator audio MUST be in Arabic, never "
                    f"English; visual is the shot described above, NOT a "
                    f"close-up of a speaker."
                )
            else:
                # On-camera dialogue — character_name is the primary identifier.
                if name:
                    speaker_desc = (
                        f"the character named {name} — appearance MUST match "
                        f"this character as drawn in the supplied character "
                        f"lineup reference image"
                    )
                else:
                    # Legacy script with no character_name. Fall back to a generic
                    # speaker label — no fruit-cast injection. This means older
                    # Sunstoriz scripts will look slightly different but won't have
                    # the cross-cast fruit leak that SPEAKER_DESCRIPTIONS caused.
                    speaker_desc = f"the {beat.speaker or 'speaking'} character"

                voice_profile = ""
                if name:
                    char_desc = (descs.get(name) or "").strip()
                    if char_desc:
                        voice_profile = (
                            f"Voice profile for this character (consistent across ALL "
                            f"clips where {name} speaks — same voice every time): "
                            f"{char_desc}. "
                        )
                base += (
                    f". {speaker_desc} faces the camera at medium close-up, "
                    f"mouth open mid-speech with realistic synchronized lip movement. "
                    f"⚠️ AUDIO LANGUAGE LOCK: the spoken voice MUST be in ARABIC. "
                    f"{lock} "
                    f"يجب أن يكون النطق باللغة العربية فقط، وممنوع النطق "
                    f"بالإنجليزية أو أي لغة أخرى. "
                    f"{voice_profile}"
                    f"The exact spoken line (in Arabic) is: \"{beat.arabic}\". "
                    f"Final reminder: dialogue audio MUST be in Arabic, never "
                    f"English or any other language."
                )
        else:
            # Silent / atmospheric beat — explicitly block Veo from inventing
            # English narration / voice-over.
            base += (
                ". This is a SILENT atmospheric beat: NO spoken dialogue, "
                "NO voice-over, NO narration in any language. Only ambient "
                "environmental sound and music. The characters MUST NOT "
                "speak. No mouth movement implying speech. No English "
                "narration."
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
    dialect: str | None = None,
    character_descriptions: dict[str, str] | None = None,
    art_style: str | None = None,
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

        prompt = build_veo_prompt(
            beat, script.global_setting,
            cast_negation=cast_negation,
            dialect=dialect,
            character_descriptions=character_descriptions,
            art_style=art_style,
        )
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
    dialect: str | None = None,
    character_descriptions: dict[str, str] | None = None,
    art_style: str | None = None,
    user: "_User | None" = None,
    run_id: str = "",
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
            dialect=dialect,
            character_descriptions=character_descriptions,
            art_style=art_style,
        )
        image_urls = [sheet_url]
        if prev_last_frame_url:
            image_urls.append(prev_last_frame_url)

        if user is not None:
            def _do_submit(b, *, clip_index):
                return submit_and_wait_with_retry(
                    client,
                    submit_kwargs={
                        "prompt": prompt,
                        "model": model,
                        "aspect_ratio": aspect_ratio,
                        "generation_type": "REFERENCE_2_VIDEO",
                        "image_urls": image_urls,
                        "duration_s": b.clip_duration_s,
                    },
                    poll_interval_s=poll_interval_s,
                    timeout_s=poll_timeout_s,
                )
            url = _charge_and_submit_clip(
                user=user, run_id=run_id, beat=beat, clip_index=i,
                submit_fn=_do_submit,
            )
        else:
            # Legacy path — no credit accounting (used by CLI without --user-id
            # when run.py doesn't pass user= to keep backwards compat).
            url = submit_and_wait_with_retry(
                client,
                submit_kwargs={
                    "prompt": prompt,
                    "model": model,
                    "aspect_ratio": aspect_ratio,
                    "generation_type": "REFERENCE_2_VIDEO",
                    "image_urls": image_urls,
                    "duration_s": beat.clip_duration_s,
                },
                poll_interval_s=poll_interval_s,
                timeout_s=poll_timeout_s,
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
