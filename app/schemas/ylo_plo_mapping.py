"""Pydantic schemas for YLOPLOMapping — ไม่มี UpdateSchema เพราะ mapping มีแค่คู่ ylo_id/plo_id
เท่านั้น (ไม่มี field อื่นให้แก้ - ถ้าจะเปลี่ยนคู่ mapping ต้องลบแล้วสร้างใหม่)"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class YLOPLOMappingSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    ylo_id: int
    plo_id: int


class YLOPLOMappingCreateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ylo_id: int
    plo_id: int
