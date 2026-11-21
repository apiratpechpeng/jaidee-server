"""เว็บเซิร์ฟเวอร์ทั้งหมดของแอป — ใช้ http.server ที่มากับ Python เท่านั้น
(ไม่ใช้ Flask/FastAPI/Express เพื่อไม่ต้อง pip install หรือ npm install เลย)

เซิร์ฟเวอร์ตัวเดียวนี้ทำ 2 หน้าที่พร้อมกัน:
  1) เสิร์ฟไฟล์หน้าเว็บ (index.html, style.css, app.js) จากโฟลเดอร์ frontend/
  2) เป็น REST API ภายใต้ path /api/... ให้หน้าเว็บเรียกใช้ผ่าน fetch()

เพราะอยู่ที่ origin เดียวกัน (พอร์ตเดียวกัน) จึงไม่ต้องกังวลเรื่อง CORS เลย
"""
import json
import mimetypes
import re
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .ai import ai_mode, analyze_assessment, classify_crisis_with_gemini, gemini_crisis_enabled, reply_to_chat
from .chatbot import CHATBOT_BUILD, CHECK_IN_REPLY, MAX_BUBBLES
from .analytics import _safety_cards, build_assessment_output, build_chat_output, log_chat_output, shown_card_types
from .crisis import assess, detect_sentiment, has_risk_signal
from .dialogues import answered_yes_to_check
from . import research_log
from . import admin
from .db import get_conn
from .scoring import SEVERITY_LABEL_TH, score_assessment
from .security import create_session, get_user_id_from_token, hash_password, now_iso, verify_password

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def row(r) -> dict:
    return dict(r) if r is not None else None


def rows(rs) -> list:
    return [dict(r) for r in rs]


# ---------------------------------------------------------------------
# v20 ความยินยอมให้เก็บข้อมูลวิจัย (ดู research_log.py)
# ---------------------------------------------------------------------
def _apply_research_consent(conn, user_id: str, body: dict) -> dict:
    """บันทึกการเลือกของผู้ใช้ ยินยอมได้เมื่อ อายุ 18 ขึ้นไป หรือ อายุต่ำกว่า 18 และผู้ปกครองรับทราบแล้ว"""
    age_band = body.get("age_band") if body.get("age_band") in ("under18", "18plus") else None
    guardian = bool(body.get("guardian_ack"))
    granted = bool(body.get("research_consent")) and (age_band == "18plus" or (age_band == "under18" and guardian))
    conn.execute("UPDATE users SET research_consent = ?, age_band = ?, guardian_ack = ? WHERE user_id = ?",
                 (int(granted), age_band, int(guardian), user_id))
    conn.execute(
        "INSERT INTO consent_logs (user_id, consent_type, is_granted, consent_version, created_at) VALUES (?, 'research_logging', ?, 'v20', ?)",
        (user_id, int(granted), now_iso()),
    )
    return {"research_consent": granted, "age_band": age_band, "guardian_ack": guardian}


def _research_ok(conn, user_id) -> bool:
    r = conn.execute("SELECT research_consent FROM users WHERE user_id = ?", (user_id,)).fetchone()
    return bool(r and r["research_consent"])


def _age_band(conn, user_id):
    r = conn.execute("SELECT age_band FROM users WHERE user_id = ?", (user_id,)).fetchone()
    return r["age_band"] if r else None


# =====================================================================
# Route handlers — แต่ละฟังก์ชันรับ (conn, user_id, params, body) คืนค่า dict ที่จะ
# แปลงเป็น JSON ตอบกลับ ถ้าต้องการ error ให้ raise ApiError(status, "ข้อความ")
# =====================================================================

def h_health(conn, user_id, params, body):
    return {"ok": True, "ai_mode": ai_mode(), "chatbot_build": CHATBOT_BUILD, "hotline": "1323", "research_log": research_log.mode()}


