"""Pydantic schemas for CLO — field ความหมายตรงกับ app/models/clo.py (pass_threshold_percent คือ
เกณฑ์ผ่านที่ใช้ตัดสินทุกจุดคำนวณในระบบ)"""
from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CLODomain = Literal["knowledge", "skills", "ethics", "character"]


class CLOSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    course_id: int
    code: str
    description: str
    pass_threshold_percent: Decimal
    domain: CLODomain | None = None
    created_by: int


class CLOCreateSchema(BaseModel):
    """`created_by` is not accepted from the client - the route sets it
    from the authenticated admin's user id. `plo_ids` (optional) ผูก CLO นี้
    กับ PLO ที่ระบุผ่าน clo_plo_mapping ในขั้นตอนเดียวกับการสร้าง CLO - ไม่ส่ง = ไม่ผูก
    (ผูก/ถอดทีหลังได้ผ่าน /clo-plo-mapping ตรงๆ)"""

    model_config = ConfigDict(from_attributes=True)

    course_id: int
    code: str
    description: str
    # จำนวนเต็มเท่านั้น 0-100
    pass_threshold_percent: int = Field(default=60, ge=0, le=100)
    plo_ids: list[int] | None = None


class CLOUpdateSchema(BaseModel):
    """`plo_ids` (optional) แทนที่ชุด PLO ที่ CLO นี้ผูกอยู่ทั้งหมดด้วยรายการที่ส่งมา (ส่ง [] = ถอด
    ออกทั้งหมด, ไม่ส่ง field นี้เลย = ไม่แตะ mapping เดิม)"""

    model_config = ConfigDict(from_attributes=True)

    description: str | None = None
    pass_threshold_percent: int | None = Field(default=None, ge=0, le=100)
    plo_ids: list[int] | None = None
