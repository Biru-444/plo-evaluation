"""Pydantic schemas for PLO"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class PLOSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    curriculum_id: int
    code: str
    description_th: str
    description_en: str | None = None


class PLOCreateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    curriculum_id: int
    code: str
    description_th: str
    description_en: str | None = None


class PLOUpdateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str | None = None
    description_th: str | None = None
    description_en: str | None = None


class PLOLinkedCourseSchema(BaseModel):
    """วิชาที่มี CLO ผูกกับ PLO ข้อนี้จริง (ผ่าน clo_plo_mapping) - คนละอันกับ course_plo
    (Curriculum Mapping ตอนออกแบบหลักสูตร) ไม่ขึ้นกับ cohort/รุ่นที่เข้าเรียนเพราะ CLO ผูกกับ course_id ตรงๆ"""

    model_config = ConfigDict(from_attributes=True)

    course_id: int
    course_code: str
    name_th: str
    clo_count: int


class PLOCoursePlanItemSchema(BaseModel):
    """วิชาที่ผูกไว้ตอนออกแบบหลักสูตร (มคอ.2) ผ่าน course_plo - คนละอันกับ PLOLinkedCourseSchema
    ข้างบน (clo_plo_mapping, การผูกจริงของอาจารย์ตอนสอน) ห้ามเอามาปนกัน"""

    model_config = ConfigDict(from_attributes=True)

    course_id: int
    course_code: str
    name_th: str
    responsibility_level: str
