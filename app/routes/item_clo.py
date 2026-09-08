"""API routes for ItemCLO"""
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
    """Sum of weight_percent already mapped to this CLO, across all assessment
    items - used to keep each CLO's total mapped weight at or under 100%."""
    query = db.query(func.coalesce(func.sum(ItemCLO.weight_percent), 0)).filter(ItemCLO.clo_id == clo_id)
    if exclude_item_clo_id is not None:
        query = query.filter(ItemCLO.id != exclude_item_clo_id)
    return query.scalar()


@router.get("", response_model=list[ItemCLOSchema])
def list_item_clo(
    item_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(ItemCLO)
    if item_id is not None:
        query = query.filter(ItemCLO.item_id == item_id)
    return query.order_by(ItemCLO.id).all()


@router.get("/{item_clo_id}", response_model=ItemCLOSchema)
def get_item_clo(
    item_clo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item_clo = db.get(ItemCLO, item_clo_id)
    if item_clo is None:
        raise HTTPException(status_code=404, detail="Item-CLO mapping not found")
    return item_clo


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
