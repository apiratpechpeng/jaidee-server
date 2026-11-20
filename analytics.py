"""สร้างข้อมูล analytics + action cards ตามโครงสร้าง Dual-Output (ดูเอกสาร MASTER SYSTEM PROMPT ข้อ 6)

ระบบของเราเป็นคนสร้าง JSON นี้เอง (ไม่ได้ให้ Gemini เขียน) ผลจึงคงที่ ตรวจสอบได้ และใช้ได้แม้ไม่มี API key
ทุกคำตอบของแชทบอทจะถูกบันทึกลงตาราง chat_analytics_logs เพื่อเอาไปวัด Accuracy / Precision / Recall / F1 ภายหลัง

หลักสำคัญ (ข้อ 3 ของเอกสาร)
  - คะแนนรวมแบบประเมินใช้บอก "ระดับอาการซึมเศร้า" เท่านั้น ไม่ใช้ตัดสินภาวะวิกฤต
  - ภาวะวิกฤตดูแยกจาก (ก) คำตอบข้อ 9 ของแบบประเมิน และ (ข) ข้อความในแชท

หมายเหตุ: แอปนี้ใช้แบบประเมิน 9Q ของกรมสุขภาพจิต ช่อง "phq9_score" จึงเก็บคะแนน 9Q (0-27)
และ "depression_severity" แปลงจากเกณฑ์ 9Q (4 ระดับ) จึงไม่มีค่า "Moderately Severe" (ดู severity_scale)
"""
import json

# เบอร์ที่ใช้ในปุ่มสายด่วน (ตรวจสอบแล้ว ณ ต.ค. 2569 — เบอร์เดียวกับในข้อความวิกฤตของ chatbot.py)
HOTLINE_CARDS = [
    {"type": "HOTLINE", "title": "สายด่วนสุขภาพจิต (ฟรี 24 ชม.)", "contact_number": "1323"},
    {"type": "HOTLINE", "title": "สะมาริตันส์ (รับฟัง)", "contact_number": "02-113-6789"},
    {"type": "HOTLINE", "title": "ฉุกเฉินทางการแพทย์", "contact_number": "1669"},
]
ABUSE_CARD = {"type": "HOTLINE", "title": "ศูนย์ช่วยเหลือสังคม (ถูกทำร้าย/ไม่ปลอดภัย)", "contact_number": "1300"}
POLICE_CARD = {"type": "HOTLINE", "title": "แจ้งเหตุด่วนเหตุร้าย", "contact_number": "191"}
SELF_CARE_CARD = {"type": "SELF_CARE", "title": "ลองหายใจผ่อนคลาย 1 นาที", "contact_number": None}
ASSESSMENT_CARD = {"type": "PHQ9_ASSESSMENT", "title": "ทำแบบประเมิน 9Q", "contact_number": None}

# ระดับของ 9Q -> ชื่อระดับตามเอกสาร
SEVERITY_9Q_TO_LABEL = {"none": "Minimal", "mild": "Mild", "moderate": "Moderate", "severe": "Severe"}


def crisis_level_from_q9(q9_value: int | None) -> str:
    """ข้อ 9 (คิดทำร้ายตนเอง): 0 = NONE, 1 = MODERATE, ตั้งแต่ 2 ขึ้นไป = HIGH"""
    if not q9_value:
        return "NONE"
    return "HIGH" if q9_value >= 2 else "MODERATE"


def _severity(assessment: dict | None) -> tuple[int | None, str]:
    if not assessment:
        return None, "N/A"
    return assessment.get("total_score"), SEVERITY_9Q_TO_LABEL.get(assessment.get("severity_level"), "N/A")


def _safety_cards(crisis: dict) -> list[dict]:
    """ปุ่มสายด่วนตามชนิดของ guardrail"""
    kind = crisis.get("reply_kind") or "crisis"
    if kind == "abuse":
        return [dict(ABUSE_CARD), dict(HOTLINE_CARDS[0]), dict(POLICE_CARD)]
    if kind == "check_in":
        return [dict(HOTLINE_CARDS[0])]
    if kind == "crisis_third_party":
        return [dict(HOTLINE_CARDS[0]), dict(HOTLINE_CARDS[1])]
    cards = [dict(c) for c in HOTLINE_CARDS]
    if crisis.get("abuse"):
        cards.insert(1, dict(ABUSE_CARD))  # วิกฤต + เล่าว่าถูกทำร้าย
    return cards


