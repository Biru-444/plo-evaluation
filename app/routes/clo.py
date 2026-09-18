"""
ทำอะไร : CRUD มาตรฐาน (list/get/create/update/delete) สำหรับตาราง clo — คนละไฟล์กับ
         app/routes/clo_calculation.py ที่คำนวณ "% บรรลุ" (ไฟล์นี้จัดการแค่ข้อมูล CLO เอง)

เชื่อมกับ : create/update/delete เช็คสิทธิ์ความเป็นเจ้าของวิชาซ้ำ 3 จุด (create/update/delete) —
            admin แก้ CLO วิชาไหนก็ได้ แต่ instructor แก้ได้เฉพาะ CLO ของวิชาที่ตัวเองเป็นผู้สอนอยู่
            จริงเท่านั้น (เช็คผ่าน course_offering.instructor_id) — created_by ถูกเซ็ตจาก
            current_user.id เสมอ ไม่รับค่าจาก client (ดู CLOCreateSchema)

ถ้าแก้ : เกณฑ์ผ่าน (pass_threshold_percent) ที่แก้ผ่าน update_clo กระทบการตัดสิน CLO ผ่าน/ไม่ผ่าน
         ย้อนหลังทั้งหมดทันที (ดู app/models/clo.py)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import CLO, CourseOffering, User
from app.schemas import CLOCreateSchema, CLOSchema, CLOUpdateSchema

router = APIRouter(prefix="/clo", tags=["CLO"])


# คืนรายการ CLO ทั้งหมด กรองตาม course_id ได้
@router.get("", response_model=list[CLOSchema])
def list_clo(
    course_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(CLO)
    if course_id is not None:
        query = query.filter(CLO.course_id == course_id)
    return query.order_by(CLO.id).all()


# คืน CLO รายตัวตาม id
@router.get("/{clo_id}", response_model=CLOSchema)
def get_clo(
    clo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    clo = db.get(CLO, clo_id)
    if clo is None:
        raise HTTPException(status_code=404, detail="CLO not found")
    return clo


# สร้าง CLO ใหม่ — instructor สร้างได้เฉพาะในวิชาที่ตัวเองสอนอยู่ (เช็คสิทธิ์ด้านล่าง) created_by
# เซ็ตจากผู้ใช้ที่ login อยู่เสมอ 409 ถ้ารหัส (code) ซ้ำในวิชาเดียวกัน
@router.post("", response_model=CLOSchema, status_code=201)
def create_clo(
    payload: CLOCreateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        owns_course = (
            db.query(CourseOffering)
            .filter(
                CourseOffering.course_id == payload.course_id,
                CourseOffering.instructor_id == current_user.id,
            )
            .first()
        )
        if owns_course is None:
            raise HTTPException(status_code=403, detail="คุณไม่ใช่ผู้สอนวิชานี้")

    clo = CLO(**payload.model_dump(), created_by=current_user.id)
    db.add(clo)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="CLO could not be created (duplicate code in this course?)",
        ) from exc
    db.refresh(clo)
    return clo


# แก้ไข CLO — instructor แก้ได้เฉพาะ CLO ของวิชาที่ตัวเองสอนอยู่ (เช็คสิทธิ์ด้านล่าง)
@router.put("/{clo_id}", response_model=CLOSchema)
def update_clo(
    clo_id: int,
    payload: CLOUpdateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    clo = db.get(CLO, clo_id)
    if clo is None:
        raise HTTPException(status_code=404, detail="CLO not found")
    if current_user.role != "admin":
        owns_course = (
            db.query(CourseOffering)
            .filter(
                CourseOffering.course_id == clo.course_id,
                CourseOffering.instructor_id == current_user.id,
            )
            .first()
        )
        if owns_course is None:
            raise HTTPException(status_code=403, detail="คุณไม่ใช่ผู้สอนวิชานี้")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(clo, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="CLO could not be updated") from exc
    db.refresh(clo)
    return clo


# ลบ CLO — instructor ลบได้เฉพาะ CLO ของวิชาที่ตัวเองสอนอยู่ (เช็คสิทธิ์ด้านล่าง)
@router.delete("/{clo_id}", status_code=204)
def delete_clo(
    clo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    clo = db.get(CLO, clo_id)
    if clo is None:
        raise HTTPException(status_code=404, detail="CLO not found")
    if current_user.role != "admin":
        owns_course = (
            db.query(CourseOffering)
            .filter(
                CourseOffering.course_id == clo.course_id,
                CourseOffering.instructor_id == current_user.id,
            )
            .first()
        )
        if owns_course is None:
            raise HTTPException(status_code=403, detail="คุณไม่ใช่ผู้สอนวิชานี้")
    db.delete(clo)  # cascade ลบ item_clo ที่อ้างถึงด้วย
    db.commit()
