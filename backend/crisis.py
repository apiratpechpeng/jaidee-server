"""ตัวตรวจจับข้อความเสี่ยงแบบ rule-based (keyword matching ภาษาไทย/อังกฤษ)

ระดับวิกฤต (crisis_level) — ทั้งสองระดับเปิด Crisis Protocol เหมือนกัน (ตอบด้วยข้อความตายตัว + สายด่วน)
  HIGH     = พูดถึงการจบชีวิต ทำร้ายตัวเอง หรือวิธีการ อย่างชัดเจน
  MODERATE = ความคิดอยากหายไป/ไม่อยากตื่น แบบไม่ชัดเจน (passive) ซึ่งยังต้องดูแลทันที
  NONE     = ไม่พบ

หมายเหตุสำคัญ
  - ส่วนนี้ "ไม่" ใช้กฎคำปฏิเสธ ("ไม่ได้อยากตายนะ แต่...") และไม่ใช้ NLP เพื่อไม่ให้พลาดข้อความเสี่ยง (ยอมเตือนเกินดีกว่าพลาด)
  - เพิ่มคำใหม่ได้ใน CRISIS_HIGH_KEYWORDS / CRISIS_MODERATE_KEYWORDS แล้วรัน python -m backend.evaluate เพื่อดูผล
  - ในระบบจริงควรเสริมด้วยโมเดลจำแนกข้อความที่ผ่านการฝึกเฉพาะทาง และผ่านการตรวจโดยผู้เชี่ยวชาญ
"""
import re

CRISIS_HIGH_KEYWORDS = [
    # พูดถึงการตาย/จบชีวิตตรงๆ
    "ฆ่าตัวตาย", "อยากตาย", "อยากจะตาย", "อยากตายๆ", "ไม่อยากมีชีวิตอยู่", "ไม่อยากมีชีวิต", "จบชีวิต", "ปลิดชีพ",
    "ลาโลก", "ลาโลกนี้", "ไปให้พ้นโลกนี้", "ตายไปซะ", "ตายๆไปซะ", "ตายไปเลยดีกว่า", "ตายดีกว่า",
    # ทำร้ายตัวเอง / วิธีการ
    "ทำร้ายตัวเอง", "ทำร้ายตนเอง", "กรีดแขน", "กรีดข้อมือ", "กรีดตัวเอง", "กินยาเกินขนาด", "กินยาตาย",
    "กินยาฆ่าตัวตาย", "กินยาหมดแผง", "กระโดดตึก", "โดดตึก", "ผูกคอ", "แขวนคอ",
    # ภาษาอังกฤษ
    "ฆ่าตัวเอง", "แทงตัวเอง", "ยิงตัวตาย", "เผาถ่าน", "จดหมายลาตาย", "วิธีตาย", "ตายคืนนี้", "เกินขนาด", "กินยานอนหลับหมด",
    "kms", "kill me", "kill myself", "suicide", "end my life", "want to die", "self harm", "self-harm", "unalive",
]

CRISIS_MODERATE_KEYWORDS = [
    "ไม่อยากอยู่แล้ว", "ไม่อยากอยู่ต่อ", "อยากหายไป", "อยากหายไปจากโลก", "อยากหลับไปยาวๆ", "อยากหลับยาวๆ",
    "อยากหลับไม่ตื่น", "หลับไม่ต้องตื่น", "ไม่อยากตื่น", "ไม่อยากตื่นมาอีก", "ไม่อยากเกิดมา",
    "ไม่น่าเกิดมา", "อยู่ไปก็ไม่มีประโยชน์", "อยู่ไปทำไม", "ถ้าไม่มีเราคงดีกว่า", "ไม่มีเราทุกคนคงสบาย",
    "หมดหวัง", "หมดหวังกับชีวิต", "ไม่อยากหายใจ",
    "เป็นภาระ", "ตัวถ่วง", "ไม่ต้องตื่น", "ไม่ตื่นอีก", "ไม่ตื่นมาอีก", "ไม่อยากอยู่บนโลก", "หนีไปจากชีวิต", "ไม่อยากเป็นตัวเอง",
    "อยากพักถาวร", "ไม่มีความหมาย", "ไม่เห็นอนาคต", "ไม่มีความหวัง", "ไม่มีใครต้องการ", "ไม่มีฉัน", "ไม่มีเรา", "รถชน", "หายไปเลย",
    "ไม่ต้องลืมตา", "ไม่ต้องรู้สึกอะไร", "อยากเป็นอากาศ", "ไม่เหลืออะไร",
    "wish i could disappear", "wish i could just disappear", "better off without me", "don't want to wake up", "dont wanna wake up",
    "disappear forever", "no point in anything",
]

