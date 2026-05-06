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
    b = Beat(arabic="أنا قلبي مكسور", english_motion="m", speaker="mother")
    p = build_veo_prompt(b, global_setting="g", with_dialogue=True)
    assert '"أنا قلبي مكسور"' in p           # exact quoting matters for Veo
    assert "LEMON MOTHER" in p                # speaker description applied
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
    a generic 'speaking character' instead of failing."""
    b = Beat(arabic="ج", english_motion="m", speaker="auntie")  # not in map
    p = build_veo_prompt(b, global_setting="g", with_dialogue=True)
    assert "the speaking character" in p
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


def test_with_dialogue_sunstoriz_keeps_fruit_speaker_desc():
    """Without cast_negation (Sunstoriz / AI Write mode), the existing
    fruit-character SPEAKER_DESCRIPTIONS path is preserved so the legacy
    style still works."""
    from pipeline.video import build_veo_prompt
    from pipeline.types import Beat
    b = Beat(
        arabic="ابني...",
        english_motion="medium close-up, mother speaks",
        clip_duration_s=8.0,
        speaker="mother",
        character_name="أم خالد",
    )
    p = build_veo_prompt(b, "global setting", with_dialogue=True)
    # Cast_negation empty → Sunstoriz path: lemon description is included
    assert "LEMON MOTHER" in p


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
