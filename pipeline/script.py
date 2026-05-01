
"""Stage 2: script generation.

Pipeline: build prompt → Gemini call → parse JSON → optional critique pass → repetition check.

This file holds:
  - first-pass generation (this task)
  - critique pass (Task 8)
  - repetition guard (Task 9)
"""
from __future__ import annotations

import json
import math
import re
from datetime import datetime
from pathlib import Path

from pipeline.types import Beat, Script, ThemeSeed

WRITER_SYSTEM = (
    "أنت كاتب قصص رعب محترف بالعربية الفصحى (MSA) بأسلوب أدبي تأملي. "
    "أسلوبك يشبه قنوات mr nightmare لكن باللغة العربية: الإيقاع البطيء، الجو القاتم، "
    "النهايات المفتوحة، ضمير المتكلم. ممنوع: الحوار الزائد، الكليشيهات، "
    "النهايات التي تشرح كل شيء، 'فجأة سمعت صوتاً'، 'كان كل شيء حلماً'."
)

WRITER_PROMPT_TEMPLATE = """\
اكتب قصة رعب قصيرة جداً (Shorts/TikTok format) باللغة العربية الفصحى وفق هذه القواعد:

الفرضية: {premise}
الفئة: {theme}

البنية المطلوبة (التزم بها) لقصة من حوالي دقيقتين:
1) خطاف فوري (أول 5 ثوانٍ، جملة واحدة قوية) — ضع المشاهد في قلب اللحظة الغريبة مباشرة، لا مقدمات.
2) تصعيد سريع (20-40 ثانية) — جملتان أو ثلاث: حدث غير عادي، ثم حدث أغرب.
3) ذروة (30-40 ثانية) — جمل قصيرة، إيقاع سريع، لحظة الرعب الأقصى.
4) نهاية مفاجئة (آخر 10 ثوانٍ) — جملة أو جملتان تكشفان أو تلمحان لشيء صادم، ثم توقف. لا تشرح.

عدد الكلمات المستهدف: {target_words} كلمة (±{tolerance}). هذا مهم جداً — لا تتجاوز هذا الحد.
ضمير المتكلم (أنا) — إجباري.
MSA الفصحى — لا لهجة.
جمل قصيرة، مكثفة. لا وصف زائد.
نهاية مفتوحة أو صادمة — إجبارية.

أرجع JSON صالح فقط (بدون أي تعليق أو ``` markdown) بالحقول التالية بالضبط:
{{
  "title": "...",
  "theme": "{theme}",
  "global_setting": "وصف موجز للموقع/الزمن/الجو الذي تجري فيه القصة كلها (إنجليزي مختصر) — يستخدم لاحقاً لتوليد الصور",
  "music_mood": "اختر كلمة واحدة فقط من هذه الأربع: drone أو dread أو cosmic أو discovery (بدون شرح أو رمز |)",
  "hook": "الفقرة الافتتاحية (3-4 جمل)",
  "story": "النص الكامل من البداية للنهاية، فقرات مفصولة بـ \\n\\n",
  "word_count": <عدد كلمات story>
}}
"""


def build_writer_prompt(seed: ThemeSeed, target_words: int, tolerance: int) -> str:
    return WRITER_PROMPT_TEMPLATE.format(
        premise=seed.premise,
        theme=seed.theme,
        target_words=target_words,
        tolerance=tolerance,
    )


def _strip_code_fence(text: str) -> str:
    """Remove ```json ... ``` or ``` ... ``` wrappers if present."""
    s = text.strip()
    fence = re.match(r"^```(?:json)?\s*\n(.*?)\n```\s*$", s, re.DOTALL)
    if fence:
        return fence.group(1).strip()
    return s


def _normalize_music_mood(raw: str) -> str:
    """Extract a valid mood from a possibly-sloppy LLM response.

    Gemini sometimes returns the literal placeholder string (e.g.
    "drone | dread | cosmic | discovery") or wraps the value in extra
    text (e.g. "dread - low rumble"). Scan for the first valid mood
    word; fall back to "dread" if none found.
    """
    from pipeline.types import VALID_MOODS
    if isinstance(raw, str) and raw.strip() in VALID_MOODS:
        return raw.strip()
    text = (raw or "").lower()
    for mood in ("drone", "dread", "cosmic", "discovery"):
        # Match the FIRST mood word that appears alone (word-boundary)
        if re.search(rf"\b{mood}\b", text):
            return mood
    return "dread"  # safe fallback for horror genre