# วลีทั่วไปที่มีคำระดับ MODERATE อยู่ข้างใน แต่ไม่ได้สื่อถึงความเสี่ยง (ตัดออกก่อนตรวจระดับ MODERATE เท่านั้น ไม่กระทบระดับ HIGH)
# เช่น "ไม่อยากตื่นเช้าไปเรียน" — ถ้าไม่แน่ใจว่าวลีไหนปลอดภัย อย่าใส่ในนี้
MODERATE_EXCEPTIONS = ["ไม่อยากตื่นเช้า", "ไม่อยากตื่นไปเรียน", "ไม่อยากตื่นไปโรงเรียน", "ไม่อยากตื่นไปทำงาน"]

DISTRESS_KEYWORDS = [
    "เศร้ามาก", "ทนไม่ไหว", "สิ้นหวัง", "เหนื่อยกับชีวิต", "ร้องไห้", "เครียดมาก", "โดดเดี่ยว",
    "เหนื่อยมาก", "ท้อมาก", "หมดกำลังใจ", "ไม่ไหวแล้ว", "กดดันมาก", "เหนื่อยใจ", "เศร้า",
]

# ใช้ร่วมกับโค้ดเดิมที่อ้างชื่อนี้
CRISIS_KEYWORDS = CRISIS_HIGH_KEYWORDS + CRISIS_MODERATE_KEYWORDS

_SPACES_RE = re.compile(r"[\s​‌‍﻿\.\-_]+")
_REPEAT_RE = re.compile(r"(.)\1{2,}")  # ตัวอักษรซ้ำ 3 ตัวขึ้นไป เช่น "ตายยยย" -> "ตาย"


def _normalize(text: str) -> str:
    """ตัวพิมพ์เล็ก ตัดช่องว่าง/จุด/ขีด (กันการพิมพ์ "อยาก ตาย" หรือ "อ-ย-า-ก-ต-า-ย") และย่อตัวอักษรที่พิมพ์ซ้ำ"""
    t = _REPEAT_RE.sub(r"\1", (text or "").lower())
    return _SPACES_RE.sub("", t)


def _find(text: str, keywords: list[str]) -> str | None:
    raw = (text or "").lower()
    norm = _normalize(text)
    for kw in keywords:
        k = kw.lower()
        if k in raw or _normalize(k) in norm:
            return kw
    return None


_JUMP_RE = re.compile(r"(จะ|ขอ|อยาก)?(กระ)?โดด(จาก|ลง)?(ตึก|สะพาน|คอนโด|ชั้น|หน้าต่าง|ดาดฟ้า)")

# v22 "วิธีการ + ความตั้งใจ" ในข้อความเดียวกัน (เช่น กินยาให้หมดแผง, ยืนรอรถไฟที่ราง) -> HIGH
# ปรับจากข้อที่พลาดในชุด dev เดิม (blind_crisis*.csv) ไม่ได้ใช้ชุด v22 ปรับ
_MEANS_STRONG = ["ยานอนหลับ", "ยาฆ่าหญ้า", "ยาเบื่อหนู", "ยาพิษ", "overdose", "โอดี", "ทั้งแผง", "หมดแผง", "ทั้งกระปุก", "หมดกระปุก",
                 "ทั้งขวด", "ตัดเส้นเลือด", "เส้นเลือดที่ข้อมือ", "รางรถไฟ", "มีดโกน", "คัตเตอร์", "เชือก", "จ่อข้อมือ", "ยาที่สะสม",
                 "เก็บยา", "สะสมยา", "ตุนยา", "ยาเม็ด"]
