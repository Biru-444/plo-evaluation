"""API routes for PLO"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_role
from app.database import get_db
from app.models import Course, CoursePLO, PLO
from app.schemas import (
    PLOCoursePlanItemSchema,
    PLOCreateSchema,
    PLOSchema,
    PLOUpdateSchema,
)

router = APIRouter(prefix="/plo", tags=["PLO"])


@router.get("", response_model=list[PLOSchema])
def list_plo(
    curriculum_id: int | None = None,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    query = db.query(PLO)
    if curriculum_id is not None:
        query = query.filter(PLO.curriculum_id == curriculum_id)
    return query.order_by(PLO.id).all()


@router.get("/{plo_id}", response_model=PLOSchema)
def get_plo(plo_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    plo = db.get(PLO, plo_id)
    if plo is None:
        raise HTTPException(status_code=404, detail="PLO not found")
    return plo


@router.get("/{plo_id}/course-plan", response_model=list[PLOCoursePlanItemSchema])
def get_plo_course_plan(
    plo_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """วิชาที่ผูกไว้ตอนออกแบบหลักสูตร (Curriculum Mapping, มคอ.2) ผ่าน course_plo - ใช้เกณฑ์เดียวกับ
    ที่ _build_plo_requirements ใน plo_calculation.py ใช้ตัดสินว่าวิชาไหน "เข้าเกณฑ์" ของ PLO ข้อนี้บ้าง

    เฉพาะวิชา responsibility_level='primary' เท่านั้น - วิชา 'secondary' ไม่โชว์ในบล็อกนี้ (สอดคล้องกับ
    _build_plo_requirements ใน plo_calculation.py ที่นับเฉพาะวิชา primary เป็นข้อกำหนดของ PLO เหมือนกัน)"""
    plo = db.get(PLO, plo_id)
    if plo is None:
        raise HTTPException(status_code=404, detail="PLO not found")

    rows = (
        db.query(Course.id, Course.course_code, Course.name_th, CoursePLO.responsibility_level)
        .join(CoursePLO, CoursePLO.course_id == Course.id)
        .filter(CoursePLO.plo_id == plo_id, CoursePLO.responsibility_level == "primary")
        .order_by(Course.course_code)
        .all()
    )
    return [
        PLOCoursePlanItemSchema(
            course_id=r[0], course_code=r[1], name_th=r[2], responsibility_level=r[3]
        )
        for r in rows
    ]


@router.post("", response_model=PLOSchema, status_code=201)
def create_plo(
    payload: PLOCreateSchema,
    db: Session = Depends(get_db),
    _=Depends(require_role("admin")),
):
    plo = PLO(**payload.model_dump())
    db.add(plo)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="PLO could not be created (duplicate code?)") from exc
    db.refresh(plo)
    return plo


@router.put("/{plo_id}", response_model=PLOSchema)
def update_plo(
    plo_id: int,
    payload: PLOUpdateSchema,
    db: Session = Depends(get_db),
    _=Depends(require_role("admin")),
):
    plo = db.get(PLO, plo_id)
    if plo is None:
        raise HTTPException(status_code=404, detail="PLO not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(plo, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="PLO could not be updated (duplicate code?)") from exc
    db.refresh(plo)
    return plo


@router.delete("/{plo_id}", status_code=204)
def delete_plo(plo_id: int, db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    plo = db.get(PLO, plo_id)
    if plo is None:
        raise HTTPException(status_code=404, detail="PLO not found")
    db.delete(plo)  # cascade ลบ ylo_plo_mapping / course_plo ที่อ้างถึงด้วย
    db.commit()
