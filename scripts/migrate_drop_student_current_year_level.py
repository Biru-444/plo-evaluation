"""
DROP COLUMN student.current_year_level (ไม่มี Alembic ต้องทำ ALTER ตรงๆ)

คอลัมน์นี้เคยเก็บชั้นปีปัจจุบันของนักศึกษาแบบค่าตายตัว ตั้งครั้งเดียวตอน roster import แล้วไม่เคยอัปเดต
อีกเลย (ไม่มี cron/scheduled job ไหนเลื่อนให้อัตโนมัติ) ทำให้นักศึกษาที่ import ไว้ตอนปี 1 ค้างเป็นปี 1
ตลอดไปแม้ข้ามปีการศึกษาไปแล้วจริง - บั๊กจริงที่เจอ 2026-09-23 กระทบทั้งตัวกรองชั้นปี (หน้ารายชื่อ
นักศึกษา/ภาพรวม PLO/YLO) และเงื่อนไข "เรียนถึงชั้นปีนี้แล้วหรือยัง" ใน ylo_calculation.py

ระบบเปลี่ยนมาคำนวณชั้นปีปัจจุบันสดจาก cohort_year ทุกครั้งที่อ่านแทนแล้ว (ดู app/services/year_level.py,
Student.current_year_level/beyond_curriculum property ใน app/models/student.py) - โค้ดแอปทุกจุดเลิกอ่าน/
เขียนคอลัมน์นี้แล้วตั้งแต่ commit ที่เพิ่ม migration นี้ ปลอดภัยที่จะลบทิ้ง

Idempotent: เช็คว่าคอลัมน์มีอยู่จริงก่อน DROP - ถ้าถูกลบไปแล้วข้าม
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from app.database import engine


def column_exists(conn, table, column):
    result = conn.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :table AND column_name = :column"
        ),
        {"table": table, "column": column},
    )
    return result.first() is not None


def main():
    with engine.begin() as conn:
        if not column_exists(conn, "student", "current_year_level"):
            print("student.current_year_level ถูกลบไปแล้ว - ข้าม")
            return

        conn.execute(text("ALTER TABLE student DROP COLUMN current_year_level"))
        print("ลบคอลัมน์ student.current_year_level แล้ว (คำนวณสดจาก cohort_year แทนตั้งแต่นี้ไป)")


if __name__ == "__main__":
    main()