def _parse_script_json(text: str, seed: ThemeSeed) -> Script:
    cleaned = _strip_code_fence(text)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"script writer returned invalid JSON: {e}\n--- got ---\n{text[:500]}")
    # We trust the seed.theme over whatever Gemini returned (defensive).
    data["theme"] = seed.theme
    # Normalize music_mood — Gemini often returns sloppy values (placeholder text or qualifiers).
    if "music_mood" in data:
        data["music_mood"] = _normalize_music_mood(data["music_mood"])
    # Recompute word_count from story to avoid LLM miscount.
    story = data.get("story", "")
    data["word_count"] = len([w for w in story.split() if w.strip()])
    try:
        return Script.from_dict(data)
    except (TypeError, ValueError) as e:
        raise ValueError(f"script JSON missing/invalid fields: {e}; got keys={list(data.keys())}")


def generate_script_first_pass(
    gemini, seed: ThemeSeed, target_words: int, tolerance: int
) -> Script:
    prompt = build_writer_prompt(seed, target_words, tolerance)
    raw = gemini.complete(prompt, system=WRITER_SYSTEM)
    return _parse_script_json(raw, seed)


CRITIQUE_PROMPT_TEMPLATE = """\
أنت محرر صارم لقصص الرعب. اقرأ المسودة التالية وقم بتحسينها:

المسودة:
{draft_json}

افحص:
- هل الخطاف الافتتاحي قوي بما يكفي ليوقف المشاهد في أول 30 ثانية؟
- هل النهاية مفتوحة وغير مفسرة؟ (إذا كانت تشرح كل شيء — أصلحها)
- هل توجد كليشيهات ممنوعة مثل: "فجأة سمعت صوتاً"، "كان كل شيء حلماً"، "شعرت بأن أحداً يراقبني" المباشر؟
- هل هناك لحظة "غريب لكن مألوف" واضحة؟
- هل الإيقاع يتصاعد بشكل صحيح؟

أعد كتابة المسودة كاملةً مع التحسينات. حافظ على عدد الكلمات تقريباً.

أرجع JSON صالح فقط بنفس الحقول السابقة (نقد + إصلاح في خطوة واحدة):
{{
  "title": "...",
  "theme": "{theme}",
  "global_setting": "...",
  "music_mood": "اختر كلمة واحدة فقط من: drone أو dread أو cosmic أو discovery (بدون شرح أو رمز |)",
  "hook": "...",
  "story": "...",
  "word_count": <int>
}}
"""


def critique_pass(gemini, seed: ThemeSeed, draft: Script) -> Script:
    prompt = CRITIQUE_PROMPT_TEMPLATE.format(
        draft_json=json.dumps(draft.to_dict(), ensure_ascii=False, indent=2),
        theme=seed.theme,
    )
    raw = gemini.complete(prompt, system=WRITER_SYSTEM)
    return _parse_script_json(raw, seed)


def generate_script(
    gemini,
    seed: ThemeSeed,
    target_words: int,
    tolerance: int,
    enable_critique: bool = True,
) -> Script:
    """First pass + (optional) critique pass. No repetition guard yet — added in next task."""
    draft = generate_script_first_pass(gemini, seed, target_words, tolerance)
    if enable_critique:
        return critique_pass(gemini, seed, draft)
    return draft


def _cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        raise ValueError(f"vector dim mismatch: {len(a)} vs {len(b)}")
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _read_history(path: Path, limit: int = 30) -> list[list[float]]:
    if not path.exists():
        return []
    embeddings: list[list[float]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            embeddings.append(json.loads(line)["embedding"])
        except (json.JSONDecodeError, KeyError):
            continue
    return embeddings[-limit:]


def check_and_record_uniqueness(
    gemini, story_text: str, history_path: Path, threshold: float
) -> tuple[bool, float]:
    """Embed `story_text`, compare against history, append if unique. Returns (is_unique, max_sim)."""
    new_emb = gemini.embed(story_text)
    history = _read_history(history_path)
    max_sim = max((_cosine(new_emb, prev) for prev in history), default=0.0)
    is_unique = max_sim < threshold
    if is_unique:
        history_path.parent.mkdir(parents=True, exist_ok=True)
        with history_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "embedding": new_emb,
                "ts": datetime.now().isoformat(timespec="seconds"),
            }) + "\n")
    return is_unique, max_sim


