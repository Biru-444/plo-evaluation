"""API routes for ItemCLO"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import AssessmentItem, CourseOffering, ItemCLO, User
from app.schemas import ItemCLOCreateSchema, ItemCLOSchema, ItemCLOUpdateSchema

router = APIRouter(prefix="/item-clo", tags=["Item-CLO Mapping"])


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
    for field, value in payload.model_dump(exclude_unset=True).items():
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
