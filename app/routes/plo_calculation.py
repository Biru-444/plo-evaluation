"""
ทำอะไร : เส้นทาง API สำหรับคำนวณ "% บรรลุ PLO" ของนักศึกษา — ทั้งแบบรายบุคคล, รายรุ่น (cohort),
         และแบบแยกตามชั้นปี (by-year) ถือเป็นไฟล์แกนกลางที่สุดของระบบ เพราะทุกหน้าที่แสดงผลบรรลุ
         PLO (ภาพรวม PLO, ผลบรรลุรายบุคคล, YLO ตามชั้นปี) ดึงตัวเลขมาจากที่นี่ทั้งหมด

สูตรคำนวณ (all-or-nothing ตาม spec ที่ยืนยันแล้ว — ไม่ใช่คะแนนเฉลี่ยแบบต่อเนื่อง) :
  1. ระดับความเชี่ยวชาญ (mastery) ของแต่ละ CLO = ค่าเฉลี่ยถ่วงน้ำหนักของ % คะแนนที่นักศึกษาได้ในทุก
     assessment item ที่วัด CLO นั้น ถ่วงน้ำหนักด้วย item_clo.weight_percent (สูตรเดียวกับใน
     clo_calculation.py) — CLO ที่นักศึกษาไม่มีคะแนนบันทึกไว้เลยจะไม่มีค่า mastery
  2. CLO จะ "ผ่าน" ก็ต่อเมื่อ mastery >= pass_threshold_percent ของ CLO นั้นเอง (กำหนดแยกได้ต่อ CLO
     ไม่ใช่ค่าคงที่ตายตัวทั้งระบบ) ไม่มีค่า mastery = ไม่ผ่าน
  3. สำหรับ PLO ข้อหนึ่ง ๆ CLO ที่มีแถวใน clo_plo_mapping ผูกกับ PLO นั้นโดยตรง (ตาม มคอ.3 ของแต่ละ
     วิชา — 1 CLO ผูกได้กับหลาย PLO และแต่ละ CLO ของวิชาเดียวกันไม่จำเป็นต้องผูกกับ PLO ชุดเดียวกัน)
     ถือเป็นหลักฐานของ PLO นั้น จัดกลุ่มตามวิชาที่ CLO นั้นสังกัดอยู่ นักศึกษาจะ "ผ่านวิชาสำหรับ PLO
     นี้" ก็ต่อเมื่อผ่านทุก CLO ของวิชานั้นที่ถูกผูกกับ PLO นี้ (ไม่ใช่ทุก CLO ของวิชา — วิชาเดียวกันอาจมี
     CLO ที่ผูกกับ PLO อื่นซึ่งไม่เกี่ยวกับ PLO นี้เลย) — รายชื่อวิชา/CLO ที่เกี่ยวข้องหาได้จาก
     clo_plo_mapping โดยตรง ไม่ขึ้นกับว่านักศึกษาคนนั้นลงทะเบียนวิชานั้นจริงหรือไม่
  4. นักศึกษาจะ "บรรลุ PLO" ก็ต่อเมื่อผ่านทุกวิชาที่มี CLO ผูกกับ PLO นั้น — PLO ที่ไม่มี CLO ผูกอยู่
     เลยจะถูกรายงานว่า "ยังไม่บรรลุ" (ไม่มีข้อมูลให้ตัดสิน ไม่ใช่ผ่านอัตโนมัติ)
  achieved_percent เป็น 100.0/0.0 เสมอ (สะท้อนค่า is_achieved ตรง ๆ) ไม่ใช่ตัวเลขบางส่วน เพราะโมเดลนี้
  ไม่มีแนวคิด "บรรลุบางส่วน" อีกต่อไป

เชื่อมกับ : - อ่าน/เขียนผ่านตาราง clo_plo_mapping, course, clo, item_clo, assessment_item,
              student_score ในฐานข้อมูล PostgreSQL (course_plo ไม่ได้ใช้คำนวณตรงนี้แล้ว — ยังเก็บไว้
              ใช้แสดง Curriculum Mapping ระดับหลักสูตรเท่านั้น ดู app/routes/course_plo.py)
            - GET /plo/achievement ถูกเรียกจากหน้าผลบรรลุรายบุคคล (student-plo / PLOAchievement.jsx)
            - GET /plo/achievement/cohort ถูกเรียกจากหน้า "ภาพรวม PLO" (PLODetailPage.jsx)
            - GET /plo/achievement/by-year ถูกเรียกจากหน้า "YLO ตามชั้นปี" (สำหรับ course_count
              ต่อปี — ตัวเลข achievement ของ endpoint นี้เองยังไม่ถูกแสดงผลที่ไหนใน UI ปัจจุบัน)
            - ylo_calculation.py ยังใช้ course_plo ของตัวเอง (_build_ylo_requirements) ไม่ได้เปลี่ยน
              ตาม — import แค่ _clo_passed จากไฟล์นี้ไปใช้ตัดสิน "ผ่าน CLO" แบบเดียวกัน

ถ้าแก้ : แก้สูตรในไฟล์นี้ (โดยเฉพาะที่มาของ CLO ที่นับเป็นหลักฐานของ PLO หรือเกณฑ์ผ่าน CLO) จะกระทบ
         % บรรลุ PLO ทั้งระบบทันที (หน้าภาพรวม PLO, ผลบรรลุรายบุคคล, /courses/{id}/enrolled-students
         ?plo_id=) รวมถึงทำให้ผลของ tests/test_plo_achievement_cohort.py และ
         tests/test_courses_enrolled_students_mastery.py เปลี่ยนไปด้วย ลำดับการลงทะเบียน router ของ
         ไฟล์นี้ใน app/main.py ก็มีผลต่อการทำงาน (ดูคอมเมนต์ใน main.py) ห้ามสลับลำดับ
"""
from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import (
    CLO,
    CLOPLOMapping,
    Course,
    CourseOffering,
    Curriculum,
    Enrollment,
    AssessmentItem,
    ItemCLO,
    PLO,
    Student,
    StudentScore,
    StudyPlan,
    User,
    YLO,
    YLOPLOMapping,
)

router = APIRouter(prefix="/plo", tags=["PLO Achievement"])


# ผลบรรลุ PLO ข้อเดียวของนักศึกษา 1 คน (ใช้เป็นรายการย่อยใน StudentPLOAchievement ด้านล่าง)
class PLOAchievementItem(BaseModel):
    plo_id: int
    plo_code: str
    description: str
    achieved_percent: float
    is_achieved: bool


