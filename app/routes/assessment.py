"""API routes for AssessmentItem and StudentScore"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import AssessmentItem, CourseOffering, StudentScore, User
from app.schemas import (
    AssessmentCreateSchema,
    AssessmentItemSchema,
    AssessmentItemUpdateSchema,
    StudentScoreDetailSchema,
    StudentScoreSchema,
    StudentScoreUpdateSchema,
)

router = APIRouter(tags=["Assessment"])


@router.get("/assessment-items", response_model=list[AssessmentItemSchema])
def list_assessment_items(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(AssessmentItem).order_by(AssessmentItem.id).all()


@router.get("/assessment-items/{item_id}", response_model=AssessmentItemSchema)
def get_assessment_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = db.get(AssessmentItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Assessment item not found")
    return item


@router.post("/assessment-items", response_model=AssessmentItemSchema, status_code=201)
def create_assessment_item(
    payload: AssessmentCreateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        offering = db.get(CourseOffering, payload.offering_id)
        if offering is None or offering.instructor_id != current_user.id:
            raise HTTPException(status_code=403, detail="คุณไม่ใช่ผู้สอนวิชานี้")

    item = AssessmentItem(**payload.model_dump())
    db.add(item)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Assessment item could not be created (invalid offering?)",
        ) from exc
    db.refresh(item)
    return item


@router.put("/assessment-items/{item_id}", response_model=AssessmentItemSchema)
def update_assessment_item(
    item_id: int,
    payload: AssessmentItemUpdateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = db.get(AssessmentItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Assessment item not found")
    if current_user.role != "admin":
        offering = db.get(CourseOffering, item.offering_id)
        if offering is None or offering.instructor_id != current_user.id:
            raise HTTPException(status_code=403, detail="คุณไม่ใช่ผู้สอนวิชานี้")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="Assessment item could not be updated"
        ) from exc
    db.refresh(item)
    return item


@router.delete("/assessment-items/{item_id}", status_code=204)
def delete_assessment_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = db.get(AssessmentItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Assessment item not found")
    if current_user.role != "admin":
        offering = db.get(CourseOffering, item.offering_id)
        if offering is None or offering.instructor_id != current_user.id:
            raise HTTPException(status_code=403, detail="คุณไม่ใช่ผู้สอนวิชานี้")
    db.delete(item)  # cascade ลบ item_clo / student_score ที่อ้างถึงด้วย
    db.commit()


@router.get("/student-scores", response_model=list[StudentScoreDetailSchema])
def list_student_scores(
    student_id: str | None = Query(None, description="Student ID, e.g. 6500001"),
    offering_id: int | None = Query(None, description="คืนคะแนนของนักศึกษาทุกคนในวิชานี้"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if student_id is None and offering_id is None:
        raise HTTPException(status_code=400, detail="Provide student_id or offering_id")

    query = db.query(StudentScore).join(AssessmentItem, StudentScore.item_id == AssessmentItem.id)
    if student_id is not None:
        query = query.filter(StudentScore.student_id == student_id)
    if offering_id is not None:
        query = query.filter(AssessmentItem.offering_id == offering_id)
    scores = query.order_by(StudentScore.id).all()
    return [
        StudentScoreDetailSchema(
            id=score.id,
            item_id=score.item_id,
            item_name=score.item.name,
            total_score=score.item.total_score,
            student_id=score.student_id,
            score_obtained=score.score_obtained,
        )
        for score in scores
    ]


@router.post("/student-scores", response_model=StudentScoreSchema, status_code=201)
def create_student_score(
    payload: StudentScoreSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    score = StudentScore(**payload.model_dump(exclude={"id"}))
    db.add(score)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Score already exists for this student/item, or references an invalid item/student",
        ) from exc
    db.refresh(score)
    return score


@router.put("/student-scores/{score_id}", response_model=StudentScoreSchema)
def update_student_score(
    score_id: int,
    payload: StudentScoreUpdateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    score = db.get(StudentScore, score_id)
    if score is None:
        raise HTTPException(status_code=404, detail="Student score not found")

    score.score_obtained = payload.score_obtained
    db.commit()
    db.refresh(score)
    return score
