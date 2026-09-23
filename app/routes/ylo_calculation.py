"""
ทำอะไร : เส้นทาง API สำหรับคำนวณ "% บรรลุ YLO" (ผลลัพธ์การเรียนรู้ระดับชั้นปี) ของนักศึกษา ทั้งแบบ
         รายรุ่นต่อชั้นปีเดียว (by-year) และรายบุคคลทุกปีพร้อมกัน (student)

สูตรคำนวณ (rewrite 2026-09 - ให้ตรงกับ PLO ตามที่ยืนยันแล้ว, เดิมอิง course_plo all-or-nothing แยกชุด
ข้อมูลกับ PLO ทำให้ "PLO บรรลุแต่ YLO ไม่บรรลุ" เกิดขึ้นได้จริง ดู audit 2026-09) :
  นักศึกษาจะ "บรรลุ YLO ปีที่ N" ก็ต่อเมื่อ PLO ทุกข้อที่ YLO ปีนี้คาดหวังไว้ (ผ่าน ylo_plo_mapping) บรรลุ
  พร้อมกันทั้งหมด โดยแต่ละ PLO ตัดสินด้วยสูตรเดียวกับที่ใช้ตัดสิน % บรรลุ PLO ทุกที่ในระบบทุกประการ
  (_build_plo_requirements/_student_plo_score จาก plo_achievement_service.py - PLO_x =
  Σ(mastery×weight)/Σ(weight) ผ่าน clo_plo_mapping ไม่ใช่ course_plo) ดู _student_achieved_ylo สำหรับ
  กฎ has_data/is_achieved แบบละเอียด (เลือกเข้มกว่า has_data ตรงที่ต้องมีข้อมูลครบทุก PLO ที่คาดหวังไว้
  ไม่ใช่แค่บางข้อ)

  YLO ที่ไม่มี PLO คาดหวังไว้เลย (ylo_plo_mapping ว่าง) จะถูกรายงานว่า "ยังไม่บรรลุ" ไม่มีข้อมูล
  (has_data=False) — ไม่มีข้อมูลให้ตัดสิน ไม่ใช่ผ่านอัตโนมัติ กฎเดียวกับฝั่ง PLO

เชื่อมกับ : - อ่านจากตาราง ylo_plo_mapping, clo_plo_mapping (ผ่าน plo_achievement_service.py),
              study_plan (แค่หา "ปีนี้เรียนอะไรบ้าง" สำหรับ field `courses`/course_items - ไม่ได้ใช้
              ตัดสิน is_achieved อีกต่อไป)
            - GET /ylo/achievement/by-year ถูกเรียกจากหน้า "YLO ตามชั้นปี"
            - GET /ylo/achievement/student ถูกเรียกจากหน้าผลบรรลุรายบุคคล (student-plo) สำหรับ
              hierarchy รายวิชา -> YLO (รายปี) -> PLO - สถานะผ่าน/ไม่ผ่าน "รายวิชา" (course_items) ยังคง
              เป็นคนละเรื่องกับ is_achieved ของ YLO เหมือนเดิม (ดู docstring ของ
              get_student_ylo_achievement) ใช้ _clo_passed ตัดสินทีละวิชาแยกต่างหาก ไม่เปลี่ยนตาม rewrite
              นี้

ถ้าแก้ : แก้ _student_achieved_ylo กระทบ % บรรลุ YLO ทั้งระบบทันที (ทั้งสอง endpoint ในไฟล์นี้ใช้
         ฟังก์ชันเดียวกัน)
"""
from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import require_role
from app.database import get_db
from app.models import (
    CLO,
    Course,
    CourseOffering,
    Curriculum,
    Enrollment,
    Student,
    StudyPlan,
    User,
    YLO,
    YLOPLOMapping,
)
from app.routes.plo_calculation import _clo_passed
from app.services.plo_achievement_service import (
    PLO_ACHIEVEMENT_THRESHOLD_PERCENT,
    _build_plo_requirements,
    _clo_mastery_for_student,
    _student_plo_score,
)
from app.services.year_level import current_year_level, min_cohort_year_for_level