def h_register(conn, user_id, params, body):
    display_name = (body.get("display_name") or "").strip()
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    birth_date = body.get("birth_date") or None
    gender = body.get("gender") or "prefer_not_to_say"
    consent = bool(body.get("consent"))

    if not display_name or not email or not password:
        raise ApiError(400, "กรุณากรอกชื่อ อีเมล และรหัสผ่านให้ครบ")
    if len(password) < 8:
        raise ApiError(400, "รหัสผ่านต้องมีอย่างน้อย 8 ตัวอักษร")
    if not consent:
        raise ApiError(400, "กรุณายินยอมให้เก็บและใช้ข้อมูลก่อนสมัครสมาชิก")

    if conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
        raise ApiError(409, "อีเมลนี้ถูกใช้สมัครแล้ว")

    new_user_id = uuid.uuid4().hex
    ts = now_iso()
    conn.execute(
        """
        INSERT INTO users (user_id, display_name, email, password_hash, birth_date, gender, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (new_user_id, display_name, email, hash_password(password), birth_date, gender, ts, ts),
    )
    conn.execute(
        "INSERT INTO notification_preferences (user_id, updated_at) VALUES (?, ?)",
        (new_user_id, ts),
    )
    conn.execute(
        """
        INSERT INTO consent_logs (user_id, consent_type, is_granted, consent_version, created_at)
        VALUES (?, 'data_collection', 1, 'v1', ?)
        """,
        (new_user_id, ts),
    )
    _apply_research_consent(conn, new_user_id, body)
    conn.commit()

    token = create_session(conn, new_user_id)
    conn.commit()
    user = row(conn.execute("SELECT user_id, display_name, email, birth_date, gender, is_anonymous, research_consent FROM users WHERE user_id = ?", (new_user_id,)).fetchone())
    user["is_anonymous"] = bool(user["is_anonymous"])
    return {"token": token, "user": user}


def h_login(conn, user_id, params, body):
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    if not email or not password:
        raise ApiError(400, "กรุณากรอกอีเมลและรหัสผ่าน")

    user = row(conn.execute(
        "SELECT user_id, display_name, email, password_hash, is_anonymous FROM users WHERE email = ? AND deleted_at IS NULL",
        (email,),
    ).fetchone())

    if not user or not verify_password(password, user["password_hash"]):
        raise ApiError(401, "อีเมลหรือรหัสผ่านไม่ถูกต้อง")

    token = create_session(conn, user["user_id"])
    conn.commit()
    return {
        "token": token,
        "user": {"user_id": user["user_id"], "display_name": user["display_name"], "email": user["email"], "is_anonymous": bool(user["is_anonymous"])},
    }


# v30 เอาโหมดเข้าใช้งานแบบไม่ระบุตัวตนออก (ผู้พัฒนาขอ) ทุกคนต้องสมัครด้วยอีเมล
# บัญชีไม่ระบุตัวตนเก่าที่ยังล็อกอินค้างอยู่ใช้ต่อได้ แต่สร้างใหม่ไม่ได้แล้ว


def h_get_me(conn, user_id, params, body):
    user = row(conn.execute(
        """
        SELECT user_id, display_name, email, birth_date, gender, is_anonymous,
               emergency_contact_name, emergency_contact_phone, created_at, research_consent, age_band
        FROM users WHERE user_id = ? AND deleted_at IS NULL
        """,
        (user_id,),
    ).fetchone())
    if not user:
        raise ApiError(404, "ไม่พบผู้ใช้")
    user["is_anonymous"] = bool(user["is_anonymous"])
    return user


def h_update_me(conn, user_id, params, body):
    fields = {
        "display_name": body.get("display_name"),
        "birth_date": body.get("birth_date"),
        "gender": body.get("gender"),
        "emergency_contact_name": body.get("emergency_contact_name"),
        "emergency_contact_phone": body.get("emergency_contact_phone"),
    }
    current = row(conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone())
    merged = {k: (v if v is not None else current[k]) for k, v in fields.items()}

    conn.execute(
        """
        UPDATE users SET display_name = ?, birth_date = ?, gender = ?,
          emergency_contact_name = ?, emergency_contact_phone = ?, updated_at = ?
        WHERE user_id = ?
        """,
        (*merged.values(), now_iso(), user_id),
    )
    conn.commit()
    return row(conn.execute(
        "SELECT user_id, display_name, email, birth_date, gender, emergency_contact_name, emergency_contact_phone FROM users WHERE user_id = ?",
        (user_id,),
    ).fetchone())


def h_questions(conn, user_id, params, body):
    questions = rows(conn.execute(
        "SELECT question_id, question_no, question_text_th, is_self_harm_item FROM phq9_questions WHERE is_active = 1 ORDER BY question_no"
    ).fetchall())
    options = rows(conn.execute(
        "SELECT option_id, option_value, option_text_th FROM phq9_options ORDER BY option_value"
    ).fetchall())
    return {"questions": questions, "options": options}


def h_submit_assessment(conn, user_id, params, body):
    answers = body.get("answers") or []
    if len(answers) != 9:
        raise ApiError(400, "กรุณาตอบให้ครบทั้ง 9 ข้อ")

    questions = rows(conn.execute("SELECT question_id, question_no, question_text_th FROM phq9_questions WHERE is_active = 1").fetchall())
    options = rows(conn.execute("SELECT option_id, option_value FROM phq9_options").fetchall())
    question_by_no = {q["question_no"]: q for q in questions}
    option_by_value = {o["option_value"]: o for o in options}

    for a in answers:
        if a.get("question_no") not in question_by_no or a.get("option_value") not in option_by_value:
            raise ApiError(400, "คำตอบไม่ถูกต้อง")

    assessment_id = uuid.uuid4().hex
    started = now_iso()
    conn.execute(
        "INSERT INTO assessments (assessment_id, user_id, status, started_at) VALUES (?, ?, 'in_progress', ?)",
        (assessment_id, user_id, started),
    )
    for a in answers:
        q = question_by_no[a["question_no"]]
        o = option_by_value[a["option_value"]]
        conn.execute(
            "INSERT INTO assessment_answers (assessment_id, question_id, option_id, answered_at) VALUES (?, ?, ?, ?)",
            (assessment_id, q["question_id"], o["option_id"], now_iso()),
        )

    enriched_answers = [{**a, "question_text_th": question_by_no[a["question_no"]]["question_text_th"]} for a in answers]
    result = score_assessment(answers)
    total_score, severity_level, self_harm_risk_flag = result["total_score"], result["severity_level"], result["self_harm_risk_flag"]

    completed = now_iso()
    conn.execute(
        """
        UPDATE assessments SET status = 'completed', completed_at = ?, total_score = ?, severity_level = ?, self_harm_risk_flag = ?
        WHERE assessment_id = ?
        """,
        (completed, total_score, severity_level, int(self_harm_risk_flag), assessment_id),
    )
    conn.commit()

    analysis = analyze_assessment(enriched_answers, total_score, severity_level, self_harm_risk_flag)

    conn.execute(
        """
        INSERT INTO ai_analyses (analysis_id, assessment_id, model_name, model_version, risk_label, risk_probability, summary_text, recommendation_text, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            uuid.uuid4().hex, assessment_id, analysis["model_name"], analysis["model_version"],
            analysis["risk_label"], analysis["risk_probability"], analysis["summary_text"],
            analysis["recommendation_text"], now_iso(),
        ),
    )
    if self_harm_risk_flag:
        conn.execute(
            """
            INSERT INTO emergency_referrals (referral_id, user_id, source_type, source_id, trigger_reason, created_at)
            VALUES (?, ?, 'assessment', ?, ?, ?)
            """,
            (uuid.uuid4().hex, user_id, assessment_id, "แบบประเมิน 9Q ข้อ 9 บ่งชี้ความเสี่ยงทำร้ายตนเอง", now_iso()),
        )
    conn.commit()

    if _research_ok(conn, user_id):
        research_log.log("research_assessment", {
            "participant": research_log.pid(user_id), "assessment_ref": research_log.pid(assessment_id),
            "total_score": total_score, "severity_level": severity_level, "q9_value": _q9_value(answers),
            "answers": sorted(({"q": a["question_no"], "v": a["option_value"]} for a in answers), key=lambda x: x["q"]),
            "age_band": _age_band(conn, user_id), "created_at": completed,
        })

    return {
        "assessment_id": assessment_id,
        "total_score": total_score,
        "severity_level": severity_level,
        "severity_label": SEVERITY_LABEL_TH[severity_level],
        "self_harm_risk_flag": self_harm_risk_flag,
        "ai_mode": ai_mode(),
        "analysis": {
            "risk_label": analysis["risk_label"],
            "risk_probability": analysis["risk_probability"],
            "summary_text": analysis["summary_text"],
            "recommendation_text": analysis["recommendation_text"],
        },
        "show_hotline_banner": self_harm_risk_flag,
        **build_assessment_output(total_score, severity_level, _q9_value(answers), analysis["summary_text"]),
    }


