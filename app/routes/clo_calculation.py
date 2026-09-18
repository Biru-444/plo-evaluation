"""
ทำอะไร : เส้นทาง API สำหรับคำนวณ "% ความเชี่ยวชาญ CLO" (mastery) ระดับ course_offering (1 กลุ่มเรียน
         ของ 1 วิชา) — ต่างจาก plo_calculation.py ที่คำนวณระดับนักศึกษา/หลักสูตรทั้งก้อน ไฟล์นี้ตอบคำถาม
         "ทั้งห้องนี้ ใครผ่าน CLO ไหนบ้าง" และ "นักศึกษาคนนี้ วิชานี้ ได้คะแนนแต่ละ CLO เท่าไหร่ จาก
         ชิ้นงานอะไรบ้าง" — CLO เป็นของวิชา (course) ส่วนคะแนนจริงผูกกับ offering ที่นักศึกษาลงทะเบียน

สูตรคำนวณ : ค่าเฉลี่ยถ่วงน้ำหนักแบบเดียวกับ "ขั้นตอนที่ 1" ใน
  plo_calculation.py._clo_mastery_for_student คือ
  sum(score/total_score*100 * item_clo.weight_percent) / sum(item_clo.weight_percent)
  นับเฉพาะ assessment item ที่นักศึกษามีคะแนนบันทึกไว้จริงเท่านั้น

เชื่อมกับ : - อ่านจากตาราง clo, assessment_item, item_clo, student_score, enrollment
            - GET /clo-achievement (ไม่มี path ต่อท้าย) ใช้ในหน้าจัดการ offering (ดูผลสอบทั้งห้อง)
            - GET /clo-achievement/student-course ใช้ในหน้าผลบรรลุรายบุคคล (student-plo) ตอนขยายดู
              รายวิชา

ถ้าแก้ : สูตรในไฟล์นี้ต้องตรงกับสูตรใน plo_calculation.py เสมอ (คำนวณ mastery เหมือนกันแต่คนละ scope)
         ถ้าแก้ไม่พร้อมกัน ตัวเลข mastery รายวิชาที่นี่กับที่ใช้ตัดสิน PLO จะไม่ตรงกัน
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
    AssessmentItem,
    Course,
    CourseOffering,
    Enrollment,
    ItemCLO,
    Student,
    StudentScore,
    User,
)

router = APIRouter(prefix="/clo-achievement", tags=["CLO Achievement"])


# คะแนน CLO ข้อเดียวของนักศึกษา 1 คนในห้อง (ใช้เป็นรายการย่อยใน CLOAchievementItem.student_scores)
class StudentCLOScore(BaseModel):
    student_id: str
    student_name: str
    clo_percent: float
    passed: bool


# สรุปผล CLO ข้อเดียวของทั้งห้อง (offering) — จำนวนผ่าน/ไม่ผ่าน/ไม่มีข้อมูล พร้อมคะแนนรายคน
class CLOAchievementItem(BaseModel):
    clo_id: int
    clo_code: str
    description: str
    pass_threshold_percent: float
    passed_count: int
    failed_count: int
    students_without_data: int
    achieved_rate_percent: float
    student_scores: list[StudentCLOScore]


# response ของ GET /clo-achievement — ผล CLO ทุกข้อของ offering เดียว
class OfferingCLOAchievement(BaseModel):
    offering_id: int
    course_name: str
    clo_achievements: list[CLOAchievementItem]


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

    เชื่อมกับ : อ่าน enrollment เพื่อหา roster ของ offering นี้ แล้วคำนวณ mastery ต่อ CLO ต่อคนด้วย
                สูตรถ่วงน้ำหนักเดียวกับ plo_calculation.py — ใช้ในหน้าจัดการ offering ของอาจารย์/แอดมิน

    ถ้าแก้ : 404 ถ้าไม่พบ offering_id — นักศึกษาที่ weight_total เป็น 0 (ไม่มีคะแนนชิ้นงานที่ผูกกับ
             CLO นี้เลย) จะถูกนับใน students_without_data ไม่ใช่ passed_count หรือ failed_count
    """
    offering = db.get(CourseOffering, offering_id)
    if offering is None:
        raise HTTPException(status_code=404, detail="Course offering not found")

    clos = db.query(CLO).filter(CLO.course_id == offering.course_id).order_by(CLO.code).all()

    items = (
        db.query(AssessmentItem)
        .filter(AssessmentItem.offering_id == offering_id)
        .all()
    )
    item_by_id: dict[int, AssessmentItem] = {item.id: item for item in items}

    item_clos: list[ItemCLO] = []
    if item_by_id:
        item_clos = db.query(ItemCLO).filter(ItemCLO.item_id.in_(item_by_id.keys())).all()

    roster: list[Student] = (
        db.query(Student)
        .join(Enrollment, Enrollment.student_id == Student.id)
        .filter(Enrollment.offering_id == offering_id)
        .order_by(Student.id)
        .all()
    )

    scores_by_student_item: dict[tuple[str, int], Decimal] = {}
    if item_by_id and roster:
        student_ids = [s.id for s in roster]
        scores = (
            db.query(StudentScore)
            .filter(
                StudentScore.item_id.in_(item_by_id.keys()),
                StudentScore.student_id.in_(student_ids),
            )
            .all()
        )
        scores_by_student_item = {(s.student_id, s.item_id): s.score_obtained for s in scores}

    item_clos_by_clo: dict[int, list[ItemCLO]] = {}
    for ic in item_clos:
        item_clos_by_clo.setdefault(ic.clo_id, []).append(ic)

    clo_achievements: list[CLOAchievementItem] = []
    for clo in clos:
        mappings = item_clos_by_clo.get(clo.id, [])
        student_scores: list[StudentCLOScore] = []
        passed_count = 0
        failed_count = 0
        students_without_data = 0

        for student in roster:
            weighted_sum = Decimal(0)
            weight_total = Decimal(0)
            # สูตรเดียวกับ plo_calculation.py._clo_mastery_for_student: แปลงคะแนนดิบเป็น % แล้ว
            # ถ่วงน้ำหนักด้วย item_clo.weight_percent สะสมเป็นตัวตั้ง/ตัวหารของ CLO นี้
            for ic in mappings:
                item = item_by_id.get(ic.item_id)
                score = scores_by_student_item.get((student.id, ic.item_id))
                if item is None or score is None or item.total_score <= 0:
                    continue
                item_percent = (score / item.total_score) * Decimal(100)
                weighted_sum += item_percent * ic.weight_percent
                weight_total += ic.weight_percent

            student_name = f"{student.first_name} {student.last_name}"

            # weight_total > 0 แปลว่ามีคะแนนชิ้นงานที่ผูกกับ CLO นี้อย่างน้อย 1 ชิ้น จึงคำนวณ % และ
            # ตัดสินผ่าน/ไม่ผ่านได้ — ถ้าไม่มีเลยจะตกไปกิ่ง else ด้านล่าง (นับเป็น "ไม่มีข้อมูล")
            if weight_total > 0:
                clo_percent = (weighted_sum / weight_total).quantize(Decimal("0.1"))
                passed = clo_percent >= clo.pass_threshold_percent
                if passed:
                    passed_count += 1
                else:
                    failed_count += 1
                student_scores.append(
                    StudentCLOScore(
                        student_id=student.id,
                        student_name=student_name,
                        clo_percent=float(clo_percent),
                        passed=passed,
                    )
                )
            else:
                students_without_data += 1
                student_scores.append(
                    StudentCLOScore(
                        student_id=student.id,
                        student_name=student_name,
                        clo_percent=0.0,
                        passed=False,
                    )
                )

        # achieved_rate_percent คิดจากคนที่ "มีข้อมูลให้ตัดสิน" เท่านั้น (passed + failed) ไม่รวม
        # students_without_data เข้าตัวหาร เพื่อไม่ให้คนที่ยังไม่มีคะแนนถูกนับเป็น "ไม่ผ่าน" ปนไปด้วย
        denom = passed_count + failed_count
        achieved_rate_percent = (
            float(Decimal(passed_count) / Decimal(denom) * Decimal(100))
            if denom > 0
            else 0.0
        )

        clo_achievements.append(
            CLOAchievementItem(
                clo_id=clo.id,
                clo_code=clo.code,
                description=clo.description,
                pass_threshold_percent=float(clo.pass_threshold_percent),
                passed_count=passed_count,
                failed_count=failed_count,
                students_without_data=students_without_data,
                achieved_rate_percent=round(achieved_rate_percent, 1),
                student_scores=student_scores,
            )
        )

    return OfferingCLOAchievement(
        offering_id=offering.id,
        course_name=offering.course.name_th,
        clo_achievements=clo_achievements,
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
