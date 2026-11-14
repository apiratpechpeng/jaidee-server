#!/usr/bin/env python3
"""จุดเริ่มต้นของแอป — รันด้วยคำสั่งเดียว:

    python app.py

ไม่ต้อง pip install อะไรเลย (ใช้แต่ Python standard library) ไม่ต้องติดตั้ง
PostgreSQL หรือรัน frontend แยก เพราะเซิร์ฟเวอร์ตัวนี้เสิร์ฟทั้งหน้าเว็บและ API
พร้อมกันในพอร์ตเดียว พอรันเสร็จให้เปิดเบราว์เซอร์ไปที่ http://localhost:4000
"""
import os

from backend.db import init_db
from backend.env_loader import load_env
from backend.reminder import start_reminder_scheduler
from backend.server import run_server

if __name__ == "__main__":
    load_env()
    init_db()
    start_reminder_scheduler()
    port = int(os.environ.get("PORT", "4000"))
    run_server(port)
