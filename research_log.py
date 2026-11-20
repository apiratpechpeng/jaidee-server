"""v20 เก็บข้อมูลการตอบของผู้ใช้ (เฉพาะคนที่กดยินยอม) ไว้ใช้วัดผลโครงงาน

ทำไมต้องแยกไฟล์นี้: เว็บบน Render แบบฟรีจะล้างไฟล์ depression_app.db ทุกครั้งที่รีสตาร์ต
ข้อมูลวิจัยจึงส่งไปเก็บที่ฐานข้อมูลภายนอก (Supabase) ซึ่งไม่หายตอนรีสตาร์ต

ตั้งค่า (ใน Render -> Environment) ถ้าไม่ตั้ง จะเก็บลงตาราง research_logs ในไฟล์ .db แทน (ใช้ตอนทดสอบในคอม)
  SUPABASE_URL           เช่น https://abcdxyz.supabase.co
  SUPABASE_SERVICE_KEY   คีย์ service_role (ห้ามใส่ในโค้ดหรือ GitHub เด็ดขาด)
  RESEARCH_SALT          ข้อความลับอะไรก็ได้ ใช้ทำรหัสแทนตัวตน (ตั้งครั้งเดียวแล้วอย่าเปลี่ยน)

สิ่งที่เก็บ: ข้อความที่ผู้ใช้พิมพ์ (ลบเบอร์โทร อีเมล ชื่อ โรงเรียน ออกก่อนด้วย privacy.scrub) + คำตอบบอท + ผลวิเคราะห์
ไม่เก็บ: ชื่อที่แสดง อีเมล วันเกิด user_id จริง (ใช้รหัสสุ่มแทน)
การส่งทำในเบื้องหลัง ถ้าส่งไม่สำเร็จ แอปยังตอบผู้ใช้ได้ตามปกติ (ไม่ทำให้ช้า)
"""
import json
import os
import queue
import threading
import urllib.error
import urllib.request

from .privacy import pseudonym, scrub

TABLES = ("research_chat", "research_assessment", "research_rating", "research_journal")  # v30 เพิ่มสมุดบันทึก


def _cfg():
    return (os.environ.get("SUPABASE_URL", "").rstrip("/"), os.environ.get("SUPABASE_SERVICE_KEY", ""))


def mode() -> str:
    url, key = _cfg()
    return "supabase" if url and key else "local"


def pid(value: str) -> str:
    """รหัสแทนตัวตน (ย้อนกลับไม่ได้)"""
    return pseudonym(value or "", os.environ.get("RESEARCH_SALT", "jaidee-local"))


def clean(text: str) -> str:
    return scrub(text or "")


# ---------------------------------------------------------------------
# ส่งข้อมูลในเบื้องหลัง
# ---------------------------------------------------------------------
_q: "queue.Queue[tuple[str, dict]]" = queue.Queue(maxsize=5000)
_started = False
_lock = threading.Lock()


def _post_supabase(table: str, row: dict) -> None:
    url, key = _cfg()
    req = urllib.request.Request(
        f"{url}/rest/v1/{table}", method="POST",
        data=json.dumps(row, ensure_ascii=False).encode("utf-8"),
        headers={"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "Prefer": "return=minimal"},
    )
    with urllib.request.urlopen(req, timeout=15) as res:
        res.read()


def _save_local(table: str, row: dict) -> None:
    from .db import get_conn
    conn = get_conn()
    try:
        conn.execute("INSERT INTO research_logs (table_name, row_json, created_at) VALUES (?, ?, ?)",
                     (table, json.dumps(row, ensure_ascii=False), row.get("created_at", "")))
        conn.commit()
    finally:
        conn.close()


def _worker():
    while True:
        table, row = _q.get()
        for attempt in range(3):
            try:
                if mode() == "supabase":
                    _post_supabase(table, row)
                else:
                    _save_local(table, row)
                break
            except (urllib.error.URLError, TimeoutError, OSError) as err:
                if attempt == 2:
                    print(f"⚠️ เก็บข้อมูลวิจัยไม่สำเร็จ ({table}): {err}")
            except Exception as err:  # noqa: BLE001 ห้ามทำให้แอปล่ม
                print(f"⚠️ เก็บข้อมูลวิจัยไม่สำเร็จ ({table}): {err}")
                break


def log(table: str, row: dict) -> None:
    """ส่ง 1 แถวไปเก็บ (ไม่รอ)"""
    global _started
    assert table in TABLES
    with _lock:
        if not _started:
            threading.Thread(target=_worker, daemon=True).start()
            _started = True
    try:
        _q.put_nowait((table, row))
    except queue.Full:
        print("⚠️ คิวข้อมูลวิจัยเต็ม ข้ามแถวนี้")


def flush(timeout: float = 5.0) -> None:
    """รอจนส่งหมดคิว (ใช้ในชุดทดสอบ)"""
    import time
    end = time.time() + timeout
    while not _q.empty() and time.time() < end:
        time.sleep(0.05)
    time.sleep(0.2)
