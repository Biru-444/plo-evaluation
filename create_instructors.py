"""
สร้าง instructor users 3 คนสำหรับ login เข้าระบบ (ไม่แตะข้อมูลอื่น)
Run: python create_instructors.py
"""
from __future__ import annotations

from dotenv import load_dotenv

from app.auth import hash_password
from app.database import SessionLocal
from app.models import User

load_dotenv()

INSTRUCTOR_PASSWORD = "devpassword123"

INSTRUCTORS = [
    ("ajarn.somsak", "สมศักดิ์", "ใจดี", "somsak@university.ac.th"),
    ("ajarn.suda", "สุดา", "แสงทอง", "suda@university.ac.th"),
    ("ajarn.wichai", "วิชัย", "รุ่งเรือง", "wichai@university.ac.th"),
]

db = SessionLocal()

for username, first_name, last_name, email in INSTRUCTORS:
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        print(f"User '{username}' มีอยู่แล้ว - ข้าม")
        continue
    user = User(
        username=username,
        password=hash_password(INSTRUCTOR_PASSWORD),
        first_name=first_name,
        last_name=last_name,
        email=email,
        role="instructor",
    )
    db.add(user)
    db.commit()
    print(f"สร้าง user '{username}' (password: {INSTRUCTOR_PASSWORD}) สำเร็จ")

db.close()
print("เสร็จสิ้น")
