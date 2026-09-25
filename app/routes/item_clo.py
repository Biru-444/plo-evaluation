"""
ทำอะไร : CRUD สำหรับตาราง item_clo (ผูกชิ้นงานเข้ากับ CLO พร้อมน้ำหนัก) — บังคับกฎ "น้ำหนักรวมของ CLO
         หนึ่งข้อ ต้องไม่เกิน 100%" ในชั้น route (ไม่ใช่ constraint ระดับฐานข้อมูล) ทุกครั้งที่สร้าง/แก้

เชื่อมกับ : weight_percent ที่ผูกไว้ที่นี่คือสิ่งที่ _clo_mastery_for_student ใน plo_calculation.py
            ใช้ถ่วงน้ำหนักคำนวณ mastery ของ CLO — instructor ดู/แก้ได้เฉพาะ mapping ของวิชาที่ตัวเองสอนอยู่
            เท่านั้น ทุก endpoint รวม GET list/get-by-id ด้วย (แก้ 2026-09 หลังพบว่าเดิม GET ไม่เช็คเลย)

ถ้าแก้ : ถ้าลบการเช็ค 100% ออก น้ำหนักรวมเกิน 100% ได้ ซึ่งจะทำให้สูตรถ่วงน้ำหนัก mastery
         (weighted_sum / weight_total) ให้ผลลัพธ์ผิดเพี้ยนไปจากที่ตั้งใจ (ค่าเฉลี่ยถ่วงน้ำหนักยังคง
         คำนวณได้ แต่ตัวเลขจะไม่สื่อความหมาย "% ของวิชา" ตามที่อาจารย์เข้าใจอีกต่อไป)
"""
from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import AssessmentItem, CourseOffering, ItemCLO, User
from app.schemas import ItemCLOCreateSchema, ItemCLOSchema, ItemCLOUpdateSchema

router = APIRouter(prefix="/item-clo", tags=["Item-CLO Mapping"])


def _other_mappings_weight_sum(db: Session, clo_id: int, exclude_item_clo_id: int | None = None) -> Decimal:
    """
    ทำอะไร : รวมน้ำหนัก (weight_percent) ของทุกชิ้นงานที่ผูกกับ CLO นี้ไว้แล้ว (ไม่รวมแถวที่กำลังจะแก้ ถ้า
             ระบุ exclude_item_clo_id) ใช้เช็คว่าจะเพิ่ม/แก้น้ำหนักใหม่แล้วเกิน 100% หรือไม่

    เชื่อมกับ : เรียกจาก create_item_clo และ update_item_clo ก่อนบันทึกทุกครั้ง

    ถ้าแก้ : ถ้า exclude_item_clo_id เป็น None (ตอนสร้างใหม่) จะรวมทุกแถวที่มีอยู่แล้ว ถ้าระบุ (ตอนแก้ไข)
             จะไม่รวมแถวตัวเอง ป้องกันนับน้ำหนักตัวเองซ้ำสองครั้ง
    """
    query = db.query(func.coalesce(func.sum(ItemCLO.weight_percent), 0)).filter(ItemCLO.clo_id == clo_id)
    if exclude_item_clo_id is not None:
        query = query.filter(ItemCLO.id != exclude_item_clo_id)
    return query.scalar()


