
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
    "اكتب باللهجة السورية / الشامية البسيطة (مش فصحى، مش مصري، مش خليجي). "
    "كلمات شامية: 'شو'، 'كتير'، 'هلق'، 'ليش'، 'ما عم'، 'بدي'، 'يلي'، 'منيح'، 'بكير'. "
    "**كل مشهد لازم يكون كلام مباشر من شخصية بضمير المتكلم (أنا) — مش راوي.** "
    "كل بيت = شخصية بتتكلم/تفكر/تصرخ بصوتها هي. ممنوع وصف خارجي 'الأم تبكي' — "
    "بدلها اكتب الكلام اللي بتقوله الأم نفسها: 'أنا قلبي مكسور…'. "
    "البطلة عادةً أم فقيرة. الابن غدّار أو ضعيف. الأب مات أو مريض. الدكتور بيبلغ الخبر. "
    "الإيقاع متوازن، الجمل قصيرة، عاطفية مباشرة، تفاصيل ملموسة. "
    "النهاية لازم تكون مأساوية حاسمة (موت، انكسار، فقدان أبدي) — مش مفتوحة. "
    "ممنوع: 'فجأة سمعت صوتاً'، 'كان حلماً'، الجن، الخوارق، شرح زائد. "
    "ممنوع نهاية مفتوحة — لازم تخلص القصة بحدث نهائي ملموس."
)

