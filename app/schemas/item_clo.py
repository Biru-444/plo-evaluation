"""Pydantic schemas for ItemCLO"""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ItemCLOSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    item_id: int
    clo_id: int
    weight_percent: Decimal


class ItemCLOCreateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    item_id: int
    clo_id: int
    # จำนวนเต็มเท่านั้น 0-100 (ผลรวมต่อ CLO ต้องไม่เกิน 100% - เช็คแยกใน route)
    weight_percent: int = Field(ge=0, le=100)


class ItemCLOUpdateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    weight_percent: int | None = Field(default=None, ge=0, le=100)
