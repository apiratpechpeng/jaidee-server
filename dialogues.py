"""คลังบทสนทนา (dialogue library) — v19

ที่มา: ผู้พัฒนาคุยกับ Claude โดยให้ Claude สมมติเป็นบอทใจดี แล้วผู้พัฒนาตัดสินว่า "ผ่าน" ทีละสถานการณ์
(พฤศจิกายน 2569) คำตอบในไฟล์นี้คือแนวคำตอบที่ผ่านแล้ว ปรับเล็กน้อยให้ใช้ได้กว้างขึ้น
(ตัดรายละเอียดที่ผูกกับคนเดียว เช่น "สองเดือน") และให้ตรงกติกาแอป (ไม่เกิน 3 กล่อง ไม่มีตัวหนา/เลขข้อ)

ใช้ทำอะไร
  1) match_dialogue(): ถ้าข้อความผู้ใช้ "คล้าย" ข้อความในคลังมากพอ และบริบทเข้ากัน ใช้คำตอบในคลังเลย
  2) casual_reply(): โหมดคุยเล่น/เรื่องดีๆ (เช่น วันเกิด เกม) ไม่ดึงหัวข้อปัญหามาตอบ
  3) ambiguous_check(): คำพูดกำกวม เช่น "ไม่เหลือใครแล้ว" -> ถามตรงๆ ว่าหมายถึงอะไร (ยังไม่ใส่เบอร์ ตามที่ผู้พัฒนาเลือก)
     ถ้าผู้ใช้ตอบรับ (answered_yes_to_check) server จะเปลี่ยนเป็นโหมดวิกฤตพร้อมเบอร์
  4) dialogue_examples(): ส่งเป็นตัวอย่าง (few-shot) ให้ Gemini ดูน้ำเสียงและความยาว

ข้อห้าม
  - ไม่ใช้กับข้อความวิกฤต (chatbot.py เช็กวิกฤตก่อนเสมอ)
  - ห้ามคัดลอกประโยคจาก eval_data/blind_*.csv มาใส่ (ชุดทดสอบต้องแยกจากชุดสร้าง)
  - คำตอบทั้งหมดยังไม่ผ่านผู้เชี่ยวชาญ ช่อง "status" บอกว่าอันไหนผู้พัฒนาทดสอบผ่านแล้ว (approved) อันไหนเป็นร่าง (draft)

เพิ่มบทสนทนาใหม่: คัดลอกรูปแบบด้านล่าง แล้วรัน python -m backend.test_dialogues

ช่องของแต่ละ turn
  user        ประโยคตัวอย่างของผู้ใช้ (หลายแบบ) ใช้เทียบความคล้าย
  bot         กล่องข้อความของบอท (ไม่เกิน 3 กล่อง) ใส่ {person} ได้ (แทนด้วย แม่/พ่อ/... ที่ผู้ใช้พูดถึง)
  start       True = ใช้เป็นข้อความเปิดเรื่องได้ (ไม่ต้องมีบริบทก่อนหน้า) ถ้าไม่ใส่ ใช้ได้เฉพาะตอนกำลังคุยเรื่องนี้อยู่
  advice      True = ใช้ตอนผู้ใช้ขอคำแนะนำ ("ควรทำไงดี") ระหว่างคุยเรื่องนี้
  need        คำที่ต้องมีในข้อความล่าสุด (คั่นทางเลือกด้วย | และใช้ & ถ้าต้องมีหลายกลุ่ม) กันคำตอบไม่ตรงเรื่อง
  need_history  คำที่ต้องเคยมีในข้อความผู้ใช้ก่อนหน้า (ทุกข้อในรายการ)
  positive    True = ข้อความต้องไม่มีคำแง่ลบ (เช่น "วันเกิด" ที่ดีใจ ไม่ใช่ "วันเกิดไม่มีใครสนใจ")
  check       True = กล่องนี้เป็นคำถามเช็กความเสี่ยง (ถ้าผู้ใช้ตอบรับ -> โหมดวิกฤต)
  if_history  [(คำ, ประโยค)] ถ้าผู้ใช้เคยพูดคำนั้น เติมประโยคต่อท้ายกล่องรองสุดท้าย
  alt_last    กล่องสุดท้ายแบบอื่น ใช้เมื่อบอทยังไม่ได้ถามคำถามเช็ก (เฉพาะ turn ที่ตั้งใจถามซ้ำ)
"""
import math
import re
from collections import Counter

