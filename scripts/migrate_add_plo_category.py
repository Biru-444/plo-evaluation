"""
เพิ่มคอลัมน์ plo.category (ประเภทของ PLO เช่น ความรู้ / ทักษะ / จริยธรรม / ลักษณะบุคคล / อื่นๆ)

เหตุผล : หน้า "จัดการ PLO" ต้องการให้ระบุได้ว่า PLO ข้อนั้นจัดอยู่ในกลุ่มใด (ชื่อคอลัมน์ตั้งให้สอดคล้อง
         กับ course.category ที่มีอยู่แล้ว) เก็บเป็น string อิสระ ไม่ทำ ENUM/lookup table ในฐานข้อมูล -
         frontend เป็นตัวจำกัดตัวเลือก 4 ค่า + "อื่นๆ" ที่พิมพ์เองได้ เหมือน pattern ของ course.category

หมายเหตุ : ฟิลด์นี้บังคับ (NOT NULL) ต่างจาก course.category ที่เป็น optional - ต้อง backfill ค่าให้
           แถวเก่าทุกแถวก่อนถึงจะตั้ง constraint ได้ ผู้ใช้ยืนยันแล้ว (2026-09-21) ให้ backfill ด้วยค่า
           placeholder 'อื่นๆ' สำหรับ PLO เก่าทั้งหมดที่มีอยู่ตอนเขียน migration นี้ (9 ข้อ หลักสูตร 2566)
           แล้วผู้ใช้จะไปแก้เป็นค่าจริงทีละข้อผ่านฟอร์ม "แก้ไข PLO" ในหน้าเว็บทีหลัง

Idempotent : เช็คว่าคอลัมน์มีอยู่แล้วหรือยังก่อน ADD - ถ้ามีแล้วข้ามทั้งหมด (รวม backfill/NOT NULL)
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
        if column_exists(conn, "plo", "category"):
            print("plo.category มีอยู่แล้ว - ข้าม")
            return

        conn.execute(text("ALTER TABLE plo ADD COLUMN category VARCHAR(100)"))
        print("เพิ่มคอลัมน์ plo.category แล้ว (nullable ชั่วคราว)")

        result = conn.execute(
            text("UPDATE plo SET category = 'อื่นๆ' WHERE category IS NULL")
        )
        print(f"Backfill ค่า category = 'อื่นๆ' ให้ PLO เก่า {result.rowcount} แถวแล้ว")

        conn.execute(text("ALTER TABLE plo ALTER COLUMN category SET NOT NULL"))
        conn.execute(
            text(
                "COMMENT ON COLUMN plo.category IS "
                "'ประเภทของ PLO เช่น ความรู้ / ทักษะ / จริยธรรม / ลักษณะบุคคล / อื่นๆ (ข้อความอิสระ)'"
            )
        )
        print("ตั้ง plo.category เป็น NOT NULL แล้ว")


if __name__ == "__main__":
    main()