def build_chat_output(reply: dict, crisis: dict, sentiment: str, latest_assessment: dict | None,
                      shown_card_types: set) -> dict:
    """reply = ผลจาก ai.reply_to_chat / crisis = ผลจาก crisis.detect_crisis ของข้อความผู้ใช้
    latest_assessment = ผลแบบประเมินล่าสุดของผู้ใช้ (หรือ None)
    shown_card_types = ชนิดปุ่มที่บทสนทนานี้เคยแสดงแล้ว (ปุ่มดูแลตัวเอง/แบบประเมิน แสดงครั้งเดียวต่อบทสนทนา ไม่ให้ดูยัดเยียด)
    ส่วนปุ่มสายด่วนตอนวิกฤต แสดงทุกครั้งเสมอ"""
    score, severity = _severity(latest_assessment)
    crisis_flag = crisis["level"] != "NONE"

    if crisis_flag:
        cards = _safety_cards(crisis)
    else:
        cards = []
        if sentiment == "distress":
            if "SELF_CARE" not in shown_card_types:
                cards.append(dict(SELF_CARE_CARD))
            # ปุ่มแบบประเมิน: เฉพาะคนที่ยังไม่เคยทำแบบประเมิน
            if not latest_assessment and "PHQ9_ASSESSMENT" not in shown_card_types:
                cards.append(dict(ASSESSMENT_CARD))

    intent = reply.get("intent", "vent")
    if crisis_flag and intent not in ("crisis_third_party", "check_in", "abuse_disclosure"):
        intent = "crisis"
    return {
        "analytics": {
            "phq9_score": score,
            "depression_severity": severity,
            "severity_scale": "9Q" if latest_assessment else None,
            "crisis_flag": crisis_flag,
            "crisis_level": crisis["level"],
            "crisis_matched_keyword": crisis.get("matched"),
            "crisis_source": crisis.get("source"),
            "crisis_context": crisis.get("context"),
            "age_group": crisis.get("age_group", "unknown"),
            "guardrail_reasons": crisis.get("reasons", []) + (["ai_output_blocked"] if reply.get("safety_blocked") else []),
            "detected_intent": intent,
            "detected_topic": None if crisis_flag else reply.get("topic"),
            "topic_source": None if crisis_flag else reply.get("topic_source"),
            "detected_secondary_topic": None if crisis_flag else reply.get("secondary_topic"),
            "topic_confidence": None if crisis_flag else reply.get("confidence"),
            "safety_guardrail_triggered": crisis_flag or bool(reply.get("safety_blocked")),
            "model_name": reply.get("model_name"),
        },
        "user_response": {
            "message": reply.get("reply_text", ""),
            "messages": reply.get("reply_parts") or [reply.get("reply_text", "")],
            "action_cards": cards,
        },
    }


def build_assessment_output(total_score: int, severity_level: str, q9_value: int | None, message: str) -> dict:
    """JSON แบบเดียวกันสำหรับหน้าผลแบบประเมิน (ภาวะวิกฤตดูจากข้อ 9 เท่านั้น ไม่ดูคะแนนรวม)"""
    level = crisis_level_from_q9(q9_value)
    crisis_flag = level != "NONE"
    cards = [dict(c) for c in HOTLINE_CARDS] if crisis_flag else []
    if not crisis_flag and severity_level in ("moderate", "severe"):
        cards.append(dict(HOTLINE_CARDS[0]))  # อาการปานกลางขึ้นไป แนะนำให้ปรึกษา 1323 ด้วย
    return {
        "analytics": {
            "phq9_score": total_score,
            "depression_severity": SEVERITY_9Q_TO_LABEL.get(severity_level, "N/A"),
            "severity_scale": "9Q",
            "crisis_flag": crisis_flag,
            "crisis_level": level,
            "detected_intent": "assessment",
            "safety_guardrail_triggered": crisis_flag,
        },
        "user_response": {"message": message, "action_cards": cards},
    }


def log_chat_output(conn, conversation_id: str, user_message_id: int, output: dict, now: str) -> None:
    """บันทึก 1 แถวต่อ 1 คำตอบ (ไม่เก็บข้อความซ้ำ อ้างอิงข้อความผู้ใช้ด้วย message_id)
    human_crisis_label / human_intent_label ปล่อยว่างไว้ ให้ผู้ตรวจมากรอกภายหลัง เพื่อคำนวณ F1 จากข้อมูลจริง"""
    a = output["analytics"]
    conn.execute(
        """
        INSERT INTO chat_analytics_logs (conversation_id, user_message_id, phq9_score, depression_severity, crisis_flag,
            crisis_level, crisis_source, crisis_context, age_group, guardrail_reasons_json, detected_intent,
            detected_topic, topic_source, safety_guardrail_triggered, model_name, action_cards_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (conversation_id, user_message_id, a["phq9_score"], a["depression_severity"], int(a["crisis_flag"]),
         a["crisis_level"], a.get("crisis_source"), a.get("crisis_context"), a.get("age_group"),
         json.dumps(a.get("guardrail_reasons", []), ensure_ascii=False), a["detected_intent"],
         a["detected_topic"], a["topic_source"], int(a["safety_guardrail_triggered"]), a["model_name"],
         json.dumps(output["user_response"]["action_cards"], ensure_ascii=False), now),
    )


def shown_card_types(conn, conversation_id: str) -> set:
    """ชนิดปุ่มที่บทสนทนานี้เคยแสดงไปแล้ว"""
    types = set()
    for (cards_json,) in conn.execute(
        "SELECT action_cards_json FROM chat_analytics_logs WHERE conversation_id = ?", (conversation_id,)
    ).fetchall():
        types.update(c.get("type") for c in json.loads(cards_json or "[]"))
    return types
