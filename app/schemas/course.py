"""Pydantic schemas for Course"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class CourseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    curriculum_id: int
    course_code: str
    name_th: str
    name_en: str | None = None
    credit: int
    category: str | None = None


class CourseCreateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    curriculum_id: int
    course_code: str
    name_th: str
    name_en: str | None = None
    credit: int
    category: str | None = None


class CourseUpdateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    course_code: str | None = None
    name_th: str | None = None
    name_en: str | None = None
    credit: int | None = None
    category: str | None = None