def _q9_value(answers: list[dict]) -> int | None:
    """คะแนนข้อ 9 (ความคิดทำร้ายตนเอง) — ใช้ตัดสินภาวะวิกฤต แยกจากคะแนนรวม"""
    return next((a["option_value"] for a in answers if a["question_no"] == 9), None)


def h_list_assessments(conn, user_id, params, body):
    return rows(conn.execute(
        """
        SELECT a.assessment_id, a.total_score, a.severity_level, a.self_harm_risk_flag,
               a.started_at, a.completed_at, ai.risk_label
        FROM assessments a
        LEFT JOIN ai_analyses ai ON ai.assessment_id = a.assessment_id
        WHERE a.user_id = ? AND a.status = 'completed'
        ORDER BY a.completed_at DESC
        """,
        (user_id,),
    ).fetchall())


def h_get_assessment(conn, user_id, params, body):
    assessment_id = params["id"]
    assessment = row(conn.execute("SELECT * FROM assessments WHERE assessment_id = ? AND user_id = ?", (assessment_id, user_id)).fetchone())
    if not assessment:
        raise ApiError(404, "ไม่พบข้อมูลการประเมินนี้")

    answers = rows(conn.execute(
        """
        SELECT q.question_no, q.question_text_th, o.option_value, o.option_text_th
        FROM assessment_answers aa
        JOIN phq9_questions q ON q.question_id = aa.question_id
        JOIN phq9_options o ON o.option_id = aa.option_id
        WHERE aa.assessment_id = ?
        ORDER BY q.question_no
        """,
        (assessment_id,),
    ).fetchall())

    analysis = row(conn.execute(
        """
        SELECT risk_label, risk_probability, summary_text, recommendation_text, model_name, created_at
        FROM ai_analyses WHERE assessment_id = ? ORDER BY created_at DESC LIMIT 1
        """,
        (assessment_id,),
    ).fetchone())

    output = build_assessment_output(assessment["total_score"], assessment["severity_level"], _q9_value(answers),
                                     (analysis or {}).get("summary_text", ""))
    return {**assessment, "severity_label": SEVERITY_LABEL_TH.get(assessment["severity_level"]), "answers": answers,
            "analysis": analysis, **output}


def h_create_conversation(conn, user_id, params, body):
    conversation_id = uuid.uuid4().hex
    started = now_iso()
    conn.execute(
        "INSERT INTO chat_conversations (conversation_id, user_id, status, started_at) VALUES (?, ?, 'active', ?)",
        (conversation_id, user_id, started),
    )
    conn.commit()
    return {"conversation_id": conversation_id, "status": "active", "started_at": started}


def h_list_conversations(conn, user_id, params, body):
    return rows(conn.execute(
        "SELECT conversation_id, status, started_at, ended_at FROM chat_conversations WHERE user_id = ? ORDER BY started_at DESC",
        (user_id,),
    ).fetchall())


def _assert_owns_conversation(conn, conversation_id, user_id):
    if not conn.execute("SELECT 1 FROM chat_conversations WHERE conversation_id = ? AND user_id = ?", (conversation_id, user_id)).fetchone():
        raise ApiError(404, "ไม่พบบทสนทนานี้")


def h_list_messages(conn, user_id, params, body):
    _assert_owns_conversation(conn, params["id"], user_id)
    return rows(conn.execute(
        "SELECT message_id, sender, content, sentiment_flag, created_at FROM chat_messages WHERE conversation_id = ? ORDER BY created_at ASC, message_id ASC",
        (params["id"],),
    ).fetchall())


# v17 งานเบื้องหลัง (ตอนนี้ใช้กับ Gemini ตรวจวิกฤตเท่านั้น)
_BG = ThreadPoolExecutor(max_workers=4)
GEMINI_CRISIS_WAIT = 8  # วินาที: รอผล Gemini ตรวจวิกฤตได้นานสุดเท่านี้ (นับจากตอนเตรียมคำตอบเสร็จ)


