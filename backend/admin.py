"""v21 หน้าผู้ดูแล (/admin): ดูคำตอบของผู้ใช้ที่ยินยอม สรุปผล และให้ผู้ตรวจ 2 คนติดป้าย

ความปลอดภัย
  - เปิดใช้ได้ก็ต่อเมื่อตั้ง ADMIN_PASSWORD (ใน Render -> Environment) ยาวอย่างน้อย 10 ตัวอักษร
  - ล็อกอินแล้วได้ token อายุ 12 ชั่วโมง เก็บในหน่วยความจำของเซิร์ฟเวอร์ (รีสตาร์ตแล้วต้องล็อกอินใหม่)
  - ใส่รหัสผิดเกิน 5 ครั้งใน 15 นาที ล็อกชั่วคราว
  - คีย์ Supabase อยู่ฝั่งเซิร์ฟเวอร์เท่านั้น หน้าเว็บไม่เคยเห็น

ข้อมูลมาจาก Supabase (ถ้าตั้งค่า) หรือตาราง research_logs ในไฟล์ .db (ตอนทดสอบในคอม) ดู research_log.py
"""
import hmac
import json
import os
import secrets
import time
import urllib.parse
import urllib.request

from . import research_log

TOKEN_HOURS = 12
_tokens: dict[str, float] = {}
_fails: list[float] = []
LABEL_FIELDS = ("rater1_crisis", "rater2_crisis", "rater1_topic", "rater2_topic", "rater_note")
CRISIS_LABELS = ("none", "moderate", "high")
PAGE = 1000          # Supabase ส่งได้ครั้งละไม่เกิน 1000 แถว
MAX_ROWS = 20000


class AdminError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


def enabled() -> bool:
    return len(os.environ.get("ADMIN_PASSWORD", "")) >= 10


def login(password: str) -> str:
    if not enabled():
        raise AdminError(503, "ยังไม่ได้ตั้งรหัสผู้ดูแล (ADMIN_PASSWORD อย่างน้อย 10 ตัวอักษร) ใน Render -> Environment")
    now = time.time()
    _fails[:] = [t for t in _fails if now - t < 900]
    if len(_fails) >= 5:
        raise AdminError(429, "ใส่รหัสผิดหลายครั้ง กรุณารอ 15 นาทีแล้วลองใหม่")
    if not hmac.compare_digest((password or "").encode(), os.environ["ADMIN_PASSWORD"].encode()):
        _fails.append(now)
        raise AdminError(401, "รหัสผู้ดูแลไม่ถูกต้อง")
    token = secrets.token_urlsafe(32)
    _tokens[token] = now + TOKEN_HOURS * 3600
    return token


def check(token: str | None) -> bool:
    exp = _tokens.get(token or "")
    if not exp:
        return False
    if exp < time.time():
        _tokens.pop(token, None)
        return False
    return True


