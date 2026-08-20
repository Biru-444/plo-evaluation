"""API routes for Enrollment"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_role
from app.database import get_db
from app.models import Enrollment, User
from app.schemas import EnrollmentCreateSchema, EnrollmentSchema, EnrollmentUpdateSchema

router = APIRouter(prefix="/enrollments", tags=["Enrollments"])


@router.get("", response_model=list[EnrollmentSchema])
def list_enrollments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(Enrollment).order_by(Enrollment.id).all()


@router.get("/{enrollment_id}", response_model=EnrollmentSchema)
def get_enrollment(
    enrollment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    enrollment = db.get(Enrollment, enrollment_id)
    if enrollment is None:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    return enrollment


@router.post("", response_model=EnrollmentSchema, status_code=201)
def create_enrollment(
    payload: EnrollmentCreateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
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


@router.put("/{enrollment_id}", response_model=EnrollmentSchema)
def update_enrollment(
    enrollment_id: int,
    payload: EnrollmentUpdateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    enrollment = db.get(Enrollment, enrollment_id)
    if enrollment is None:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(enrollment, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Enrollment could not be updated") from exc
    db.refresh(enrollment)
    return enrollment


@router.delete("/{enrollment_id}", status_code=204)
def delete_enrollment(
    enrollment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    enrollment = db.get(Enrollment, enrollment_id)
    if enrollment is None:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    db.delete(enrollment)  # cascade ลบ ไม่มี child table อ้างถึง enrollment โดยตรง
    db.commit()
