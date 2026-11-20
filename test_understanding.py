"""v24 ทดสอบ "เข้าใจปัญหา + เล่าหลายเรื่อง + ช่วยหาทางออกทีละขั้น" — รัน: python -m backend.test_understanding

ชุดนี้เป็นชุด dev (ใช้ปรับโค้ดได้) ข้อแรกคือบทสนทนาจริงที่ผู้พัฒนาส่งมาว่าบอทไม่เข้าใจ
กฎเพิ่มจาก test_roleplay: all=ทุกคำต้องอยู่ในคำตอบ, stage=ขั้นที่บอทควรอยู่ (ask/tried/options/plan/multi)
"""
import sys

from .test_roleplay import _run, check

STAGE_MARK = {
    "multi": ("เรื่องไหนก่อน", "เรื่องไหนที่หนักใจที่สุด"),
    "tried": ("ลองทำอะไรไปบ้าง", "เคยลอง", "ได้ลอง", "ลองถาม", "ลองบอก", "ลองคุย", "ลองจัดการ", "เคยบอก", "เคยได้"),
    "options": ("อย่างแรก",),
    "plan": ("ขั้นแรก",),
}

S = [
    ("ตัวอย่างจากผู้พัฒนา: โครงงาน -> ไม่เข้าใจงาน -> พ่อแม่รักแต่น้อง", [
        ("เราเครียดเรื่องโครงงาน", dict(has=["โครงงาน"], not_=["กดดันคุณมาก"], advice=False, ask=True)),
        ("ทำไงดี", dict(advice=False, ask=True, not_=["โพโมโดโร", "25 นาที"], all=["ไม่เข้าใจ"])),
        ("เราไม่เข้าใจงาน", dict(has=["ไม่เข้าใจ"], advice=False, ask=True, stage="tried")),
        ("พ่อแม่ก็รักแต่น้อง ไม่สนใจเรา เราเหมือนเป็นส่วนเกิน", dict(has=["พ่อแม่"], all=["น้อง", "ส่วนเกิน"], not_=["เพื่อน", "กลุ่ม"], ask=True)),
    ]),
    ("หลายเรื่องในข้อความเดียว", [
        ("ช่วงนี้งานเยอะมาก ทะเลาะกับแม่ด้วย แล้วก็นอนไม่หลับ", dict(all=["งาน", "แม่", "นอน"], advice=False, stage="multi")),
        ("เรื่องแม่ก่อน", dict(has=["แม่"], not_=["นอนไม่หลับ"], ask=True, advice=False)),
    ]),
    ("หลายเรื่อง 2", [
        ("เพื่อนในห้องไม่ชวนเราเข้ากลุ่ม แล้วพ่อแม่ก็ทะเลาะกันทุกคืน", dict(all=["เพื่อน", "พ่อแม่"], stage="multi")),
        ("ไม่รู้ หนักทั้งคู่", dict(ask=True, advice=False)),
    ]),
    ("ช่วยหาทางออกทีละขั้น: งานกลุ่ม", [
        ("เพื่อนในกลุ่มไม่ช่วยทำงานเลย เราทำอยู่คนเดียว", dict(has=["กลุ่ม", "คนเดียว"], advice=False, ask=True, not_=["เหงา"])),
        ("ทำไงดี", dict(stage="options", not_=["โพโมโดโร"])),
        ("ลองอันแรก", dict(stage="plan", ask=True)),
    ]),
    ("ช่วยหาทางออกทีละขั้น: ตอบรับข้อเสนอ", [
        ("ช่วงนี้นอนไม่หลับเลย", dict(has=["นอน"], ask=True, advice=False)),
        ("ประมาณสองอาทิตย์แล้ว คิดเรื่องสอบตลอด", dict(ask=True, advice=False)),
        ("อยากได้แนวทาง", dict(stage="options")),
        ("อันที่สองน่าจะได้", dict(stage="plan")),
    ]),
    ("ไม่เข้าใจงาน + ขอแนวทางทันที", [
        ("งานคอมไม่เข้าใจเลยว่าต้องทำอะไร ทำไงดี", dict(has=["ไม่เข้าใจ"], stage="tried", advice=False)),
        ("ยังไม่ได้ถามใครเลย", dict(stage="options")),
    ]),
    ("ปฏิเสธทางเลือก", [
        ("โดนแฟนบอกเลิก เศร้ามาก", dict(has=["เลิก"], ask=True, advice=False, not_=["ทะเลาะ"])),
        ("ทำไงดี", dict(stage="options")),
        ("ทำไม่ได้หรอก", dict(ask=True, not_=["ขั้นแรก"])),
    ]),
    ("ไม่สับสนกับคนไม่เข้าใจเรา", [
        ("ไม่มีใครเข้าใจเราเลย", dict(not_=["โจทย์", "ครูที่สั่งงาน"], ask=True)),
    ]),
]


def main() -> int:
    total = ok = 0
    cases = S
    if len(sys.argv) > 1 and sys.argv[1] == "blind4":
        from .eval_data.v24.blind4 import S as cases  # ชุดลับ: รันเพื่อรายงานผลเท่านั้น
    for name, turns in cases:
        h, prev = [], []
        print(f"\n== {name}")
        for text, rule in turns:
            r = _run(h, prev, text)
            bad = check(r, rule)
            joined = " ".join(r["parts"])
            for w in rule.get("all", []):
                if w not in joined:
                    bad.append(f"ไม่ได้พูดถึง '{w}'")
            if "stage" in rule and not any(m in joined for m in STAGE_MARK[rule["stage"]]):
                bad.append(f"ไม่อยู่ขั้น {rule['stage']}")
            total += 1
            ok += not bad
            print(("  ✓ " if not bad else "  ❌ ") + text)
            for p in r["parts"]:
                print("      บอท:", p)
            for b in bad:
                print("      ->", b)
    print(f"\nสรุป: ผ่าน {ok}/{total} ข้อ")
    return 0 if ok == total else 1


if __name__ == "__main__":
    sys.exit(main())
