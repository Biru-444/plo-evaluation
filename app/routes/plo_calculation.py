"""
ทำอะไร : เส้นทาง API สำหรับคำนวณ "% บรรลุ PLO" ของนักศึกษา — ทั้งแบบรายบุคคล, รายรุ่น (cohort), แบบ
         export Excel ของรายรุ่น, และแบบแยกตามชั้นปี (by-year) ถือเป็นไฟล์แกนกลางที่สุดของระบบ เพราะ
         ทุกหน้าที่แสดงผลบรรลุ PLO (ภาพรวม PLO, ผลบรรลุรายบุคคล, YLO ตามชั้นปี) ดึงตัวเลขมาจากที่นี่
         ทั้งหมด

สูตรคำนวณจริงทั้งหมด (mastery/PLO_x/threshold) ย้ายไปอยู่ที่ app/services/plo_achievement_service.py
แล้ว (ไม่มีการแก้สูตร - ย้ายตรงๆ) ไฟล์นี้เหลือแค่ endpoint + schema เฉพาะที่ไม่มีใครใช้ร่วมนอกจากที่นี่
(YearlyPLOSummaryItem/YearProgressItem/CurriculumYearProgress/StudentPLOCourseBreakdownItem) - schema
ที่ใช้ร่วมกับ export (PLOAchievementItem/StudentPLOAchievement/PLOCohortSummaryItem/
CurriculumPLOAchievement) ย้ายไป app/schemas/plo_calculation.py แล้วเช่นกัน

ตัวหารสถิติระดับรุ่น (TASK-plo-denominator, 2026-09) : average_achieved_percent/achieved_rate_percent
ของทั้ง /achievement/cohort และ /achievement/by-year หารด้วย**นักศึกษาที่มีข้อมูลของ PLO นั้น**
(has_data=True ใน PLOAchievementItem) ไม่ใช่นักศึกษาทั้งหมดอีกต่อไป - เป็น None เมื่อไม่มีใครมีข้อมูลเลย
(หารไม่ได้ ไม่ใช่ 0%) coverage_percent (ใหม่) คือสัดส่วนคนมีข้อมูลจากทั้งหมด ต้องแสดงคู่กันเสมอฝั่ง
frontend สูตร/เกณฑ์รายบุคคล (PLO_x, 60%) ไม่เปลี่ยน - รายละเอียดเต็มอยู่ที่ module docstring ของ
plo_achievement_service.py

เชื่อมกับ : - GET /plo/achievement ถูกเรียกจากหน้าผลบรรลุรายบุคคล (student-plo / PLOAchievement.jsx)
            - GET /plo/achievement/cohort ถูกเรียกจากหน้า "ภาพรวม PLO ทั้งหลักสูตร" (PLODashboard.jsx,
              route /dashboard) — เรียก compute_cohort_plo_achievement() ตรงๆ ไม่มีตรรกะคำนวณเองอีก
              ต่อไป
            - GET /plo/achievement/export คืนไฟล์ Excel จาก compute_cohort_plo_achievement() ตัวเดียว
              กับ endpoint ด้านบน (ดู app/services/plo_report_export_service.py) ตัวเลขจึงตรงกันเป๊ะ
              เสมอ
            - GET /plo/achievement/by-year ถูกเรียกจากหน้า "YLO ตามชั้นปี" (สำหรับ course_count
              ต่อปี — ตัวเลข achievement ของ endpoint นี้เองยังไม่ถูกแสดงผลที่ไหนใน UI ปัจจุบัน)
            - app/routes/courses.py และ app/routes/ylo_calculation.py ยัง import ฟังก์ชันคำนวณ
              (_build_plo_requirements, _clo_mastery_for_students_batch, _student_passed_course_for_plo,
              _clo_passed) จาก `app.routes.plo_calculation` เหมือนเดิม (ไฟล์นี้ import ชื่อเหล่านั้นมา
              จาก plo_achievement_service.py แล้ว re-export ต่อผ่าน module namespace ของตัวเอง - ไม่ต้อง
              แก้ import ใน 2 ไฟล์นั้น)

ถ้าแก้ : ลำดับการลงทะเบียน router ของไฟล์นี้ใน app/main.py มีผลต่อการทำงาน (ดูคอมเมนต์ใน main.py) ห้าม
         สลับลำดับ (path /{plo_id}/students/{student_id}/course-breakdown เป็น path parameter ต้อง
         ลงทะเบียนหลัง literal path ของ router อื่นที่อาจชนกัน)
"""
from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import require_role
from app.database import get_db
from app.models import Course, Curriculum, PLO, Student, StudyPlan, User, YLO, YLOPLOMapping
from app.schemas.plo_calculation import (
    CurriculumPLOAchievement,
    StudentPLOAchievement,
)
from app.services.plo_achievement_service import (
    _build_plo_requirements,
    _calculate_plo_achievement_for_student,
    _calculate_plo_achievement_from_mastery,
    _clo_mastery_for_student,
    _clo_mastery_for_students_batch,
    _clo_passed,
    _compute_plo_rate_stats,
    _student_passed_course_for_plo,
    _aggregate_plo_percent_stats,
    compute_cohort_plo_achievement,
)
from app.services.plo_report_export_service import build_plo_report_excel

