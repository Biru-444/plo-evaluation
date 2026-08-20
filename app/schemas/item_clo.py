"""Pydantic schemas for ItemCLO"""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict


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
    weight_percent: Decimal


class ItemCLOUpdateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    weight_percent: Decimal | None = None