# ผลบรรลุ PLO ทุกข้อของนักศึกษา 1 คน — response ของ GET /plo/achievement (รายบุคคล)
class StudentPLOAchievement(BaseModel):
    student_id: str
    student_name: str
    curriculum_id: int
    plo_achievements: list[PLOAchievementItem]


# สรุปผลบรรลุ PLO ข้อเดียวของทั้งรุ่น/หลักสูตร (ค่าเฉลี่ย + จำนวนคนที่บรรลุ) — ใช้ในหน้า "ภาพรวม PLO"
class PLOCohortSummaryItem(BaseModel):
    plo_id: int
    plo_code: str
    description: str
    student_count_with_data: int
    average_achieved_percent: float
    achieved_student_count: int
    achieved_rate_percent: float


# response หลักของ GET /plo/achievement/cohort — สรุปทั้งหลักสูตร + รายชื่อนักศึกษาทุกคนพร้อมผลบรรลุ
class CurriculumPLOAchievement(BaseModel):
    curriculum_id: int
    curriculum_name: str
    total_students: int
    plo_summary: list[PLOCohortSummaryItem]
    students: list[StudentPLOAchievement]
    available_cohort_years: list[int] = []
    # สถิติวงแหวน "บรรลุ PLO ครบทุกข้อ" (hero stat หน้า "ภาพรวม PLO") - "ครบทุกข้อ" นับเฉพาะ PLO ที่
    # qualifying_plo_count (ดู _qualifying_plo_ids) ไม่ใช่ total_plo_count ทั้งหมด เพราะ PLO ที่ไม่มี
    # วิชา "หลัก" ที่ผ่านเกณฑ์คำนวณเลยเป็นไปไม่ได้อยู่แล้วโดยดีไซน์ ไม่ควรทำให้วงแหวนนี้ค้างที่ 0% ตลอด
    all_plo_achieved_count: int = 0
    all_plo_achieved_percent: float = 0.0
    qualifying_plo_count: int = 0
    total_plo_count: int = 0


# เหมือน PLOCohortSummaryItem แต่เพิ่ม is_expected_this_year (PLO นี้ถูกคาดหวังในชั้นปีนี้หรือไม่
# ตาม ylo_plo_mapping) — ใช้ในสรุปผลบรรลุ PLO แยกตามชั้นปี
class YearlyPLOSummaryItem(BaseModel):
    plo_id: int
    plo_code: str
    description: str
    is_expected_this_year: bool
    student_count_with_data: int
    average_achieved_percent: float
    achieved_student_count: int
    achieved_rate_percent: float


# ผลบรรลุ PLO ของชั้นปีเดียว (1 ใน 4 ปี) — รายการย่อยใน CurriculumYearProgress ด้านล่าง
class YearProgressItem(BaseModel):
    year_level: int
    ylo_description: str
    course_count: int
    plo_summary: list[YearlyPLOSummaryItem]
    students: list[StudentPLOAchievement]


# response หลักของ GET /plo/achievement/by-year — ผลบรรลุ PLO แยกเป็น 4 ก้อนตามชั้นปี
class CurriculumYearProgress(BaseModel):
    curriculum_id: int
    curriculum_name: str
    years: list[YearProgressItem]
    available_cohort_years: list[int] = []


# วิชาบังคับ 1 วิชาของ PLO ข้อหนึ่ง พร้อมสถานะผ่าน/ไม่ผ่านของนักศึกษาคนเดียว — response ของ
# GET /plo/{plo_id}/students/{student_id}/course-breakdown
class StudentPLOCourseBreakdownItem(BaseModel):
    course_id: int
    course_code: str
    name_th: str
    passed: bool


def _build_plo_requirements(
    db: Session, curriculum_id: int
) -> tuple[dict[int, dict[int, set[int]]], dict[int, Decimal]]:
    """
    ทำอะไร : สร้างตาราง "PLO แต่ละข้อ มี CLO อะไรบ้างเป็นหลักฐาน และ CLO เหล่านั้นสังกัดวิชาไหน" คำนวณ
             ต่อหลักสูตรเพียงครั้งเดียว (ไม่ใช่ต่อนักศึกษา) แล้วนำผลไปใช้ซ้ำกับนักศึกษาทุกคนในรุ่น เพื่อลด
             จำนวน query คืนค่าเป็น 2 ตัว : plo_requirements[plo_id][course_id] = เซตของ CLO id ที่ถูก
             ผูกกับ PLO นั้นโดยตรง (ผ่าน clo_plo_mapping) และสังกัดวิชานั้น (อาจเป็นแค่บางส่วนของ CLO
             ทั้งหมดในวิชา ไม่ใช่ทุก CLO เสมอไป — วิชาเดียวกันอาจมี CLO ที่ผูกกับ PLO อื่นแยกกัน), และ
             clo_pass_thresholds[clo_id] = เกณฑ์ผ่านของ CLO นั้น

    เชื่อมกับ : - อ่านจากตาราง clo_plo_mapping, clo, course — กรองเฉพาะ CLO ของวิชาที่อยู่ในหลักสูตรนี้
                  เท่านั้น (course_plo ไม่ได้ใช้ตรงนี้แล้ว — ดูโมดูล docstring ด้านบน)
                - ถูกเรียกจากทุก endpoint ในไฟล์นี้ที่ต้องคำนวณผลบรรลุ PLO รวมถึง
                  courses.py::get_course_enrolled_students (?plo_id=)

    ถ้าแก้ : เปลี่ยนที่มาของ CLO ที่นับเป็นหลักฐานตรงนี้ จะทำให้ % บรรลุ PLO เปลี่ยนทั้งระบบทันที
    """
    rows = (
        db.query(CLOPLOMapping.plo_id, CLO.course_id, CLO.id, CLO.pass_threshold_percent)
        .join(CLO, CLO.id == CLOPLOMapping.clo_id)
        .join(Course, Course.id == CLO.course_id)
        .filter(Course.curriculum_id == curriculum_id)
        .all()
    )
    plo_requirements: dict[int, dict[int, set[int]]] = {}
    clo_pass_thresholds: dict[int, Decimal] = {}
    for plo_id, course_id, clo_id, threshold in rows:
        plo_requirements.setdefault(plo_id, {}).setdefault(course_id, set()).add(clo_id)
        clo_pass_thresholds[clo_id] = threshold
    return plo_requirements, clo_pass_thresholds