SHORTS_WRITER_PROMPT_TEMPLATE = """\
اكتب قصة ميلودراما عائلية مأساوية لـ TikTok، طولها بين 60 و 120 ثانية حسب تعقيد القصة.
أنت تختار عدد المشاهد ({min_beats} كحد أدنى، {max_beats} كحد أقصى) وزمن كل مشهد بناء على القصة.

الفرضية: {premise}
الفئة: {theme}

أسلوب القصة (المهم):
- ميلودراما عائلية واقعية: فقر، تضحية الأم، مرض، إدمان، خيانة الابن، حسرة.
- **اللهجة السورية / الشامية فقط** (مش فصحى ولا مصرية ولا خليجية)، جمل قصيرة عاطفية.
- استخدم كلمات شامية: شو/كتير/هلق/ليش/ما عم/بدي/يلي/منيح/بكير/ولاد/البي/إيمتى/ع/تاع/متل/هيك/خلص.
- صوت سرد متحول: كل مشهد شخصية مختلفة بتتكلم — الأم بتشتكي، الابن بيصرخ، الدكتور بيبلغ الخبر.
- البطلة أم فقيرة تضحي. ابنها يكبر ويتنكر لها أو يدمن أو يضيع المال.
- الأب مات أو مريض. الجار غني ومتجاهل.
- النهاية مأساوية حاسمة وملموسة (موت، انكسار نهائي، فقدان أبدي) — لازم تكون مغلقة، مش مفتوحة.

CRITICAL WORD COUNT — كل مشهد كلامه لازم يتسع في {clip_seconds} ثانية صوت فقط:
- كل مشهد ≈ **{words_per_beat} كلمة** كحد أقصى ({min_words_per_beat} كحد أدنى).
- المشاهد الأقل من {min_words_per_beat} كلمة سترفض. المشاهد الأكثر من {max_words_per_beat} كلمة سترفض كذلك (الصوت يطول على الكليب).
- مجموع كل المشاهد لازم ≥ {min_total_words} كلمة و ≤ {max_total_words} كلمة.
- اكتب جمل قصيرة مكثفة (مش طويلة) — ركز على لقطة واحدة عاطفية في كل مشهد.
- مثال على مشهد بالعدد الصحيح للكلمات (~22 كلمة، لهجة شامية):
  "أنا قاعدة بالمطبخ عم بكي بصمت، عم بتطلع ع ابني عم ياكل آخر لقمة عنا، قلبي مكسور بس عم خبي حزني."
  (~22 Arabic words in Syrian dialect — that's the target length)

CRITICAL — كل مشهد لازم تتكلم فيه شخصية بضمير المتكلم (أنا). ممنوع راوي خارجي:
- كل مشهد عنده حقل `speaker` يحدد مين بيتكلم. القيم المسموحة فقط:
  * "mother"      — الأم (صوت أنثوي حزين)
  * "son"         — الابن (صوت ذكوري)
  * "father"      — الأب (صوت ذكوري)
  * "doctor"      — الدكتور (صوت ذكوري)
  * "neighbor"    — الجار/صاحب المحل (صوت ذكوري)
  * "grandmother" — الجدة (صوت أنثوي)
  * "wife"        — الزوجة (صوت أنثوي)
  * "daughter"    — البنت (صوت أنثوي)
- لازم البيت يكون كلام مباشر من تلك الشخصية بضمير المتكلم (مثلاً الأم تقول: "أنا قاعدة في المطبخ، قلبي مكسور…").
- ممنوع تماماً قيمة "narrator" — كل مشهد لشخصية معينة.
- البطلة الأم لها على الأقل 4 مشاهد. الابن له على الأقل 2 مشهد.
- التنويع مطلوب: غير الشخصية المتكلمة بين المشاهد (مش كلهم mother).

CRITICAL — كل شخصية لها اسم عربي ثابت (character_name):
- لكل بيت أعطِ `character_name` (اسم عربي قصير، مثلاً "أم خالد"، "خالد"، "د. سامي").
- نفس الشخصية = نفس الاسم في كل البيتات. الأم اسمها واحد عبر القصة كلها.
- اختر أسماء عربية مألوفة. ممنوع أسماء أجنبية.
- إذا الشخصية بدون اسم محدد (مثل بائع الخضرة)، استعمل لقبًا قصيرًا (مثل "البقال").

CRITICAL — ALL CHARACTERS ARE ANTHROPOMORPHIC FRUIT (Sunstoriz signature style):
- الأم = LEMON character (yellow lemon-head, sad eyes, wears black hijab and grey dress, mid-50s)
- **الابن = adult STRAWBERRY character (early 20s young man, red strawberry head with green-leaf hair, light beard, grey t-shirt). NEVER a child or boy. The son is a grown young adult in EVERY beat.**
- الأب = older LEMON character (mid-60s, white beard, white thobe, weak)
- الدكتور = APPLE character (red apple head, round glasses, white coat, stethoscope)
- الجار = MANGO character (orange-yellow mango head, beige dishdasha, smug)
- الزوجة = PEACH character (mid-20s, beige hijab, anxious)
- البنت = CHERRY character (~6 years old, red cherry head, white dress)

**CHARACTER AGE LOCK — لا يتغير عمر الشخصية وسط الفيديو:**
- الابن دائماً شاب بالغ (20-25 سنة) في كل البيتات. ممنوع طفل ثم شاب — الفيديو لا يصور التقدم في العمر.
- استخدم نفس وصف الشخصية (نفس الفاكهة، نفس العمر، نفس الملابس) عبر كل المشاهد.
- إذا القصة تتطلب طفولة وبلوغ، اختر واحد فقط للفيديو كله.

البنية الدرامية (كل بيت = شخصية بتتكلم بصوتها):
- مشهد 1 (افتتاحية): الأم تتكلم عن فقرها وابنها الصغير ("أنا قاعدة في المطبخ، ما عندي غير لقمة لابني…")
- مشاهد 2-4 (التصاعد): تنويع المتكلمين — الابن يقول كلامه، الأم ترد، الأب أو الدكتور يدخل
- مشاهد 5-7 (الأزمة): الابن يتنكر/يصرخ، الأم تتوسل، الدكتور يبلغ خبر سيء
- المشهد قبل الأخير: الأم لحظة الانكسار النهائي
- المشهد الأخير (النهاية): الأم أو الابن يقول الكلمة الأخيرة قبل الموت/الفقدان. **لازم نهاية مغلقة حاسمة ملموسة.**

كل مشهد:
- نص عربي ~{words_per_beat} كلمة من كلام الشخصية نفسها بضمير المتكلم (أنا) باللهجة الشامية، جملة أو جملتين.
  مثال صح: "أنا قلبي عم يحترق، ابني نسي شو عملت لأجلو، ضحيت بكل عمري وبالآخر تنكر لي."
  مثال غلط (راوي): "الأم تبكي على ابنها." — هذا ممنوع.
- وصف بصري بالإنجليزية ~30 كلمة، **يصف استمراراً مباشراً من المشهد السابق**:
  - **CONTINUITY-CRITICAL**: each beat's visual MUST start exactly where the previous beat's visual ended. If beat N ended with "mother holding bread, looking down", beat N+1 must start with "mother still holding bread, raising her eyes" — same character, same outfit, same camera framing as the previous frame, then the new motion begins.
  - **CRITICAL: 3D Pixar-style animation, the speaking character centered, FACING CAMERA, mouth open mid-speech, frontal medium close-up**
  - شخصية معينة من الفاكهة بتتكلم (lemon mother speaking, strawberry son shouting, apple doctor delivering news)
  - تعبير وجهي عاطفي قوي يطابق الكلام (crying eyes, angry shout, broken whisper)
  - بيئة محددة وراء الشخصية (poor humble home, hospital corridor, junkyard at sunset)
  - إضاءة درامية (dim warm lamp on face, fluorescent hospital, golden sunset)
  - Use phrases like: "continuing from prior frame", "still in the same kitchen", "same lemon mother now turns to look at..."

أرجع JSON صالح فقط (بدون markdown أو ``` أو شرح) بهذه الحقول بالضبط:
{{
  "title": "عنوان مأساوي قصير",
  "theme": "{theme}",
  "global_setting": "وصف بصري قصير بالإنجليزية: '3D Pixar animation, anthropomorphic fruit characters as humans, dramatic emotional lighting, vertical 9:16, cinematic quality'",
  "music_mood": "اختر كلمة واحدة فقط: drone أو dread أو cosmic أو discovery (بدون شرح أو رمز |)",
  "target_duration_s": <integer 60..120, your chosen total length>,
  "beats": [
    {{"arabic": "...", "english_motion": "...", "clip_duration_s": <float 6..10>, "speaker": "mother|son|father|doctor|neighbor|narrator", "character_name": "اسم عربي محدد للشخصية"}},
    ...repeat between {min_beats} and {max_beats} times...
  ]
}}

ملاحظات إجبارية:
- عدد البيتات لازم بين {min_beats} و {max_beats}.
- مجموع clip_duration_s لازم ≈ target_duration_s.
- المشهد الأخير لازم يكون نهاية مغلقة حاسمة (موت، فقدان نهائي، انكسار). ممنوع نهاية مفتوحة أو سؤال.
"""


