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
