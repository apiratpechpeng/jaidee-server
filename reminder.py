"""ตัวจัดตารางแจ้งเตือนทำแบบประเมินรายสัปดาห์ — รันเป็น background thread ธรรมดา
(ไม่ต้องใช้ไลบรารีอย่าง APScheduler หรือ node-cron) วนทุก 60 วินาที:
  1) ถ้าวันนี้ตรงกับวันที่ผู้ใช้คนไหนตั้งแจ้งเตือนไว้ และยังไม่เคยสร้างของวันนี้ → สร้างแถวใหม่
  2) แจ้งเตือนที่ถึงเวลาแล้ว → "ส่ง" (ในต้นแบบนี้คือ print ออก terminal)
"""
import threading
import time
import uuid
from datetime import datetime, timezone

from .db import get_conn
from .security import now_iso

CHECK_INTERVAL_SECONDS = 60


def _generate_todays_reminders(conn):
    now = datetime.now()
    day_of_week = (now.weekday() + 1) % 7  # Python: จันทร์=0 ... ปรับให้ 0=อาทิตย์เหมือนฝั่งเว็บ
    today_str = now.date().isoformat()

    prefs = conn.execute(
        """
        SELECT np.user_id, np.time_of_day, u.display_name
        FROM notification_preferences np
        JOIN users u ON u.user_id = np.user_id AND u.deleted_at IS NULL
        WHERE np.reminder_enabled = 1 AND np.day_of_week = ?
        """,
        (day_of_week,),
    ).fetchall()

    for pref in prefs:
        existing = conn.execute(
            """
            SELECT 1 FROM notifications
            WHERE user_id = ? AND type = 'weekly_reminder' AND substr(scheduled_at, 1, 10) = ?
            """,
            (pref["user_id"], today_str),
        ).fetchone()
        if existing:
            continue

        hh, mm = pref["time_of_day"].split(":")[:2]
        scheduled_at = now.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)

        conn.execute(
            """
            INSERT INTO notifications (notification_id, user_id, type, title, body, scheduled_at, status, created_at)
            VALUES (?, ?, 'weekly_reminder', ?, ?, ?, 'pending', ?)
            """,
            (
                uuid.uuid4().hex,
                pref["user_id"],
                "ถึงเวลาทำแบบประเมิน 9Q ประจำสัปดาห์แล้ว",
                f"สวัสดีคุณ {pref['display_name']} อย่าลืมทำแบบประเมินสุขภาพใจประจำสัปดาห์นี้นะคะ ใช้เวลาไม่ถึง 2 นาที",
                scheduled_at.isoformat(),
                now_iso(),
            ),
        )
        print(f"[reminder] สร้างการแจ้งเตือนให้ user {pref['user_id']} เวลา {scheduled_at.isoformat()}")
    conn.commit()


def _deliver_due_notifications(conn):
    due = conn.execute(
        "SELECT notification_id, user_id, title FROM notifications WHERE status = 'pending' AND scheduled_at <= ?",
        (datetime.now().isoformat(),),
    ).fetchall()

    for n in due:
        # TODO: ในระบบจริง เรียก push service / LINE Notify / ส่งอีเมลจริงตรงนี้
        print(f"[notify] ส่งแจ้งเตือน \"{n['title']}\" ให้ user {n['user_id']}")
        conn.execute(
            "UPDATE notifications SET status = 'sent', sent_at = ? WHERE notification_id = ?",
            (now_iso(), n["notification_id"]),
        )
    conn.commit()


def _loop(stop_event: threading.Event):
    while not stop_event.is_set():
        conn = get_conn()
        try:
            _generate_todays_reminders(conn)
            _deliver_due_notifications(conn)
        except Exception as err:  # noqa: BLE001 — ตัวจัดตารางไม่ควรทำให้ทั้งเซิร์ฟเวอร์ล้ม
            print(f"reminder loop error: {err}")
        finally:
            conn.close()
        stop_event.wait(CHECK_INTERVAL_SECONDS)


def start_reminder_scheduler() -> threading.Event:
    stop_event = threading.Event()
    thread = threading.Thread(target=_loop, args=(stop_event,), daemon=True)
    thread.start()
    print("⏰ Reminder scheduler เริ่มทำงานแล้ว (ตรวจทุก 60 วินาที)")
    return stop_event
