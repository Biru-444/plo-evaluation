"""API routes for CoursePLO"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_role
from app.database import get_db
from app.models import CoursePLO, User
from app.schemas import CoursePLOCreateSchema, CoursePLOSchema, CoursePLOUpdateSchema

router = APIRouter(prefix="/course-plo", tags=["Course-PLO Mapping"])


@router.get("", response_model=list[CoursePLOSchema])
def list_course_plo(
    course_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(CoursePLO)
    if course_id is not None:
        query = query.filter(CoursePLO.course_id == course_id)
    return query.order_by(CoursePLO.id).all()


@router.get("/{course_plo_id}", response_model=CoursePLOSchema)
def get_course_plo(
    course_plo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    course_plo = db.get(CoursePLO, course_plo_id)
    if course_plo is None:
        raise HTTPException(status_code=404, detail="Course-PLO mapping not found")
    return course_plo


@router.post("", response_model=CoursePLOSchema, status_code=201)
def create_course_plo(
    payload: CoursePLOCreateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    course_plo = CoursePLO(**payload.model_dump())
    db.add(course_plo)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Mapping already exists, or references an invalid course/PLO",
        ) from exc
    db.refresh(course_plo)
    return course_plo


@router.put("/{course_plo_id}", response_model=CoursePLOSchema)
def update_course_plo(
    course_plo_id: int,
    payload: CoursePLOUpdateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    course_plo = db.get(CoursePLO, course_plo_id)
    if course_plo is None:
        raise HTTPException(status_code=404, detail="Course-PLO mapping not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(course_plo, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="Course-PLO mapping could not be updated"
        ) from exc
    db.refresh(course_plo)
    return course_plo


@router.delete("/{course_plo_id}", status_code=204)
def delete_course_plo(
    course_plo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    course_plo = db.get(CoursePLO, course_plo_id)
    if course_plo is None:
        raise HTTPException(status_code=404, detail="Course-PLO mapping not found")
    db.delete(course_plo)
    db.commit()
