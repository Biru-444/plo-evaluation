"""
เพิ่มคอลัมน์ assessment_item.domain (ด้านการเรียนรู้ที่ชิ้นงานวัด - ค่าชุดเดียวกับ clo.domain:
knowledge/skills/ethics/character)

เหตุผล : ให้อาจารย์เลือกประเภทแบบเดียวกับ CLO/PLO ตอนสร้างงานประเมิน (แท็บ "โครงสร้างการประเมิน") -
         เก็บเป็น nullable string ไม่ทำ ENUM ระดับฐานข้อมูล (จำกัดค่าฝั่ง Pydantic แทน ดู
         app/schemas/assessment.py) เหมือน migrate_add_clo_domain.py

หมายเหตุ : ไม่ backfill ค่าเดาให้ชิ้นงานเก่า - แถวเก่าเป็น NULL จนกว่าจะมีคนกรอก
           ต้องรันก่อน deploy โค้ดที่มีคอลัมน์นี้ใน model เสมอ ไม่งั้นทุก query ของ assessment_item พัง

Idempotent : เช็คว่าคอลัมน์มีอยู่แล้วหรือยังก่อน ADD - ถ้ามีแล้วข้าม
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
        if column_exists(conn, "assessment_item", "domain"):
            print("assessment_item.domain มีอยู่แล้ว - ข้าม")
            return

        conn.execute(text("ALTER TABLE assessment_item ADD COLUMN domain VARCHAR(20)"))
        conn.execute(
            text(
                "COMMENT ON COLUMN assessment_item.domain IS "
                "'ด้านการเรียนรู้ที่ชิ้นงานวัด: knowledge/skills/ethics/character หรือ NULL'"
            )
        )
        print("เพิ่มคอลัมน์ assessment_item.domain แล้ว (nullable, ไม่ backfill)")


if __name__ == "__main__":
    main()
