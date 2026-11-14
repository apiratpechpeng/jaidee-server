"""เข้ารหัสรหัสผ่านและจัดการ session token — ใช้ hashlib/hmac/secrets ที่มากับ
Python อยู่แล้วทั้งหมด (ไม่ต้อง pip install bcrypt หรือ PyJWT)
"""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

PBKDF2_ITERATIONS = 200_000
SESSION_LIFETIME_DAYS = 7


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), PBKDF2_ITERATIONS)
    return f"{salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, digest_hex = stored.split("$", 1)
    except ValueError:
        return False
    check = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), PBKDF2_ITERATIONS)
    return hmac.compare_digest(check.hex(), digest_hex)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_session(conn, user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    created = datetime.now(timezone.utc)
    expires = created + timedelta(days=SESSION_LIFETIME_DAYS)
    conn.execute(
        "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (token, user_id, created.isoformat(), expires.isoformat()),
    )
    return token


def get_user_id_from_token(conn, token: str) -> str | None:
    if not token:
        return None
    row = conn.execute("SELECT user_id, expires_at FROM sessions WHERE token = ?", (token,)).fetchone()
    if not row:
        return None
    expires_at = datetime.fromisoformat(row["expires_at"])
    if datetime.now(timezone.utc) > expires_at:
        return None
    return row["user_id"]