_INTENT_WORDS = ["จะ", "กำลัง", "คืนนี้", "ตอนนี้", "ไปแล้ว", "ตัดสินใจ", "เตรียม", "เก็บไว้", "สะสม", "วันสุดท้าย", "ลาก่อน",
                 "ขอโทษที่", "ให้หมด", "หมดเลย", "รอ", "เอามา", "แล้ว", "will", "going to", "gonna"]
_HIGH_RE = [
    re.compile(r"(กิน|กลืน|ทาน)ยา\S{0,20}(หมด|ทั้งแผง|ทั้งกระปุก|ทั้งขวด|เกินขนาด|เยอะมาก)"),
    re.compile(r"วันสุดท้ายของ(ฉัน|เรา|ผม|หนู|กู|ชีวิต)"),
    re.compile(r"(กิน|ทาน)ยา\S{0,12}ตาย(เร็ว|ไว|ง่าย|ไม่ทรมาน)"),
    re.compile(r"ไม่เห็น(หนู|เรา|ฉัน|ผม)อีก"),
    re.compile(r"(จะ|ขอ)?จบ(ทุกอย่าง|ชีวิต)?ด้วย(ยา|เชือก|มีด)"),
]
# v22 เพิ่มรูปแบบความสิ้นหวัง/อยากไม่มีตัวตน (MODERATE) ที่ keyword เดิมไม่ครอบคลุม
_MODERATE_EXTRA = ["ไม่ควรมีอยู่", "ไม่ควรเกิด", "ถ้าเราไม่อยู่", "ถ้าฉันไม่อยู่", "ถ้าผมไม่อยู่", "ถ้าหนูไม่อยู่", "ถ้าไม่มีฉัน",
                   "ไม่มีเหตุผลที่จะอยู่", "ไม่มีเหตุผลจะอยู่", "ไม่มีเหตุผลที่ต้องอยู่", "ไม่อยากมีลมหายใจ", "หมดลมหายใจ", "หยุดหายใจ",
                   "อยากหายตัวไป", "ให้ทุกคนลืมเรา", "ให้ทุกคนลืมฉัน", "ตัวปัญหาของ", "อยู่ไปก็เป็นตัวปัญหา", "ไม่มีทางดีขึ้น", "ไม่มีวันดีขึ้น",
                   "จะได้ตายไปเลย", "จะได้ตาย", "ตายไปเลยก็ได้", "hopeless", "no reason to live", "want to disappear",
                   "ไม่มีใครเสียใจถ้า", "คงไม่มีใครเสียใจ", "ไม่อยากอยู่แล้วจริงๆ"]


def _means_and_intent(norm_text: str) -> str | None:
    for m in _MEANS_STRONG:
        if m in norm_text and any(w in norm_text for w in _INTENT_WORDS if w != m):
            return m
    for rx in _HIGH_RE:
        if rx.search(norm_text):
            return rx.pattern[:20]
    return None


def detect_crisis_keyword(text: str) -> dict:
    """ด่านที่ 1: keyword อย่างเดียว คืน {'level', 'matched'}"""
    hit = _find(text, CRISIS_HIGH_KEYWORDS)
    if not hit and _JUMP_RE.search(_normalize(text)):
        hit = "โดดจากที่สูง"
    if not hit:
        hit = _means_and_intent(_normalize(text))
    if hit:
        return {"level": "HIGH", "matched": hit}
    cleaned = text or ""
    for phrase in MODERATE_EXCEPTIONS:
        cleaned = cleaned.replace(phrase, " ")
    hit = _find(cleaned, CRISIS_MODERATE_KEYWORDS) or _find(cleaned, _MODERATE_EXTRA)
    if hit:
        return {"level": "MODERATE", "matched": hit}
    return {"level": "NONE", "matched": None}


