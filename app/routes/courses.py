"""API routes for Course"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_role
from app.database import get_db
from app.models import Course, CourseOffering, Enrollment, PLO, Student, User
from app.schemas import (
    CourseCreateSchema,
    CourseSchema,
    CourseUpdateSchema,
    EnrolledStudentSchema,
    StudentSchema,
)
from app.routes.plo_calculation import (
    _build_plo_requirements,
    _clo_mastery_for_students_batch,
    _course_plo_mastery_percent,
)

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


@router.get("/{course_id}/enrolled-students", response_model=list[EnrolledStudentSchema])
def get_course_enrolled_students(
    course_id: int,
    cohort_year: int | None = Query(
        None, description="กรองเฉพาะนักศึกษารุ่นนี้ (Student.cohort_year) - ไม่ใส่ = ทุกรุ่น"
    ),
    plo_id: int | None = Query(
        None,
        description=(
            "ถ้าส่งมา จะคำนวณ clo_mastery_percent ของนักศึกษาแต่ละคนในวิชานี้ เทียบกับ PLO ข้อนี้ "
            "เพิ่มมาในแต่ละ item ของ response ด้วย (ไม่ส่ง = clo_mastery_percent เป็น null ทุกคน "
            "พฤติกรรมเดิมทุกประการ ไม่กระทบ caller เดิม)"
        ),
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """นักศึกษาที่ลงทะเบียนวิชานี้จริง (ผ่าน enrollment -> course_offering ที่ course_id นี้) - คนละ
    เรื่องกับ "ใครบรรลุ PLO". กรองด้วย Student.cohort_year (รุ่นที่เข้าเรียนจริงของนักศึกษา) ให้ตรงกับ
    semantics เดียวกับที่หน้า PLO ตามชั้นปี/ภาพรวม PLO ใช้กรองอยู่แล้ว (ดู plo_calculation.py) - ไม่ใช้
    CourseOffering.cohort_year เพราะเป็นคนละแนวคิด (รุ่นที่ไฟล์ roster ระบุตอน import ไม่ใช่ตัวตัดสินว่า
    นักศึกษาคนนั้นเข้าเรียนรุ่นไหนจริง) ไม่ต้องกรองด้วย curriculum_id เพิ่ม เพราะ course_id หนึ่งอยู่ได้
    แค่หลักสูตรเดียวอยู่แล้ว (Course.curriculum_id)

    plo_id (optional): คำนวณ clo_mastery_percent แบบ batch เดียวให้นักศึกษาทั้ง roster (ไม่ query
    ทีละคน) reuse ตรรกะเดียวกับที่ตัดสิน "% บรรลุ PLO" ทุกที่ (_build_plo_requirements,
    _clo_mastery_for_students_batch, _course_plo_mastery_percent จาก plo_calculation.py) ไม่มี logic
    คำนวณแยกที่อาจ drift ไม่ตรงกัน"""
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")

    if plo_id is not None:
        plo = db.get(PLO, plo_id)
        if plo is None:
            raise HTTPException(status_code=404, detail="PLO not found")

    query = (
        db.query(Student)
        .join(Enrollment, Enrollment.student_id == Student.id)
        .join(CourseOffering, CourseOffering.id == Enrollment.offering_id)
        .filter(CourseOffering.course_id == course_id)
        .distinct()
    )
    if cohort_year is not None:
        query = query.filter(Student.cohort_year == cohort_year)

    students = query.order_by(Student.first_name, Student.last_name).all()

    mastery_percent_by_student_id: dict[str, float | None] = {}
    if plo_id is not None and students:
        plo_requirements, _ = _build_plo_requirements(db, course.curriculum_id)
        course_clo_ids = plo_requirements.get(plo_id, {}).get(course_id, set())
        if course_clo_ids:
            student_ids = [s.id for s in students]
            clo_mastery_by_student = _clo_mastery_for_students_batch(
                db, student_ids, course_id_filter={course_id}
            )
            for student_id in student_ids:
                percent = _course_plo_mastery_percent(
                    clo_mastery_by_student.get(student_id, {}), course_clo_ids
                )
                mastery_percent_by_student_id[student_id] = float(percent) if percent is not None else None
        else:
            # วิชานี้ไม่มี CLO ผูกกับ PLO ข้อนี้เลย (ไม่ว่าเพราะไม่ใช่ primary หรือยังไม่มี
            # clo_plo_mapping จริง) - ไม่มีอะไรให้คำนวณ ไม่ใช่ error แค่ null ทุกคน
            mastery_percent_by_student_id = {s.id: None for s in students}

    return [
        EnrolledStudentSchema(
            **StudentSchema.model_validate(s).model_dump(),
            clo_mastery_percent=mastery_percent_by_student_id.get(s.id) if plo_id is not None else None,
        )
        for s in students
    ]


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
