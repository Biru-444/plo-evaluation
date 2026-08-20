"""Pydantic schemas for Student"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

StudentStatus = Literal["กำลังศึกษา", "ลาออก", "พักการเรียน", "จบการศึกษา"]


class StudentSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str | None = None
    curriculum_id: int
    first_name: str
    last_name: str
    title: str | None = None
    status: StudentStatus = "กำลังศึกษา"
    cohort_year: int
    current_year_level: int


class StudentCreateSchema(BaseModel):
    """`id` (student code) has no DB default/sequence, so unlike other
    create schemas it must be supplied by the client rather than omitted."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., max_length=15)
    curriculum_id: int
    first_name: str
    last_name: str
    title: str | None = None
    status: StudentStatus = "กำลังศึกษา"
    cohort_year: int
    current_year_level: int


class StudentUpdateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    first_name: str | None = None
    last_name: str | None = None
    title: str | None = None
    status: StudentStatus | None = None
    cohort_year: int | None = None
    current_year_level: int | None = None
