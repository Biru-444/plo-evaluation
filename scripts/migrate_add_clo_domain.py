"""
เพิ่มคอลัมน์ clo.domain (โดเมนการเรียนรู้ของ CLO ข้อนั้น เช่น "ความรู้"/"ทักษะ"/"จริยธรรม"/
"ลักษณะบุคคล" - มักกำกับด้วยวงเล็บ (K)/(S)/(A)/(C) ในเอกสาร มคอ.3)

เหตุผล : ฟีเจอร์ "นำเข้าข้อมูลวิชาจาก มคอ.3 ด้วย AI" (ดู app/services/mco3_import_service.py) ต้องมี
         ที่เก็บค่านี้เพื่อแสดงในหน้าตรวจสอบ - เก็บเป็น nullable string ตายตัว 4 ค่า ไม่ทำ ENUM ระดับ
         ฐานข้อมูล (จำกัดค่าฝั่ง Pydantic แทน ดู app/schemas/clo.py)

หมายเหตุ : ต่างจาก plo.category (migrate_add_plo_category.py) ตรงที่ฟิลด์นี้ nullable และ **ห้าม
           backfill ค่าเดา** ให้ CLO เก่าที่มีอยู่แล้วเด็ดขาด (ผู้ใช้ระบุไว้ชัดเจนในสเปค) - CLO เก่าทุกแถว
           จะมี domain = NULL ไปเรื่อยๆ จนกว่าจะมีคนกรอกจริง (ผ่านฟอร์มแก้ไข CLO หรือฟีเจอร์ import นี้)

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
        if column_exists(conn, "clo", "domain"):
            print("clo.domain มีอยู่แล้ว - ข้าม")
            return

        conn.execute(text("ALTER TABLE clo ADD COLUMN domain VARCHAR(20)"))
        conn.execute(
            text(
                "COMMENT ON COLUMN clo.domain IS "
                "'โดเมนการเรียนรู้ของ CLO: knowledge/skills/ethics/character หรือ NULL "
                "ถ้าเอกสารไม่ได้ระบุไว้ชัดเจน (ห้ามเดา)'"
            )
        )
        print("เพิ่มคอลัมน์ clo.domain แล้ว (nullable, ไม่ backfill ค่าเดา)")


if __name__ == "__main__":
    main()
