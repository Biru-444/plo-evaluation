"""
YLO achievement calculation route.

Brand-new feature - there was previously no "% บรรลุ YLO" calculation anywhere in
this system (confirmed while building the "YLO ตามชั้นปี" page, which only showed
the YLO goal text). Reuses _clo_passed from plo_calculation.py (imported, not
duplicated or modified) since "passes a CLO" is defined identically everywhere.

Calculation (confirmed spec):
  A student achieves YLO year N of a curriculum only if they pass EVERY course
  that satisfies BOTH conditions at once:
    (a) the course has a CLO mapped (via clo_plo_mapping) to any PLO that this
        YLO is mapped to (via ylo_plo_mapping - a YLO is usually mapped to
        several PLOs, this is a union across all of them, not just one)
    (b) the course is scheduled for year_level N in study_plan, for the same
        curriculum (courses from other years that happen to share a PLO with
        this YLO are excluded - condition (b) is what keeps them out)
  "Passes a course" (for this YLO) = every one of that course's CLOs that maps
  to *any* PLO in this YLO's PLO group passes its own pass_threshold_percent
  (same per-CLO pass/fail rule as the PLO work - CLOs of the same course that
  don't map to any PLO in this group are irrelevant and excluded).
  A YLO with zero qualifying courses (no PLO mapped, or no study_plan course
  for that year matches any of those PLOs) is reported as not achieved - no
  data to judge from, not an automatic pass. Same rule as the PLO work.
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

router = APIRouter(prefix="/ylo", tags=["YLO Achievement"])


class YLOAchievementStudentItem(BaseModel):
    student_id: str
    student_name: str
    is_achieved: bool


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


def _study_plan_course_ids(
    db: Session, curriculum_id: int, year_level: int, cohort_year: int | None
) -> set[int]:
    """Cohort-specific study_plan rows win if any exist for this exact cohort_year,
    else fall back to the standard plan (cohort_year IS NULL). Real data in this
    system currently only has standard-plan rows, but this keeps the behavior
    correct if per-cohort overrides get added later."""
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


def _build_ylo_requirements(
    db: Session, ylo: YLO, cohort_year: int | None
) -> dict[int, set[int]]:
    """course_id -> set of that course's CLO ids that map to any PLO in this
    YLO's PLO group AND belong to a course scheduled for this YLO's year_level.
    Both condition (a) (PLO group membership) and (b) (year match) are applied
    here together, so a course from a different year never leaks in even if it
    shares a PLO with this YLO."""
    plo_ids = {
        row[0]
        for row in db.query(YLOPLOMapping.plo_id).filter(YLOPLOMapping.ylo_id == ylo.id).all()
    }
    if not plo_ids:
        return {}

    course_ids_this_year = _study_plan_course_ids(db, ylo.curriculum_id, ylo.year_level, cohort_year)
    if not course_ids_this_year:
        return {}

    rows = (
        db.query(CLOPLOMapping.clo_id, CLO.course_id)
        .join(CLO, CLO.id == CLOPLOMapping.clo_id)
        .filter(CLOPLOMapping.plo_id.in_(plo_ids), CLO.course_id.in_(course_ids_this_year))
        .all()
    )
    requirements: dict[int, set[int]] = {}
    for clo_id, course_id in rows:
        requirements.setdefault(course_id, set()).add(clo_id)
    return requirements


def _clo_mastery_for_student(db: Session, student_id: str) -> dict[int, Decimal]:
    """Same weighted-average-per-CLO formula as plo_calculation.py/clo_calculation.py,
    computed across all of the student's enrollments (not scoped to any one
    course) - duplicated here on purpose rather than importing a private helper
    out of plo_calculation.py, so that file stays untouched."""
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
        if score is None or item is None or item.total_score <= 0:
            continue
        item_percent = (score / item.total_score) * Decimal(100)
        clo_weighted_sum[ic.clo_id] = clo_weighted_sum.get(ic.clo_id, Decimal(0)) + item_percent * ic.weight_percent
        clo_weight_total[ic.clo_id] = clo_weight_total.get(ic.clo_id, Decimal(0)) + ic.weight_percent

    return {
        clo_id: clo_weighted_sum[clo_id] / clo_weight_total[clo_id]
        for clo_id in clo_weighted_sum
        if clo_weight_total[clo_id] > 0
    }


def _clo_pass_thresholds(db: Session, clo_ids: set[int]) -> dict[int, Decimal]:
    if not clo_ids:
        return {}
    return {c.id: c.pass_threshold_percent for c in db.query(CLO).filter(CLO.id.in_(clo_ids)).all()}


def _student_achieved_ylo(
    requirements: dict[int, set[int]],
    clo_mastery: dict[int, Decimal],
    clo_pass_thresholds: dict[int, Decimal],
) -> bool:
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
    current_user: User = Depends(get_current_user),
):
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

    students_query = db.query(Student).filter(Student.curriculum_id == curriculum_id)
    if cohort_year is not None:
        students_query = students_query.filter(Student.cohort_year == cohort_year)
    students = students_query.all()
    total_students = len(students)

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
    student_items.sort(key=lambda s: (s.student_name, s.student_id))

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
        available_cohort_years=available_cohort_years,
    )
