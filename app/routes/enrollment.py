"""API routes for Enrollment"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Enrollment
from app.schemas import EnrollmentCreateSchema, EnrollmentSchema

router = APIRouter(prefix="/enrollments", tags=["Enrollments"])


@router.get("", response_model=list[EnrollmentSchema])
def list_enrollments(db: Session = Depends(get_db)):
    return db.query(Enrollment).order_by(Enrollment.id).all()


@router.post("", response_model=EnrollmentSchema, status_code=201)
def create_enrollment(payload: EnrollmentCreateSchema, db: Session = Depends(get_db)):
    enrollment = Enrollment(**payload.model_dump())
    db.add(enrollment)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Enrollment already exists or references an invalid student/offering",
        ) from exc
    db.refresh(enrollment)
    return enrollment