def _qualifying_plo_ids(plo_requirements: dict[int, dict[int, set[int]]]) -> set[int]:
    """
    ทำอะไร : หา PLO ที่มี CLO ผูกอยู่อย่างน้อย 1 ตัวผ่านเกณฑ์การคำนวณ (คือมี key อยู่ใน
             plo_requirements เลย — _build_plo_requirements ใส่ key เฉพาะ plo_id ที่เจอ clo_plo_mapping
             จริงเท่านั้น)

    เชื่อมกับ : ใช้ตัดสินว่า PLO ข้อไหนควรถูกนับเป็นส่วนหนึ่งของ "บรรลุ PLO ครบทุกข้อ" (สถิติวงแหวนหน้า
                "ภาพรวม PLO" ดู all_plo_achieved_count/_count_all_qualifying_plo_achieved) — dynamic
                ตามข้อมูล clo_plo_mapping จริงเสมอ ไม่ hardcode รายชื่อ PLO ที่ตัดออก

    ถ้าแก้ : ถ้าข้อมูล clo_plo_mapping เปลี่ยน (เช่นมีคนเติม mapping ให้ PLO ที่เคยไม่มี CLO ผูกเลย)
             ผลลัพธ์จะเปลี่ยนตามอัตโนมัติโดยไม่ต้องแก้โค้ดจุดนี้ — ถ้าลบฟังก์ชันนี้ไป วงแหวน "บรรลุครบทุก
             ข้อ" จะค้างที่ 0% เสมอ เพราะ PLO ที่ไม่มี CLO ผูกเลยเป็นไปไม่ได้อยู่แล้วโดยดีไซน์
    """
    return {plo_id for plo_id, courses in plo_requirements.items() if courses}


def _clo_passed(
    clo_id: int, clo_mastery: dict[int, Decimal], clo_pass_thresholds: dict[int, Decimal]
) -> bool:
    """
    ทำอะไร : ตัดสินว่านักศึกษา "ผ่าน" CLO ข้อนี้หรือไม่ — ผ่านก็ต่อเมื่อ mastery >=
             pass_threshold_percent ของ CLO นั้นเอง ไม่มีข้อมูลคะแนนเลย (mastery หา key ไม่เจอ) = ไม่ผ่าน

    เชื่อมกับ : ใช้กฎเดียวกับที่ clo_calculation.py ใช้แยก "students_without_data" — ถูกเรียกโดย
                _student_passed_course_for_plo และ ylo_calculation.py (import ตรงจากไฟล์นี้)

    ถ้าแก้ : เปลี่ยนเกณฑ์ตรงนี้กระทบทั้งผลบรรลุ PLO และ YLO พร้อมกัน เพราะสองไฟล์ใช้ฟังก์ชันเดียวกัน
    """
    mastery = clo_mastery.get(clo_id)
    if mastery is None:
        return False
    threshold = clo_pass_thresholds.get(clo_id)
    if threshold is None:
        return False
    return mastery >= threshold


def _student_passed_course_for_plo(
    course_clo_ids: set[int], clo_mastery: dict[int, Decimal], clo_pass_thresholds: dict[int, Decimal]
) -> bool:
    """
    ทำอะไร : ตัดสินว่านักศึกษา "ผ่านวิชานี้สำหรับ PLO นี้" หรือไม่ — ผ่านก็ต่อเมื่อผ่านทุก CLO ในกลุ่มนี้
             (course_clo_ids คือ CLO ของวิชาที่ถูกผูกกับ PLO นี้โดยตรงผ่าน clo_plo_mapping เท่านั้น
             อาจเป็นแค่บางส่วนของ CLO ทั้งหมดในวิชา — ดู docstring ของ _build_plo_requirements)

    เชื่อมกับ : เรียก _clo_passed ทีละ CLO — ถูกเรียกโดย _student_achieved_plo และ
                get_student_plo_course_breakdown

    ถ้าแก้ : ถ้าเปลี่ยนจาก all() เป็น any() จะทำให้ผ่านวิชาง่ายขึ้นมาก (แค่ CLO เดียวผ่านก็พอ) ซึ่ง
             ขัดกับ spec ที่ยืนยันแล้วว่าต้องผ่านทุก CLO
    """
    return all(_clo_passed(clo_id, clo_mastery, clo_pass_thresholds) for clo_id in course_clo_ids)


def _student_achieved_plo(
    courses_for_plo: dict[int, set[int]] | None,
    clo_mastery: dict[int, Decimal],
    clo_pass_thresholds: dict[int, Decimal],
) -> bool:
    """
    ทำอะไร : ตัดสินว่านักศึกษา "บรรลุ PLO" ข้อนี้หรือไม่ — บรรลุก็ต่อเมื่อผ่านทุกวิชาที่มี CLO ผูกกับ PLO
             นี้ (ดึงมาจาก clo_plo_mapping แบบ global ไม่ใช่เฉพาะวิชาที่ลงทะเบียนจริง) PLO ที่ไม่มี CLO
             ผูกอยู่เลยถือว่า "ยังไม่บรรลุ" (ไม่มีข้อมูลให้ตัดสิน ไม่ใช่ผ่านอัตโนมัติ)

    เชื่อมกับ : ใช้ courses_for_plo ที่ได้จาก _build_plo_requirements และเรียก
                _student_passed_course_for_plo ทีละวิชา — ผลลัพธ์นี้คือค่า is_achieved ที่แสดงบนหน้า
                ภาพรวม PLO / ผลบรรลุรายบุคคลทุกจุด

    ถ้าแก้ : เป็นจุดตัดสินใจหลักของทั้งระบบ แก้ตรงนี้กระทบ is_achieved/achieved_percent ทุกที่
    """
    if not courses_for_plo:
        return False
    return all(
        _student_passed_course_for_plo(clo_ids, clo_mastery, clo_pass_thresholds)
        for clo_ids in courses_for_plo.values()
    )


