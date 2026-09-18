"""
ทำอะไร : CRUD มาตรฐาน (list/get/create/update/delete) สำหรับตาราง course_offering (การเปิดสอนจริง)
         บวก endpoint จับจองวิชาสำหรับอาจารย์ (claim)

เชื่อมกับ : list_course_offerings รับ filter unassigned=True เพื่อหาวิชาที่ยังไม่มีผู้สอน (ใช้ในหน้า
            ให้อาจารย์เลือกจับจอง) — claim ใช้ atomic UPDATE กันปัญหาสองคนจับจองพร้อมกัน (ดู
            docstring ของ claim_course_offering ด้านล่าง)

ถ้าแก้ : create/update/delete เฉพาะ admin — claim เปิดให้ instructor ทำเองได้ (ไม่ต้อง admin)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import update
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


# คืนรายการ offering ทั้งหมด กรองตาม course_id / instructor_id / unassigned (ยังไม่มีผู้สอน) ได้
@router.get("", response_model=list[CourseOfferingSchema])
def list_course_offerings(
    course_id: int | None = None,
    instructor_id: int | None = None,
    unassigned: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(CourseOffering)
    if course_id is not None:
        query = query.filter(CourseOffering.course_id == course_id)
    if instructor_id is not None:
        query = query.filter(CourseOffering.instructor_id == instructor_id)
    if unassigned:
        query = query.filter(CourseOffering.instructor_id.is_(None))
    return query.order_by(CourseOffering.id).all()


# คืน offering รายตัวตาม id
@router.get("/{offering_id}", response_model=CourseOfferingSchema)
def get_course_offering(
    offering_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    offering = db.get(CourseOffering, offering_id)
    if offering is None:
        raise HTTPException(status_code=404, detail="Course offering not found")
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


# แก้ไข offering (admin เท่านั้น) — รวมถึงมอบหมาย/เปลี่ยนผู้สอนโดยตรงได้ (ไม่ต้องผ่าน claim/release)
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


@router.post("/{offering_id}/claim", response_model=CourseOfferingSchema)
def claim_course_offering(
    offering_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """ให้อาจารย์ "จับจอง" วิชาที่เปิดสอนแต่ยังไม่มีผู้สอน (instructor_id เป็น NULL) เอาตัวเองเป็น
    ผู้สอน - ใช้ atomic UPDATE ... WHERE instructor_id IS NULL แทนการ SELECT แล้วเช็คเองใน Python
    เพื่อกันเคสสองคนกดจับจองวิชาเดียวกันพร้อมกัน (race condition): ถ้ามีคนอื่นจับจองไปก่อนแล้วแม้แค่
    เสี้ยววินาที คำสั่ง UPDATE นี้จะไม่แมตช์แถวไหนเลย (เพราะ instructor_id ไม่ใช่ NULL อีกต่อไป) และ
    เราจะรู้ได้จาก returning ว่าไม่มีอะไรถูกอัปเดต"""
    if current_user.role == "admin":
        raise HTTPException(
            status_code=400,
            detail="แอดมินมอบหมายผู้สอนได้โดยตรงที่หน้าจัดการระบบ ไม่ต้องใช้การจับจอง",
        )

    stmt = (
        update(CourseOffering)
        .where(CourseOffering.id == offering_id, CourseOffering.instructor_id.is_(None))
        .values(instructor_id=current_user.id)
    )
    result = db.execute(stmt)

    if result.rowcount == 0:
        existing = db.get(CourseOffering, offering_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="ไม่พบวิชาที่เปิดสอนนี้")
        raise HTTPException(
            status_code=409,
            detail="วิชานี้มีอาจารย์ท่านอื่นจับจองไปแล้ว ลองรีเฟรชแล้วเลือกวิชาอื่น",
        )

    db.commit()
    offering = db.get(CourseOffering, offering_id)
    return offering