# v23 ไม่ใช้คลังประโยคตายตัวแล้ว (ผู้พัฒนาขอให้บอท "เรียนวิธีตอบ" แทน ดู story.py และ test_roleplay.py)
# โครงสร้างยังรองรับถ้าอยากเพิ่มบทสนทนาพิเศษภายหลัง แต่ chatbot.py ไม่ได้เรียก match_dialogue แล้ว
DIALOGUES = []

# ---------------------------------------------------------------------
# เกณฑ์การจับคู่ (ปรับจากบทสนทนาในคลังเอง ไม่ได้ใช้ชุด blind)
# ---------------------------------------------------------------------
START_MIN = 0.40      # เปิดเรื่องใหม่: ต้องคล้ายประโยคในคลังอย่างน้อยเท่านี้
FOLLOW_MIN = 0.18     # กำลังคุยเรื่องนี้อยู่ (turn ถัดๆ ไป): ใช้เกณฑ์ต่ำกว่า เพราะบริบทช่วยยืนยัน
NEXT_BONUS = 0.10     # turn ถัดไปทันทีได้คะแนนเพิ่ม
CHECK_MARK = "มีความคิดอยากหายไปจากทุกอย่าง"  # ประโยคที่อยู่ในคำถามเช็กความเสี่ยงทุกแบบ

NEGATIVE_WORDS = ["เครียด", "เศร้า", "เสียใจ", "กังวล", "กลัว", "เหนื่อย", "ร้องไห้", "ทะเลาะ", "แย่", "ไม่ไหว",
                  "เจ็บ", "ท้อ", "เหงา", "โกรธ", "ไม่สนใจ", "ไม่มีใคร", "ลำเอียง", "โดน", "อาย", "ผิดหวัง", "ทุกข์",
                  "ป่วย", "โรงพยาบาล", "ตาย", "ไม่มีเวลา", "น้อยใจ", "หงุดหงิด", "รำคาญ", "ไม่ชอบ", "เบื่อ", "ปวด",
                  "ล้อ", "แกล้ง", "คนเดียว", "บูลลี่", "ทิ้ง", "เกลียด", "กลัว", "ทะเลาะ", "ด่า", "หนี้", "ไม่มีเงิน", "สอบตก", "ร้องไห้"]
POSITIVE_WORDS = ["ดีใจ", "สนุก", "ชอบมาก", "มีความสุข", "แฮปปี้", "เริ่ด", "ปัง", "ได้รางวัล", "สุดยอด", "เย้",
                  "ฟิน", "ของขวัญ", "วันเกิด", "ภูมิใจ", "สอบผ่าน", "ได้ที่ 1", "ได้ที่หนึ่ง", "โชคดี", "อร่อย", "น่ารัก", "ชนะ", "เย้"]
# ไม่ใส่คำสั้นที่ซ้อนในคำอื่นบ่อย เช่น "อา" (อาการ) "ตา" (ตาม) "น้า"
PERSON_WORDS = ["แม่", "พ่อ", "ยาย", "ย่า", "ปู่", "พี่สาว", "พี่ชาย", "น้องสาว", "น้องชาย", "พี่", "น้อง", "แฟน", "ป้า", "ลุง"]
PERSON_NOT = ["แม่น้ำ", "แม่ค้า", "พ่อค้า", "พี่เลี้ยง", "พี่น้อง"]

