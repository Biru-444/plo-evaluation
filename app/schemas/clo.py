"""Pydantic schemas for CLO"""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class CLOSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    course_id: int
    code: str
    description: str
    pass_threshold_percent: Decimal
    created_by: int


class CLOCreateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    course_id: int
    code: str
    description: str
    pass_threshold_percent: Decimal = Decimal("60.00")
    created_by: int
