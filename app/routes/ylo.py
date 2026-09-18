"""
ทำอะไร : CRUD มาตรฐาน (list/get/create/update/delete) สำหรับตาราง ylo (เป้าหมายการเรียนรู้ระดับ
         ชั้นปี) — คนละไฟล์กับ app/routes/ylo_calculation.py ที่คำนวณ "% บรรลุ" (ไฟล์นี้จัดการแค่
         ข้อมูล YLO เอง ไม่คำนวณอะไร)

เชื่อมกับ : ลบ YLO ที่นี่จะ cascade ลบ ylo_plo_mapping ที่อ้างถึงไปด้วย (ดู app/models/ylo.py) กระทบ
            การคำนวณ YLO ปีนั้นทันที (ไม่มีวิชาบังคับให้ตัดสินอีกต่อไป)

ถ้าแก้ : เฉพาะ admin เท่านั้นที่แก้ได้ — list/get เปิดให้ทุก role ดูได้
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_role
from app.database import get_db
from app.models import YLO, User
from app.schemas import YLOCreateSchema, YLOSchema, YLOUpdateSchema

router = APIRouter(prefix="/ylo", tags=["YLO"])


# คืนรายการ YLO ทั้งหมด กรองตาม curriculum_id ได้
@router.get("", response_model=list[YLOSchema])
def list_ylo(
    curriculum_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(YLO)
    if curriculum_id is not None:
        query = query.filter(YLO.curriculum_id == curriculum_id)
    return query.order_by(YLO.id).all()


# คืน YLO รายตัวตาม id
@router.get("/{ylo_id}", response_model=YLOSchema)
def get_ylo(
    ylo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ylo = db.get(YLO, ylo_id)
    if ylo is None:
        raise HTTPException(status_code=404, detail="YLO not found")
    return ylo


# สร้าง YLO ใหม่ (admin เท่านั้น) — 409 ถ้า year_level ซ้ำในหลักสูตรเดียวกัน
@router.post("", response_model=YLOSchema, status_code=201)
def create_ylo(
    payload: YLOCreateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    ylo = YLO(**payload.model_dump())
    db.add(ylo)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="YLO could not be created (duplicate year_level in this curriculum?)",
        ) from exc
    db.refresh(ylo)
    return ylo


# แก้ไข YLO (admin เท่านั้น)
@router.put("/{ylo_id}", response_model=YLOSchema)
def update_ylo(
    ylo_id: int,
    payload: YLOUpdateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    ylo = db.get(YLO, ylo_id)
    if ylo is None:
        raise HTTPException(status_code=404, detail="YLO not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(ylo, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="YLO could not be updated (duplicate year_level in this curriculum?)",
        ) from exc
    db.refresh(ylo)
    return ylo


# ลบ YLO (admin เท่านั้น)
@router.delete("/{ylo_id}", status_code=204)
def delete_ylo(
    ylo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    ylo = db.get(YLO, ylo_id)
    if ylo is None:
        raise HTTPException(status_code=404, detail="YLO not found")
    db.delete(ylo)  # cascade ลบ ylo_plo_mapping ที่อ้างถึงด้วย
    db.commit()