# คืนรายการ mapping ทั้งหมด กรองตาม item_id ได้ — สิทธิ์เหมือน create/update/delete ในไฟล์นี้ (admin
# ผ่านหมด, instructor เฉพาะ offering ตัวเอง) - ระบุ item_id ของชิ้นงานวิชาอื่น -> 403, ไม่ระบุเลย ->
# กรองใน query เหลือเฉพาะ mapping ของ offering ตัวเอง (ไม่ใช่กรองหลังดึงมาทั้งหมด)
@router.get("", response_model=list[ItemCLOSchema])
def list_item_clo(
    item_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if item_id is not None:
        item = db.get(AssessmentItem, item_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Assessment item not found")
        if current_user.role != "admin" and item.offering.instructor_id != current_user.id:
            raise HTTPException(status_code=403, detail="คุณไม่ใช่ผู้สอนวิชานี้")

    query = db.query(ItemCLO)
    if item_id is not None:
        query = query.filter(ItemCLO.item_id == item_id)
    elif current_user.role != "admin":
        query = (
            query.join(AssessmentItem, AssessmentItem.id == ItemCLO.item_id)
            .join(CourseOffering, CourseOffering.id == AssessmentItem.offering_id)
            .filter(CourseOffering.instructor_id == current_user.id)
        )
    return query.order_by(ItemCLO.id).all()


# คืน mapping รายตัวตาม id — สิทธิ์เหมือน list_item_clo(item_id=...) (403 ถ้าเป็นอาจารย์คนอื่น)
@router.get("/{item_clo_id}", response_model=ItemCLOSchema)
def get_item_clo(
    item_clo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item_clo = db.get(ItemCLO, item_clo_id)
    if item_clo is None:
        raise HTTPException(status_code=404, detail="Item-CLO mapping not found")
    if current_user.role != "admin" and item_clo.item.offering.instructor_id != current_user.id:
        raise HTTPException(status_code=403, detail="คุณไม่ใช่ผู้สอนวิชานี้")
    return item_clo


# สร้าง mapping ใหม่ — เช็คสิทธิ์ความเป็นเจ้าของวิชา + เช็คว่าน้ำหนักรวมของ CLO นี้จะไม่เกิน 100%
@router.post("", response_model=ItemCLOSchema, status_code=201)
def create_item_clo(
    payload: ItemCLOCreateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        item = db.get(AssessmentItem, payload.item_id)
        offering = db.get(CourseOffering, item.offering_id) if item else None
        if offering is None or offering.instructor_id != current_user.id:
            raise HTTPException(status_code=403, detail="คุณไม่ใช่ผู้สอนวิชานี้")

    existing_total = _other_mappings_weight_sum(db, payload.clo_id)
    new_total = existing_total + payload.weight_percent
    if new_total > 100:
        raise HTTPException(
            status_code=400,
            detail=(
                f"น้ำหนักรวมของ CLO นี้จะเกิน 100% "
                f"(มีอยู่แล้ว {existing_total}% + ที่จะเพิ่ม {payload.weight_percent}% = {new_total}%)"
            ),
        )

    item_clo = ItemCLO(**payload.model_dump())
    db.add(item_clo)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Mapping already exists, or references an invalid item/CLO",
        ) from exc
    db.refresh(item_clo)
    return item_clo


# แก้ไข mapping (ปกติแก้แค่ weight_percent) — เช็คน้ำหนักรวมไม่เกิน 100% ซ้ำเช่นเดียวกับตอนสร้าง
@router.put("/{item_clo_id}", response_model=ItemCLOSchema)
def update_item_clo(
    item_clo_id: int,
    payload: ItemCLOUpdateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item_clo = db.get(ItemCLO, item_clo_id)
    if item_clo is None:
        raise HTTPException(status_code=404, detail="Item-CLO mapping not found")
    if current_user.role != "admin":
        if item_clo.item.offering.instructor_id != current_user.id:
            raise HTTPException(status_code=403, detail="คุณไม่ใช่ผู้สอนวิชานี้")

    updates = payload.model_dump(exclude_unset=True)
    if updates.get("weight_percent") is not None:
        existing_total = _other_mappings_weight_sum(db, item_clo.clo_id, exclude_item_clo_id=item_clo.id)
        new_total = existing_total + updates["weight_percent"]
        if new_total > 100:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"น้ำหนักรวมของ CLO นี้จะเกิน 100% "
                    f"(มีอยู่แล้ว {existing_total}% + ค่าใหม่ {updates['weight_percent']}% = {new_total}%)"
                ),
            )
    for field, value in updates.items():
        setattr(item_clo, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="Item-CLO mapping could not be updated"
        ) from exc
    db.refresh(item_clo)
    return item_clo


# ลบ mapping — เช็คสิทธิ์ความเป็นเจ้าของวิชาเช่นเดียวกับ create/update
@router.delete("/{item_clo_id}", status_code=204)
def delete_item_clo(
    item_clo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item_clo = db.get(ItemCLO, item_clo_id)
    if item_clo is None:
        raise HTTPException(status_code=404, detail="Item-CLO mapping not found")
    if current_user.role != "admin":
        if item_clo.item.offering.instructor_id != current_user.id:
            raise HTTPException(status_code=403, detail="คุณไม่ใช่ผู้สอนวิชานี้")
    db.delete(item_clo)
    db.commit()
