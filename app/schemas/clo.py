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
    """`created_by` is not accepted from the client - the route sets it
    from the authenticated admin's user id."""

    model_config = ConfigDict(from_attributes=True)

    course_id: int
    code: str
    description: str
    pass_threshold_percent: Decimal = Decimal("60.00")


class CLOUpdateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    description: str | None = None
    pass_threshold_percent: Decimal | None = None