# ---------------------------------------------------------------------
# อ่าน/แก้ข้อมูล
# ---------------------------------------------------------------------
def _sb(method: str, path: str, body=None):
    url, key = research_log._cfg()
    req = urllib.request.Request(f"{url}/rest/v1/{path}", method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json",
                                          "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=20) as res:
        raw = res.read()
    return json.loads(raw) if raw else None


def fetch(table: str) -> list[dict]:
    """ทุกแถวของตาราง (ใหม่สุดก่อน)"""
    if table not in research_log.TABLES:
        raise AdminError(404, "ไม่พบตารางนี้")
    if research_log.mode() == "supabase":
        out = []
        while len(out) < MAX_ROWS:
            page = _sb("GET", f"{table}?select=*&order=created_at.desc,id.desc&limit={PAGE}&offset={len(out)}")
            out += page
            if len(page) < PAGE:
                break
        return out
    from .db import get_conn
    conn = get_conn()
    try:
        rows = conn.execute("SELECT log_id, row_json FROM research_logs WHERE table_name = ? ORDER BY log_id DESC LIMIT ?",
                            (table, MAX_ROWS)).fetchall()
    finally:
        conn.close()
    return [{"id": r["log_id"], **json.loads(r["row_json"])} for r in rows]


def update_labels(row_id, labels: dict) -> dict:
    """บันทึกป้ายของผู้ตรวจ (เฉพาะช่อง rater_*) ในตาราง research_chat"""
    patch = {}
    for k, v in labels.items():
        if k not in LABEL_FIELDS:
            continue
        v = (str(v).strip() if v is not None else "") or None
        if k.endswith("_crisis") and v is not None and v not in CRISIS_LABELS:
            raise AdminError(400, "ป้ายวิกฤตต้องเป็น none / moderate / high")
        if v is not None and len(v) > 300:
            raise AdminError(400, "ข้อความยาวเกินไป")
        patch[k] = v
    if not patch:
        raise AdminError(400, "ไม่มีป้ายให้บันทึก")
    if research_log.mode() == "supabase":
        rows = _sb("PATCH", f"research_chat?id=eq.{urllib.parse.quote(str(int(row_id)))}", patch)
        if not rows:
            raise AdminError(404, "ไม่พบแถวนี้")
        return rows[0]
    from .db import get_conn
    conn = get_conn()
    try:
        r = conn.execute("SELECT row_json FROM research_logs WHERE log_id = ? AND table_name = 'research_chat'", (int(row_id),)).fetchone()
        if not r:
            raise AdminError(404, "ไม่พบแถวนี้")
        data = {**json.loads(r["row_json"]), **patch}
        conn.execute("UPDATE research_logs SET row_json = ? WHERE log_id = ?", (json.dumps(data, ensure_ascii=False), int(row_id)))
        conn.commit()
    finally:
        conn.close()
    return {"id": int(row_id), **data}


# ---------------------------------------------------------------------
# สรุปผล
# ---------------------------------------------------------------------
def _count(rows, key):
    out: dict = {}
    for r in rows:
        k = r.get(key) or "-"
        out[k] = out.get(k, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def cohen_kappa(pairs: list[tuple[str, str]]):
    """ความเห็นตรงกันของผู้ตรวจ 2 คน (ตัดโอกาสบังเอิญออก) คืน None ถ้ามีน้อยกว่า 2 คู่"""
    n = len(pairs)
    if n < 2:
        return None
    labels = sorted({x for p in pairs for x in p})
    po = sum(a == b for a, b in pairs) / n
    pe = sum((sum(a == l for a, _ in pairs) / n) * (sum(b == l for _, b in pairs) / n) for l in labels)
    return 1.0 if pe == 1 else round((po - pe) / (1 - pe), 3)


def _fetch_optional(table: str) -> list[dict]:
    """v30 ตารางใหม่ (research_journal) อาจยังไม่ได้สร้างบน Supabase -> ถือว่ายังไม่มีข้อมูล ไม่ให้หน้าสรุปพัง"""
    try:
        return fetch(table)
    except (OSError, ValueError):
        return []


def summary() -> dict:
    chats, assessments, ratings = fetch("research_chat"), fetch("research_assessment"), fetch("research_rating")
    journals = _fetch_optional("research_journal")
    convs: dict = {}
    for r in chats:
        convs.setdefault(r.get("conversation"), 0)
        convs[r.get("conversation")] += 1
    pairs = [(r["rater1_crisis"], r["rater2_crisis"]) for r in chats if r.get("rater1_crisis") and r.get("rater2_crisis")]
    # เทียบระบบกับป้ายของผู้ตรวจ 1 (ถือว่า moderate/high = วิกฤต)
    sys_vs = [(r.get("crisis_level", "NONE") != "NONE", r["rater1_crisis"] != "none") for r in chats if r.get("rater1_crisis")]
    tp = sum(s and h for s, h in sys_vs)
    fp = sum(s and not h for s, h in sys_vs)
    fn = sum(h and not s for s, h in sys_vs)
    prec = round(tp / (tp + fp), 3) if tp + fp else None
    rec = round(tp / (tp + fn), 3) if tp + fn else None
    f1 = round(2 * prec * rec / (prec + rec), 3) if prec and rec else None
    return {
        "storage": research_log.mode(),
        "counts": {"messages": len(chats), "participants": len({r.get("participant") for r in chats + assessments + ratings + journals}),
                   "conversations": len(convs), "assessments": len(assessments), "ratings": len(ratings), "journals": len(journals),
                   "avg_turns": round(sum(convs.values()) / len(convs), 1) if convs else 0},
        "crisis_level": _count(chats, "crisis_level"), "intent": _count(chats, "intent"), "topic": _count(chats, "topic"),
        "age_band": _count(chats, "age_band"), "rating": _count(ratings, "bucket"), "severity": _count(assessments, "severity_level"), "journal_mood": _count(journals, "mood"),
        "labels": {"rater1": sum(1 for r in chats if r.get("rater1_crisis")), "rater2": sum(1 for r in chats if r.get("rater2_crisis")),
                   "both": len(pairs), "kappa_crisis": cohen_kappa(pairs),
                   "system_vs_rater1": {"n": len(sys_vs), "tp": tp, "fp": fp, "fn": fn, "precision": prec, "recall": rec, "f1": f1}},
    }
