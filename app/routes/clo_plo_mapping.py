"""
ทำอะไร : CRUD (list/create/update(เฉพาะ weight_percent)/delete) สำหรับตาราง clo_plo_mapping — ผูก/ถอด
         CLO กับ PLO โดยตรงเป็นรายข้อ (many-to-many) ตาม มคอ.3 ของแต่ละวิชา ใช้เป็นหลักฐานคำนวณบรรลุ
         PLO ใน plo_calculation.py แทน course_plo - เพิ่ม GET /domain-check ให้แอดมินเช็คว่า CLO/PLO
         ที่กำลังจะผูกกัน domain/category ตรงกันไหม real-time ก่อนกดผูกจริง (Workstream 4 - ดู
         แผนการแก้ไขครั้งใหญ่-PLO-CLO.md)

         weight_percent (Workstream 3) : น้ำหนักของคู่นี้โดยเฉพาะ auto-fill เกลี่ยเท่ากันเสมอตอนผูก/
         ถอด (ดู _rebalance_clo_weights_evenly ด้านล่าง) - POST ไม่รับค่าจาก client เลย (ดู
         CLOPLOMappingCreateSchema) แก้เองทีหลังได้ผ่าน PUT (ไม่ trigger rebalance ของคู่อื่น - แก้
         เจาะจงค่าเดียวตามที่แอดมินตั้งใจ)

เชื่อมกับ : สิทธิ์เช็คผ่าน CLO.course_id -> CourseOffering.instructor_id แบบเดียวกับ create_clo/
            update_clo/delete_clo ใน app/routes/clo.py (admin แก้ได้ทุกวิชา, อาจารย์แก้ได้เฉพาะวิชาที่
            ตัวเองสอนอยู่จริงเท่านั้น) — ผูก/ถอด/แก้ mapping คือการแก้ไข CLO ของวิชานั้นทางอ้อม จึงใช้
            เกณฑ์เดียวกัน - /domain-check ใช้แค่ get_current_user เฉยๆ (ไม่เช็ค ownership) เพราะเป็นแค่
            การอ่าน/เทียบข้อมูล ไม่ได้แก้อะไร เรียก check_domain_category_mismatch จาก
            app/services/domain_category_check.py ตัวเดียวกับที่ app/routes/course_import.py เรียกใช้
            ตอนแกะ มคอ.3 (ไม่เขียนตรรกะเทียบซ้ำสองชุด)

            การ auto-fill/rebalance นี้เกิดขึ้น 3 ที่ในระบบ (ต้องเกลี่ยแบบเดียวกันทุกที่ - ดู
            แผนการแก้ไขครั้งใหญ่-PLO-CLO.md Workstream 3): (1) ที่นี่ (POST/DELETE ทีละคู่) (2)
            app/routes/clo.py::create_clo/update_clo (plo_ids แทนที่ทั้งชุดในคำขอเดียว - คำนวณตรงๆ ไม่
            เรียกฟังก์ชันนี้ เพราะรู้ชุดใหม่ทั้งหมดอยู่แล้วในคำขอเดียว ไม่ต้อง query ทีละคู่) (3) Phase 2
            ของ มคอ.3 import (frontend คำนวณเองฝั่ง client แล้วส่ง weight_percent มาตรงๆ ในคำขอเดียวกัน)

ถ้าแก้ : ต้อง include_router ในนี้ที่ app/main.py ด้วย ไม่งั้นเรียกไม่ได้เลย (404)
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import CLO, CLOPLOMapping, CourseOffering, PLO, User
from app.schemas import CLOPLOMappingCreateSchema, CLOPLOMappingSchema, CLOPLOMappingUpdateSchema
from app.schemas.clo_plo_mapping import DomainCategoryCheckResponse
from app.services.domain_category_check import check_domain_category_mismatch

router = APIRouter(prefix="/clo-plo-mapping", tags=["CLO-PLO Mapping"])

TWO_DECIMAL_PLACES = Decimal("0.01")


def _rebalance_clo_weights_evenly(db: Session, clo_id: int) -> None:
    """เกลี่ยน้ำหนักของทุกคู่ CLO-PLO ที่ CLO นี้มีอยู่ ณ ตอนนี้ให้เท่ากันหมด (100/จำนวนคู่) - เรียกหลัง
    insert/delete แถวเสร็จแล้วเสมอ (ต้อง query ใหม่ในทรานแซกชันเดียวกันถึงจะเห็นจำนวนคู่ล่าสุด) ไม่ทำ
    อะไรถ้า CLO นี้ไม่มีคู่เหลือเลย (หารด้วยศูนย์ไม่ได้ และไม่มีอะไรให้เกลี่ย)"""
    mappings = db.query(CLOPLOMapping).filter(CLOPLOMapping.clo_id == clo_id).all()
    if not mappings:
        return
    even_weight = (Decimal(100) / Decimal(len(mappings))).quantize(
        TWO_DECIMAL_PLACES, rounding=ROUND_HALF_UP
    )
    for mapping in mappings:
        mapping.weight_percent = even_weight


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


# เช็ค clo.domain vs plo.category ล้วนๆ (pure code-level, ไม่พึ่ง Gemini) - แอดมินเรียกตอนเลือกครบทั้ง
# CLO และ PLO ในฟอร์มผูก mapping ด้วยมือ (real-time, ก่อนกดผูกจริง) ไม่บล็อกอะไร แค่คืนข้อความเตือน
@router.get("/domain-check", response_model=DomainCategoryCheckResponse)
def check_clo_plo_domain_match(
    clo_id: int = Query(...),
    plo_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    clo = db.get(CLO, clo_id)
    if clo is None:
        raise HTTPException(status_code=404, detail="CLO not found")
    plo = db.get(PLO, plo_id)
    if plo is None:
        raise HTTPException(status_code=404, detail="PLO not found")

    message = check_domain_category_mismatch(clo.domain, plo.category)
    return DomainCategoryCheckResponse(mismatch=message is not None, message=message)


# ผูก CLO กับ PLO ใหม่ — instructor ทำได้เฉพาะ CLO ของวิชาที่ตัวเองสอนอยู่ (เช็คสิทธิ์ด้านล่าง) 409 ถ้า
# คู่ clo_id+plo_id นี้ผูกไว้อยู่แล้ว หรือ plo_id ไม่มีอยู่จริง - weight_percent เกลี่ยเท่ากันอัตโนมัติ
# ทุกคู่ของ CLO นี้ (รวมคู่ใหม่ด้วย) ไม่รับค่าจาก client (ดู CLOPLOMappingCreateSchema)
@router.post("", response_model=CLOPLOMappingSchema, status_code=201)
def create_clo_plo_mapping(
    payload: CLOPLOMappingCreateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_clo_ownership(db, payload.clo_id, current_user)
    # placeholder ชั่วคราว - _rebalance_clo_weights_evenly ด้านล่างจะเขียนทับค่าจริงให้ทุกคู่ (รวมแถวนี้)
    # ก่อน commit อยู่แล้ว ต้องใส่ค่าเริ่มต้นเพราะคอลัมน์ NOT NULL
    mapping = CLOPLOMapping(**payload.model_dump(), weight_percent=Decimal("100.00"))
    db.add(mapping)
    try:
        db.flush()  # ต้องมี mapping.id ก่อน rebalance query กลับมาเห็นแถวนี้ด้วย
        _rebalance_clo_weights_evenly(db, payload.clo_id)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Mapping already exists, or references an invalid PLO",
        ) from exc
    db.refresh(mapping)
    return mapping


# แก้ weight_percent ของคู่ที่มีอยู่แล้ว (ไม่แตะ clo_id/plo_id เลย - เปลี่ยนคู่ทำผ่าน DELETE+POST ใหม่)
# ไม่ trigger rebalance ของคู่อื่นๆ ของ CLO เดียวกัน - แก้เจาะจงค่าเดียวตามที่แอดมินตั้งใจพิมพ์เอง
@router.put("/{mapping_id}", response_model=CLOPLOMappingSchema)
def update_clo_plo_mapping(
    mapping_id: int,
    payload: CLOPLOMappingUpdateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    mapping = db.get(CLOPLOMapping, mapping_id)
    if mapping is None:
        raise HTTPException(status_code=404, detail="CLO-PLO mapping not found")
    _require_clo_ownership(db, mapping.clo_id, current_user)
    mapping.weight_percent = payload.weight_percent
    db.commit()
    db.refresh(mapping)
    return mapping


# ถอด mapping — instructor ทำได้เฉพาะ CLO ของวิชาที่ตัวเองสอนอยู่ (เช็คสิทธิ์ด้านล่าง) weight_percent
# ของคู่ที่เหลือของ CLO เดียวกันเกลี่ยใหม่เท่ากันอัตโนมัติหลังถอด
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
    clo_id = mapping.clo_id
    db.delete(mapping)
    db.flush()  # ต้องลบแถวออกจริงก่อน rebalance query ใหม่ ไม่งั้นจะยังนับแถวที่กำลังจะลบรวมด้วย
    _rebalance_clo_weights_evenly(db, clo_id)
    db.commit()