def _age_group(conn, user_id) -> str:
    """'minor' (ต่ำกว่า 18), 'adult' หรือ 'unknown' (ไม่ได้กรอกวันเกิด / ผู้ใช้แบบไม่ระบุตัวตน)
    guardrail ถือว่า unknown = ผู้เยาว์ไว้ก่อน (ปลอดภัยกว่า)"""
    r = conn.execute("SELECT birth_date FROM users WHERE user_id = ?", (user_id,)).fetchone()
    bd = (r["birth_date"] if r else None) or ""
    try:
        y, m, d = (int(x) for x in bd[:10].split("-"))
        if y > 2400:  # กรอกเป็น พ.ศ.
            y -= 543
        today = datetime.now().date()
        age = today.year - y - ((today.month, today.day) < (m, d))
    except ValueError:
        return "unknown"
    return "minor" if age < 18 else "adult"


def h_send_message(conn, user_id, params, body):
    conversation_id = params["id"]
    content = (body.get("content") or "").strip()
    if not content:
        raise ApiError(400, "กรุณาพิมพ์ข้อความ")
    _assert_owns_conversation(conn, conversation_id, user_id)

    # ประวัติก่อนบันทึกข้อความใหม่ (ใช้ดูความเสี่ยงสะสม + ไม่ถามเช็กซ้ำในบทสนทนาเดิม)
    before = rows(conn.execute(
        "SELECT sender, content FROM (SELECT message_id, sender, content, created_at FROM chat_messages "
        "WHERE conversation_id = ? ORDER BY created_at DESC, message_id DESC LIMIT 30) ORDER BY created_at ASC, message_id ASC",
        (conversation_id,),
    ).fetchall())
    prev_user = [m["content"] for m in before if m["sender"] == "user"]
    already_checked_in = any(m["sender"] == "ai" and m["content"] == CHECK_IN_REPLY[1] for m in before)
    age_group = _age_group(conn, user_id)
    t_start = time.perf_counter()
    crisis = assess(content, prev_user, age_group=age_group, allow_check_in=not already_checked_in)
    # v19 ผู้ใช้ตอบรับคำถามเช็กความเสี่ยง (เช่น บอทถามว่า "มีความคิดอยากหายไปไหม" แล้วตอบ "ใช่") -> โหมดวิกฤต
    if crisis["reply_kind"] is None and answered_yes_to_check(before, content):
        crisis = assess(content, prev_user, age_group=age_group, allow_check_in=False,
                        second_opinion=lambda _t: "MODERATE")
        crisis["source"] = "check_answer"  # ไม่ใช่ Gemini แต่เป็นคำตอบของผู้ใช้เอง
        crisis["reasons"] = [r.replace("crisis_gemini", "crisis_check_answer") for r in crisis["reasons"]]
    # v17 ด่าน Gemini ตรวจวิกฤต: เรียก "เฉพาะข้อความที่มีสัญญาณ" และ "ทำพร้อมกัน" กับการเตรียมคำตอบ (ไม่ต้องรอกัน)
    gemini_check = None
    if crisis["reply_kind"] is None and gemini_crisis_enabled() and has_risk_signal(content):
        gemini_check = _BG.submit(classify_crisis_with_gemini, content)
    sentiment = "crisis" if crisis["reply_kind"] else detect_sentiment(content)
    t_assess = time.perf_counter()
    user_cur = conn.execute(
        "INSERT INTO chat_messages (conversation_id, sender, content, sentiment_flag, created_at) VALUES (?, 'user', ?, ?, ?)",
        (conversation_id, content, sentiment, now_iso()),
    )
    user_message_id = user_cur.lastrowid

    if crisis["reply_kind"] in ("crisis", "abuse"):  # ถามเช็ก/เรื่องของคนอื่น ไม่นับเป็นการส่งต่อฉุกเฉิน
        conn.execute(
            """
            INSERT INTO emergency_referrals (referral_id, user_id, source_type, source_id, trigger_reason, created_at)
            VALUES (?, ?, 'chat_message', ?, ?, ?)
            """,
            (uuid.uuid4().hex, user_id, conversation_id,
             "ผู้ใช้เล่าว่าถูกทำร้าย/ไม่ปลอดภัย" if crisis["reply_kind"] == "abuse" else "ข้อความในแชทบอทมีสัญญาณความเสี่ยงทำร้ายตนเอง",
             now_iso()),
        )
        conn.execute("UPDATE chat_conversations SET status = 'escalated' WHERE conversation_id = ?", (conversation_id,))

    history = rows(conn.execute(
        "SELECT sender, content FROM (SELECT message_id, sender, content, created_at FROM chat_messages "
        "WHERE conversation_id = ? ORDER BY created_at DESC, message_id DESC LIMIT 30) ORDER BY created_at ASC, message_id ASC",
        (conversation_id,),
    ).fetchall())

    reply = reply_to_chat(history, sentiment, crisis)
    t_reply = time.perf_counter()
    if gemini_check is not None:
        try:
            level = gemini_check.result(timeout=GEMINI_CRISIS_WAIT)
        except Exception as err:  # หมดเวลา/พัง -> ใช้ผลในเครื่องต่อ
            print(f"Gemini ตรวจวิกฤตไม่ทัน/ไม่สำเร็จ ใช้ผลในเครื่อง: {err}")
            level = None
        if level in ("HIGH", "MODERATE"):
            # Gemini เห็นสัญญาณที่ keyword + NLP พลาด -> เปลี่ยนเป็นคำตอบวิกฤต (ยกระดับได้อย่างเดียว)
            crisis = assess(content, prev_user, age_group=age_group, allow_check_in=False,
                            second_opinion=lambda _t, lv=level: lv)
            sentiment = "crisis"
            conn.execute(
                "INSERT INTO emergency_referrals (referral_id, user_id, source_type, source_id, trigger_reason, created_at) "
                "VALUES (?, ?, 'chat_message', ?, ?, ?)",
                (uuid.uuid4().hex, user_id, conversation_id, "Gemini พบสัญญาณความเสี่ยงทำร้ายตนเอง", now_iso()),
            )
            reply = reply_to_chat(history, sentiment, crisis)
        t_reply = time.perf_counter()

    # คำตอบหนึ่งครั้งอาจมีหลายกล่องข้อความ (กล่องละไม่เกิน ~4 บรรทัด) เก็บเป็นแถวแยกกัน เหมือนคนพิมพ์ส่งทีละข้อความ
    ai_messages = []
    parts = reply.get("reply_parts") or [reply["reply_text"]]
    if sentiment != "crisis" and len(parts) > MAX_BUBBLES:
        parts = parts[:MAX_BUBBLES - 1] + parts[-1:]  # ด่านสุดท้ายกันเกิน: เก็บกล่องแรกๆ กับกล่องท้าย (คำถาม)
    for part in parts:
        cur = conn.execute(
            "INSERT INTO chat_messages (conversation_id, sender, content, sentiment_flag, created_at) VALUES (?, 'ai', ?, 'normal', ?)",
            (conversation_id, part, now_iso()),
        )
        ai_messages.append(row(conn.execute(
            "SELECT message_id, sender, content, created_at FROM chat_messages WHERE message_id = ?", (cur.lastrowid,)
        ).fetchone()))
    # Dual-output: analytics (เก็บ log ไว้วัดผล) + user_response (ข้อความ + ปุ่ม action cards)
    latest_assessment = row(conn.execute(
        "SELECT total_score, severity_level FROM assessments WHERE user_id = ? AND status = 'completed' "
        "ORDER BY completed_at DESC LIMIT 1",
        (user_id,),
    ).fetchone())
    reply["reply_parts"] = [m["content"] for m in ai_messages]
    reply["reply_text"] = "\n\n".join(reply["reply_parts"])
    output = build_chat_output(reply, crisis, sentiment, latest_assessment, shown_card_types(conn, conversation_id))
    log_chat_output(conn, conversation_id, user_message_id, output, now_iso())
    conn.commit()
    a = output["analytics"]
    if _research_ok(conn, user_id):
        research_log.log("research_chat", {
            "participant": research_log.pid(user_id), "conversation": research_log.pid(conversation_id),
            "turn_no": len(prev_user) + 1, "user_text": research_log.clean(content),
            "bot_text": research_log.clean(reply["reply_text"]), "bot_bubbles": len(ai_messages),
            "intent": a["detected_intent"], "topic": a["detected_topic"], "secondary_topic": a.get("detected_secondary_topic"),
            "topic_source": a.get("topic_source"), "topic_confidence": a.get("topic_confidence"),
            "dialogue_id": reply.get("dialogue_id"), "sentiment": sentiment, "crisis_level": a["crisis_level"],
            "crisis_source": a.get("crisis_source"), "reply_kind": crisis.get("reply_kind"), "age_group": a.get("age_group"),
            "age_band": _age_band(conn, user_id), "cards": [c["type"] + ":" + str(c.get("contact_number") or "") for c in output["user_response"]["action_cards"]],
            "model_name": reply.get("model_name"), "chatbot_build": CHATBOT_BUILD, "created_at": now_iso(),
        })
    t_end = time.perf_counter()
    # v17 จับเวลาแต่ละขั้น ถ้ารู้สึกว่าช้า ดูบรรทัดนี้ใน terminal ว่าช้าที่ขั้นไหน
    print(f"⏱️ ใช้เวลา {(t_end - t_start) * 1000:.0f} ms (ตรวจวิกฤต {(t_assess - t_start) * 1000:.0f} | "
          f"เตรียมคำตอบ{'+Gemini' if reply.get('model_name', '').endswith('gemini') or gemini_check else ''} "
          f"{(t_reply - t_assess) * 1000:.0f} | บันทึก {(t_end - t_reply) * 1000:.0f})")
    print(f"💬 ตอบ {len(ai_messages)} กล่อง รูปแบบ={reply.get('layout', '-')} ({reply['model_name']}) "
          f"| intent={a['detected_intent']} crisis={a['crisis_level']} ปุ่ม={[c['type'] for c in output['user_response']['action_cards']]}")

    return {
        "user_message_sentiment": sentiment,
        "show_hotline_banner": sentiment == "crisis",
        "ai_message": ai_messages[-1],  # คงไว้ให้โค้ดเดิมที่ใช้ชื่อนี้ยังทำงานได้
        "ai_messages": ai_messages,
        "analytics": output["analytics"],
        "user_response": output["user_response"],
    }


