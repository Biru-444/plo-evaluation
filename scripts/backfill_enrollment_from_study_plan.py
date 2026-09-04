"""
เติม enrollment จริงให้นักศึกษาจริงทุกคนตาม study_plan ย้อนหลังครอบคลุมทุกปีที่เรียนมาแล้วจนถึงปัจจุบัน
(year_level <= current_year_level) - ข้อมูล "ลงทะเบียนตามแผน" เท่านั้น ไม่ใช่เกรด (final_grade เว้นว่าง)
ไม่สร้าง course_offering ใหม่เอง - วิชาไหนยังไม่มี offering รองรับ ข้ามแล้วรายงานกลับ

สูตรจับคู่ course_offering: academic_year = 2500 + cohort_year + (year_level - 1), semester ตรงกับ
study_plan.semester - ยืนยันจากข้อมูลจริงที่มีอยู่ก่อนเขียนสคริปต์นี้ (รุ่น 66 เรียนปี1 ปีการศึกษา2566,
ปี2 2567, ปี3 2568, ปี4 2569; รุ่น 67/68/69 เรียนปี1 ปีการศึกษา 2567/2568/2569 ตามลำดับ - สอดคล้องกับ
current_year_level ของแต่ละรุ่นที่มีอยู่จริง [66->4, 67->3, 68->2, 69->1] แปลว่า "วันนี้" ของระบบคือ
ปีการศึกษา 2569)

กันพลาดกรณี offering ซ้ำ section (เจอจริง: วิชา 4121301 ปีการศึกษา 2566 และ 2569 มี 2 sections) -
เช็คก่อนว่านักศึกษามี enrollment ของ course_id นี้อยู่แล้วหรือยัง (offering ไหนก็ได้ ไม่ใช่แค่ offering
ที่คำนวณได้) ถ้ามีแล้วข้ามเลย (ครอบคลุมทั้ง "ลงแล้วจริง" และ "เคยมีอยู่ก่อนสคริปต์นี้") - ถ้ายังไม่มีและ
เจอ offering ตรง (course_id, academic_year, semester) มากกว่า 1 ตัว = เลือก section เองไม่ได้ ข้าม +
รายงานแยกเป็น "หลาย section เลือกไม่ได้" ไม่เดาว่าใช่ section ไหน
"""
from __future__ import annotations

import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from app.database import engine

ACADEMIC_YEAR_BASE = 2500


def main():
    with engine.begin() as conn:
        students = conn.execute(
            text("SELECT id, curriculum_id, cohort_year, current_year_level FROM student")
        ).all()

        study_plan_rows = conn.execute(
            text(
                "SELECT sp.curriculum_id, sp.course_id, sp.year_level, sp.semester, "
                "c.course_code, c.name_th "
                "FROM study_plan sp JOIN course c ON c.id = sp.course_id "
                "WHERE sp.cohort_year IS NULL"
            )
        ).all()
        plan_by_curriculum: dict[int, list] = defaultdict(list)
        for row in study_plan_rows:
            plan_by_curriculum[row.curriculum_id].append(row)

        offering_rows = conn.execute(
            text("SELECT id, course_id, academic_year, semester FROM course_offering")
        ).all()
        offerings_by_key: dict[tuple[int, int, int], list[int]] = defaultdict(list)
        for row in offering_rows:
            offerings_by_key[(row.course_id, row.academic_year, row.semester)].append(row.id)

        existing_course_ids_by_student: dict[str, set[int]] = defaultdict(set)
        for student_id, offering_id, course_id in conn.execute(
            text(
                "SELECT e.student_id, e.offering_id, co.course_id "
                "FROM enrollment e JOIN course_offering co ON co.id = e.offering_id"
            )
        ).all():
            existing_course_ids_by_student[student_id].add(course_id)

        inserted = 0
        students_touched: set[str] = set()
        missing_offering_impact: dict[tuple[str, str, int, int], int] = defaultdict(int)
        ambiguous_impact: dict[tuple[str, str, int, int], int] = defaultdict(int)

        for student in students:
            plan_rows = [
                r for r in plan_by_curriculum.get(student.curriculum_id, [])
                if r.year_level <= student.current_year_level
            ]
            if student.cohort_year is None:
                continue

            for plan_row in plan_rows:
                if plan_row.course_id in existing_course_ids_by_student[student.id]:
                    continue

                academic_year = ACADEMIC_YEAR_BASE + student.cohort_year + (plan_row.year_level - 1)
                key = (plan_row.course_id, academic_year, plan_row.semester)
                matches = offerings_by_key.get(key, [])

                if len(matches) == 0:
                    missing_offering_impact[
                        (plan_row.course_code, plan_row.name_th, plan_row.year_level, academic_year)
                    ] += 1
                    continue
                if len(matches) > 1:
                    ambiguous_impact[
                        (plan_row.course_code, plan_row.name_th, plan_row.year_level, academic_year)
                    ] += 1
                    continue

                offering_id = matches[0]
                conn.execute(
                    text(
                        "INSERT INTO enrollment (student_id, offering_id) VALUES (:sid, :oid) "
                        "ON CONFLICT (student_id, offering_id) DO NOTHING"
                    ),
                    {"sid": student.id, "oid": offering_id},
                )
                inserted += 1
                students_touched.add(student.id)
                existing_course_ids_by_student[student.id].add(plan_row.course_id)

        print("=" * 70)
        print("Backfill enrollment ตาม study_plan เสร็จแล้ว")
        print("=" * 70)
        print(f"enrollment ที่สร้างใหม่: {inserted} แถว")
        print(f"นักศึกษาที่ได้ enrollment เพิ่มอย่างน้อย 1 วิชารอบนี้: {len(students_touched)} คน")
        print()

        if missing_offering_impact:
            print("รายวิชาที่ 'ขาด course_offering' (เรียงผลกระทบมากไปน้อย):")
            for (code, name, year_level, ay), count in sorted(
                missing_offering_impact.items(), key=lambda kv: -kv[1]
            ):
                print(f"  - {code} {name} | ปี {year_level} | ปีการศึกษา {ay} | กระทบ {count} คน")
        else:
            print("ไม่มีวิชาไหนขาด course_offering")
        print()

        if ambiguous_impact:
            print("รายวิชาที่มีหลาย section ตรงกัน เลือกเองไม่ได้ (ต้องให้ผู้ใช้ระบุ):")
            for (code, name, year_level, ay), count in sorted(
                ambiguous_impact.items(), key=lambda kv: -kv[1]
            ):
                print(f"  - {code} {name} | ปี {year_level} | ปีการศึกษา {ay} | กระทบ {count} คน")
        else:
            print("ไม่มีวิชาไหนเจอ section ซ้ำแบบเลือกไม่ได้")


if __name__ == "__main__":
    main()
