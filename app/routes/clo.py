"""API routes for CLO"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import CLO, CourseOffering, User
from app.schemas import CLOCreateSchema, CLOSchema, CLOUpdateSchema

router = APIRouter(prefix="/clo", tags=["CLO"])


@router.get("", response_model=list[CLOSchema])
def list_clo(
    course_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(CLO)
    if course_id is not None:
        query = query.filter(CLO.course_id == course_id)
    return query.order_by(CLO.id).all()


@router.get("/{clo_id}", response_model=CLOSchema)
def get_clo(
    clo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    clo = db.get(CLO, clo_id)
    if clo is None:
        raise HTTPException(status_code=404, detail="CLO not found")
    return clo


@router.post("", response_model=CLOSchema, status_code=201)
def create_clo(
    payload: CLOCreateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        owns_course = (
            db.query(CourseOffering)
            .filter(
                CourseOffering.course_id == payload.course_id,
                CourseOffering.instructor_id == current_user.id,
            )
            .first()
        )
        if owns_course is None:
            raise HTTPException(status_code=403, detail="คุณไม่ใช่ผู้สอนวิชานี้")

    clo = CLO(**payload.model_dump(), created_by=current_user.id)
    db.add(clo)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="CLO could not be created (duplicate code in this course?)",
        ) from exc
    db.refresh(clo)
    return clo


@router.put("/{clo_id}", response_model=CLOSchema)
def update_clo(
    clo_id: int,
    payload: CLOUpdateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    clo = db.get(CLO, clo_id)
    if clo is None:
        raise HTTPException(status_code=404, detail="CLO not found")
    if current_user.role != "admin":
        owns_course = (
            db.query(CourseOffering)
            .filter(
                CourseOffering.course_id == clo.course_id,
                CourseOffering.instructor_id == current_user.id,
            )
            .first()
        )
        if owns_course is None:
            raise HTTPException(status_code=403, detail="คุณไม่ใช่ผู้สอนวิชานี้")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(clo, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="CLO could not be updated") from exc
    db.refresh(clo)
    return clo


@router.delete("/{clo_id}", status_code=204)
def delete_clo(
    clo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    clo = db.get(CLO, clo_id)
    if clo is None:
        raise HTTPException(status_code=404, detail="CLO not found")
    if current_user.role != "admin":
        owns_course = (
            db.query(CourseOffering)
            .filter(
                CourseOffering.course_id == clo.course_id,
                CourseOffering.instructor_id == current_user.id,
            )
            .first()
        )
        if owns_course is None:
            raise HTTPException(status_code=403, detail="คุณไม่ใช่ผู้สอนวิชานี้")
    db.delete(clo)  # cascade ลบ item_clo ที่อ้างถึงด้วย
    db.commit()
