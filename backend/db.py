"""ชั้นเชื่อมต่อฐานข้อมูล — ใช้ SQLite (มากับ Python อยู่แล้ว ไม่ต้องติดตั้งอะไรเพิ่ม
ไม่ต้องลง PostgreSQL, ไม่ต้องสร้างฐานข้อมูลเอง) ข้อมูลทั้งหมดเก็บอยู่ในไฟล์เดียว
คือ depression_app.db ที่จะถูกสร้างขึ้นอัตโนมัติตอนรันครั้งแรก

โครงสร้างตารางแปลงมาจาก schema.sql (เวอร์ชัน PostgreSQL) ที่ออกแบบไว้ก่อนหน้านี้
ปรับชนิดข้อมูลให้เข้ากับ SQLite (เช่น ไม่มี ENUM/UUID จริง จึงใช้ TEXT แทน)
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "depression_app.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    birth_date TEXT,
    gender TEXT NOT NULL DEFAULT 'prefer_not_to_say',
    emergency_contact_name TEXT,
    emergency_contact_phone TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    is_anonymous INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS phq9_questions (
    question_id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_no INTEGER NOT NULL UNIQUE,
    question_text_th TEXT NOT NULL,
    is_self_harm_item INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS phq9_options (
    option_id INTEGER PRIMARY KEY AUTOINCREMENT,
    option_value INTEGER NOT NULL UNIQUE,
    option_text_th TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS assessments (
    assessment_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'in_progress',
    total_score INTEGER,
    severity_level TEXT,
    self_harm_risk_flag INTEGER NOT NULL DEFAULT 0,
    started_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS assessment_answers (
    answer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    assessment_id TEXT NOT NULL REFERENCES assessments(assessment_id) ON DELETE CASCADE,
    question_id INTEGER NOT NULL REFERENCES phq9_questions(question_id),
    option_id INTEGER NOT NULL REFERENCES phq9_options(option_id),
    answered_at TEXT NOT NULL,
    UNIQUE (assessment_id, question_id)
);

CREATE TABLE IF NOT EXISTS ai_analyses (
    analysis_id TEXT PRIMARY KEY,
    assessment_id TEXT NOT NULL REFERENCES assessments(assessment_id) ON DELETE CASCADE,
    model_name TEXT,
    model_version TEXT,
    risk_label TEXT,
    risk_probability REAL,
    summary_text TEXT,
    recommendation_text TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_conversations (
    conversation_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'active',
    started_at TEXT NOT NULL,
    ended_at TEXT
);

CREATE TABLE IF NOT EXISTS chat_messages (
    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL REFERENCES chat_conversations(conversation_id) ON DELETE CASCADE,
    sender TEXT NOT NULL,
    content TEXT NOT NULL,
    sentiment_flag TEXT NOT NULL DEFAULT 'normal',
    created_at TEXT NOT NULL
);

-- บันทึก analytics ของแชทบอท 1 แถวต่อ 1 คำตอบ (ใช้วัด Accuracy / Precision / Recall / F1)
-- ไม่เก็บข้อความซ้ำ อ้างถึงข้อความผู้ใช้ผ่าน user_message_id
-- human_crisis_label / human_intent_label ให้ผู้ตรวจกรอกภายหลัง (ค่าจริง) เพื่อเทียบกับสิ่งที่ระบบทำนาย
CREATE TABLE IF NOT EXISTS chat_analytics_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL REFERENCES chat_conversations(conversation_id) ON DELETE CASCADE,
    user_message_id INTEGER REFERENCES chat_messages(message_id) ON DELETE CASCADE,
    phq9_score INTEGER,
    depression_severity TEXT NOT NULL DEFAULT 'N/A',
    crisis_flag INTEGER NOT NULL DEFAULT 0,
    crisis_level TEXT NOT NULL DEFAULT 'NONE',
    detected_intent TEXT,
    detected_topic TEXT,
    topic_source TEXT,
    safety_guardrail_triggered INTEGER NOT NULL DEFAULT 0,
    model_name TEXT,
    action_cards_json TEXT NOT NULL DEFAULT '[]',
    human_crisis_label TEXT,
    human_intent_label TEXT,
    created_at TEXT NOT NULL
);

-- แบบประเมินความพึงพอใจสั้นๆ ที่โผล่ขึ้นมาระหว่างคุยกับแชทบอท (หลังส่งข้อความครบ 3 ครั้ง)
-- rating_bucket เป็นช่วงคะแนน 0-10 แบบแบ่งเป็น 5 กลุ่ม ไม่ใช่คะแนนเป๊ะๆ ทีละแต้ม
CREATE TABLE IF NOT EXISTS chat_satisfaction_ratings (
    rating_id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL UNIQUE REFERENCES chat_conversations(conversation_id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    rating_bucket TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS emergency_referrals (
    referral_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    source_type TEXT NOT NULL,
    source_id TEXT,
    trigger_reason TEXT NOT NULL,
    hotline_number TEXT NOT NULL DEFAULT '1323',
    status TEXT NOT NULL DEFAULT 'suggested',
    created_at TEXT NOT NULL,
    resolved_at TEXT
);

CREATE TABLE IF NOT EXISTS notification_preferences (
    user_id TEXT PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    reminder_enabled INTEGER NOT NULL DEFAULT 1,
    day_of_week INTEGER NOT NULL DEFAULT 1,
    time_of_day TEXT NOT NULL DEFAULT '19:00',
    timezone TEXT NOT NULL DEFAULT 'Asia/Bangkok',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notifications (
    notification_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    related_assessment_id TEXT,
    title TEXT NOT NULL,
    body TEXT,
    scheduled_at TEXT NOT NULL,
    sent_at TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS consent_logs (
    consent_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    consent_type TEXT NOT NULL,
    is_granted INTEGER NOT NULL,
    consent_version TEXT NOT NULL,
    ip_address TEXT,
    created_at TEXT NOT NULL
);

-- v20 ข้อมูลวิจัย (ใช้เมื่อยังไม่ได้ตั้งค่า Supabase ดู research_log.py)
CREATE TABLE IF NOT EXISTS research_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name TEXT NOT NULL,
    row_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

# คำถามมาตรฐาน 9Q ของกรมสุขภาพจิต (ข้อ 9 คือคำถามเกี่ยวกับความคิดทำร้ายตนเอง)
QUESTIONS_SEED = [
    (1, "เบื่อ ไม่สนใจอยากทำอะไร", 0),
    (2, "ไม่สบายใจ ซึมเศร้า ท้อแท้", 0),
    (3, "หลับยาก หรือหลับๆ ตื่นๆ หรือหลับมากไป", 0),
    (4, "เหนื่อยง่าย หรือไม่ค่อยมีแรง", 0),
    (5, "เบื่ออาหาร หรือกินมากเกินไป", 0),
    (6, "รู้สึกไม่ดีกับตัวเอง คิดว่าตัวเองล้มเหลว หรือทำให้ตนเองหรือครอบครัวผิดหวัง", 0),
    (7, "สมาธิไม่ดีเวลาทำอะไร เช่น ดูโทรทัศน์ ฟังวิทยุ หรือทำงานที่ต้องใช้สมาธิ", 0),
    (8, "พูดหรือเคลื่อนไหวช้าจนคนอื่นสังเกตเห็น หรือกระสับกระส่าย ไม่สามารถอยู่นิ่งได้เหมือนที่เคยเป็น", 0),
    (9, "คิดทำร้ายตนเอง หรือคิดว่าถ้าตายไปคงจะดี", 1),
]

OPTIONS_SEED = [
    (0, "ไม่มีเลย"),
    (1, "เป็นบางวัน (1-7 วัน)"),
    (2, "เป็นบ่อย (มากกว่า 7 วัน)"),
    (3, "เป็นทุกวัน"),
]


def get_conn() -> sqlite3.Connection:
    """เปิดการเชื่อมต่อใหม่ 1 อันต่อ 1 request (ไฟล์ SQLite รองรับหลาย connection พร้อมกันได้)"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _migrate_existing_db(conn) -> None:
    """เผื่อกรณีมีไฟล์ depression_app.db เก่าอยู่แล้วจากก่อนที่จะเพิ่มฟีเจอร์นี้ —
    CREATE TABLE IF NOT EXISTS จะไม่แก้ตารางที่มีอยู่แล้วให้เอง จึงต้องเช็คคอลัมน์เอง
    แล้วเพิ่มด้วย ALTER TABLE ถ้ายังไม่มี (ไม่ต้องลบไฟล์ .db เดิมทิ้ง ข้อมูลเก่าไม่หาย)
    """
    existing_columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    if "is_anonymous" not in existing_columns:
        conn.execute("ALTER TABLE users ADD COLUMN is_anonymous INTEGER NOT NULL DEFAULT 0")
    # v20 ความยินยอมให้เก็บข้อมูลวิจัย: research_consent 0/1, age_band under18/18plus, guardian_ack 0/1
    for col, ddl in (("research_consent", "INTEGER NOT NULL DEFAULT 0"), ("age_band", "TEXT"), ("guardian_ack", "INTEGER NOT NULL DEFAULT 0")):
        if col not in existing_columns:
            conn.execute(f"ALTER TABLE users ADD COLUMN {col} {ddl}")
    # v14: ข้อมูล guardrail ใน log
    log_cols = {row["name"] for row in conn.execute("PRAGMA table_info(chat_analytics_logs)").fetchall()}
    for col in ("crisis_source", "crisis_context", "age_group", "guardrail_reasons_json"):
        if col not in log_cols:
            conn.execute(f"ALTER TABLE chat_analytics_logs ADD COLUMN {col} TEXT")


def init_db() -> None:
    conn = get_conn()
    try:
        conn.executescript(SCHEMA)
        _migrate_existing_db(conn)

        count = conn.execute("SELECT COUNT(*) FROM phq9_questions").fetchone()[0]
        if count == 0:
            conn.executemany(
                "INSERT INTO phq9_questions (question_no, question_text_th, is_self_harm_item) VALUES (?, ?, ?)",
                QUESTIONS_SEED,
            )
            conn.executemany(
                "INSERT INTO phq9_options (option_value, option_text_th) VALUES (?, ?)",
                OPTIONS_SEED,
            )
        conn.commit()
    finally:
        conn.close()
