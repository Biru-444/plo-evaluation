"""API routes for YLOPLOMapping"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_role
from app.database import get_db
from app.models import YLOPLOMapping, User
from app.schemas import YLOPLOMappingCreateSchema, YLOPLOMappingSchema

router = APIRouter(prefix="/ylo-plo-mapping", tags=["YLO-PLO Mapping"])


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
