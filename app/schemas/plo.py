"""Pydantic schemas for PLO — field ความหมายตรงกับ app/models/plo.py ทุกตัว"""
from __future__ import annotations

from decimal import Decimal

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


class PLOLinkedCourseCLOItemSchema(BaseModel):
    """CLO ตัวหนึ่งที่ผูกกับ PLO นี้โดยตรงผ่าน clo_plo_mapping - ข้อมูลย่อยของ
    PLOLinkedCourseItemSchema ด้านล่าง (1 วิชาอาจมีหลาย CLO ผูกกับ PLO เดียวกัน)"""

    clo_id: int
    clo_code: str
    # ชื่อ field ตั้งเป็น description_th เพื่อให้สื่อความหมายชัดเจนตรงกับ PLO/Course ในไฟล์นี้ - ตัวโมเดล
    # จริง (CLO.description) มีคำอธิบายภาษาเดียว (ไม่มี description_en แยก) จึงเป็นค่าเดียวกับ
    # CLO.description เป๊ะๆ ไม่ใช่คนละ field
    description_th: str
    weight_percent: Decimal


class PLOLinkedCourseItemSchema(BaseModel):
    """วิชาหนึ่งวิชาที่เชื่อมกับ PLO นี้ผ่าน CLO-PLO mapping (clo_plo_mapping) - คนละที่มากับ
    PLOCoursePlanItemSchema ด้านบน (นั่นมาจาก course_plo/มคอ.2 ซึ่งไม่ได้ใช้คำนวณผลบรรลุแล้ว ดู
    GET /plo/{plo_id}/linked-courses ใน app/routes/plo.py) - clos อาจมีมากกว่า 1 รายการถ้าวิชานี้มีหลาย
    CLO ผูกกับ PLO เดียวกัน"""

    course_id: int
    course_code: str
    course_name_th: str
    credits: int
    clos: list[PLOLinkedCourseCLOItemSchema]
