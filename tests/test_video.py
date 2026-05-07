"""Video clip generator tests. Kie.ai is replaced via monkeypatch."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline import video as video_mod
from pipeline.kie import KieClient
from pipeline.types import Beat, Script
from pipeline.video import (
    BudgetExceededError,
    REROLL_SEED_BUMP,
    build_veo_prompt,
    clip_seed,
    estimate_spend_usd,
    generate_clips,
)


def _script(num_beats: int = 4) -> Script:
    return Script(
        title="بئر",
        theme="folkloric",
        global_setting="abandoned village, night, desert",
        music_mood="dread",
        beats=tuple(
            Beat(arabic=f"ج{i+1}", english_motion=f"motion{i+1}, push-in")
            for i in range(num_beats)
        ),
        story_combined=" ".join(f"ج{i+1}" for i in range(num_beats)),
    )


def _client() -> KieClient:
    return KieClient(api_key="k", base_url="https://api.kie.ai")


def _patch_generate_clip(monkeypatch, fixtures_dir: Path):
    """Replace pipeline.video.generate_clip with a stub that writes a tiny mp4."""
    sample = (fixtures_dir / "narration_sample.mp3").read_bytes()  # any small file
    calls: list[dict] = []

    def fake(client, prompt, model, duration_s, aspect_ratio, seed, out_path,
             negative_prompt, poll_interval_s, timeout_s):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"\x00\x00\x00\x18ftypmp42")  # mp4 magic prefix
        calls.append({
            "prompt": prompt, "model": model, "seed": seed,
            "duration_s": duration_s, "aspect_ratio": aspect_ratio,
            "out_path": str(out_path),
        })

    monkeypatch.setattr(video_mod, "generate_clip", fake)
    return calls


def test_estimate_spend_math():
    assert estimate_spend_usd(4, 7, 0.10) == pytest.approx(2.80)
    assert estimate_spend_usd(0, 7, 0.10) == 0
    assert estimate_spend_usd(4, 8, 0.50) == 16.0


def test_clip_seed_deterministic_per_title():
    s1 = clip_seed("title-A", 0)
    s2 = clip_seed("title-A", 0)
    s3 = clip_seed("title-A", 1)
    s4 = clip_seed("title-B", 0)
    assert s1 == s2
    assert s1 != s3
    assert s1 != s4


def test_build_veo_prompt_combines_setting_and_motion():
    b = Beat(arabic="x", english_motion="lone hooded figure, moonlight")
    p = build_veo_prompt(b, global_setting="abandoned village at night")
    assert "abandoned village at night" in p
    assert "lone hooded figure" in p
    # Style suffix appended (3D Pixar fruit-character for @sunstoriz-style TikTok)
    assert "3D Pixar" in p
    assert "anthropomorphic fruit characters" in p


def test_build_veo_prompt_silent_default_omits_dialogue():
    """Default (with_dialogue=False) — Arabic line is NOT in the prompt;
    Veo will produce silent video and an external TTS supplies the voice."""
    b = Beat(arabic="أنا قلبي مكسور", english_motion="m", speaker="mother")
    p = build_veo_prompt(b, global_setting="g")
    assert "أنا قلبي مكسور" not in p
    assert "speaks emotionally" not in p


def test_build_veo_prompt_with_dialogue_quotes_arabic_and_names_speaker():
    """Tier-4 native-audio path: dialogue line appears inside double-quotes
    with a speaker description, so Veo 3 generates lip-synced speech."""
    b = Beat(arabic="أنا قلبي مكسور", english_motion="m", speaker="mother",
             character_name="أم خالد")
    p = build_veo_prompt(b, global_setting="g", with_dialogue=True)
    assert '"أنا قلبي مكسور"' in p           # exact quoting matters for Veo
    assert "أم خالد" in p                     # character_name used (no fruit desc)
    assert "synchronized lip movement" in p
    assert "Syrian" in p
    # Audio-language lock — the prompt explicitly forbids English plus the
    # other Arabic dialects so Veo's TTS doesn't default to English.
    assert "ENGLISH" in p                       # explicit "NOT in ENGLISH"
    assert "ممنوع النطق بالإنجليزية" in p       # Arabic-side directive
    assert "Modern Standard Arabic" in p
    assert "Egyptian" in p and "Gulf" in p


def test_build_veo_prompt_with_dialogue_unknown_speaker_falls_back():
    """Unknown speaker labels still produce a usable prompt — Veo gets
    a generic 'the {speaker} character' label instead of failing."""
    b = Beat(arabic="ج", english_motion="m", speaker="auntie",
             character_name="")  # no character_name → generic fallback
    p = build_veo_prompt(b, global_setting="g", with_dialogue=True)
    # PA-1: generic fallback is "the {speaker} character", not SPEAKER_DESCRIPTIONS
    assert "the auntie character" in p
    assert '"ج"' in p


def test_generate_all_clips(monkeypatch, tmp_path: Path, fixtures_dir: Path):
    calls = _patch_generate_clip(monkeypatch, fixtures_dir)
    clips_dir = tmp_path / "clips"
    spend = tmp_path / "kie_spend.json"
    generate_clips(
        client=_client(), script=_script(4),
        clips_dir=clips_dir, spend_log_path=spend,
        model="veo-3.1-fast", clip_duration_s=7, aspect_ratio="9:16",
        cost_per_second_usd=0.10, max_spend_usd=5.0,
        poll_interval_s=1, poll_timeout_s=10,
    )
    for i in range(1, 5):
        assert (clips_dir / f"{i:02d}.mp4").exists()
    assert len(calls) == 4
    # Spend log records 4 entries × 7s × $0.10 = $2.80 total
    spend_data = json.loads(spend.read_text())
    assert len(spend_data["entries"]) == 4
    total = sum(e["cost_usd"] for e in spend_data["entries"])
    assert total == pytest.approx(2.80)


def test_skips_existing_clips(monkeypatch, tmp_path: Path, fixtures_dir: Path):
    calls = _patch_generate_clip(monkeypatch, fixtures_dir)
    clips_dir = tmp_path / "clips"
    clips_dir.mkdir()
    (clips_dir / "01.mp4").write_bytes(b"existing")
    (clips_dir / "02.mp4").write_bytes(b"existing")
    generate_clips(
        client=_client(), script=_script(4),
        clips_dir=clips_dir, spend_log_path=tmp_path / "spend.json",
        model="m", clip_duration_s=7, aspect_ratio="9:16",
        cost_per_second_usd=0.10, max_spend_usd=5.0,
        poll_interval_s=1, poll_timeout_s=10,
    )
    # Only 03 and 04 should be (re)generated
    assert len(calls) == 2


def test_reroll_regenerates_with_bumped_seed(monkeypatch, tmp_path: Path, fixtures_dir: Path):
    calls = _patch_generate_clip(monkeypatch, fixtures_dir)
    clips_dir = tmp_path / "clips"
    clips_dir.mkdir()
    for i in range(1, 5):
        (clips_dir / f"{i:02d}.mp4").write_bytes(b"existing")

    generate_clips(
        client=_client(), script=_script(4),
        clips_dir=clips_dir, spend_log_path=tmp_path / "spend.json",
        model="m", clip_duration_s=7, aspect_ratio="9:16",
        cost_per_second_usd=0.10, max_spend_usd=5.0,
        poll_interval_s=1, poll_timeout_s=10,
        reroll_indices=[2],
    )
    assert len(calls) == 1
    # Rerolled seed should be the original seed + REROLL_SEED_BUMP
    expected = clip_seed(_script().title, 1) + REROLL_SEED_BUMP  # 0-based index 1 = clip 2
    assert calls[0]["seed"] == expected


def test_budget_guard_refuses_when_over_cap(monkeypatch, tmp_path: Path, fixtures_dir: Path):
    _patch_generate_clip(monkeypatch, fixtures_dir)
    clips_dir = tmp_path / "clips"
    # 4 clips × 7s × $0.50 = $14 > $5 cap → must raise BEFORE any API call
    with pytest.raises(BudgetExceededError, match=r"projected spend \$14"):
        generate_clips(
            client=_client(), script=_script(4),
            clips_dir=clips_dir, spend_log_path=tmp_path / "spend.json",
            model="m", clip_duration_s=7, aspect_ratio="9:16",
            cost_per_second_usd=0.50, max_spend_usd=5.0,
            poll_interval_s=1, poll_timeout_s=10,
        )


def test_budget_guard_uses_only_pending_clips(monkeypatch, tmp_path: Path, fixtures_dir: Path):
    """Budget projects spend for clips that actually need (re)generation, not all clips."""
    _patch_generate_clip(monkeypatch, fixtures_dir)
    clips_dir = tmp_path / "clips"
    clips_dir.mkdir()
    # 3 of 4 clips already done — only 1 will be generated → $0.70 < cap
    for i in (1, 2, 3):
        (clips_dir / f"{i:02d}.mp4").write_bytes(b"existing")
    generate_clips(
        client=_client(), script=_script(4),
        clips_dir=clips_dir, spend_log_path=tmp_path / "spend.json",
        model="m", clip_duration_s=7, aspect_ratio="9:16",
        cost_per_second_usd=0.10, max_spend_usd=1.0,  # 1 clip = $0.70 ok
        poll_interval_s=1, poll_timeout_s=10,
    )


def test_raises_on_empty_beats(tmp_path: Path):
    s = Script(
        title="x", theme="folkloric", global_setting="x",
        music_mood="dread", beats=(),
    )
    with pytest.raises(ValueError, match="no beats"):
        generate_clips(
            client=_client(), script=s,
            clips_dir=tmp_path / "clips", spend_log_path=tmp_path / "s.json",
            model="m", clip_duration_s=7, aspect_ratio="9:16",
            cost_per_second_usd=0.10, max_spend_usd=5.0,
            poll_interval_s=1, poll_timeout_s=10,
        )


def test_generate_clips_uses_reference_2_video_with_character_sheet(
    monkeypatch, tmp_path: Path, fixtures_dir: Path,
):
    """Each clip must be submitted as REFERENCE_2_VIDEO with character_sheet in image_urls."""
    submit_calls: list[dict] = []

    def fake_submit(self, **kw):
        submit_calls.append(kw)
        return f"task_{len(submit_calls)}"

    monkeypatch.setattr(KieClient, "submit_video_job", fake_submit)
    monkeypatch.setattr(KieClient, "wait_for_video",
                        lambda self, jid, **kw: f"https://cdn/{jid}.mp4")

    def fake_dl(self, url, out_path):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"\x00\x00\x00\x18ftypmp42")

    monkeypatch.setattr(KieClient, "_download", fake_dl)
    monkeypatch.setattr("pipeline.video._extract_last_frame",
                        lambda clip, out: out.write_bytes(b"\x89PNG\r\n\x1a\n"))
    monkeypatch.setattr("pipeline.video._upload_image_get_url",
                        lambda path: f"https://cdn/upl/{path.name}")

    clips_dir = tmp_path / "clips"
    last_frames_dir = tmp_path / "last_frames"
    spend = tmp_path / "spend.json"
    char_sheet = tmp_path / "character_sheet.png"
    char_sheet.write_bytes(b"\x89PNG\r\n\x1a\n")

    from pipeline.video import generate_clips_chained
    generate_clips_chained(
        client=KieClient(api_key="k"),
        script=_script(3),
        clips_dir=clips_dir, last_frames_dir=last_frames_dir,
        spend_log_path=spend,
        character_sheet_path=char_sheet,
        model="veo3", aspect_ratio="9:16",
        cost_per_second_usd=0.40, max_spend_usd=20.0,
        poll_interval_s=1, poll_timeout_s=10,
    )
    # 3 clips submitted
    assert len(submit_calls) == 3
    # Every submit has REFERENCE_2_VIDEO
    for call in submit_calls:
        assert call["generation_type"] == "REFERENCE_2_VIDEO"
        # Character sheet always in image_urls
        assert any("character_sheet" in u or "/upl/" in u for u in call["image_urls"])
    # Clips 2 and 3 also reference last frame of previous
    assert len(submit_calls[1]["image_urls"]) >= 2
    assert len(submit_calls[2]["image_urls"]) >= 2


def test_build_veo_prompt_no_cast_negation_unchanged():
    from pipeline.video import build_veo_prompt
    from pipeline.types import Beat
    b = Beat(arabic="x", english_motion="wide shot", clip_duration_s=8.0,
             speaker="mother")
    p = build_veo_prompt(b, "global setting")
    assert p.startswith("global setting,")


def test_build_veo_prompt_with_animal_cast_negation():
    from pipeline.video import build_veo_prompt
    from pipeline.cast_guidance import veo_clip_negation
    from pipeline.types import Beat
    b = Beat(arabic="x", english_motion="wide shot of fox in snow",
             clip_duration_s=8.0, speaker="mother")
    p = build_veo_prompt(
        b, "anthropomorphic animals in folkloric setting",
        cast_negation=veo_clip_negation("animal"),
    )
    p_lower = p.lower()
    assert p.startswith("Cast: anthropomorphic animal")
    assert "blueberries" in p_lower
    assert "wide shot of fox in snow" in p


def test_build_veo_prompt_fruit_sunstoriz_no_negation():
    from pipeline.video import build_veo_prompt
    from pipeline.cast_guidance import veo_clip_negation
    from pipeline.types import Beat
    b = Beat(arabic="x", english_motion="wide", clip_duration_s=8.0,
             speaker="mother")
    p = build_veo_prompt(b, "g", cast_negation=veo_clip_negation("fruit_sunstoriz"))
    assert p.startswith("g,")


def test_generate_clips_chained_uses_per_beat_duration(monkeypatch, tmp_path: Path):
    """duration_seconds passed to Veo must come from beat.clip_duration_s."""
    durations: list = []

    def fake_submit(self, **kw):
        durations.append(kw.get("duration_s"))
        return f"task_{len(durations)}"

    monkeypatch.setattr(KieClient, "submit_video_job", fake_submit)
    monkeypatch.setattr(KieClient, "wait_for_video",
                        lambda self, jid, **kw: f"https://cdn/{jid}.mp4")
    monkeypatch.setattr(KieClient, "_download",
                        lambda self, url, out: out.parent.mkdir(parents=True, exist_ok=True) or
                                                out.write_bytes(b"x"))
    monkeypatch.setattr("pipeline.video._extract_last_frame",
                        lambda clip, out: out.write_bytes(b"x"))
    monkeypatch.setattr("pipeline.video._upload_image_get_url",
                        lambda path: f"https://cdn/{path.name}")

    # Build a script whose beats have varying durations
    s = Script(
        title="t", theme="folkloric", global_setting="x", music_mood="dread",
        beats=(
            Beat(arabic="a", english_motion="m", clip_duration_s=6.0),
            Beat(arabic="b", english_motion="m", clip_duration_s=9.5),
        ),
        story_combined="a b",
        target_duration_s=15.5,
    )

    char_sheet = tmp_path / "cs.png"
    char_sheet.write_bytes(b"x")

    from pipeline.video import generate_clips_chained
    generate_clips_chained(
        client=KieClient(api_key="k"),
        script=s,
        clips_dir=tmp_path / "clips",
        last_frames_dir=tmp_path / "lf",
        spend_log_path=tmp_path / "s.json",
        character_sheet_path=char_sheet,
        model="veo3", aspect_ratio="9:16",
        cost_per_second_usd=0.40, max_spend_usd=20.0,
        poll_interval_s=1, poll_timeout_s=10,
    )
    assert durations == [6.0, 9.5]


def test_with_dialogue_freeform_animal_cast_strips_fruit_speaker_desc():
    """When cast_negation is non-empty (freeform animal/human/surreal),
    the per-beat Veo prompt MUST NOT include the hardcoded fruit
    SPEAKER_DESCRIPTIONS entry — that text overpowers the negation
    and Veo ends up rendering the fruit anyway."""
    from pipeline.video import build_veo_prompt
    from pipeline.cast_guidance import veo_clip_negation
    from pipeline.types import Beat

    b = Beat(
        arabic="يا إلهي! وين طلعتِ من؟",
        english_motion="over-the-shoulder shot, snow rabbit speaks",
        clip_duration_s=8.0,
        speaker="friend",            # SPEAKER_DESCRIPTIONS["friend"] = blueberry text
        character_name="سالم",
    )
    p = build_veo_prompt(
        b, "anthropomorphic animals in folkloric setting",
        with_dialogue=True,
        cast_negation=veo_clip_negation("animal"),
    )
    p_lower = p.lower()
    # Smoking-gun phrases — must be absent
    assert "blueberry" not in p_lower
    assert "blueberry-shaped head" not in p_lower
    # Sanity — negation IS still in the prompt
    assert "strictly not anthropomorphic fruit" in p_lower
    # Per-beat character_name should appear (so Veo identifies the
    # speaker as a specific character from the lineup)
    assert "سالم" in p


def test_with_dialogue_freeform_human_cast_strips_fruit_speaker_desc():
    from pipeline.video import build_veo_prompt
    from pipeline.cast_guidance import veo_clip_negation
    from pipeline.types import Beat
    b = Beat(
        arabic="ابني!",
        english_motion="medium close-up, mother speaks",
        clip_duration_s=8.0,
        speaker="mother",            # SPEAKER_DESCRIPTIONS["mother"] = lemon text
        character_name="أم خالد",
    )
    p = build_veo_prompt(
        b, "real human cast in urban setting",
        with_dialogue=True,
        cast_negation=veo_clip_negation("human"),
    )
    p_lower = p.lower()
    # "lemon" alone appears legitimately in the cast_negation ("no lemons") — the
    # smoking-gun fruit-character descriptions are the more specific phrases below.
    assert "lemon-shaped head" not in p_lower
    assert "yellow lemon" not in p_lower
    assert "lemon mother" not in p_lower   # SPEAKER_DESCRIPTIONS capitalized key phrase
    assert "أم خالد" in p


def test_with_dialogue_sunstoriz_no_fruit_leak_when_character_name_empty():
    """PA-1: Without cast_negation AND without a character_name, the prompt
    falls back to a generic speaker label — no fruit-cast injection."""
    from pipeline.video import build_veo_prompt
    from pipeline.types import Beat
    b = Beat(
        arabic="ابني...",
        english_motion="medium close-up, mother speaks",
        clip_duration_s=8.0,
        speaker="mother",
        character_name="",   # empty → generic fallback (no fruit)
    )
    p = build_veo_prompt(b, "global setting", with_dialogue=True)
    p_lower = p.lower()
    # PA-1: SPEAKER_DESCRIPTIONS removed — no fruit descriptions
    assert "lemon mother" not in p_lower
    assert "lemon-shaped head" not in p_lower
    # Generic fallback label appears instead
    assert "the mother" in p_lower


def test_with_dialogue_freeform_no_character_name_uses_speaker_label():
    """If the writer didn't fill character_name, fall back to the speaker
    enum label (no fruit mentions)."""
    from pipeline.video import build_veo_prompt
    from pipeline.cast_guidance import veo_clip_negation
    from pipeline.types import Beat
    b = Beat(
        arabic="x",
        english_motion="y",
        clip_duration_s=8.0,
        speaker="friend",
        character_name="",
    )
    p = build_veo_prompt(
        b, "g",
        with_dialogue=True,
        cast_negation=veo_clip_negation("animal"),
    )
    p_lower = p.lower()
    assert "blueberry" not in p_lower
    # The speaker enum label appears in some form
    assert "friend" in p_lower


def test_speaker_uses_character_name_in_sunstoriz_when_present():
    """Bug A: When character_name is set, it overrides SPEAKER_DESCRIPTIONS
    even in Sunstoriz mode (cast_negation='')."""
    from pipeline.video import build_veo_prompt
    from pipeline.types import Beat
    b = Beat(
        arabic="أنا فراولة وأنا غلطت",
        english_motion="OTS, strawberry speaks",
        clip_duration_s=8.0,
        speaker="friend",
        character_name="فراولة",
    )
    p = build_veo_prompt(b, "fruit village", with_dialogue=True)  # Sunstoriz path
    p_lower = p.lower()
    assert "blueberry" not in p_lower
    assert "blueberry-shaped head" not in p_lower
    assert "فراولة" in p


def test_legacy_sunstoriz_no_fruit_when_character_name_empty():
    """PA-1: When cast_negation='' AND character_name='', the old fruit
    SPEAKER_DESCRIPTIONS is no longer injected — a generic speaker label
    is used instead."""
    from pipeline.video import build_veo_prompt
    from pipeline.types import Beat
    b = Beat(
        arabic="x",
        english_motion="y",
        clip_duration_s=8.0,
        speaker="mother",
        character_name="",
    )
    p = build_veo_prompt(b, "g", with_dialogue=True)
    p_lower = p.lower()
    assert "lemon mother" not in p_lower   # PA-1: fruit-cast map gone
    assert "the mother" in p_lower          # generic label used


def test_dialect_param_threads_to_audio_lock():
    """Bug B: build_veo_prompt accepts dialect param and the audio-lock
    text reflects it. Defaults to Syrian for back-compat."""
    from pipeline.video import build_veo_prompt
    from pipeline.types import Beat
    b = Beat(
        arabic="x", english_motion="y", clip_duration_s=8.0,
        speaker="mother", character_name="أم خالد",
    )
    # Egyptian
    p_eg = build_veo_prompt(b, "g", with_dialogue=True, dialect="egyptian")
    assert "egyptian" in p_eg.lower() or "مصري" in p_eg
    # Egyptian must NOT also force Syrian
    assert "specifically syrian" not in p_eg.lower()

    # Default (None) maps to Syrian for back-compat
    p_default = build_veo_prompt(b, "g", with_dialogue=True)
    assert "syrian" in p_default.lower() or "شامي" in p_default


def test_silent_beat_blocks_english_narration():
    """Bug C: when arabic='' the prompt instructs Veo NOT to render any
    speech / voice-over / narration."""
    from pipeline.video import build_veo_prompt
    from pipeline.types import Beat
    b = Beat(
        arabic="",
        english_motion="wide establishing shot, lanterns sway",
        clip_duration_s=8.0,
        speaker="narrator",
        character_name="",
    )
    p = build_veo_prompt(b, "g", with_dialogue=True)
    p_lower = p.lower()
    # No language-lock audio block on silent beats — there's no line to lock
    assert "the exact spoken line" not in p_lower
    # And we explicitly forbid Veo from inventing speech
    assert "no spoken" in p_lower or "no voice-over" in p_lower or "no dialogue" in p_lower
    assert "ambient" in p_lower or "no speech" in p_lower


def test_no_repeat_literal_in_audio_lock():
    """Bug D: the audio-lock no longer ends with the literal 'Repeat:' which
    may have caused Veo to double-speak the line."""
    from pipeline.video import build_veo_prompt
    from pipeline.types import Beat
    b = Beat(
        arabic="مرحبا", english_motion="x", clip_duration_s=8.0,
        speaker="mother", character_name="أم خالد",
    )
    p = build_veo_prompt(b, "g", with_dialogue=True)
    assert "Repeat: spoken in Arabic" not in p
    assert "Repeat:" not in p   # nothing literal "Repeat:"


def test_with_dialogue_freeform_animal_cast_strips_fruit_speaker_desc_still_works():
    """Regression: the previous fix (cast_negation strips fruit map) still works."""
    from pipeline.video import build_veo_prompt
    from pipeline.cast_guidance import veo_clip_negation
    from pipeline.types import Beat
    b = Beat(
        arabic="مرحبا", english_motion="OTS, fox speaks",
        clip_duration_s=8.0, speaker="friend", character_name="سالم",
    )
    p = build_veo_prompt(
        b, "anthropomorphic animals",
        with_dialogue=True,
        cast_negation=veo_clip_negation("animal"),
    )
    assert "blueberry" not in p.lower()


def test_speaker_desc_does_not_leak_role_word_when_character_name_set():
    """Bug 2: when character_name is set, the prompt MUST NOT contain
    '(the friend role)' or '(the mother role)' etc. — the speaker enum
    should not leak into the rendered prompt."""
    from pipeline.video import build_veo_prompt
    from pipeline.types import Beat
    b = Beat(
        arabic="أنا فراولة",
        english_motion="OTS, strawberry speaks",
        clip_duration_s=8.0,
        speaker="friend",                        # the leak source
        character_name="فراولة",
    )
    p = build_veo_prompt(b, "g", with_dialogue=True)
    assert "(the friend role)" not in p
    assert "the friend role" not in p.lower()
    # Sanity: character_name still in prompt
    assert "فراولة" in p


def test_speaker_desc_no_role_leak_for_freeform_animal():
    """Same with cast_negation set (animal mode)."""
    from pipeline.video import build_veo_prompt
    from pipeline.cast_guidance import veo_clip_negation
    from pipeline.types import Beat
    b = Beat(
        arabic="مرحبا", english_motion="x", clip_duration_s=8.0,
        speaker="friend", character_name="سالم",
    )
    p = build_veo_prompt(
        b, "g", with_dialogue=True,
        cast_negation=veo_clip_negation("animal"),
    )
    assert "the friend role" not in p.lower()
    assert "سالم" in p


# ===========================================================================
# PA-1: SPEAKER_DESCRIPTIONS deleted + free-form speaker
# ===========================================================================

def test_speaker_descriptions_constant_is_gone():
    """SPEAKER_DESCRIPTIONS should no longer be defined as a public constant
    in pipeline.video — it was the source of fruit-cast leak into Veo prompts."""
    import pipeline.video as v
    assert not hasattr(v, "SPEAKER_DESCRIPTIONS"), (
        "SPEAKER_DESCRIPTIONS must be deleted in PA-1 — character_name is now "
        "the source of truth for character identity."
    )


def test_dialogue_without_character_name_uses_generic_speaker_label():
    """When character_name is empty and cast_negation is empty (legacy
    Sunstoriz path), the prompt no longer injects fruit descriptions —
    instead it falls back to a simple 'the {speaker} character' label."""
    from pipeline.video import build_veo_prompt
    from pipeline.types import Beat
    b = Beat(
        arabic="x", english_motion="y", clip_duration_s=8.0,
        speaker="mother", character_name="",
    )
    p = build_veo_prompt(b, "g", with_dialogue=True)
    p_lower = p.lower()
    # Generic fallback is used
    assert "the mother" in p_lower or "the speaking character" in p_lower
    # No fruit-cast leak
    assert "lemon mother" not in p_lower
    assert "lemon-shaped head" not in p_lower
    assert "strawberry son" not in p_lower
    assert "blueberry friend" not in p_lower


def test_freeform_path_unchanged_when_character_name_set():
    """Regression: when character_name is set, the existing 'character named X'
    descriptor still works."""
    from pipeline.video import build_veo_prompt
    from pipeline.types import Beat
    b = Beat(
        arabic="x", english_motion="y", clip_duration_s=8.0,
        speaker="warrior", character_name="ليلى",
    )
    p = build_veo_prompt(b, "g", with_dialogue=True)
    assert "ليلى" in p
    assert "the character named" in p.lower() or "named ليلى" in p


def test_speaker_can_be_arbitrary_string():
    """Loosened enum: any non-empty string works as a speaker (e.g.
    'warrior', 'wizard', 'computer-AI', etc.)."""
    from pipeline.video import build_veo_prompt
    from pipeline.types import Beat
    b = Beat(
        arabic="x", english_motion="y", clip_duration_s=8.0,
        speaker="wizard",  # not in the legacy enum
        character_name="غاندالف",
    )
    # Just shouldn't crash; the speaker value is used as a label only
    p = build_veo_prompt(b, "g", with_dialogue=True)
    assert "غاندالف" in p


# ===========================================================================
# PB-1: Voice-over narration must NOT render an on-camera speaker face
# ===========================================================================

def test_voice_over_beat_does_not_render_on_camera_speaker():
    """Voice-over: speaker=narrator + no character_name + non-empty arabic.
    The prompt MUST NOT instruct Veo to render a speaking face — instead
    it should preserve the english_motion visual and only add an audio-only
    narrator instruction."""
    from pipeline.video import build_veo_prompt
    from pipeline.types import Beat
    b = Beat(
        arabic="منذ ثلاثة أيام غاب سامر في هذه الصحراء.",
        english_motion="Extreme wide establishing shot of a lone armored "
                       "warrior on a dune ridge at golden hour",
        clip_duration_s=9.0,
        speaker="narrator",
        character_name="",
    )
    p = build_veo_prompt(b, "g", with_dialogue=True)
    p_lower = p.lower()
    # Must NOT include the on-camera dialogue framing
    assert "faces the camera at medium close-up" not in p_lower
    assert "mouth open mid-speech" not in p_lower
    assert "synchronized lip movement" not in p_lower
    # Must include voice-over guidance
    assert ("voice-over" in p_lower or "voiceover" in p_lower
            or "off-screen narrator" in p_lower or "narrator's voice" in p_lower)
    # Must still include the audio-lock (Arabic + dialect)
    assert "language lock" in p_lower or "must be in arabic" in p_lower.lower()
    # The exact spoken line is still in the prompt
    assert "منذ ثلاثة أيام" in p


def test_dialogue_beat_unchanged_still_renders_speaker_face():
    """Regression: a beat with character_name set still gets the
    'faces the camera at medium close-up' instruction (existing behavior)."""
    from pipeline.video import build_veo_prompt
    from pipeline.types import Beat
    b = Beat(
        arabic="سامر! أين أنت يا أخي؟",
        english_motion="Hand-held tracking shot",
        clip_duration_s=8.5,
        speaker="father",
        character_name="طارق",
    )
    p = build_veo_prompt(b, "g", with_dialogue=True)
    assert "faces the camera at medium close-up" in p.lower()
    assert "طارق" in p


def test_silent_beat_unchanged():
    """Regression: silent beats (arabic='') still get the no-speech block."""
    from pipeline.video import build_veo_prompt
    from pipeline.types import Beat
    b = Beat(arabic="", english_motion="ambient wide", clip_duration_s=9.0,
             speaker="narrator", character_name="")
    p = build_veo_prompt(b, "g", with_dialogue=True)
    assert "no spoken dialogue" in p.lower()
    assert "voice-over" in p.lower() or "voiceover" in p.lower()  # silent says NO voice-over


def test_voiceover_with_character_name_set_treated_as_dialogue():
    """Edge case: speaker=narrator BUT character_name is set (e.g. an
    omniscient named narrator like 'Khaled the elder narrator'). Treat as
    on-camera dialogue, not voice-over."""
    from pipeline.video import build_veo_prompt
    from pipeline.types import Beat
    b = Beat(
        arabic="x",
        english_motion="y",
        clip_duration_s=8.0,
        speaker="narrator",
        character_name="الراوي خالد",
    )
    p = build_veo_prompt(b, "g", with_dialogue=True)
    assert "faces the camera at medium close-up" in p.lower()
    assert "الراوي خالد" in p


# ---------------------------------------------------------------------------
# PB-2: character_descriptions preamble in build_veo_prompt
# ---------------------------------------------------------------------------

def test_build_veo_prompt_prepends_character_descriptions_for_speaker():
    """When character_descriptions is provided AND the speaker is named, the
    prompt prepends a physical description for visual continuity."""
    from pipeline.video import build_veo_prompt
    from pipeline.types import Beat
    b = Beat(
        arabic="x",
        english_motion="medium close-up on Khaled",
        clip_duration_s=8.0,
        speaker="son",
        character_name="خالد",
    )
    p = build_veo_prompt(
        b, "g", with_dialogue=True,
        character_descriptions={
            "خالد": "young man mid-20s, slim, short black hair, white thobe",
            "أم خالد": "woman mid-50s, black hijab",
        },
    )
    p_lower = p.lower()
    # Description for the active speaker is prepended
    assert "young man mid-20s" in p_lower
    assert "خالد" in p
    # Inactive characters NOT included if not mentioned in this beat's english_motion
    assert "أم خالد" not in p


def test_build_veo_prompt_includes_descriptions_for_chars_mentioned_in_motion():
    """If english_motion mentions other character_names, include their
    descriptions too — they may appear in the frame."""
    from pipeline.video import build_veo_prompt
    from pipeline.types import Beat
    b = Beat(
        arabic="نحن قادمون يا أم خالد",
        english_motion="OTS from خالد looking at أم خالد across the room",
        clip_duration_s=8.0,
        speaker="son",
        character_name="خالد",
    )
    p = build_veo_prompt(
        b, "g", with_dialogue=True,
        character_descriptions={
            "خالد": "young man mid-20s, slim, short black hair",
            "أم خالد": "woman mid-50s, black hijab, grey dress",
        },
    )
    # Both descriptions present
    assert "young man mid-20s" in p
    assert "woman mid-50s" in p


def test_build_veo_prompt_no_descriptions_when_dict_empty():
    """Backwards compat: empty character_descriptions → no preamble."""
    from pipeline.video import build_veo_prompt
    from pipeline.types import Beat
    b = Beat(
        arabic="x", english_motion="y", clip_duration_s=8.0,
        speaker="son", character_name="خالد",
    )
    p = build_veo_prompt(b, "g", with_dialogue=True, character_descriptions={})
    # No "character physical descriptions" preamble
    p_lower = p.lower()
    assert "character physical descriptions" not in p_lower
