"""API routes for Student"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Student
from app.schemas import StudentSchema

router = APIRouter(prefix="/students", tags=["Students"])


@router.get("", response_model=list[StudentSchema])
def list_students(db: Session = Depends(get_db)):
    return db.query(Student).order_by(Student.id).all()


@router.get("/{student_id}", response_model=StudentSchema)
def get_student(student_id: str, db: Session = Depends(get_db)):
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")
    return student
