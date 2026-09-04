"""
Rollback: ลบ enrollment ของนักศึกษาจริงทั้งหมด (ไม่แตะ TEST/mock) ที่เกิดจากงาน backfill
enrollment ตาม study_plan ก่อนหน้า (scripts/backfill_enrollment_from_study_plan.py) รวมถึง
enrollment ที่มีอยู่ก่อนสคริปต์นั้นด้วย (ทุกแถวของนักศึกษาจริง ไม่ใช่แค่ที่สคริปต์นั้นสร้าง) -
ผู้ใช้ต้องการกลับไปลงทะเบียนเองทั้งหมด เพราะ auto-enroll ไม่รู้ว่านักศึกษาคนไหนลาออกกลางคันแล้ว
ไม่ควรลงทะเบียนวิชาต่อๆ ไปให้

ก่อนรันสคริปต์นี้ (ทำครั้งเดียวตอนตรวจสอบ ไม่ได้ทำอัตโนมัติในสคริปต์นี้):
  - backup ตาราง enrollment ทั้งตารางไว้แล้ว (CSV + pg_dump custom format)
  - เช็คแล้วว่าไม่มีแถวไหนที่ final_grade IS NOT NULL (ถ้าเจอต้องหยุดถามผู้ใช้ก่อน ห้ามลบ)
  - เช็คแล้วว่าไม่มี enrollment ของ TEST/mock student เลย (ไม่มีอะไรต้องกันไว้เป็นพิเศษ)

เงื่อนไขลบ: student_id NOT LIKE 'TEST%' (ตรงกับ convention ที่ใช้แยกนักศึกษาจริง/ทดสอบทั้งระบบ -
ดู scripts/remove_mock_test_data.py) - ถ้ามี TEST/mock enrollment อยู่จริงตอนรัน จะไม่ถูกลบ
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from app.database import engine


def main():
    with engine.begin() as conn:
        before_total = conn.execute(text("SELECT count(*) FROM enrollment")).scalar()
        non_null_grades = conn.execute(
            text("SELECT count(*) FROM enrollment WHERE final_grade IS NOT NULL")
        ).scalar()
        test_rows = conn.execute(
            text("SELECT count(*) FROM enrollment WHERE student_id LIKE 'TEST%'")
        ).scalar()

        if non_null_grades > 0:
            print(
                f"หยุด: พบ enrollment ที่มี final_grade ไม่ใช่ NULL อยู่ {non_null_grades} แถว "
                "- ต้องถามผู้ใช้ก่อน ไม่ลบอัตโนมัติ"
            )
            return

        deleted = conn.execute(
            text("DELETE FROM enrollment WHERE student_id NOT LIKE 'TEST%'")
        ).rowcount

        after_total = conn.execute(text("SELECT count(*) FROM enrollment")).scalar()

        print("=" * 70)
        print("Rollback enrollment (นักศึกษาจริง) เสร็จแล้ว")
        print("=" * 70)
        print(f"ก่อนลบ: {before_total} แถว (TEST/mock: {test_rows} แถว)")
        print(f"ลบไป: {deleted} แถว")
        print(f"หลังลบ: {after_total} แถว (ควรเท่ากับ TEST/mock ที่มีอยู่เดิม = {test_rows})")


if __name__ == "__main__":
    main()
