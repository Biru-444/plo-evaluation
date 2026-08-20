"""Pydantic schemas for CLOPLOMapping"""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict


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
    weight_percent: Decimal


class CLOPLOMappingUpdateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    weight_percent: Decimal | None = None
