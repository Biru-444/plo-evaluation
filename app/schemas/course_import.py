"""Pydantic schemas สำหรับฟีเจอร์ "นำเข้าข้อมูลวิชาจาก มคอ.3 ด้วย AI" (Phase 1: แกะข้อมูลอย่างเดียว
ไม่เขียนอะไรลง DB)

เชื่อมกับ : CourseImportFromMCO3Response ตัวเดียวกันนี้ถูกส่งให้ Gemini เป็น response_schema
            (structured output) ใน app/services/mco3_import_service.py และใช้เป็น response_model
            ของ POST /courses/import-from-mco3 ด้วย - เป็น single source of truth เดียวระหว่าง
            "รูปแบบที่บอกโมเดลให้ตอบ" กับ "contract ที่ frontend ได้รับกลับจริง" กันไม่ให้สอง
            ฝั่ง drift ไม่ตรงกัน

ถ้าแก้ : เพิ่ม field ใหม่ต้องคิดด้วยว่า Gemini จะรู้ได้ยังไงว่าต้องกรอกอะไร (ดู system instruction ใน
         mco3_import_service.py ที่อธิบาย field พวกนี้เป็นภาษาไทยให้โมเดลอ่าน)
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class MCO3CLOItem(BaseModel):
    code: str
    description: str


class MCO3CLOPLOMappingItem(BaseModel):
    clo_code: str
    plo_code: str


MCO3FlagType = Literal[
    "category_mismatch",
    "checkbox_ambiguous",
    "duplicate_course_code",
    "curriculum_mismatch",
    "other",
]


class MCO3ImportFlag(BaseModel):
    type: MCO3FlagType
    message: str


class CourseImportFromMCO3Response(BaseModel):
    course_code: str
    name_th: str
    name_en: str | None = None
    credit: int
    category_raw: str
    category_mapped: str | None = None
    clos: list[MCO3CLOItem] = Field(default_factory=list)
    clo_plo_mapping: list[MCO3CLOPLOMappingItem] = Field(default_factory=list)
    flags: list[MCO3ImportFlag] = Field(default_factory=list)
