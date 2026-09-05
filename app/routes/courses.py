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
    _student_passed_course_for_plo,
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
            "ถ้าส่งมา จะคำนวณ plo_achieved (ผ่าน/ไม่ผ่าน) ของนักศึกษาแต่ละคนในวิชานี้ เทียบกับ PLO ข้อนี้ "
            "เพิ่มมาในแต่ละ item ของ response ด้วย (ไม่ส่ง = plo_achieved เป็น null ทุกคน "
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

    plo_id (optional): คำนวณ plo_achieved (ผ่าน/ไม่ผ่านวิชานี้สำหรับ PLO ข้อนี้) แบบ batch เดียวให้
    นักศึกษาทั้ง roster (ไม่ query ทีละคน) reuse _student_passed_course_for_plo ตัวเดียวกับที่ตัดสิน
    "บรรลุ PLO" ทุกที่ในระบบ (all-or-nothing ต่อ CLO - ต้องผ่านทุก CLO ที่ผูกกับ PLO นี้ แต่ละ CLO เทียบ
    กับ pass_threshold_percent ของตัวเอง ไม่ใช่ derive จากค่าเฉลี่ย %) ไม่มี logic คำนวณแยกที่อาจ drift
    ไม่ตรงกัน

    plo_achieved เป็น null ใน 2 กรณี: (1) วิชานี้ไม่มี CLO ผูกกับ PLO นี้เลย หรือ (2) มี CLO ผูกอยู่ แต่
    นักศึกษาคนนี้ยังไม่มี "record" คะแนนบันทึกไว้เลยสักรายการสำหรับ CLO เหล่านั้น (ยังไม่มีข้อมูลให้
    ประเมิน ต่างจากได้คะแนน 0 จริงซึ่งนับเป็นข้อมูลแล้ว) - เทียบ course_clo_ids กับ key ที่มีอยู่จริงใน
    ผลลัพธ์ของ _clo_mastery_for_students_batch (ซึ่งมี key เฉพาะ CLO ที่มี StudentScore record จริง
    อย่างน้อย 1 แถวเท่านั้น ไม่ใช่ CLO ที่คำนวณได้ 0%) ถ้ามี record คะแนนอยู่แล้วอย่างน้อย 1 รายการใน
    CLO ที่เกี่ยวข้อง ถึงจะเรียก _student_passed_course_for_plo เพื่อได้ True/False จริง (ซึ่ง CLO ที่ยัง
    ไม่มี record ในกลุ่มนี้จะยังคงถูกนับเป็น "ไม่ผ่าน" ตาม all-or-nothing ตามปกติ)"""
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

    # offering_id ของแต่ละคน (ให้ frontend รู้ว่าจะเรียก /clo-achievement?offering_id=... ของ offering
    # ไหนต่อ) - roster query ด้านบนใช้ .distinct() บนคอลัมน์ Student ล้วนๆ เจตนา ไม่ต้องการให้นักศึกษา
    # คนเดียวโผล่ซ้ำถ้าลงทะเบียนวิชานี้มากกว่า 1 course_offering จึงต้อง query แยกต่างหากเพื่อ resolve
    # offering_id ต่อคน - เลือก enrollment ล่าสุด (Enrollment.id มากสุด) ถ้ามีมากกว่า 1 offering ต่อคน
    # (ยืนยันจากข้อมูลจริงแล้วว่าปัจจุบันไม่มีเคสนี้เลยสักคนในระบบ - ถ้าในอนาคตพบว่ามีการลงทะเบียนซ้ำ
    # offering ของวิชาเดียวกันจริง (เช่น ลงเรียนซ้ำคนละเทอมหลังตก) ต้องกลับมาทบทวนใหม่ว่า "ล่าสุด" ยังเป็น
    # คำตอบที่ถูกต้องเสมอไปหรือไม่ - อาจต้องให้ผู้ใช้เลือก offering เองแทน)
    offering_id_by_student: dict[str, int] = {}
    if students:
        enrollment_rows = (
            db.query(Enrollment.student_id, Enrollment.offering_id, Enrollment.id)
            .join(CourseOffering, CourseOffering.id == Enrollment.offering_id)
            .filter(
                CourseOffering.course_id == course_id,
                Enrollment.student_id.in_([s.id for s in students]),
            )
            .all()
        )
        latest_enrollment_id_by_student: dict[str, int] = {}
        for student_id, offering_id, enrollment_id in enrollment_rows:
            if enrollment_id > latest_enrollment_id_by_student.get(student_id, -1):
                latest_enrollment_id_by_student[student_id] = enrollment_id
                offering_id_by_student[student_id] = offering_id

    plo_achieved_by_student_id: dict[str, bool | None] = {}
    if plo_id is not None and students:
        plo_requirements, clo_pass_thresholds = _build_plo_requirements(db, course.curriculum_id)
        course_clo_ids = plo_requirements.get(plo_id, {}).get(course_id, set())
        if course_clo_ids:
            student_ids = [s.id for s in students]
            clo_mastery_by_student = _clo_mastery_for_students_batch(
                db, student_ids, course_id_filter={course_id}
            )
            for student_id in student_ids:
                student_mastery = clo_mastery_by_student.get(student_id, {})
                # key ปรากฏใน student_mastery เฉพาะ CLO ที่มี StudentScore record จริงอย่างน้อย 1 แถว
                # (ดู _clo_mastery_for_students_batch) - ไม่มี key ร่วมกับ course_clo_ids เลยสักตัว แปลว่า
                # ยังไม่มีคะแนนบันทึกให้ CLO ที่เกี่ยวข้องกับ PLO นี้เลยสักรายการ (ต่างจากได้ 0 จริง)
                has_any_recorded_score = bool(course_clo_ids & student_mastery.keys())
                plo_achieved_by_student_id[student_id] = (
                    _student_passed_course_for_plo(course_clo_ids, student_mastery, clo_pass_thresholds)
                    if has_any_recorded_score
                    else None
                )
        else:
            # วิชานี้ไม่มี CLO ผูกกับ PLO ข้อนี้เลย (ไม่ว่าเพราะไม่ใช่ primary หรือยังไม่มี CLO
            # เลยสักตัวในวิชานี้) - ไม่มีอะไรให้คำนวณ ไม่ใช่ error แค่ null ทุกคน
            plo_achieved_by_student_id = {s.id: None for s in students}

    return [
        EnrolledStudentSchema(
            **StudentSchema.model_validate(s).model_dump(),
            offering_id=offering_id_by_student[s.id],
            plo_achieved=plo_achieved_by_student_id.get(s.id) if plo_id is not None else None,
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
