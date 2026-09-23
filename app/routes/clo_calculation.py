"""
ทำอะไร : เส้นทาง API สำหรับคำนวณ "% ความเชี่ยวชาญ CLO" (mastery) ระดับ course_offering (1 กลุ่มเรียน
         ของ 1 วิชา) — ต่างจาก plo_calculation.py ที่คำนวณระดับนักศึกษา/หลักสูตรทั้งก้อน ไฟล์นี้ตอบคำถาม
         "ทั้งห้องนี้ ใครผ่าน CLO ไหนบ้าง" และ "นักศึกษาคนนี้ วิชานี้ ได้คะแนนแต่ละ CLO เท่าไหร่ จาก
         ชิ้นงานอะไรบ้าง" — CLO เป็นของวิชา (course) ส่วนคะแนนจริงผูกกับ offering ที่นักศึกษาลงทะเบียน
         รวมถึง export มคอ.5 (Excel) ของ offering เดียว - ใช้ตัวเลขชุดเดียวกับ GET /clo-achievement เป๊ะ

สูตรคำนวณ : ค่าเฉลี่ยถ่วงน้ำหนักแบบเดียวกับ "ขั้นตอนที่ 1" ใน
  plo_calculation.py._clo_mastery_for_student คือ
  sum(score/total_score*100 * item_clo.weight_percent) / sum(item_clo.weight_percent)
  นับเฉพาะ assessment item ที่นักศึกษามีคะแนนบันทึกไว้จริงเท่านั้น - ตัวสูตรจริงอยู่ใน
  app/services/clo_achievement_service.py แล้ว (refactor ออกมาให้ endpoint นี้กับ export มคอ.5 เรียกตัว
  เดียวกัน ไม่มีสองชุด)

เชื่อมกับ : - GET /clo-achievement (ไม่มี path ต่อท้าย) ใช้ในหน้าจัดการ offering (ดูผลสอบทั้งห้อง) เรียก
              compute_offering_clo_achievement() จาก clo_achievement_service.py ตรงๆ
            - GET /clo-achievement/student-course ใช้ในหน้าผลบรรลุรายบุคคล (student-plo) ตอนขยายดู
              รายวิชา (endpoint นี้ยังคำนวณเองในไฟล์นี้ ไม่ได้ผ่าน service - คนละ scope คือ 1 คน 1 วิชา
              ไม่ใช่ทั้งห้อง)
            - GET /clo-achievement/export/mco5 ใช้ app/services/mco5_export_service.py สร้างไฟล์ Excel
              ประกอบ มคอ.5 - เรียก compute_offering_clo_achievement_raw() (รุ่นละเอียด แยก "ไม่มีข้อมูล"
              ออกจาก "ได้ 0%" ได้ตรงๆ) ไม่ใช่ compute_offering_clo_achievement() (รุ่น response เดิม)

ถ้าแก้ : สูตรใน clo_achievement_service.py ต้องตรงกับสูตรใน plo_calculation.py เสมอ (คำนวณ mastery
         เหมือนกันแต่คนละ scope) ถ้าแก้ไม่พร้อมกัน ตัวเลข mastery รายวิชาที่นี่กับที่ใช้ตัดสิน PLO จะไม่
         ตรงกัน
"""
from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import (
    CLO,
    AssessmentItem,
    Course,
    CourseOffering,
    Enrollment,
    ItemCLO,
    Student,
    StudentScore,
    User,
)
from app.schemas.clo_calculation import OfferingCLOAchievement
from app.services.clo_achievement_service import compute_offering_clo_achievement
from app.services.mco5_export_service import build_mco5_excel, resolve_mco5_export_access

router = APIRouter(prefix="/clo-achievement", tags=["CLO Achievement"])


# ชิ้นงาน (assessment item) 1 ชิ้นที่ส่งผลต่อ CLO ข้อหนึ่ง พร้อมคะแนนที่นักศึกษาคนนี้ได้จริง
class CLOItemContribution(BaseModel):
    item_id: int
    item_name: str
    item_type: str
    total_score: Decimal
    score_obtained: Decimal | None  # None = ยังไม่มีคะแนนบันทึกสำหรับชิ้นงานนี้
    weight_percent: Decimal