def detect_crisis(text: str, use_nlp: bool = True) -> dict:
    """คืน {'level': 'HIGH'|'MODERATE'|'NONE', 'matched': คำที่เจอ, 'source': 'keyword'|'nlp'|None}
    ด่านที่ 1 keyword -> ถ้าไม่เจอ ด่านที่ 2 NLP (ยกระดับได้อย่างเดียว ไม่มีทางลดระดับที่ keyword จับได้)"""
    out = detect_crisis_keyword(text)
    if out["level"] != "NONE":
        return {**out, "source": "keyword"}
    if use_nlp:
        level, score = nlp_crisis_level(text)
        if level != "NONE":
            return {"level": level, "matched": f"nlp:{score:.2f}", "source": "nlp"}
    return {"level": "NONE", "matched": None, "source": None}


def detect_sentiment(text: str) -> str:
    """'crisis' (ทั้ง HIGH และ MODERATE) / 'distress' / 'normal'"""
    if detect_crisis(text)["level"] != "NONE":
        return "crisis"
    if _find(text, DISTRESS_KEYWORDS):
        return "distress"
    return "normal"


# =====================================================================
# ด่านที่ 2: NLP เทียบความคล้ายกับประโยคตัวอย่าง (crisis_examples.py)
# =====================================================================
# ค่าเกณฑ์ปรับจากชุด eval_data/blind_crisis.csv (ชุด dev) เท่านั้น
# ชุด eval_data/blind_crisis_test2.csv ใช้วัดผลครั้งสุดท้าย ห้ามใช้ปรับค่า
NLP_HIGH_MIN = 0.35      # คล้ายกลุ่ม HIGH อย่างน้อยเท่านี้ -> HIGH
NLP_RISK_MIN = 0.22      # คล้ายกลุ่มเสี่ยง (HIGH หรือ MODERATE) อย่างน้อยเท่านี้ -> MODERATE
NLP_SAFE_MARGIN = 0.02   # และต้องคล้ายกลุ่มเสี่ยงมากกว่ากลุ่ม SAFE อย่างน้อยเท่านี้
NLP_MIN_CHARS = 8        # ข้อความสั้นกว่านี้ไม่ใช้ NLP (สั้นเกินจะเทียบได้แม่น)

_crisis_matcher = None


def _get_crisis_matcher():
    global _crisis_matcher
    if _crisis_matcher is None:
        from .crisis_examples import CRISIS_EXAMPLES
        from .nlp import TopicMatcher
        from .topic_examples import TOPIC_EXAMPLES
        # กลุ่ม SAFE = ประโยคไม่เสี่ยงใน crisis_examples.py + ประโยคตัวอย่างปัญหาทั่วไปทุกหัวข้อ (topic_examples.py)
        # ต้องมีกลุ่ม SAFE ใหญ่พอ ไม่อย่างนั้นข้อความปัญหาทั่วไป (เรื่องเรียน เพื่อน เงิน) จะถูกเตือนเกินบ่อยมาก
        safe = list(CRISIS_EXAMPLES["SAFE"]) + [x for sents in TOPIC_EXAMPLES.values() for x in sents]
        _crisis_matcher = TopicMatcher({"HIGH": CRISIS_EXAMPLES["HIGH"], "MODERATE": CRISIS_EXAMPLES["MODERATE"],
                                        "SAFE": safe})
    return _crisis_matcher


def nlp_crisis_scores(text: str) -> dict:
    from .nlp import content_length
    if content_length(text) < NLP_MIN_CHARS:
        return {}
    return _get_crisis_matcher().scores(text)


def nlp_crisis_level(text: str) -> tuple[str, float]:
    s = nlp_crisis_scores(text)
    if not s:
        return "NONE", 0.0
    high, mod, safe = s.get("HIGH", 0.0), s.get("MODERATE", 0.0), s.get("SAFE", 0.0)
    risk = max(high, mod)
    if risk < NLP_RISK_MIN or risk < safe + NLP_SAFE_MARGIN:
        return "NONE", risk
    if high >= NLP_HIGH_MIN and high >= mod:
        return "HIGH", high
    return "MODERATE", risk


