"""เกณฑ์คะแนนแบบประเมิน 9Q ของกรมสุขภาพจิต ประเทศไทย
(ต่างจากเกณฑ์ PHQ-9 สากล จึงกำหนดไว้ในชั้นแอปพลิเคชัน)
"""
CUTOFFS = [
    (6, "none"),
    (12, "mild"),
    (18, "moderate"),
    (27, "severe"),
]

SEVERITY_LABEL_TH = {
    "none": "ไม่มีอาการซึมเศร้า",
    "mild": "มีอาการซึมเศร้า ระดับน้อย",
    "moderate": "มีอาการซึมเศร้า ระดับปานกลาง",
    "severe": "มีอาการซึมเศร้า ระดับรุนแรง",
}


def severity_from_score(total_score: int) -> str:
    for max_score, level in CUTOFFS:
        if total_score <= max_score:
            return level
    return "severe"


def score_assessment(answers: list[dict]) -> dict:
    """answers: [{"question_no": int, "option_value": int}, ...] (ต้องมีครบ 9 ข้อ)"""
    total_score = sum(a["option_value"] for a in answers)
    severity_level = severity_from_score(total_score)

    # ข้อ 9 คือคำถามเกี่ยวกับความคิดทำร้ายตนเอง — ต้องตรวจแยกเสมอไม่ว่าคะแนนรวมจะเท่าไหร่
    q9 = next((a for a in answers if a["question_no"] == 9), None)
    self_harm_risk_flag = bool(q9 and q9["option_value"] > 0)

    return {
        "total_score": total_score,
        "severity_level": severity_level,
        "self_harm_risk_flag": self_harm_risk_flag,
    }
