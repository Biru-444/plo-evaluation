"""
DROP TABLE clo_plo_mapping (ไม่มี Alembic ต้องทำ ALTER/DROP ตรงๆ)

ตารางนี้เก็บการผูก CLO รายตัว <-> PLO พร้อมน้ำหนัก % ต่อ CLO - ระบบเปลี่ยนแกนคำนวณผลบรรลุ PLO/YLO
มาใช้ course_plo (responsibility_level='primary') แทนแล้ว (ดู _build_plo_requirements ใน
app/routes/plo_calculation.py และ _build_ylo_requirements ใน app/routes/ylo_calculation.py) - CLO
ทุกตัวของวิชาที่ course_plo ทำเครื่องหมาย primary ไว้กับ PLO ข้อนั้นนับเท่ากันหมด ไม่มีน้ำหนักต่อ CLO
อีกต่อไป ตารางนี้จึงไม่ถูกอ้างอิงจากโค้ดแอปที่ไหนเลย (โมเดล SQLAlchemy CLOPLOMapping ถูกลบไปแล้วเช่นกัน)

ยืนยันก่อนรันจริงว่าตารางนี้มี 0 แถวในฐานข้อมูล dev (เช็คแล้ว ณ วันที่เขียน migration นี้) - ไม่กระทบ
ข้อมูลจริงของนักศึกษาคนไหนเลย ปลอดภัยที่จะลบทิ้ง ไม่ต้อง backup ข้อมูลจากตารางนี้ก่อน

Idempotent: เช็ค information_schema ก่อนว่าตารางยังอยู่หรือถูกลบไปแล้ว
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


def main():
    with engine.begin() as conn:
        if table_exists(conn, "clo_plo_mapping"):
            row_count = conn.execute(text("SELECT count(*) FROM clo_plo_mapping")).scalar()
            conn.execute(text("DROP TABLE clo_plo_mapping"))
            print(f"ลบตาราง clo_plo_mapping แล้ว (มี {row_count} แถวก่อนลบ)")
        else:
            print("ตาราง clo_plo_mapping ถูกลบไปแล้ว - ข้าม")


if __name__ == "__main__":
    main()
