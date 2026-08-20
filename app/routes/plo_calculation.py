"""
PLO achievement calculation route.

Calculation:
  1. CLO mastery  = weighted average of a student's % score on every
     assessment item that measures that CLO, weighted by item_clo.weight_percent.
  2. PLO achievement = weighted average of the student's CLO masteries for
     every CLO that maps to that PLO, weighted by clo_plo_mapping.weight_percent.
  Only items/CLOs the student actually has a recorded score for are counted;
  a PLO with no underlying data yet is reported as 0% / not achieved.
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

PLO_ACHIEVEMENT_THRESHOLD = Decimal("60.0")


class PLOAchievementItem(BaseModel):
    plo_id: int
    plo_code: str
    description: str
    achieved_percent: float
    is_achieved: bool


class StudentPLOAchievement(BaseModel):
    student_id: str
    student_name: str
    curriculum_id: int
    plo_achievements: list[PLOAchievementItem]


class PLOCohortSummaryItem(BaseModel):
    plo_id: int
    plo_code: str
    description: str
    student_count_with_data: int
    average_achieved_percent: float
    achieved_student_count: int
    achieved_rate_percent: float


class CurriculumPLOAchievement(BaseModel):
    curriculum_id: int
    curriculum_name: str
    total_students: int
    plo_summary: list[PLOCohortSummaryItem]
    students: list[StudentPLOAchievement]


class YearlyPLOSummaryItem(BaseModel):
    plo_id: int
    plo_code: str
    description: str
    is_expected_this_year: bool
    student_count_with_data: int
    average_achieved_percent: float
    achieved_student_count: int
    achieved_rate_percent: float


class YearProgressItem(BaseModel):
    year_level: int
    ylo_description: str
    course_count: int
    plo_summary: list[YearlyPLOSummaryItem]
    students: list[StudentPLOAchievement]


class CurriculumYearProgress(BaseModel):
    curriculum_id: int
    curriculum_name: str
    years: list[YearProgressItem]


def _calculate_plo_achievement_for_student(
    db: Session, student: Student, course_id_filter: set[int] | None = None
) -> StudentPLOAchievement:
    plos = (
        db.query(PLO)
        .filter(PLO.curriculum_id == student.curriculum_id)
        .order_by(PLO.code)
        .all()
    )

    offering_query = db.query(Enrollment.offering_id).filter(Enrollment.student_id == student.id)
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
                    StudentScore.student_id == student.id,
                    StudentScore.item_id.in_(item_by_id.keys()),
                )
                .all()
            )
            score_by_item = {s.item_id: s.score_obtained for s in scores}

            item_clos = (
                db.query(ItemCLO).filter(ItemCLO.item_id.in_(item_by_id.keys())).all()
            )

    # Step 1: CLO mastery per CLO the student has been assessed on.
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

    clo_mastery: dict[int, Decimal] = {
        clo_id: clo_weighted_sum[clo_id] / clo_weight_total[clo_id]
        for clo_id in clo_weighted_sum
        if clo_weight_total[clo_id] > 0
    }

    # Step 2: PLO achievement per PLO, from the CLOs mastered above.
    plo_weighted_sum: dict[int, Decimal] = {}
    plo_weight_total: dict[int, Decimal] = {}
    if clo_mastery:
        clo_plo_mappings = (
            db.query(CLOPLOMapping).filter(CLOPLOMapping.clo_id.in_(clo_mastery.keys())).all()
        )
        for mapping in clo_plo_mappings:
            mastery = clo_mastery.get(mapping.clo_id)
            if mastery is None:
                continue
            plo_weighted_sum[mapping.plo_id] = (
                plo_weighted_sum.get(mapping.plo_id, Decimal(0)) + mastery * mapping.weight_percent
            )
            plo_weight_total[mapping.plo_id] = (
                plo_weight_total.get(mapping.plo_id, Decimal(0)) + mapping.weight_percent
            )

    achievements = []
    for plo in plos:
        total_weight = plo_weight_total.get(plo.id, Decimal(0))
        achieved = (plo_weighted_sum[plo.id] / total_weight) if total_weight > 0 else Decimal(0)
        achieved = achieved.quantize(Decimal("0.1"))
        achievements.append(
            PLOAchievementItem(
                plo_id=plo.id,
                plo_code=plo.code,
                description=plo.description_th,
                achieved_percent=float(achieved),
                is_achieved=achieved >= PLO_ACHIEVEMENT_THRESHOLD,
            )
        )

    return StudentPLOAchievement(
        student_id=student.id,
        student_name=f"{student.first_name} {student.last_name}",
        curriculum_id=student.curriculum_id,
        plo_achievements=achievements,
    )


def _aggregate_plo_percent_stats(
    student_achievements: list[StudentPLOAchievement],
) -> tuple[dict[int, Decimal], dict[int, int], dict[int, int]]:
    """Sum achieved_percent, and count students with data / who achieved, per PLO.

    Shared by /achievement/cohort and /achievement/by-year so the cohort-level
    averaging logic exists in exactly one place.
    """
    percent_sum_by_plo: dict[int, Decimal] = {}
    # A 0% achieved_percent is the same sentinel _calculate_plo_achievement_for_student
    # uses for "no underlying data yet" (see module docstring), so it doubles here as
    # the signal that this student has no recorded data for that PLO.
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


@router.get("/achievement", response_model=StudentPLOAchievement)
def get_plo_achievement(
    student_id: str = Query(..., description="Student ID, e.g. 6500001"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")

    return _calculate_plo_achievement_for_student(db, student)


@router.get("/achievement/cohort", response_model=CurriculumPLOAchievement)
def get_cohort_plo_achievement(
    curriculum_id: int = Query(..., description="Curriculum ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    curriculum = db.get(Curriculum, curriculum_id)
    if curriculum is None:
        raise HTTPException(status_code=404, detail="Curriculum not found")

    plos = (
        db.query(PLO)
        .filter(PLO.curriculum_id == curriculum_id)
        .order_by(PLO.code)
        .all()
    )

    students = db.query(Student).filter(Student.curriculum_id == curriculum_id).all()

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
        )

    student_achievements = [
        _calculate_plo_achievement_for_student(db, student) for student in students
    ]
    students_sorted = sorted(
        student_achievements, key=lambda sa: (sa.student_name, sa.student_id)
    )

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

    return CurriculumPLOAchievement(
        curriculum_id=curriculum.id,
        curriculum_name=curriculum.name,
        total_students=total_students,
        plo_summary=plo_summary,
        students=students_sorted,
    )


@router.get("/achievement/by-year", response_model=CurriculumYearProgress)
def get_plo_achievement_by_year(
    curriculum_id: int = Query(..., description="Curriculum ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Same weighted-average PLO calculation as /achievement/cohort, but run
    once per year_level (1-4) with only that year's study_plan courses
    counted - so each year reflects what was taught that year, not a
    cumulative total. Also flags which PLOs that year's YLO expects."""
    curriculum = db.get(Curriculum, curriculum_id)
    if curriculum is None:
        raise HTTPException(status_code=404, detail="Curriculum not found")

    plos = db.query(PLO).filter(PLO.curriculum_id == curriculum_id).order_by(PLO.code).all()
    students = db.query(Student).filter(Student.curriculum_id == curriculum_id).all()
    total_students = len(students)

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

        student_achievements = [
            _calculate_plo_achievement_for_student(db, student, course_id_filter=course_ids)
            for student in students
        ]
        students_sorted = sorted(
            student_achievements, key=lambda sa: (sa.student_name, sa.student_id)
        )

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
    )