# ผล CLO ข้อเดียวของนักศึกษา 1 คนในวิชาเดียว พร้อมรายชิ้นงานที่ประกอบเป็นคะแนนนี้ (items)
class StudentCourseCLOItem(BaseModel):
    clo_id: int
    clo_code: str
    description: str
    pass_threshold_percent: Decimal
    mastery_percent: Decimal | None  # None = ไม่มีข้อมูลคะแนนเลยสักชิ้นงานที่ผูกกับ CLO นี้
    passed: bool
    items: list[CLOItemContribution]


# response ของ GET /clo-achievement/student-course — ผล CLO ทุกข้อของวิชานี้ สำหรับนักศึกษา 1 คน
class StudentCourseCLOBreakdown(BaseModel):
    student_id: str
    course_id: int
    course_code: str
    name_th: str
    offering_id: int | None  # None = นักศึกษาคนนี้ไม่เคยลงทะเบียนวิชานี้เลย (ไม่มี offering ให้เทียบคะแนน)
    clos: list[StudentCourseCLOItem]


@router.get("", response_model=OfferingCLOAchievement)
def get_offering_clo_achievement(
    offering_id: int = Query(..., description="Course offering ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    ทำอะไร : คำนวณผล CLO ทุกข้อของวิชานี้ สำหรับนักศึกษาทั้งห้อง (offering) เดียว — คืนจำนวนคนผ่าน/
             ไม่ผ่าน/ไม่มีข้อมูล ต่อ CLO พร้อมคะแนน % ของนักศึกษาแต่ละคน

    เชื่อมกับ : เรียก compute_offering_clo_achievement() จาก clo_achievement_service.py ตรงๆ (ตัวสูตร
                จริงอยู่ที่นั่น) — ใช้ในหน้าจัดการ offering ของอาจารย์/แอดมิน (CLOAchievementPanel.jsx)

    ถ้าแก้ : 404 ถ้าไม่พบ offering_id — นักศึกษาที่ weight_total เป็น 0 (ไม่มีคะแนนชิ้นงานที่ผูกกับ
             CLO นี้เลย) จะถูกนับใน students_without_data ไม่ใช่ passed_count หรือ failed_count
    """
    offering = db.get(CourseOffering, offering_id)
    if offering is None:
        raise HTTPException(status_code=404, detail="Course offering not found")

    return compute_offering_clo_achievement(db, offering)


@router.get("/export/mco5")
def export_mco5_excel(
    offering_id: int = Query(..., description="Course offering ID"),
    target_rate: float = Query(70.0, description="เกณฑ์ระดับรายวิชา (%) - CLO บรรลุเมื่อร้อยละที่ผ่าน >= ค่านี้"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    ทำอะไร : export ข้อมูลประกอบ มคอ.5 (รายงานผลรายวิชา) ของ offering เดียวเป็นไฟล์ Excel (5 ชีต) -
             ตัวเลขทุกตัวคำนวณจากระบบ ไม่ให้อาจารย์คิดเลขเอง (ดู TASK-export-mco5.md)

    เชื่อมกับ : resolve_mco5_export_access() (mco5_export_service.py) เช็คสิทธิ์ + หา offering ให้ในตัว
                เดียว (404/403 จากตรงนั้น) แล้ว build_mco5_excel() ใช้
                compute_offering_clo_achievement_raw() คำนวณตัวเลข CLO ชุดเดียวกับ GET /clo-achievement
                เป๊ะ (คนละฟังก์ชันแค่เพราะต้องการความละเอียดกว่า - ดู clo_achievement_service.py)

    ถ้าแก้ : สิทธิ์ (สำคัญ - ข้อมูลรายบุคคล/PDPA) : admin หรืออาจารย์เจ้าของ offering ได้ทุกชีต role
             อื่นได้แค่ชีตสรุป (ไม่มีชีต 5 รายบุคคล) - ดู resolve_mco5_export_access()
    """
    offering, include_personal_sheet = resolve_mco5_export_access(db, offering_id, current_user)

    workbook_bytes = build_mco5_excel(
        db,
        offering,
        target_rate=Decimal(str(target_rate)),
        include_personal_sheet=include_personal_sheet,
    )

    filename = (
        f"mco5_{offering.course.course_code}_{offering.academic_year}-{offering.semester}"
        f"_sec{offering.section}.xlsx"
    )
    return StreamingResponse(
        workbook_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/student-course", response_model=StudentCourseCLOBreakdown)
def get_student_course_clo_breakdown(
    student_id: str = Query(..., description="Student ID, e.g. 6500001"),
    course_id: int = Query(..., description="Course ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    ทำอะไร : เจาะลึกระดับ CLO -> คะแนน สำหรับนักศึกษาคนเดียวในวิชาเดียว คืนทั้งค่า mastery สรุปต่อ CLO
             และรายละเอียดว่าแต่ละชิ้นงาน (assessment item) ให้คะแนนเท่าไหร่ น้ำหนักเท่าไหร่

    เชื่อมกับ : ใช้สูตรเดียวกับ _clo_mastery_for_student ใน plo_calculation.py (weighted average) แต่
                คืนรายละเอียดราย item ด้วย ไม่ใช่แค่ตัวเลขสรุป — เรียกจากหน้ารายละเอียดนักศึกษา
                (student-plo) ตอนกดขยายดูว่าทำไมวิชานั้นถึงผ่าน/ไม่ผ่าน (CourseCLOBreakdown.jsx)

    ถ้าแก้ : 404 ถ้าไม่พบนักศึกษาหรือวิชา — offering_id เป็น None ถ้านักศึกษาคนนี้ไม่เคยลงทะเบียนวิชา
             นี้เลย (clos จะคืนมาแต่ mastery_percent เป็น None ทุกข้อ เพราะไม่มี offering ให้เทียบคะแนน)
    """
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")

    offering = (
        db.query(CourseOffering)
        .join(Enrollment, Enrollment.offering_id == CourseOffering.id)
        .filter(Enrollment.student_id == student_id, CourseOffering.course_id == course_id)
        .first()
    )

    clos = db.query(CLO).filter(CLO.course_id == course_id).order_by(CLO.code).all()

    items_by_id: dict[int, AssessmentItem] = {}
    item_clos: list[ItemCLO] = []
    scores_by_item: dict[int, Decimal] = {}
    if offering is not None:
        items_by_id = {
            item.id: item
            for item in db.query(AssessmentItem).filter(AssessmentItem.offering_id == offering.id).all()
        }
        if items_by_id:
            item_clos = db.query(ItemCLO).filter(ItemCLO.item_id.in_(items_by_id.keys())).all()
            scores = (
                db.query(StudentScore)
                .filter(
                    StudentScore.student_id == student_id,
                    StudentScore.item_id.in_(items_by_id.keys()),
                )
                .all()
            )
            scores_by_item = {s.item_id: s.score_obtained for s in scores}

    item_clos_by_clo: dict[int, list[ItemCLO]] = {}
    for ic in item_clos:
        item_clos_by_clo.setdefault(ic.clo_id, []).append(ic)

    clo_results: list[StudentCourseCLOItem] = []
    for clo in clos:
        mappings = item_clos_by_clo.get(clo.id, [])
        weighted_sum = Decimal(0)
        weight_total = Decimal(0)
        contributions: list[CLOItemContribution] = []
        for ic in mappings:
            item = items_by_id.get(ic.item_id)
            if item is None:
                continue
            score = scores_by_item.get(ic.item_id)
            # สะสม weighted_sum/weight_total เฉพาะชิ้นงานที่มีคะแนนแล้ว (สูตรเดียวกับที่อื่นในระบบ) แต่
            # ยังคงเก็บ contributions ของทุกชิ้นงานไว้แสดง แม้จะยังไม่มีคะแนน (score_obtained เป็น None)
            if score is not None and item.total_score > 0:
                item_percent = (score / item.total_score) * Decimal(100)
                weighted_sum += item_percent * ic.weight_percent
                weight_total += ic.weight_percent
            contributions.append(
                CLOItemContribution(
                    item_id=item.id,
                    item_name=item.name,
                    item_type=item.type,
                    total_score=item.total_score,
                    score_obtained=score,
                    weight_percent=ic.weight_percent,
                )
            )

        mastery = (weighted_sum / weight_total).quantize(Decimal("0.1")) if weight_total > 0 else None
        passed = mastery is not None and mastery >= clo.pass_threshold_percent

        clo_results.append(
            StudentCourseCLOItem(
                clo_id=clo.id,
                clo_code=clo.code,
                description=clo.description,
                pass_threshold_percent=clo.pass_threshold_percent,
                mastery_percent=mastery,
                passed=passed,
                items=contributions,
            )
        )

    return StudentCourseCLOBreakdown(
        student_id=student.id,
        course_id=course.id,
        course_code=course.course_code,
        name_th=course.name_th,
        offering_id=offering.id if offering is not None else None,
        clos=clo_results,
    )
