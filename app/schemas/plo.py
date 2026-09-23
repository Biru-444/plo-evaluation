"""Pydantic schemas for PLO — field ความหมายตรงกับ app/models/plo.py ทุกตัว"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator

from app.services.code_normalize import normalize_code


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

    # normalize เสมอตอนสร้างใหม่ด้วยมือ (เว้นช่องว่าง/ตัวพิมพ์เล็ก/เลขไทยต้องไม่ทำให้รหัสซ้ำหลุดผ่านไป
    # ได้ - ดู app/services/code_normalize.py)
    @field_validator("code")
    @classmethod
    def _normalize_code(cls, v: str) -> str:
        return normalize_code(v)


class PLOUpdateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str | None = None
    description_th: str | None = None
    description_en: str | None = None
    category: str | None = None

    @field_validator("code")
    @classmethod
    def _normalize_code(cls, v: str | None) -> str | None:
        return normalize_code(v) if v is not None else v


class PLOCoursePlanItemSchema(BaseModel):
    """วิชาที่ผูกไว้ตอนออกแบบหลักสูตร (มคอ.2) ผ่าน course_plo"""

    model_config = ConfigDict(from_attributes=True)

    course_id: int
    course_code: str
    name_th: str
    responsibility_level: str
