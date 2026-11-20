"""ส่งออกข้อความแชทจริงเป็นไฟล์ CSV ให้ผู้เชี่ยวชาญติดป้าย (ไม่มีข้อมูลระบุตัวตน)

วิธีรัน (ที่โฟลเดอร์ simple-python)
    python -m backend.export_for_labeling                  -> eval_reports/labeling_sheet.csv
    python -m backend.export_for_labeling --blind          ซ่อนคำตอบของระบบ (แนะนำ: ผู้ตรวจไม่เห็นว่าระบบทายอะไร)

สิ่งที่ทำเพื่อความเป็นส่วนตัว
  - conversation_id -> รหัสสุ่มแบบย้อนกลับไม่ได้ (privacy.pseudonym)
  - ข้อความผ่าน privacy.scrub (ตัดเบอร์โทร อีเมล ชื่อโรงเรียน ฯลฯ) — ผู้ส่งออกยังต้องอ่านตรวจซ้ำก่อนส่งให้คนนอก
  - ไม่ส่งออก user_id ชื่อ อีเมล วันเกิด

ผู้ตรวจ 2 คน กรอกคอลัมน์ rater1_crisis / rater2_crisis (HIGH / MODERATE / NONE) แยกกันโดยไม่ปรึกษากัน
แล้ววัดความสอดคล้อง:  python -m backend.evaluate --kappa eval_reports/labeling_sheet.csv rater1_crisis rater2_crisis
"""
import csv
import sys
from pathlib import Path

from .db import get_conn
from .privacy import pseudonym, scrub

OUT = Path(__file__).resolve().parent.parent / "eval_reports" / "labeling_sheet.csv"


def main(blind: bool) -> None:
    with get_conn() as conn:
        data = conn.execute(
            """SELECT l.log_id, l.conversation_id, m.content, l.crisis_level, l.crisis_source, l.detected_intent,
                      l.detected_topic, l.age_group
               FROM chat_analytics_logs l JOIN chat_messages m ON m.message_id = l.user_message_id
               ORDER BY l.log_id"""
        ).fetchall()
    OUT.parent.mkdir(exist_ok=True)
    cols = ["log_id", "conversation", "message"]
    if not blind:
        cols += ["system_crisis_level", "system_crisis_source", "system_intent", "system_topic"]
    cols += ["age_group", "rater1_crisis", "rater2_crisis", "rater1_topic", "rater2_topic", "notes"]
    with open(OUT, "w", encoding="utf-8-sig", newline="") as f:  # utf-8-sig = เปิดใน Excel ภาษาไทยไม่เพี้ยน
        w = csv.writer(f)
        w.writerow(cols)
        for r in data:
            row = [r["log_id"], pseudonym(r["conversation_id"]), scrub(r["content"])]
            if not blind:
                row += [r["crisis_level"], r["crisis_source"], r["detected_intent"], r["detected_topic"]]
            row += [r["age_group"], "", "", "", "", ""]
            w.writerow(row)
    print(f"ส่งออก {len(data)} แถว -> {OUT}")


if __name__ == "__main__":
    main(blind="--blind" in sys.argv)
