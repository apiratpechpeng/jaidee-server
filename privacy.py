"""ลบข้อมูลที่ระบุตัวตนได้ ก่อนส่งข้อความไป Gemini และก่อนส่งออก log ให้ผู้เชี่ยวชาญ

ตัดได้: เบอร์โทร, อีเมล, ไลน์ไอดี, เลขบัตรประชาชน 13 หลัก, ลิงก์, ชื่อหลังคำว่า "ชื่อ", ชื่อโรงเรียน (แบบ "โรงเรียน..." / "ร.ร....")
ข้อจำกัด: ชื่อคนที่พิมพ์ลอยๆ (เช่น "มายด์ไม่คุยกับเรา") ตัดไม่ได้ เพราะไม่มีรูปแบบให้จับ
เบอร์สายด่วนที่อยู่ใน ALLOWED (เช่น 1323, 02-113-6789) ไม่ถูกตัด
"""
import hashlib
import re

ALLOWED_NUMBERS = {"1323", "1300", "1441", "1443", "1669", "191", "021136789", "027136793"}

_PATTERNS = [
    (re.compile(r"https?://\S+|www\.\S+"), "[ลิงก์]"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[อีเมล]"),
    (re.compile(r"(?i)(line\s*(id)?|ไลน์|ไอดีไลน์|ig|ไอจี|instagram|tiktok|ติ๊กต็อก)\s*[:：]?\s*@?[\w.\-]{3,}"), "[บัญชีโซเชียล]"),
    (re.compile(r"(?<!\d)\d[\s-]?\d{4}[\s-]?\d{5}[\s-]?\d{2}[\s-]?\d(?!\d)"), "[เลขบัตร]"),
    (re.compile(r"(โรงเรียน|ร\.ร\.|รร\.)\s?[^\s,.!?]{2,25}"), "[โรงเรียน]"),
    (re.compile(r"(ชื่อ(?:จริง|เล่น)?(?:ว่า|คือ)?)\s?([^\s,.!?]{2,20})"), r"\1 [ชื่อ]"),
]
_PHONE = re.compile(r"(?<!\d)(\+66|0)[\s-]?\d{1,2}[\s-]?\d{3}[\s-]?\d{3,4}(?!\d)")


def _phone_sub(m: re.Match) -> str:
    digits = re.sub(r"\D", "", m.group(0))
    return m.group(0) if digits in ALLOWED_NUMBERS else "[เบอร์โทร]"


def scrub(text: str) -> str:
    t = _PHONE.sub(_phone_sub, text or "")
    for pat, rep in _PATTERNS:
        t = pat.sub(rep, t)
    return t


def pseudonym(value: str, salt: str = "jaidee") -> str:
    """รหัสแทนตัวตน (เหมือนกันทุกครั้งสำหรับค่าเดิม แต่ย้อนกลับเป็นค่าเดิมไม่ได้)"""
    return hashlib.sha256(f"{salt}:{value}".encode("utf-8")).hexdigest()[:10]