router = APIRouter(prefix="/ylo", tags=["YLO Achievement"])


# ผลบรรลุ YLO ของนักศึกษา 1 คน (ใช้เป็นรายการย่อยใน YLOCohortAchievement.students)
class YLOAchievementStudentItem(BaseModel):
    student_id: str
    student_name: str
    is_achieved: bool
    # has_data=False = ยังไม่มีข้อมูลให้ตัดสินเลย (ไม่ใช่ "ไม่บรรลุ" จริง) มิเรอร์ PLOAchievementItem.has_data
    # (ดู plo_achievement_service.py) - is_achieved เป็น False เสมอตอน has_data=False เช่นกัน (ดู
    # _student_achieved_ylo) frontend ต้องเช็ค has_data ก่อนตัดสิน ไม่ใช่ดูแค่ is_achieved เฉยๆ
    has_data: bool


# ข้อมูลวิชา 1 วิชาที่สอนในชั้นปีนั้นตาม study_plan (ไม่จำกัดว่าต้องเกี่ยวกับ YLO นี้โดยตรง)
class YLOCourseInfo(BaseModel):
    course_id: int
    course_code: str
    name_th: str
    name_en: str | None
    credit: int
    category: str | None


class StudentYLOCourseItem(BaseModel):
    course_id: int
    course_code: str
    name_th: str
    is_enrolled: bool
    # มีความหมายเฉพาะตอน is_enrolled=True เท่านั้น (ยังไม่ลงทะเบียน = ยังไม่มีข้อมูลตัดสิน ไม่ใช่ "ไม่ผ่าน")
    passed: bool


# ผลบรรลุ YLO 1 ปีของนักศึกษา 1 คน พร้อมรายวิชาของปีนั้น — รายการย่อยใน StudentYLOAchievement.years
class StudentYLOYearItem(BaseModel):
    year_level: int
    ylo_description: str
    is_reached: bool  # current_year_level(student.cohort_year).level >= year_level แล้วหรือยัง
    is_achieved: bool
    has_data: bool  # ดูคอมเมนต์ YLOAchievementStudentItem.has_data
    courses: list[StudentYLOCourseItem]


# response ของ GET /ylo/achievement/student — ผลบรรลุ YLO ครบทั้ง 4 ปีของนักศึกษา 1 คน
class StudentYLOAchievement(BaseModel):
    student_id: str
    curriculum_id: int
    years: list[StudentYLOYearItem]


# response ของ GET /ylo/achievement/by-year — ผลบรรลุ YLO ปีเดียว ของนักศึกษาทั้งรุ่น
#
# student_count_with_data/achieved_rate_percent(nullable)/coverage_percent (rewrite 2026-09) มิเรอร์
# YearlyPLOSummaryItem (plo_calculation.py) ตรงๆ - หารด้วยนักศึกษาที่มีข้อมูล (has_data=True) ไม่ใช่
# นักศึกษาทั้งหมด (TASK-plo-denominator หลักการเดียวกัน) achieved_rate_percent เป็น None เมื่อไม่มีใครมี
# ข้อมูลเลย (หารไม่ได้ ไม่ใช่ 0%) coverage_percent = สัดส่วนคนมีข้อมูลจากทั้งหมด ต้องแสดงคู่กันเสมอฝั่ง
# frontend เหมือน PLO
class YLOCohortAchievement(BaseModel):
    ylo_id: int
    curriculum_id: int
    curriculum_name: str
    year_level: int
    description: str
    total_students: int
    student_count_with_data: int
    achieved_student_count: int
    achieved_rate_percent: float | None
    coverage_percent: float = 0.0
    students: list[YLOAchievementStudentItem]
    available_cohort_years: list[int] = []
    # รายวิชาที่เปิดสอนชั้นปีนี้ตามแผนการศึกษา (study_plan) - ทุกวิชาที่กำหนดไว้ ไม่ใช่แค่วิชาที่ใช้ตัดสิน
    # is_achieved อีกต่อไป (rewrite 2026-09 เปลี่ยนไปตัดสินจาก PLO/clo_plo_mapping แทน course_plo แล้ว -
    # field นี้ยังคงไว้แค่ตอบ "ปีนี้เรียนอะไรบ้าง" เฉยๆ)
    courses: list[YLOCourseInfo] = []


