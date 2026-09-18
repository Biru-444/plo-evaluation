"""
ทำอะไร : CRUD มาตรฐาน (list/get/create/delete — ไม่มี update เพราะ mapping มีแค่คู่ ylo_id/plo_id
         ดูเหตุผลใน app/schemas/ylo_plo_mapping.py) สำหรับตาราง ylo_plo_mapping

เชื่อมกับ : สร้าง/ลบคู่ mapping นี้มีผลโดยตรงต่อ _build_ylo_requirements ใน ylo_calculation.py — คู่ที่
            เพิ่ม/ลบจะเปลี่ยน "PLO กลุ่มที่ YLO ปีนี้ต้องพึ่งพา" ทันที กระทบ % บรรลุ YLO ทั้งรุ่น

ถ้าแก้ : เฉพาะ admin เท่านั้นที่สร้าง/ลบได้ (require_role("admin")) — list/get เปิดให้ทุก role ที่
         login แล้วดูได้
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_role
from app.database import get_db
from app.models import YLOPLOMapping, User
from app.schemas import YLOPLOMappingCreateSchema, YLOPLOMappingSchema

router = APIRouter(prefix="/ylo-plo-mapping", tags=["YLO-PLO Mapping"])


# คืนรายการ mapping ทั้งหมด กรองตาม ylo_id ได้ (ไม่ใส่ = ทุก YLO ทุกหลักสูตร)
@router.get("", response_model=list[YLOPLOMappingSchema])
def list_ylo_plo_mappings(
    ylo_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(YLOPLOMapping)
    if ylo_id is not None:
        query = query.filter(YLOPLOMapping.ylo_id == ylo_id)
    return query.order_by(YLOPLOMapping.id).all()


# คืน mapping รายตัวตาม id
@router.get("/{mapping_id}", response_model=YLOPLOMappingSchema)
def get_ylo_plo_mapping(
    mapping_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    mapping = db.get(YLOPLOMapping, mapping_id)
    if mapping is None:
        raise HTTPException(status_code=404, detail="YLO-PLO mapping not found")
    return mapping


# สร้างคู่ mapping ใหม่ (admin เท่านั้น) — 409 ถ้าซ้ำคู่เดิม หรืออ้าง ylo_id/plo_id ที่ไม่มีจริง
@router.post("", response_model=YLOPLOMappingSchema, status_code=201)
def create_ylo_plo_mapping(
    payload: YLOPLOMappingCreateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    mapping = YLOPLOMapping(**payload.model_dump())
    db.add(mapping)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Mapping already exists, or references an invalid YLO/PLO",
        ) from exc
    db.refresh(mapping)
    return mapping


# ลบคู่ mapping (admin เท่านั้น)
@router.delete("/{mapping_id}", status_code=204)
def delete_ylo_plo_mapping(
    mapping_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    mapping = db.get(YLOPLOMapping, mapping_id)
    if mapping is None:
        raise HTTPException(status_code=404, detail="YLO-PLO mapping not found")
    db.delete(mapping)
    db.commit()