# ระดับความพึงพอใจแบ่งเป็น 5 ช่วงคะแนน (จากทั้งหมด 0-10) ไม่ใช่ตัวเลขเป๊ะๆ ทีละแต้ม
SATISFACTION_BUCKETS = {"0-1", "2-3", "4-5", "6-8", "9-10"}


def h_submit_satisfaction(conn, user_id, params, body):
    conversation_id = params["id"]
    bucket = (body.get("bucket") or "").strip()
    if bucket not in SATISFACTION_BUCKETS:
        raise ApiError(400, "กรุณาเลือกระดับความพึงพอใจที่ถูกต้อง")
    _assert_owns_conversation(conn, conversation_id, user_id)

    existing = conn.execute(
        "SELECT rating_id FROM chat_satisfaction_ratings WHERE conversation_id = ?", (conversation_id,)
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE chat_satisfaction_ratings SET rating_bucket = ?, created_at = ? WHERE conversation_id = ?",
            (bucket, now_iso(), conversation_id),
        )
    else:
        conn.execute(
            "INSERT INTO chat_satisfaction_ratings (conversation_id, user_id, rating_bucket, created_at) VALUES (?, ?, ?, ?)",
            (conversation_id, user_id, bucket, now_iso()),
        )
    conn.commit()
    if _research_ok(conn, user_id):
        research_log.log("research_rating", {"participant": research_log.pid(user_id), "conversation": research_log.pid(conversation_id),
                                             "bucket": bucket, "created_at": now_iso()})
    return {"ok": True, "bucket": bucket}


