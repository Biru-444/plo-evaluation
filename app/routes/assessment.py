"""API routes for AssessmentItem and StudentScore"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AssessmentItem, StudentScore
from app.schemas import AssessmentItemSchema, StudentScoreSchema

router = APIRouter(tags=["Assessment"])


@router.get("/assessment-items", response_model=list[AssessmentItemSchema])
def list_assessment_items(db: Session = Depends(get_db)):
    return db.query(AssessmentItem).order_by(AssessmentItem.id).all()


@router.post("/student-scores", response_model=StudentScoreSchema, status_code=201)
def create_student_score(payload: StudentScoreSchema, db: Session = Depends(get_db)):
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
