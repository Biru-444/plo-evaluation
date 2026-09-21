"""Pydantic schemas for PLO — field ความหมายตรงกับ app/models/plo.py ทุกตัว"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class PLOSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    curriculum_id: int
    code: str
    description_th: str
    description_en: str | None = None
    category: str


class PLOCreateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    curriculum_id: int
    code: str
    description_th: str
    description_en: str | None = None
    category: str


class PLOUpdateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str | None = None
    description_th: str | None = None
    description_en: str | None = None
    category: str | None = None


class PLOCoursePlanItemSchema(BaseModel):
    """วิชาที่ผูกไว้ตอนออกแบบหลักสูตร (มคอ.2) ผ่าน course_plo"""

    model_config = ConfigDict(from_attributes=True)

    course_id: int
    course_code: str
    name_th: str
    responsibility_level: str