router = APIRouter(prefix="/plo", tags=["PLO Achievement"])


# เหมือน PLOCohortSummaryItem (app/schemas/plo_calculation.py) แต่เพิ่ม is_expected_this_year (PLO นี้
# ถูกคาดหวังในชั้นปีนี้หรือไม่ตาม ylo_plo_mapping) — ใช้ในสรุปผลบรรลุ PLO แยกตามชั้นปีเท่านั้น ไม่มีใคร
# ใช้ร่วมนอกไฟล์นี้ จึงไม่ได้ย้ายไป schemas/plo_calculation.py ด้วย - average/rate เป็น float | None และ
# มี coverage_percent เหมือน PLOCohortSummaryItem (TASK-plo-denominator - หารด้วยนักศึกษาที่มีข้อมูล
# ไม่ใช่ทั้งหมด ดู plo_achievement_service.py module docstring)
class YearlyPLOSummaryItem(BaseModel):
    plo_id: int
    plo_code: str
    description: str
    is_expected_this_year: bool
    student_count_with_data: int
    average_achieved_percent: float | None
    achieved_student_count: int
    achieved_rate_percent: float | None
    coverage_percent: float = 0.0


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


@router.get("/achievement", response_model=StudentPLOAchievement)
def get_plo_achievement(
    student_id: str = Query(..., description="Student ID, e.g. 6500001"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "instructor")),
):
    """
    ทำอะไร : endpoint คืนผลบรรลุ PLO ทุกข้อของนักศึกษา 1 คน (ตาม curriculum_id ของนักศึกษาคนนั้นเอง)

    เชื่อมกับ : เรียก _build_plo_requirements + _calculate_plo_achievement_for_student — ใช้โดยหน้า
                ผลบรรลุรายบุคคล (student-plo / PLOAchievement.jsx) เพื่อแสดง chip grid ผลบรรลุ PLO
                ของนักศึกษาคนที่ล็อกอินอยู่ หรือที่อาจารย์/แอดมินเลือกดู

    ถ้าแก้ : เป็น endpoint เดียวที่คืนผลบรรลุ PLO "รายบุคคล" ทั้งระบบ — 404 ถ้าไม่พบ student_id

             สิทธิ์ (curriculum-level - ตั้งใจเปิดกว้าง) : admin หรืออาจารย์คนไหนก็ได้ (ไม่ต้องเป็น
             อาจารย์ของนักศึกษาคนนั้นโดยตรง) - ผลบรรลุ PLO เป็นข้อมูลระดับหลักสูตรที่บุคลากรทุกคนของ
             หลักสูตรควรเห็นภาพรวมได้ ต่างจากคะแนนดิบรายวิชา (ดู GET /clo-achievement/* ที่จำกัดแค่
             อาจารย์เจ้าของ offering เท่านั้น)
    """
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")

    plo_clo_weights, _plo_course_clo_ids, _clo_pass_thresholds = _build_plo_requirements(
        db, student.curriculum_id
    )
    return _calculate_plo_achievement_for_student(db, student, plo_clo_weights)


