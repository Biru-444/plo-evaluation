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

from app.database import get_db
from app.models import CLO, CLOPLOMapping, Enrollment, AssessmentItem, ItemCLO, PLO, Student, StudentScore

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


@router.get("/achievement", response_model=StudentPLOAchievement)
def get_plo_achievement(
    student_id: str = Query(..., description="Student ID, e.g. 6500001"),
    db: Session = Depends(get_db),
):
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")

    plos = (
        db.query(PLO)
        .filter(PLO.curriculum_id == student.curriculum_id)
        .order_by(PLO.code)
        .all()
    )

    offering_ids = [
        row[0]
        for row in db.query(Enrollment.offering_id)
        .filter(Enrollment.student_id == student.id)
        .all()
    ]

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
