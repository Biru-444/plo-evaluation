"""API routes for Curriculum"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Curriculum
from app.schemas import CurriculumCreateSchema, CurriculumSchema

router = APIRouter(prefix="/curricula", tags=["Curriculum"])


@router.get("", response_model=list[CurriculumSchema])
def list_curricula(db: Session = Depends(get_db)):
    return db.query(Curriculum).order_by(Curriculum.id).all()


@router.get("/{curriculum_id}", response_model=CurriculumSchema)
def get_curriculum(curriculum_id: int, db: Session = Depends(get_db)):
    curriculum = db.get(Curriculum, curriculum_id)
    if curriculum is None:
        raise HTTPException(status_code=404, detail="Curriculum not found")
    return curriculum


@router.post("", response_model=CurriculumSchema, status_code=201)
def create_curriculum(payload: CurriculumCreateSchema, db: Session = Depends(get_db)):
    curriculum = Curriculum(**payload.model_dump())
    db.add(curriculum)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Curriculum could not be created") from exc
    db.refresh(curriculum)
    return curriculum
