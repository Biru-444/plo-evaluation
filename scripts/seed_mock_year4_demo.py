"""
Seed script: 3 นักศึกษาทดสอบชั้นปีที่ 4 ไว้ค้างดูจริงในเบราว์เซอร์ (ไม่ลบทิ้งทันทีหลัง seed
แบบ seed_mock_test_data.py เดิม - รอผู้ใช้สั่งลบเองเมื่อดูเสร็จ ผ่าน remove_mock_test_data.py)

จุดประสงค์: ให้วงกลมใหญ่ "% นักศึกษาบรรลุ PLO ครบทุกข้อ" หน้า "ภาพรวม PLO" ไม่ใช่ 0% เปล่าๆ
- 2 คนแรก (TESTY4-01, TESTY4-02): คะแนนสูงพอผ่านทุก CLO -> บรรลุครบทั้ง 9 PLO
- 1 คน (TESTY4-03): เหมือน 2 คนแรกทุกอย่าง ยกเว้นคะแนนของ CLO ที่ผูกกับ PLO9 (ตัวสุดท้าย) ต่ำกว่า
  เกณฑ์โดยตั้งใจ -> บรรลุแค่ 8/9 ข้อ ให้เห็นความต่างชัดเจนตอนเปิดดูในหน้าเว็บ

วิชาที่ใช้ (เลือกน้อยที่สุดเท่าที่ครอบคลุมครบ 9 PLO ได้ โดยอิง course_plo จริงที่มีอยู่แล้วเป็นตัวช่วย
เลือกว่าวิชาไหนควรเป็นตัวแทนของ PLO ข้อไหน - primary ก่อน, PLO1/2/3 ไม่มี primary มีแต่ secondary
เลยต้องใช้ secondary สำหรับ 3 ข้อนี้ - แต่ CLO/clo_plo_mapping ที่ผูกจริงเป็นของสร้างใหม่ทั้งหมด):
  - 4124804 สหกิจศึกษา (course_id=42): ครอบคลุม PLO1,2,3 (secondary ในระบบ) + PLO7,8,9 (primary)
    ในตัวเดียว - วิชาเดียวคุ้มที่สุด เลยใช้เป็นตัวแทน 6 ใน 9 PLO
  - 4000101 โครงสร้างดิสคณิต (course_id=17): PLO4 (primary)
  - 4122305 โครงสร้างข้อมูล (course_id=27): PLO5 (primary)
  - 4123304 การออกแบบและการวิเคราะห์ขั้นตอนวิธี (course_id=34): PLO6 (primary)

แยกจากข้อมูลจริงชัดเจน (ตรวจสอบ/ลบทีหลังได้ผ่าน scripts/remove_mock_test_data.py ที่แก้ไขให้
ครอบคลุมชุดนี้ด้วยแล้ว):
  - นักศึกษา: id = TESTY4-01/02/03, first_name ขึ้นต้น "[MOCK] "
  - course_offering ใหม่: academic_year=9999, section="MOCK" (cohort_year=66 ตั้งใจให้ตรงกับ
    รุ่นจริงที่ควรอยู่ปี 4 ในปีการศึกษาปัจจุบัน - ไม่ใช่ตัวกันชนข้อมูลปลอมเหมือนรอบก่อน จึงต้องพึ่ง
    academic_year=9999+section="MOCK" แทนในการกรองลบ)
  - CLO ใหม่: code ขึ้นต้น "MOCK-CLO-PLO"
  - ไม่แก้ course/course_plo ที่มีอยู่แล้วเลย, ไม่แตะนักศึกษาจริง 171 คนเดิม

Idempotent: เช็คก่อนว่าเคยรันแล้วหรือยัง (มี TESTY4-01 อยู่แล้ว = ข้าม)
"""
from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal
from app.models import (
    CLO,
    AssessmentItem,
    CLOPLOMapping,
    Course,
    CourseOffering,
    Enrollment,
    ItemCLO,
    PLO,
    Student,
    StudentScore,
    User,
)

CURRICULUM_ID = 1
COHORT_YEAR = 66  # รุ่นที่ควรอยู่ชั้นปีที่ 4 ในปีการศึกษาปัจจุบัน (ตรงกับนักศึกษาจริงรุ่น 66 ที่มีอยู่แล้ว)
CURRENT_YEAR_LEVEL = 4
MOCK_ACADEMIC_YEAR = 9999
MOCK_SECTION = "MOCK"