def _study_plan_course_ids(
    db: Session, curriculum_id: int, year_level: int, cohort_year: int | None
) -> set[int]:
    """
    ทำอะไร : หารายชื่อวิชาที่สอนในปี year_level ของหลักสูตรนี้ตาม study_plan — ถ้ามี study_plan ที่
             เจาะจงรุ่น (cohort_year) นี้อยู่จริง จะใช้ชุดนั้นก่อน ถ้าไม่มีจะ fallback ไปใช้แผนมาตรฐาน
             (cohort_year เป็น NULL)

    เชื่อมกับ : ใช้โดย _year_courses และ _build_ylo_requirements ในการหาวิชาของแต่ละชั้นปี

    ถ้าแก้ : ข้อมูลจริงในระบบตอนนี้มีแต่แถว "แผนมาตรฐาน" (cohort_year เป็น NULL) เท่านั้น แต่โค้ดนี้
             เขียนรองรับไว้ล่วงหน้า ถ้ามีการเพิ่มแผนเฉพาะรุ่นภายหลังจะยังทำงานถูกต้อง
    """
    if cohort_year is not None:
        cohort_specific = {
            row[0]
            for row in db.query(StudyPlan.course_id)
            .filter(
                StudyPlan.curriculum_id == curriculum_id,
                StudyPlan.year_level == year_level,
                StudyPlan.cohort_year == cohort_year,
            )
            .all()
        }
        if cohort_specific:
            return cohort_specific
    return {
        row[0]
        for row in db.query(StudyPlan.course_id)
        .filter(
            StudyPlan.curriculum_id == curriculum_id,
            StudyPlan.year_level == year_level,
            StudyPlan.cohort_year.is_(None),
        )
        .all()
    }


def _year_courses(db: Session, curriculum_id: int, year_level: int, cohort_year: int | None) -> list[YLOCourseInfo]:
    """
    ทำอะไร : คืนวิชาทั้งหมดที่ถูกกำหนดสอนในปี year_level ตาม study_plan เรียงตาม course_code — ตอบ
             คำถาม "ปีนี้เรียนอะไรบ้าง" ทั้งหมด ไม่ใช่แค่วิชาที่เกี่ยวข้องกับ PLO กลุ่มของ YLO นี้
             โดยเฉพาะ (ดู field `courses` ใน YLOCohortAchievement)

    เชื่อมกับ : เรียก _study_plan_course_ids — ใช้แสดงรายวิชาของปีในหน้า "YLO ตามชั้นปี" และ
                หน้าผลบรรลุรายบุคคล

    ถ้าแก้ : คืน [] ถ้าไม่มีวิชาเลยในปีนั้น (ไม่ error)
    """
    course_ids = _study_plan_course_ids(db, curriculum_id, year_level, cohort_year)
    if not course_ids:
        return []
    courses = db.query(Course).filter(Course.id.in_(course_ids)).order_by(Course.course_code).all()
    return [
        YLOCourseInfo(
            course_id=c.id,
            course_code=c.course_code,
            name_th=c.name_th,
            name_en=c.name_en,
            credit=c.credit,
            category=c.category,
        )
        for c in courses
    ]


def _expected_plo_ids_for_ylo(db: Session, ylo_id: int) -> set[int]:
    """PLO ที่ YLO ปีนี้คาดหวังไว้ (ผ่าน ylo_plo_mapping) - YLO 1 ปีมักถูก map กับหลาย PLO พร้อมกัน"""
    return {
        row[0] for row in db.query(YLOPLOMapping.plo_id).filter(YLOPLOMapping.ylo_id == ylo_id).all()
    }


