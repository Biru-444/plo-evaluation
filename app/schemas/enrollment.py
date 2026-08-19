"""Pydantic schemas for Enrollment"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class EnrollmentSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    student_id: str
    offering_id: int
    final_grade: str | None = None


class EnrollmentCreateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    student_id: str
    offering_id: int
    final_grade: str | None = None