def _clo_mastery_for_student(
    db: Session, student_id: str, course_id_filter: set[int] | None = None
) -> dict[int, Decimal]:
    """
    ทำอะไร : คำนวณระดับความเชี่ยวชาญ (mastery) ของนักศึกษา 1 คน แยกเป็นราย CLO ที่เคยถูกประเมิน
             สูตรคือค่าเฉลี่ยถ่วงน้ำหนัก (weighted average) ของ % คะแนนแต่ละชิ้นงาน โดยถ่วงน้ำหนักด้วย
             item_clo.weight_percent (สูตรเดียวกับใน clo_calculation.py) — CLO ที่ไม่มี key อยู่ใน
             dict ที่คืนกลับมา แปลว่าไม่มีข้อมูลคะแนนเลยสักชิ้นงาน (ดู _clo_passed)

    เชื่อมกับ : - อ่านจากตาราง enrollment, assessment_item, student_score, item_clo
                - course_id_filter (ถ้าใส่มา) จำกัดเฉพาะวิชาที่นักศึกษาลงทะเบียนในกลุ่มนั้น ใช้โดย
                  endpoint by-year เพื่อคิดคะแนนเฉพาะวิชาของปีนั้น ๆ ไม่ใส่ = นับทุกวิชาที่ลงทะเบียน

    ถ้าแก้ : เป็นสูตรคำนวณ mastery หลักของทั้งระบบ (ใช้ตัดสิน CLO ผ่าน/ไม่ผ่าน) แก้สูตรตรงนี้กระทบ
             % บรรลุ PLO ทุกจุดที่พึ่งพา mastery
    """
    offering_query = db.query(Enrollment.offering_id).filter(Enrollment.student_id == student_id)
    if course_id_filter is not None:
        offering_query = offering_query.join(
            CourseOffering, CourseOffering.id == Enrollment.offering_id
        ).filter(CourseOffering.course_id.in_(course_id_filter))
    offering_ids = [row[0] for row in offering_query.all()]

    item_by_id: dict[int, AssessmentItem] = {}
    score_by_item: dict[int, Decimal] = {}
    item_clos: list[ItemCLO] = []

    if offering_ids:
        items = (
            db.query(AssessmentItem)
            .filter(AssessmentItem.offering_id.in_(offering_ids))
            .all()
        )
        item_by_id = {item.id: item for item in items}

        if item_by_id:
            scores = (
                db.query(StudentScore)
                .filter(
                    StudentScore.student_id == student_id,
                    StudentScore.item_id.in_(item_by_id.keys()),
                )
                .all()
            )
            score_by_item = {s.item_id: s.score_obtained for s in scores}

            item_clos = (
                db.query(ItemCLO).filter(ItemCLO.item_id.in_(item_by_id.keys())).all()
            )

    clo_weighted_sum: dict[int, Decimal] = {}
    clo_weight_total: dict[int, Decimal] = {}
    for ic in item_clos:
        score = score_by_item.get(ic.item_id)
        item = item_by_id.get(ic.item_id)
        # ข้ามชิ้นงานที่ยังไม่มีคะแนน หรือคะแนนเต็มเป็น 0 (หารไม่ได้) — ไม่นับรวมเข้าสูตรเลย ไม่ใช่นับเป็น 0
        if score is None or item is None or item.total_score <= 0:
            continue
        # แปลงคะแนนดิบเป็น % ก่อน (เช่น 18/20 -> 90%) แล้วค่อยถ่วงน้ำหนักด้วย weight_percent ของ
        # item_clo แต่ละอัน สะสมทั้งตัวตั้ง (weighted_sum) และตัวหาร (weight_total) แยกตาม CLO
        item_percent = (score / item.total_score) * Decimal(100)
        clo_weighted_sum[ic.clo_id] = clo_weighted_sum.get(ic.clo_id, Decimal(0)) + item_percent * ic.weight_percent
        clo_weight_total[ic.clo_id] = clo_weight_total.get(ic.clo_id, Decimal(0)) + ic.weight_percent

    # mastery ของแต่ละ CLO = weighted_sum / weight_total (ถ่วงน้ำหนักเฉลี่ย) — CLO ที่ weight_total
    # เป็น 0 (ไม่มีชิ้นงานที่มีคะแนนเลย) จะไม่มี key อยู่ใน dict ที่คืนกลับ ไม่ใช่คืนค่า 0
    return {
        clo_id: clo_weighted_sum[clo_id] / clo_weight_total[clo_id]
        for clo_id in clo_weighted_sum
        if clo_weight_total[clo_id] > 0
    }


def _clo_mastery_for_students_batch(
    db: Session, student_ids: list[str], course_id_filter: set[int] | None = None
) -> dict[str, dict[int, Decimal]]:
    """
    ทำอะไร : เหมือน _clo_mastery_for_student ทุกประการ (สูตร weighted average เดียวกัน) แต่คำนวณให้
             หลายคนพร้อมกันด้วย query ชุดเดียว คืนค่า {student_id: {clo_id: mastery}} ครบทุก
             student_id ที่ส่งมาเสมอ (dict ว่างถ้าคนนั้นไม่มีข้อมูลเลย ไม่ใช่ key หายไป)

    เชื่อมกับ : ใช้ตอนต้องได้ CLO mastery ของนักศึกษาทั้ง roster พร้อมกัน — เรียกโดย
                get_cohort_plo_achievement และ get_plo_achievement_by_year

    ถ้าแก้ : ห้ามเปลี่ยนกลับไปวนเรียก _clo_mastery_for_student ทีละคนในลูป เพราะจะกลายเป็น N+1
             query — รุ่นที่มีนักศึกษาเยอะ (~200 คน) เคยทำให้ backend ตอบช้าจนเกิน timeout ของ
             frontend แม้จะคำนวณเสร็จถูกต้องในที่สุดก็ตาม (ดูรายละเอียดใน
             _calculate_plo_achievement_from_mastery ด้านล่าง)
    """
    result: dict[str, dict[int, Decimal]] = {sid: {} for sid in student_ids}
    if not student_ids:
        return result

    offering_query = db.query(Enrollment.student_id, Enrollment.offering_id).filter(
        Enrollment.student_id.in_(student_ids)
    )
    if course_id_filter is not None:
        offering_query = offering_query.join(
            CourseOffering, CourseOffering.id == Enrollment.offering_id
        ).filter(CourseOffering.course_id.in_(course_id_filter))
    enrollment_rows = offering_query.all()

    offering_ids_by_student: dict[str, set[int]] = {}
    all_offering_ids: set[int] = set()
    for student_id, offering_id in enrollment_rows:
        offering_ids_by_student.setdefault(student_id, set()).add(offering_id)
        all_offering_ids.add(offering_id)

    if not all_offering_ids:
        return result

    items = db.query(AssessmentItem).filter(AssessmentItem.offering_id.in_(all_offering_ids)).all()
    item_by_id: dict[int, AssessmentItem] = {item.id: item for item in items}
    if not item_by_id:
        return result

    item_clos = db.query(ItemCLO).filter(ItemCLO.item_id.in_(item_by_id.keys())).all()
    scores = (
        db.query(StudentScore)
        .filter(
            StudentScore.student_id.in_(student_ids),
            StudentScore.item_id.in_(item_by_id.keys()),
        )
        .all()
    )
    score_by_student_item: dict[tuple[str, int], Decimal] = {
        (s.student_id, s.item_id): s.score_obtained for s in scores
    }

    for student_id in student_ids:
        enrolled_offering_ids = offering_ids_by_student.get(student_id)
        if not enrolled_offering_ids:
            continue
        clo_weighted_sum: dict[int, Decimal] = {}
        clo_weight_total: dict[int, Decimal] = {}
        for ic in item_clos:
            item = item_by_id.get(ic.item_id)
            if item is None or item.offering_id not in enrolled_offering_ids:
                continue
            score = score_by_student_item.get((student_id, ic.item_id))
            if score is None or item.total_score <= 0:
                continue
            item_percent = (score / item.total_score) * Decimal(100)
            clo_weighted_sum[ic.clo_id] = clo_weighted_sum.get(ic.clo_id, Decimal(0)) + item_percent * ic.weight_percent
            clo_weight_total[ic.clo_id] = clo_weight_total.get(ic.clo_id, Decimal(0)) + ic.weight_percent
        result[student_id] = {
            clo_id: clo_weighted_sum[clo_id] / clo_weight_total[clo_id]
            for clo_id in clo_weighted_sum
            if clo_weight_total[clo_id] > 0
        }
    return result


