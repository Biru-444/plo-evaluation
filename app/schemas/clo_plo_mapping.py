"""Pydantic schemas for CLOPLOMapping

weight_percent (Workstream 3) : น้ำหนักของคู่ CLO-PLO นี้โดยเฉพาะ - CLOPLOMappingCreateSchema **ไม่มี**
field นี้โดยตั้งใจ (สร้างคู่ใหม่ = backend auto-fill เกลี่ยเท่ากันเสมอ ห้าม client ส่งค่าเอง ห้าม null -
ดู app/routes/clo_plo_mapping.py::_rebalance_clo_weights_evenly) แก้น้ำหนักทีหลังได้ผ่าน
CLOPLOMappingUpdateSchema (PUT) เท่านั้น ซึ่งแก้ได้แค่ weight_percent อย่างเดียว (เปลี่ยน clo_id/plo_id
ทำผ่าน DELETE+POST ใหม่ ไม่ใช่ PUT)"""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class CLOPLOMappingSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    clo_id: int
    plo_id: int
    weight_percent: Decimal


class CLOPLOMappingCreateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    clo_id: int
    plo_id: int


class CLOPLOMappingUpdateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    weight_percent: Decimal = Field(gt=0, le=100)


# response ของ GET /clo-plo-mapping/domain-check - เช็ค clo.domain vs plo.category ล้วนๆ (pure
# code-level, ดู app/services/domain_category_check.py) ไม่บล็อกอะไร ใช้แค่แสดงเตือน
class DomainCategoryCheckResponse(BaseModel):
    mismatch: bool
    message: str | None = None
