"""
1. อัปเดต curriculum_id=1 ให้เป็นชื่อ/ปีจริงจาก มคอ.2 (เดิมเป็นค่า mock "Computer Science 2024"/2024)
2. สร้าง course_offering ให้ครบทุกวิชาที่มี study_plan (26 วิชา: วิชาแกน+วิชาบังคับ+วิชาชีพ/สหกิจ)
   สำหรับ cohort_year=66 (นักศึกษา 660112230001-70 ที่ current_year_level=4 ตอนนี้
   ถือว่าเรียนผ่านมาแล้วทั้ง 4 ปีตามแผน) โดย map:
     year_level 1 -> academic_year 2566
     year_level 2 -> academic_year 2567
     year_level 3 -> academic_year 2568
     year_level 4 -> academic_year 2569
   semester = ตาม study_plan.semester, section = "1"
   instructor_id: วนรอบ (round-robin) ในบรรดา user ที่ role="instructor" ที่มีอยู่แล้วในระบบ
   (เป็นการ assign ชั่วคราว ยังไม่ใช่ผู้สอนจริงแต่ละวิชา - แก้ทีหลังได้)

Idempotent: รันซ้ำได้ - update ถ้ามีอยู่แล้ว, insert ถ้ายังไม่มี
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal
from app.models import Curriculum, StudyPlan, CourseOffering, User

CURRICULUM_ID = 1
COHORT_YEAR = 66


def main():
    db = SessionLocal()
    try:
        # 1) แก้ curriculum name/year
        curriculum = db.get(Curriculum, CURRICULUM_ID)
        if curriculum is None:
            raise RuntimeError(f"ไม่พบ curriculum id={CURRICULUM_ID}")
        new_name = "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาการคอมพิวเตอร์ (หลักสูตรปรับปรุง พ.ศ. 2566)"
        new_year = 2566
        curriculum_changed = False
        if curriculum.name != new_name:
            curriculum.name = new_name
            curriculum_changed = True
        if curriculum.year != new_year:
            curriculum.year = new_year
            curriculum_changed = True

        # 2) instructor สำหรับวนรอบ assign
        instructors = (
            db.query(User).filter(User.role == "instructor").order_by(User.id).all()
        )
        if not instructors:
            raise RuntimeError(
                "ไม่พบ user ที่ role='instructor' ในระบบ - ต้องมีอย่างน้อย 1 คนก่อนสร้าง course_offering"
            )

        study_plan_rows = (
            db.query(StudyPlan)
            .filter(StudyPlan.curriculum_id == CURRICULUM_ID, StudyPlan.cohort_year.is_(None))
            .order_by(StudyPlan.year_level, StudyPlan.semester, StudyPlan.course_id)
            .all()
        )
        if not study_plan_rows:
            raise RuntimeError(
                "ไม่พบ study_plan สำหรับ curriculum_id=1 - รัน scripts/seed_courses_and_mapping.py ก่อน"
            )

        created, updated, unchanged = 0, 0, 0
        for i, sp in enumerate(study_plan_rows):
            academic_year = 2566 + (sp.year_level - 1)
            instructor = instructors[i % len(instructors)]
            offering = (
                db.query(CourseOffering)
                .filter(
                    CourseOffering.course_id == sp.course_id,
                    CourseOffering.academic_year == academic_year,
                    CourseOffering.semester == sp.semester,
                    CourseOffering.section == "1",
                )
                .one_or_none()
            )
            if offering is None:
                db.add(
                    CourseOffering(
                        course_id=sp.course_id,
                        instructor_id=instructor.id,
                        cohort_year=COHORT_YEAR,
                        academic_year=academic_year,
                        semester=sp.semester,
                        section="1",
                    )
                )
                created += 1
            else:
                changed = False
                if offering.instructor_id != instructor.id:
                    offering.instructor_id = instructor.id
                    changed = True
                if offering.cohort_year != COHORT_YEAR:
                    offering.cohort_year = COHORT_YEAR
                    changed = True
                if changed:
                    updated += 1
                else:
                    unchanged += 1

        db.commit()

        print(
            f"curriculum: {'updated' if curriculum_changed else 'unchanged'} "
            f"(name={curriculum.name!r}, year={curriculum.year})"
        )
        print(
            f"course_offering: created {created}, updated {updated}, unchanged {unchanged} "
            f"(จาก study_plan {len(study_plan_rows)} แถว)"
        )

        total_offerings = db.query(CourseOffering).count()
        print("--- sanity check ---")
        print(f"course_offering ทั้งหมดในระบบ: {total_offerings}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
