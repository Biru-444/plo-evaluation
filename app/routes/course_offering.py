"""API routes for CourseOffering"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_role
from app.database import get_db
from app.models import CourseOffering, User
from app.schemas import (
    CourseOfferingCreateSchema,
    CourseOfferingSchema,
    CourseOfferingUpdateSchema,
)

router = APIRouter(prefix="/course-offerings", tags=["Course Offerings"])


@router.get("", response_model=list[CourseOfferingSchema])
def list_course_offerings(
    course_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(CourseOffering)
    if course_id is not None:
        query = query.filter(CourseOffering.course_id == course_id)
    return query.order_by(CourseOffering.id).all()


@router.get("/{offering_id}", response_model=CourseOfferingSchema)
def get_course_offering(
    offering_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    offering = db.get(CourseOffering, offering_id)
    if offering is None:
        raise HTTPException(status_code=404, detail="Course offering not found")
    return offering


@router.post("", response_model=CourseOfferingSchema, status_code=201)
def create_course_offering(
    payload: CourseOfferingCreateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    offering = CourseOffering(**payload.model_dump())
    db.add(offering)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Offering already exists, or references an invalid course/instructor",
        ) from exc
    db.refresh(offering)
    return offering


@router.put("/{offering_id}", response_model=CourseOfferingSchema)
def update_course_offering(
    offering_id: int,
    payload: CourseOfferingUpdateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    offering = db.get(CourseOffering, offering_id)
    if offering is None:
        raise HTTPException(status_code=404, detail="Course offering not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(offering, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="Course offering could not be updated"
        ) from exc
    db.refresh(offering)
    return offering


@router.delete("/{offering_id}", status_code=204)
def delete_course_offering(
    offering_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    offering = db.get(CourseOffering, offering_id)
    if offering is None:
        raise HTTPException(status_code=404, detail="Course offering not found")
    db.delete(offering)  # cascade ลบ enrollment / assessment_item ที่อ้างถึงด้วย
    db.commit()
