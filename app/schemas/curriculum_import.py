"""Pydantic schemas สำหรับฟีเจอร์ "นำเข้าหลักสูตร/PLO จาก มคอ.2 ด้วย AI" (Workstream 2 - ดู
แผนการแก้ไขครั้งใหญ่-PLO-CLO.md) - เลียนแบบแพทเทิร์น Phase 1/2 เดียวกับ app/schemas/course_import.py
(มคอ.3) ทุกประการ แต่ขอบเขตแคบกว่ามาก: เฉพาะ Curriculum (name, year) + PLO (code, description
th/en, category) เท่านั้น ไม่แตะ Course/CLO เลย

Phase 1 (แกะข้อมูลอย่างเดียว ไม่เขียนอะไรลง DB): CurriculumImportFromMCO2Response
Phase 2 (บันทึกจริงจากผลลัพธ์ที่แอดมินตรวจ/แก้ไขแล้วใน Phase 3): CurriculumImportSaveRequest/Response

เชื่อมกับ : CurriculumImportFromMCO2Response ตัวเดียวกันนี้ถูกส่งให้ Gemini เป็น response_schema
            (structured output) ใน app/services/mco2_import_service.py และใช้เป็น response_model
            ของ POST /curricula/import-from-mco2 ด้วย เหมือนกับที่ course_import.py ทำ

ถ้าแก้ : ต่างจาก มคอ.3 ตรงที่ Phase 1 ของ มคอ.2 **ไม่ต้องเลือกหลักสูตรเป้าหมายล่วงหน้า** เพราะตัวเอกสาร
         มคอ.2 คือเอกสารนิยามหลักสูตรเอง (ไม่ใช่วิชาย่อยที่สังกัดหลักสูตรที่มีอยู่แล้วแบบ มคอ.3) -
         existing_curriculum_id/existing_plo_codes ถูกเติมโดย backend หลัง Gemini ตอบกลับมาแล้ว (เช็ค
         จาก DB ตรงๆ ว่ามีหลักสูตรชื่อ+ปีตรงกับที่แกะได้อยู่แล้วหรือไม่ - ดู app/routes/curriculum_import.py)
         เพื่อให้หน้า Phase 3 เตือนแอดมินว่ากำลังจะ "เพิ่ม/อัปเดต PLO เข้าหลักสูตรเดิม" ไม่ใช่สร้างใหม่
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.curriculum import CurriculumSchema
from app.schemas.plo import PLOSchema
from app.services.code_normalize import normalize_code


# ต้องตรงกับ PLO_CATEGORY_OPTIONS ใน plo-frontend/src/pages/admin/AdminPLO.jsx เป๊ะ (ค่าที่เก็บจริงใน
# plo.category เป็นคำไทยล้วน ไม่ใช่ enum ภาษาอังกฤษแบบ clo.domain) - เปลี่ยนฝั่งใดฝั่งหนึ่งแล้วไม่แก้อีก
# ฝั่ง Gemini จะแม็ปหมวดหมู่ผิดเงียบๆ
MCO2PLOCategory = Literal["ความรู้", "ทักษะ", "จริยธรรม", "ลักษณะบุคคล"]


class MCO2PLOItem(BaseModel):
    code: str
    description_th: str
    description_en: str | None = None
    # หมวดหมู่ของ PLO ข้อนี้ - null ถ้าเอกสารไม่ได้ระบุชัดเจนพอจะแม็ปเข้า 4 ค่านี้ได้ตรงๆ (ห้ามเดา
    # เหมือนกฎเดียวกับ clo.domain ใน มคอ.3)
    category: MCO2PLOCategory | None = None

    # normalize ทั้ง Phase 1 (แสดงผล) และ Phase 2 (บันทึกจริง - schema เดียวกัน) - บั๊กจริงที่เจอ
    # 2026-09-23: มคอ.2 เคยบันทึก "PLO 1".."PLO 9" (มีช่องว่าง) ทำให้ มคอ.3 extraction ที่คืน "PLO4"
    # (ไม่มีช่องว่าง) จับคู่ไม่ติด - ดู app/services/code_normalize.py
    @field_validator("code")
    @classmethod
    def _normalize_code(cls, v: str) -> str:
        return normalize_code(v)


MCO2FlagType = Literal[
    "duplicate_plo_code",
    "category_unclear",
    "other",
]


class MCO2ImportFlag(BaseModel):
    type: MCO2FlagType
    message: str


class CurriculumImportFromMCO2Response(BaseModel):
    curriculum_name: str
    curriculum_year: int
    plos: list[MCO2PLOItem] = Field(default_factory=list)
    flags: list[MCO2ImportFlag] = Field(default_factory=list)
    # เติมทีหลังโดย backend เอง (pure code-level เช็คจาก DB ตรงๆ ไม่ใช่ Gemini ตัดสิน) - มีหลักสูตรที่
    # ชื่อ+ปีตรงกับที่แกะได้อยู่แล้วหรือไม่ ถ้ามี ให้รายการ code ของ PLO ที่มีอยู่แล้วในหลักสูตรนั้นมาด้วย
    # เพื่อให้หน้า Phase 3 บอกแอดมินได้ว่า code ไหนจะเป็น "อัปเดต" vs "สร้างใหม่"
    existing_curriculum_id: int | None = None
    existing_plo_codes: list[str] = Field(default_factory=list)


class CurriculumImportSaveRequest(BaseModel):
    """ร่างคำขอบันทึกจริงของ Phase 2 - รับข้อมูลที่แอดมินตรวจ/แก้ไขแล้วในหน้า Phase 3

    curriculum_id: None = สร้างหลักสูตรใหม่ (จาก curriculum_name/curriculum_year ที่ให้มา) / ไม่ None =
    ใช้หลักสูตรที่มีอยู่แล้วนี้ - ไม่แตะ name/year ของหลักสูตรเดิมเลย (แค่ใช้ id อ้างอิง) แล้ว upsert
    PLO ทีละตัวตาม code: code ที่มีอยู่แล้วในหลักสูตรนั้น = อัปเดต description/category, code ใหม่ = สร้าง
    """

    curriculum_id: int | None = None
    curriculum_name: str
    curriculum_year: int
    plos: list[MCO2PLOItem] = Field(default_factory=list)


class CurriculumImportSaveResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    curriculum: CurriculumSchema
    plos: list[PLOSchema]
    created_plo_codes: list[str]
    updated_plo_codes: list[str]
