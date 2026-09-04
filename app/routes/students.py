"""API routes for Student"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_role
from app.database import get_db
from app.models import Course, CourseOffering, Enrollment, Student, StudyPlan, User
from app.schemas import (
    RecommendedOfferingSchema,
    StudentCreateSchema,
    StudentSchema,
    StudentUpdateSchema,
)

router = APIRouter(prefix="/students", tags=["Students"])

# ปีการศึกษาที่ตรงกับ study_plan.year_level ของนักศึกษารุ่น cohort_year คำนวณจากสูตรนี้ - ยืนยันจาก
# ข้อมูลจริงตอนทำ scripts/backfill_enrollment_from_study_plan.py (ดูสคริปต์นั้นสำหรับที่มา)
_ACADEMIC_YEAR_BASE = 2500


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


@router.get("/{student_id}/recommended-offerings", response_model=list[RecommendedOfferingSchema])
def get_recommended_offerings(
    student_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """วิชาที่ study_plan แนะนำสำหรับนักศึกษาคนนี้ (year_level <= current_year_level) ที่มี
    course_offering จริงรองรับแล้วแต่ยังไม่ได้ลงทะเบียน - ใช้ประกอบหน้าลงทะเบียนด้วยตนเอง เป็นแค่
    "คำแนะนำ" ให้กดเลือกทีละวิชา ไม่ auto-enroll เอง (ต่างจาก scripts/backfill_enrollment_from_study_plan.py
    ที่ auto-insert ตรงๆ - endpoint นี้แค่ list ตัวเลือกให้แอดมินตัดสินใจเอง) วิชาที่มีหลาย section
    ตรงกัน (course_id, academic_year, semester เดียวกัน) จะโชว์ทุก section ให้เลือกเอง ต่างจากสคริปต์
    backfill ที่ต้องข้ามเพราะเลือกเองไม่ได้ (ที่นี่มีแอดมินเป็นคนตัดสินใจ ไม่ใช่ auto-insert)"""
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")

    plan_rows = (
        db.query(StudyPlan, Course)
        .join(Course, Course.id == StudyPlan.course_id)
        .filter(
            StudyPlan.curriculum_id == student.curriculum_id,
            StudyPlan.cohort_year.is_(None),
            StudyPlan.year_level <= student.current_year_level,
        )
        .all()
    )
    if not plan_rows:
        return []

    already_enrolled_course_ids = {
        row[0]
        for row in db.query(CourseOffering.course_id)
        .join(Enrollment, Enrollment.offering_id == CourseOffering.id)
        .filter(Enrollment.student_id == student_id)
        .all()
    }

    recommendations: list[RecommendedOfferingSchema] = []
    for plan, course in plan_rows:
        if plan.course_id in already_enrolled_course_ids:
            continue
        academic_year = _ACADEMIC_YEAR_BASE + student.cohort_year + (plan.year_level - 1)
        offerings = (
            db.query(CourseOffering)
            .filter(
                CourseOffering.course_id == plan.course_id,
                CourseOffering.academic_year == academic_year,
                CourseOffering.semester == plan.semester,
            )
            .all()
        )
        for offering in offerings:
            recommendations.append(
                RecommendedOfferingSchema(
                    offering_id=offering.id,
                    course_id=course.id,
                    course_code=course.course_code,
                    name_th=course.name_th,
                    academic_year=offering.academic_year,
                    semester=offering.semester,
                    section=offering.section,
                    year_level=plan.year_level,
                )
            )

    recommendations.sort(key=lambda r: (r.year_level, r.course_code, r.section))
    return recommendations


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
