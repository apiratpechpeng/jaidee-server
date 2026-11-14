"""วัดผลแชทบอท "ทั้งระบบ" (แบบที่ผู้ใช้เห็นจริง) ด้วยชุดทดสอบลับ v22 — รัน: python -m backend.evaluate_v22 [ชื่อรายงาน]

ชุดทดสอบใน eval_data/v22/ เขียนขึ้นก่อนเริ่มแก้โค้ดรอบ v22 และ "ห้ามใช้ปรับค่า" (ห้ามดูข้อที่ผิดแล้วแก้ให้ตรง)
ผู้พัฒนา/AI เขียนเอง จึงยังไม่ใช่ข้อมูลจริง ต้องวัดซ้ำด้วยข้อมูลจริงจากหน้า /admin ที่ผู้ตรวจติดป้ายแล้ว
  blind3_topic.csv      125 ข้อ  หัวข้อ 11 กลุ่ม + none (คุยเล่น/เรื่องดี ต้องไม่ถูกจับเป็นปัญหา)
  blind3_crisis.csv      80 ข้อ  วิกฤต 40 (พูดอ้อม) + ไม่วิกฤตที่หน้าตาคล้าย 40
  blind3_multiturn.csv   30 บทสนทนา  หัวข้อสุดท้ายที่ควรตอบ (ต้นตอเผยข้อความถัดไป / ความรู้สึกต่อเรื่องเดิม)
  blind3_clarify.csv     20 ข้อ  ข้อความแรก: ควรถามสำรวจก่อน (yes) หรือไม่ (no)
"""
import contextlib
import csv
import io
import random
import sys
from collections import Counter
from pathlib import Path

from .chatbot import build_reply
from .crisis import assess, detect_sentiment
from .dialogues import answered_yes_to_check
from .eval_data.topic_groups import to_group

D = Path(__file__).parent / "eval_data" / "v22"


# คำเรื่องราวที่ใช้ตรวจว่าบอทหยิบคำของผู้ใช้มาสะท้อนไหม / พูดเกินเรื่องไหม (กำหนดก่อนแก้ v23)
STORY_WORDS = ["สอบ", "เกรด", "การบ้าน", "รายงาน", "อ่านหนังสือ", "เรียน", "แฟน", "พ่อ", "แม่", "ที่บ้าน", "พี่", "น้อง", "เพื่อน", "รุ่นพี่", "ครู",
               "เงิน", "ค่าเทอม", "หนี้", "งาน", "ร้าน", "หัวหน้า", "นอน", "หลับ", "ฝันร้าย", "รูปร่าง", "หน้า", "อ้วน", "สิว", "ผิว", "ฟัน",
               "อนาคต", "คณะ", "มหาลัย", "โรงเรียน", "ห้อง", "ล้อ", "แกล้ง", "ด่า", "เลิก", "ทะเลาะ", "หย่า", "เหงา", "คนเดียว", "ลูกค้า",
               "กลุ่ม", "โพสต์", "คลิป", "รูป", "ตัวเอง", "พอร์ต", "ม็อค"]
ENTITY_WORDS = ["สอบ", "เกรด", "การบ้าน", "แฟน", "พ่อแม่", "ครอบครัว", "ครู", "ค่าเทอม", "หัวหน้า", "โครงงาน", "เพื่อนร่วมงาน", "มือถือ", "เกม"]


