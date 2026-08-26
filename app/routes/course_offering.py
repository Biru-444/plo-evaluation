"""API routes for CourseOffering"""
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


@router.post("/{offering_id}/release", response_model=CourseOfferingSchema)
def release_course_offering(
    offering_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """ให้อาจารย์ปล่อยคืนวิชาที่ตัวเองจับจองไว้ (กลับไปเป็น instructor_id = NULL ให้คนอื่นจับจองต่อได้)
    แอดมินก็ปล่อยคืนแทนใครก็ได้เหมือนกัน (เผื่อกรณีอาจารย์ลาออก/ย้ายวิชา)"""
    offering = db.get(CourseOffering, offering_id)
    if offering is None:
        raise HTTPException(status_code=404, detail="ไม่พบวิชาที่เปิดสอนนี้")
    if current_user.role != "admin" and offering.instructor_id != current_user.id:
        raise HTTPException(status_code=403, detail="คุณไม่ใช่ผู้สอนวิชานี้ ปล่อยคืนไม่ได้")
    offering.instructor_id = None
    db.commit()
    db.refresh(offering)
    return offering
