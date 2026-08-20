"""Pydantic schemas for YLOPLOMapping"""
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