def _calculate_plo_achievement_from_mastery(
    student: Student,
    plos: list[PLO],
    clo_mastery: dict[int, Decimal],
    plo_requirements: dict[int, dict[int, set[int]]],
    clo_pass_thresholds: dict[int, Decimal],
) -> StudentPLOAchievement:
    """
    ทำอะไร : รวม CLO mastery ของนักศึกษา 1 คนขึ้นเป็นผลบรรลุ PLO ทุกข้อ (คำนวณล้วน ๆ ไม่แตะฐานข้อมูล)
             ใช้ plo_requirements/clo_pass_thresholds ที่คำนวณไว้แล้วระดับหลักสูตร (เหมือนกันทุก
             นักศึกษา) ร่วมกับ clo_mastery ของนักศึกษาคนนั้นที่ดึงมาก่อนหน้าแล้ว

    เชื่อมกับ : เรียก _student_achieved_plo ทีละ PLO — ถูกเรียกโดย get_cohort_plo_achievement และ
                get_plo_achievement_by_year เพื่อให้ดึงรายชื่อ PLO และคำนวณ mastery ของทั้ง roster
                ได้ครั้งเดียว แทนที่จะ query ซ้ำทุกครั้งต่อนักศึกษา 1 คน (รุ่นที่มีนักศึกษาจริงราว 200
                คน เคยทำให้ backend ตอบช้าจนเกิน timeout ของ frontend แม้จะคำนวณเสร็จถูกต้องในที่สุด
                ก็ตาม)

    ถ้าแก้ : ถ้าเปลี่ยนให้ query ข้อมูลเพิ่มในฟังก์ชันนี้ จะเสียจุดประสงค์ของการ batch ไป
    """
    achievements = []
    for plo in plos:
        achieved = _student_achieved_plo(
            plo_requirements.get(plo.id), clo_mastery, clo_pass_thresholds
        )
        achievements.append(
            PLOAchievementItem(
                plo_id=plo.id,
                plo_code=plo.code,
                description=plo.description_th,
                achieved_percent=100.0 if achieved else 0.0,
                is_achieved=achieved,
            )
        )

    return StudentPLOAchievement(
        student_id=student.id,
        student_name=f"{student.first_name} {student.last_name}",
        curriculum_id=student.curriculum_id,
        plo_achievements=achievements,
    )


def _calculate_plo_achievement_for_student(
    db: Session,
    student: Student,
    plo_requirements: dict[int, dict[int, set[int]]],
    clo_pass_thresholds: dict[int, Decimal],
    course_id_filter: set[int] | None = None,
) -> StudentPLOAchievement:
    """
    ทำอะไร : เวอร์ชันรายบุคคล — ดึงรายชื่อ PLO และ CLO mastery ของนักศึกษาคนนี้เอง แล้วคำนวณผลบรรลุ

    เชื่อมกับ : เรียกโดย GET /plo/achievement (endpoint รายบุคคลเท่านั้น) — endpoint ระดับ cohort/
                by-year ใช้ _calculate_plo_achievement_from_mastery แบบ batch แทน เพื่อไม่ต้อง query
                รายชื่อ PLO และ mastery ซ้ำทุกคนในรุ่น

    ถ้าแก้ : ปลอดภัยที่จะ query ต่อครั้งที่นี่ เพราะมีผู้เรียกเดียวคือ endpoint รายบุคคล (1 คนต่อ 1
             request) ไม่ใช่จุดที่ทำให้เกิด N+1 query เหมือน endpoint ระดับ cohort
    """
    plos = (
        db.query(PLO)
        .filter(PLO.curriculum_id == student.curriculum_id)
        .order_by(PLO.code)
        .all()
    )
    clo_mastery = _clo_mastery_for_student(db, student.id, course_id_filter)
    return _calculate_plo_achievement_from_mastery(
        student, plos, clo_mastery, plo_requirements, clo_pass_thresholds
    )