# คำกำกวมที่อาจเป็นสัญญาณเสี่ยงหรือไม่ก็ได้ -> ถามตรงๆ ก่อน (ยังไม่ใส่เบอร์)
AMBIGUOUS_PHRASES = {
    "ไม่เหลือใคร": "รู้สึกว่าไม่มีใครให้พึ่งตอนนี้",
    "ไม่มีใครเหลือ": "รู้สึกว่าไม่มีใครให้พึ่งตอนนี้",
    "ตัวคนเดียวแล้ว": "รู้สึกว่าไม่มีใครให้พึ่งตอนนี้",
    "ไม่อยากอยู่บ้าน": "อยากออกไปจากบ้านที่รู้สึกว่าไม่มีที่ยืน",
    "ไม่อยากอยู่ที่นี่": "อยากออกไปจากที่ที่อยู่ตอนนี้",
    "ไม่อยากกลับบ้าน": "อยากออกไปจากบ้านที่รู้สึกว่าไม่มีที่ยืน",
    "เคว้งคว้าง": "รู้สึกเหมือนไม่มีที่ยึดเหนี่ยว",
    "ไม่มีที่ไป": "รู้สึกว่าไม่มีที่ไหนให้ไป",
    "ไม่รู้จะอยู่ยังไง": "ไม่รู้จะใช้ชีวิตต่อไปยังไงในตอนนี้",
    "ไม่มีใครแล้ว": "รู้สึกว่าไม่มีใครให้พึ่งตอนนี้",
}
AMBIGUOUS_FEEL = "ฟังแล้วรู้สึกได้ว่าตอนนี้มันหนักมากจริงๆ นะครับ ขอบคุณที่ยังบอกผม"
AMBIGUOUS_ASK = ("ผมอยากเข้าใจให้ถูกครับ ที่บอกว่า{phrase} หมายถึง{meaning} "
                 "หรือมีความคิดอยากหายไปจากทุกอย่างด้วยหรือเปล่า บอกตรงๆ ได้เลย ผมรับฟังได้")

AFFIRM_START = ("ใช่", "มี", "คิด", "ก็มี", "ก็คิด", "บางที", "บางครั้ง", "นิดหน่อย", "ค่อนข้าง", "อาจจะ", "เคย", "อืม", "ครับ", "ค่ะ", "yes")

# โหมดคุยเล่น
GREETING_HEADS = ["สวัสดีครับ", "ยินดีเลยครับ", "ไม่เป็นไรเลยครับ", "ได้เลยครับ ขอบคุณที่แวะ"]  # ต้นประโยคทักทาย/ขอบคุณใน chatbot.py
CASUAL_MARKERS = ["สุขสันต์วันเกิด", "พลอยดีใจไปด้วย", "ฟังดูน่าสนใจดีนะครับ", "เจ๋งดีครับ", "ผมเป็นแชทบอท", "ผมยังไม่รู้จัก"]  # v23 คำตอบคุยเล่นรอบก่อน
CASUAL_TRIGGERS = ["แค่ทักมา", "ทักมาเฉยๆ", "คุยเล่น", "ทดสอบ", "test", "ไม่มีอะไรหรอก", "เบื่อๆ เลยทัก"]
BOT_SELF_RE = re.compile(r"(นาย|คุณ|บอท|ใจดี|เธอ|แก)\s*(เคย)?\s*(เล่น|ชอบ|กิน|ดู|ฟัง|ไป|รู้จัก|มี|ทำ)(.*)(ไหม|มั้ย|ป่ะ|ปะ|หรือเปล่า|รึเปล่า|ป่าว|อะไร|ที่ไหน)")
BOT_ACTIONS = ["เล่น", "กิน", "ดู", "ฟัง", "ไป", "ทำ"]
LATIN_NAME_RE = re.compile(r"[A-Za-z][A-Za-z0-9 '\-]{1,40}")
CASUAL_GENERAL = [
    ["ฟังแล้วพลอยดีใจไปด้วยเลยครับ", "เล่าเพิ่มอีกหน่อยได้ไหมครับ ตรงไหนที่ชอบที่สุด"],
    ["ฟังดูสนุกดีนะครับ ผมชอบฟังคุณเล่าแบบนี้", "แล้วต่อจากนั้นเป็นยังไงบ้างครับ"],
    ["น่าสนใจดีครับ ผมเพิ่งรู้เหมือนกัน", "อะไรที่ทำให้คุณชอบเรื่องนี้ครับ เล่าให้ฟังหน่อย"],
]
CASUAL_UNKNOWN = ["{name} ผมยังไม่รู้จักเลยครับ ฟังดูน่าสนใจดี",
                  "ช่วยเล่าให้ฟังหน่อยได้ไหมครับ ว่าเป็นยังไง แล้วอะไรที่ทำให้ชอบ"]