def generate_script_with_uniqueness(
    gemini,
    seed: ThemeSeed,
    target_words: int,
    tolerance: int,
    enable_critique: bool,
    history_path: Path,
    repetition_threshold: float,
    max_attempts: int = 3,
) -> Script:
    """Loop: generate → check uniqueness → accept or retry up to max_attempts.

    If the embedding API itself fails (network / model unavailable), we log
    a warning and accept the script — uniqueness tracking is a nice-to-have,
    not a hard requirement, and we don't want to throw away an expensive
    Gemini script generation over an embedding-side outage.
    """
    last_sim = 0.0
    for attempt in range(max_attempts):
        script = generate_script(gemini, seed, target_words, tolerance, enable_critique)
        try:
            is_unique, sim = check_and_record_uniqueness(
                gemini, script.story, history_path, repetition_threshold,
            )
        except Exception as e:
            # Degrade gracefully: keep the script, skip uniqueness check.
            print(f"[script] uniqueness check skipped (embed failed: {type(e).__name__}: {e})")
            return script
        if is_unique:
            return script
        last_sim = sim
    raise RuntimeError(
        f"could not generate unique script after {max_attempts} attempts "
        f"(last similarity {last_sim:.3f} >= threshold {repetition_threshold})"
    )


# ============================================================================
# Shorts mode (TikTok / Reels) — different output shape, single Gemini call.
# Produces both the Arabic narration AND English motion prompts for Veo.
# ============================================================================

SHORTS_WRITER_SYSTEM = (
    "أنت كاتب قصص ميلودراما عائلية للـTikTok بأسلوب قنوات Sunstoriz — "
    "قصص مأساوية واقعية: فقر، تضحية، مرض، خيانة، إدمان، حسرة الأمومة. "
    "اكتب باللهجة المصرية أو الخليجية البسيطة. ضمير الراوي / المشاهد. "
    "البطلة عادةً أم فقيرة. الابن غدّار أو ضعيف. "
    "الإيقاع متوازن، الجمل قصيرة، التفاصيل ملموسة (نقود، مستشفى، بيت قديم، شارع، قمامة). "
    "النهاية لازم تكون مأساوية حاسمة (موت، انكسار، فقدان أبدي) — مش مفتوحة. "
    "ممنوع: 'فجأة سمعت صوتاً'، 'كان حلماً'، الجن، الخوارق، شرح زائد. "
    "ممنوع نهاية مفتوحة — لازم تخلص القصة بحدث نهائي ملموس."
)

SHORTS_WRITER_PROMPT_TEMPLATE = """\
اكتب قصة ميلودراما عائلية مأساوية لـ TikTok مدتها ~75 ثانية، مقسمة لـ {num_beats} مشاهد.

الفرضية: {premise}
الفئة: {theme}

أسلوب القصة (المهم):
- ميلودراما عائلية واقعية: فقر، تضحية الأم، مرض، إدمان، خيانة الابن، حسرة.
- لهجة مصرية أو خليجية بسيطة، جمل قصيرة عاطفية.
- ضمير الراوي (يحكي عن شخصيات، مش بضمير المتكلم).
- البطلة أم فقيرة تضحي. ابنها يكبر ويتنكر لها أو يدمن أو يضيع المال.
- الأب مات أو مريض. الجار غني ومتجاهل.
- النهاية مأساوية حاسمة (الأم بتموت، الابن بيندم متأخر، تدمير العائلة).

CRITICAL — ALL CHARACTERS ARE ANTHROPOMORPHIC FRUIT (Sunstoriz signature style):
- الأم = LEMON character (yellow lemon-head body, sad eyes, wears black hijab/dress)
- الابن (طفل) = small STRAWBERRY character (red strawberry head with green leaves, child clothes)
- الابن (كبير) = adult STRAWBERRY character (with beard, traditional thobe or casual clothes)
- الأب = older LEMON character (with beard) أو APPLE
- الدكتور = APPLE character (red apple head, white coat, stethoscope)
- الجار / صاحب المحل = MANGO أو POMEGRANATE
- الزوجة = PEACH أو ORANGE
- استخدم نفس الشخصية (نفس الفاكهة) عبر كل المشاهد للحفاظ على التطابق

البنية الدرامية:
- مشهد 1 (الفقر/البداية): الأم وابنها الصغير في بيت متواضع، تعطيه آخر فلوس
- مشاهد 2-4 (التصاعد): الابن يكبر، يبدأ في التغيير — يدمن، يقامر، يهجر الأم
- مشاهد 5-6 (الأزمة): الأم تكتشف، تنكسر، تواجه مأساة (مرض الأب، الفقر المدقع)
- المشهد الأخير (النهاية الحاسمة المأساوية): موت أو فقدان نهائي. **لازم نهاية حاسمة وملموسة — موت، خراب، فقدان أبدي. مش مفتوحة.**

كل مشهد:
- نص عربي ~{words_per_beat} كلمة (جملة أو جملتين، عاطفية، تفاصيل ملموسة).
- وصف بصري بالإنجليزية ~30 كلمة:
  - **CRITICAL: 3D Pixar-style animation, photorealistic textures, anthropomorphic fruit characters with human clothing**
  - شخصية معينة من الفاكهة (lemon mother in black hijab, strawberry son, apple doctor, etc.)
  - تعبير وجهي عاطفي قوي (sad eyes, crying, angry, shocked, smug)
  - بيئة محددة (poor humble home, hospital corridor, gambling den with hookah, junkyard at sunset, dump trucks)
  - إضاءة درامية (dim warm lamp, fluorescent hospital, golden sunset, dark shadows)

أرجع JSON صالح فقط (بدون markdown أو ``` أو شرح) بهذه الحقول بالضبط:
{{
  "title": "عنوان مأساوي قصير",
  "theme": "{theme}",
  "global_setting": "وصف بصري قصير بالإنجليزية: '3D Pixar animation, anthropomorphic fruit characters as humans, dramatic emotional lighting, vertical 9:16, cinematic quality'",
  "music_mood": "اختر كلمة واحدة فقط: drone أو dread أو cosmic أو discovery (بدون شرح أو رمز |)",
  "beats": [
    {{"arabic": "...", "english_motion": "..."}},
    {{"arabic": "...", "english_motion": "..."}},
    {{"arabic": "...", "english_motion": "..."}},
    {{"arabic": "...", "english_motion": "..."}},
    {{"arabic": "...", "english_motion": "..."}},
    {{"arabic": "...", "english_motion": "..."}},
    {{"arabic": "...", "english_motion": "..."}},
    {{"arabic": "...", "english_motion": "..."}}
  ]
}}
"""


