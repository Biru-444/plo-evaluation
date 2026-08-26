"""
ทำให้คอลัมน์ course_offering.instructor_id เป็น NULL ได้ (ไม่มี Alembic ต้องทำ ALTER TABLE ตรงๆ)
จำเป็นสำหรับฟีเจอร์ "จับจองวิชา" - วิชาที่เปิดสอนแต่ยังไม่มีผู้สอนต้องเก็บ instructor_id = NULL ได้
โมเดล SQLAlchemy (app/models/course_offering.py) ถูกแก้เป็น nullable=True ไปแล้ว แต่คอลัมน์จริงใน
ฐานข้อมูลยังเป็น NOT NULL อยู่ (สร้างจาก schema เดิมตอนตั้งโปรเจกต์) ต้องรัน migration นี้ก่อนใช้งานจริง
Idempotent: เช็ค information_schema ก่อนว่า nullable อยู่แล้วหรือยัง
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from app.database import engine


def is_nullable(conn, table, column):
    result = conn.execute(
        text(
            "SELECT is_nullable FROM information_schema.columns "
            "WHERE table_name = :table AND column_name = :column"
        ),
        {"table": table, "column": column},
    )
    row = result.first()
    return row is not None and row[0] == "YES"


def main():
    with engine.begin() as conn:
        if not is_nullable(conn, "course_offering", "instructor_id"):
            conn.execute(text("ALTER TABLE course_offering ALTER COLUMN instructor_id DROP NOT NULL"))
            print("แก้ course_offering.instructor_id ให้เป็น NULL ได้แล้ว")
        else:
            print("course_offering.instructor_id เป็น NULL ได้อยู่แล้ว - ข้าม")


if __name__ == "__main__":
    main()