def _student_achieved_ylo(
    expected_plo_ids: set[int],
    plo_clo_weights: dict[int, dict[int, Decimal]],
    clo_mastery: dict[int, Decimal],
) -> tuple[bool, bool]:
    """
    ทำอะไร : ตัดสินว่านักศึกษา "บรรลุ YLO" ปีนี้หรือไม่ (is_achieved) พร้อม has_data - คืน
             (is_achieved, has_data) เรียก _student_plo_score ของ plo_achievement_service.py ทีละ
             PLO ที่ YLO ปีนี้คาดหวังไว้ (ตัวเดียวกับที่ตัดสิน % บรรลุ PLO ทุกที่ในระบบ ไม่มี logic
             คำนวณแยก) แทน course_plo all-or-nothing เดิม (rewrite 2026-09 - ดู module docstring)

             กฎที่เลือก : has_data = True ถ้ามี PLO ที่คาดหวังไว้อย่างน้อย 1 ข้อมีข้อมูล (ใจกว้าง - แค่
             เริ่มมีหลักฐานบ้างก็พอให้ UI เลิกโชว์ "ยังไม่มีข้อมูล" สีเทา) ส่วน is_achieved เข้มกว่านั้น
             มาก - ต้อง "ทุก" PLO ที่คาดหวังไว้ (ไม่ใช่แค่ข้อที่มีข้อมูล) มีข้อมูลครบ "และ" บรรลุทุกข้อ
             พร้อมกัน เลือกกฎนี้เพราะ YLO ควรถือว่า "บรรลุ" ก็ต่อเมื่อมีหลักฐานครบทุก PLO ที่คาดหวังไว้
             จริง ไม่ใช่แค่ข้อที่บังเอิญมีคะแนนแล้วบรรลุ (ถ้าใช้กฎใจกว้างแบบ has_data คือ "ทุกข้อที่มี
             ข้อมูลบรรลุ" เฉยๆ YLO ที่มี PLO 3 ข้อ มีคะแนนแค่ข้อเดียวแล้วบรรลุ จะถูกนับ "บรรลุ YLO" ทั้งที่
             อีก 2 ข้อยังตัดสินไม่ได้เลย - ผิดเจตนารมณ์)

    เชื่อมกับ : ใช้โดย get_ylo_achievement และ get_student_ylo_achievement - YLO ที่ไม่มี PLO คาดหวังไว้
                เลย (ylo_plo_mapping ว่าง) คืน (False, False) เสมอ (ไม่มีข้อมูลให้ตัดสิน)

    ถ้าแก้ : เป็นจุดตัดสินใจหลักของผลบรรลุ YLO ทั้งระบบ - PLO ที่บรรลุจะทำให้ YLO ของปีที่ PLO นั้น
             คาดหวังไว้ขยับตามเสมอ (ถ้าเป็น PLO ข้อเดียวที่ YLO ปีนั้นคาดหวัง) ไม่มีทาง "PLO บรรลุแต่ YLO
             ไม่บรรลุ" (หรือกลับกัน) อีกต่อไปเหมือนตรรกะเดิมที่แยกอิง course_plo คนละชุดข้อมูลกับ PLO
    """
    if not expected_plo_ids:
        return False, False

    per_plo_results = []
    for plo_id in expected_plo_ids:
        score, has_data = _student_plo_score(plo_clo_weights.get(plo_id, {}), clo_mastery)
        is_plo_achieved = has_data and score >= PLO_ACHIEVEMENT_THRESHOLD_PERCENT
        per_plo_results.append((is_plo_achieved, has_data))

    has_data = any(plo_has_data for _, plo_has_data in per_plo_results)
    is_achieved = all(plo_has_data and plo_achieved for plo_achieved, plo_has_data in per_plo_results)
    return is_achieved, has_data


