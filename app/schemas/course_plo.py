"""Pydantic schemas for CoursePLO"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class CoursePLOSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    course_id: int
    plo_id: int
    responsibility_level: str


class CoursePLOCreateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    course_id: int
    plo_id: int
    responsibility_level: str


class CoursePLOUpdateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    responsibility_level: str | None = None
