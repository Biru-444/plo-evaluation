"""Pydantic schemas for Curriculum"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CurriculumSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    name: str
    year: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CurriculumCreateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    year: int
    is_active: bool = True
