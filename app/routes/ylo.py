"""API routes for YLO"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_role
from app.database import get_db
from app.models import YLO, User
from app.schemas import YLOCreateSchema, YLOSchema, YLOUpdateSchema

router = APIRouter(prefix="/ylo", tags=["YLO"])


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
