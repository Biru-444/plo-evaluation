"""Pydantic schemas for CLOPLOMapping — pure join table, ไม่มี field ให้แก้ไข (จึงไม่มี
CLOPLOMappingUpdateSchema) ผูกใหม่/ถอดออกทำผ่าน POST/DELETE เท่านั้น"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class CLOPLOMappingSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    clo_id: int
    plo_id: int


class CLOPLOMappingCreateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    clo_id: int
    plo_id: int


# response ของ GET /clo-plo-mapping/domain-check - เช็ค clo.domain vs plo.category ล้วนๆ (pure
# code-level, ดู app/services/domain_category_check.py) ไม่บล็อกอะไร ใช้แค่แสดงเตือน
class DomainCategoryCheckResponse(BaseModel):
    mismatch: bool
    message: str | None = None