@router.get("/achievement/by-year", response_model=YLOCohortAchievement)
def get_ylo_achievement(
    curriculum_id: int = Query(..., description="Curriculum ID"),
    year_level: int = Query(..., ge=1, le=4, description="ชั้นปี 1-4"),
    cohort_year: int | None = Query(None, description="กรองเฉพาะรุ่นที่เข้าเรียนปีนี้ (เช่น 66) - ไม่ใส่ = รวมทุกรุ่น"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "instructor")),
):
    """
    ทำอะไร : endpoint หลักของหน้า "YLO ตามชั้นปี" — คืนผลบรรลุ YLO ของชั้นปีหนึ่ง (year_level) สำหรับ
             นักศึกษาทั้งรุ่นที่เรียนถึงปีนั้นแล้ว พร้อมรายวิชาของปีนั้น กรองตามรุ่น (cohort_year) ได้

    สิทธิ์ (curriculum-level - ตั้งใจเปิดกว้าง) : admin หรืออาจารย์คนไหนก็ได้ เหมือน
    GET /plo/achievement/cohort (ดูเหตุผลที่นั่น ใน plo_calculation.py)

    เชื่อมกับ : ใช้ _build_ylo_requirements + _clo_mastery_for_student (คำนวณทีละคนในลูป ไม่ได้ batch
                เหมือนฝั่ง PLO — ดู "ถ้าแก้" ด้านล่าง) และ _year_courses — เรียกโดยหน้า "YLO ตามชั้นปี"

    ถ้าแก้ : เฉพาะนักศึกษาที่ชั้นปีปัจจุบัน (คำนวณสดจาก cohort_year - ดู app/services/year_level.py) >=
             year_level ที่ขอเท่านั้นถึงจะถูกนับ (คนที่ยังเรียนไม่ถึงปีนี้ยังไม่มีโอกาสสอบวิชาที่กำหนด
             YLO ปีนี้ ไม่ควรถูกนับเป็น "ไม่บรรลุ") กรองที่ระดับ SQL ผ่าน min_cohort_year_for_level()
             (เทียบ cohort_year ตรงๆ) แทนการดึงนักศึกษาทุกคนมาคำนวณทีละคนในหน่วยความจำ ฟังก์ชันนี้วน
             query mastery ทีละนักศึกษาในลูป (ไม่ batch เหมือน plo_calculation.py) — ถ้า roster
             ใหญ่ขึ้นมากในอนาคต อาจต้องปรับให้ batch แบบเดียวกันเพื่อความเร็ว
    """
    curriculum = db.get(Curriculum, curriculum_id)
    if curriculum is None:
        raise HTTPException(status_code=404, detail="Curriculum not found")

    ylo = (
        db.query(YLO)
        .filter(YLO.curriculum_id == curriculum_id, YLO.year_level == year_level)
        .first()
    )

    available_cohort_years = sorted(
        {
            row[0]
            for row in db.query(Student.cohort_year)
            .filter(Student.curriculum_id == curriculum_id, Student.cohort_year.isnot(None))
            .distinct()
            .all()
        }
    )

    # เฉพาะนักศึกษาที่เรียนถึงชั้นปีนี้แล้ว (ชั้นปีจริง >= year_level ที่ขอ) - ปีนี้ยังไม่ถึงแปลว่ายังไม่มี
    # โอกาสได้เรียน/สอบวิชาที่กำหนด YLO ปีนี้เลย จึงไม่ควรถูกนับเป็น "ไม่บรรลุ" ปนเข้ามา - กรองผ่าน
    # cohort_year ตรงๆ (min_cohort_year_for_level เป็นด้านกลับของ current_year_level()) แทนการดึง
    # นักศึกษาทุกคนมาคำนวณทีละคนในหน่วยความจำ
    students_query = db.query(Student).filter(
        Student.curriculum_id == curriculum_id,
        Student.cohort_year <= min_cohort_year_for_level(year_level),
    )
    if cohort_year is not None:
        students_query = students_query.filter(Student.cohort_year == cohort_year)
    students = students_query.all()
    total_students = len(students)
    courses = _year_courses(db, curriculum_id, year_level, cohort_year)

    if ylo is None or total_students == 0:
        return YLOCohortAchievement(
            ylo_id=ylo.id if ylo is not None else 0,
            curriculum_id=curriculum.id,
            curriculum_name=curriculum.name,
            year_level=year_level,
            description=ylo.description if ylo is not None else "",
            total_students=total_students,
            student_count_with_data=0,
            achieved_student_count=0,
            achieved_rate_percent=None,
            coverage_percent=0.0,
            students=[],
            available_cohort_years=available_cohort_years,
            courses=courses,
        )

    plo_clo_weights, _plo_course_clo_ids, _clo_pass_thresholds = _build_plo_requirements(
        db, curriculum_id
    )
    expected_plo_ids = _expected_plo_ids_for_ylo(db, ylo.id)

    student_items = []
    achieved_count = 0
    count_with_data = 0
    for student in students:
        clo_mastery = _clo_mastery_for_student(db, student.id)
        is_achieved, has_data = _student_achieved_ylo(expected_plo_ids, plo_clo_weights, clo_mastery)
        if has_data:
            count_with_data += 1
        if is_achieved:
            achieved_count += 1
        student_items.append(
            YLOAchievementStudentItem(
                student_id=student.id,
                student_name=f"{student.first_name} {student.last_name}",
                is_achieved=is_achieved,
                has_data=has_data,
            )
        )
    # เรียงตามรหัสนักศึกษาจากน้อยไปมาก ไม่ใช่ตามชื่อ - ผู้เรียก endpoint นี้ไม่ควรต้องมา sort ซ้ำเองอีกที
    # ใช้ string sort ตรงๆ (ไม่ int()) เพราะรหัสจริงในระบบเป็นตัวเลขความยาวคงที่เสมอ (เช่น
    # "660112230027") ทำให้ string sort ให้ผลเหมือน numeric sort ทุกประการ และไม่พังกับรหัสทดสอบที่ไม่ใช่
    # ตัวเลขล้วน (เช่น "TEST001" ที่ใช้ในเทสอื่นของระบบนี้ - int("TEST001") จะ raise ValueError ทันที)
    student_items.sort(key=lambda s: s.student_id)

    # หารด้วยนักศึกษาที่มีข้อมูล (count_with_data) ไม่ใช่ total_students (TASK-plo-denominator หลักการ
    # เดียวกัน) - None ถ้าไม่มีใครมีข้อมูลเลย (หารไม่ได้ ไม่ใช่ 0%)
    achieved_rate_percent = (
        float((Decimal(achieved_count) / Decimal(count_with_data) * Decimal(100)).quantize(Decimal("0.1")))
        if count_with_data > 0
        else None
    )
    coverage_percent = float(
        (Decimal(count_with_data) / Decimal(total_students) * Decimal(100)).quantize(Decimal("0.1"))
    )

    return YLOCohortAchievement(
        ylo_id=ylo.id,
        curriculum_id=curriculum.id,
        curriculum_name=curriculum.name,
        year_level=year_level,
        description=ylo.description,
        total_students=total_students,
        student_count_with_data=count_with_data,
        achieved_student_count=achieved_count,
        achieved_rate_percent=achieved_rate_percent,
        coverage_percent=coverage_percent,
        students=student_items,
        courses=courses,
        available_cohort_years=available_cohort_years,
    )