def h_list_notifications(conn, user_id, params, body):
    return rows(conn.execute(
        "SELECT notification_id, type, title, body, scheduled_at, sent_at, status FROM notifications WHERE user_id = ? ORDER BY scheduled_at DESC LIMIT 50",
        (user_id,),
    ).fetchall())


def h_mark_read(conn, user_id, params, body):
    cur = conn.execute(
        "UPDATE notifications SET status = 'read' WHERE notification_id = ? AND user_id = ?",
        (params["id"], user_id),
    )
    conn.commit()
    if cur.rowcount == 0:
        raise ApiError(404, "ไม่พบการแจ้งเตือนนี้")
    return {"ok": True}


def h_get_preferences(conn, user_id, params, body):
    return row(conn.execute(
        "SELECT reminder_enabled, day_of_week, time_of_day, timezone FROM notification_preferences WHERE user_id = ?",
        (user_id,),
    ).fetchone())


def h_update_preferences(conn, user_id, params, body):
    current = row(conn.execute("SELECT * FROM notification_preferences WHERE user_id = ?", (user_id,)).fetchone())
    reminder_enabled = body.get("reminder_enabled")
    day_of_week = body.get("day_of_week")
    time_of_day = body.get("time_of_day")

    conn.execute(
        """
        UPDATE notification_preferences SET reminder_enabled = ?, day_of_week = ?, time_of_day = ?, updated_at = ?
        WHERE user_id = ?
        """,
        (
            int(reminder_enabled) if reminder_enabled is not None else current["reminder_enabled"],
            day_of_week if day_of_week is not None else current["day_of_week"],
            time_of_day if time_of_day is not None else current["time_of_day"],
            now_iso(),
            user_id,
        ),
    )
    conn.commit()
    return row(conn.execute(
        "SELECT reminder_enabled, day_of_week, time_of_day, timezone FROM notification_preferences WHERE user_id = ?",
        (user_id,),
    ).fetchone())


def h_get_research_consent(conn, user_id, params, body):
    r = row(conn.execute("SELECT research_consent, age_band, guardian_ack FROM users WHERE user_id = ?", (user_id,)).fetchone())
    return {"research_consent": bool(r["research_consent"]), "age_band": r["age_band"], "guardian_ack": bool(r["guardian_ack"])}


def h_set_research_consent(conn, user_id, params, body):
    out = _apply_research_consent(conn, user_id, body)
    conn.commit()
    return out


def h_export_assessments(conn, user_id, params, body):
    """v30 ประวัติแบบประเมินทั้งหมดพร้อมคำตอบรายข้อ (เก่าไปใหม่) ให้หน้าเว็บสร้างไฟล์ CSV"""
    items = rows(conn.execute(
        "SELECT assessment_id, total_score, severity_level, self_harm_risk_flag, completed_at FROM assessments "
        "WHERE user_id = ? AND status = 'completed' ORDER BY completed_at ASC",
        (user_id,),
    ).fetchall())
    for it in items:
        ans = conn.execute(
            "SELECT q.question_no, o.option_value FROM assessment_answers aa "
            "JOIN phq9_questions q ON q.question_id = aa.question_id JOIN phq9_options o ON o.option_id = aa.option_id "
            "WHERE aa.assessment_id = ?",
            (it["assessment_id"],),
        ).fetchall()
        it["answers"] = {str(r["question_no"]): r["option_value"] for r in ans}
        it["severity_label"] = SEVERITY_LABEL_TH.get(it["severity_level"])
    return items


# ---------------------------------------------------------------------
# v30 สมุดบันทึกความรู้สึก: เขียนระบายเอง บอทไม่ตอบ แต่ตรวจวิกฤตทุกครั้ง
# ---------------------------------------------------------------------
MOODS = {1: "แย่มาก", 2: "ไม่ค่อยดี", 3: "เฉยๆ", 4: "ดี", 5: "ดีมาก"}
JOURNAL_MAX_CHARS = 3000


def h_list_journal(conn, user_id, params, body):
    return rows(conn.execute(
        "SELECT entry_id, mood, content, crisis_level, created_at FROM journal_entries "
        "WHERE user_id = ? ORDER BY created_at DESC LIMIT 100",
        (user_id,),
    ).fetchall())


