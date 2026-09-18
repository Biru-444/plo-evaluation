"""Pydantic schemas for StudyPlan — field ความหมายตรงกับ app/models/study_plan.py ทุกตัว
(cohort_year เป็น None = แผนมาตรฐาน ดูรายละเอียดที่ model)"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class StudyPlanSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    curriculum_id: int
    course_id: int
    cohort_year: int | None = None
    year_level: int
    semester: int


class StudyPlanCreateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    curriculum_id: int
    course_id: int
    cohort_year: int | None = None
    year_level: int
    semester: int


class StudyPlanUpdateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    cohort_year: int | None = None
    year_level: int | None = None
    semester: int | None = None
