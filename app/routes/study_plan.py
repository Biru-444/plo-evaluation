"""
ทำอะไร : CRUD มาตรฐาน (list/get/create/update/delete) สำหรับตาราง study_plan (แผนการศึกษา — วิชาไหน
         สอนชั้นปี/เทอมไหน)

เชื่อมกับ : ข้อมูลจากตารางนี้ถูกอ่านโดย _study_plan_course_ids ใน ylo_calculation.py เพื่อตัดสินว่า
            วิชาไหน "อยู่ในปีนี้" — แก้ปี/เทอมของวิชาที่นี่กระทบการคำนวณ YLO โดยตรง

ถ้าแก้ : เฉพาะ admin เท่านั้นที่แก้ได้ — list/get เปิดให้ทุก role ดูได้
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_role
from app.database import get_db
from app.models import StudyPlan, User
from app.schemas import StudyPlanCreateSchema, StudyPlanSchema, StudyPlanUpdateSchema

router = APIRouter(prefix="/study-plan", tags=["Study Plan"])


# คืนรายการแผนการศึกษาทั้งหมด กรองตาม curriculum_id ได้
@router.get("", response_model=list[StudyPlanSchema])
def list_study_plan(
    curriculum_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(StudyPlan)
    if curriculum_id is not None:
        query = query.filter(StudyPlan.curriculum_id == curriculum_id)
    return query.order_by(StudyPlan.id).all()


# คืนแผนการศึกษารายตัวตาม id
@router.get("/{study_plan_id}", response_model=StudyPlanSchema)
def get_study_plan(
    study_plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    study_plan = db.get(StudyPlan, study_plan_id)
    if study_plan is None:
        raise HTTPException(status_code=404, detail="Study plan not found")
    return study_plan


# สร้างแผนการศึกษาใหม่ (admin เท่านั้น) — 409 ถ้าซ้ำ (curriculum+course+cohort_year เดิม) หรืออ้าง
# curriculum/course ที่ไม่มีจริง
@router.post("", response_model=StudyPlanSchema, status_code=201)
def create_study_plan(
    payload: StudyPlanCreateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    study_plan = StudyPlan(**payload.model_dump())
    db.add(study_plan)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Study plan already exists, or references an invalid curriculum/course",
        ) from exc
    db.refresh(study_plan)
    return study_plan


# แก้ไขแผนการศึกษา (admin เท่านั้น) — ส่งเฉพาะ field ที่ต้องการแก้ (exclude_unset)
@router.put("/{study_plan_id}", response_model=StudyPlanSchema)
def update_study_plan(
    study_plan_id: int,
    payload: StudyPlanUpdateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    study_plan = db.get(StudyPlan, study_plan_id)
    if study_plan is None:
        raise HTTPException(status_code=404, detail="Study plan not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(study_plan, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Study plan could not be updated") from exc
    db.refresh(study_plan)
    return study_plan


# ลบแผนการศึกษา (admin เท่านั้น)
@router.delete("/{study_plan_id}", status_code=204)
def delete_study_plan(
    study_plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    study_plan = db.get(StudyPlan, study_plan_id)
    if study_plan is None:
        raise HTTPException(status_code=404, detail="Study plan not found")
    db.delete(study_plan)
    db.commit()
