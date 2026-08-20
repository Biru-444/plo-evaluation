"""API routes for Student"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_role
from app.database import get_db
from app.models import Student, User
from app.schemas import StudentCreateSchema, StudentSchema, StudentUpdateSchema

router = APIRouter(prefix="/students", tags=["Students"])


@router.get("", response_model=list[StudentSchema])
def list_students(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(Student).order_by(Student.id).all()


@router.get("/{student_id}", response_model=StudentSchema)
def get_student(
    student_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")
    return student


@router.post("", response_model=StudentSchema, status_code=201)
def create_student(
    payload: StudentCreateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    student = Student(**payload.model_dump())
    db.add(student)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Student ID already exists, or references an invalid curriculum",
        ) from exc
    db.refresh(student)
    return student


@router.put("/{student_id}", response_model=StudentSchema)
def update_student(
    student_id: str,
    payload: StudentUpdateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(student, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Student could not be updated") from exc
    db.refresh(student)
    return student


@router.delete("/{student_id}", status_code=204)
def delete_student(
    student_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")
    db.delete(student)  # cascade ลบ enrollment / student_score ที่อ้างถึงด้วย
    db.commit()
