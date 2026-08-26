"""API routes for CLOPLOMapping"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import CLO, CLOPLOMapping, CourseOffering, User
from app.schemas import CLOPLOMappingCreateSchema, CLOPLOMappingSchema, CLOPLOMappingUpdateSchema

router = APIRouter(prefix="/clo-plo-mapping", tags=["CLO-PLO Mapping"])


def _require_clo_ownership(db: Session, clo_id: int, current_user: User) -> CLO:
    """เหมือน _require_offering_ownership ใน enrollment.py - แต่เช็คผ่าน CLO.course_id แทน
    admin ผ่านได้เสมอ, อาจารย์ต้องเป็นคนสอนวิชาที่ CLO นี้สังกัดอยู่เท่านั้น"""
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


@router.get("", response_model=list[CLOPLOMappingSchema])
def list_clo_plo_mappings(
    clo_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(CLOPLOMapping)
    if clo_id is not None:
        query = query.filter(CLOPLOMapping.clo_id == clo_id)
    return query.order_by(CLOPLOMapping.id).all()


@router.get("/{mapping_id}", response_model=CLOPLOMappingSchema)
def get_clo_plo_mapping(
    mapping_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    mapping = db.get(CLOPLOMapping, mapping_id)
    if mapping is None:
        raise HTTPException(status_code=404, detail="CLO-PLO mapping not found")
    return mapping


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
            detail="Mapping already exists, or references an invalid CLO/PLO",
        ) from exc
    db.refresh(mapping)
    return mapping


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
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(mapping, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="CLO-PLO mapping could not be updated"
        ) from exc
    db.refresh(mapping)
    return mapping


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
