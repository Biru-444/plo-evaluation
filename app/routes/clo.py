"""
ทำอะไร : CRUD มาตรฐาน (list/get/create/update/delete) สำหรับตาราง clo — คนละไฟล์กับ
         app/routes/clo_calculation.py ที่คำนวณ "% บรรลุ" (ไฟล์นี้จัดการแค่ข้อมูล CLO เอง)

เชื่อมกับ : create/update/delete เช็คสิทธิ์ความเป็นเจ้าของวิชาซ้ำ 3 จุด (create/update/delete) —
            admin แก้ CLO วิชาไหนก็ได้ แต่ instructor แก้ได้เฉพาะ CLO ของวิชาที่ตัวเองเป็นผู้สอนอยู่
            จริงเท่านั้น (เช็คผ่าน course_offering.instructor_id) — created_by ถูกเซ็ตจาก
            current_user.id เสมอ ไม่รับค่าจาก client (ดู CLOCreateSchema) — create/update รับ plo_ids
            เสริมได้เพื่อผูก/แทนที่ mapping ใน clo_plo_mapping ในคำขอเดียวกัน (ดู CLOCreateSchema/
            CLOUpdateSchema) ไม่ผูกก็ยังทำได้ปกติผ่าน POST /clo-plo-mapping แยกทีหลัง - weight_percent
            ของทุกคู่ที่สร้างผ่าน plo_ids เกลี่ยเท่ากันเสมอ (100/len(plo_ids)) เหมือนกับที่
            POST /clo-plo-mapping ทำ (Workstream 3) - คำนวณตรงๆ ที่นี่แทนเรียก
            _rebalance_clo_weights_evenly เพราะรู้ชุด PLO ทั้งหมดอยู่แล้วในคำขอเดียว ไม่ต้อง query ซ้ำ -
            plo_ids แต่ละตัวต้องอยู่หลักสูตรเดียวกับ CLO นี้ด้วย (422 ถ้าไม่ตรง - ดู
            app/services/curriculum_match_check.py)

ถ้าแก้ : เกณฑ์ผ่าน (pass_threshold_percent) ที่แก้ผ่าน update_clo กระทบการตัดสิน CLO ผ่าน/ไม่ผ่าน
         ย้อนหลังทั้งหมดทันที (ดู app/models/clo.py)

         delete_clo (2026-09-28) บล็อกด้วย 409 ถ้า CLO ผูกกับ item_clo หรือ clo_plo_mapping อยู่ - ทุก
         role รวมแอดมินด้วย (เดิม cascade ลบเงียบๆ ไม่เตือน) - ไม่กระทบการลบ Course ทั้งวิชา (ที่ cascade
         ลบ CLO ไปด้วยผ่าน DB/ORM ตรงๆ ใน app/routes/courses.py ไม่ผ่านฟังก์ชันนี้เลย) หรือสคริปต์
         seed/reset ที่ลบด้วย raw SQL ตรงๆ (ไม่ผ่าน API เลยเช่นกัน) - ทั้งสองจุดนี้ยังคงพฤติกรรมเดิม
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import CLO, CLOPLOMapping, CourseOffering, ItemCLO, PLO, User
from app.schemas import CLOCreateSchema, CLOSchema, CLOUpdateSchema
from app.services.curriculum_match_check import require_same_curriculum

router = APIRouter(prefix="/clo", tags=["CLO"])

TWO_DECIMAL_PLACES = Decimal("0.01")


def _even_weight_for(count: int) -> Decimal:
    return (Decimal(100) / Decimal(count)).quantize(TWO_DECIMAL_PLACES, rounding=ROUND_HALF_UP)


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
# เซ็ตจากผู้ใช้ที่ login อยู่เสมอ 409 ถ้ารหัส (code) ซ้ำในวิชาเดียวกัน หรือ plo_ids มีค่าซ้ำ/ไม่มีอยู่จริง
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

    plo_ids = payload.plo_ids or []
    clo = CLO(**payload.model_dump(exclude={"plo_ids"}), created_by=current_user.id)
    db.add(clo)
    db.flush()  # ต้องมี clo.id ก่อนสร้างแถว clo_plo_mapping ที่อ้างถึง
    if plo_ids:
        # เช็คเฉพาะ plo_id ที่มีอยู่จริง - ที่ไม่มีจริงปล่อยให้ IntegrityError ตอน insert ด้านล่างจัดการ
        for plo_id in plo_ids:
            plo = db.get(PLO, plo_id)
            if plo is not None:
                require_same_curriculum(clo, plo)
        even_weight = _even_weight_for(len(plo_ids))
        for plo_id in plo_ids:
            db.add(CLOPLOMapping(clo_id=clo.id, plo_id=plo_id, weight_percent=even_weight))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=(
                "CLO could not be created (duplicate code in this course, or "
                "duplicate/invalid plo_id?)"
            ),
        ) from exc
    db.refresh(clo)
    return clo


# แก้ไข CLO — instructor แก้ได้เฉพาะ CLO ของวิชาที่ตัวเองสอนอยู่ (เช็คสิทธิ์ด้านล่าง) ส่ง plo_ids มา
# จะแทนที่ชุด PLO ที่ CLO นี้ผูกอยู่ทั้งหมด (ดู docstring ของ CLOUpdateSchema) ไม่ส่ง = ไม่แตะ mapping เดิม
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
    fields = payload.model_dump(exclude_unset=True)
    plo_ids_provided = "plo_ids" in fields
    plo_ids = fields.pop("plo_ids", None)
    for field, value in fields.items():
        setattr(clo, field, value)
    if plo_ids_provided:
        db.query(CLOPLOMapping).filter(CLOPLOMapping.clo_id == clo_id).delete()
        if plo_ids:
            # เช็คเฉพาะ plo_id ที่มีอยู่จริง - ที่ไม่มีจริงปล่อยให้ IntegrityError ตอน insert ด้านล่างจัดการ
            for plo_id in plo_ids:
                plo = db.get(PLO, plo_id)
                if plo is not None:
                    require_same_curriculum(clo, plo)
            even_weight = _even_weight_for(len(plo_ids))
            for plo_id in plo_ids:
                db.add(CLOPLOMapping(clo_id=clo_id, plo_id=plo_id, weight_percent=even_weight))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="CLO could not be updated (duplicate/invalid plo_id?)",
        ) from exc
    db.refresh(clo)
    return clo


# ลบ CLO — instructor ลบได้เฉพาะ CLO ของวิชาที่ตัวเองสอนอยู่ (เช็คสิทธิ์ด้านล่าง) 409 ถ้า CLO นี้ถูกใช้
# แล้ว (ผูกกับงานประเมิน item_clo หรือผูกกับ PLO clo_plo_mapping) - กฎเดียวกันทุก role รวมแอดมินด้วย
# (ผู้ใช้ยืนยันแล้ว 2026-09-28 - เดิมลบได้เสมอแล้ว cascade ลบข้อมูลที่เกี่ยวข้องไปเงียบๆ ไม่เตือนเลย)
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

    item_clo_count = db.query(ItemCLO).filter(ItemCLO.clo_id == clo_id).count()
    plo_mapping_count = db.query(CLOPLOMapping).filter(CLOPLOMapping.clo_id == clo_id).count()
    if item_clo_count or plo_mapping_count:
        reasons = []
        if item_clo_count:
            reasons.append(f"งานประเมิน {item_clo_count} รายการ")
        if plo_mapping_count:
            reasons.append(f"PLO {plo_mapping_count} รายการ")
        raise HTTPException(
            status_code=409,
            detail=f"CLO นี้ผูกกับ {' และ '.join(reasons)} แล้ว ลบไม่ได้ - กรุณาถอดการผูกออกก่อน",
        )

    db.delete(clo)
    db.commit()