# =====================================================================
# บริบท: พูดถึงคนอื่น / ข่าว / นิยาย / การบ้าน (ยังนับเป็นวิกฤต แต่ตอบแบบถามกลับ + แสดงปุ่มสายด่วน)
# =====================================================================
THIRD_PARTY_MARKERS = [
    "ข่าว", "หนัง", "ซีรีส์", "ซีรี่ส์", "ละคร", "นิยาย", "เรื่องสั้น", "การ์ตูน", "อนิเมะ", "เพลง", "สารคดี",
    "ตัวละคร", "ตัวเอก", "พระเอก", "นางเอก", "รายงาน", "การบ้าน", "บทความ", "งานวิจัย", "สถิติ",
    "เพื่อนบอกว่า", "เพื่อนบอก", "เพื่อนเคย", "เพื่อนสนิท", "น้องบอก", "พี่บอก", "เขาบอกว่า",
    "ช่วยเพื่อน", "ช่วยเขา", "my friend", "a friend", "movie", "novel", "news",
]
# คำที่บอกว่าผู้ใช้พูดถึงตัวเอง (ถ้ามี จะไม่ถือว่าเป็นเรื่องของคนอื่น)
SELF_MARKERS = ["ฉันอยาก", "เราอยาก", "ผมอยาก", "หนูอยาก", "กูอยาก", "ตัวเราเอง", "ตัวฉันเอง", "ตัวผมเอง",
                "ฉันก็", "เราก็", "ผมก็", "หนูก็", "i want", "i wanna", "myself"]


def crisis_context(text: str) -> str:
    """'third_party' = พูดถึงข่าว/นิยาย/คนอื่น, 'self' = อื่นๆ (ไม่แน่ใจให้ถือว่าเป็นเรื่องของผู้ใช้เอง)"""
    t = (text or "").lower()
    if any(m in t for m in SELF_MARKERS):
        return "self"
    if any(m in t for m in THIRD_PARTY_MARKERS):
        return "third_party"
    return "self"


# =====================================================================
# การเล่าว่าถูกทำร้าย / ถูกล่วงละเมิด (สำคัญมากกับผู้เยาว์) -> ข้อความตายตัว + ปุ่ม 1300
# =====================================================================
ABUSE_KEYWORDS = [
    "ถูกทำร้ายร่างกาย", "โดนทำร้ายร่างกาย", "ถูกทุบตี", "โดนทุบตี", "พ่อตี", "แม่ตี", "โดนตีจน", "ถูกตีจน",
    "ตีจนเป็นแผล", "ตีจนช้ำ", "เอาไม้ตี", "เอาเข็มขัดตี", "ถูกขังไว้", "โดนขังไว้", "ไม่ให้กินข้าว",
    "ถูกลวนลาม", "โดนลวนลาม", "ถูกล่วงละเมิด", "โดนล่วงละเมิด", "ล่วงละเมิดทางเพศ", "ถูกข่มขืน", "โดนข่มขืน",
    "ถูกจับตัว", "โดนจับหน้าอก", "จับของลับ", "บังคับให้ถอด", "ขอรูปโป๊", "ส่งรูปโป๊", "ขู่จะปล่อยรูป",
    "ถูกบังคับมีเพศสัมพันธ์", "โดนบังคับ",
    "abused", "molested", "raped",
]


def detect_abuse(text: str) -> str | None:
    return _find(text, ABUSE_KEYWORDS)


# =====================================================================
# ความเสี่ยงสะสมทั้งบทสนทนา (สัญญาณเล็กๆ หลายข้อความรวมกัน)
# =====================================================================
CUMULATIVE_WINDOW = 6     # ดูข้อความผู้ใช้ล่าสุดกี่ข้อความ
CUMULATIVE_MIN = 4        # คะแนนรวมถึงเท่านี้ -> ถามเช็กอย่างนุ่มนวล
NLP_SOFT_MIN = 0.14       # คล้ายกลุ่มเสี่ยงระดับอ่อนๆ (ต่ำกว่าเกณฑ์วิกฤต) นับเป็นสัญญาณ


def _signal(text: str) -> int:
    """คะแนนสัญญาณของ 1 ข้อความ: คำแสดงความทุกข์ = 1, NLP คล้ายกลุ่มเสี่ยงแบบอ่อนๆ = 2"""
    pts = 1 if _find(text, DISTRESS_KEYWORDS) else 0
    s = nlp_crisis_scores(text)
    if s and max(s.get("HIGH", 0), s.get("MODERATE", 0)) >= max(NLP_SOFT_MIN, s.get("SAFE", 0)):
        pts += 2
    return pts


