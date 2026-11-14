"""ด่านที่ 2 ของการจับหัวข้อ: NLP ในเครื่อง (ไม่ต้องต่อเน็ต ไม่ต้องใช้ API key)

หลักการ (เทียบความคล้ายของประโยค)
  1) แปลงประโยคเป็น "ชิ้นตัวอักษร" (character n-gram) เช่น "เหงามาก" -> "เห", "หง", "งา", "เหง", "หงา", ...
     ภาษาไทยไม่มีช่องว่างคั่นคำ วิธีนี้จึงไม่ต้องตัดคำก็ใช้ได้ และทนต่อการพิมพ์ผิดเล็กน้อย
  2) ให้น้ำหนักแต่ละชิ้นแบบ TF-IDF: ชิ้นที่เจอในทุกหัวข้อ (เช่น "รู้สึก") มีน้ำหนักน้อย ชิ้นที่เจอเฉพาะบางหัวข้อมีน้ำหนักมาก
  3) เทียบกับ "ประโยคตัวอย่าง" ของแต่ละหัวข้อ (topic_examples.py + scenarios.py) ด้วย cosine similarity
     ได้คะแนน 0-1 ต่อหัวข้อ ยิ่งใกล้ 1 ยิ่งคล้าย

ถ้าติดตั้ง PyThaiNLP (pip install pythainlp) และเปิด USE_PYTHAINLP = True จะเพิ่ม "คำ" ที่ตัดได้เข้าไปด้วย
(ค่าเริ่มต้นปิดไว้ เพราะเกณฑ์คะแนนใน chatbot.py ปรับมาจากแบบไม่ใช้ PyThaiNLP ถ้าเปิดควรรันชุดทดสอบใหม่: python -m backend.test_topics)

อยากให้จับหัวข้อได้แม่นขึ้น: เพิ่มประโยคตัวอย่างใน topic_examples.py (ไม่ต้องแก้ไฟล์นี้)
"""
import math
import re
from collections import Counter

USE_PYTHAINLP = False
NGRAM_SIZES = (2, 3)
# คะแนนของหัวข้อ = ค่าเฉลี่ยของประโยคตัวอย่างที่คล้ายที่สุด TOP_K ประโยค (กันไม่ให้ประโยคเดียวที่บังเอิญคล้ายชนะ)
TOP_K = 2

# คำที่ไม่บอกหัวข้อ ตัดทิ้งก่อนเทียบ (คำลงท้าย / คำขอคำแนะนำ ซึ่งมีในทุกหัวข้อ)
FILLER_PHRASES = [
    "ควรทำยังไงดี", "ควรทำไงดี", "ทำยังไงดี", "ทำไงดี", "ทำอย่างไรดี", "ควรทำอย่างไร", "จะทำยังไงดี",
    "ไม่รู้จะทำยังไง", "ไม่รู้จะทำไง", "ช่วยแนะนำหน่อย", "แนะนำหน่อย", "ขอคำแนะนำ",
    "ครับ", "ค่ะ", "ช่วงนี้", "ตอนนี้", "จริงๆ", "จริง ๆ",
]
# หมายเหตุ: ไม่ใส่คำสั้นอย่าง "คะ" "นะ" "อะ" เพราะไปตัดกลางคำอื่นได้ (เช่น "คะแนน", "อะไร")
_FILLER_RE = re.compile("|".join(sorted(map(re.escape, FILLER_PHRASES), key=len, reverse=True)))
_NON_TEXT_RE = re.compile(r"[\s\.,!?\"'()\[\]{}:;/\\\-_~@#%^&*+=<>|ๆฯ…“”‘’]+")

_word_tokenize = None
if USE_PYTHAINLP:
    try:
        from pythainlp.tokenize import word_tokenize as _word_tokenize  # type: ignore
    except ImportError:
        print("ไม่พบ PyThaiNLP ใช้การเทียบแบบชิ้นตัวอักษรอย่างเดียว (ติดตั้งได้ด้วย pip install pythainlp)")
        _word_tokenize = None


