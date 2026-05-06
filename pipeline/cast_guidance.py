"""Cast-type guidance for Flux character sheets and Veo per-clip prompts.

Why this exists: Both Flux Kontext and Veo are biased toward the Sunstoriz
fruit-character TikTok style they've seen heavily in training. When a
freeform user picks character_template=animal/human/surreal, the writer's
script.global_setting alone isn't enough to push the models off that
default. Aggressive negation + concrete cast-type vocabulary, placed early
in the prompt, is required.

This module centralises the two negation strings (one for Flux, one for
Veo) so both pipeline stages stay in sync.
"""
from __future__ import annotations


_CAST_FLUX_GUIDANCE: dict[str, str] = {
    "human": (
        "Realistic human characters with diverse Arabic features (skin tones, "
        "hair, eyes), wearing clothing appropriate to the story's setting. "
        "STRICTLY NOT anthropomorphic fruit. NO lemons, NO strawberries, NO "
        "apples, NO mangoes, NO blueberries. NOT animal characters either — "
        "real human beings."
    ),
    "animal": (
        "Anthropomorphic animal characters — concrete species like fox, "
        "rabbit, deer, bear, wolf, owl, cat, panda — each character a "
        "distinct species, wearing clothing appropriate to the story's "
        "setting. STRICTLY NOT fruit characters. NO lemons, NO strawberries, "
        "NO apples, NO mangoes, NO blueberries. NOT humans either — "
        "anthropomorphic animals."
    ),
    "surreal": (
        "Surreal abstract creatures with non-natural body shapes — geometric, "
        "ethereal, dreamlike. STRICTLY NOT realistic humans, NOT real "
        "animals, and NOT fruit characters. NO lemons, NO strawberries, NO "
        "apples, NO mangoes, NO blueberries."
    ),
}


_CAST_VEO_GUIDANCE: dict[str, str] = {
    "human": (
        "Cast: realistic human characters with diverse Arabic features. "
        "STRICTLY NOT anthropomorphic fruit (no lemons, strawberries, "
        "apples, mangoes, blueberries) and NOT animals — real human beings."
    ),
    "animal": (
        "Cast: anthropomorphic animal characters (fox, rabbit, deer, bear, "
        "wolf, owl, panda — distinct species). STRICTLY NOT anthropomorphic "
        "fruit (no lemons, strawberries, apples, mangoes, blueberries) and "
        "NOT humans."
    ),
    "surreal": (
        "Cast: surreal abstract creatures with non-natural body shapes. "
        "STRICTLY NOT anthropomorphic fruit, NOT real animals, NOT humans."
    ),
}


def flux_lineup_override(character_template: str | None) -> str:
    """Flux character-sheet override clause; '' for fruit_sunstoriz/ai_choose/unknown."""
    return _CAST_FLUX_GUIDANCE.get(character_template or "", "")


def veo_clip_negation(character_template: str | None) -> str:
    """Concise Veo per-beat negation; '' for fruit_sunstoriz/ai_choose/unknown."""
    return _CAST_VEO_GUIDANCE.get(character_template or "", "")