CASUAL_SELF = ["ผมเป็นแชทบอทเลย{verb}เองไม่ได้ครับ แต่ชอบฟังคนเล่าเรื่องแบบนี้นะ",
               "แล้วคุณล่ะครับ ชอบตรงไหนที่สุด เล่าให้ฟังหน่อย"]
CASUAL_SELF_GENERIC = "ผมเป็นแชทบอท เลยไม่ได้มีประสบการณ์แบบนั้นเองครับ แต่ชอบฟังคนเล่าเรื่องแบบนี้นะ"


# ---------------------------------------------------------------------
# เทียบความคล้าย (ชิ้นตัวอักษร 2-3 ตัว + TF-IDF + cosine) ไม่ตัดคำลงท้าย เพราะ turn ขอคำแนะนำต้องใช้คำพวกนั้น
# ---------------------------------------------------------------------
_PUNCT_RE = re.compile(r"[\s\.,!?\"'()\[\]{}:;/\\\-_~@#%^&*+=<>|ๆฯ…“”‘’]+")


def _grams(text: str) -> Counter:
    t = _PUNCT_RE.sub("", (text or "").lower())
    g = Counter()
    for n in (2, 3):
        for i in range(len(t) - n + 1):
            g[t[i:i + n]] += 1
    return g


class _Index:
    def __init__(self):
        sents = [(di, ti, s) for di, d in enumerate(DIALOGUES) for ti, t in enumerate(d["turns"]) for s in t["user"]]
        df = Counter()
        feats = [(di, ti, _grams(s)) for di, ti, s in sents]
        for *_, f in feats:
            df.update(f.keys())
        n = len(feats)
        self.idf = {g: math.log((1 + n) / (1 + c)) + 1 for g, c in df.items()}
        self.items = [(di, ti, self._vec(f)) for di, ti, f in feats]

    def _vec(self, f: Counter) -> dict:
        v = {g: (1 + math.log(c)) * self.idf.get(g, 1.0) for g, c in f.items()}
        norm = math.sqrt(sum(x * x for x in v.values()))
        return {g: x / norm for g, x in v.items()} if norm else {}

    def scores(self, text: str) -> dict[tuple[int, int], float]:
        q = self._vec(_grams(text))
        out: dict[tuple[int, int], float] = {}
        if not q:
            return out
        for di, ti, d in self.items:
            sim = sum(x * d.get(g, 0.0) for g, x in q.items())
            if sim > out.get((di, ti), 0.0):
                out[(di, ti)] = sim
        return out


_index = None


def _get_index() -> _Index:
    global _index
    if _index is None:
        _index = _Index()
    return _index


# ---------------------------------------------------------------------
# ตัวช่วย
# ---------------------------------------------------------------------
def _has_any(text: str, pattern: str | None) -> bool:
    """pattern "ก|ข&ค|ง" = (มี ก หรือ ข) และ (มี ค หรือ ง)"""
    return bool(pattern) and all(any(w and w in text for w in grp.split("|")) for grp in pattern.split("&"))


def is_negative(text: str) -> bool:
    t = (text or "").lower()
    return any(w in t for w in NEGATIVE_WORDS)


def is_positive(text: str) -> bool:
    t = (text or "").lower()
    return any(w in t for w in POSITIVE_WORDS) and not is_negative(t)


def _person(user_texts: list[str]) -> str:
    """คนที่ผู้ใช้พูดถึงล่าสุด (แม่ พ่อ ยาย ...) ไว้แทน {person} ถ้าไม่เจอใช้ "คนที่คุณรัก" """
    for text in reversed(user_texts):
        best = None
        for bad in PERSON_NOT:
            text = text.replace(bad, " " * len(bad))
        for w in PERSON_WORDS:
            pos = text.find(w)
            if pos >= 0 and (best is None or pos < best[0] or (pos == best[0] and len(w) > len(best[1]))):
                best = (pos, w)
        if best:
            return best[1]
    return "คนที่คุณรัก"


def _active(history: list[dict]) -> tuple[int, int] | None:
    """บทสนทนาในคลังที่กำลังคุยอยู่ = turn ล่าสุดที่บอทตอบด้วยข้อความจากคลัง -> (dialogue index, turn index)"""
    bot_lines = [m["content"] for m in history if m["sender"] == "ai"]
    for line in reversed(bot_lines[-10:]):
        for di, d in enumerate(DIALOGUES):
            for ti, t in enumerate(d["turns"]):
                if any(_same(line, b) for b in _bots(t)):
                    return di, ti
    return None


