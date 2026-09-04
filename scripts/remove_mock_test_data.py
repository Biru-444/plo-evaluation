"""
ลบข้อมูลทดสอบทั้งหมดที่ scripts/seed_mock_test_data.py และ scripts/seed_mock_year4_demo.py
สร้างไว้ - คู่กับทั้งสอง seed script (ทั้งสองใช้ลายเซ็นเดียวกัน จึงลบด้วยสคริปต์เดียวได้)

กรองด้วยลายเซ็นที่ seed script ใช้เท่านั้น เพื่อไม่ให้โดนข้อมูลจริงเผลอ:
  - student.id LIKE 'TEST%' (ครอบคลุมทั้ง TEST0001.. และ TESTY4-01..)
  - course_offering: academic_year=9999 AND section='MOCK' (ไม่กรองด้วย cohort_year อีกต่อไป
    เพราะ seed_mock_year4_demo.py ตั้งใจใช้ cohort_year=66 ให้ตรงกับรุ่นจริง ไม่ใช่รุ่นปลอมเหมือน
    seed_mock_test_data.py รอบก่อน - academic_year=9999+section='MOCK' คู่กันยังเป็นค่าที่ข้อมูล
    จริงไม่มีทางชนอยู่ดี)
  - clo.code LIKE 'MOCK%' (ครอบคลุมทั้ง MOCKCLO1.. และ MOCK-CLO-PLO..)

ลบแค่ 3 จุดนี้พอ - ที่เหลือ (enrollment, student_score, assessment_item, item_clo,
clo_plo_mapping) ถูกลบตามด้วย ON DELETE CASCADE ที่ระดับ DB อยู่แล้ว (ดู FK constraints
ในตารางเหล่านั้น) ไม่ต้องลบเองทีละตาราง

ไม่แตะ course/course_plo/นักศึกษาจริงเลย - ไม่มีเงื่อนไขไหนแมตช์ข้อมูลจริงได้
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from app.database import engine

MOCK_ACADEMIC_YEAR = 9999
MOCK_SECTION = "MOCK"


def main():
    with engine.begin() as conn:
        before_students = conn.execute(text("SELECT count(*) FROM student")).scalar()

        test_student_ids = [
            row[0]
            for row in conn.execute(
                text("SELECT id FROM student WHERE id LIKE 'TEST%'")
            ).all()
        ]
        if not test_student_ids:
            print("ไม่พบข้อมูลทดสอบ (ไม่มี student.id ที่ขึ้นต้นด้วย TEST) - ไม่มีอะไรให้ลบ")
            return

        mock_offering_ids = [
            row[0]
            for row in conn.execute(
                text(
                    "SELECT id FROM course_offering "
                    "WHERE academic_year = :academic_year AND section = :section"
                ),
                {
                    "academic_year": MOCK_ACADEMIC_YEAR,
                    "section": MOCK_SECTION,
                },
            ).all()
        ]

        mock_clo_ids = [
            row[0] for row in conn.execute(text("SELECT id FROM clo WHERE code LIKE 'MOCK%'")).all()
        ]

        deleted_students = conn.execute(
            text("DELETE FROM student WHERE id LIKE 'TEST%'")
        ).rowcount
        deleted_offerings = conn.execute(
            text(
                "DELETE FROM course_offering "
                "WHERE academic_year = :academic_year AND section = :section"
            ),
            {
                "academic_year": MOCK_ACADEMIC_YEAR,
                "section": MOCK_SECTION,
            },
        ).rowcount
        deleted_clos = conn.execute(text("DELETE FROM clo WHERE code LIKE 'MOCK%'")).rowcount

        after_students = conn.execute(text("SELECT count(*) FROM student")).scalar()

        print("=" * 70)
        print("ลบข้อมูลทดสอบเรียบร้อย")
        print("=" * 70)
        print(f"นักศึกษาทดสอบที่ลบ: {deleted_students} คน ({', '.join(test_student_ids)})")
        print(f"course_offering ทดสอบที่ลบ: {deleted_offerings} รายการ (id: {mock_offering_ids})")
        print(f"CLO ทดสอบที่ลบ: {deleted_clos} รายการ (id: {mock_clo_ids})")
        print("(enrollment / student_score / assessment_item / item_clo / clo_plo_mapping "
              "ที่เกี่ยวข้องถูกลบตามอัตโนมัติผ่าน ON DELETE CASCADE)")
        print()
        print(f"จำนวนนักศึกษาทั้งระบบ: ก่อนลบ={before_students} -> หลังลบ={after_students}")


if __name__ == "__main__":
    main()
