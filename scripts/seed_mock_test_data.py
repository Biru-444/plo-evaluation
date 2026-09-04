"""
Seed script: ข้อมูลทดสอบ (mock) ให้หน้า PLO/YLO มีตัวเลข % บรรลุที่หลากหลายไว้ดูตอนทดสอบ UI
(ตอนนี้ทุก PLO ในระบบขึ้น 0% เหมือนกันหมดเพราะยังไม่มีใครป้อนคะแนนจริงเข้าระบบเลย)

ยัดข้อมูลเข้า "จุดต้นทาง" ที่ backend ใช้คำนวณจริง (ดู _calculate_plo_achievement_for_student ใน
app/routes/plo_calculation.py):
  enrollment -> assessment_item -> student_score -> item_clo -> clo_plo_mapping
ไม่ hardcode ผลลัพธ์ % ปลายทางลงตารางไหนตรงๆ ทั้งสิ้น

หมายเหตุ: ระบบนี้ไม่มีการคำนวณ "% บรรลุ YLO" อยู่แล้ว (เช็คโค้ดยืนยันแล้ว - YLO มีแค่ข้อความเป้าหมาย
ไม่มีตัวเลข) จึงไม่ต้อง seed อะไรเพิ่มสำหรับ YLO โดยเฉพาะ - ข้อมูล PLO ที่ seed ที่นี่ก็เพียงพอแล้ว

แยกจากข้อมูลจริงชัดเจน (ตรวจสอบ/ลบทีหลังได้ง่ายด้วย scripts/remove_mock_test_data.py):
  - นักศึกษา: id ขึ้นต้น "TEST" (TEST0001-TEST0016), first_name ขึ้นต้น "[MOCK] ",
    cohort_year=99 (ไม่ชนรุ่นจริง 66-69 เลย แยกเป็นแท็บ "รุ่น 99" ต่างหากในทุกหน้า)
  - course_offering ใหม่: cohort_year=99, academic_year=9999, semester=1, section="MOCK"
    (ไม่แตะ course_offering จริงของวิชาเดิมเลย - offering ใหม่แยกต่างหากทั้งหมด)
  - CLO ใหม่: code ขึ้นต้น "MOCK" (MOCKCLO1, MOCKCLO2)
  - ไม่แก้ course/course_plo ที่มีอยู่แล้วเลย, ไม่แตะนักศึกษาจริง 171 คนเดิม, ไม่มี clo_plo_mapping
    จริงอยู่ก่อนแล้วให้ชนด้วย (ตาราง clo_plo_mapping ทั้งระบบว่างอยู่ก่อน seed) - เพิ่มแถวใหม่เท่านั้น

Idempotent: เช็คก่อนว่าเคยรันแล้วหรือยัง (มี TEST0001 อยู่แล้ว = ข้าม)
"""
from __future__ import annotations

import random
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
MOCK_COHORT_YEAR = 99
MOCK_ACADEMIC_YEAR = 9999
MOCK_SECTION = "MOCK"
NUM_STUDENTS = 16

random.seed(42)  # ผลลัพธ์เดิมทุกครั้งที่รัน - ตรวจสอบ/reproduce ได้

FIRST_NAMES = [
    "สมชาย", "สมหญิง", "วิชัย", "อารีย์", "ประเสริฐ", "มาลี", "สมศักดิ์", "อรุณี",
    "ธนพล", "ปวีณา", "ชัยวัฒน์", "กัญญา", "ณัฐพล", "สุภาพร", "วีรชัย", "จันทร์เพ็ญ",
]

# (course_id, course_code สำหรับ log, base_percent เฉลี่ยของวิชานี้, plo_id ของ CLO1, plo_id ของ CLO2)
# base_percent ต่างกันมากๆ ต่อวิชา เพื่อให้ % บรรลุต่อ PLO กระจาย ไม่ใช่ทุกข้อเท่ากันหมด
# course 4121301 ใช้ PLO1 ซ้ำกับ 4000101 โดยตั้งใจ - ทดสอบเคส "หลายวิชา/หลาย CLO ผูก PLO เดียวกัน"
MOCK_COURSES = [
    (17, "4000101", 82, 1, 2),  # ปี 1 - คะแนนดี ผ่านเกือบทุกคน
    (21, "4121301", 58, 9, 1),  # ปี 1 - คะแนนกลางๆ
    (27, "4122305", 68, 3, 4),  # ปี 2
    (34, "4123304", 48, 5, 6),  # ปี 3
    (38, "4124901", 25, 7, 8),  # ปี 4 - คะแนนแย่ ไม่บรรลุเกือบทุกคน
]

