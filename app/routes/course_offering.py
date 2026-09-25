"""
ทำอะไร : CRUD มาตรฐาน (list/get/create/update/delete) สำหรับตาราง course_offering (การเปิดสอนจริง)

เชื่อมกับ : create/update/delete เฉพาะ admin (ไม่เปลี่ยน) — GET list/get-by-id (2026-09 แก้) admin เห็น
            ทุก offering เหมือนเดิม, instructor เห็นเฉพาะ offering ที่ตัวเองสอน (ระบุ instructor_id เป็น
            คนอื่น -> 403, ไม่ระบุเลย -> กรองใน query เหลือเฉพาะของตัวเอง) - เดิมไม่เช็คเลย ใครก็ดูชื่อ
            ผู้สอน/วิชา/เทอมของทุก offering ในระบบได้
"""
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


# คืนรายการ offering ทั้งหมด กรองตาม course_id / instructor_id ได้ — instructor ระบุ instructor_id เป็น
# คนอื่นไม่ได้ (403) ไม่ระบุเลย = กรองในคิวรีเหลือเฉพาะ offering ของตัวเอง (ไม่ใช่ดึงมาทั้งหมดแล้วกรองทีหลัง)
@router.get("", response_model=list[CourseOfferingSchema])
def list_course_offerings(
    course_id: int | None = None,
    instructor_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        if instructor_id is not None and instructor_id != current_user.id:
            raise HTTPException(status_code=403, detail="คุณไม่ใช่ผู้สอนวิชานี้")
        instructor_id = current_user.id

    query = db.query(CourseOffering)
    if course_id is not None:
        query = query.filter(CourseOffering.course_id == course_id)
    if instructor_id is not None:
        query = query.filter(CourseOffering.instructor_id == instructor_id)
    return query.order_by(CourseOffering.id).all()


# คืน offering รายตัวตาม id — instructor ดูได้เฉพาะ offering ที่ตัวเองสอน (403 ถ้าเป็นคนอื่น)
@router.get("/{offering_id}", response_model=CourseOfferingSchema)
def get_course_offering(
    offering_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    offering = db.get(CourseOffering, offering_id)
    if offering is None:
        raise HTTPException(status_code=404, detail="Course offering not found")
    if current_user.role != "admin" and offering.instructor_id != current_user.id:
        raise HTTPException(status_code=403, detail="คุณไม่ใช่ผู้สอนวิชานี้")
    return offering


# สร้าง offering ใหม่ (admin เท่านั้น) — instructor_id ใส่หรือเว้นว่างไว้ก็ได้ (ดู model)
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


# แก้ไข offering (admin เท่านั้น) — รวมถึงมอบหมาย/เปลี่ยนผู้สอนโดยตรงได้
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


# ลบ offering (admin เท่านั้น)
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