@router.get(
    "/{plo_id}/students/{student_id}/course-breakdown",
    response_model=list[StudentPLOCourseBreakdownItem],
)
def get_student_plo_course_breakdown(
    plo_id: int,
    student_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "instructor")),
):
    """
    ทำอะไร : คืนวิชาทั้งหมดที่มี CLO ผูกกับ PLO ข้อนี้โดยตรง (จาก clo_plo_mapping) พร้อมสถานะผ่าน/
             ไม่ผ่านของนักศึกษาคนนี้โดยเฉพาะต่อวิชา

    เชื่อมกับ : เรียก _build_plo_requirements และ _student_passed_course_for_plo ตัวเดียวกับที่ตัดสิน
                "% บรรลุ PLO" ทุกที่ในระบบ ไม่มี logic คำนวณแยกที่อาจ drift ไม่ตรงกัน — ใช้ในหน้า
                ภาพรวม PLO ตอนขยายดูรายชื่อนักศึกษาต่อ PLO (PLOStudentBreakdown.jsx)

    ถ้าแก้ : 404 ถ้าไม่พบ PLO หรือนักศึกษา — คืน [] ถ้า PLO นั้นไม่มี CLO ผูกอยู่เลย (ไม่ error)

             สิทธิ์ (curriculum-level - ตั้งใจเปิดกว้าง) : admin หรืออาจารย์คนไหนก็ได้ เหมือน
             GET /plo/achievement (ดูเหตุผลที่นั่น) - แม้จะคืนสถานะผ่าน/ไม่ผ่านต่อ "วิชา" แต่เป็นแค่
             true/false รวม ไม่ใช่คะแนนดิบรายชิ้นงาน (นั่นคือ GET /clo-achievement/student-course ที่
             จำกัดแค่อาจารย์เจ้าของ offering)
    """
    plo = db.get(PLO, plo_id)
    if plo is None:
        raise HTTPException(status_code=404, detail="PLO not found")
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")

    _plo_clo_weights, plo_course_clo_ids, clo_pass_thresholds = _build_plo_requirements(
        db, student.curriculum_id
    )
    courses_for_plo = plo_course_clo_ids.get(plo_id)
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
    current_user: User = Depends(require_role("admin", "instructor")),
):
    """
    ทำอะไร : endpoint หลักของหน้า "ภาพรวม PLO" — คืนสรุปผลบรรลุ PLO ทุกข้อของทั้งหลักสูตร (ค่าเฉลี่ย,
             อัตราบรรลุ) พร้อมรายชื่อนักศึกษาทุกคนและผลบรรลุ PLO รายข้อของแต่ละคน กรองตามรุ่น
             (cohort_year) ได้ ถ้าไม่ใส่จะรวมทุกรุ่น

    เชื่อมกับ : เป็น wrapper บาง ๆ รอบ compute_cohort_plo_achievement() (plo_achievement_service.py) -
                ไม่มีตรรกะคำนวณเองในไฟล์นี้อีกต่อไป GET /plo/achievement/export
                (export_plo_report_excel ด้านล่าง) เรียกฟังก์ชันเดียวกันนี้ เพื่อให้ตัวเลขตรงกันเป๊ะ

    ถ้าแก้ : 404 ถ้าไม่พบ curriculum_id

             สิทธิ์ (curriculum-level - ตั้งใจเปิดกว้าง) : admin หรืออาจารย์คนไหนก็ได้ เหมือน
             GET /plo/achievement (ดูเหตุผลที่นั่น)
    """
    result = compute_cohort_plo_achievement(db, curriculum_id, cohort_year)
    if result is None:
        raise HTTPException(status_code=404, detail="Curriculum not found")
    return result


