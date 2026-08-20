"""API routes for Curriculum"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_role
from app.database import get_db
from app.models import Curriculum, User
from app.schemas import CurriculumCreateSchema, CurriculumSchema, CurriculumUpdateSchema

router = APIRouter(prefix="/curricula", tags=["Curriculum"])


@router.get("", response_model=list[CurriculumSchema])
def list_curricula(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(Curriculum).order_by(Curriculum.id).all()


@router.get("/{curriculum_id}", response_model=CurriculumSchema)
def get_curriculum(
    curriculum_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    curriculum = db.get(Curriculum, curriculum_id)
    if curriculum is None:
        raise HTTPException(status_code=404, detail="Curriculum not found")
    return curriculum


@router.post("", response_model=CurriculumSchema, status_code=201)
def create_curriculum(
    payload: CurriculumCreateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    curriculum = Curriculum(**payload.model_dump())
    db.add(curriculum)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Curriculum could not be created") from exc
    db.refresh(curriculum)
    return curriculum


@router.put("/{curriculum_id}", response_model=CurriculumSchema)
def update_curriculum(
    curriculum_id: int,
    payload: CurriculumUpdateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    curriculum = db.get(Curriculum, curriculum_id)
    if curriculum is None:
        raise HTTPException(status_code=404, detail="Curriculum not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(curriculum, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Curriculum could not be updated") from exc
    db.refresh(curriculum)
    return curriculum


@router.delete("/{curriculum_id}", status_code=204)
def delete_curriculum(
    curriculum_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """DANGEROUS: cascades to every PLO, YLO, course, and study plan under this
    curriculum (see ondelete="CASCADE" on their curriculum_id FKs) - deleting a
    curriculum wipes most of its subtree, not just the row itself. Student.curriculum_id
    is ondelete="RESTRICT" though, so the delete is blocked (409) while students
    still reference this curriculum."""
    curriculum = db.get(Curriculum, curriculum_id)
    if curriculum is None:
        raise HTTPException(status_code=404, detail="Curriculum not found")
    try:
        db.delete(curriculum)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Curriculum could not be deleted - students still reference it",
        ) from exc