def build_shorts_writer_prompt(seed: ThemeSeed, num_beats: int = 8, words_per_beat: int = 30) -> str:
    return SHORTS_WRITER_PROMPT_TEMPLATE.format(
        premise=seed.premise,
        theme=seed.theme,
        num_beats=num_beats,
        words_per_beat=words_per_beat,
        global_setting_hint="نفس الإعداد عبر المشاهد",
    )


def _parse_shorts_script_json(text: str, seed: ThemeSeed) -> Script:
    """Parse Gemini's Shorts response into a Script with beats."""
    cleaned = _strip_code_fence(text)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"shorts writer returned invalid JSON: {e}\n--- got ---\n{text[:500]}")
    # Trust the seed.theme defensively.
    data["theme"] = seed.theme
    # Normalize music_mood (handles sloppy LLM output — same logic as long-form path).
    if "music_mood" in data:
        data["music_mood"] = _normalize_music_mood(data["music_mood"])
    beats_raw = data.get("beats") or []
    if not isinstance(beats_raw, list) or not beats_raw:
        raise ValueError("shorts script must contain a non-empty 'beats' list")
    beats: tuple[Beat, ...] = tuple(
        Beat(arabic=str(b.get("arabic", "")).strip(),
             english_motion=str(b.get("english_motion", "")).strip())
        for b in beats_raw
    )
    # Reject if any beat is missing both fields — clear LLM failure.
    for i, b in enumerate(beats):
        if not b.arabic or not b.english_motion:
            raise ValueError(f"beat {i+1} missing arabic or english_motion: {b}")

    story_combined = " ".join(b.arabic for b in beats)
    try:
        return Script(
            title=str(data.get("title", "")).strip() or "بلا عنوان",
            theme=data["theme"],
            global_setting=str(data.get("global_setting", "")).strip(),
            music_mood=data["music_mood"],
            beats=beats,
            story_combined=story_combined,
            # Long-form fields stay default (empty)
        )
    except (TypeError, ValueError) as e:
        raise ValueError(f"shorts script construction failed: {e}; got keys={list(data.keys())}")


def generate_shorts_script(
    gemini, seed: ThemeSeed, num_beats: int = 8, words_per_beat: int = 30,
) -> Script:
    """Single Gemini call → Script with beats[]. No critique pass for Shorts (story is short enough)."""
    prompt = build_shorts_writer_prompt(seed, num_beats=num_beats, words_per_beat=words_per_beat)
    raw = gemini.complete(prompt, system=SHORTS_WRITER_SYSTEM)
    return _parse_shorts_script_json(raw, seed)
