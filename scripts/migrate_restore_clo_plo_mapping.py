"""
คืนตาราง clo_plo_mapping (ไม่มี Alembic ต้องทำ DROP/CREATE ตรงๆ) — ย้อนกลับ
migrate_drop_clo_plo_mapping.py

เหตุผล : ตรรกะเดิมตัดสิน "บรรลุ PLO" จากระดับวิชา (course_plo.responsibility_level='primary')
         โดยเหมาว่า CLO ทุกข้อของวิชานั้นคือหลักฐานของทุก PLO ที่วิชารับผิดชอบ แต่เอกสาร มคอ.3 จริง
         ยืนยันว่า CLO แต่ละข้อผูกกับ PLO เฉพาะบางข้อเท่านั้น (many-to-many รายข้อ) ไม่ใช่ทุก PLO ของวิชา
         จึงต้องคืนตารางนี้มาเป็นหลักฐานคำนวณแทน (ดู app/models/clo_plo_mapping.py)

หมายเหตุ : ตาราง clo_plo_mapping เดิม (ก่อนถูกลบ) ยังมีอยู่จริงในฐานข้อมูล dev ตอนเขียน migration นี้ -
           มี 66 แถว แต่ทั้งหมดเป็นข้อมูลค้าง (orphaned) อ้าง clo_id ที่ไม่มีอยู่แล้วในตาราง clo (ตาราง
           clo_plo_mapping เดิมไม่มี FOREIGN KEY constraint จริง มีแค่ PRIMARY KEY + UNIQUE(clo_id,
           plo_id) จึงไม่ถูก cascade ลบไปตอน CLO ชุดเก่าถูกลบ) - ยืนยันแล้วว่าไม่เชื่อมกับ CLO/วิชา/
           นักศึกษาจริงตัวไหนเลย ปลอดภัยที่จะทิ้ง (ผู้ใช้ยืนยันแล้วว่าให้ DROP แล้วสร้างใหม่)

           schema ใหม่ตัดคอลัมน์ weight_percent ออก (ตรรกะ all-or-nothing เดิมของ plo_calculation.py
           ไม่ได้ใช้น้ำหนักต่อ CLO - ผ่านครบทุก CLO ที่ผูกไว้ = บรรลุ) และเพิ่ม FOREIGN KEY จริงที่ขาดไปใน
           ตารางเดิม เพื่อให้ลบ CLO/PLO แล้ว mapping ที่ค้างอยู่ถูก cascade ลบตามไปด้วยอัตโนมัติ

Idempotent : เช็คว่าตารางมีอยู่แล้วหรือยัง และ schema ตรงกับที่ต้องการหรือยัง (ไม่มีคอลัมน์
             weight_percent) - ถ้าตรงแล้วข้าม ไม่ทำอะไรซ้ำ
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from app.database import engine


def table_exists(conn, table):
    result = conn.execute(
        text("SELECT 1 FROM information_schema.tables WHERE table_name = :table"),
        {"table": table},
    )
    return result.first() is not None


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
        if table_exists(conn, "clo_plo_mapping"):
            if not column_exists(conn, "clo_plo_mapping", "weight_percent"):
                print("clo_plo_mapping มี schema ใหม่อยู่แล้ว - ข้าม")
                return

            row_count = conn.execute(text("SELECT count(*) FROM clo_plo_mapping")).scalar()
            conn.execute(text("DROP TABLE clo_plo_mapping"))
            print(
                f"ลบตาราง clo_plo_mapping เดิม (schema เก่า มี weight_percent, {row_count} "
                "แถวข้อมูลค้าง) แล้ว"
            )

        conn.execute(
            text(
                """
                CREATE TABLE clo_plo_mapping (
                  id       SERIAL PRIMARY KEY,
                  clo_id   INTEGER NOT NULL REFERENCES clo(id) ON UPDATE CASCADE ON DELETE CASCADE,
                  plo_id   INTEGER NOT NULL REFERENCES plo(id) ON UPDATE CASCADE ON DELETE CASCADE,
                  UNIQUE (clo_id, plo_id)
                )
                """
            )
        )
        conn.execute(
            text(
                "COMMENT ON TABLE clo_plo_mapping IS "
                "'การเชื่อมโยงโดยตรงระหว่าง CLO และ PLO (many-to-many) — "
                "ใช้เป็นหลักฐานการคำนวณบรรลุ PLO แทน course_plo'"
            )
        )
        print("สร้างตาราง clo_plo_mapping ใหม่แล้ว (clo_id, plo_id, FK จริง, ไม่มี weight_percent)")


if __name__ == "__main__":
    main()
