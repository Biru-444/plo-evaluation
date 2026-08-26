"""
สร้าง admin user คนแรกสำหรับ login เข้าระบบ (ไม่แตะข้อมูลอื่น)
Run: python create_admin.py
"""
from __future__ import annotations

from dotenv import load_dotenv

from app.auth import hash_password
from app.database import SessionLocal
from app.models import User

load_dotenv()

db = SessionLocal()

existing = db.query(User).filter(User.username == "admin").first()
if existing:
    print("User 'admin' มีอยู่แล้ว - ไม่สร้างซ้ำ")
else:
    admin = User(
        username="admin",
        password=hash_password("admin123"),
        first_name="Admin",
        last_name="User",
        email="admin@university.ac.th",
        role="admin",
    )
    db.add(admin)
    db.commit()
    print("สร้าง user 'admin' (password: admin123) สำเร็จ")

db.close()