def _rows(name):
    with open(D / name, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def run_conv(turns):
    random.seed(0)
    h, prev, out = [], [], []
    for u in turns:
        before = list(h)
        a = assess(u, prev, age_group="unknown", allow_check_in=True)
        if a["reply_kind"] is None and answered_yes_to_check(before, u):
            a = assess(u, prev, age_group="unknown", allow_check_in=False, second_opinion=lambda _t: "MODERATE")
        s = "crisis" if a["reply_kind"] else detect_sentiment(u)
        h.append({"sender": "user", "content": u})
        with contextlib.redirect_stdout(io.StringIO()):
            r = build_reply(h, s, {m["content"] for m in h if m["sender"] == "ai"}, None, a)
        h += [{"sender": "ai", "content": p} for p in r["parts"]]
        prev.append(u)
        out.append((a, r))
    return out


def topic_group(r):
    if r["is_crisis"]:
        return "crisis"
    return to_group(r.get("topic"))


def macro_f1(pairs):
    labels = sorted({g for g, _ in pairs})
    f1s = []
    for l in labels:
        tp = sum(g == l and p == l for g, p in pairs); fp = sum(g != l and p == l for g, p in pairs); fn = sum(g == l and p != l for g, p in pairs)
        pr = tp / (tp + fp) if tp + fp else 0; rc = tp / (tp + fn) if tp + fn else 0
        f1s.append(2 * pr * rc / (pr + rc) if pr + rc else 0)
    return sum(f1s) / len(f1s)


def main(name="v22"):
    lines = [f"# ผลวัดทั้งระบบ ({name}) ชุดทดสอบลับ v22\n"]
    # 1 topic
    pairs, alarms = [], 0
    for row in _rows("blind3_topic.csv"):
        a, r = run_conv([row["text"]])[-1]
        g = topic_group(r); alarms += g == "crisis"
        pairs.append((row["label"], g))
    acc = sum(g == p for g, p in pairs) / len(pairs)
    none_ok = sum(p == "none" for g, p in pairs if g == "none"); none_n = sum(g == "none" for g, _ in pairs)
    lines.append(f"## 1. หัวข้อ (125 ข้อ)\nAccuracy {acc:.0%} · Macro-F1 {macro_f1(pairs):.2f} · คุยเล่น/เรื่องดีไม่ถูกจับเป็นปัญหา {none_ok}/{none_n} · เตือนวิกฤตเกิน {alarms}/125\n")
    # 2 crisis
    tp = fp = fn = tn = 0
    for row in _rows("blind3_crisis.csv"):
        a, r = run_conv([row["text"]])[-1]
        pred, gold = a["level"] != "NONE", row["label"] != "NONE"
        tp += pred and gold; fp += pred and not gold; fn += gold and not pred; tn += not pred and not gold
    pr = tp / (tp + fp) if tp + fp else 0; rc = tp / (tp + fn) if tp + fn else 0
    lines.append(f"## 2. วิกฤต (80 ข้อ)\nRecall {rc:.0%} · Precision {pr:.0%} · F1 {2*pr*rc/(pr+rc) if pr+rc else 0:.2f} · พลาด {fn} · เตือนเกิน {fp}\n")
    # 3 multiturn
    ok = 0; rows = _rows("blind3_multiturn.csv")
    for row in rows:
        a, r = run_conv([t.strip() for t in row["turns"].split("||")])[-1]
        ok += topic_group(r) == row["final_group"]
    lines.append(f"## 3. หลายข้อความ (30 บทสนทนา)\nหัวข้อสุดท้ายถูก {ok}/{len(rows)} ({ok/len(rows):.0%})\n")
    # 4 clarify
    tp = fp = fn = 0; rows = _rows("blind3_clarify.csv")
    for row in rows:
        a, r = run_conv([row["text"]])[-1]
        pred = r["intent"] == "clarify" or (r.get("topic_source") == "dialogue" and r["intent"] not in ("advice",) and "?" not in "")
        gold = row["should_clarify"] == "yes"
        tp += pred and gold; fp += pred and not gold; fn += gold and not pred
    pr = tp / (tp + fp) if tp + fp else 0; rc = tp / (tp + fn) if tp + fn else 0
    lines.append(f"## 4. ถามสำรวจก่อน (20 ข้อ)\nPrecision {pr:.0%} · Recall {rc:.0%}\n")
    # 5 v23 ความเข้าใจเรื่องที่เล่า (กำหนดเกณฑ์ก่อนแก้โค้ด v23): คำตอบแรกต่อข้อความปัญหา
    #   ใช้คำของผู้ใช้ = กล่องแรกมีคำสำคัญ (2 ตัวอักษรขึ้นไป) ที่ผู้ใช้พิมพ์จริงอย่างน้อย 1 คำ จากรายการคำเรื่องราว
    #   พูดเกินเรื่อง = คำตอบพูดถึงคน/เรื่องที่ผู้ใช้ไม่ได้พูดถึงเลย
    used_ok = invent = n = 0
    for row in _rows("blind3_topic.csv"):
        if row["label"] == "none":
            continue
        a, r = run_conv([row["text"]])[-1]
        if r["is_crisis"] or r["intent"] in ("advice",):
            continue
        n += 1
        text = row["text"]
        words_user = [w for w in STORY_WORDS if w in text]
        used_ok += bool(words_user) and any(w in r["parts"][0] for w in words_user)
        reply = " ".join(r["parts"])
        invent += any(w in reply and w not in text for w in ENTITY_WORDS)
    lines.append(f"## 5. ความเข้าใจเรื่องที่เล่า ({n} ข้อความปัญหา)\nกล่องแรกใช้คำของผู้ใช้ {used_ok}/{n} ({used_ok/n:.0%}) · พูดถึงคน/เรื่องที่ผู้ใช้ไม่ได้เล่า {invent}/{n} ({invent/n:.0%})\n")
    text = "\n".join(lines)
    out = Path(__file__).resolve().parent.parent / "eval_reports" / f"{name}.md"
    out.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main(*(sys.argv[1:2] or ["v22"]))