# นักศึกษา 16 คน แบ่ง 4 tier ผลการเรียน (offset บวก/ลบจาก base_percent ของวิชา) วนซ้ำทุก 4 คน
STUDENT_TIER_OFFSET = [15, 15, 15, 15, 5, 5, 5, 5, -5, -5, -5, -5, -15, -15, -15, -15]


def student_id(i: int) -> str:
    return f"TEST{i:04d}"


def clamp(value: float, lo: float = 3, hi: float = 99) -> float:
    return max(lo, min(hi, value))


def main():
    db = SessionLocal()
    try:
        if db.get(Student, student_id(1)) is not None:
            print(
                f"มีข้อมูลทดสอบอยู่แล้ว ({student_id(1)}) - ข้าม ไม่สร้างซ้ำ "
                "(รัน scripts/remove_mock_test_data.py ก่อนถ้าอยากรันใหม่)"
            )
            return

        before_student_count = db.query(Student).count()

        admin = db.query(User).filter(User.role == "admin").first()
        if admin is None:
            print("!! ไม่พบ user role=admin ในระบบ - ต้องมี user อย่างน้อย 1 คนสำหรับ CLO.created_by")
            return

        # --- 1. นักศึกษาทดสอบ ---
        student_ids: list[str] = []
        for i in range(1, NUM_STUDENTS + 1):
            year_level = (i - 1) // 4 + 1
            title = "นาย" if i % 2 == 1 else "นางสาว"
            db.add(
                Student(
                    id=student_id(i),
                    curriculum_id=CURRICULUM_ID,
                    first_name=f"[MOCK] {FIRST_NAMES[i - 1]}",
                    last_name=f"ทดสอบ{i:02d}",
                    title=title,
                    status="กำลังศึกษา",
                    cohort_year=MOCK_COHORT_YEAR,
                    current_year_level=year_level,
                )
            )
            student_ids.append(student_id(i))
        db.flush()

        # --- 2. วิชาทดสอบ: course_offering + assessment_item x2 + CLO x2 + item_clo + clo_plo_mapping ---
        course_summaries = []
        touched_plo_ids: set[int] = set()
        offering_ids: list[int] = []

        for course_id, course_code, base_percent, plo_a, plo_b in MOCK_COURSES:
            course = db.get(Course, course_id)
            if course is None:
                print(f"  !! ไม่พบวิชา course_id={course_id} ({course_code}) - ข้ามวิชานี้")
                continue

            offering = CourseOffering(
                course_id=course_id,
                # instructor_id=None ควรใช้ได้ตาม model (nullable=True) แต่คอลัมน์จริงในฐานข้อมูล
                # เครื่องนี้ยังเป็น NOT NULL อยู่ (ยังไม่เคยรัน
                # scripts/migrate_course_offering_instructor_nullable.py - พบระหว่างรัน seed script
                # นี้ครั้งแรก ไม่ใช่ปัญหาที่ script นี้ต้องแก้) จึงใช้ admin.id แทนเพื่อไม่ต้องพึ่ง migration
                instructor_id=admin.id,
                cohort_year=MOCK_COHORT_YEAR,
                academic_year=MOCK_ACADEMIC_YEAR,
                semester=1,
                section=MOCK_SECTION,
            )
            db.add(offering)
            db.flush()
            offering_ids.append(offering.id)

            item_midterm = AssessmentItem(
                offering_id=offering.id,
                name="สอบกลางภาค (ข้อมูลทดสอบ)",
                type="midterm",
                total_score=Decimal("100"),
            )
            item_quiz = AssessmentItem(
                offering_id=offering.id,
                name="ควิซ (ข้อมูลทดสอบ)",
                type="quiz",
                total_score=Decimal("20"),
            )
            db.add_all([item_midterm, item_quiz])
            db.flush()

            clo1 = CLO(
                course_id=course_id,
                code="MOCKCLO1",
                description="[ข้อมูลทดสอบ] สร้างโดย seed_mock_test_data.py",
                pass_threshold_percent=Decimal("60"),
                created_by=admin.id,
            )
            clo2 = CLO(
                course_id=course_id,
                code="MOCKCLO2",
                description="[ข้อมูลทดสอบ] สร้างโดย seed_mock_test_data.py",
                pass_threshold_percent=Decimal("60"),
                created_by=admin.id,
            )
            db.add_all([clo1, clo2])
            db.flush()

            db.add_all(
                [
                    ItemCLO(item_id=item_midterm.id, clo_id=clo1.id, weight_percent=Decimal("100")),
                    ItemCLO(item_id=item_quiz.id, clo_id=clo2.id, weight_percent=Decimal("100")),
                    CLOPLOMapping(clo_id=clo1.id, plo_id=plo_a, weight_percent=Decimal("100")),
                    CLOPLOMapping(clo_id=clo2.id, plo_id=plo_b, weight_percent=Decimal("100")),
                ]
            )
            touched_plo_ids.update([plo_a, plo_b])

            # --- 3. ลงทะเบียนนักศึกษาทดสอบทุกคนเข้าวิชานี้ + ใส่คะแนน ---
            for i in range(1, NUM_STUDENTS + 1):
                db.add(Enrollment(student_id=student_id(i), offering_id=offering.id))

                tier_offset = STUDENT_TIER_OFFSET[i - 1]
                midterm_percent = clamp(base_percent + tier_offset + random.uniform(-6, 6))
                quiz_percent = clamp(base_percent + tier_offset + random.uniform(-6, 6))

                db.add(
                    StudentScore(
                        item_id=item_midterm.id,
                        student_id=student_id(i),
                        score_obtained=Decimal(str(round(100 * midterm_percent / 100, 2))),
                    )
                )
                db.add(
                    StudentScore(
                        item_id=item_quiz.id,
                        student_id=student_id(i),
                        score_obtained=Decimal(str(round(20 * quiz_percent / 100, 2))),
                    )
                )

            course_summaries.append(
                {
                    "course_code": course_code,
                    "course_name": course.name_th,
                    "offering_id": offering.id,
                    "clo1_id": clo1.id,
                    "clo2_id": clo2.id,
                    "plo_a": plo_a,
                    "plo_b": plo_b,
                    "base_percent": base_percent,
                }
            )

        db.commit()

        after_student_count = db.query(Student).count()
        plo_codes = {
            p.id: p.code for p in db.query(PLO).filter(PLO.id.in_(touched_plo_ids)).all()
        }

        print("=" * 70)
        print("สร้างข้อมูลทดสอบสำเร็จ")
        print("=" * 70)
        print(f"นักศึกษาทดสอบ: {NUM_STUDENTS} คน ({student_ids[0]} - {student_ids[-1]})")
        print(f"  รุ่น (cohort_year): {MOCK_COHORT_YEAR}, หลักสูตร curriculum_id={CURRICULUM_ID}")
        print(f"  ชั้นปีกระจาย: ปี 1-4 (ปีละ {NUM_STUDENTS // 4} คน)")
        print(f"  รายชื่อทั้งหมด: {', '.join(student_ids)}")
        print()
        print(f"วิชาทดสอบ: {len(course_summaries)} วิชา (course_offering ใหม่ทั้งหมด)")
        for cs in course_summaries:
            plo_a_code = plo_codes.get(cs["plo_a"], f"PLO#{cs['plo_a']}")
            plo_b_code = plo_codes.get(cs["plo_b"], f"PLO#{cs['plo_b']}")
            print(
                f"  - {cs['course_code']} {cs['course_name']} (offering_id={cs['offering_id']}, "
                f"เฉลี่ย ~{cs['base_percent']}%) -> CLO1(id={cs['clo1_id']})->{plo_a_code}, "
                f"CLO2(id={cs['clo2_id']})->{plo_b_code}"
            )
        print()
        print(f"PLO ที่มีข้อมูลทดสอบครอบคลุม: {sorted(plo_codes.values())}")
        print(f"ลงทะเบียน (enrollment): {NUM_STUDENTS} คน x {len(course_summaries)} วิชา = "
              f"{NUM_STUDENTS * len(course_summaries)} แถว")
        print(f"คะแนน (student_score): {NUM_STUDENTS * len(course_summaries) * 2} แถว (2 งานประเมิน/วิชา)")
        print()
        print(f"จำนวนนักศึกษาทั้งระบบ: ก่อน seed={before_student_count} -> หลัง seed={after_student_count} "
              f"(เพิ่มขึ้น {after_student_count - before_student_count} คน = ตัวเลขทดสอบเท่านั้น)")
        print()
        print("ลบข้อมูลทดสอบทั้งหมดทีหลังได้ด้วย: python scripts/remove_mock_test_data.py")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
