"""
ทำอะไร : CRUD (list/create/delete — ไม่มี update เพราะเป็น pure join table ไม่มี field ให้แก้) สำหรับ
         ตาราง clo_plo_mapping — ผูก/ถอด CLO กับ PLO โดยตรงเป็นรายข้อ (many-to-many) ตาม มคอ.3 ของ
         แต่ละวิชา ใช้เป็นหลักฐานคำนวณบรรลุ PLO ใน plo_calculation.py แทน course_plo

เชื่อมกับ : สิทธิ์เช็คผ่าน CLO.course_id -> CourseOffering.instructor_id แบบเดียวกับ create_clo/
            update_clo/delete_clo ใน app/routes/clo.py (admin แก้ได้ทุกวิชา, อาจารย์แก้ได้เฉพาะวิชาที่
            ตัวเองสอนอยู่จริงเท่านั้น) — ผูก/ถอด mapping คือการแก้ไข CLO ของวิชานั้นทางอ้อม จึงใช้เกณฑ์
            เดียวกัน

ถ้าแก้ : ต้อง include_router ในนี้ที่ app/main.py ด้วย ไม่งั้นเรียกไม่ได้เลย (404)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import CLO, CLOPLOMapping, CourseOffering, User
from app.schemas import CLOPLOMappingCreateSchema, CLOPLOMappingSchema

router = APIRouter(prefix="/clo-plo-mapping", tags=["CLO-PLO Mapping"])


def _require_clo_ownership(db: Session, clo_id: int, current_user: User) -> CLO:
    """เหมือน ownership check ใน clo.py - admin ผ่านได้เสมอ, อาจารย์ต้องเป็นคนสอนวิชาที่ CLO นี้
    สังกัดอยู่เท่านั้น"""
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
    return clo


# คืนรายการ mapping ทั้งหมด กรองตาม clo_id และ/หรือ plo_id ได้
@router.get("", response_model=list[CLOPLOMappingSchema])
def list_clo_plo_mappings(
    clo_id: int | None = None,
    plo_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(CLOPLOMapping)
    if clo_id is not None:
        query = query.filter(CLOPLOMapping.clo_id == clo_id)
    if plo_id is not None:
        query = query.filter(CLOPLOMapping.plo_id == plo_id)
    return query.order_by(CLOPLOMapping.id).all()


# ผูก CLO กับ PLO ใหม่ — instructor ทำได้เฉพาะ CLO ของวิชาที่ตัวเองสอนอยู่ (เช็คสิทธิ์ด้านล่าง) 409 ถ้า
# คู่ clo_id+plo_id นี้ผูกไว้อยู่แล้ว หรือ plo_id ไม่มีอยู่จริง
@router.post("", response_model=CLOPLOMappingSchema, status_code=201)
def create_clo_plo_mapping(
    payload: CLOPLOMappingCreateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_clo_ownership(db, payload.clo_id, current_user)
    mapping = CLOPLOMapping(**payload.model_dump())
    db.add(mapping)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Mapping already exists, or references an invalid PLO",
        ) from exc
    db.refresh(mapping)
    return mapping


# ถอด mapping — instructor ทำได้เฉพาะ CLO ของวิชาที่ตัวเองสอนอยู่ (เช็คสิทธิ์ด้านล่าง)
@router.delete("/{mapping_id}", status_code=204)
def delete_clo_plo_mapping(
    mapping_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    mapping = db.get(CLOPLOMapping, mapping_id)
    if mapping is None:
        raise HTTPException(status_code=404, detail="CLO-PLO mapping not found")
    _require_clo_ownership(db, mapping.clo_id, current_user)
    db.delete(mapping)
    db.commit()