# ชั้นปีมี 4 ระดับเสมอตามโครงสร้างหลักสูตร (สมมติฐานเดียวกับที่หน้า YLOYearProgress.jsx ใช้)
_STUDENT_YEAR_LEVELS = (1, 2, 3, 4)


@router.get("/achievement/student", response_model=StudentYLOAchievement)
def get_student_ylo_achievement(
    student_id: str = Query(..., description="Student ID, e.g. 6500001"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "instructor")),
):
    """
    ทำอะไร : เวอร์ชันรายบุคคลของ /achievement/by-year — แทนที่จะเป็น "ปีเดียว ทุกคน" กลายเป็น
             "ทุกปี คนเดียว" คืนผลบรรลุ YLO ครบทั้ง 4 ปีของนักศึกษา 1 คน พร้อมรายวิชาและสถานะผ่าน/
             ไม่ผ่านของแต่ละวิชาในแต่ละปี

    สิทธิ์ (curriculum-level - ตั้งใจเปิดกว้าง) : admin หรืออาจารย์คนไหนก็ได้ เหมือน
    GET /plo/achievement (ดูเหตุผลที่นั่น ใน plo_calculation.py)

    เชื่อมกับ : ใช้ในหน้ารายละเอียดนักศึกษา (student-plo) สำหรับ hierarchy รายวิชา -> YLO (รายปี) ->
                PLO เรียก _build_plo_requirements / _student_achieved_ylo / _year_courses ชุดเดียวกับ
                /achievement/by-year เพื่อให้ตัดสิน "บรรลุ YLO" ตรงกันทุกที่

    ถ้าแก้ : สถานะผ่าน/ไม่ผ่าน "รายวิชา" ที่แสดงในนี้ (course_items) คำนวณแยกจาก is_achieved ของ YLO
             — นับ CLO ทุกตัวของวิชานั้นทั้งหมด ไม่ใช่แค่ CLO ที่เกี่ยวกับ PLO กลุ่มของ YLO ปีนั้น (ต่างจาก
             requirements ที่ใช้ตัดสิน is_achieved ของ YLO) ตั้งใจแยกเพราะ "วิชานี้ผ่านไหม" ในมุมมอง
             ทั่วไปของนักศึกษา ควรตอบคำถาม "ผ่านทุก CLO ของวิชา" ไม่ใช่แค่ CLO ที่เกี่ยวกับ YLO เดียว
    """
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")

    student_year_level = current_year_level(student.cohort_year).level

    ylo_by_year = {
        y.year_level: y
        for y in db.query(YLO).filter(YLO.curriculum_id == student.curriculum_id).all()
    }
    clo_mastery = _clo_mastery_for_student(db, student.id)
    plo_clo_weights, _plo_course_clo_ids, _clo_pass_thresholds = _build_plo_requirements(
        db, student.curriculum_id
    )
    enrolled_course_ids = {
        row[0]
        for row in db.query(CourseOffering.course_id)
        .join(Enrollment, Enrollment.offering_id == CourseOffering.id)
        .filter(Enrollment.student_id == student.id)
        .distinct()
        .all()
    }

    years: list[StudentYLOYearItem] = []
    for year_level in _STUDENT_YEAR_LEVELS:
        ylo = ylo_by_year.get(year_level)
        year_courses = _year_courses(db, student.curriculum_id, year_level, student.cohort_year)

        if ylo is not None:
            expected_plo_ids = _expected_plo_ids_for_ylo(db, ylo.id)
            is_achieved, has_data = _student_achieved_ylo(expected_plo_ids, plo_clo_weights, clo_mastery)
        else:
            is_achieved, has_data = False, False

        # ผ่าน/ไม่ผ่านรายวิชา = ทุก CLO ของวิชานั้น (ทั้งหมด ไม่ใช่แค่ที่เกี่ยวกับ YLO นี้) ผ่านเกณฑ์ของตัวเอง
        course_ids_this_year = [c.course_id for c in year_courses]
        clos_this_year = (
            db.query(CLO).filter(CLO.course_id.in_(course_ids_this_year)).all()
            if course_ids_this_year
            else []
        )
        clo_ids_by_course: dict[int, set[int]] = {}
        for clo in clos_this_year:
            clo_ids_by_course.setdefault(clo.course_id, set()).add(clo.id)
        course_clo_pass_thresholds = {c.id: c.pass_threshold_percent for c in clos_this_year}

        course_items = [
            StudentYLOCourseItem(
                course_id=c.course_id,
                course_code=c.course_code,
                name_th=c.name_th,
                is_enrolled=c.course_id in enrolled_course_ids,
                passed=bool(clo_ids_by_course.get(c.course_id))
                and all(
                    _clo_passed(clo_id, clo_mastery, course_clo_pass_thresholds)
                    for clo_id in clo_ids_by_course[c.course_id]
                ),
            )
            for c in year_courses
        ]

        years.append(
            StudentYLOYearItem(
                year_level=year_level,
                ylo_description=ylo.description if ylo is not None else "",
                is_reached=student_year_level >= year_level,
                is_achieved=is_achieved,
                has_data=has_data,
                courses=course_items,
            )
        )

    return StudentYLOAchievement(
        student_id=student.id,
        curriculum_id=student.curriculum_id,
        years=years,
    )
