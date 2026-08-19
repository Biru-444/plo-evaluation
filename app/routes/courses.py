"""API routes for Course"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Course
from app.schemas import CourseSchema

router = APIRouter(prefix="/courses", tags=["Courses"])


@router.get("", response_model=list[CourseSchema])
def list_courses(db: Session = Depends(get_db)):
    return db.query(Course).order_by(Course.id).all()


@router.get("/{course_id}", response_model=CourseSchema)
def get_course(course_id: int, db: Session = Depends(get_db)):
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    return course
