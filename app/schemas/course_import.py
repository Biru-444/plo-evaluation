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


MCO3CLODomain = Literal["knowledge", "skills", "ethics", "character"]


class MCO3CLOItem(BaseModel):
    code: str
    description: str
    # โดเมนการเรียนรู้ของ CLO ข้อนี้ (มักกำกับด้วย (K)/(S)/(A)/(C) ในเอกสาร) - null ถ้าเอกสารไม่ได้
    # ระบุไว้ชัดเจนพอจะแม็ปเข้า 4 ค่านี้ได้ตรงๆ (ห้ามเดา เหมือนกฎ checkbox_ambiguous) เก็บคู่กับ
    # clo.domain ที่เพิ่มไว้แล้วใน migrate_add_clo_domain.py
    domain: MCO3CLODomain | None = None


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
    # แสดงอ้างอิงในหน้าตรวจสอบเท่านั้น - Phase 2 (endpoint บันทึกจริง) ต้องไม่รับ/ไม่ใช้ 2 ฟิลด์นี้
    # เลย เพราะไม่มีที่เก็บใน course (ข้อมูลนี้เป็นของ course_offering/study_plan คนละ layer)
    instructor_name: str | None = None
    semester_display: str | None = None
    flags: list[MCO3ImportFlag] = Field(default_factory=list)