def _same(text: str, b: str) -> bool:
    """กล่องข้อความ b (แม่แบบ อาจมี {person}/{name}) ปรากฏใน text ไหม — เทียบท่อนคงที่ท่อนแรกที่ยาวพอ (30 ตัวอักษร)"""
    frags = [f for f in re.split(r"\{[a-z]+\}", b) if len(f.strip()) >= 10]
    head = (frags[0] if frags else b)[:30]
    return bool(head.strip()) and head in text


def _bots(turn: dict) -> list[str]:
    """กล่องข้อความทุกแบบของ turn นี้ (แบบทั่วไป + แบบตรงตามบทบาทสมมติ)"""
    return list(turn["bot"]) + [b for v in turn.get("exact", []) for b in v["bot"]]


def _render(turn: dict, user_texts: list[str], prev_bot: str) -> list[str]:
    person = _person(user_texts)
    last = (user_texts[-1] if user_texts else "").lower()
    # v22.1 ถ้าผู้ใช้พูดรายละเอียดเดียวกับตอนเล่นบทบาทสมมติ (เช่น "สองเดือน" "robux") ใช้คำตอบตามบทนั้นตรงๆ
    bot = next((v["bot"] for v in turn.get("exact", []) if _has_any(last, v["need"])), turn["bot"])
    parts = [b.format(person=person) for b in bot]
    history_text = " ".join(user_texts[:-1])
    for pattern, sentence in turn.get("if_history", []):
        if _has_any(history_text, pattern) and len(parts) >= 2:
            parts[-2] = parts[-2] + " " + sentence
    if turn.get("alt_last") and CHECK_MARK not in prev_bot:
        parts[-1] = turn["alt_last"]
    return parts


def _turn_ok(turn: dict, last: str, history_text: str, advice: bool) -> bool:
    if turn.get("need") and not _has_any(last, turn["need"]):
        return False
    if turn.get("need_not") and _has_any(last, turn["need_not"]):
        return False
    if any(not _has_any(history_text, p) for p in turn.get("need_history", [])):
        return False
    if turn.get("positive") and is_negative(last):
        return False
    if turn.get("advice") and not advice:
        return False
    return True


# ---------------------------------------------------------------------
# ฟังก์ชันที่ chatbot.py เรียก
# ---------------------------------------------------------------------
def match_dialogue(history: list[dict], advice: bool) -> dict | None:
    """หา turn ในคลังที่ตรงกับข้อความล่าสุด คืน {'id','turn','parts','topic','score','casual','check'} หรือ None"""
    user_texts = [m["content"] for m in history if m["sender"] == "user"]
    if not user_texts:
        return None
    last = user_texts[-1].lower()
    history_text = " ".join(user_texts[:-1]).lower()
    used = "\n".join(m["content"] for m in history if m["sender"] == "ai")
    prev_bot = next((m["content"] for m in reversed(history) if m["sender"] == "ai"), "")
    active = _active(history)
    scores = _get_index().scores(last)
    best = None
    for di, d in enumerate(DIALOGUES):
        for ti, turn in enumerate(d["turns"]):
            if not _turn_ok(turn, last, history_text, advice):
                continue
            if any(_same(used, b) for b in _bots(turn)):
                continue  # ตอบไปแล้ว ไม่ซ้ำ
            s = scores.get((di, ti), 0.0)
            in_flow = active is not None and active[0] == di and ti > active[1]
            if in_flow:
                s += NEXT_BONUS if ti == active[1] + 1 else 0.0
                if turn.get("advice"):
                    s = max(s, FOLLOW_MIN + 0.01)  # ขอคำแนะนำระหว่างคุยเรื่องนี้ = ตรง turn นี้เสมอ
                ok = s >= FOLLOW_MIN
            else:
                ok = turn.get("start", False) and s >= START_MIN
            if ok and (best is None or s > best[0]):
                best = (s, di, ti)
    if not best:
        return None
    s, di, ti = best
    d, turn = DIALOGUES[di], DIALOGUES[di]["turns"][ti]
    return {"id": d["id"], "turn": ti, "parts": _render(turn, user_texts, prev_bot), "topic": d.get("topic"),
            "score": round(s, 3), "casual": d.get("casual", False), "check": turn.get("check", False),
            "status": turn.get("status", d.get("status", "draft"))}