def _aggregate_plo_percent_stats(
    student_achievements: list[StudentPLOAchievement],
) -> tuple[dict[int, Decimal], dict[int, int], dict[int, int]]:
    """
    ทำอะไร : รวมยอด achieved_percent และนับจำนวนนักศึกษาที่มีข้อมูล / ที่บรรลุ แยกตาม PLO แต่ละข้อ
             (ใช้คิดค่าเฉลี่ยและอัตราการบรรลุของทั้งรุ่น)

    เชื่อมกับ : ใช้ร่วมกันโดย GET /achievement/cohort และ GET /achievement/by-year เพื่อให้ตรรกะ
                หาค่าเฉลี่ยระดับรุ่น (cohort-level averaging) อยู่ที่เดียวไม่ซ้ำโค้ด

    ถ้าแก้ : ถ้าแก้เงื่อนไขการนับตรงนี้ จะกระทบทั้ง average_achieved_percent และ
             achieved_rate_percent ที่แสดงในหน้าภาพรวม PLO และ YLO ตามชั้นปีพร้อมกัน
    """
    percent_sum_by_plo: dict[int, Decimal] = {}
    # achieved_percent is now always 100.0 or 0.0 (see module docstring), so
    # count_with_data_by_plo below is really just achieved_count_by_plo again -
    # kept as-is since nothing in the frontend reads student_count_with_data
    # (the field it feeds) and this function isn't the place to drop it.
    count_with_data_by_plo: dict[int, int] = {}
    achieved_count_by_plo: dict[int, int] = {}

    for achievement in student_achievements:
        for item in achievement.plo_achievements:
            percent_sum_by_plo[item.plo_id] = (
                percent_sum_by_plo.get(item.plo_id, Decimal(0)) + Decimal(str(item.achieved_percent))
            )
            if item.achieved_percent > 0:
                count_with_data_by_plo[item.plo_id] = count_with_data_by_plo.get(item.plo_id, 0) + 1
            if item.is_achieved:
                achieved_count_by_plo[item.plo_id] = achieved_count_by_plo.get(item.plo_id, 0) + 1

    return percent_sum_by_plo, count_with_data_by_plo, achieved_count_by_plo


def _count_all_qualifying_plo_achieved(
    student_achievements: list[StudentPLOAchievement], qualifying_plo_ids: set[int]
) -> int:
    """
    ทำอะไร : นับจำนวนนักศึกษาที่บรรลุ PLO ครบทุกข้อใน qualifying_plo_ids (ไม่ใช่ครบทุก PLO ในหลักสูตร
             เสมอไป — ดู _qualifying_plo_ids) PLO ที่ไม่มีวิชา "หลัก" ผ่านเกณฑ์เลยไม่ถูกนับ เพราะเป็น
             ไปไม่ได้อยู่แล้วโดยดีไซน์ ไม่ควรทำให้ไม่มีใครนับว่า "บรรลุครบ" เลยสักคน

    เชื่อมกับ : ใช้คำนวณ all_plo_achieved_count ใน get_cohort_plo_achievement (สถิติวงแหวนหน้า
                "ภาพรวม PLO")

    ถ้าแก้ : 0 qualifying PLO = ไม่มีใครบรรลุครบได้ (edge case ที่ไม่ควรเกิดในทางปฏิบัติ แต่คืน 0
             อย่างปลอดภัยแทนการหารด้วยศูนย์/พังตอนไม่มี PLO เข้าเกณฑ์เลย)
    """
    if not qualifying_plo_ids:
        return 0
    count = 0
    for achievement in student_achievements:
        if all(
            item.is_achieved
            for item in achievement.plo_achievements
            if item.plo_id in qualifying_plo_ids
        ):
            count += 1
    return count