HIGH_SCORE = Decimal("90")  # /100 - ผ่านเกณฑ์ 60% สบายๆ
LOW_SCORE = Decimal("30")  # /100 - ไม่ผ่านเกณฑ์ 60% ชัดเจน

STUDENTS = [
    ("TESTY4-01", "[MOCK] วรรณา", "ทดสอบปี4-01", "นางสาว"),
    ("TESTY4-02", "[MOCK] ธีรพงษ์", "ทดสอบปี4-02", "นาย"),
    ("TESTY4-03", "[MOCK] อรทัย", "ทดสอบปี4-03", "นางสาว"),
]

# (course_id, course_code สำหรับ log, [รหัส PLO ที่ต้องผูก])
COURSES = [
    (42, "4124804", ["PLO1", "PLO2", "PLO3", "PLO7", "PLO8", "PLO9"]),
    (17, "4000101", ["PLO4"]),
    (27, "4122305", ["PLO5"]),
    (34, "4123304", ["PLO6"]),
]

# PLO ที่ตั้งใจให้ TESTY4-03 คนเดียวสอบตก (คนอื่นผ่านหมด)
FAILING_PLO_FOR_STUDENT_3 = "PLO9"


def main():
    db = SessionLocal()
    try:
        if db.get(Student, STUDENTS[0][0]) is not None:
            print(
                f"มีข้อมูลทดสอบอยู่แล้ว ({STUDENTS[0][0]}) - ข้าม ไม่สร้างซ้ำ "
                "(รัน scripts/remove_mock_test_data.py ก่อนถ้าอยากรันใหม่)"
            )
            return

        before_student_count = db.query(Student).count()

        admin = db.query(User).filter(User.role == "admin").first()
        if admin is None:
            print("!! ไม่พบ user role=admin ในระบบ - ต้องมี user อย่างน้อย 1 คนสำหรับ CLO.created_by")
            return

        plo_by_code = {p.code: p for p in db.query(PLO).filter(PLO.curriculum_id == CURRICULUM_ID).all()}
        missing = [code for _, _, plos in COURSES for code in plos if code not in plo_by_code]
        if missing:
            print(f"!! ไม่พบ PLO ต่อไปนี้ในหลักสูตร curriculum_id={CURRICULUM_ID}: {missing} - หยุด")
            return

        # --- 1. นักศึกษาทดสอบ 3 คน ---
        for student_id, first_name, last_name, title in STUDENTS:
            db.add(
                Student(
                    id=student_id,
                    curriculum_id=CURRICULUM_ID,
                    first_name=first_name,
                    last_name=last_name,
                    title=title,
                    status="กำลังศึกษา",
                    cohort_year=COHORT_YEAR,
                    current_year_level=CURRENT_YEAR_LEVEL,
                )
            )
        db.flush()

        # --- 2. วิชา + CLO ต่อ PLO + course_offering + enrollment ---
        clo_by_plo_code: dict[str, CLO] = {}
        course_summaries = []

        for course_id, course_code, plo_codes in COURSES:
            course = db.get(Course, course_id)
            if course is None:
                print(f"  !! ไม่พบวิชา course_id={course_id} ({course_code}) - ข้ามวิชานี้")
                continue

            offering = CourseOffering(
                course_id=course_id,
                instructor_id=admin.id,  # course_offering.instructor_id ยัง NOT NULL จริงในเครื่องนี้
                cohort_year=COHORT_YEAR,
                academic_year=MOCK_ACADEMIC_YEAR,
                semester=1,
                section=MOCK_SECTION,
            )
            db.add(offering)
            db.flush()

            for student_id, *_ in STUDENTS:
                db.add(Enrollment(student_id=student_id, offering_id=offering.id))

            clo_ids_this_course = []
            for plo_code in plo_codes:
                clo = CLO(
                    course_id=course_id,
                    code=f"MOCK-CLO-{plo_code}",
                    description=f"[ข้อมูลทดสอบ] สร้างโดย seed_mock_year4_demo.py - แทน {plo_code}",
                    pass_threshold_percent=Decimal("60"),
                    created_by=admin.id,
                )
                db.add(clo)
                db.flush()
                db.add(
                    CLOPLOMapping(
                        clo_id=clo.id, plo_id=plo_by_code[plo_code].id, weight_percent=Decimal("100")
                    )
                )
                clo_by_plo_code[plo_code] = clo
                clo_ids_this_course.append((plo_code, clo.id))

            # แยก assessment item ของ PLO ที่ตั้งใจให้สอบตก ออกจากอันอื่นในวิชาเดียวกัน (ถ้ามี) -
            # ต้องให้คะแนนคนละค่ากันได้ จะใช้ item เดียวรวมกันไม่ได้ ถ้าไม่งั้นทุก CLO ในวิชานั้น
            # จะได้คะแนนเดียวกันหมด
            failing_plo_in_this_course = FAILING_PLO_FOR_STUDENT_3 in plo_codes
            normal_plo_codes = [
                code for code in plo_codes if code != FAILING_PLO_FOR_STUDENT_3
            ]

            def make_item_and_score(item_name: str, item_type: str, plo_codes_for_item: list[str], is_failing_item: bool):
                item = AssessmentItem(
                    offering_id=offering.id,
                    name=item_name,
                    type=item_type,
                    total_score=Decimal("100"),
                )
                db.add(item)
                db.flush()
                for plo_code in plo_codes_for_item:
                    db.add(
                        ItemCLO(
                            item_id=item.id,
                            clo_id=clo_by_plo_code[plo_code].id,
                            weight_percent=Decimal("100"),
                        )
                    )
                for student_id, *_ in STUDENTS:
                    score = (
                        LOW_SCORE
                        if (is_failing_item and student_id == "TESTY4-03")
                        else HIGH_SCORE
                    )
                    db.add(StudentScore(item_id=item.id, student_id=student_id, score_obtained=score))

            if normal_plo_codes:
                make_item_and_score(
                    "งานประเมิน (ข้อมูลทดสอบ)", "assignment", normal_plo_codes, is_failing_item=False
                )
            if failing_plo_in_this_course:
                make_item_and_score(
                    f"งานประเมิน {FAILING_PLO_FOR_STUDENT_3} (ข้อมูลทดสอบ)",
                    "final",
                    [FAILING_PLO_FOR_STUDENT_3],
                    is_failing_item=True,
                )

            course_summaries.append(
                {
                    "course_code": course_code,
                    "course_name": course.name_th,
                    "offering_id": offering.id,
                    "clos": [(plo_code, clo_id) for plo_code, clo_id in clo_ids_this_course],
                }
            )

        db.commit()

        after_student_count = db.query(Student).count()

        print("=" * 70)
        print("สร้างข้อมูลทดสอบ (ค้างไว้ให้ดู - ยังไม่ลบ) สำเร็จ")
        print("=" * 70)
        print("นักศึกษาทดสอบ 3 คน (ชั้นปีที่ 4, รุ่น 66):")
        for student_id, first_name, last_name, title in STUDENTS:
            outcome = "บรรลุครบ 9/9 PLO" if student_id != "TESTY4-03" else "บรรลุ 8/9 PLO (ขาด PLO9)"
            print(f"  - {student_id}: {title}{first_name} {last_name} -> {outcome}")
        print()
        print("วิชา/CLO ที่สร้าง:")
        for cs in course_summaries:
            clo_list = ", ".join(f"{code}(clo_id={cid})" for code, cid in cs["clos"])
            print(f"  - {cs['course_code']} {cs['course_name']} (offering_id={cs['offering_id']}): {clo_list}")
        print()
        print(f"จำนวนนักศึกษาทั้งระบบ: ก่อน seed={before_student_count} -> หลัง seed={after_student_count} "
              f"(เพิ่มขึ้น {after_student_count - before_student_count} คน)")
        print()
        print("*** ข้อมูลชุดนี้ตั้งใจปล่อยค้างไว้ให้ดูในเบราว์เซอร์ - ยังไม่ลบ ***")
        print("เปิด /dashboard (ภาพรวม PLO) เลือกหลักสูตรนี้ + รุ่น 66 เพื่อดูผล")
        print("สั่งลบทั้งหมดทีหลังด้วย: python scripts/remove_mock_test_data.py")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
