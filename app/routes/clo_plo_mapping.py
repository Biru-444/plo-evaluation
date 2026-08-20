"""API routes for CLOPLOMapping"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_role
from app.database import get_db
from app.models import CLOPLOMapping, User
from app.schemas import CLOPLOMappingCreateSchema, CLOPLOMappingSchema, CLOPLOMappingUpdateSchema

router = APIRouter(prefix="/clo-plo-mapping", tags=["CLO-PLO Mapping"])


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
    current_user: User = Depends(require_role("admin")),
):
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
    current_user: User = Depends(require_role("admin")),
):
    mapping = db.get(CLOPLOMapping, mapping_id)
    if mapping is None:
        raise HTTPException(status_code=404, detail="CLO-PLO mapping not found")
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
    current_user: User = Depends(require_role("admin")),
):
    mapping = db.get(CLOPLOMapping, mapping_id)
    if mapping is None:
        raise HTTPException(status_code=404, detail="CLO-PLO mapping not found")
    db.delete(mapping)
    db.commit()