@router.get("/achievement", response_model=StudentPLOAchievement)
def get_plo_achievement(
    student_id: str = Query(..., description="Student ID, e.g. 6500001"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    ทำอะไร : endpoint คืนผลบรรลุ PLO ทุกข้อของนักศึกษา 1 คน (ตาม curriculum_id ของนักศึกษาคนนั้นเอง)

    เชื่อมกับ : เรียก _build_plo_requirements + _calculate_plo_achievement_for_student — ใช้โดยหน้า
                ผลบรรลุรายบุคคล (student-plo / PLOAchievement.jsx) เพื่อแสดง chip grid ผลบรรลุ PLO
                ของนักศึกษาคนที่ล็อกอินอยู่ หรือที่อาจารย์/แอดมินเลือกดู

    ถ้าแก้ : เป็น endpoint เดียวที่คืนผลบรรลุ PLO "รายบุคคล" ทั้งระบบ — 404 ถ้าไม่พบ student_id
    """
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")

    plo_requirements, clo_pass_thresholds = _build_plo_requirements(db, student.curriculum_id)
    return _calculate_plo_achievement_for_student(db, student, plo_requirements, clo_pass_thresholds)


@router.get(
    "/{plo_id}/students/{student_id}/course-breakdown",
    response_model=list[StudentPLOCourseBreakdownItem],
)
def get_student_plo_course_breakdown(
    plo_id: int,
    student_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    ทำอะไร : คืนวิชาทั้งหมดที่มี CLO ผูกกับ PLO ข้อนี้โดยตรง (จาก clo_plo_mapping) พร้อมสถานะผ่าน/
             ไม่ผ่านของนักศึกษาคนนี้โดยเฉพาะต่อวิชา

    เชื่อมกับ : เรียก _build_plo_requirements และ _student_passed_course_for_plo ตัวเดียวกับที่ตัดสิน
                "% บรรลุ PLO" ทุกที่ในไฟล์นี้ ไม่มี logic คำนวณแยกที่อาจ drift ไม่ตรงกัน — ใช้ในหน้า
                ภาพรวม PLO ตอนขยายดูรายชื่อนักศึกษาต่อ PLO (PLOStudentBreakdown.jsx)

    ถ้าแก้ : 404 ถ้าไม่พบ PLO หรือนักศึกษา — คืน [] ถ้า PLO นั้นไม่มี CLO ผูกอยู่เลย (ไม่ error)
    """
    plo = db.get(PLO, plo_id)
    if plo is None:
        raise HTTPException(status_code=404, detail="PLO not found")
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")

    plo_requirements, clo_pass_thresholds = _build_plo_requirements(db, student.curriculum_id)
    courses_for_plo = plo_requirements.get(plo_id)
    if not courses_for_plo:
        return []

    clo_mastery = _clo_mastery_for_student(db, student.id)

    courses = db.query(Course).filter(Course.id.in_(courses_for_plo.keys())).all()
    course_by_id = {c.id: c for c in courses}

    breakdown = []
    for course_id, clo_ids in courses_for_plo.items():
        course = course_by_id.get(course_id)
        if course is None:
            continue
        breakdown.append(
            StudentPLOCourseBreakdownItem(
                course_id=course_id,
                course_code=course.course_code,
                name_th=course.name_th,
                passed=_student_passed_course_for_plo(clo_ids, clo_mastery, clo_pass_thresholds),
            )
        )
    breakdown.sort(key=lambda c: c.course_code)
    return breakdown


@router.get("/achievement/cohort", response_model=CurriculumPLOAchievement)
def get_cohort_plo_achievement(
    curriculum_id: int = Query(..., description="Curriculum ID"),
    cohort_year: int | None = Query(None, description="กรองเฉพาะรุ่นที่เข้าเรียนปีนี้ (เช่น 66) - ไม่ใส่ = รวมทุกรุ่น"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    ทำอะไร : endpoint หลักของหน้า "ภาพรวม PLO" — คืนสรุปผลบรรลุ PLO ทุกข้อของทั้งหลักสูตร (ค่าเฉลี่ย,
             อัตราบรรลุ) พร้อมรายชื่อนักศึกษาทุกคนและผลบรรลุ PLO รายข้อของแต่ละคน กรองตามรุ่น
             (cohort_year) ได้ ถ้าไม่ใส่จะรวมทุกรุ่น

    เชื่อมกับ : ใช้ _build_plo_requirements + _qualifying_plo_ids (คำนวณครั้งเดียวต่อ request) แล้ว
                ดึง CLO mastery ของนักศึกษาทั้ง roster แบบ batch ผ่าน _clo_mastery_for_students_batch
                ก่อนวนคำนวณผลบรรลุทีละคนด้วย _calculate_plo_achievement_from_mastery — เรียกโดยหน้า
                "ภาพรวม PLO" (PLODetailPage.jsx)

    ถ้าแก้ : ห้ามเปลี่ยนกลับไปคำนวณ mastery ทีละคนในลูป (ดูคอมเมนต์ด้านล่างเรื่อง N+1 query) —
             404 ถ้าไม่พบ curriculum_id
    """
    curriculum = db.get(Curriculum, curriculum_id)
    if curriculum is None:
        raise HTTPException(status_code=404, detail="Curriculum not found")

    plos = (
        db.query(PLO)
        .filter(PLO.curriculum_id == curriculum_id)
        .order_by(PLO.code)
        .all()
    )

    plo_requirements, clo_pass_thresholds = _build_plo_requirements(db, curriculum_id)
    qualifying_plo_ids = _qualifying_plo_ids(plo_requirements)

    available_cohort_years = sorted(
        {
            row[0]
            for row in db.query(Student.cohort_year)
            .filter(Student.curriculum_id == curriculum_id, Student.cohort_year.isnot(None))
            .distinct()
            .all()
        }
    )

    students_query = db.query(Student).filter(Student.curriculum_id == curriculum_id)
    if cohort_year is not None:
        students_query = students_query.filter(Student.cohort_year == cohort_year)
    students = students_query.all()

    if not students:
        return CurriculumPLOAchievement(
            curriculum_id=curriculum.id,
            curriculum_name=curriculum.name,
            total_students=0,
            plo_summary=[
                PLOCohortSummaryItem(
                    plo_id=plo.id,
                    plo_code=plo.code,
                    description=plo.description_th,
                    student_count_with_data=0,
                    average_achieved_percent=0.0,
                    achieved_student_count=0,
                    achieved_rate_percent=0.0,
                )
                for plo in plos
            ],
            students=[],
            available_cohort_years=available_cohort_years,
            qualifying_plo_count=len(qualifying_plo_ids),
            total_plo_count=len(plos),
        )

    # Batched: one round of queries for every student's CLO mastery instead
    # of one round PER student - a ~200-student roster otherwise means
    # thousands of individual DB round-trips (fine on a local Postgres, slow
    # enough over the network to a hosted DB that the frontend's request
    # timeout fires before the response comes back, even though it eventually
    # would have finished correctly).
    student_ids = [student.id for student in students]
    clo_mastery_by_student = _clo_mastery_for_students_batch(db, student_ids)
    student_achievements = [
        _calculate_plo_achievement_from_mastery(
            student, plos, clo_mastery_by_student.get(student.id, {}), plo_requirements, clo_pass_thresholds
        )
        for student in students
    ]
    # เรียงตามรหัสนักศึกษาจากน้อยไปมาก ไม่ใช่ตามชื่อ (string sort ตรงๆ ไม่ int() - ดูเหตุผลเดียวกับ
    # ylo_calculation.py คือรหัสจริงยาวคงที่อยู่แล้ว แต่รหัสทดสอบในระบบนี้ไม่ใช่ตัวเลขล้วนเสมอไป)
    students_sorted = sorted(student_achievements, key=lambda sa: sa.student_id)

    total_students = len(students)
    percent_sum_by_plo, count_with_data_by_plo, achieved_count_by_plo = _aggregate_plo_percent_stats(
        student_achievements
    )

    plo_summary = []
    for plo in plos:
        percent_sum = percent_sum_by_plo.get(plo.id, Decimal(0))
        achieved_count = achieved_count_by_plo.get(plo.id, 0)

        average_achieved_percent = (percent_sum / Decimal(total_students)).quantize(Decimal("0.1"))
        achieved_rate_percent = (
            Decimal(achieved_count) / Decimal(total_students) * Decimal(100)
        ).quantize(Decimal("0.1"))

        plo_summary.append(
            PLOCohortSummaryItem(
                plo_id=plo.id,
                plo_code=plo.code,
                description=plo.description_th,
                student_count_with_data=count_with_data_by_plo.get(plo.id, 0),
                average_achieved_percent=float(average_achieved_percent),
                achieved_student_count=achieved_count,
                achieved_rate_percent=float(achieved_rate_percent),
            )
        )

    all_plo_achieved_count = _count_all_qualifying_plo_achieved(student_achievements, qualifying_plo_ids)
    all_plo_achieved_percent = (
        Decimal(all_plo_achieved_count) / Decimal(total_students) * Decimal(100)
    ).quantize(Decimal("0.1"))

    return CurriculumPLOAchievement(
        curriculum_id=curriculum.id,
        curriculum_name=curriculum.name,
        total_students=total_students,
        plo_summary=plo_summary,
        students=students_sorted,
        available_cohort_years=available_cohort_years,
        all_plo_achieved_count=all_plo_achieved_count,
        all_plo_achieved_percent=float(all_plo_achieved_percent),
        qualifying_plo_count=len(qualifying_plo_ids),
        total_plo_count=len(plos),
    )


@router.get("/achievement/by-year", response_model=CurriculumYearProgress)
def get_plo_achievement_by_year(
    curriculum_id: int = Query(..., description="Curriculum ID"),
    cohort_year: int | None = Query(None, description="กรองเฉพาะรุ่นที่เข้าเรียนปีนี้ (เช่น 66) - ไม่ใส่ = รวมทุกรุ่น"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    ทำอะไร : คำนวณผลบรรลุ PLO แบบ all-or-nothing เหมือน /achievement/cohort ทุกประการ แต่รันแยกทีละ
             ชั้นปี (1-4) โดยนับเฉพาะคะแนนวิชาที่อยู่ใน study_plan ของปีนั้น — แต่ละปีจึงสะท้อนสิ่งที่
             สอนในปีนั้นจริง ๆ ไม่ใช่ยอดสะสมทั้งหมด พร้อมทั้งบอกด้วยว่า PLO ข้อไหนที่ YLO ของปีนั้น
             คาดหวังไว้ (is_expected_this_year)

    เชื่อมกับ : ใช้ _build_plo_requirements + _clo_mastery_for_students_batch (scope ด้วย
                course_id_filter ต่อปี) — เรียกโดยหน้า "YLO ตามชั้นปี" เพื่อดึง course_count ต่อปี
                (ตัวเลข achievement ของ endpoint นี้เองยังไม่ถูกแสดงผลที่ไหนใน UI ปัจจุบัน)

    ถ้าแก้ : ข้อควรระวัง — วิชาที่ "บังคับ" สำหรับ PLO หนึ่ง (plo_requirements) ยังเป็นชุดข้อมูล
             curriculum-global ไม่ได้ scope ตามปี ดังนั้น PLO ที่มีวิชาบังคับกระจายหลายปี จะขึ้นเป็น
             "ยังไม่บรรลุ" ในทุกปีย่อย เว้นแต่วิชาบังคับทั้งหมดของ PLO นั้นบังเอิญอยู่ในปีเดียวกัน — เป็น
             quirk ที่รู้แล้วและตั้งใจไม่แก้เพิ่มความซับซ้อน เพราะตัวเลขบรรลุของ endpoint นี้ยังไม่ถูก
             render ที่ไหนใน UI
    """
    curriculum = db.get(Curriculum, curriculum_id)
    if curriculum is None:
        raise HTTPException(status_code=404, detail="Curriculum not found")

    plos = db.query(PLO).filter(PLO.curriculum_id == curriculum_id).order_by(PLO.code).all()

    plo_requirements, clo_pass_thresholds = _build_plo_requirements(db, curriculum_id)

    available_cohort_years = sorted(
        {
            row[0]
            for row in db.query(Student.cohort_year)
            .filter(Student.curriculum_id == curriculum_id, Student.cohort_year.isnot(None))
            .distinct()
            .all()
        }
    )

    students_query = db.query(Student).filter(Student.curriculum_id == curriculum_id)
    if cohort_year is not None:
        students_query = students_query.filter(Student.cohort_year == cohort_year)
    students = students_query.all()
    total_students = len(students)
    student_ids = [student.id for student in students]

    ylo_by_year = {
        ylo.year_level: ylo
        for ylo in db.query(YLO).filter(YLO.curriculum_id == curriculum_id).all()
    }

    years: list[YearProgressItem] = []
    for year_level in (1, 2, 3, 4):
        ylo = ylo_by_year.get(year_level)
        ylo_description = ylo.description if ylo is not None else ""

        expected_plo_ids: set[int] = set()
        if ylo is not None:
            expected_plo_ids = {
                row[0]
                for row in db.query(YLOPLOMapping.plo_id)
                .filter(YLOPLOMapping.ylo_id == ylo.id)
                .all()
            }

        course_ids = {
            row[0]
            for row in db.query(StudyPlan.course_id)
            .filter(
                StudyPlan.curriculum_id == curriculum_id,
                StudyPlan.year_level == year_level,
                StudyPlan.cohort_year.is_(None),
            )
            .all()
        }

        if total_students == 0:
            years.append(
                YearProgressItem(
                    year_level=year_level,
                    ylo_description=ylo_description,
                    course_count=len(course_ids),
                    plo_summary=[
                        YearlyPLOSummaryItem(
                            plo_id=plo.id,
                            plo_code=plo.code,
                            description=plo.description_th,
                            is_expected_this_year=plo.id in expected_plo_ids,
                            student_count_with_data=0,
                            average_achieved_percent=0.0,
                            achieved_student_count=0,
                            achieved_rate_percent=0.0,
                        )
                        for plo in plos
                    ],
                    students=[],
                )
            )
            continue

        # Batched per year, same reasoning as /achievement/cohort above - one
        # round of mastery queries for the whole roster instead of one round
        # per student, times 4 years.
        clo_mastery_by_student = _clo_mastery_for_students_batch(
            db, student_ids, course_id_filter=course_ids
        )
        student_achievements = [
            _calculate_plo_achievement_from_mastery(
                student, plos, clo_mastery_by_student.get(student.id, {}), plo_requirements, clo_pass_thresholds
            )
            for student in students
        ]
        # เรียงตามรหัสนักศึกษาจากน้อยไปมาก ไม่ใช่ตามชื่อ (เดียวกับ /achievement/cohort ด้านบน) แม้
        # field students ของ endpoint นี้จะยังไม่ถูก render ที่ไหนใน UI ตอนนี้ก็ตาม
        students_sorted = sorted(student_achievements, key=lambda sa: sa.student_id)

        percent_sum_by_plo, count_with_data_by_plo, achieved_count_by_plo = _aggregate_plo_percent_stats(
            student_achievements
        )

        plo_summary = []
        for plo in plos:
            percent_sum = percent_sum_by_plo.get(plo.id, Decimal(0))
            achieved_count = achieved_count_by_plo.get(plo.id, 0)

            average_achieved_percent = (percent_sum / Decimal(total_students)).quantize(Decimal("0.1"))
            achieved_rate_percent = (
                Decimal(achieved_count) / Decimal(total_students) * Decimal(100)
            ).quantize(Decimal("0.1"))

            plo_summary.append(
                YearlyPLOSummaryItem(
                    plo_id=plo.id,
                    plo_code=plo.code,
                    description=plo.description_th,
                    is_expected_this_year=plo.id in expected_plo_ids,
                    student_count_with_data=count_with_data_by_plo.get(plo.id, 0),
                    average_achieved_percent=float(average_achieved_percent),
                    achieved_student_count=achieved_count,
                    achieved_rate_percent=float(achieved_rate_percent),
                )
            )

        years.append(
            YearProgressItem(
                year_level=year_level,
                ylo_description=ylo_description,
                course_count=len(course_ids),
                plo_summary=plo_summary,
                students=students_sorted,
            )
        )

    return CurriculumYearProgress(
        curriculum_id=curriculum.id,
        curriculum_name=curriculum.name,
        years=years,
        available_cohort_years=available_cohort_years,
    )
