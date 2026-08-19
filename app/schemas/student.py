"""Pydantic schemas for Student"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class StudentSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str | None = None
    curriculum_id: int
    first_name: str
    last_name: str
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
    cohort_year: int
    current_year_level: int
