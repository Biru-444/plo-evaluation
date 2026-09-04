"""API routes for Course"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_role
from app.database import get_db
from app.models import Course, CourseOffering, Enrollment, Student, User
from app.schemas import CourseCreateSchema, CourseSchema, CourseUpdateSchema, StudentSchema

router = APIRouter(prefix="/courses", tags=["Courses"])


@router.get("", response_model=list[CourseSchema])
def list_courses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(Course).order_by(Course.id).all()


@router.get("/{course_id}", response_model=CourseSchema)
def get_course(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


@router.get("/{course_id}/enrolled-students", response_model=list[StudentSchema])
def get_course_enrolled_students(
    course_id: int,
    cohort_year: int | None = Query(
        None, description="กรองเฉพาะนักศึกษารุ่นนี้ (Student.cohort_year) - ไม่ใส่ = ทุกรุ่น"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """นักศึกษาที่ลงทะเบียนวิชานี้จริง (ผ่าน enrollment -> course_offering ที่ course_id นี้) - คนละ
    เรื่องกับ "ใครบรรลุ PLO". กรองด้วย Student.cohort_year (รุ่นที่เข้าเรียนจริงของนักศึกษา) ให้ตรงกับ
    semantics เดียวกับที่หน้า PLO ตามชั้นปี/ภาพรวม PLO ใช้กรองอยู่แล้ว (ดู plo_calculation.py) - ไม่ใช้
    CourseOffering.cohort_year เพราะเป็นคนละแนวคิด (รุ่นที่ไฟล์ roster ระบุตอน import ไม่ใช่ตัวตัดสินว่า
    นักศึกษาคนนั้นเข้าเรียนรุ่นไหนจริง) ไม่ต้องกรองด้วย curriculum_id เพิ่ม เพราะ course_id หนึ่งอยู่ได้
    แค่หลักสูตรเดียวอยู่แล้ว (Course.curriculum_id)"""
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")

    query = (
        db.query(Student)
        .join(Enrollment, Enrollment.student_id == Student.id)
        .join(CourseOffering, CourseOffering.id == Enrollment.offering_id)
        .filter(CourseOffering.course_id == course_id)
        .distinct()
    )
    if cohort_year is not None:
        query = query.filter(Student.cohort_year == cohort_year)

    return query.order_by(Student.first_name, Student.last_name).all()


@router.post("", response_model=CourseSchema, status_code=201)
def create_course(
    payload: CourseCreateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    course = Course(**payload.model_dump())
    db.add(course)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Course already exists in this curriculum, or references an invalid curriculum",
        ) from exc
    db.refresh(course)
    return course


@router.put("/{course_id}", response_model=CourseSchema)
def update_course(
    course_id: int,
    payload: CourseUpdateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(course, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Course could not be updated (duplicate course_code in this curriculum?)",
        ) from exc
    db.refresh(course)
    return course


@router.delete("/{course_id}", status_code=204)
def delete_course(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    db.delete(course)  # cascade ลบ course_plo / study_plan / course_offering / clo ที่อ้างถึงด้วย
    db.commit()
