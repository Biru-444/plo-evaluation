"""API routes for PLO"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_role
from app.database import get_db
from app.models import PLO
from app.schemas import PLOCreateSchema, PLOSchema, PLOUpdateSchema

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
    db.delete(plo)  # cascade ลบ ylo_plo_mapping / course_plo / clo_plo_mapping ที่อ้างถึงด้วย
    db.commit()
