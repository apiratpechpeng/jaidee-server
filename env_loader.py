"""ตัวโหลดไฟล์ .env แบบง่าย เขียนเองด้วย Python standard library ล้วนๆ
(ไม่ใช้ไลบรารีข้างนอกอย่าง python-dotenv เพื่อให้รันได้ทันทีโดยไม่ต้อง pip install)
"""
import os
from pathlib import Path


def load_env(path: str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        # ไม่เขียนทับถ้ามีการตั้งค่าไว้แล้วในระบบ (เช่นตั้งผ่าน environment variable ตอนรัน)
        os.environ.setdefault(key, value)
