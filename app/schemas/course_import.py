"""Pydantic schemas สำหรับฟีเจอร์ "นำเข้าข้อมูลวิชาจาก มคอ.3 ด้วย AI"

Phase 1 (แกะข้อมูลอย่างเดียว ไม่เขียนอะไรลง DB): CourseImportFromMCO3Response
Phase 2 (บันทึกจริงจากผลลัพธ์ที่แอดมินตรวจ/แก้ไขแล้วใน Phase 3): CourseImportSaveRequest/Response

เชื่อมกับ : CourseImportFromMCO3Response ตัวเดียวกันนี้ถูกส่งให้ Gemini เป็น response_schema
            (structured output) ใน app/services/mco3_import_service.py และใช้เป็น response_model
            ของ POST /courses/import-from-mco3 ด้วย - เป็น single source of truth เดียวระหว่าง
            "รูปแบบที่บอกโมเดลให้ตอบ" กับ "contract ที่ frontend ได้รับกลับจริง" กันไม่ให้สอง
            ฝั่ง drift ไม่ตรงกัน - CourseImportSaveRequest ใช้ MCO3CLOItem ร่วมกับ Phase 1 (โครงเดียวกัน
            เป๊ะ) แต่ clo_plo_mapping ใช้ MCO3CLOPLOMappingSaveItem แยกต่างหาก (เพิ่ม weight_percent -
            Workstream 3 - ที่ Phase 1/Gemini ไม่รู้จักเลย ดู docstring ของ 2 คลาสนั้น) และไม่มี
            category_raw/instructor_name/semester_display/flags เพราะ field พวกนี้เป็นข้อมูลสำหรับ
            "หน้าตรวจสอบ" เท่านั้น ไม่มีที่เก็บถาวร (ดู app/routes/course_import.py POST
            /courses/import-from-mco3/save)

ถ้าแก้ : เพิ่ม field ใหม่ใน CourseImportFromMCO3Response ต้องคิดด้วยว่า Gemini จะรู้ได้ยังไงว่าต้อง
         กรอกอะไร (ดู system instruction ใน mco3_import_service.py ที่อธิบาย field พวกนี้เป็นภาษาไทย
         ให้โมเดลอ่าน) - เพิ่ม field ใหม่ใน CourseImportSaveRequest ต้องเช็คด้วยว่า Course/CLO model
         มีคอลัมน์รองรับจริง (ดู app/models/course.py, app/models/clo.py)
"""
from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.clo import CLOSchema
from app.schemas.course import CourseSchema


MCO3CLODomain = Literal["knowledge", "skills", "ethics", "character"]


class MCO3CLOItem(BaseModel):
    code: str
    description: str
    # โดเมนการเรียนรู้ของ CLO ข้อนี้ (มักกำกับด้วย (K)/(S)/(A)/(C) ในเอกสาร) - null ถ้าเอกสารไม่ได้
    # ระบุไว้ชัดเจนพอจะแม็ปเข้า 4 ค่านี้ได้ตรงๆ (ห้ามเดา เหมือนกฎ checkbox_ambiguous) เก็บคู่กับ
    # clo.domain ที่เพิ่มไว้แล้วใน migrate_add_clo_domain.py
    domain: MCO3CLODomain | None = None


class MCO3CLOPLOMappingItem(BaseModel):
    """เฉพาะ Phase 1 (ผลลัพธ์ดิบจาก Gemini) - ไม่มี weight_percent เพราะ Gemini บอกได้แค่ว่า CLO ข้อไหน
    "เกี่ยวข้อง" กับ PLO ข้อไหน ไม่ใช่ "สำคัญแค่ไหน" (ดู MCO3CLOPLOMappingSaveItem สำหรับ Phase 2)"""

    clo_code: str
    plo_code: str


class MCO3CLOPLOMappingSaveItem(BaseModel):
    """เฉพาะ Phase 2 (คำขอบันทึกจริง) - เพิ่ม weight_percent ของคู่นี้ (Workstream 3) ที่หน้า Phase 3
    (AdminCourseImportMCO3.jsx) auto-fill เกลี่ยเท่ากันต่อ CLO ให้เองฝั่ง client ตอนติ๊ก/ถอด PLO แต่ละ
    ข้อ แล้วค่อยส่งมาที่นี่ตอนกด "ยืนยันบันทึก" - ต้องมีค่าเสมอ (NOT NULL ที่ DB ด้วย)"""

    clo_code: str
    plo_code: str
    weight_percent: Decimal = Field(gt=0, le=100)


MCO3FlagType = Literal[
    "category_mismatch",
    "checkbox_ambiguous",
    "duplicate_course_code",
    "curriculum_mismatch",
    "title_content_mismatch",
    "plo_mapping_not_filled",
    "domain_category_mismatch",
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


class CourseImportSaveRequest(BaseModel):
    """ร่างคำขอบันทึกจริงของ Phase 2 - รับข้อมูลที่แอดมินตรวจ/แก้ไขแล้วในหน้า Phase 3 (ไม่ใช่ไฟล์ดิบ
    อีกต่อไป ไม่เรียก Gemini ซ้ำ) category เป็นค่าสุดท้ายที่แอดมินตัดสินใจแล้ว (ไม่มี category_raw/
    category_mapped แยกกันเหมือน Phase 1 เพราะนั่นเป็นข้อมูลช่วยตัดสินใจตอนตรวจ ไม่ใช่ข้อมูลที่ต้องเก็บ)
    ไม่มี instructor_name/semester_display/flags เพราะไม่มีที่เก็บถาวรและไม่ต้องเก็บเป็น audit trail
    (ตามที่ผู้ใช้ยืนยัน 2026-09-22) - curriculum_mismatch ที่แอดมินเห็น warning แล้วยังกดบันทึกต่อ ก็
    ไม่ถูกเช็คซ้ำที่นี่เช่นกัน (แอดมินตัดสินใจแล้วตอนตรวจ ไม่ block)"""

    curriculum_id: int
    course_code: str
    name_th: str
    name_en: str | None = None
    credit: int
    category: str | None = None
    clos: list[MCO3CLOItem] = Field(default_factory=list)
    clo_plo_mapping: list[MCO3CLOPLOMappingSaveItem] = Field(default_factory=list)


class CourseImportSaveResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    course: CourseSchema
    clos: list[CLOSchema]