def build_shorts_writer_prompt(
    seed: ThemeSeed, min_beats: int = 8, max_beats: int = 15,
    words_per_beat: int = 22, clip_seconds: int = 8,
) -> str:
    """Build the per-beat writer prompt.

    Default words_per_beat dropped from 30 → 22 because per-beat audio at
    natural Arabic pace is ~3 words/second, so >24 words won't fit in an
    8-second clip and would either truncate the audio or stretch the video.
    """
    min_words_per_beat = max(int(words_per_beat * 0.6), 12)
    max_words_per_beat = int(words_per_beat * 1.2)
    min_total_words = min_beats * min_words_per_beat
    max_total_words = max_beats * max_words_per_beat
    return SHORTS_WRITER_PROMPT_TEMPLATE.format(
        premise=seed.premise,
        theme=seed.theme,
        min_beats=min_beats,
        max_beats=max_beats,
        words_per_beat=words_per_beat,
        min_words_per_beat=min_words_per_beat,
        max_words_per_beat=max_words_per_beat,
        min_total_words=min_total_words,
        max_total_words=max_total_words,
        clip_seconds=clip_seconds,
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
    valid_speakers = {
        "mother", "son", "father", "doctor", "neighbor",
        "grandmother", "wife", "daughter", "friend", "enemy", "shadow",
        "narrator",
    }
    beats: tuple[Beat, ...] = tuple(
        Beat(
            arabic=str(b.get("arabic", "")).strip(),
            english_motion=str(b.get("english_motion", "")).strip(),
            clip_duration_s=float(b.get("clip_duration_s", 8.0)),
            speaker=str(b.get("speaker", "")).strip().lower(),
            character_name=str(b.get("character_name", "")).strip(),
        )
        for b in beats_raw
    )
    # Enforce: every beat must use a known speaker role.
    for i, b in enumerate(beats):
        if b.speaker not in valid_speakers:
            raise ValueError(
                f"beat {i+1} has invalid speaker={b.speaker!r}; "
                f"must be one of {sorted(valid_speakers)}."
            )
    # Reject if the visual prompt is missing — Veo needs it for every beat.
    # Empty arabic is allowed (silent action / atmospheric beats).
    for i, b in enumerate(beats):
        if not b.english_motion:
            raise ValueError(
                f"beat {i+1} missing english_motion (the visual prompt is "
                f"required for every beat — silent beats still need a "
                f"shot description for Veo): {b}"
            )

    target_duration_s = float(data.get("target_duration_s", 0.0))
    if target_duration_s <= 0:
        target_duration_s = sum(b.clip_duration_s for b in beats)

    story_combined = " ".join(b.arabic for b in beats)
    try:
        return Script(
            title=str(data.get("title", "")).strip() or "بلا عنوان",
            theme=data["theme"],
            global_setting=str(data.get("global_setting", "")).strip(),
            music_mood=data["music_mood"],
            beats=beats,
            story_combined=story_combined,
            target_duration_s=target_duration_s,
            # Long-form fields stay default (empty)
        )
    except (TypeError, ValueError) as e:
        raise ValueError(f"shorts script construction failed: {e}; got keys={list(data.keys())}")


EXPAND_PROMPT_TEMPLATE = """\
المسودة التالية قصيرة جداً. كل مشهد لازم يكون ~{target} كلمة، لكنك أنتجت مشاهد بـ
{actual} كلمة بالمتوسط. أعد كتابة كل مشهد بنفس المعنى لكن أطول وأكثر تفصيلاً —
أضف تفاصيل بصرية (المكان، الإضاءة، الأشخاص في الخلفية)، تفاصيل عاطفية (دموع،
اهتزاز اليد، نبرة الصوت)، تفاصيل ملموسة (أسماء، أرقام، أسماء أماكن).

المسودة:
{draft_json}

أرجع JSON صالح فقط بنفس الحقول السابقة، لكن مع مشاهد مفصلة (~{target} كلمة لكل مشهد).
حافظ على حقل character_name كما هو لكل بيت — لا تغير أسماء الشخصيات.
"""


def _expand_short_script(gemini, draft: Script, target_words_per_beat: int) -> Script:
    """If a script came back too short, ask the LLM to expand it without changing the plot."""
    actual = sum(len(b.arabic.split()) for b in draft.beats) / max(len(draft.beats), 1)
    prompt = EXPAND_PROMPT_TEMPLATE.format(
        target=target_words_per_beat,
        actual=int(actual),
        draft_json=json.dumps(draft.to_dict(), ensure_ascii=False, indent=2),
    )
    raw = gemini.complete(prompt, system=SHORTS_WRITER_SYSTEM)
    # Re-parse with same seed assumptions
    from pipeline.types import VALID_THEMES  # noqa
    seed_proxy = ThemeSeed(theme=draft.theme, premise="(expand pass)")
    return _parse_shorts_script_json(raw, seed_proxy)


SHORTS_CRITIQUE_PROMPT_TEMPLATE = """\
أنت محرر صارم لقصص ميلودراما عائلية للـTikTok بأسلوب @sunstoriz.
المسودة التالية لازم تتحسن قبل ما تتحول لفيديو.

المسودة:
{draft_json}

افحص هذه النقاط واحدة واحدة وصلح كل واحدة:

1) **اللهجة الشامية / السورية فقط** عبر كل المشاهد.
   - ممنوع كلمات فصحى (بكاء، يبكي، يصرخ) → بدلها بشامية (عم يبكي، عم يصرخ).
   - ممنوع كلمات مصرية (بصرخ، بياكل، عشان) → بدلها (عم صرخ، عم ياكل، تا).
   - ممنوع كلمات خليجية (شلون، وايد، لي) → بدلها (شو، كتير، لإلي).
   - استخدم: عم / شو / كتير / بدي / ليش / هلق / متل / ولا / منيح / تا / لإلي / يلي.

2) **عمر الابن ثابت عبر كل المشاهد.** اختر إما طفل صغير لكل القصة، أو شاب بالغ لكل القصة.
   ممنوع طفل في مشهد ثم شاب بالغ في مشهد آخر — العمر لا يتغير وسط الفيديو.
   إذا ما كان واضح، اختر "شاب بالغ في عشرينياته" ووحّد كل البيتات.

3) **القصة فيها بداية + تصاعد + ذروة + نهاية حاسمة.**
   - البيت الأول: لقطة افتتاحية قوية تشد المشاهد فوراً.
   - البيتات الوسط: تصاعد عاطفي حقيقي، مش تكرار نفس الإحساس.
   - البيت الأخير: نهاية مغلقة ملموسة (موت، فقدان نهائي، انكسار) — ممنوع نهاية مفتوحة.

4) **الحوار طبيعي ومش مكرر.** لو شخصية تتكلم في عدة بيتات، كل بيت لازم يقول شيء جديد.
   ممنوع تكرار نفس الجملة بصيغ مختلفة.

5) **الـenglish_motion يلتزم بالاستمرارية البصرية بين البيتات.**
   كل بيت لازم يبدأ من حيث انتهى البيت السابق (نفس المكان، نفس الإضاءة، نفس الشخصية تستمر بحركتها).
   اكتب "continuing from prior frame" أو "same X still..." في كل البيتات بعد الأول.

6) **الكلمات العربية كلها واضحة ومكتوبة صح.**
   ممنوع أحرف غير عربية (كورية، يابانية، صينية، إلخ).
   ممنوع كلمات مكتوبة غلط أو مخلوطة.

7) **character_name ثابت لكل شخصية** عبر كل البيتات.
   - لو الأم في بعض البيتات اسمها "أم خالد" وفي بيت آخر "أم محمد" — صلّحها لتكون موحدة.
   - كل بيت لازم يحتوي حقل `character_name` بقيمة عربية قصيرة. لا تترك فارغًا.

أرجع JSON صالح فقط (بدون markdown أو ``` أو شرح) بنفس الحقول السابقة (title, theme, global_setting, music_mood, target_duration_s, beats[]) لكن مع كل التحسينات.
كل بيت لازم يحتوي: arabic, english_motion, clip_duration_s, speaker, character_name.
"""


def _critique_shorts_script(gemini, draft: Script, seed: ThemeSeed) -> Script:
    """Second-pass editor that fixes dialect drift, character age, story arc, continuity."""
    prompt = SHORTS_CRITIQUE_PROMPT_TEMPLATE.format(
        draft_json=json.dumps(draft.to_dict(), ensure_ascii=False, indent=2),
    )
    raw = gemini.complete(prompt, system=SHORTS_WRITER_SYSTEM)
    return _parse_shorts_script_json(raw, seed)


def generate_shorts_script(
    gemini, seed: ThemeSeed,
    *,
    min_beats: int = 8, max_beats: int = 15, words_per_beat: int = 22,
    min_total_words: int | None = None, max_expand_retries: int = 2,
    enable_critique: bool = True,
) -> Script:
    """Generate a Shorts script: writer pass → critique pass → optional expand pass.

    `words_per_beat` defaults to 22 to keep each beat's narration ≤ 8s
    (Veo's per-clip limit) so audio and clip durations stay aligned.

    `enable_critique=True` runs a second LLM call that explicitly checks
    dialect consistency (Syrian only), character age stability, story-arc
    quality, dialogue freshness, visual continuity, and Arabic correctness.
    Adds one extra LLM call (free on Groq); meaningfully improves output.
    """
    if min_total_words is None:
        min_total_words = int(min_beats * words_per_beat * 0.7)

    prompt = build_shorts_writer_prompt(
        seed, min_beats=min_beats, max_beats=max_beats, words_per_beat=words_per_beat,
    )
    raw = gemini.complete(prompt, system=SHORTS_WRITER_SYSTEM)
    script = _parse_shorts_script_json(raw, seed)

    if len(script.beats) < min_beats:
        raise ValueError(
            f"writer returned {len(script.beats)} beats, below min_beats={min_beats}"
        )

    if enable_critique:
        try:
            critiqued = _critique_shorts_script(gemini, script, seed)
            if len(critiqued.beats) >= min_beats:
                script = critiqued
            else:
                print(f"[script] critique returned only {len(critiqued.beats)} beats; "
                      f"keeping draft")
        except Exception as e:
            print(f"[script] critique failed ({type(e).__name__}: {e}); using draft")

    for attempt in range(max_expand_retries):
        total = sum(len(b.arabic.split()) for b in script.beats)
        if total >= min_total_words:
            return script
        print(f"[script] expand pass {attempt+1}/{max_expand_retries}: "
              f"got {total} words, want ≥{min_total_words}")
        try:
            script = _expand_short_script(gemini, script, words_per_beat)
        except Exception as e:
            print(f"[script] expand failed ({type(e).__name__}: {e}); using shorter draft")
            return script
    return script
