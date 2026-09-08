"""
Per-offering CLO achievement calculation.

Unlike plo_calculation.py (student- and curriculum-level PLO achievement),
this computes CLO mastery for one course_offering's whole class - the CLOs
belong to the offering's course, and only students enrolled in that
offering are considered.

Calculation: same weighted-average CLO mastery as
_calculate_plo_achievement_for_student's "Step 1" in plo_calculation.py -
sum(score/total_score*100 * item_clo.weight_percent) / sum(item_clo.weight_percent),
counting only assessment items the student actually has a recorded score for.
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


class StudentCLOScore(BaseModel):
    student_id: str
    student_name: str
    clo_percent: float
    passed: bool


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


class OfferingCLOAchievement(BaseModel):
    offering_id: int
    course_name: str
    clo_achievements: list[CLOAchievementItem]


class CLOItemContribution(BaseModel):
    item_id: int
    item_name: str
    item_type: str
    total_score: Decimal
    score_obtained: Decimal | None  # None = ยังไม่มีคะแนนบันทึกสำหรับชิ้นงานนี้
    weight_percent: Decimal


class StudentCourseCLOItem(BaseModel):
    clo_id: int
    clo_code: str
    description: str
    pass_threshold_percent: Decimal
    mastery_percent: Decimal | None  # None = ไม่มีข้อมูลคะแนนเลยสักชิ้นงานที่ผูกกับ CLO นี้
    passed: bool
    items: list[CLOItemContribution]


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
            for ic in mappings:
                item = item_by_id.get(ic.item_id)
                score = scores_by_student_item.get((student.id, ic.item_id))
                if item is None or score is None or item.total_score <= 0:
                    continue
                item_percent = (score / item.total_score) * Decimal(100)
                weighted_sum += item_percent * ic.weight_percent
                weight_total += ic.weight_percent

            student_name = f"{student.first_name} {student.last_name}"

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
    """เจาะลึกระดับ CLO -> คะแนน สำหรับนักศึกษาคนเดียวในวิชาเดียว - ใช้ในหน้ารายละเอียดนักศึกษา
    (student-plo) ตอนกดขยายดูว่าทำไมวิชานั้นถึงผ่าน/ไม่ผ่าน ใช้สูตรเดียวกับ _clo_mastery_for_student
    ใน plo_calculation.py (weighted average) แต่คืนรายละเอียดราย item ด้วย ไม่ใช่แค่ตัวเลขสรุป"""
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
