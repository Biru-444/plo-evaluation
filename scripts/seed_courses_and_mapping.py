"""
Seed script: รายวิชาเอกจริงจาก มคอ.2 (หลักสูตรวิทยาการคอมพิวเตอร์ ปรับปรุง 2566)
- course: 44 วิชา (วิชาแกน 4, วิชาบังคับ 18, วิชาชีพ/สหกิจ 4, วิชาเลือก 18)
- course_plo: PLO mapping ของทุกวิชา (responsibility_level = "primary" / "secondary")
- study_plan: เฉพาะ 26 วิชาที่มีปี/ภาคระบุตายตัวในแผนการศึกษา (วิชาเลือก 18 ตัว
  ไม่มีปี/ภาคตายตัวในเอกสาร จึงไม่ใส่ study_plan ให้ - รอข้อมูล course_offering จริง)

Idempotent: รันซ้ำได้ - update ถ้ามีอยู่แล้ว, insert ถ้ายังไม่มี
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal
from app.models import Course, CoursePLO, PLO, StudyPlan

CURRICULUM_ID = 1

# (course_code, name_th, name_en, credit, category, plo_map, year_level, semester)
COURSES = [
    # --- วิชาแกน (4) ---
    ("4000101", "โครงสร้างดิสครีต", "Discrete Mathematics", 3, "วิชาแกน",
     {"PLO4": "primary"}, 1, 1),
    ("4000201", "ความน่าจะเป็นและสถิติสำหรับวิทยาการคอมพิวเตอร์", "Probability and Statistics for Computing", 3, "วิชาแกน",
     {"PLO4": "primary"}, 1, 1),
    ("4000102", "คณิตศาสตร์สำหรับคอมพิวเตอร์", "Mathematics for Computing", 3, "วิชาแกน",
     {"PLO4": "primary"}, 1, 2),
    ("4000103", "แคลคูลัสสำหรับวิทยาการคอมพิวเตอร์", "Calculus for Computer Scientists", 3, "วิชาแกน",
     {"PLO4": "primary"}, 2, 2),

    # --- วิชาบังคับ (18) ---
    ("4121301", "พื้นฐานการเขียนโปรแกรม", None, 3, "วิชาบังคับ",
     {"PLO2": "secondary", "PLO4": "primary"}, 1, 1),
    ("4121401", "การคิดเชิงคำนวณเบื้องต้น", None, 3, "วิชาบังคับ",
     {"PLO5": "primary"}, 1, 1),
    ("4121201", "วิทยาศาสตร์ข้อมูลเบื้องต้นและการวิเคราะห์ข้อมูล", None, 3, "วิชาบังคับ",
     {"PLO4": "primary"}, 1, 2),
    ("4121501", "ตรรกะดิจิทัลพื้นฐานและอินเทอร์เน็ตสรรพสิ่ง", None, 3, "วิชาบังคับ",
     {"PLO1": "secondary", "PLO4": "primary"}, 1, 2),
    ("4122301", "การพัฒนาและการออกแบบส่วนติดต่อผู้ใช้งาน", None, 3, "วิชาบังคับ",
     {"PLO2": "secondary", "PLO6": "primary"}, 2, 1),
    ("4122303", "การเขียนโปรแกรมขั้นสูง", None, 3, "วิชาบังคับ",
     {"PLO2": "secondary", "PLO6": "primary"}, 2, 1),
    ("4122305", "โครงสร้างข้อมูล", None, 3, "วิชาบังคับ",
     {"PLO5": "primary"}, 2, 1),
    ("4122304", "ระบบฐานข้อมูล", None, 3, "วิชาบังคับ",
     {"PLO1": "secondary", "PLO5": "primary"}, 2, 1),
    ("4122201", "การวิเคราะห์และออกแบบระบบ", None, 3, "วิชาบังคับ",
     {"PLO3": "secondary", "PLO6": "primary", "PLO8": "primary", "PLO9": "primary"}, 2, 2),
    ("4122302", "การพัฒนาโปรแกรมประยุกต์บนอินเทอร์เน็ต", None, 3, "วิชาบังคับ",
     {"PLO2": "secondary", "PLO6": "primary"}, 2, 2),
    ("4123101", "ระบบสารสนเทศเพื่อการจัดการ", None, 3, "วิชาบังคับ",
     {"PLO6": "primary"}, 3, 1),
    ("4123401", "เครือข่ายคอมพิวเตอร์", None, 3, "วิชาบังคับ",
     {"PLO6": "primary"}, 3, 1),
    ("4123501", "ระบบคอมพิวเตอร์และสถาปัตยกรรม", None, 3, "วิชาบังคับ",
     {"PLO6": "primary"}, 3, 1),
    ("4123304", "การออกแบบและการวิเคราะห์ขั้นตอนวิธี", None, 3, "วิชาบังคับ",
     {"PLO6": "primary"}, 3, 2),
    ("4123403", "ระบบปฏิบัติการ", None, 3, "วิชาบังคับ",
     {"PLO1": "secondary", "PLO6": "primary"}, 3, 2),
    ("4123901", "ภาษาอังกฤษสำหรับวิทยาการคอมพิวเตอร์", None, 3, "วิชาบังคับ",
     {"PLO2": "secondary", "PLO6": "primary", "PLO8": "primary"}, 3, 2),
    ("4123902", "โครงงานวิทยาการคอมพิวเตอร์ 1", None, 1, "วิชาบังคับ",
     {"PLO2": "secondary", "PLO6": "primary"}, 3, 2),
    ("4124901", "โครงงานวิทยาการคอมพิวเตอร์ 2", None, 3, "วิชาบังคับ",
     {"PLO2": "secondary", "PLO7": "primary"}, 4, 1),

    # --- วิชาพื้นฐานวิชาชีพและวิชาชีพ (4, เป็นคู่ทางเลือก) ---
    ("4124801", "การเตรียมฝึกประสบการณ์วิชาชีพด้านวิทยาการคอมพิวเตอร์", None, 2, "วิชาพื้นฐานวิชาชีพและวิชาชีพ",
     {"PLO2": "secondary", "PLO3": "secondary", "PLO7": "primary", "PLO8": "primary", "PLO9": "primary"}, 4, 1),
    ("4124803", "การเตรียมสหกิจศึกษา", None, 2, "วิชาพื้นฐานวิชาชีพและวิชาชีพ",
     {"PLO1": "secondary", "PLO2": "secondary", "PLO3": "secondary", "PLO7": "primary", "PLO8": "primary", "PLO9": "primary"}, 4, 1),
    ("4124802", "การฝึกประสบการณ์วิชาชีพด้านวิทยาการคอมพิวเตอร์", None, 6, "วิชาพื้นฐานวิชาชีพและวิชาชีพ",
     {"PLO2": "secondary", "PLO3": "secondary", "PLO7": "primary", "PLO8": "primary", "PLO9": "primary"}, 4, 2),
    ("4124804", "สหกิจศึกษา", None, 6, "วิชาพื้นฐานวิชาชีพและวิชาชีพ",
     {"PLO1": "secondary", "PLO2": "secondary", "PLO3": "secondary", "PLO7": "primary", "PLO8": "primary", "PLO9": "primary"}, 4, 2),

    # --- วิชาเลือก (18) - ไม่มีปี/ภาคตายตัวในเอกสาร -> year_level/semester = None ---
    ("4123102", "การจัดการโครงงานซอฟต์แวร์", None, 3, "วิชาเลือก - องค์การและระบบสารสนเทศ",
     {"PLO2": "secondary", "PLO6": "primary", "PLO8": "primary", "PLO9": "primary"}, None, None),
    ("4122202", "การพัฒนาแอปพลิเคชันบนอุปกรณ์เคลื่อนที่", None, 3, "วิชาเลือก - เทคโนโลยีเพื่องานประยุกต์",
     {"PLO6": "primary"}, None, None),
    ("4122203", "การออกแบบและพัฒนาเกมคอมพิวเตอร์", None, 3, "วิชาเลือก - เทคโนโลยีเพื่องานประยุกต์",
     {"PLO6": "primary"}, None, None),
    ("4123201", "การทำเหมืองข้อมูล", None, 3, "วิชาเลือก - เทคโนโลยีเพื่องานประยุกต์",
     {"PLO6": "primary"}, None, None),
    ("4123202", "ข้อมูลขนาดใหญ่", None, 3, "วิชาเลือก - เทคโนโลยีเพื่องานประยุกต์",
     {"PLO6": "primary"}, None, None),
    ("4124201", "หัวข้อเลือกสรรทางวิทยาการคอมพิวเตอร์ 1", None, 3, "วิชาเลือก - เทคโนโลยีเพื่องานประยุกต์",
     {"PLO7": "primary"}, None, None),
    ("4124202", "หัวข้อเลือกสรรทางวิทยาการคอมพิวเตอร์ 2", None, 3, "วิชาเลือก - เทคโนโลยีเพื่องานประยุกต์",
     {"PLO7": "primary"}, None, None),
    ("4124203", "การตลาดดิจิทัล", None, 3, "วิชาเลือก - เทคโนโลยีเพื่องานประยุกต์",
     {"PLO1": "secondary", "PLO7": "primary"}, None, None),
    ("4124204", "ปัญญาประดิษฐ์", None, 3, "วิชาเลือก - เทคโนโลยีเพื่องานประยุกต์",
     {"PLO7": "primary"}, None, None),
    ("4124205", "การทำเหมืองเว็บและการวิเคราะห์ข้อมูลจากโซเชียลมีเดีย", None, 3, "วิชาเลือก - เทคโนโลยีเพื่องานประยุกต์",
     {"PLO7": "primary"}, None, None),
    ("4121302", "การออกแบบและการพัฒนาเว็บไซต์", None, 3, "วิชาเลือก - เทคโนโลยีและวิธีการทางซอฟต์แวร์",
     {"PLO1": "secondary", "PLO4": "primary"}, None, None),
    ("4123301", "ความเป็นจริงเสมือนและความเป็นจริงเสริม", None, 3, "วิชาเลือก - เทคโนโลยีและวิธีการทางซอฟต์แวร์",
     {"PLO6": "primary"}, None, None),
    ("4123302", "วิศวกรรมซอฟต์แวร์", None, 3, "วิชาเลือก - เทคโนโลยีและวิธีการทางซอฟต์แวร์",
     {"PLO6": "primary"}, None, None),
    ("4123303", "การประมวลผลแบบกลุ่มเมฆ", None, 3, "วิชาเลือก - เทคโนโลยีและวิธีการทางซอฟต์แวร์",
     {"PLO6": "primary"}, None, None),
    ("4124301", "เทคโนโลยีบล็อกเชนและการเข้ารหัสลับ", None, 3, "วิชาเลือก - เทคโนโลยีและวิธีการทางซอฟต์แวร์",
     {"PLO7": "primary"}, None, None),
    ("4124302", "การวิเคราะห์และออกแบบเชิงวัตถุ", None, 3, "วิชาเลือก - เทคโนโลยีและวิธีการทางซอฟต์แวร์",
     {"PLO7": "primary"}, None, None),
    ("4122403", "คอมพิวเตอร์กราฟิก", None, 3, "วิชาเลือก - โครงสร้างพื้นฐานของระบบ",
     {"PLO5": "primary"}, None, None),
    ("4123402", "ฐานข้อมูลขั้นสูง", None, 3, "วิชาเลือก - โครงสร้างพื้นฐานของระบบ",
     {"PLO6": "primary"}, None, None),
]


def upsert_course(db, code, name_th, name_en, credit, category):
    course = (
        db.query(Course)
        .filter(Course.curriculum_id == CURRICULUM_ID, Course.course_code == code)
        .one_or_none()
    )
    if course is None:
        course = Course(
            curriculum_id=CURRICULUM_ID,
            course_code=code,
            name_th=name_th,
            name_en=name_en,
            credit=credit,
            category=category,
        )
        db.add(course)
        db.flush()
        return course, "created"
    changed = False
    for field, value in (
        ("name_th", name_th),
        ("name_en", name_en),
        ("credit", credit),
        ("category", category),
    ):
        if getattr(course, field) != value:
            setattr(course, field, value)
            changed = True
    return course, ("updated" if changed else "unchanged")


def upsert_course_plo(db, course_id, plo_id, level):
    row = (
        db.query(CoursePLO)
        .filter(CoursePLO.course_id == course_id, CoursePLO.plo_id == plo_id)
        .one_or_none()
    )
    if row is None:
        db.add(CoursePLO(course_id=course_id, plo_id=plo_id, responsibility_level=level))
        return True
    if row.responsibility_level != level:
        row.responsibility_level = level
        return True
    return False


def upsert_study_plan(db, course_id, year_level, semester):
    row = (
        db.query(StudyPlan)
        .filter(
            StudyPlan.curriculum_id == CURRICULUM_ID,
            StudyPlan.course_id == course_id,
            StudyPlan.cohort_year.is_(None),
        )
        .one_or_none()
    )
    if row is None:
        db.add(
            StudyPlan(
                curriculum_id=CURRICULUM_ID,
                course_id=course_id,
                cohort_year=None,
                year_level=year_level,
                semester=semester,
            )
        )
        return True
    changed = False
    if row.year_level != year_level:
        row.year_level = year_level
        changed = True
    if row.semester != semester:
        row.semester = semester
        changed = True
    return changed


def main():
    db = SessionLocal()
    try:
        plo_by_code = {
            plo.code: plo.id
            for plo in db.query(PLO).filter(PLO.curriculum_id == CURRICULUM_ID).all()
        }
        if len(plo_by_code) != 9:
            raise RuntimeError(
                f"คาดว่าจะมี PLO 9 ตัวสำหรับ curriculum_id={CURRICULUM_ID} "
                f"แต่พบ {len(plo_by_code)} ตัว - รัน scripts/seed_real_plo_ylo.py ก่อน"
            )

        courses_created, courses_updated = 0, 0
        course_plo_written = 0
        study_plan_written = 0
        skipped_no_study_plan = []

        for code, name_th, name_en, credit, category, plo_map, year_level, semester in COURSES:
            course, status = upsert_course(db, code, name_th, name_en, credit, category)
            if status == "created":
                courses_created += 1
            elif status == "updated":
                courses_updated += 1
            db.flush()

            for plo_code, level in plo_map.items():
                if plo_code not in plo_by_code:
                    raise RuntimeError(f"ไม่พบ PLO code={plo_code} ในระบบ (วิชา {code})")
                if upsert_course_plo(db, course.id, plo_by_code[plo_code], level):
                    course_plo_written += 1

            if year_level is not None and semester is not None:
                if upsert_study_plan(db, course.id, year_level, semester):
                    study_plan_written += 1
            else:
                skipped_no_study_plan.append(code)

        db.commit()

        print(f"course: created {courses_created}, updated {courses_updated} (จากทั้งหมด {len(COURSES)} วิชา)")
        print(f"course_plo: insert/update {course_plo_written} แถว")
        print(f"study_plan: insert/update {study_plan_written} แถว")
        print(f"วิชาที่ไม่ได้ใส่ study_plan (วิชาเลือก, ไม่มีปี/ภาคตายตัวในเอกสาร): {len(skipped_no_study_plan)} วิชา")
        print(skipped_no_study_plan)

        total_courses = db.query(Course).filter(Course.curriculum_id == CURRICULUM_ID).count()
        total_course_plo = (
            db.query(CoursePLO)
            .join(Course, CoursePLO.course_id == Course.id)
            .filter(Course.curriculum_id == CURRICULUM_ID)
            .count()
        )
        total_study_plan = (
            db.query(StudyPlan).filter(StudyPlan.curriculum_id == CURRICULUM_ID).count()
        )
        print(f"--- sanity check ---")
        print(f"course ทั้งหมดใน curriculum_id={CURRICULUM_ID}: {total_courses}")
        print(f"course_plo ทั้งหมด: {total_course_plo}")
        print(f"study_plan ทั้งหมด: {total_study_plan}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
