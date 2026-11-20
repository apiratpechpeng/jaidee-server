"""จับคู่ 48 หัวข้อของระบบ -> 11 กลุ่มกว้างที่ใช้ในชุดทดสอบ blind_topic.csv

ใช้เฉพาะตอนวัดผล (ไม่กระทบการทำงานของแชทบอท)
"other" = หัวข้อที่ไม่มีกลุ่มตรงในชุดทดสอบ ถ้าระบบตอบหัวข้อเหล่านี้ จะนับว่าผิดเสมอ
ตารางนี้ผู้พัฒนาจัดเอง บางหัวข้อจัดได้หลายแบบ (เช่น new_class อาจเป็น loneliness หรือ friend_conflict)
ควรให้ผู้ตรวจอีกคนดูตารางนี้ด้วย
"""

TOPIC_TO_GROUP = {
    "bullying": "bullying", "cyberbullying": "bullying",
    "study_stress": "exam_stress", "exam_fail": "exam_stress", "group_work": "friend_conflict",
    "family_pressure": "family_conflict", "family_conflict": "family_conflict",
    "parent_pressure_teacher": "other",
    "loneliness": "loneliness", "new_class": "loneliness", "excluded_group": "loneliness",
    "friend_drift": "friend_conflict", "toxic_friend": "friend_conflict", "peer_pressure": "friend_conflict",
    "emotional_dumping": "friend_conflict", "people_pleasing": "friend_conflict",
    "relationship": "romantic_breakup",
    "sleep": "sleep_problem",
    "finance": "money_problem", "friend_money": "money_problem", "no_tutoring_money": "money_problem",
    "family_finance_stress": "money_problem", "tuition_guilt": "money_problem", "family_debt": "money_problem",
    "allowance": "money_problem", "lifestyle_gap": "money_problem", "online_scam": "money_problem",
    "salary_short": "money_problem", "no_emergency_savings": "money_problem", "guarantor_debt": "money_problem",
    "appearance": "body_image", "health_body": "other",
    "future": "future_worry",
    "parttime_work": "parttime_work", "work_life_balance": "parttime_work",
    "workload": "other", "no_way_out_workload": "other", "colleague_conflict": "other", "responsibility_pressure": "other", "anxiety": "other",
    "self_worth": "other", "burnout": "other", "screen_addiction": "other", "anger": "other",
    "guilt_shame": "other", "envy_comparison": "other", "grief": "other", "identity_lgbt": "other",
    "student_behavior": "other",
    # v19 หัวข้อใหม่จากคลังบทสนทนา
    "sibling_favoritism": "family_conflict", "dropout_pressure": "family_conflict",
    "unplanned_pregnancy": "other", "family_illness": "other",
}


def to_group(topic: str | None) -> str:
    if not topic:
        return "none"
    return TOPIC_TO_GROUP.get(topic, "other")