@router.get("/achievement/export")
def export_plo_report_excel(
    curriculum_id: int = Query(..., description="Curriculum ID"),
    cohort_year: int | None = Query(None, description="กรองเฉพาะรุ่นที่เข้าเรียนปีนี้ (เช่น 66) - ไม่ใส่ = รวมทุกรุ่น (จะมีชีตเปรียบเทียบรายรุ่นเพิ่ม)"),
    target_rate: float = Query(70.0, description="เกณฑ์บรรลุระดับหลักสูตร (%) - PLO บรรลุเมื่อร้อยละนักศึกษาที่บรรลุ >= ค่านี้"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "instructor")),
):
    """
    ทำอะไร : export รายงานภาพรวม PLO ↔ รายวิชาของหลักสูตรเดียวเป็นไฟล์ Excel - ตอบ 3 คำถามหลักของ
             AUN-QA ในไฟล์เดียว: หลักสูตรออกแบบให้ PLO ถูกสอน/วัดที่ไหน (แผนที่หลักสูตร), นักศึกษาบรรลุ
             PLO กี่เปอร์เซ็นต์ (สรุปการบรรลุ), ตัวเลขมาจาก CLO/วิชาไหนน้ำหนักเท่าไร (ย้อนรอยการคำนวณ)
             ไม่ยึดตามแบบฟอร์มราชการใดๆ (แนวทางเดียวกับ export รายงานผลบรรลุ CLO ระดับ offering - ดู
             clo_report_export_service.py)

    เชื่อมกับ : เรียก compute_cohort_plo_achievement() ตัวเดียวกับ GET /plo/achievement/cohort (ตัวเลข
                ในรายงานตรงกับหน้าเว็บเป๊ะเสมอ ไม่มีสูตรคำนวณซ้ำสองชุด) แล้วส่งต่อให้
                build_plo_report_excel() (plo_report_export_service.py) จัดรูปแบบ+วาดลง openpyxl

    ถ้าแก้ : สิทธิ์ (curriculum-level - ตั้งใจเปิดกว้าง) : admin หรืออาจารย์คนไหนก็ได้ ได้ทุกชีตรวมชีต
             รายบุคคลเหมือนกัน (แก้ 2026-09 ให้ตรงกับ GET /plo/achievement/cohort ที่เปิดกว้างแบบเดียวกัน
             อยู่แล้ว - เดิม instructor ไม่ได้ชีตรายบุคคล ไม่สอดคล้องกับ endpoint คู่กันที่ให้ดูรายชื่อ
             นักศึกษาทุกคนอยู่แล้วผ่าน JSON) - 404 ถ้าไม่พบ curriculum_id
    """
    result = compute_cohort_plo_achievement(db, curriculum_id, cohort_year)
    if result is None:
        raise HTTPException(status_code=404, detail="Curriculum not found")

    include_personal_sheet = current_user.role in ("admin", "instructor")
    workbook_bytes = build_plo_report_excel(
        db,
        result,
        curriculum_id=curriculum_id,
        cohort_year=cohort_year,
        target_rate=Decimal(str(target_rate)),
        include_personal_sheet=include_personal_sheet,
        exported_by=f"{current_user.first_name} {current_user.last_name}",
    )

    cohort_label = str(cohort_year) if cohort_year is not None else "all"
    from datetime import date

    filename = f"plo_report_{result.curriculum_name.replace(' ', '_')}_{cohort_label}_{date.today():%Y%m%d}.xlsx"
    return StreamingResponse(
        workbook_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/achievement/by-year", response_model=CurriculumYearProgress)
def get_plo_achievement_by_year(
    curriculum_id: int = Query(..., description="Curriculum ID"),
    cohort_year: int | None = Query(None, description="กรองเฉพาะรุ่นที่เข้าเรียนปีนี้ (เช่น 66) - ไม่ใส่ = รวมทุกรุ่น"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "instructor")),
):
    """
    ทำอะไร : คำนวณผลบรรลุ PLO ด้วยสูตรถ่วงน้ำหนักเดียวกับ /achievement/cohort ทุกประการ แต่รันแยกทีละ
             ชั้นปี (1-4) โดยนับเฉพาะคะแนนวิชาที่อยู่ใน study_plan ของปีนั้น — แต่ละปีจึงสะท้อนสิ่งที่
             สอนในปีนั้นจริง ๆ ไม่ใช่ยอดสะสมทั้งหมด พร้อมทั้งบอกด้วยว่า PLO ข้อไหนที่ YLO ของปีนั้น
             คาดหวังไว้ (is_expected_this_year)

             สิทธิ์ (curriculum-level - ตั้งใจเปิดกว้าง) : admin หรืออาจารย์คนไหนก็ได้ เหมือน
             GET /plo/achievement/cohort

    เชื่อมกับ : ใช้ _build_plo_requirements + _clo_mastery_for_students_batch (scope ด้วย
                course_id_filter ต่อปี) — เรียกโดยหน้า "YLO ตามชั้นปี" เพื่อดึง course_count ต่อปี
                (ตัวเลข achievement ของ endpoint นี้เองยังไม่ถูกแสดงผลที่ไหนใน UI ปัจจุบัน)

    ถ้าแก้ : ข้อควรระวัง — CLO ที่ผูกกับ PLO หนึ่ง (plo_clo_weights) ยังเป็นชุดข้อมูล curriculum-global
             ไม่ได้ scope ตามปี ดังนั้น PLO ที่มี CLO หลักฐานกระจายหลายปี คะแนนถ่วงน้ำหนักของปีย่อยแต่ละ
             ปีจะนับเฉพาะ mastery ของ CLO ที่มีคะแนนในปีนั้น (course_id_filter) เท่านั้น ไม่ใช่ภาพรวมทั้ง
             หลักสูตร — เป็น quirk ที่รู้แล้วและตั้งใจไม่แก้เพิ่มความซับซ้อน เพราะตัวเลขบรรลุของ endpoint
             นี้ยังไม่ถูก render ที่ไหนใน UI
    """
    curriculum = db.get(Curriculum, curriculum_id)
    if curriculum is None:
        raise HTTPException(status_code=404, detail="Curriculum not found")

    plos = db.query(PLO).filter(PLO.curriculum_id == curriculum_id).order_by(PLO.code).all()

    plo_clo_weights, _plo_course_clo_ids, _clo_pass_thresholds = _build_plo_requirements(
        db, curriculum_id
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
                            average_achieved_percent=None,
                            achieved_student_count=0,
                            achieved_rate_percent=None,
                            coverage_percent=0.0,
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
                student, plos, clo_mastery_by_student.get(student.id, {}), plo_clo_weights
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
            count_with_data = count_with_data_by_plo.get(plo.id, 0)

            average_achieved_percent, achieved_rate_percent, coverage_percent = _compute_plo_rate_stats(
                percent_sum, achieved_count, count_with_data, total_students
            )

            plo_summary.append(
                YearlyPLOSummaryItem(
                    plo_id=plo.id,
                    plo_code=plo.code,
                    description=plo.description_th,
                    is_expected_this_year=plo.id in expected_plo_ids,
                    student_count_with_data=count_with_data,
                    average_achieved_percent=average_achieved_percent,
                    achieved_student_count=achieved_count,
                    achieved_rate_percent=achieved_rate_percent,
                    coverage_percent=coverage_percent,
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