def h_create_journal(conn, user_id, params, body):
    try:
        mood = int(body.get("mood"))
    except (TypeError, ValueError):
        mood = 0
    if mood not in MOODS:
        raise ApiError(400, "กรุณาเลือกอารมณ์ของวันนี้")
    content = (body.get("content") or "").strip()
    if len(content) > JOURNAL_MAX_CHARS:
        raise ApiError(400, f"เขียนได้ไม่เกิน {JOURNAL_MAX_CHARS} ตัวอักษรต่อครั้ง")

    # ตรวจวิกฤตแบบเดียวกับแชท (keyword + NLP + ถูกทำร้าย) ถ้ามีสัญญาณเสี่ยงและเปิด Gemini ไว้ ให้ Gemini ช่วยดูซ้ำ
    crisis = {"level": "NONE", "source": None, "reply_kind": None, "abuse": None}
    if content:
        second = None
        if gemini_crisis_enabled() and has_risk_signal(content):
            second = classify_crisis_with_gemini
        crisis = assess(content, [], age_group=_age_group(conn, user_id), allow_check_in=False, second_opinion=second)
    flagged = crisis["reply_kind"] is not None

    entry_id = uuid.uuid4().hex
    ts = now_iso()
    conn.execute(
        "INSERT INTO journal_entries (entry_id, user_id, mood, content, crisis_level, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (entry_id, user_id, mood, content, crisis["level"], ts),
    )
    if crisis["reply_kind"] in ("crisis", "abuse"):
        conn.execute(
            "INSERT INTO emergency_referrals (referral_id, user_id, source_type, source_id, trigger_reason, created_at) "
            "VALUES (?, ?, 'journal', ?, ?, ?)",
            (uuid.uuid4().hex, user_id, entry_id,
             "บันทึกความรู้สึกเล่าว่าถูกทำร้าย/ไม่ปลอดภัย" if crisis["reply_kind"] == "abuse"
             else "บันทึกความรู้สึกมีสัญญาณความเสี่ยงทำร้ายตนเอง", ts),
        )
    conn.commit()

    if _research_ok(conn, user_id):
        research_log.log("research_journal", {
            "participant": research_log.pid(user_id), "entry_ref": research_log.pid(entry_id), "mood": mood,
            "text": research_log.clean(content), "text_length": len(content), "crisis_level": crisis["level"],
            "crisis_source": crisis.get("source"), "reply_kind": crisis.get("reply_kind"),
            "age_band": _age_band(conn, user_id), "created_at": ts,
        })

    return {
        "entry": {"entry_id": entry_id, "mood": mood, "content": content, "crisis_level": crisis["level"], "created_at": ts},
        "show_hotline_banner": flagged,
        "action_cards": _safety_cards(crisis) if flagged else [],
    }


def h_delete_journal(conn, user_id, params, body):
    cur = conn.execute("DELETE FROM journal_entries WHERE entry_id = ? AND user_id = ?", (params["id"], user_id))
    conn.commit()
    if cur.rowcount == 0:
        raise ApiError(404, "ไม่พบบันทึกนี้")
    return {"ok": True}


# ---------------------------------------------------------------------
# v21 หน้าผู้ดูแล (/admin) — ดู backend/admin.py
# ---------------------------------------------------------------------
def _admin_call(fn, *args):
    try:
        return fn(*args)
    except admin.AdminError as err:
        raise ApiError(err.status, err.message)
    except (OSError, ValueError) as err:  # ต่อ Supabase ไม่ได้ / ข้อมูลผิดรูป
        raise ApiError(502, f"อ่านข้อมูลจากฐานข้อมูลไม่สำเร็จ: {err}")


def h_admin_login(conn, user_id, params, body):
    return {"token": _admin_call(admin.login, body.get("password") or ""), "hours": admin.TOKEN_HOURS}


def h_admin_summary(conn, user_id, params, body):
    return _admin_call(admin.summary)


def h_admin_rows(conn, user_id, params, body):
    return _admin_call(admin.fetch, params["table"])


def h_admin_label(conn, user_id, params, body):
    return _admin_call(admin.update_labels, params["id"], body)


# =====================================================================
# ตารางเส้นทาง — เรียงจากเฉพาะเจาะจงไปหาทั่วไป (path คงที่ต้องมาก่อน path ที่มีตัวแปร)
# =====================================================================
ROUTES = [
    ("GET", r"^/api/health$", h_health, False, 200),
    ("POST", r"^/api/admin/login$", h_admin_login, False, 200),
    ("GET", r"^/api/admin/summary$", h_admin_summary, "admin", 200),
    ("GET", r"^/api/admin/rows/(?P<table>research_chat|research_assessment|research_rating|research_journal)$", h_admin_rows, "admin", 200),
    ("PATCH", r"^/api/admin/chat/(?P<id>\d+)$", h_admin_label, "admin", 200),
    ("POST", r"^/api/auth/register$", h_register, False, 201),
    ("POST", r"^/api/auth/login$", h_login, False, 200),
    ("GET", r"^/api/users/me$", h_get_me, True, 200),
    ("PATCH", r"^/api/users/me$", h_update_me, True, 200),
    ("GET", r"^/api/research/consent$", h_get_research_consent, True, 200),
    ("PUT", r"^/api/research/consent$", h_set_research_consent, True, 200),
    ("GET", r"^/api/assessments/questions$", h_questions, True, 200),
    ("GET", r"^/api/assessments/export$", h_export_assessments, True, 200),
    ("POST", r"^/api/assessments$", h_submit_assessment, True, 201),
    ("GET", r"^/api/assessments$", h_list_assessments, True, 200),
    ("GET", r"^/api/assessments/(?P<id>[^/]+)$", h_get_assessment, True, 200),
    ("POST", r"^/api/chat/conversations$", h_create_conversation, True, 201),
    ("GET", r"^/api/chat/conversations$", h_list_conversations, True, 200),
    ("GET", r"^/api/chat/conversations/(?P<id>[^/]+)/messages$", h_list_messages, True, 200),
    ("POST", r"^/api/chat/conversations/(?P<id>[^/]+)/messages$", h_send_message, True, 201),
    ("POST", r"^/api/chat/conversations/(?P<id>[^/]+)/satisfaction$", h_submit_satisfaction, True, 201),
    ("GET", r"^/api/journal$", h_list_journal, True, 200),
    ("POST", r"^/api/journal$", h_create_journal, True, 201),
    ("DELETE", r"^/api/journal/(?P<id>[^/]+)$", h_delete_journal, True, 200),
    ("GET", r"^/api/notifications$", h_list_notifications, True, 200),
    ("PATCH", r"^/api/notifications/(?P<id>[^/]+)/read$", h_mark_read, True, 200),
    ("GET", r"^/api/notifications/preferences$", h_get_preferences, True, 200),
    ("PUT", r"^/api/notifications/preferences$", h_update_preferences, True, 200),
]
COMPILED_ROUTES = [
    (method, re.compile(pattern), handler, needs_auth, success_status)
    for method, pattern, handler, needs_auth, success_status in ROUTES
]

STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "application/javascript; charset=utf-8"),
    "/admin": ("admin.html", "text/html; charset=utf-8"),
    "/admin.js": ("admin.js", "application/javascript; charset=utf-8"),
    # ไฟล์สำหรับทำให้ติดตั้งเป็นแอปได้ (PWA) — ดู manifest.json และ sw.js
    "/manifest.json": ("manifest.json", "application/manifest+json; charset=utf-8"),
    "/sw.js": ("sw.js", "application/javascript; charset=utf-8"),
    "/icons/icon-192.png": ("icons/icon-192.png", "image/png"),
    "/icons/icon-512.png": ("icons/icon-512.png", "image/png"),
    "/icons/icon-180.png": ("icons/icon-180.png", "image/png"),
    "/icons/icon-maskable-512.png": ("icons/icon-maskable-512.png", "image/png"),
    "/icons/favicon-32.png": ("icons/favicon-32.png", "image/png"),
}


class Handler(BaseHTTPRequestHandler):
    server_version = "DepressionAppPrototype/1.0"

    def log_message(self, fmt, *args):  # ลด log ที่ไม่จำเป็นให้ terminal อ่านง่ายขึ้น
        print(f"{self.address_string()} - {fmt % args}")

    # ---- helpers ----
    def _send_json(self, status: int, data) -> None:
        payload = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_static(self, filename: str, content_type: str) -> None:
        file_path = FRONTEND_DIR / filename
        if not file_path.exists():
            self._send_json(404, {"error": "ไม่พบไฟล์นี้"})
            return
        data = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def _current_user_id(self, conn):
        auth_header = self.headers.get("Authorization", "")
        token = auth_header[7:] if auth_header.startswith("Bearer ") else None
        return get_user_id_from_token(conn, token)

    def _dispatch(self, method: str) -> None:
        path = self.path.split("?", 1)[0]

        if method == "GET" and path in STATIC_FILES:
            filename, content_type = STATIC_FILES[path]
            self._send_static(filename, content_type)
            return

        for route_method, pattern, handler, needs_auth, success_status in COMPILED_ROUTES:
            if route_method != method:
                continue
            match = pattern.match(path)
            if not match:
                continue

            conn = get_conn()
            try:
                user_id = None
                if needs_auth == "admin":
                    if not admin.check(self.headers.get("X-Admin-Token")):
                        self._send_json(401, {"error": "กรุณาเข้าสู่ระบบผู้ดูแลก่อน"})
                        return
                elif needs_auth:
                    user_id = self._current_user_id(conn)
                    if not user_id:
                        self._send_json(401, {"error": "กรุณาเข้าสู่ระบบก่อนใช้งาน"})
                        return

                body = self._read_json_body() if method in ("POST", "PATCH", "PUT") else {}
                try:
                    result = handler(conn, user_id, match.groupdict(), body)
                    self._send_json(success_status, result)
                except ApiError as err:
                    conn.rollback()
                    self._send_json(err.status, {"error": err.message})
                except Exception as err:  # noqa: BLE001
                    conn.rollback()
                    print(f"เกิดข้อผิดพลาดที่ไม่คาดคิด: {err}")
                    self._send_json(500, {"error": "เกิดข้อผิดพลาดบางอย่างในระบบ กรุณาลองใหม่"})
            finally:
                conn.close()
            return

        # ไม่มี route ไหนตรงเลย
        if path.startswith("/api/"):
            self._send_json(404, {"error": "ไม่พบ endpoint นี้"})
        else:
            self._send_json(404, {"error": "ไม่พบหน้านี้"})

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_PATCH(self):
        self._dispatch("PATCH")

    def do_PUT(self):
        self._dispatch("PUT")

    def do_DELETE(self):
        self._dispatch("DELETE")


def run_server(port: int = 4000):
    mimetypes.init()
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"🚀 เซิร์ฟเวอร์รันที่ http://localhost:{port}")
    print(f"🤖 โหมด AI: {ai_mode()}")
    print(f"💬 แชทบอทเวอร์ชัน: {CHATBOT_BUILD} (ตอบไม่เกิน {MAX_BUBBLES} กล่องต่อครั้ง)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 ปิดเซิร์ฟเวอร์แล้ว")
        server.shutdown()