def cumulative_risk(user_texts: list[str]) -> int:
    """คะแนนสะสมของข้อความผู้ใช้ล่าสุด (ข้อความสุดท้ายในรายการคือข้อความล่าสุด)"""
    return sum(_signal(t) for t in user_texts[-CUMULATIVE_WINDOW:])


# =====================================================================
# ฟังก์ชันหลักที่ server ใช้: รวมทุกด่าน
# =====================================================================
def assess(text: str, prev_user_texts: list[str] | None = None, age_group: str = "unknown",
           allow_check_in: bool = True, use_nlp: bool = True, second_opinion=None) -> dict:
    """ประเมินความปลอดภัยของข้อความล่าสุด คืน dict
      level        HIGH / MODERATE / NONE (ใช้ใน analytics)
      source       keyword / nlp / gemini / cumulative / abuse / None
      context      self / third_party
      reply_kind   crisis / crisis_third_party / check_in / abuse / None (None = ตอบตามปกติ)
      abuse        คำที่บ่งบอกการถูกทำร้าย (หรือ None)
      reasons      รายการเหตุผลของ guardrail (เก็บลง log)
    second_opinion = ฟังก์ชัน (text) -> 'HIGH'|'MODERATE'|'NONE'|None เช่น Gemini (ยกระดับได้อย่างเดียว)"""
    prev_user_texts = prev_user_texts or []
    reasons = []
    c = detect_crisis(text, use_nlp=use_nlp)
    level, source, matched = c["level"], c["source"], c["matched"]

    if level == "NONE" and second_opinion is not None:
        try:
            g = second_opinion(text)
        except Exception as err:  # ด่านเสริม พังได้ ไม่กระทบด่านหลัก
            print(f"ด่านเสริมตรวจวิกฤตไม่สำเร็จ: {err}")
            g = None
        if g in ("HIGH", "MODERATE"):
            level, source, matched = g, "gemini", "gemini"

    abuse = detect_abuse(text)
    context = crisis_context(text) if level != "NONE" else "self"
    reply_kind = None
    if level != "NONE":
        reply_kind = "crisis_third_party" if context == "third_party" else "crisis"
        reasons.append(f"crisis_{source}")
    elif abuse:
        level, source, reply_kind = "MODERATE", "abuse", "abuse"
        reasons.append("abuse_disclosure")
    elif allow_check_in and use_nlp and _signal(text) > 0 and \
            cumulative_risk(prev_user_texts + [text]) >= CUMULATIVE_MIN:
        level, source, reply_kind = "MODERATE", "cumulative", "check_in"
        reasons.append("cumulative_risk")
    if abuse and reply_kind != "abuse":
        reasons.append("abuse_disclosure")
    if age_group != "adult" and reply_kind:
        reasons.append("minor_or_unknown_age")
    return {"level": level, "matched": matched, "source": source, "context": context,
            "reply_kind": reply_kind, "abuse": abuse, "age_group": age_group, "reasons": reasons}


def has_risk_signal(text: str) -> bool:
    """v17: ข้อความนี้ "ควรส่งให้ Gemini ตรวจวิกฤตซ้ำ" ไหม — มีคำแสดงความทุกข์ หรือ NLP เห็นความคล้ายกลุ่มเสี่ยงอ่อนๆ
    ข้อความทั่วไป (ทักทาย การบ้านเยอะ) ไม่ต้องเรียก เพื่อความเร็วและประหยัดโควตา"""
    if _find(text, DISTRESS_KEYWORDS) or _find(text, ["หมดหวัง", "ไม่มีความหมาย", "ภาระ", "หายไป", "ไม่ตื่น", "เบื่อชีวิต",
                                                        "ไม่อยากอยู่", "อยู่ไปทำไม", "ไม่มีใครต้องการ", "ทำไมต้องเกิด"]):
        return True
    s = nlp_crisis_scores(text)
    return bool(s) and max(s.get("HIGH", 0), s.get("MODERATE", 0)) >= NLP_SOFT_MIN