def _all_casual_lines() -> list[str]:
    lines = [b for d in DIALOGUES if d.get("casual") for t in d["turns"] for b in _bots(t)]
    lines += [b for pair in CASUAL_GENERAL for b in pair] + CASUAL_UNKNOWN + CASUAL_SELF
    return lines


def casual_reply(history: list[dict], used_text: str) -> list[str] | None:
    """คุยเล่น: ข้อความแง่บวก หรือคุยเล่นต่อจากรอบก่อน (และข้อความนี้ไม่มีคำแง่ลบ) คืนกล่องข้อความหรือ None"""
    user_texts = [m["content"] for m in history if m["sender"] == "user"]
    if not user_texts:
        return None
    last = user_texts[-1].strip()
    if is_negative(last):
        return None
    from .story import kinds_of
    if [k for k in kinds_of(last) if k not in ("result", "dream", "future", "ability")]:
        return None  # v25 มีเรื่องปัญหาในข้อความ (เช่น "พอจะคุยเรื่องวันเกิดตัวเองก็ปัดบทสนทนาหนี") ไม่ใช่คุยเล่น
    prev_bot = next((m["content"] for m in reversed(history) if m["sender"] == "ai"), "")
    # คำตอบรอบก่อนทั้งชุด (หลายกล่อง)
    prev_turn = []
    for m in reversed(history[:-1]):
        if m["sender"] != "ai":
            break
        prev_turn.append(m["content"])
    prev_all = " ".join(prev_turn)
    in_casual = any(_same(prev_all, x) for x in _all_casual_lines()) or any(k in prev_all for k in CASUAL_MARKERS)
    if not (in_casual or is_positive(last) or BOT_SELF_RE.search(last.lower()) or any(w in last.lower() for w in CASUAL_TRIGGERS)):
        return None
    # v22 ไม่กระโดดเข้าโหมดคุยเล่นกลางเรื่องปัญหา (เช่น "เห็นเพื่อนได้รางวัลกันหมด" ต่อจาก "รู้สึกไม่ดีพอ")
    if not in_casual and len(user_texts) > 1 and any(is_negative(t) for t in user_texts[:-1]):
        return None
    if not in_casual and len(user_texts) > 1 and prev_bot and not any(prev_bot.startswith(g[:12]) for g in GREETING_HEADS):
        return None

    m = BOT_SELF_RE.search(last.lower())
    if m:
        action = next((v for v in BOT_ACTIONS if v in m.group(0)), None)
        first = CASUAL_SELF[0].format(verb=action) if action else CASUAL_SELF_GENERIC
        second = "แล้วคุณเล่นอะไรบ่อยที่สุดครับ เล่าให้ฟังหน่อย" if action == "เล่น" else CASUAL_SELF[1]
        return [first, second]
    names = [x.strip() for x in LATIN_NAME_RE.findall(last) if len(x.strip()) >= 3]
    # ชื่อที่ไม่รู้จัก: ใช้เมื่อข้อความแทบมีแต่ชื่อ หรือ "เล่น <ชื่อ>" (ไม่ใช่ "เพื่อนเติม robux ให้" ที่ควรสะท้อนเรื่องเล่า)
    names = [n for n in names if len(n) >= 0.5 * len(last.strip()) or re.search("เล่น\\s*" + re.escape(n), last)]
    if names:
        name = max(names, key=len)
        first = CASUAL_UNKNOWN[0].format(name=name)
        if first not in used_text:
            return [first, CASUAL_UNKNOWN[1]]
    # v23 เรื่องดีๆ: สะท้อนด้วยรายละเอียดที่ผู้ใช้เล่า (วันเกิด ของขวัญ สอบผ่าน ฯลฯ) แทนประโยคกลาง
    from .story import to_you, clean
    low = clean(last).lower()
    if "วันเกิด" in low and "สุขสันต์วันเกิด" not in used_text:
        extra = " ได้ของขวัญเยอะขนาดนี้ แสดงว่าเพื่อนๆ รักและเห็นคุณมากเลย ฟังแล้วพลอยยิ้มตามไปด้วยครับ" if "ของขวัญ" in low else " ขอให้วันนี้เป็นวันที่ดีของคุณนะครับ"
        q = "ของขวัญชิ้นไหนที่ถูกใจที่สุดครับ แล้ววันนี้ได้ฉลองอะไรกับเพื่อนๆ บ้างไหม" if "ของขวัญ" in low else "วันนี้ได้ทำอะไรพิเศษบ้างไหมครับ"
        return ["สุขสันต์วันเกิดนะครับ!" + extra, q]
    echo = to_you(clean(last))
    if 4 <= len(echo) <= 60 and not BOT_SELF_RE.search(low):
        lines = [f"{echo} ฟังแล้วพลอยดีใจไปด้วยเลยครับ", f"{echo} ฟังดูน่าสนใจดีนะครับ", f"{echo} เจ๋งดีครับ"]
        qs = ["เล่าเพิ่มอีกหน่อยได้ไหมครับ ตรงไหนที่ชอบที่สุด", "แล้วเป็นยังไงต่อครับ เล่าให้ฟังหน่อย", "อะไรที่ทำให้คุณชอบเรื่องนี้ครับ"]
        k = sum(1 for x in ("พลอยดีใจไปด้วย", "ฟังดูน่าสนใจดีนะครับ", "เจ๋งดีครับ") if x in used_text) % 3
        return [lines[k], qs[k]]
    for pair in CASUAL_GENERAL:
        if pair[0] not in used_text:
            return list(pair)
    return list(CASUAL_GENERAL[0])


