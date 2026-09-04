"""
เพิ่มคอลัมน์ section ในตาราง student (ไม่มี Alembic ต้องทำ ALTER TABLE ตรงๆ)
Idempotent: เช็ค information_schema ก่อนว่ามีคอลัมน์แล้วหรือยัง
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
        if not column_exists(conn, "student", "section"):
            conn.execute(text("ALTER TABLE student ADD COLUMN section VARCHAR(20)"))
            print("เพิ่มคอลัมน์ student.section แล้ว (nullable, ค่าเดิมเป็น NULL ทั้งหมด)")
        else:
            print("student.section มีอยู่แล้ว - ข้าม")


if __name__ == "__main__":
    main()
