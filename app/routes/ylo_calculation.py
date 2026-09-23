"""
ทำอะไร : เส้นทาง API สำหรับคำนวณ "% บรรลุ YLO" (ผลลัพธ์การเรียนรู้ระดับชั้นปี) ของนักศึกษา ทั้งแบบ
         รายรุ่นต่อชั้นปีเดียว (by-year) และรายบุคคลทุกปีพร้อมกัน (student) เป็นฟีเจอร์ที่เพิ่มเข้ามาใหม่
         — ก่อนหน้านี้ระบบยังไม่มีการคำนวณ "% บรรลุ YLO" เลย (พบตอนสร้างหน้า "YLO ตามชั้นปี" ซึ่งเดิม
         แสดงแค่ข้อความเป้าหมาย YLO เฉย ๆ) ไฟล์นี้ import _clo_passed จาก plo_calculation.py มาใช้ตรง ๆ
         (ไม่ copy/แก้ไข) เพราะนิยาม "ผ่าน CLO" ต้องเหมือนกันทุกที่ในระบบ

สูตรคำนวณ (ตาม spec ที่ยืนยันแล้ว) :
  นักศึกษาจะ "บรรลุ YLO ปีที่ N" ของหลักสูตรหนึ่ง ๆ ก็ต่อเมื่อผ่านทุกวิชาที่เข้าเงื่อนไข 2 ข้อพร้อมกัน :
    (ก) วิชานั้นถูก mark responsibility_level='primary' ใน course_plo กับ PLO ข้อใดข้อหนึ่งที่ YLO
        นี้ถูก map ไว้ (ผ่าน ylo_plo_mapping — YLO 1 ปีมักถูก map กับหลาย PLO พร้อมกัน เงื่อนไขนี้คือ
        union ของทุก PLO เหล่านั้น ไม่ใช่แค่ PLO เดียว) — ทุก CLO ของวิชานั้นนับรวมเท่ากันหมด ไม่มีการ
        เลือกเฉพาะบาง CLO
    (ข) วิชานั้นถูกกำหนดไว้ใน study_plan ให้สอนที่ year_level N ของหลักสูตรเดียวกัน (วิชาจากปีอื่นที่
        บังเอิญแชร์ PLO เดียวกับ YLO นี้จะถูกตัดออก — เงื่อนไข (ข) นี่แหละที่กันวิชาปีอื่นไม่ให้หลุดเข้ามา)
  "ผ่านวิชา" (สำหรับ YLO นี้) = ทุก CLO ของวิชานั้นผ่าน pass_threshold_percent ของตัวเอง (กฎผ่าน/ไม่ผ่าน
  ต่อ CLO เดียวกับที่ใช้คำนวณ PLO)
  YLO ที่ไม่มีวิชาเข้าเงื่อนไขเลย (ไม่มี PLO ที่ map ไว้ หรือไม่มีวิชาใน study_plan ปีนั้นตรงกับ PLO กลุ่ม
  นี้เลย) จะถูกรายงานว่า "ยังไม่บรรลุ" — ไม่มีข้อมูลให้ตัดสิน ไม่ใช่ผ่านอัตโนมัติ กฎเดียวกับฝั่ง PLO

เชื่อมกับ : - อ่านจากตาราง course_plo, study_plan, ylo_plo_mapping, clo, item_clo, student_score
            - GET /ylo/achievement/by-year ถูกเรียกจากหน้า "YLO ตามชั้นปี"
            - GET /ylo/achievement/student ถูกเรียกจากหน้าผลบรรลุรายบุคคล (student-plo) สำหรับ
              hierarchy รายวิชา -> YLO (รายปี) -> PLO

ถ้าแก้ : แก้เงื่อนไข (ก)/(ข) หรือเกณฑ์ผ่าน CLO จะกระทบ % บรรลุ YLO ทั้งระบบทันที (ทั้งสอง endpoint
         ในไฟล์นี้ใช้ตรรกะเดียวกัน)
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
    CoursePLO,
    Curriculum,
    Enrollment,
    AssessmentItem,
    ItemCLO,
    Student,
    StudentScore,
    StudyPlan,
    User,
    YLO,
    YLOPLOMapping,
)
from app.routes.plo_calculation import _clo_passed
from app.services.year_level import current_year_level, min_cohort_year_for_level

router = APIRouter(prefix="/ylo", tags=["YLO Achievement"])


# ผลบรรลุ YLO ของนักศึกษา 1 คน (ใช้เป็นรายการย่อยใน YLOCohortAchievement.students)
class YLOAchievementStudentItem(BaseModel):
    student_id: str
    student_name: str
    is_achieved: bool


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
    courses: list[StudentYLOCourseItem]


# response ของ GET /ylo/achievement/student — ผลบรรลุ YLO ครบทั้ง 4 ปีของนักศึกษา 1 คน
class StudentYLOAchievement(BaseModel):
    student_id: str
    curriculum_id: int
    years: list[StudentYLOYearItem]


# response ของ GET /ylo/achievement/by-year — ผลบรรลุ YLO ปีเดียว ของนักศึกษาทั้งรุ่น
class YLOCohortAchievement(BaseModel):
    ylo_id: int
    curriculum_id: int
    curriculum_name: str
    year_level: int
    description: str
    total_students: int
    achieved_student_count: int
    achieved_rate_percent: float
    students: list[YLOAchievementStudentItem]
    available_cohort_years: list[int] = []
    # รายวิชาที่เปิดสอนชั้นปีนี้ตามแผนการศึกษา (study_plan) - ทุกวิชาที่กำหนดไว้ ไม่ใช่แค่วิชาที่ถูกใช้
    # คำนวณ YLO นี้ (ดู _build_ylo_requirements ที่กรองเฉพาะวิชา responsibility_level='primary' ต่อ PLO
    # กลุ่มนี้) - จุดประสงค์ต่างกัน: อันนี้ตอบ "ปีนี้เรียนอะไรบ้าง" ไม่ใช่ "อะไรที่ใช้ตัดสิน YLO"
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


def _build_ylo_requirements(
    db: Session, ylo: YLO, cohort_year: int | None
) -> dict[int, set[int]]:
    """
    ทำอะไร : สร้างตาราง course_id -> เซตของ CLO id ทั้งหมดของวิชานั้น เฉพาะวิชาที่ถูก mark
             responsibility_level='primary' (course_plo) กับ PLO ข้อใดข้อหนึ่งในกลุ่ม PLO ของ YLO
             นี้ "และ" อยู่ในวิชาที่กำหนดสอนที่ year_level ของ YLO นี้ด้วย — ใช้ทั้งเงื่อนไข (ก) และ
             (ข) จากคอมเมนต์หัวไฟล์พร้อมกัน ทำให้วิชาจากปีอื่นไม่มีทางหลุดเข้ามาแม้จะแชร์ PLO กับ YLO
             นี้ก็ตาม

    เชื่อมกับ : อ่านจาก ylo_plo_mapping (หา PLO กลุ่มของ YLO นี้), _study_plan_course_ids (หาวิชาของปี
                นี้), course_plo, clo — ถูกเรียกโดย get_ylo_achievement และ
                get_student_ylo_achievement

    ถ้าแก้ : เป็นจุดกำหนด "วิชาบังคับของ YLO นี้" ทั้งหมด แก้เงื่อนไข (ก)/(ข) ที่นี่กระทบผลบรรลุ YLO
             โดยตรง
    """
    plo_ids = {
        row[0]
        for row in db.query(YLOPLOMapping.plo_id).filter(YLOPLOMapping.ylo_id == ylo.id).all()
    }
    if not plo_ids:
        return {}

    course_ids_this_year = _study_plan_course_ids(db, ylo.curriculum_id, ylo.year_level, cohort_year)
    if not course_ids_this_year:
        return {}

    primary_course_ids = {
        row[0]
        for row in db.query(CoursePLO.course_id)
        .filter(
            CoursePLO.plo_id.in_(plo_ids),
            CoursePLO.responsibility_level == "primary",
            CoursePLO.course_id.in_(course_ids_this_year),
        )
        .all()
    }
    if not primary_course_ids:
        return {}

    rows = db.query(CLO.id, CLO.course_id).filter(CLO.course_id.in_(primary_course_ids)).all()
    requirements: dict[int, set[int]] = {}
    for clo_id, course_id in rows:
        requirements.setdefault(course_id, set()).add(clo_id)
    return requirements


def _clo_mastery_for_student(db: Session, student_id: str) -> dict[int, Decimal]:
    """
    ทำอะไร : คำนวณระดับความเชี่ยวชาญ (mastery) ต่อ CLO ของนักศึกษา 1 คน ด้วยสูตรค่าเฉลี่ยถ่วงน้ำหนัก
             เดียวกับ plo_calculation.py/clo_calculation.py คำนวณจากทุกวิชาที่ลงทะเบียนทั้งหมด (ไม่จำกัด
             เฉพาะวิชาใดวิชาหนึ่ง)

    เชื่อมกับ : จงใจ "เขียนซ้ำ" สูตรนี้ในไฟล์นี้ แทนที่จะ import ฟังก์ชัน private ข้ามไฟล์จาก
                plo_calculation.py เพื่อให้ไฟล์นั้นไม่ต้องถูกแก้เพื่อ export อะไรเพิ่ม — เรียกโดย
                get_ylo_achievement และ get_student_ylo_achievement

    ถ้าแก้ : ถ้าแก้สูตรตรงนี้ ต้องแก้ _clo_mastery_for_student ใน plo_calculation.py ให้ตรงกันด้วย
             ไม่งั้นผลบรรลุ PLO กับ YLO จะคำนวณ mastery ไม่ตรงกัน
    """
    offering_ids = [
        row[0]
        for row in db.query(Enrollment.offering_id).filter(Enrollment.student_id == student_id).all()
    ]
    if not offering_ids:
        return {}

    items = db.query(AssessmentItem).filter(AssessmentItem.offering_id.in_(offering_ids)).all()
    item_by_id = {item.id: item for item in items}
    if not item_by_id:
        return {}

    scores = (
        db.query(StudentScore)
        .filter(StudentScore.student_id == student_id, StudentScore.item_id.in_(item_by_id.keys()))
        .all()
    )
    score_by_item = {s.item_id: s.score_obtained for s in scores}

    item_clos = db.query(ItemCLO).filter(ItemCLO.item_id.in_(item_by_id.keys())).all()

    clo_weighted_sum: dict[int, Decimal] = {}
    clo_weight_total: dict[int, Decimal] = {}
    for ic in item_clos:
        score = score_by_item.get(ic.item_id)
        item = item_by_id.get(ic.item_id)
        # ข้ามชิ้นงานที่ยังไม่มีคะแนน หรือคะแนนเต็มเป็น 0 (หารไม่ได้)
        if score is None or item is None or item.total_score <= 0:
            continue
        # แปลงคะแนนดิบเป็น % แล้วถ่วงน้ำหนักด้วย weight_percent สะสมแยกตาม CLO (สูตรเดียวกับ
        # plo_calculation.py._clo_mastery_for_student)
        item_percent = (score / item.total_score) * Decimal(100)
        clo_weighted_sum[ic.clo_id] = clo_weighted_sum.get(ic.clo_id, Decimal(0)) + item_percent * ic.weight_percent
        clo_weight_total[ic.clo_id] = clo_weight_total.get(ic.clo_id, Decimal(0)) + ic.weight_percent

    return {
        clo_id: clo_weighted_sum[clo_id] / clo_weight_total[clo_id]
        for clo_id in clo_weighted_sum
        if clo_weight_total[clo_id] > 0
    }


def _clo_pass_thresholds(db: Session, clo_ids: set[int]) -> dict[int, Decimal]:
    """
    ทำอะไร : ดึงเกณฑ์ผ่าน (pass_threshold_percent) ของ CLO ที่ขอมา คืนเป็น {clo_id: threshold}

    เชื่อมกับ : ใช้คู่กับผลจาก _build_ylo_requirements ก่อนเรียก _student_achieved_ylo

    ถ้าแก้ : คืน dict ว่างถ้า clo_ids ว่างเปล่า (ไม่ query เปล่า ๆ)
    """
    if not clo_ids:
        return {}
    return {c.id: c.pass_threshold_percent for c in db.query(CLO).filter(CLO.id.in_(clo_ids)).all()}


def _student_achieved_ylo(
    requirements: dict[int, set[int]],
    clo_mastery: dict[int, Decimal],
    clo_pass_thresholds: dict[int, Decimal],
) -> bool:
    """
    ทำอะไร : ตัดสินว่านักศึกษา "บรรลุ YLO" ปีนี้หรือไม่ — บรรลุก็ต่อเมื่อผ่านทุกวิชาบังคับ (จาก
             _build_ylo_requirements) โดยแต่ละวิชาต้องผ่านทุก CLO ของตัวเอง YLO ที่ไม่มีวิชาบังคับเลย
             ถือว่า "ยังไม่บรรลุ" (ไม่มีข้อมูลให้ตัดสิน ไม่ใช่ผ่านอัตโนมัติ)

    เชื่อมกับ : เรียก _clo_passed (import จาก plo_calculation.py) ทีละ CLO — ใช้โดย
                get_ylo_achievement และ get_student_ylo_achievement

    ถ้าแก้ : เป็นจุดตัดสินใจหลักของผลบรรลุ YLO ทั้งระบบ
    """
    if not requirements:
        return False
    return all(
        all(_clo_passed(clo_id, clo_mastery, clo_pass_thresholds) for clo_id in clo_ids)
        for clo_ids in requirements.values()
    )


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
            achieved_student_count=0,
            achieved_rate_percent=0.0,
            students=[],
            available_cohort_years=available_cohort_years,
            courses=courses,
        )

    requirements = _build_ylo_requirements(db, ylo, cohort_year)
    required_clo_ids = {clo_id for clo_ids in requirements.values() for clo_id in clo_ids}
    clo_pass_thresholds = _clo_pass_thresholds(db, required_clo_ids)

    student_items = []
    achieved_count = 0
    for student in students:
        clo_mastery = _clo_mastery_for_student(db, student.id)
        achieved = _student_achieved_ylo(requirements, clo_mastery, clo_pass_thresholds)
        if achieved:
            achieved_count += 1
        student_items.append(
            YLOAchievementStudentItem(
                student_id=student.id,
                student_name=f"{student.first_name} {student.last_name}",
                is_achieved=achieved,
            )
        )
    # เรียงตามรหัสนักศึกษาจากน้อยไปมาก ไม่ใช่ตามชื่อ - ผู้เรียก endpoint นี้ไม่ควรต้องมา sort ซ้ำเองอีกที
    # ใช้ string sort ตรงๆ (ไม่ int()) เพราะรหัสจริงในระบบเป็นตัวเลขความยาวคงที่เสมอ (เช่น
    # "660112230027") ทำให้ string sort ให้ผลเหมือน numeric sort ทุกประการ และไม่พังกับรหัสทดสอบที่ไม่ใช่
    # ตัวเลขล้วน (เช่น "TEST001" ที่ใช้ในเทสอื่นของระบบนี้ - int("TEST001") จะ raise ValueError ทันที)
    student_items.sort(key=lambda s: s.student_id)

    achieved_rate_percent = (
        Decimal(achieved_count) / Decimal(total_students) * Decimal(100)
    ).quantize(Decimal("0.1"))

    return YLOCohortAchievement(
        ylo_id=ylo.id,
        curriculum_id=curriculum.id,
        curriculum_name=curriculum.name,
        year_level=year_level,
        description=ylo.description,
        total_students=total_students,
        achieved_student_count=achieved_count,
        achieved_rate_percent=float(achieved_rate_percent),
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
                PLO เรียก _build_ylo_requirements / _student_achieved_ylo / _year_courses ชุดเดียวกับ
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
            requirements = _build_ylo_requirements(db, ylo, student.cohort_year)
            required_clo_ids = {clo_id for clo_ids in requirements.values() for clo_id in clo_ids}
            ylo_clo_pass_thresholds = _clo_pass_thresholds(db, required_clo_ids)
            is_achieved = _student_achieved_ylo(requirements, clo_mastery, ylo_clo_pass_thresholds)
        else:
            is_achieved = False

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
                courses=course_items,
            )
        )

    return StudentYLOAchievement(
        student_id=student.id,
        curriculum_id=student.curriculum_id,
        years=years,
    )