def ambiguous_check(history: list[dict], used_text: str) -> list[str] | None:
    """คำกำกวม (ไม่เหลือใคร / ไม่อยากอยู่บ้าน / เคว้งคว้าง) -> ถามตรงๆ หนึ่งครั้งต่อบทสนทนา ยังไม่ใส่เบอร์"""
    last = next((m["content"] for m in reversed(history) if m["sender"] == "user"), "").lower()
    if CHECK_MARK in used_text:
        return None  # ถามไปแล้วในบทสนทนานี้ ไม่ถามซ้ำ
    for phrase, meaning in AMBIGUOUS_PHRASES.items():
        if phrase in last:
            return [AMBIGUOUS_FEEL, AMBIGUOUS_ASK.format(phrase=phrase, meaning=meaning)]
    return None


def answered_yes_to_check(history_before: list[dict], text: str) -> bool:
    """ผู้ใช้ตอบรับคำถามเช็กความเสี่ยงไหม (ข้อความบอทล่าสุดเป็นคำถามเช็ก และคำตอบขึ้นต้นแบบตอบรับ ไม่มีคำปฏิเสธ)
    เช่น "ใช่" "มีบ้าง" "บางทีก็คิด" -> True / "ไม่ได้คิดแบบนั้น" "แค่ไม่มีใครพึ่ง" -> False"""
    last_ai = next((m["content"] for m in reversed(history_before) if m["sender"] == "ai"), "")
    if CHECK_MARK not in last_ai:
        return False
    t = _PUNCT_RE.sub(" ", (text or "").lower()).strip()
    if not t or "ไม่" in t or "แค่" in t[:6]:
        return False
    return t.startswith(AFFIRM_START) or any(w in t for w in ("อยากหายไป", "คิดอยู่", "ก็มีบ้าง", "มีบ้าง", "คิดบ่อย"))


def dialogue_examples(history: list[dict], n: int = 2) -> list[tuple[str, str]]:
    """ตัวอย่างคำตอบที่ใกล้ข้อความล่าสุดที่สุด n คู่ [(ผู้ใช้, บอท)] สำหรับส่งให้ Gemini ดูน้ำเสียง/ความยาว"""
    last = next((m["content"] for m in reversed(history) if m["sender"] == "user"), "")
    scores = sorted(_get_index().scores(last).items(), key=lambda kv: kv[1], reverse=True)
    out = []
    for (di, ti), s in scores[:n]:
        if s < FOLLOW_MIN:
            break
        t = DIALOGUES[di]["turns"][ti]
        out.append((t["user"][0], " / ".join(b.replace("{person}", "แม่") for b in t["bot"])))
    return out