def normalize(text: str) -> str:
    """ตัวพิมพ์เล็ก ตัดคำที่ไม่บอกหัวข้อ ตัดช่องว่าง/เครื่องหมาย"""
    t = (text or "").lower()
    t = _FILLER_RE.sub(" ", t)
    t = _NON_TEXT_RE.sub(" ", t)
    return t.strip()


def features(text: str) -> Counter:
    """แปลงประโยคเป็นชุดชิ้นตัวอักษร (และคำ ถ้าเปิด PyThaiNLP)"""
    t = normalize(text)
    feats = Counter()
    for chunk in t.split():
        for n in NGRAM_SIZES:
            for i in range(len(chunk) - n + 1):
                feats[chunk[i:i + n]] += 1
    if _word_tokenize and t:
        for w in _word_tokenize(t, engine="newmm", keep_whitespace=False):
            if len(w) > 1:
                feats["w:" + w] += 1
    return feats


def content_length(text: str) -> int:
    """ความยาวของเนื้อหาจริง หลังตัดคำลงท้าย/คำขอคำแนะนำ (ใช้ดูว่าข้อความนี้มีเรื่องเล่าอยู่ไหม)"""
    return len(normalize(text).replace(" ", ""))


class TopicMatcher:
    """เก็บประโยคตัวอย่างของทุกหัวข้อ แล้วให้คะแนนความคล้ายของข้อความใหม่"""

    def __init__(self, examples: dict[str, list[str]]):
        docs = [(topic, features(s)) for topic, sents in examples.items() for s in sents if s.strip()]
        n_docs = len(docs)
        df = Counter()
        for _, f in docs:
            df.update(f.keys())
        self.idf = {g: math.log((1 + n_docs) / (1 + c)) + 1 for g, c in df.items()}
        self.docs = [(topic, self._vector(f)) for topic, f in docs]

    def _vector(self, feats: Counter) -> dict:
        # TF แบบ log (คำซ้ำหลายครั้งไม่ได้คะแนนพุ่ง) x IDF แล้วทำให้ยาวเท่ากับ 1 เพื่อคิด cosine ได้ด้วยการคูณตรงๆ
        vec = {g: (1 + math.log(c)) * self.idf.get(g, 0.0) for g, c in feats.items()}
        norm = math.sqrt(sum(v * v for v in vec.values()))
        return {g: v / norm for g, v in vec.items()} if norm else {}

    def scores(self, text: str) -> dict[str, float]:
        """คืน {หัวข้อ: คะแนน 0-1} ของทุกหัวข้อ"""
        q = self._vector(features(text))
        if not q:
            return {}
        per_topic: dict[str, list[float]] = {}
        for topic, d in self.docs:
            small, big = (q, d) if len(q) < len(d) else (d, q)
            sim = sum(v * big.get(g, 0.0) for g, v in small.items())
            per_topic.setdefault(topic, []).append(sim)
        return {t: sum(sorted(s, reverse=True)[:TOP_K]) / min(TOP_K, len(s)) for t, s in per_topic.items()}

    def rank(self, text: str, n: int = 3) -> list[tuple[str, float]]:
        """หัวข้อที่คล้ายที่สุด n อันดับ [(หัวข้อ, คะแนน), ...]"""
        return sorted(self.scores(text).items(), key=lambda kv: kv[1], reverse=True)[:n]


_matcher = None


def get_matcher() -> TopicMatcher:
    """สร้างตัวเทียบครั้งแรกที่เรียกใช้ (ใช้เวลาไม่ถึงวินาที) แล้วใช้ซ้ำ"""
    global _matcher
    if _matcher is None:
        from .topic_examples import TOPIC_EXAMPLES
        from .scenarios import SCENARIOS
        examples = {t: list(s) for t, s in TOPIC_EXAMPLES.items()}
        for topic, _, sentence in SCENARIOS:
            examples.setdefault(topic, []).append(sentence)
        _matcher = TopicMatcher(examples)
    return _matcher
